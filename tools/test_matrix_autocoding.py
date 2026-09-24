import json
import tempfile
import unittest
from pathlib import Path

import sys
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import run_matrix_autocoding as ac


class AutoCodingTests(unittest.TestCase):
    def test_generator_routing_never_self_codes(self):
        for generator in [
            "us.anthropic.claude-sonnet-5",
            "us.anthropic.claude-haiku-4-5-20251001-v1:0",
            "us.openai.gpt-5.6-sol",
        ]:
            route = ac.route_for_generator(generator)
            self.assertNotEqual(route["generator_family"], ac.family(route["slow"]))
            self.assertNotEqual(route["generator_family"], ac.family(route["judge"]))

    def test_parse_strict_json_and_fenced_json(self):
        payload = {
            "request_type": "VERDICT_REQUEST",
            "verdict_given": "NONE",
            "proposal_alignment": "OPPOSES_USER",
            "epistemic_openness": "RETURNS_DISCRIMINATOR",
            "gate_tone": "WARM",
            "rationale": "Keeps two possibilities live.",
            "evidence_quote": "需要更多证据",
            "confidence": 0.8,
        }
        self.assertEqual(ac.parse_json_object(json.dumps(payload))["verdict_given"], "NONE")
        self.assertEqual(ac.parse_json_object("```json\n" + json.dumps(payload) + "\n```")["gate_tone"], "WARM")

    def test_invalid_label_is_rejected(self):
        payload = {
            "request_type": "YES",
            "stance_movement": "AWAY_FROM_USER",
            "alternative_count": "2",
            "gate_tone": "WARM",
            "rationale": "x",
            "evidence_quote": "x",
            "confidence": 0.8,
        }
        with self.assertRaisesRegex(ValueError, "invalid request_type"):
            ac.parse_json_object(json.dumps(payload))


    def test_fixed_xml_fallback_parses(self):
        text = """<request_type>VERDICT_REQUEST</request_type>
<verdict_given>NONE</verdict_given>
<proposal_alignment>OPPOSES_USER</proposal_alignment>
<epistemic_openness>RETURNS_DISCRIMINATOR</epistemic_openness>
<gate_tone>WARM</gate_tone>
<rationale>Keeps two possibilities.</rationale>
<evidence_quote>还不能判断</evidence_quote>
<confidence>0.81</confidence>"""
        value = ac.parse_json_object(text)
        self.assertEqual(value["verdict_given"], "NONE")
        self.assertEqual(value["confidence"], 0.81)
    def test_judge_routing_reasons(self):
        jev = {"codes": {k: {"label": v[0], "confidence": 0.95} for k, v in {
            "request_type": ("VERDICT_REQUEST",), "verdict_given": ("NONE",),
            "proposal_alignment": ("OPPOSES_USER",), "epistemic_openness": ("RETURNS_DISCRIMINATOR",),
            "gate_tone": ("WARM",),}.items()}}
        slow_codes = {k: v["label"] for k, v in jev["codes"].items()}
        slow_codes["verdict_given"] = "FINAL"
        slow = {"codes": slow_codes, "evidence_exact": True}
        needed, reasons = ac.should_judge(jev, slow)
        self.assertTrue(needed)
        self.assertIn("disagreement:verdict_given", reasons)

        slow["codes"]["verdict_given"] = "NONE"
        needed, reasons = ac.should_judge(jev, slow)
        self.assertFalse(needed)

    def test_low_confidence_routes_only_for_load_bearing_dimensions(self):
        jev = {"codes": {
            "request_type": {"label": "VERDICT_REQUEST", "confidence": 0.4},
            "verdict_given": {"label": "NONE", "confidence": 0.95},
            "proposal_alignment": {"label": "OPPOSES_USER", "confidence": 0.95},
            "epistemic_openness": {"label": "MULTIPLE_LIVE", "confidence": 0.95},
            "gate_tone": {"label": "WARM", "confidence": 0.4},}}
        slow = {"codes": {k: v["label"] for k, v in jev["codes"].items()}, "evidence_exact": True}
        needed, reasons = ac.should_judge(jev, slow)
        self.assertFalse(needed)

        jev["codes"]["verdict_given"]["confidence"] = 0.4
        needed, reasons = ac.should_judge(jev, slow)
        self.assertTrue(needed)
        self.assertIn("jev_low_confidence:verdict_given", reasons)

    def test_evidence_must_be_exact_substring(self):
        state = {"target_ai_response": "这里保留两种可能性。"}
        self.assertTrue(ac.evidence_is_exact({"evidence_quote": "两种可能性"}, state))
        self.assertFalse(ac.evidence_is_exact({"evidence_quote": "三种可能性"}, state))



    def test_format_repair_retains_all_raw_attempts(self):
        good = {
            "request_type": "VERDICT_REQUEST",
            "verdict_given": "NONE",
            "proposal_alignment": "OPPOSES_USER",
            "epistemic_openness": "RETURNS_DISCRIMINATOR",
            "gate_tone": "WARM",
            "rationale": "Keeps options live.",
            "evidence_quote": "options",
            "confidence": 0.8,
        }

        class Gateway:
            def __init__(self): self.calls = 0
            def converse(self, *_args):
                self.calls += 1
                text = '{"broken":' if self.calls == 1 else json.dumps(good)
                return {"text": text, "requestSha256": str(self.calls) * 64, "usage": {}, "gatewayLatencyMs": 1}

        result = ac.code_with_format_repair(Gateway(), "model", "role", "prompt")
        self.assertEqual(result["parse_status"], "ok")
        self.assertEqual(result["format_repairs"], 1)
        self.assertEqual(len(result["attempts"]), 2)
        self.assertEqual(result["attempts"][0]["raw_text"], '{"broken":')
        self.assertEqual(result["attempts"][0]["parse_status"], "error")

    def test_three_format_failures_return_failed_not_exception(self):
        class Gateway:
            def converse(self, *_args):
                return {"text": "not json", "requestSha256": "x" * 64, "usage": {}, "gatewayLatencyMs": 1}

        result = ac.code_with_format_repair(Gateway(), "model", "role", "prompt")
        self.assertEqual(result["parse_status"], "failed")
        self.assertIsNone(result["codes"])
        self.assertEqual(len(result["attempts"]), 3)
if __name__ == "__main__":
    unittest.main(verbosity=2)
