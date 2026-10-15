"""Allowlisted Bedrock models and their regions.

Adding a model is a reviewed code change, not a caller-controlled input.
"""

from __future__ import annotations

MODEL_REGIONS: dict[str, str] = {
    "us.anthropic.claude-opus-5-5": "us-west-2",
    "us.anthropic.claude-sonnet-5-5": "us-west-2",
    "us.anthropic.claude-haiku-5-5": "us-west-2",
    "us.anthropic.claude-opus-5": "us-west-2",
    "us.anthropic.claude-sonnet-5": "us-west-2",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": "us-west-2",
    "us.anthropic.claude-opus-4-7": "us-west-2",
    "us.anthropic.claude-sonnet-4-6": "us-west-2",
    "us.openai.gpt-5.6-sol": "us-east-2",
    "us.openai.gpt-5.6-terra": "us-east-2",
    "us.openai.gpt-5.6-luna": "us-east-2",
}


def is_anthropic(model: str) -> bool:
    return ".anthropic." in model


def is_openai(model: str) -> bool:
    return ".openai." in model
