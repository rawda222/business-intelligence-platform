from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter


BACKEND_DIR = Path(__file__).resolve().parents[1]

CAMPAIGN_DIR = (
    BACKEND_DIR
    / "assets"
    / "najdi_campaign"
)

INPUT_DIR = (
    CAMPAIGN_DIR
    / "02_lamb_hero"
)

OUTPUT_DIR = (
    CAMPAIGN_DIR
    / "19_veo_ready"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920


SOURCE_BASENAMES = [
    "lamb_hero_vertical_01",
    "lamb_hero_platter_01",
    "lamb_hero_platter_02",
    "lamb_hero_platter_03",
]


SUPPORTED_EXTENSIONS = [
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
]


def find_source_image(
    basename: str,
) -> Path:
    matches = []

    for extension in SUPPORTED_EXTENSIONS:
        candidate = (
            INPUT_DIR
            / f"{basename}{extension}"
        )

        if candidate.exists():
            matches.append(candidate)

    if not matches:
        raise FileNotFoundError(
            "Could not find an image for "
            f"{basename} inside {INPUT_DIR}"
        )

    if len(matches) > 1:
        raise RuntimeError(
            "More than one image has the same "
            f"base name: {matches}"
        )

    return matches[0]


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

    # Fill the vertical frame without stretching.
    background = resize_cover(source)

    background = background.filter(
        ImageFilter.GaussianBlur(
            radius=38
        )
    )

    background = ImageEnhance.Brightness(
        background
    ).enhance(0.38)

    background = ImageEnhance.Color(
        background
    ).enhance(0.88)

    # Preserve the full original food image.
    foreground = resize_contain(source)

    foreground = ImageEnhance.Contrast(
        foreground
    ).enhance(1.04)

    foreground = ImageEnhance.Color(
        foreground
    ).enhance(1.04)

    foreground = ImageEnhance.Sharpness(
        foreground
    ).enhance(1.08)

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

    print(
        f"Created: {output_path}"
    )

    print(
        f"Source: {source_path.name}"
    )

    print(
        f"Output size: {background.size}"
    )


def main() -> None:
    for basename in SOURCE_BASENAMES:
        source_path = find_source_image(
            basename
        )

        output_path = (
            OUTPUT_DIR
            / f"{basename}_9x16.jpg"
        )

        prepare_image(
            source_path=source_path,
            output_path=output_path,
        )


if __name__ == "__main__":
    main()