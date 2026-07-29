from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


BACKEND_DIR = Path(__file__).resolve().parents[1]

OUTPUT_DIR = (
    BACKEND_DIR
    / "generated"
    / "najdi_vertex_pilot"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

LOCAL_IMAGE_PATH = (
    OUTPUT_DIR
    / "najdi_meat_keyframe_01.png"
)

PROMPT_PATH = (
    OUTPUT_DIR
    / "nano_banana_prompt.txt"
)

load_dotenv(BACKEND_DIR / ".env")


PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]

IMAGE_MODEL = os.environ["IMAGE_MODEL"]

IMAGE_MODEL_LOCATION = os.getenv(
    "IMAGE_MODEL_LOCATION",
    "global",
)


IMAGE_PROMPT = """
Create one vertical 9:16 photorealistic keyframe for a premium
commercial food advertisement for a traditional Najdi restaurant
in Riyadh, Saudi Arabia.

Show an extreme macro three-quarter side view of a large piece of
fully cooked, tender Najdi-style lamb held naturally between two
clean adult hands. Capture the exact instant when the hands have just
begun pulling the meat apart. A small separation already reveals
realistic tender fibers and natural moisture, creating a strong
starting frame that can later continue into a meat-tearing animation.

The cooked lamb is the dominant visual subject and occupies most of
the frame. Warm golden rice appears beneath it as a secondary element.
Soft natural steam rises around the meat. Use warm soft side lighting,
realistic natural brown cooked-meat color, controlled highlights,
slightly increased contrast, restrained saturation, shallow depth of
field, and a softly blurred authentic food-serving background.

Composition must be stable and physically plausible, with natural
hand anatomy, correct fingers, realistic grip, consistent food scale,
and clean safe space in the upper-left corner for branding to be added
later during editing.

Premium commercial food photography, cinematic realism, appetizing
but believable texture, professional advertising composition.

Do not generate text, Arabic lettering, captions, logos, watermarks,
prices, delivery-app logos, packaging, restaurant signs, human faces,
customers, employees, or a visible restaurant interior.

No raw meat, no blood, no unnatural red color, no plastic texture,
no fake gloss, no orange rice, no duplicated meat, no floating food,
no extra fingers, no missing fingers, no deformed hands, no fused
fingers, no unstable utensils, no unrealistic portion size, no
cartoon style, and no CGI-looking materials.
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate one Najdi restaurant keyframe "
            "with Nano Banana."
        )
    )

    parser.add_argument(
        "--submit",
        action="store_true",
        help=(
            "Send the real image-generation request. "
            "Without this flag, only perform a dry run."
        ),
    )

    return parser.parse_args()


def validate_settings() -> None:
    if PROJECT_ID != "generate-502313":
        raise ValueError(
            f"Unexpected project: {PROJECT_ID}"
        )

    if IMAGE_MODEL != "gemini-3.1-flash-image":
        raise ValueError(
            f"Unexpected image model: {IMAGE_MODEL}"
        )

    if IMAGE_MODEL_LOCATION != "global":
        raise ValueError(
            "Nano Banana 2 must use the configured "
            "global location."
        )

    if any(
        term in IMAGE_PROMPT
        for term in [
            "مطعم",
            "اللحم",
            "جاهز",
            "هنقرستيشن",
            "نينجا",
        ]
    ):
        raise ValueError(
            "Image prompt must not contain Arabic text."
        )


def run_dry_run() -> None:
    PROMPT_PATH.write_text(
        IMAGE_PROMPT,
        encoding="utf-8",
    )

    print("DRY RUN — no image request was submitted")
    print("=" * 80)
    print(f"Project: {PROJECT_ID}")
    print(f"Location: {IMAGE_MODEL_LOCATION}")
    print(f"Model: {IMAGE_MODEL}")
    print("Aspect ratio: 9:16")
    print("Image size: 1K")
    print(f"Prompt words: {len(IMAGE_PROMPT.split())}")
    print(f"Prompt saved: {PROMPT_PATH}")
    print("=" * 80)
    print(IMAGE_PROMPT)
    print("=" * 80)
    print(
        "Validation: PASS\n"
        "No image was generated."
    )


def generate_image() -> None:
    client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=IMAGE_MODEL_LOCATION,
    )

    print("Submitting one Nano Banana keyframe...")
    print(f"Model: {IMAGE_MODEL}")

    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=IMAGE_PROMPT,
        config=types.GenerateContentConfig(
            response_modalities=[
                "IMAGE",
                "TEXT",
            ],
            image_config=types.ImageConfig(
                aspect_ratio="9:16",
                image_size="1K",
                output_mime_type="image/png",
            ),
        ),
    )

    if not response.candidates:
        raise RuntimeError(
            "Nano Banana returned no candidates."
        )

    candidate = response.candidates[0]

    if candidate.finish_reason != types.FinishReason.STOP:
        raise RuntimeError(
            "Image generation did not finish normally. "
            f"Reason: {candidate.finish_reason}"
        )

    image_saved = False

    for part in candidate.content.parts:
        if getattr(part, "thought", False):
            continue

        inline_data = getattr(
            part,
            "inline_data",
            None,
        )

        if inline_data and inline_data.data:
            LOCAL_IMAGE_PATH.write_bytes(
                inline_data.data
            )

            image_saved = True
            break

    if not image_saved:
        raise RuntimeError(
            "The response contained no generated image."
        )

    PROMPT_PATH.write_text(
        IMAGE_PROMPT,
        encoding="utf-8",
    )

    print(f"Image saved: {LOCAL_IMAGE_PATH}")
    print(f"Prompt saved: {PROMPT_PATH}")
    print(
        "Review the image before sending it to Veo."
    )


def main() -> None:
    args = parse_args()

    validate_settings()

    if not args.submit:
        run_dry_run()
        return

    generate_image()


if __name__ == "__main__":
    main()