#!/usr/bin/env python3
"""
LLM wrapper — OpenRouter client with retry, backoff, multi-model support.
Used by generator, verifier, batch_generate.
"""

import os
import random
import time
from typing import Optional

from openai import OpenAI, APIError, APITimeoutError, APIConnectionError, RateLimitError


def make_client(api_key: Optional[str] = None) -> OpenAI:
    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    return OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")


def complete(client: OpenAI, model: str, prompt: str,
             max_tokens: int = 16384, temperature: float = 0.3,
             max_retries: int = 4, base_delay: float = 2.0) -> str:
    """Call model with exponential backoff + jitter on retryable errors."""
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content or ""
        except (RateLimitError, APITimeoutError, APIConnectionError) as e:
            last_err = e
            if attempt == max_retries:
                break
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            print(f"    retry {attempt+1}/{max_retries} after {delay:.1f}s: {type(e).__name__}")
            time.sleep(delay)
        except APIError as e:
            last_err = e
            code = getattr(e, "status_code", 0)
            if code and 500 <= code < 600 and attempt < max_retries:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                print(f"    retry {attempt+1}/{max_retries} after {delay:.1f}s: {code}")
                time.sleep(delay)
                continue
            raise
    raise RuntimeError(f"LLM failed after {max_retries} retries: {last_err}")


def get_primary_model() -> str:
    return os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-r1")


def get_verifier_model() -> str:
    """Different model for cross-verification. Independent errors → higher catch rate."""
    return os.environ.get("OPENROUTER_VERIFIER_MODEL", "google/gemini-2.5-flash")
