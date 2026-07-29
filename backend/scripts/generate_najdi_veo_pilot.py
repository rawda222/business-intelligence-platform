from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.cloud import storage
from google.genai import types


BACKEND_DIR = Path(__file__).resolve().parents[1]

PROMPT_PATH = (
    BACKEND_DIR
    / "generated"
    / "najdi_vertex_pilot"
    / "veo_prompt.txt"
)

OUTPUT_DIR = (
    BACKEND_DIR
    / "generated"
    / "najdi_vertex_pilot"
)

STATE_PATH = OUTPUT_DIR / "veo_generation_state.json"

LOCAL_VIDEO_PATH = OUTPUT_DIR / "najdi_veo_pilot_01.mp4"

load_dotenv(BACKEND_DIR / ".env")


PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]

LOCATION = (
    os.getenv("VERTEX_AI_LOCATION")
    or os.getenv("GOOGLE_CLOUD_LOCATION")
    or "us-central1"
)

VEO_MODEL = os.environ["VEO_MODEL"]

BASE_OUTPUT_GCS_URI = os.environ["VEO_OUTPUT_GCS_URI"].rstrip("/")


QUALITY_CONSTRAINTS = """
No deformed hands, no extra fingers, no missing fingers,
no duplicated meat, no plastic texture, no raw meat, no blood,
no unnaturally red meat, no morphing, no flickering,
no unstable objects, no text, no captions, no logo,
no watermark, no packaging, no human faces.
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one Najdi restaurant Veo pilot clip."
    )

    parser.add_argument(
        "--submit",
        action="store_true",
        help=(
            "Submit the real billable Veo request. "
            "Without this flag, the script performs a dry run."
        ),
    )

    return parser.parse_args()


def load_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {PROMPT_PATH}"
        )

    prompt = PROMPT_PATH.read_text(
        encoding="utf-8",
    ).strip()

    if not prompt:
        raise ValueError(
            "The Veo prompt file is empty."
        )

    final_prompt = f"{prompt}\n\n{QUALITY_CONSTRAINTS}"

    return final_prompt


def validate_settings(prompt: str) -> None:
    if PROJECT_ID != "generate-502313":
        raise ValueError(
            f"Unexpected project: {PROJECT_ID}"
        )

    if LOCATION != "us-central1":
        raise ValueError(
            f"Unexpected location: {LOCATION}"
        )

    if VEO_MODEL not in {
        "veo-3.1-generate-001",
        "veo-3.1-fast-generate-001",
        "veo-3.1-lite-generate-001",
    }:
        raise ValueError(
            f"Unexpected Veo model: {VEO_MODEL}"
        )

    expected_prefix = (
        "gs://generate-502313-veo-rawda-20260719/"
    )

    if not BASE_OUTPUT_GCS_URI.startswith(
        expected_prefix
    ):
        raise ValueError(
            "VEO_OUTPUT_GCS_URI points to an unexpected bucket."
        )

    if any(
        term in prompt
        for term in [
            "مطعم",
            "اللحم",
            "جاهز",
            "هنقرستيشن",
            "نينجا",
        ]
    ):
        raise ValueError(
            "The Veo prompt must not contain Arabic text."
        )


def create_client() -> genai.Client:
    return genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=LOCATION,
    )


def build_unique_output_uri() -> str:
    run_id = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")

    return (
        f"{BASE_OUTPUT_GCS_URI}/"
        f"run-{run_id}/"
    )


def save_state(data: dict) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    STATE_PATH.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


def extract_video_uri(operation) -> str:
    response = getattr(
        operation,
        "response",
        None,
    )

    if response is None:
        raise RuntimeError(
            "Veo completed without a response."
        )

    generated_videos = getattr(
        response,
        "generated_videos",
        None,
    )

    if not generated_videos:
        raise RuntimeError(
            "Veo returned no generated videos."
        )

    video = generated_videos[0].video

    video_uri = getattr(
        video,
        "uri",
        None,
    )

    if not video_uri:
        raise RuntimeError(
            "The generated video does not have a GCS URI."
        )

    return str(video_uri)


def split_gcs_uri(
    uri: str,
) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError(
            f"Invalid GCS URI: {uri}"
        )

    path = uri[5:]

    return tuple(
        path.split("/", 1)
    )


def download_video(
    video_uri: str,
) -> Path:
    bucket_name, blob_name = split_gcs_uri(
        video_uri
    )

    storage_client = storage.Client(
        project=PROJECT_ID,
    )

    blob = (
        storage_client
        .bucket(bucket_name)
        .blob(blob_name)
    )

    blob.download_to_filename(
        str(LOCAL_VIDEO_PATH)
    )

    return LOCAL_VIDEO_PATH


def run_dry_run(
    prompt: str,
    output_uri: str,
) -> None:
    print("DRY RUN — no Veo request was submitted")
    print("=" * 80)
    print(f"Project: {PROJECT_ID}")
    print(f"Location: {LOCATION}")
    print(f"Model: {VEO_MODEL}")
    print(f"Output: {output_uri}")
    print("Aspect ratio: 9:16")
    print("Resolution: 720p")
    print("Duration: 8 seconds")
    print("Number of videos: 1")
    print(f"Prompt words: {len(prompt.split())}")
    print("=" * 80)
    print(prompt)
    print("=" * 80)
    print(
        "Validation: PASS\n"
        "No video was generated and no Veo request was sent."
    )


def submit_generation(
    prompt: str,
    output_uri: str,
) -> None:
    client = create_client()

    print("Submitting one Veo pilot...")
    print(f"Model: {VEO_MODEL}")
    print(f"Output: {output_uri}")

    operation = client.models.generate_videos(
        model=VEO_MODEL,
        prompt=prompt,
        config=types.GenerateVideosConfig(
            aspect_ratio="9:16",
            resolution="720p",
            duration_seconds=8,
            number_of_videos=1,
            output_gcs_uri=output_uri,
        ),
    )

    operation_name = getattr(
        operation,
        "name",
        None,
    )

    save_state(
        {
            "status": "SUBMITTED",
            "project_id": PROJECT_ID,
            "location": LOCATION,
            "model": VEO_MODEL,
            "operation_name": operation_name,
            "output_gcs_uri": output_uri,
            "submitted_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }
    )

    print(f"Operation: {operation_name}")

    while not operation.done:
        print("Generation in progress...")
        time.sleep(15)

        operation = client.operations.get(
            operation
        )

    video_uri = extract_video_uri(
        operation
    )

    save_state(
        {
            "status": "COMPLETED",
            "project_id": PROJECT_ID,
            "location": LOCATION,
            "model": VEO_MODEL,
            "operation_name": operation_name,
            "output_gcs_uri": output_uri,
            "video_gcs_uri": video_uri,
            "completed_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }
    )

    print(f"Cloud video: {video_uri}")

    local_path = download_video(
        video_uri
    )

    print(f"Local video: {local_path}")
    print("Pilot generation completed successfully.")


def main() -> None:
    args = parse_args()

    prompt = load_prompt()

    validate_settings(
        prompt
    )

    output_uri = build_unique_output_uri()

    if not args.submit:
        run_dry_run(
            prompt=prompt,
            output_uri=output_uri,
        )
        return

    submit_generation(
        prompt=prompt,
        output_uri=output_uri,
    )


if __name__ == "__main__":
    main()