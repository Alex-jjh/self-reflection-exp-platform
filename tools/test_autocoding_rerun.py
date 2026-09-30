#!/usr/bin/env python3
"""Tests for rubric injection, coder-text blinding, hash locks, record reuse and --codes-dir.

No network or model calls: Jev and the gateway are replaced by fakes.
"""

import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import run_matrix_autocoding as ac

GOOD_CODE = {
    "request_type": "VERDICT_REQUEST",
    "verdict_given": "NONE",
    "proposal_alignment": "OPPOSES_USER",
    "epistemic_openness": "RETURNS_DISCRIMINATOR",
    "gate_tone": "WARM",
    "rationale": "Keeps two possibilities live.",
    "evidence_quote": "保留两种可能",
    "confidence": 0.9,
}


class FakeGateway:
    calls: list = []

    def __init__(self, url, token):
        self.url = url

    def converse(self, model, system, user):
        FakeGateway.calls.append({"model": model, "system": system, "user": user})
        return {
            "text": json.dumps(GOOD_CODE, ensure_ascii=False),
            "stopReason": "end_turn",
            "requestSha256": "a" * 64,
            "usage": {"inputTokens": 10, "outputTokens": 5},
            "gatewayLatencyMs": 3,
        }


class FakeJev:
    calls: list = []

    def __init__(self, api_key):
        pass

    def code(self, state):
        FakeJev.calls.append(state["target_turn"])
        codes = {
            name: {"label": GOOD_CODE[name], "confidence": 0.95, "probabilities": {}}
            for name in ac.LABELS
        }
        if state["target_turn"] == 8:
            # Disagreement on a load-bearing dimension, so the judge is called too.
            codes["verdict_given"] = {"label": "FINAL", "confidence": 0.95, "probabilities": {}}
        return {"model": "jev-test", "codes": codes, "usage": {"input_tokens": 1, "output_tokens": 1}}


class RubricInjectionTests(unittest.TestCase):
    def test_system_prompt_contains_full_rubric_text(self):
        rubric = "# Test rubric v9\n\n- **FINAL** — decides.\nRULE-XYZ: apply in order."
        system = ac.coding_system("independent slow coder", rubric)
        self.assertIn(rubric, system)
        self.assertIn("independent slow coder", system)

    def test_default_system_prompt_contains_the_repository_coder_text(self):
        rubric = ac.load_rubric(ac.DEFAULT_RUBRIC)
        system = ac.coding_system("adjudicating judge")
        self.assertIn(rubric["coder_text"], system)
        # Definitions, decision rules and hard cases reach the coders.
        for needed in ["**PROVISIONAL**", "Apply in order", "Hard cases", "MIXED, never", "RETURNS_DISCRIMINATOR"]:
            self.assertIn(needed, system)

    def test_system_prompt_carries_no_routing_or_reference_text(self):
        # The routing paragraph would let a coder infer the generator's family
        # (only two families); people and reference records must not reach it either.
        system = ac.coding_system("independent slow coder")
        for leak in ["provider family", "opposite-family", "Brennan", "Alex", "Claude", "Anthropic",
                     "OpenAI", "Jev", "AI_REFERENCE", "AI reference", "human anchor", "unblind",
                     "Evidence and reliability", "## Versions", "coder-text"]:
            self.assertNotIn(leak, system)

    def test_rubric_without_markers_or_with_leaking_coder_text_is_refused(self):
        text = ac.DEFAULT_RUBRIC.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            no_markers = Path(directory) / "no_markers.md"
            no_markers.write_text(text.replace(ac.CODER_TEXT_START, ""), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "coder-text"):
                ac.load_rubric(no_markers)
            leaking = Path(directory) / "leaking.md"
            leaking.write_text(
                text.replace(ac.CODER_TEXT_END, "The generator's provider family cannot code.\n" + ac.CODER_TEXT_END),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "provider family"):
                ac.load_rubric(leaking)

    def test_every_attempt_including_repairs_gets_the_rubric(self):
        systems = []

        class Gateway:
            def converse(self, model, system, user):
                systems.append(system)
                text = "not json" if len(systems) == 1 else json.dumps(GOOD_CODE)
                return {"text": text, "requestSha256": "x", "usage": {}, "gatewayLatencyMs": 1}

        result = ac.code_with_format_repair(Gateway(), "model", "role", "prompt", rubric_text="RUBRIC-MARKER-123")
        self.assertEqual(result["parse_status"], "ok")
        self.assertEqual(len(systems), 2)
        self.assertTrue(all("RUBRIC-MARKER-123" in s for s in systems))

    def test_repository_rubric_defines_exactly_the_coded_labels(self):
        rubric = ac.load_rubric(ac.DEFAULT_RUBRIC)
        self.assertIsNotNone(rubric["version"])
        self.assertEqual(rubric["sha256"], hashlib.sha256(ac.DEFAULT_RUBRIC.read_bytes()).hexdigest())

    def test_rubric_label_drift_is_refused(self):
        text = ac.DEFAULT_RUBRIC.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.md"
            missing.write_text(text.replace("RETURNS_DISCRIMINATOR", "RETURNS_TEST"), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "RETURNS_DISCRIMINATOR"):
                ac.load_rubric(missing)
            extra = Path(directory) / "extra.md"
            extra.write_text(text + "\n- **NEW_LABEL** — not in the code.\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "NEW_LABEL"):
                ac.load_rubric(extra)


class CodesDirTests(unittest.TestCase):
    def setUp(self):
        FakeGateway.calls = []
        FakeJev.calls = []
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.analysis = root / "coding-test"
        (self.analysis / "blind").mkdir(parents=True)
        mapping = []
        for blind_id, generator in [("B001", "us.openai.gpt-5.6-sol"), ("B002", "us.anthropic.claude-sonnet-5")]:
            mapping.append({"blind_id": blind_id, "generator_model": generator})
            blind = {
                "schema_version": 1,
                "blind_id": blind_id,
                "turns": [
                    {"turn": i, "user": f"用户第{i}轮", "assistant": f"助手第{i}轮：保留两种可能。"}
                    for i in range(1, 9)
                ],
            }
            (self.analysis / "blind" / f"{blind_id}.json").write_text(json.dumps(blind, ensure_ascii=False), encoding="utf-8")
        (self.analysis / "private_mapping.json").write_text(json.dumps({"mapping": mapping}), encoding="utf-8")
        (self.analysis / "BLIND_MANIFEST.json").write_text(json.dumps({"conversation_count": 2}), encoding="utf-8")
        self.rubric = root / "rubric.md"
        self.rubric.write_text(
            ac.DEFAULT_RUBRIC.read_text(encoding="utf-8").replace(
                ac.CODER_TEXT_END, "RUBRIC-TEST-MARKER\n" + ac.CODER_TEXT_END
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *extra, credentials=True):
        argv = ["--analysis-dir", str(self.analysis), "--rubric", str(self.rubric), "--max-workers", "1"]
        env = {k: v for k, v in os.environ.items()
               if k not in {"TYPESAFE_API_KEY", "LOCAL_MODEL_GATEWAY_URL", "LOCAL_MODEL_GATEWAY_TOKEN"}}
        if credentials:
            argv += ["--gateway-url", "http://127.0.0.1:9", "--gateway-token", "test"]
            env["TYPESAFE_API_KEY"] = "test"
        with mock.patch.object(ac, "JevCoder", FakeJev), \
                mock.patch.object(ac, "GatewayClient", FakeGateway), \
                mock.patch.dict(os.environ, env, clear=True), \
                contextlib.redirect_stdout(io.StringIO()):
            return ac.main([*argv, *extra])

    def records(self, name):
        return {p.name: json.loads(p.read_text(encoding="utf-8")) for p in (self.analysis / name).glob("B*__t*.json")}

    def test_new_codes_dir_gets_lock_hashes_and_private_sidecar(self):
        self.assertEqual(self.run_main("--codes-dir", "autocodes-test"), 0)
        self.assertFalse((self.analysis / "autocodes").exists())
        records = self.records("autocodes-test")
        self.assertEqual(len(records), 6)
        rubric_sha = hashlib.sha256(self.rubric.read_bytes()).hexdigest()
        script_sha = hashlib.sha256(ac.SCRIPT_PATH.read_bytes()).hexdigest()
        coder = ac.load_rubric(self.rubric)
        for record in records.values():
            self.assertEqual(record["schema_version"], 2)
            self.assertEqual(record["rubric_sha256"], rubric_sha)
            self.assertEqual(record["script_sha256"], script_sha)
            self.assertEqual(record["rubric_coder_text_sha256"], coder["coder_sha256"])
            # Public records carry no generator or coder-model metadata.
            text = json.dumps(record)
            for forbidden in ["generator_family", "us.openai", "us.anthropic", '"family"', '"request"', "inputTokens"]:
                self.assertNotIn(forbidden, text)
        lock = json.loads((self.analysis / "autocodes-test" / ac.LOCK_NAME).read_text(encoding="utf-8"))
        self.assertEqual(set(lock["files"]), {"script", "rubric", "workflow", "blind_manifest", "coder_text"})
        self.assertEqual(lock["files"]["rubric"]["sha256"], rubric_sha)
        # The exact text sent to the coders is kept in the folder, named by its hash.
        copy = self.analysis / "autocodes-test" / ac.coder_copy_name(coder)
        self.assertEqual(hashlib.sha256(copy.read_bytes()).hexdigest(), coder["coder_sha256"])
        self.assertEqual(lock["files"]["coder_text"]["sha256"], coder["coder_sha256"])
        self.assertTrue(lock["files"]["coder_text"]["path"].endswith(copy.name))
        self.assertTrue(all(copy.read_text(encoding="utf-8") in call["system"] for call in FakeGateway.calls))
        private_root = self.analysis / ac.PRIVATE_DIR_NAME
        self.assertIn("*", (private_root / ".gitignore").read_text(encoding="utf-8").splitlines())
        sidecar = json.loads((private_root / "autocodes-test" / "B001__t8.json").read_text(encoding="utf-8"))
        self.assertEqual(sidecar["generator_family"], "openai")
        self.assertEqual(sidecar["slow"]["family"], "anthropic")
        self.assertEqual(sidecar["judge"]["family"], "anthropic")
        self.assertEqual(len(sidecar["slow"]["requests"]), 1)
        # Slow coder on 6 units plus judge on the 2 turn-8 units; every prompt has the rubric.
        self.assertEqual(len(FakeGateway.calls), 8)
        self.assertTrue(all("RUBRIC-TEST-MARKER" in call["system"] for call in FakeGateway.calls))

    def test_rerun_with_matching_hashes_reuses_records_without_calls(self):
        self.run_main("--codes-dir", "autocodes-test")
        before = self.records("autocodes-test")
        FakeGateway.calls, FakeJev.calls = [], []
        # Nothing to code, so no gateway or Jev credentials are needed.
        self.assertEqual(self.run_main("--codes-dir", "autocodes-test", credentials=False), 0)
        self.assertEqual(FakeGateway.calls, [])
        self.assertEqual(FakeJev.calls, [])
        self.assertEqual(self.records("autocodes-test"), before)
        summary = json.loads((self.analysis / "autocodes-test" / "SUMMARY.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["reused_units"], 6)
        self.assertEqual(summary["coded_units_in_directory"], 6)
        self.assertEqual(summary["stale_units_in_directory"], 0)

    def test_rubric_change_refuses_the_locked_directory(self):
        self.run_main("--codes-dir", "autocodes-test")
        before = self.records("autocodes-test")
        self.rubric.write_text(self.rubric.read_text(encoding="utf-8") + "\nA new rule.\n", encoding="utf-8")
        FakeGateway.calls = []
        with self.assertRaises(SystemExit) as refused:
            self.run_main("--codes-dir", "autocodes-test")
        self.assertIn("rubric", str(refused.exception))
        self.assertIn("--codes-dir", str(refused.exception))
        self.assertEqual(FakeGateway.calls, [])
        self.assertEqual(self.records("autocodes-test"), before)

    def test_record_hash_mismatch_is_refused(self):
        self.run_main("--codes-dir", "autocodes-test")
        path = self.analysis / "autocodes-test" / "B002__t7.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["script_sha256"] = "0" * 64
        path.write_text(json.dumps(record), encoding="utf-8")
        FakeGateway.calls = []
        with self.assertRaises(SystemExit) as refused:
            self.run_main("--codes-dir", "autocodes-test")
        self.assertIn("B002__t7.json", str(refused.exception))
        self.assertIn("--force-recode", str(refused.exception))
        self.assertEqual(FakeGateway.calls, [])

    def test_force_recode_recodes_and_relocks(self):
        self.run_main("--codes-dir", "autocodes-test")
        self.rubric.write_text(self.rubric.read_text(encoding="utf-8") + "\nA new rule.\n", encoding="utf-8")
        FakeGateway.calls = []
        self.assertEqual(self.run_main("--codes-dir", "autocodes-test", "--force-recode"), 0)
        self.assertEqual(len(FakeGateway.calls), 8)
        new_sha = hashlib.sha256(self.rubric.read_bytes()).hexdigest()
        lock = json.loads((self.analysis / "autocodes-test" / ac.LOCK_NAME).read_text(encoding="utf-8"))
        self.assertEqual(lock["files"]["rubric"]["sha256"], new_sha)
        self.assertTrue(all(r["rubric_sha256"] == new_sha for r in self.records("autocodes-test").values()))

    def test_partial_force_recode_keeps_both_coder_texts_and_scorer_skips_stale(self):
        import csv
        import score_autocoding_against_gold as scorer
        self.run_main("--codes-dir", "autocodes-test")
        old = ac.load_rubric(self.rubric)
        self.rubric.write_text(
            self.rubric.read_text(encoding="utf-8").replace("RUBRIC-TEST-MARKER", "RUBRIC-TEST-MARKER-2"),
            encoding="utf-8",
        )
        new = ac.load_rubric(self.rubric)
        self.assertNotEqual(old["coder_sha256"], new["coder_sha256"])
        self.assertEqual(self.run_main("--codes-dir", "autocodes-test", "--force-recode", "--blind-ids", "B001"), 0)
        folder = self.analysis / "autocodes-test"
        for rubric in (old, new):
            self.assertTrue((folder / ac.coder_copy_name(rubric)).exists())
        reference = self.analysis / "ref.csv"
        with reference.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["blind_id", "turn", *ac.LABELS, "rationale", "evidence_quote", "adjudicator"])
            for blind_id in ("B001", "B002"):
                for turn in ac.CODED_TURNS:
                    writer.writerow([blind_id, turn, *(GOOD_CODE[d] for d in ac.LABELS), "r", "q", "Alex"])
        report = scorer.score(reference, folder)
        self.assertEqual(report["stale_units_excluded"], ["B002 t6", "B002 t7", "B002 t8"])
        self.assertEqual(report["units_without_autocode"], [])
        self.assertEqual(report["sources"]["final"]["verdict_given"]["n"], 3)
        self.assertEqual(report["codes_lock"]["rubric_sha256"], new["sha256"])
        self.assertEqual([entry["units"] for entry in report["autocode_rubrics"]], [3])

    def test_directory_without_lock_is_never_written(self):
        legacy = self.analysis / "autocodes"
        legacy.mkdir()
        (legacy / "B001__t6.json").write_text('{"schema_version": 1}', encoding="utf-8")
        for extra in ([], ["--force-recode"]):
            with self.assertRaises(SystemExit) as refused:
                self.run_main(*extra)  # default --codes-dir is autocodes
            self.assertIn(ac.LOCK_NAME, str(refused.exception))
        self.assertEqual(sorted(p.name for p in legacy.iterdir()), ["B001__t6.json"])
        self.assertEqual(FakeGateway.calls, [])

    def test_default_codes_dir_is_autocodes(self):
        self.assertEqual(self.run_main(), 0)
        self.assertEqual(len(self.records("autocodes")), 6)
        self.assertTrue((self.analysis / "autocodes" / ac.LOCK_NAME).exists())

    def test_codes_dir_cannot_be_the_blind_package(self):
        with self.assertRaises(SystemExit):
            self.run_main("--codes-dir", "blind")
        self.assertFalse((self.analysis / "blind" / ac.LOCK_NAME).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
