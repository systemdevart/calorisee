"""Thin wrapper around the OpenAI SDK with retry logic and logging."""

import base64
import json
import logging
import os
import time
from pathlib import Path

import openai

logger = logging.getLogger(__name__)

# Transient error codes worth retrying
_RETRYABLE = (
    openai.RateLimitError,
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.InternalServerError,
)


def _get_client() -> openai.OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set. Add it to your .env file.")
    kwargs: dict = {"api_key": api_key}
    org = os.environ.get("OPENAI_ORG_ID")
    if org:
        kwargs["organization"] = org
    project = os.environ.get("OPENAI_PROJECT_ID")
    if project:
        kwargs["project"] = project
    return openai.OpenAI(**kwargs)


_client: openai.OpenAI | None = None


def get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        _client = _get_client()
    return _client


def _encode_image(image_path: str) -> str:
    """Read and base64-encode an image file."""
    data = Path(image_path).read_bytes()
    return base64.standard_b64encode(data).decode("utf-8")


def _media_type(image_path: str) -> str:
    ext = Path(image_path).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(ext, "image/jpeg")


def call_openai_text(
    prompt: str,
    system: str,
    model: str = "gpt-4.1-mini",
    json_mode: bool = True,
    max_retries: int = 3,
) -> str:
    """Call OpenAI Responses API with text-only input. Returns response text."""
    client = get_client()
    text_format = {"format": {"type": "json_object"}} if json_mode else {}
    # Responses API requires the word "json" in input for json_object mode
    if json_mode and "json" not in prompt.lower():
        prompt += "\n\nRespond with valid JSON."

    for attempt in range(max_retries):
        try:
            logger.debug("OpenAI request (text, model=%s, attempt=%d)", model, attempt + 1)
            response = client.responses.create(
                model=model,
                instructions=system,
                input=prompt,
                **{"text": text_format} if text_format else {},
            )
            result = response.output_text
            logger.debug("OpenAI response length: %d chars", len(result))
            return result
        except _RETRYABLE as e:
            wait = 2 ** attempt
            logger.warning("Transient OpenAI error (attempt %d/%d): %s. Retrying in %ds...", attempt + 1, max_retries, e, wait)
            time.sleep(wait)
        except openai.BadRequestError as e:
            logger.error("OpenAI bad request: %s", e)
            raise

    raise RuntimeError(f"OpenAI call failed after {max_retries} retries.")


def call_openai_vision(
    prompt: str,
    system: str,
    image_paths: list[str],
    model: str = "gpt-4.1",
    json_mode: bool = True,
    max_retries: int = 3,
) -> str:
    """Call OpenAI Responses API with image(s) + text. Returns response text."""
    client = get_client()
    text_format = {"format": {"type": "json_object"}} if json_mode else {}

    # Responses API requires the word "json" in input for json_object mode
    if json_mode and "json" not in prompt.lower():
        prompt += "\n\nRespond with valid JSON."

    # Build content array with text + images
    content: list[dict] = [{"type": "input_text", "text": prompt}]
    for img_path in image_paths:
        try:
            b64 = _encode_image(img_path)
            mt = _media_type(img_path)
            content.append({
                "type": "input_image",
                "image_url": f"data:{mt};base64,{b64}",
            })
        except (OSError, IOError) as e:
            logger.warning("Could not read image %s: %s", img_path, e)

    input_messages = [{"role": "user", "content": content}]

    for attempt in range(max_retries):
        try:
            logger.debug("OpenAI request (vision, model=%s, %d images, attempt=%d)", model, len(image_paths), attempt + 1)
            response = client.responses.create(
                model=model,
                instructions=system,
                input=input_messages,
                **{"text": text_format} if text_format else {},
            )
            result = response.output_text
            logger.debug("OpenAI response length: %d chars", len(result))
            return result
        except _RETRYABLE as e:
            wait = 2 ** attempt
            logger.warning("Transient OpenAI error (attempt %d/%d): %s. Retrying in %ds...", attempt + 1, max_retries, e, wait)
            time.sleep(wait)
        except openai.BadRequestError as e:
            logger.error("OpenAI bad request: %s", e)
            raise

    raise RuntimeError(f"OpenAI vision call failed after {max_retries} retries.")


def parse_json_response(raw: str) -> dict:
    """Parse a JSON response, with one repair attempt if needed."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        import re
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # Try to find JSON object
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end])
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse JSON from response: {raw[:200]}...")
