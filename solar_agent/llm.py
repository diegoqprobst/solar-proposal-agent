"""Meta Model API client. The API is OpenAI-compatible, so the official OpenAI SDK talks to it."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MODEL = "muse-spark-1.3"


def load_env(path: str | Path = ".env") -> None:
    """Read KEY=VALUE lines from a .env file into os.environ. Variables already set win."""
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        value = value.strip().strip("\"'")
        if value:
            os.environ.setdefault(name.strip(), value)


def client():
    from openai import OpenAI

    load_env()
    key = os.environ.get("MODEL_API_KEY")
    if not key:
        raise RuntimeError("MODEL_API_KEY is not set (see .env.example)")
    return OpenAI(api_key=key, base_url=os.environ.get("MODEL_API_BASE_URL", DEFAULT_BASE_URL))


def model() -> str:
    load_env()
    return os.environ.get("MODEL_API_MODEL", DEFAULT_MODEL)
