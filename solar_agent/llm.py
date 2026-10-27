"""Meta Model API client. The API is OpenAI-compatible, so the official OpenAI SDK talks to it."""

from __future__ import annotations

import os

DEFAULT_BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MODEL = "muse-spark-1.3"


def client():
    from openai import OpenAI

    key = os.environ.get("MODEL_API_KEY")
    if not key:
        raise RuntimeError("MODEL_API_KEY is not set (see .env.example)")
    return OpenAI(api_key=key, base_url=os.environ.get("MODEL_API_BASE_URL", DEFAULT_BASE_URL))


def model() -> str:
    return os.environ.get("MODEL_API_MODEL", DEFAULT_MODEL)
