"""Two-stage AI inference pipeline: food classification + calorie estimation."""

import json
import logging

from whatsapp_calorie_bot.openai_client import call_openai_text, call_openai_vision, parse_json_response
from whatsapp_calorie_bot.storage import Storage

logger = logging.getLogger(__name__)

CLASSIFICATION_SYSTEM = """\
You are a food message classifier for WhatsApp messages in a food-tracking chat. \
Your job is to determine whether a message is about food, drinks, meals, snacks, \
supplements, or groceries.

Respond with ONLY valid JSON in this exact format:
{
  "is_food": true/false,
  "food_confidence": 0.0 to 1.0,
  "reason_short": "brief explanation",
  "food_context": "meal" | "snack" | "drink" | "supplement" | "grocery" | "restaurant_menu" | "non_food"
}

Be GENEROUS in classifying food messages. This is a food-tracking chat, so most \
messages are food-related. If someone mentions eating, drinking, cooking, ordering, \
or any food item, classify as food. Messages about restaurants, recipes, grocery \
shopping, or meal planning also count.
"""

ESTIMATION_SYSTEM = """\
You are a nutrition expert analyzing food photos and descriptions from a WhatsApp \
food-tracking chat between a person and their trainer.

Your analysis MUST follow this sequence:
1. IDENTIFY: What dish(es) or food items do you see? Describe them clearly.
2. PORTION SIZE: Estimate each portion using visual cues. A standard dinner plate \
is 25-27cm. A fork is ~20cm. Use these as references.
3. CALCULATE: Compute calories and macros from your portion estimates.

CRITICAL portion-size rules:
- Real-world portions are LARGER than textbook "serving sizes". Do NOT default to \
minimum portions.
- A chicken breast piece covering 1/3 of a plate is 200-250g, not 100-120g.
- A full bowl of food is typically 400-600g total weight.
- A generous spread of smoked salmon on toast is 80-120g of fish.
- Always account for cooking oils, butter, dressings, and sauces — they add \
100-200+ calories that are easy to miss.
- A poached/fried egg is ~60g. Avocado spread on toast is typically half an \
avocado (~80g).
- Cheesecake slice or small individual cake is 200-350g and 400-700+ kcal.
- When in doubt, estimate HIGHER — underestimating defeats the purpose of tracking.

If the image is NOT food (screenshot, selfie, document, etc.), set "is_food" to false.

Respond with ONLY valid JSON:
{
  "is_food": true,
  "visual_description": "Detailed description of what you see — the dish, \
ingredients, plating, and any visual cues about portion size",
  "meal_name": "Short name, e.g. 'Smoked salmon avocado toast with poached egg'",
  "items": [
    {
      "name": "item name",
      "portion_description": "How you estimated this portion — what visual cues \
you used (plate coverage, thickness, comparison to fork/hand, container size)",
      "estimated_grams": 250,
      "calories": 400,
      "protein_g": 30,
      "carbs_g": 20,
      "fat_g": 15,
      "assumptions": ["list of assumptions"]
    }
  ],
  "total_calories": 400,
  "total_protein_g": 30,
  "total_carbs_g": 20,
  "total_fat_g": 15,
  "uncertainty": {
    "level": "low" | "medium" | "high",
    "calories_range": [min, max],
    "main_uncertainty_factors": ["list"]
  },
  "notes": "any additional notes"
}
"""

ESTIMATION_PROMPT_WITH_IMAGE = """\
Analyze this food photo from a WhatsApp food-tracking chat.

Message text: {text}
Sender: {sender}

Step by step:
1. Describe exactly what you see in the image (dishes, ingredients, plating)
2. Estimate portion sizes using visual references (plate size, utensils, containers)
3. Calculate calories and macros — use realistic real-world portions, not minimums

Remember: people track food to get ACCURATE counts. Underestimating is worse than \
overestimating. Include cooking oils and hidden fats.
"""

ESTIMATION_PROMPT_TEXT_ONLY = """\
Estimate the calories and macronutrients for this food.

Message text: {text}
Sender: {sender}

Step by step:
1. Identify what food items are described
2. Estimate realistic portion sizes (not minimum textbook servings)
3. Calculate calories and macros — include cooking oils, sauces, and hidden fats

Remember: people track food to get ACCURATE counts. Underestimating is worse than \
overestimating.
"""


def _has_images(msg: dict) -> bool:
    """Check if a message has actual image files attached."""
    return bool(
        msg.get("has_media")
        and msg.get("media_paths")
        and not msg.get("media_missing")
    )


def classify_message(msg: dict, model: str = "gpt-4.1-mini") -> dict:
    """Step A: Classify whether a message is about food.

    For messages with attached images, auto-classify as likely food
    (the vision estimation model will verify).
    """
    if _has_images(msg):
        return {
            "is_food": True,
            "food_confidence": 0.85,
            "reason_short": "Photo in food-tracking chat — sending to vision model",
            "food_context": "meal",
        }

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
    has_imgs = _has_images(msg)
    image_paths = [p for p in msg.get("media_paths", []) if p] if has_imgs else []

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
                "visual_description": "",
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


def _process_single_message(
    msg: dict,
    storage: Storage,
    force_redo: bool,
    food_confidence_threshold: float,
    model_text: str,
    model_vision: str,
) -> dict:
    """Process a single message: classify and optionally estimate. Thread-safe."""
    msg_id = msg["msg_id"]

    if not force_redo:
        cached = storage.get_inference(msg_id)
        if cached:
            msg["classification"] = cached.get("classification", {})
            msg["estimation"] = cached.get("estimation")
            return msg

    classification = classify_message(msg, model=model_text)
    msg["classification"] = classification

    is_food = classification.get("is_food", False)
    confidence = classification.get("food_confidence", 0.0)

    estimation = None
    if is_food and confidence >= food_confidence_threshold:
        estimation = estimate_calories(msg, model_vision=model_vision, model_text=model_text)

        # Vision model may determine image is not food — update classification
        if estimation and estimation.get("is_food") is False:
            classification["is_food"] = False
            classification["food_confidence"] = 0.1
            classification["reason_short"] = "Vision model determined not food"
            classification["food_context"] = "non_food"
            msg["classification"] = classification
            estimation = None

    msg["estimation"] = estimation

    storage.store_inference(msg_id, {
        "classification": classification,
        "estimation": estimation,
        "model_text": model_text,
        "model_vision": model_vision,
    })

    return msg


def run_inference_pipeline(
    messages: list[dict],
    storage: Storage,
    force_redo: bool = False,
    food_confidence_threshold: float = 0.6,
    model_text: str = "gpt-4.1-mini",
    model_vision: str = "gpt-4.1",
    max_workers: int = 10,
) -> list[dict]:
    """Run the full two-stage inference pipeline on all messages in parallel."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    total = len(messages)
    enriched: list[dict | None] = [None] * total
    done_count = 0

    def _process(i: int, msg: dict) -> tuple[int, dict]:
        return i, _process_single_message(
            msg, storage, force_redo, food_confidence_threshold, model_text, model_vision,
        )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process, i, msg): i for i, msg in enumerate(messages)}
        for future in as_completed(futures):
            i, result = future.result()
            enriched[i] = result
            done_count += 1
            if done_count % 50 == 0 or done_count == total:
                logger.info("Processed %d/%d messages.", done_count, total)

    return enriched
