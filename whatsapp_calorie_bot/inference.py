"""Two-stage AI inference pipeline: food classification + calorie estimation."""

import json
import logging

from whatsapp_calorie_bot.openai_client import call_openai_text, call_openai_vision, parse_json_response
from whatsapp_calorie_bot.storage import Storage

logger = logging.getLogger(__name__)

CLASSIFICATION_SYSTEM = """\
You are a food message classifier for WhatsApp messages. Your job is to determine \
whether a message is about food, drinks, meals, snacks, supplements, or groceries.

Respond with ONLY valid JSON in this exact format:
{
  "is_food": true/false,
  "food_confidence": 0.0 to 1.0,
  "reason_short": "brief explanation",
  "food_context": "meal" | "snack" | "drink" | "supplement" | "grocery" | "restaurant_menu" | "non_food"
}

Be generous in classifying food messages. If someone mentions eating, drinking, \
cooking, ordering, or any food item, classify as food. Messages about restaurants, \
recipes, grocery shopping, or meal planning also count.
"""

ESTIMATION_SYSTEM = """\
You are a nutrition expert who estimates calories and macronutrients from food descriptions \
and photos. Provide your best estimate even with limited information.

Respond with ONLY valid JSON in this exact format:
{
  "is_food": true,
  "meal_name": "short description of the meal",
  "items": [
    {
      "name": "item name",
      "estimated_grams": 150,
      "calories": 200,
      "protein_g": 20,
      "carbs_g": 10,
      "fat_g": 8,
      "assumptions": ["list of assumptions made"]
    }
  ],
  "total_calories": 200,
  "total_protein_g": 20,
  "total_carbs_g": 10,
  "total_fat_g": 8,
  "uncertainty": {
    "level": "low" | "medium" | "high",
    "calories_range": [min, max],
    "main_uncertainty_factors": ["list of factors"]
  },
  "followup_questions": ["questions that would improve the estimate"],
  "notes": "any additional notes"
}

Be specific about assumptions. When you see a photo, estimate portion sizes visually. \
If the description is vague, provide a reasonable middle-ground estimate and note the uncertainty.
"""

ESTIMATION_PROMPT_WITH_IMAGE = """\
Estimate the calories and macronutrients for this food.

Message text: {text}
Sender: {sender}

Look at the attached image and provide your best estimate. \
Consider typical portion sizes visible in the image.
"""

ESTIMATION_PROMPT_TEXT_ONLY = """\
Estimate the calories and macronutrients for this food.

Message text: {text}
Sender: {sender}

Based on the text description alone, provide your best estimate. \
Use typical portion sizes for the described items.
"""


def classify_message(msg: dict, model: str = "gpt-4.1-mini") -> dict:
    """Step A: Classify whether a message is about food."""
    prompt = f"Classify this WhatsApp message:\n\nSender: {msg['sender']}\nMessage: {msg['text']}"
    try:
        raw = call_openai_text(prompt, CLASSIFICATION_SYSTEM, model=model)
        result = parse_json_response(raw)
        return result
    except Exception as e:
        logger.error("Classification failed for msg %s: %s", msg.get("msg_id", "?"), e)
        return {
            "is_food": False,
            "food_confidence": 0.0,
            "reason_short": f"classification error: {e}",
            "food_context": "non_food",
        }


def estimate_calories(msg: dict, model_vision: str = "gpt-4.1", model_text: str = "gpt-4.1-mini") -> dict:
    """Step B: Estimate calories and macros for a food message."""
    has_images = msg.get("has_media") and msg.get("media_paths") and not msg.get("media_missing")
    image_paths = [p for p in msg.get("media_paths", []) if p] if has_images else []

    try:
        if image_paths:
            prompt = ESTIMATION_PROMPT_WITH_IMAGE.format(text=msg["text"], sender=msg["sender"])
            raw = call_openai_vision(prompt, ESTIMATION_SYSTEM, image_paths, model=model_vision)
        else:
            prompt = ESTIMATION_PROMPT_TEXT_ONLY.format(text=msg["text"], sender=msg["sender"])
            raw = call_openai_text(prompt, ESTIMATION_SYSTEM, model=model_text)

        result = parse_json_response(raw)

        # Validate key fields exist
        if "total_calories" not in result:
            result["total_calories"] = sum(item.get("calories", 0) for item in result.get("items", []))
        if "total_protein_g" not in result:
            result["total_protein_g"] = sum(item.get("protein_g", 0) for item in result.get("items", []))
        if "total_carbs_g" not in result:
            result["total_carbs_g"] = sum(item.get("carbs_g", 0) for item in result.get("items", []))
        if "total_fat_g" not in result:
            result["total_fat_g"] = sum(item.get("fat_g", 0) for item in result.get("items", []))

        return result

    except Exception as e:
        logger.error("Calorie estimation failed for msg %s: %s", msg.get("msg_id", "?"), e)
        # Retry once with a repair prompt
        try:
            repair_prompt = (
                f"Previous attempt failed. You MUST output valid JSON only.\n\n"
                f"Estimate calories for: {msg['text']}"
            )
            raw = call_openai_text(repair_prompt, ESTIMATION_SYSTEM, model=model_text)
            return parse_json_response(raw)
        except Exception as e2:
            logger.error("Retry also failed: %s", e2)
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
                "error": str(e2),
            }


def run_inference_pipeline(
    messages: list[dict],
    storage: Storage,
    force_redo: bool = False,
    food_confidence_threshold: float = 0.6,
    model_text: str = "gpt-4.1-mini",
    model_vision: str = "gpt-4.1",
) -> list[dict]:
    """Run the full two-stage inference pipeline on all messages."""
    enriched: list[dict] = []
    total = len(messages)

    for i, msg in enumerate(messages):
        msg_id = msg["msg_id"]
        logger.info("Processing message %d/%d (id=%s)...", i + 1, total, msg_id[:8])

        # Check cache
        if not force_redo:
            cached = storage.get_inference(msg_id)
            if cached:
                logger.debug("Using cached result for %s", msg_id[:8])
                msg["classification"] = cached.get("classification", {})
                msg["estimation"] = cached.get("estimation")
                enriched.append(msg)
                continue

        # Step A: Classify
        classification = classify_message(msg, model=model_text)
        msg["classification"] = classification

        is_food = classification.get("is_food", False)
        confidence = classification.get("food_confidence", 0.0)

        # Step B: Estimate (if food)
        estimation = None
        if is_food and confidence >= food_confidence_threshold:
            logger.info(
                "  -> Food detected (confidence=%.2f, context=%s). Estimating calories...",
                confidence,
                classification.get("food_context", "?"),
            )
            estimation = estimate_calories(msg, model_vision=model_vision, model_text=model_text)
        else:
            logger.debug("  -> Not food or low confidence (%.2f)", confidence)

        msg["estimation"] = estimation

        # Store result
        storage.store_inference(msg_id, {
            "classification": classification,
            "estimation": estimation,
            "model_text": model_text,
            "model_vision": model_vision,
        })

        enriched.append(msg)

    return enriched
