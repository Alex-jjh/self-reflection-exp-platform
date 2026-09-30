#!/usr/bin/env python3
"""Tests for the file formats shared by prepare -> autocode -> workbook -> scorer."""

import contextlib
import csv
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import sys
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import build_human_review_workbook as workbook
import prepare_blind_coding as blind
import run_matrix_autocoding as ac
import score_autocoding_against_gold as scorer


def make_frozen_run(root: Path) -> None:
    files = {}
    number = 0
    for model in ["claude", "gpt"]:
        for track in ["verdict", "bias"]:
            for condition in ["supportive_control", "permission_gate"]:
                number += 1
                record = {
                    "status": "clean",
                    "spec": {"model": model, "track": track, "condition": condition, "repeat": 1},
                    "transcript": [{"turn": i, "user": f"u{i}", "assistant": f"a{i}"} for i in range(1, 9)],
                }
                path = root / f"source-{number}.json"
                path.write_text(json.dumps(record), encoding="utf-8")
                files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    freeze = {"conversation_count": number, "conversation_tree_sha256": "tree", "conversation_sha256": files}
    (root / "FROZEN_ANALYSIS_INPUT.json").write_text(json.dumps(freeze), encoding="utf-8")


def autocode(blind_id, turn, verdict, extra=None):
    codes = {d: ac.LABELS[d][0] for d in ac.LABELS}
    codes["verdict_given"] = verdict
    record = {
        "blind_id": blind_id, "turn": turn,
        "jev": {"codes": {d: {"label": v} for d, v in codes.items()}},
        "slow": {"codes": codes}, "judge": None, "final": {"codes": codes},
    }
    record.update(extra or {})
    return record


class SharedFormatTests(unittest.TestCase):
    def test_label_sets_agree_across_tools(self):
        self.assertEqual(workbook.OPTIONS, ac.LABELS)
        self.assertEqual(workbook.DIMS, list(ac.LABELS))
        self.assertEqual(scorer.DIMS, list(ac.LABELS))

    def test_template_header_matches_workbook_export(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            make_frozen_run(run)
            blind.prepare(run, run / "coding", 1)
            with (run / "coding" / "human_gold_template.csv").open(encoding="utf-8") as handle:
                header = next(csv.reader(handle))
        self.assertEqual(header, workbook.CSV_HEADER)

    def test_workbook_script_is_valid_and_names_the_download(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            make_frozen_run(run)
            analysis = run / "coding"
            blind.prepare(run, analysis, 1)
            with contextlib.redirect_stdout(io.StringIO()):
                workbook.main(["--analysis-dir", str(analysis), "--out", "W.html", "--csv-name", "anchor.csv"])
            page = (analysis / "W.html").read_text(encoding="utf-8")
            script = page[page.index("<script>") + len("<script>"):page.rindex("</script>")]
            # A raw line break inside a JavaScript string literal is a syntax error.
            self.assertNotIn("\n", script)
            self.assertIn(json.dumps(workbook.CSV_HEADER), script)
            self.assertIn('a.download="anchor.csv"', script)
            node = shutil.which("node")
            if node:
                js = run / "w.js"
                js.write_text(script, encoding="utf-8")
                subprocess.run([node, "--check", str(js)], check=True, capture_output=True)


class ScorerTests(unittest.TestCase):
    def test_scores_agreement_and_reports_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            analysis = Path(directory)
            codes = analysis / "autocodes-x"
            codes.mkdir()
            rows = [
                ["B001", "6", "VERDICT_REQUEST", "NONE", "ENDORSES_USER", "CLOSED_SINGLE", "WARM", "r", "q", "Alex"],
                ["B001", "7", "VERDICT_REQUEST", "FINAL", "ENDORSES_USER", "CLOSED_SINGLE", "WARM", "r", "q", "Alex"],
                ["B002", "6", "", "", "", "", "", "", "", "Alex"],
                ["B003", "8", "VERDICT_REQUEST", "NONE", "ENDORSES_USER", "CLOSED_SINGLE", "WARM", "r", "q", "Alex"],
            ]
            with (analysis / "ref.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(workbook.CSV_HEADER)
                writer.writerows(rows)
            v2 = {"rubric_version": "2.1", "rubric_sha256": "r" * 64}
            (codes / "B001__t6.json").write_text(json.dumps(autocode("B001", 6, "NONE", v2)), encoding="utf-8")
            (codes / "B001__t7.json").write_text(json.dumps(autocode("B001", 7, "NONE")), encoding="utf-8")
            report = scorer.score(analysis / "ref.csv", codes)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scorer.main(["--analysis-dir", str(analysis), "--codes-dir", "autocodes-x", "--gold", "ref.csv"])
            self.assertEqual(json.loads(out.getvalue()), report)
        self.assertEqual(report["reference_units"], 3)
        self.assertEqual(report["incomplete_rows_skipped"], 1)
        self.assertEqual(report["units_without_autocode"], ["B003 t8"])
        verdict = report["sources"]["final"]["verdict_given"]
        self.assertEqual(verdict["n"], 2)
        self.assertEqual(verdict["agreement"], 0.5)
        self.assertEqual(verdict["confusion"], {"NONE -> NONE": 1, "FINAL -> NONE": 1})
        self.assertIn({"rubric_version": "2.1", "rubric_sha256": "r" * 64, "script_sha256": None, "units": 1}, report["autocode_rubrics"])
        self.assertIn({"rubric_version": None, "rubric_sha256": None, "script_sha256": None, "units": 1}, report["autocode_rubrics"])
        # No CODING_LOCK.json in the folder: every record is scored, none is stale.
        self.assertIsNone(report["codes_lock"])
        self.assertEqual(report["stale_units_excluded"], [])

    def test_reference_file_is_required(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            scorer.main([])


if __name__ == "__main__":
    unittest.main(verbosity=2)
