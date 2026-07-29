from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


BACKEND_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BACKEND_DIR / "generated" / "najdi_vertex_pilot"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BACKEND_DIR / ".env")


PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]

LOCATION = (
    os.getenv("VERTEX_AI_LOCATION")
    or os.getenv("GOOGLE_CLOUD_LOCATION")
    or "us-central1"
)

GEMINI_MODEL = os.getenv(
    "VERTEX_AI_MODEL",
    "gemini-2.5-flash",
)


MASTER_PROMPT = """
You are a senior food advertising creative director,
Saudi restaurant marketing strategist,
short-form video retention specialist,
food cinematographer, sound designer,
and Veo prompt engineer.

Create one production-ready Veo prompt for the opening hero shot
of a vertical advertisement for a traditional Najdi restaurant
in Riyadh, Saudi Arabia.

PROJECT:
Restaurant: مطعم شعبي نجدي
Hero product: اللحم المخصوص
Platforms: TikTok and Snapchat
Format: vertical 9:16

CLIENT REQUIREMENTS:

- The first two seconds must stop scrolling.
- Begin immediately with tender cooked lamb being pulled apart by hand.
- The meat must remain the dominant visual subject.
- Sell tenderness, heat, appetite, and the sensory experience.
- Use one continuous physically realistic action.
- Use a very slow controlled camera push-in.
- Use an extreme macro three-quarter side angle.
- Use warm soft side lighting.
- Use subtle natural steam.
- Use realistic cooked-meat fibers and natural moisture.
- Use slightly increased contrast and restrained saturation.
- End on a stable close-up of the separated meat fibers.
- Sound direction: synchronized natural meat-tearing texture,
  subtle steam sound, quiet restaurant ambience, no dialogue.

LIMITATIONS:

- There are no reference images.
- Do not claim that the food exactly represents the real restaurant dish.
- Do not invent Abu Dawas, a customer, an employee,
  a testimonial, a restaurant interior, a price,
  a discount, a promotion, or packaging.
- Show only cooked food and two natural adult hands.
- Do not generate text, Arabic lettering, logos,
  watermarks, captions, or delivery-app logos.

The final Veo prompt must:

- Be written only in English.
- Describe exactly one continuous shot.
- Start the food action from the first frame.
- Be between 100 and 160 English words.
- Include subject, action, camera, lighting, mood,
  sound direction, ending frame, and concise negative constraints.
- Include this exact visual continuity phrase:

traditional Najdi food commercial, warm soft lighting,
realistic cooked lamb, natural brown color, golden rice,
subtle steam, shallow depth of field

Return valid JSON only with exactly these fields:

{
  "concept_name": "string",
  "duration_seconds": 8,
  "veo_prompt": "string"
}
""".strip()


def validate_result(result: dict) -> None:
    expected_keys = {
        "concept_name",
        "duration_seconds",
        "veo_prompt",
    }

    if set(result) != expected_keys:
        raise ValueError(
            f"Unexpected JSON keys: {set(result)}"
        )

    if result["duration_seconds"] != 8:
        raise ValueError(
            "duration_seconds must equal 8."
        )

    prompt = result["veo_prompt"].strip()
    word_count = len(prompt.split())

    if not 100 <= word_count <= 160:
        raise ValueError(
            f"Prompt has {word_count} words; expected 100-160."
        )

    required_phrase = (
        "traditional Najdi food commercial, warm soft lighting, "
        "realistic cooked lamb, natural brown color, golden rice, "
        "subtle steam, shallow depth of field"
    )

    if required_phrase.lower() not in prompt.lower():
        raise ValueError(
            "Required visual continuity phrase is missing."
        )

    forbidden_arabic = [
        "مطعم",
        "اللحم",
        "جاهز",
        "هنقرستيشن",
        "نينجا",
        "أبو",
    ]

    for term in forbidden_arabic:
        if term in prompt:
            raise ValueError(
                f"Arabic term found in Veo prompt: {term}"
            )


def main() -> None:
    client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION,
)

    print("Building Veo prompt with Gemini...")
    print(f"Project: {PROJECT_ID}")
    print(f"Location: {LOCATION}")
    print(f"Gemini model: {GEMINI_MODEL}")

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=MASTER_PROMPT,
        config=types.GenerateContentConfig(
            temperature=0.5,
            response_mime_type="application/json",
        ),
    )

    if not response.text:
        raise RuntimeError(
            "Gemini returned an empty response."
        )

    result = json.loads(response.text)
    validate_result(result)

    json_path = OUTPUT_DIR / "pilot_prompt_plan.json"
    prompt_path = OUTPUT_DIR / "veo_prompt.txt"

    json_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    prompt_path.write_text(
        result["veo_prompt"],
        encoding="utf-8",
    )

    print("\nValidation: PASS")
    print(f"Concept: {result['concept_name']}")
    print(
        "Prompt words:",
        len(result["veo_prompt"].split()),
    )
    print(f"JSON saved: {json_path}")
    print(f"Prompt saved: {prompt_path}")

    print("\nVEO PROMPT")
    print("=" * 80)
    print(result["veo_prompt"])
    print("=" * 80)


if __name__ == "__main__":
    main()