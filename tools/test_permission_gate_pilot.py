import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import sys

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import run_permission_gate_pilot as pilot


class FakeGatewayHandler(BaseHTTPRequestHandler):
    counter = 0
    requests = []

    def log_message(self, *_args):
        return

    def do_GET(self):
        if self.path == "/healthz":
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        request = json.loads(self.rfile.read(length))
        type(self).requests.append(request)
        type(self).counter += 1
        text = f"synthetic response {type(self).counter}"
        result = {
            "model": request["model"],
            "region": "test-region",
            "output": {"message": {"role": "assistant", "content": [{"text": text}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 10, "outputTokens": 3},
            "gatewayLatencyMs": 2,
            "requestSha256": "f" * 64,
        }
        body = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class PilotTests(unittest.TestCase):
    def test_default_plan_is_sixty_conversations(self):
        plan = pilot.build_plan(
            pilot.DEFAULT_MODELS,
            pilot.DEFAULT_TRACKS,
            pilot.DEFAULT_CONDITIONS,
            5,
            pilot.DEFAULT_SEED,
        )
        self.assertEqual(len(plan), 60)
        self.assertEqual(len({item.conversation_id for item in plan}), 60)
        self.assertEqual(len(plan) * 8, 480)

    def test_tracks_are_semantically_parallel_in_length(self):
        verdict = pilot.load_track("verdict")["turns"]
        bias = pilot.load_track("bias")["turns"]
        self.assertEqual(len(verdict), 8)
        self.assertEqual(len(bias), 8)
        self.assertGreater(sum(text.count("？") + text.count("?") for text in verdict), 4)
        self.assertEqual(sum(text.count("？") + text.count("?") for text in bias), 0)

    def test_gate_prompt_is_baseline_plus_addon(self):
        control, control_sources = pilot.load_prompt("supportive_control")
        gate, gate_sources = pilot.load_prompt("permission_gate")
        self.assertEqual(len(control_sources), 2)
        self.assertEqual(len(gate_sources), 2)
        control_core, control_policy = control.split("\n\n【判断政策】\n", 1)
        gate_core, gate_policy = gate.split("\n\n【判断政策】\n", 1)
        self.assertEqual(control_core, gate_core)
        # Policy blocks are structurally matched: neither should gain an
        # advantage from simply being much longer or more detailed.
        ratio = len(control_policy) / len(gate_policy)
        self.assertGreaterEqual(ratio, 0.90)
        self.assertLessEqual(ratio, 1.10)
        self.assertNotEqual(control_policy, gate_policy)

    def test_one_turn_conversation_through_fake_gateway(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeGatewayHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = pilot.GatewayClient(f"http://127.0.0.1:{server.server_address[1]}", "local")
            with tempfile.TemporaryDirectory() as directory:
                spec = pilot.ConversationSpec(
                    1, "cell", "conversation", pilot.DEFAULT_MODELS[0], "verdict", "supportive_control", 1
                )
                record = pilot.run_conversation(spec, 1, Path(directory), client, max_turns=1)
                self.assertEqual(record["status"], "clean")
                self.assertEqual(len(record["transcript"]), 1)
                self.assertTrue((Path(directory) / "conversation.json").exists())
                sent = FakeGatewayHandler.requests[-1]
                self.assertIsInstance(sent["system"], str)
                self.assertIn("温暖", sent["system"])
                self.assertEqual([message["role"] for message in sent["messages"]], ["user"])
                self.assertNotIn(sent["system"], [message["content"] for message in sent["messages"]])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_gateway_must_be_loopback(self):
        with self.assertRaises(ValueError):
            pilot.GatewayClient("https://example.com", "token")


if __name__ == "__main__":
    unittest.main(verbosity=2)
