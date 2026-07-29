from __future__ import annotations

import json
import shutil
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

CAMPAIGN_DIR = (
    BACKEND_DIR
    / "assets"
    / "najdi_campaign"
)

READY_DIR = (
    CAMPAIGN_DIR
    / "23_reel2_veo_ready"
)

READY_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_JSON = (
    BACKEND_DIR
    / "scripts"
    / "reel2_veo_shots.json"
)


SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}


SHOT_CONFIG = [
    {
        "id": "reel2_chicken_rice",
        "folder": "04_chicken_rice_original",
        "output_name": "reel2_chicken_rice_source",
        "duration_seconds": 4,
        "prompt": (
            "A premium Saudi restaurant food advertisement. "
            "Start with a slow controlled cinematic push-in toward "
            "the chicken and rice. Gentle natural steam rises from "
            "the hot food. Preserve the exact chicken, rice, plate, "
            "garnish, portions, colors, lighting and composition from "
            "the source image. Only the camera and subtle steam move. "
            "No new food, no hands, no people, no duplication, "
            "no morphing, no text, no logo, no watermark, "
            "no dialogue and no camera shake."
        ),
    },
    {
        "id": "reel2_grill_action",
        "folder": "06_grill",
        "output_name": "reel2_grill_source",
        "duration_seconds": 4,
        "prompt": (
            "A cinematic Saudi grill advertisement. A slow controlled "
            "camera movement toward the grilled food with subtle heat "
            "shimmer, glowing warm highlights and very gentle natural "
            "grill smoke. Preserve the exact meat, plate, sides, "
            "portions, colors and composition. No new ingredients, "
            "no flames covering the food, no hands, no food movement, "
            "no morphing, no text, no logo, no watermark, "
            "no dialogue and no camera shake."
        ),
    },
    {
        "id": "reel2_hot_side",
        "folder": "08_hot_sides",
        "output_name": "reel2_hot_side_source",
        "duration_seconds": 4,
        "prompt": (
            "A polished close-up restaurant presentation of the hot "
            "side dish. A stable gentle push-in with soft natural steam "
            "and warm appetizing light. Preserve the exact dish, bowl, "
            "ingredients, portions, colors, background and composition. "
            "Only the camera and subtle steam move. No spoon movement, "
            "no hands, no new ingredients, no morphing, no text, "
            "no logo, no watermark, no dialogue and no camera shake."
        ),
    },
    {
        "id": "reel2_character",
        "folder": "15_character_ai",
        "output_name": "reel2_character_source",
        "duration_seconds": 4,
        "prompt": (
            "A polished animated restaurant mascot reveal. Preserve "
            "the exact cartoon character design, face, clothing, colors, "
            "food plate and environment. The existing character makes "
            "one small controlled presentation movement toward the camera "
            "while the camera performs a subtle push-in. No lip movement, "
            "no dialogue, no waving, no extra fingers, no body deformation, "
            "no new objects, no text, no logo, no watermark and "
            "no camera shake."
        ),
    },
]


def find_best_image(
    folder_name: str,
) -> Path:
    folder = (
        CAMPAIGN_DIR
        / folder_name
    )

    if not folder.exists():
        raise FileNotFoundError(
            f"Folder not found: {folder}"
        )

    candidates = [
        path
        for path in folder.rglob("*")
        if (
            path.is_file()
            and path.suffix.lower()
            in SUPPORTED_EXTENSIONS
        )
    ]

    if not candidates:
        raise FileNotFoundError(
            f"No supported images in: {folder}"
        )

    # Deterministic choice:
    # prefer the largest source file as the initial candidate.
    candidates.sort(
        key=lambda path: (
            path.stat().st_size,
            path.name.lower(),
        ),
        reverse=True,
    )

    return candidates[0]


def copy_selected_image(
    source_path: Path,
    output_stem: str,
) -> Path:
    output_path = (
        READY_DIR
        / (
            output_stem
            + source_path.suffix.lower()
        )
    )

    shutil.copy2(
        source_path,
        output_path,
    )

    return output_path


def relative_to_backend(
    path: Path,
) -> str:
    return path.relative_to(
        BACKEND_DIR
    ).as_posix()


def main() -> None:
    shots: list[dict] = []

    print(
        "Selected source images:"
    )

    for config in SHOT_CONFIG:
        source_path = find_best_image(
            config["folder"]
        )

        copied_path = copy_selected_image(
            source_path=source_path,
            output_stem=(
                config["output_name"]
            ),
        )

        print()
        print(
            config["id"]
        )
        print(
            "  Folder:",
            config["folder"],
        )
        print(
            "  Source:",
            source_path.name,
        )
        print(
            "  Size:",
            source_path.stat().st_size,
        )
        print(
            "  Copied:",
            copied_path,
        )

        shots.append(
            {
                "id": config["id"],
                "image": relative_to_backend(
                    copied_path
                ),
                "duration_seconds": (
                    config[
                        "duration_seconds"
                    ]
                ),
                "prompt": config["prompt"],
            }
        )

    OUTPUT_JSON.write_text(
        json.dumps(
            shots,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print(
        "Shot manifest created:",
        OUTPUT_JSON,
    )

if __name__ == "__main__":
    main()