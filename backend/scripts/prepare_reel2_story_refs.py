from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter


BACKEND_DIR = Path(__file__).resolve().parents[1]

SOURCE_DIR = (
    BACKEND_DIR
    / "assets"
    / "najdi_campaign"
    / "24_reel2_story_refs"
)

OUTPUT_DIR = (
    BACKEND_DIR
    / "assets"
    / "najdi_campaign"
    / "25_reel2_story_ready"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

OUTPUT_NAMES = [
    "story_restaurant_ref.jpg",
    "story_kitchen_ref.jpg",
    "story_table_ref.jpg",
]


def resize_cover(
    image: Image.Image,
) -> Image.Image:
    scale = max(
        TARGET_WIDTH / image.width,
        TARGET_HEIGHT / image.height,
    )

    new_size = (
        round(image.width * scale),
        round(image.height * scale),
    )

    resized = image.resize(
        new_size,
        Image.Resampling.LANCZOS,
    )

    left = (
        resized.width - TARGET_WIDTH
    ) // 2

    top = (
        resized.height - TARGET_HEIGHT
    ) // 2

    return resized.crop(
        (
            left,
            top,
            left + TARGET_WIDTH,
            top + TARGET_HEIGHT,
        )
    )


def resize_contain(
    image: Image.Image,
) -> Image.Image:
    scale = min(
        TARGET_WIDTH / image.width,
        TARGET_HEIGHT / image.height,
    )

    new_size = (
        round(image.width * scale),
        round(image.height * scale),
    )

    return image.resize(
        new_size,
        Image.Resampling.LANCZOS,
    )


def prepare_image(
    source_path: Path,
    output_path: Path,
) -> None:
    source = Image.open(
        source_path
    ).convert("RGB")

    background = resize_cover(
        source
    )

    background = background.filter(
        ImageFilter.GaussianBlur(
            radius=36
        )
    )

    background = ImageEnhance.Brightness(
        background
    ).enhance(0.42)

    background = ImageEnhance.Color(
        background
    ).enhance(0.92)

    foreground = resize_contain(
        source
    )

    foreground = ImageEnhance.Contrast(
        foreground
    ).enhance(1.03)

    foreground = ImageEnhance.Color(
        foreground
    ).enhance(1.03)

    foreground = ImageEnhance.Sharpness(
        foreground
    ).enhance(1.06)

    x = (
        TARGET_WIDTH - foreground.width
    ) // 2

    y = (
        TARGET_HEIGHT - foreground.height
    ) // 2

    background.paste(
        foreground,
        (x, y),
    )

    background.save(
        output_path,
        format="JPEG",
        quality=95,
        optimize=True,
        progressive=True,
    )

    print(f"Source: {source_path.name}")
    print(f"Created: {output_path}")
    print()


def main() -> None:
    images = sorted(
        [
            path
            for path in SOURCE_DIR.iterdir()
            if (
                path.is_file()
                and path.suffix.lower()
                in SUPPORTED_EXTENSIONS
                and path.stat().st_size > 0
            )
        ],
        key=lambda path: path.name.lower(),
    )

    if len(images) != 3:
        raise RuntimeError(
            "Expected exactly 3 images inside "
            f"{SOURCE_DIR}, but found {len(images)}."
        )

    for source_path, output_name in zip(
        images,
        OUTPUT_NAMES,
        strict=True,
    ):
        prepare_image(
            source_path=source_path,
            output_path=(
                OUTPUT_DIR / output_name
            ),
        )


if __name__ == "__main__":
    main()