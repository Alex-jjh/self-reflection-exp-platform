"""Tests of the token-source / model-access package and of the package boundary."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from helpers import PACKAGE_ROOT, FakeBedrockClient, client_error, fake_backend, ok_response

from botocore.exceptions import (
    CredentialRetrievalError,
    EndpointConnectionError,
    NoCredentialsError,
    ReadTimeoutError,
)

import bedrock_access
from bedrock_access import AccessError, classify_error, scrub_bearer_env
from experiment_runtime import contract


class TestClassification(unittest.TestCase):
    def kind(self, exc: BaseException) -> str:
        return classify_error(exc).kind

    def test_client_error_codes(self) -> None:
        cases = {
            ("ThrottlingException", 429): "throttled",
            ("ServiceQuotaExceededException", 400): "throttled",
            ("ExpiredTokenException", 403): "credential",
            ("UnrecognizedClientException", 403): "credential",
            ("InvalidSignatureException", 403): "credential",
            ("AccessDeniedException", 403): "access_denied",
            ("ResourceNotFoundException", 404): "model_unavailable",
            ("ValidationException", 400): "invalid",
            ("InternalServerException", 500): "transient",
            ("ServiceUnavailableException", 503): "transient",
            ("ModelNotReadyException", 429): "throttled",  # 429 wins: capacity
            ("ModelTimeoutException", 408): "transient",
            ("SomethingNew", 502): "transient",
            ("SomethingNew", 400): "invalid",
        }
        for (code, status), expected in cases.items():
            with self.subTest(code=code):
                self.assertEqual(self.kind(client_error(code, status)), expected)

    def test_non_client_errors(self) -> None:
        self.assertEqual(self.kind(CredentialRetrievalError(provider="custom-process", error_msg="mwinit needed")),
                         "credential")
        self.assertEqual(self.kind(NoCredentialsError()), "credential")
        self.assertEqual(self.kind(ReadTimeoutError(endpoint_url="https://x")), "transient")
        self.assertEqual(self.kind(EndpointConnectionError(endpoint_url="https://x")), "transient")
        self.assertEqual(self.kind(RuntimeError("Caminus returned 401")), "credential")
        self.assertEqual(self.kind(RuntimeError("weird")), "transient")

    def test_messages_are_verbatim_but_key_ids_are_scrubbed(self) -> None:
        info = classify_error(client_error("ValidationException", 400, "bad AKIAABCDEFGHIJKLMNOP thing"))
        self.assertEqual(info.message, "bad <redacted-key-id> thing")
        self.assertEqual(info.error_class, "ClientError:ValidationException")


class TestBackend(unittest.TestCase):
    def test_prepare_builds_converse_request(self) -> None:
        backend, _ = fake_backend(FakeBedrockClient())
        request = backend.prepare("us.openai.gpt-5.6-sol", "sys", (("user", "a"), ("assistant", "b"), ("user", "c")),
                                  {"maxTokens": 10}, {"reasoning": {"effort": "low"}})
        self.assertEqual(request, {
            "modelId": "us.openai.gpt-5.6-sol",
            "messages": [{"role": "user", "content": [{"text": "a"}]},
                         {"role": "assistant", "content": [{"text": "b"}]},
                         {"role": "user", "content": [{"text": "c"}]}],
            "inferenceConfig": {"maxTokens": 10},
            "system": [{"text": "sys"}],
            "additionalModelRequestFields": {"reasoning": {"effort": "low"}},
        })
        self.assertNotIn("system", backend.prepare("us.openai.gpt-5.6-sol", None, (("user", "a"),),
                                                   {"maxTokens": 1}, None))
        with self.assertRaises(ValueError):
            backend.prepare("not.allowlisted", None, (("user", "a"),), {"maxTokens": 1}, None)

    def test_invoke_parses_text_and_reasoning(self) -> None:
        client = FakeBedrockClient(lambda call: ok_response("hello", reasoning="thought"))
        backend, _ = fake_backend(client)
        request = backend.prepare("us.anthropic.claude-opus-5", None, (("user", "cell:x hi"),), {"maxTokens": 5}, None)
        reply = backend.invoke("us.anthropic.claude-opus-5", request)
        self.assertEqual(reply.text, "hello")
        self.assertEqual(reply.reasoning, ["thought"])
        self.assertEqual(reply.stop_reason, "end_turn")
        self.assertEqual(reply.usage["outputTokens"], 5)

    def test_invoke_raises_classified_error(self) -> None:
        client = FakeBedrockClient(lambda call: (_ for _ in ()).throw(client_error("ThrottlingException", 429)))
        backend, _ = fake_backend(client)
        request = backend.prepare("us.anthropic.claude-opus-5", None, (("user", "cell:x hi"),), {"maxTokens": 5}, None)
        with self.assertRaises(AccessError) as caught:
            backend.invoke("us.anthropic.claude-opus-5", request)
        self.assertEqual(caught.exception.kind, "throttled")
        self.assertEqual(caught.exception.http_status, 429)

    def test_scrub_bearer_env(self) -> None:
        os.environ["AWS_BEARER_TOKEN_BEDROCK"] = "not-a-real-token"
        try:
            removed = scrub_bearer_env()
        finally:
            os.environ.pop("AWS_BEARER_TOKEN_BEDROCK", None)
        self.assertEqual(removed, ["AWS_BEARER_TOKEN_BEDROCK"])
        self.assertNotIn("AWS_BEARER_TOKEN_BEDROCK", os.environ)

    def test_allowlist(self) -> None:
        self.assertEqual(len(bedrock_access.MODEL_REGIONS), 11)
        self.assertEqual({r for m, r in bedrock_access.MODEL_REGIONS.items() if ".openai." in m}, {"us-east-2"})
        self.assertEqual({r for m, r in bedrock_access.MODEL_REGIONS.items() if ".anthropic." in m}, {"us-west-2"})


class TestPackageBoundary(unittest.TestCase):
    def test_error_kinds_match_the_runtime_contract(self) -> None:
        self.assertEqual(set(bedrock_access.KINDS), set(contract.KINDS))

    def _imported_after(self, statement: str) -> set[str]:
        code = (f"import sys; sys.path.insert(0, {str(PACKAGE_ROOT)!r}); {statement}; "
                "print('\\n'.join(sorted({m.split('.')[0] for m in sys.modules})))")
        output = subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True).stdout
        return set(output.split())

    def test_runtime_does_not_import_provider_code(self) -> None:
        modules = self._imported_after("import experiment_runtime.engine, experiment_runtime.status")
        self.assertFalse(modules & {"boto3", "botocore", "bedrock_access"}, modules & {"boto3", "botocore", "bedrock_access"})

    def test_provider_does_not_import_runtime(self) -> None:
        modules = self._imported_after("import bedrock_access, bedrock_access.diagnostics")
        self.assertNotIn("experiment_runtime", modules)


if __name__ == "__main__":
    unittest.main()
