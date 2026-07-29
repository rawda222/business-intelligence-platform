from __future__ import annotations

import argparse
import json
import mimetypes
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.cloud import storage
from google.genai import types


BACKEND_DIR = Path(__file__).resolve().parents[1]

SHOTS_PATH = BACKEND_DIR / "scripts" / "najdi_shots.json"

OUTPUT_DIR = (
    BACKEND_DIR
    / "generated"
    / "najdi_image_to_video"
)

STATE_DIR = OUTPUT_DIR / "states"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BACKEND_DIR / ".env")


PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]

LOCATION = (
    os.getenv("VERTEX_AI_LOCATION")
    or os.getenv("GOOGLE_CLOUD_LOCATION")
    or "us-central1"
)

VEO_MODEL = os.environ["VEO_MODEL"]

BASE_OUTPUT_GCS_URI = os.environ[
    "VEO_OUTPUT_GCS_URI"
].rstrip("/")


ALLOWED_DURATIONS = {4, 6, 8}

ALLOWED_MODELS = {
    "veo-3.1-generate-001",
    "veo-3.1-fast-generate-001",
    "veo-3.1-lite-generate-001",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Animate an existing restaurant image "
            "using Veo Image-to-Video."
        )
    )

    parser.add_argument(
        "--shot",
        required=True,
        help=(
            "Shot id from najdi_shots.json, "
            "for example hero_lamb."
        ),
    )

    parser.add_argument(
        "--submit",
        action="store_true",
        help=(
            "Submit the real billable request. "
            "Without this flag, perform a dry run."
        ),
    )

    return parser.parse_args()


def load_shots() -> list:
    if not SHOTS_PATH.exists():
        raise FileNotFoundError(
            f"Shots file not found: {SHOTS_PATH}"
        )

    shots = json.loads(
        SHOTS_PATH.read_text(
            encoding="utf-8-sig"
        )
    )

    if not isinstance(shots, list):
        raise ValueError(
            "najdi_shots.json must contain a JSON list."
        )

    return shots


def get_shot(shot_id: str) -> dict:
    shots = load_shots()

    for shot in shots:
        if shot.get("id") == shot_id:
            return shot

    available = ", ".join(
        str(shot.get("id"))
        for shot in shots
    )

    raise ValueError(
        f"Unknown shot: {shot_id}. "
        f"Available: {available}"
    )


def get_image_path(shot: dict) -> Path:
    image_value = shot.get("image")

    if not image_value:
        raise ValueError(
            "The shot does not contain an image path."
        )

    image_path = (
        BACKEND_DIR / image_value
    ).resolve()

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    if not image_path.is_file():
        raise ValueError(
            f"Image path is not a file: {image_path}"
        )

    if image_path.stat().st_size == 0:
        raise ValueError(
            f"Image file is empty: {image_path}"
        )

    return image_path


def get_mime_type(image_path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(
        image_path.name
    )

    if mime_type not in {
        "image/jpeg",
        "image/png",
        "image/webp",
    }:
        raise ValueError(
            f"Unsupported image type: {mime_type}"
        )

    return mime_type


def validate_shot(
    shot: dict,
    image_path: Path,
) -> None:
    if PROJECT_ID != "generate-502313":
        raise ValueError(
            f"Unexpected project: {PROJECT_ID}"
        )

    if LOCATION != "us-central1":
        raise ValueError(
            f"Unexpected location: {LOCATION}"
        )

    if VEO_MODEL not in ALLOWED_MODELS:
        raise ValueError(
            f"Unexpected Veo model: {VEO_MODEL}"
        )

    if not BASE_OUTPUT_GCS_URI.startswith(
        "gs://generate-502313-veo-rawda-20260719/"
    ):
        raise ValueError(
            "Unexpected Cloud Storage bucket."
        )

    duration = shot.get("duration_seconds")

    if duration not in ALLOWED_DURATIONS:
        raise ValueError(
            f"Duration must be 4, 6 or 8. "
            f"Received: {duration}"
        )

    prompt = str(
        shot.get("prompt", "")
    ).strip()

    if not prompt:
        raise ValueError(
            "The shot prompt is empty."
        )

    get_mime_type(image_path)


def split_gcs_uri(
    uri: str,
) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError(
            f"Invalid GCS URI: {uri}"
        )

    path = uri[5:]
    parts = path.split("/", 1)

    bucket_name = parts[0]
    blob_name = parts[1] if len(parts) > 1 else ""

    return bucket_name, blob_name


def create_run_id() -> str:
    return datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")


def create_output_uri(
    shot_id: str,
    run_id: str,
) -> str:
    return (
        f"{BASE_OUTPUT_GCS_URI}/"
        f"image-to-video/"
        f"{shot_id}/"
        f"run-{run_id}/"
    )


def upload_image(
    image_path: Path,
    shot_id: str,
    run_id: str,
) -> str:
    bucket_name, base_prefix = split_gcs_uri(
        BASE_OUTPUT_GCS_URI
    )

    blob_name = "/".join(
        part.strip("/")
        for part in [
            base_prefix,
            "inputs",
            shot_id,
            run_id,
            image_path.name,
        ]
        if part.strip("/")
    )

    client = storage.Client(
        project=PROJECT_ID
    )

    blob = (
        client
        .bucket(bucket_name)
        .blob(blob_name)
    )

    blob.upload_from_filename(
        str(image_path),
        content_type=get_mime_type(
            image_path
        ),
    )

    return f"gs://{bucket_name}/{blob_name}"


def create_veo_client() -> genai.Client:
    return genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=LOCATION,
    )


def save_state(
    shot_id: str,
    data: dict,
) -> Path:
    state_path = (
        STATE_DIR / f"{shot_id}.json"
    )

    state_path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    return state_path


def get_video_uri(operation) -> str:
    response = getattr(
        operation,
        "response",
        None,
    )

    if response is None:
        raise RuntimeError(
            "Veo completed without a response."
        )

    videos = getattr(
        response,
        "generated_videos",
        None,
    )

    if not videos:
        raise RuntimeError(
            "Veo returned no generated videos."
        )

    video = getattr(
        videos[0],
        "video",
        None,
    )

    if video is None:
        raise RuntimeError(
            "Generated video payload is missing."
        )

    video_uri = getattr(
        video,
        "uri",
        None,
    )

    if not video_uri:
        raise RuntimeError(
            "Generated video has no GCS URI."
        )

    return str(video_uri)


def download_video(
    video_uri: str,
    shot_id: str,
) -> Path:
    bucket_name, blob_name = split_gcs_uri(
        video_uri
    )

    client = storage.Client(
        project=PROJECT_ID
    )

    blob = (
        client
        .bucket(bucket_name)
        .blob(blob_name)
    )

    local_path = (
        OUTPUT_DIR / f"{shot_id}.mp4"
    )

    blob.download_to_filename(
        str(local_path)
    )

    return local_path


def dry_run(
    shot: dict,
    image_path: Path,
    output_uri: str,
) -> None:
    print(
        "DRY RUN — no upload and "
        "no Veo request"
    )

    print("=" * 80)
    print(f"Shot: {shot['id']}")
    print(f"Image: {image_path}")
    print(f"Image exists: {image_path.exists()}")
    print(f"Image bytes: {image_path.stat().st_size}")
    print(f"MIME type: {get_mime_type(image_path)}")
    print(f"Project: {PROJECT_ID}")
    print(f"Location: {LOCATION}")
    print(f"Model: {VEO_MODEL}")
    print(f"Output: {output_uri}")
    print("Aspect ratio: 9:16")
    print("Resolution: 720p")
    print(
        f"Duration: "
        f"{shot['duration_seconds']} seconds"
    )
    print("Number of videos: 1")
    print("=" * 80)
    print(shot["prompt"])
    print("=" * 80)
    print(
        "Validation: PASS\n"
        "No billable request was sent."
    )


def submit(
    shot: dict,
    image_path: Path,
    output_uri: str,
    run_id: str,
) -> None:
    shot_id = str(shot["id"])

    print(
        f"Uploading source image: {image_path}"
    )

    input_gcs_uri = upload_image(
        image_path=image_path,
        shot_id=shot_id,
        run_id=run_id,
    )

    print(
        f"Uploaded image: {input_gcs_uri}"
    )

    source_image = types.Image(
        gcs_uri=input_gcs_uri,
        mime_type=get_mime_type(
            image_path
        ),
    )

    client = create_veo_client()

    print(
        f"Submitting Veo Image-to-Video: "
        f"{shot_id}"
    )

    operation = client.models.generate_videos(
        model=VEO_MODEL,
        prompt=shot["prompt"],
        image=source_image,
        config=types.GenerateVideosConfig(
            aspect_ratio="9:16",
            resolution="720p",
            duration_seconds=shot[
                "duration_seconds"
            ],
            number_of_videos=1,
            output_gcs_uri=output_uri,
        ),
    )

    operation_name = getattr(
        operation,
        "name",
        None,
    )

    state_path = save_state(
        shot_id,
        {
            "status": "SUBMITTED",
            "shot_id": shot_id,
            "image_path": str(image_path),
            "input_gcs_uri": input_gcs_uri,
            "operation_name": operation_name,
            "output_gcs_uri": output_uri,
            "model": VEO_MODEL,
            "submitted_at": datetime.now(
                timezone.utc
            ).isoformat(),
        },
    )

    print(f"Operation: {operation_name}")
    print(f"State: {state_path}")

    while not operation.done:
        print(
            f"{shot_id}: generation in progress..."
        )

        time.sleep(15)

        operation = client.operations.get(
            operation
        )

    video_uri = get_video_uri(
        operation
    )

    save_state(
        shot_id,
        {
            "status": "COMPLETED",
            "shot_id": shot_id,
            "image_path": str(image_path),
            "input_gcs_uri": input_gcs_uri,
            "operation_name": operation_name,
            "output_gcs_uri": output_uri,
            "video_gcs_uri": video_uri,
            "model": VEO_MODEL,
            "completed_at": datetime.now(
                timezone.utc
            ).isoformat(),
        },
    )

    print(f"Cloud video: {video_uri}")

    local_path = download_video(
        video_uri=video_uri,
        shot_id=shot_id,
    )

    print(f"Local video: {local_path}")
    print(
        f"{shot_id}: generation completed."
    )


def main() -> None:
    args = parse_args()

    shot = get_shot(
        args.shot
    )

    image_path = get_image_path(
        shot
    )

    validate_shot(
        shot=shot,
        image_path=image_path,
    )

    run_id = create_run_id()

    output_uri = create_output_uri(
        shot_id=str(shot["id"]),
        run_id=run_id,
    )

    if not args.submit:
        dry_run(
            shot=shot,
            image_path=image_path,
            output_uri=output_uri,
        )
        return

    submit(
        shot=shot,
        image_path=image_path,
        output_uri=output_uri,
        run_id=run_id,
    )


if __name__ == "__main__":
    main()
