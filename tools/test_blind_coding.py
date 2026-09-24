#!/usr/bin/env python3
"""Unit tests for blind package integrity and generator-aware routing."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import sys
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import prepare_blind_coding as blind


class BlindPackageTests(unittest.TestCase):
    def make_run(self, root: Path):
        files = {}
        specs = []
        number = 0
        for model in ["claude", "gpt"]:
            for track in ["verdict", "bias"]:
                for condition in ["supportive_control", "permission_gate"]:
                    number += 1
                    name = f"source-{number}.json"
                    record = {
                        "status": "clean",
                        "spec": {"model": model, "track": track, "condition": condition, "repeat": 1},
                        "transcript": [
                            {"turn": i, "user": f"user {i}", "assistant": f"assistant {i}"}
                            for i in range(1, 9)
                        ],
                    }
                    path = root / name
                    path.write_text(json.dumps(record), encoding="utf-8")
                    files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        freeze = {
            "conversation_count": 8,
            "conversation_tree_sha256": "tree",
            "conversation_sha256": files,
        }
        (root / "FROZEN_ANALYSIS_INPUT.json").write_text(json.dumps(freeze))

    def test_blind_files_contain_no_experimental_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            self.make_run(run)
            analysis = run / "coding"
            manifest = blind.prepare(run, analysis, 3)
            self.assertEqual(manifest["conversation_count"], 8)
            self.assertEqual(manifest["human_gold_count"], 8)
            for path in (analysis / "blind").glob("*.json"):
                text = path.read_text()
                for forbidden in ["generator_model", "condition", "repeat", "source_file", "supportive_control", "permission_gate"]:
                    self.assertNotIn(forbidden, text)

    def test_checksum_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            self.make_run(run)
            (run / "source-1.json").write_text("tampered")
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                blind.load_and_verify_run(run)


if __name__ == "__main__":
    unittest.main(verbosity=2)
