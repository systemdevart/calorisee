"""OpenAI Batch API support for classification and estimation."""

import base64
import io
import json
import logging
import time
from pathlib import Path

from whatsapp_calorie_bot.openai_client import get_client, parse_json_response, _encode_image, _media_type
from whatsapp_calorie_bot.inference import (
    CLASSIFICATION_SYSTEM,
    ESTIMATION_SYSTEM,
    ESTIMATION_PROMPT_WITH_IMAGE,
    ESTIMATION_PROMPT_TEXT_ONLY,
)
from whatsapp_calorie_bot.storage import Storage

logger = logging.getLogger(__name__)

# Poll interval bounds
_POLL_MIN_SECONDS = 10
_POLL_MAX_SECONDS = 60


def _make_classification_request(msg: dict, model: str) -> dict:
    """Build a single Batch API request line for food classification."""
    prompt = f"Classify this WhatsApp message:\n\nSender: {msg['sender']}\nMessage: {msg['text']}"
    if "json" not in prompt.lower():
        prompt += "\n\nRespond with valid JSON."
    return {
        "custom_id": f"classify-{msg['msg_id']}",
        "method": "POST",
        "url": "/v1/responses",
        "body": {
            "model": model,
            "instructions": CLASSIFICATION_SYSTEM,
            "input": prompt,
            "text": {"format": {"type": "json_object"}},
        },
    }


def _make_estimation_request(msg: dict, model_text: str, model_vision: str) -> dict:
    """Build a single Batch API request line for calorie estimation."""
    has_images = msg.get("has_media") and msg.get("media_paths") and not msg.get("media_missing")
    image_paths = [p for p in msg.get("media_paths", []) if p] if has_images else []

    if image_paths:
        prompt = ESTIMATION_PROMPT_WITH_IMAGE.format(text=msg["text"], sender=msg["sender"])
        if "json" not in prompt.lower():
            prompt += "\n\nRespond with valid JSON."
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
        return {
            "custom_id": f"estimate-{msg['msg_id']}",
            "method": "POST",
            "url": "/v1/responses",
            "body": {
                "model": model_vision,
                "instructions": ESTIMATION_SYSTEM,
                "input": [{"role": "user", "content": content}],
                "text": {"format": {"type": "json_object"}},
            },
        }
    else:
        prompt = ESTIMATION_PROMPT_TEXT_ONLY.format(text=msg["text"], sender=msg["sender"])
        if "json" not in prompt.lower():
            prompt += "\n\nRespond with valid JSON."
        return {
            "custom_id": f"estimate-{msg['msg_id']}",
            "method": "POST",
            "url": "/v1/responses",
            "body": {
                "model": model_text,
                "instructions": ESTIMATION_SYSTEM,
                "input": prompt,
                "text": {"format": {"type": "json_object"}},
            },
        }


def _upload_and_submit_batch(requests: list[dict], description: str) -> str:
    """Write requests to JSONL, upload, and submit a batch. Returns batch ID."""
    client = get_client()

    # Build JSONL in memory
    buf = io.BytesIO()
    for req in requests:
        buf.write(json.dumps(req, ensure_ascii=False).encode("utf-8"))
        buf.write(b"\n")
    buf.seek(0)

    size_mb = buf.getbuffer().nbytes / 1e6
    logger.info("Uploading batch file (%.1f MB, %d requests)...", size_mb, len(requests))

    file_obj = client.files.create(file=("batch_input.jsonl", buf), purpose="batch")
    logger.info("Uploaded file: %s", file_obj.id)

    batch = client.batches.create(
        input_file_id=file_obj.id,
        endpoint="/v1/responses",
        completion_window="24h",
        metadata={"description": description},
    )
    logger.info("Batch created: %s (status=%s)", batch.id, batch.status)
    return batch.id


def _poll_batch(batch_id: str) -> dict:
    """Poll a batch until it completes. Returns the batch object."""
    client = get_client()
    poll_interval = _POLL_MIN_SECONDS
    start = time.time()

    while True:
        batch = client.batches.retrieve(batch_id)
        elapsed = time.time() - start
        counts = f"{batch.request_counts.completed}/{batch.request_counts.total}" if batch.request_counts else "?"
        logger.info(
            "Batch %s: status=%s, progress=%s, elapsed=%.0fs",
            batch_id[:12], batch.status, counts, elapsed,
        )

        if batch.status in ("completed", "failed", "cancelled", "expired"):
            return batch

        time.sleep(poll_interval)
        poll_interval = min(poll_interval * 1.5, _POLL_MAX_SECONDS)


def _download_batch_results(batch) -> dict[str, dict]:
    """Download and parse batch results. Returns {custom_id: response_body}."""
    client = get_client()

    if batch.status != "completed":
        logger.error("Batch %s finished with status=%s", batch.id, batch.status)
        if batch.errors and batch.errors.data:
            for err in batch.errors.data[:5]:
                logger.error("  Batch error: %s", err)
        return {}

    output_file_id = batch.output_file_id
    if not output_file_id:
        logger.error("Batch completed but no output_file_id")
        return {}

    logger.info("Downloading batch results from file %s...", output_file_id)
    content = client.files.content(output_file_id).text

    results: dict[str, dict] = {}
    for line in content.strip().split("\n"):
        if not line:
            continue
        row = json.loads(line)
        custom_id = row["custom_id"]
        response = row.get("response", {})
        if response.get("status_code") == 200:
            body = response.get("body", {})
            # Extract text output from the responses API result
            output_text = body.get("output_text", "")
            if not output_text:
                # Try to extract from output array
                for item in body.get("output", []):
                    if item.get("type") == "message":
                        for content_part in item.get("content", []):
                            if content_part.get("type") == "output_text":
                                output_text = content_part.get("text", "")
                                break
            results[custom_id] = {"output_text": output_text}
        else:
            error = response.get("error", {})
            logger.warning("Batch request %s failed: %s", custom_id, error)
            results[custom_id] = {"error": error}

    logger.info("Parsed %d batch results.", len(results))
    return results


def run_batch_inference_pipeline(
    messages: list[dict],
    storage: Storage,
    force_redo: bool = False,
    food_confidence_threshold: float = 0.6,
    model_text: str = "gpt-4.1-mini",
    model_vision: str = "gpt-4.1",
) -> list[dict]:
    """Run the two-stage inference pipeline using the OpenAI Batch API."""

    # Separate cached vs uncached
    cached_msgs: list[dict] = []
    uncached_msgs: list[dict] = []

    for msg in messages:
        if not force_redo:
            cached = storage.get_inference(msg["msg_id"])
            if cached:
                msg["classification"] = cached.get("classification", {})
                msg["estimation"] = cached.get("estimation")
                cached_msgs.append(msg)
                continue
        uncached_msgs.append(msg)

    logger.info(
        "Batch pipeline: %d cached, %d to process.",
        len(cached_msgs), len(uncached_msgs),
    )

    if not uncached_msgs:
        return cached_msgs

    # ── Phase 1: Classification batch ──
    logger.info("Phase 1: Submitting classification batch for %d messages...", len(uncached_msgs))
    classify_requests = [_make_classification_request(m, model_text) for m in uncached_msgs]
    classify_batch_id = _upload_and_submit_batch(classify_requests, "food-classification")
    classify_batch = _poll_batch(classify_batch_id)
    classify_results = _download_batch_results(classify_batch)

    # Apply classification results and identify food messages
    food_msgs: list[dict] = []
    for msg in uncached_msgs:
        custom_id = f"classify-{msg['msg_id']}"
        result = classify_results.get(custom_id, {})
        output_text = result.get("output_text", "")

        if output_text:
            try:
                classification = parse_json_response(output_text)
            except Exception as e:
                logger.warning("Failed to parse classification for %s: %s", msg["msg_id"][:8], e)
                classification = {"is_food": False, "food_confidence": 0, "reason_short": "parse error", "food_context": "non_food"}
        else:
            classification = {"is_food": False, "food_confidence": 0, "reason_short": "batch error", "food_context": "non_food"}

        msg["classification"] = classification

        is_food = classification.get("is_food", False)
        confidence = classification.get("food_confidence", 0.0)
        if is_food and confidence >= food_confidence_threshold:
            food_msgs.append(msg)

    logger.info("Classification done: %d food messages identified.", len(food_msgs))

    # ── Phase 2: Estimation batches (split by model since batches require single model) ──
    if food_msgs:
        # Split into vision (has images) vs text-only
        vision_msgs = []
        text_msgs = []
        for m in food_msgs:
            has_images = m.get("has_media") and m.get("media_paths") and not m.get("media_missing")
            if has_images and [p for p in m.get("media_paths", []) if p]:
                vision_msgs.append(m)
            else:
                text_msgs.append(m)

        logger.info(
            "Phase 2: %d food messages (%d with images → %s, %d text-only → %s)",
            len(food_msgs), len(vision_msgs), model_vision, len(text_msgs), model_text,
        )

        estimate_results: dict[str, dict] = {}

        # Submit vision batch
        if vision_msgs:
            vision_requests = [_make_estimation_request(m, model_text, model_vision) for m in vision_msgs]
            logger.info("Submitting vision estimation batch (%d requests, model=%s)...", len(vision_requests), model_vision)
            vision_batch_id = _upload_and_submit_batch(vision_requests, f"estimation-vision-{model_vision}")
            vision_batch = _poll_batch(vision_batch_id)
            estimate_results.update(_download_batch_results(vision_batch))

        # Submit text batch
        if text_msgs:
            text_requests = [_make_estimation_request(m, model_text, model_vision) for m in text_msgs]
            logger.info("Submitting text estimation batch (%d requests, model=%s)...", len(text_requests), model_text)
            text_batch_id = _upload_and_submit_batch(text_requests, f"estimation-text-{model_text}")
            text_batch = _poll_batch(text_batch_id)
            estimate_results.update(_download_batch_results(text_batch))

        # Apply estimation results
        for msg in food_msgs:
            custom_id = f"estimate-{msg['msg_id']}"
            result = estimate_results.get(custom_id, {})
            output_text = result.get("output_text", "")

            if output_text:
                try:
                    estimation = parse_json_response(output_text)
                    for field, item_field in [
                        ("total_calories", "calories"),
                        ("total_protein_g", "protein_g"),
                        ("total_carbs_g", "carbs_g"),
                        ("total_fat_g", "fat_g"),
                    ]:
                        if field not in estimation:
                            estimation[field] = sum(
                                item.get(item_field, 0) for item in estimation.get("items", [])
                            )
                except Exception as e:
                    logger.warning("Failed to parse estimation for %s: %s", msg["msg_id"][:8], e)
                    estimation = _error_estimation(str(e))
            else:
                estimation = _error_estimation("batch error")

            msg["estimation"] = estimation
    else:
        logger.info("Phase 2: No food messages to estimate.")

    # Set estimation=None for non-food messages
    food_ids = {m["msg_id"] for m in food_msgs}
    for msg in uncached_msgs:
        if msg["msg_id"] not in food_ids:
            msg["estimation"] = None

    # Store all results in cache
    for msg in uncached_msgs:
        storage.store_inference(msg["msg_id"], {
            "classification": msg["classification"],
            "estimation": msg.get("estimation"),
            "model_text": model_text,
            "model_vision": model_vision,
        })

    return cached_msgs + uncached_msgs


def _error_estimation(reason: str) -> dict:
    return {
        "is_food": True,
        "meal_name": "unknown",
        "items": [],
        "total_calories": 0,
        "total_protein_g": 0,
        "total_carbs_g": 0,
        "total_fat_g": 0,
        "uncertainty": {
            "level": "high",
            "calories_range": [0, 0],
            "main_uncertainty_factors": ["estimation failed"],
        },
        "error": reason,
    }
