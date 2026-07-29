from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

VIDEO_DIR = (
    BACKEND_DIR
    / "generated"
    / "najdi_image_to_video"
)

ASSET_DIR = (
    BACKEND_DIR
    / "assets"
    / "najdi_campaign"
)

AUDIO_DIR = ASSET_DIR / "20_audio"

WORK_DIR = (
    BACKEND_DIR
    / "generated"
    / "najdi_ffmpeg_work"
)

OUTPUT_DIR = (
    BACKEND_DIR
    / "generated"
    / "najdi_final_ads"
)

WORK_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


OUTPUT_PATH = (
    OUTPUT_DIR
    / "najdi_lamb_special_v2_client_preview.mp4"
)


VIDEO_SEGMENTS = [
    {
        "id": "01_hook",
        "path": VIDEO_DIR / "hero_lamb_action.mp4",
        "duration": 4,
    },
    {
        "id": "02_lamb_detail",
        "path": VIDEO_DIR / "lamb_detail_slider.mp4",
        "duration": 6,
    },
    {
        "id": "03_lamb_action_reprise",
        "path": VIDEO_DIR / "hero_lamb_action.mp4",
        "duration": 4,
    },
]


IMAGE_SEGMENTS = [
    {
        "id": "04_lamb_ribs",
        "path": (
            ASSET_DIR
            / "06_grill"
            / "grilled_lamb_ribs_01.jpg"
        ),
        "duration": 3,
        "motion": "push_in",
    },
    {
        "id": "05_lamb_feast",
        "path": (
            ASSET_DIR
            / "03_lamb_feasts"
            / "lamb_feast_table_01.jpg"
        ),
        "duration": 3,
        "motion": "pull_back",
    },
    {
        "id": "06_rotisserie_action",
        "path": (
            ASSET_DIR
            / "07_rotisserie"
            / "rotisserie_chicken_wall_01.jpg"
        ),
        "duration": 3,
        "motion": "push_in",
    },
    {
        "id": "07_restaurant_identity",
        "path": (
            ASSET_DIR
            / "11_restaurant_exterior"
            / "restaurant_exterior_night_01.jpg"
        ),
        "duration": 3,
        "motion": "push_in",
    },
]


END_CARD_DURATION = 4
TOTAL_DURATION = 30


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
) -> None:
    print()
    print("$", " ".join(command))

    subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        check=True,
    )


def require_program(name: str) -> None:
    executable = shutil.which(name)

    if executable is None:
        raise FileNotFoundError(
            f"Required program not found in PATH: {name}"
        )

    print(f"{name}: {executable}")


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Expected a file: {path}"
        )

    if path.stat().st_size == 0:
        raise ValueError(
            f"File is empty: {path}"
        )


def normalize_video(
    input_path: Path,
    output_path: Path,
    duration: int,
) -> None:
    video_filter = (
        "scale=1080:1920:"
        "force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "fps=30,"
        "eq=saturation=1.04:"
        "contrast=1.04:"
        "brightness=0.005,"
        "format=yuv420p"
    )

    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-t",
            str(duration),
            "-vf",
            video_filter,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )


def create_image_segment(
    input_path: Path,
    output_path: Path,
    duration: int,
    motion: str,
) -> None:
    del motion

    video_filter = (
        "scale=1080:1920:"
        "force_original_aspect_ratio=decrease,"
        "pad=1080:1920:"
        "(ow-iw)/2:"
        "(oh-ih)/2:"
        "color=0x211713,"
        "setsar=1,"
        "fps=30,"
        "eq=saturation=1.04:"
        "contrast=1.04:"
        "brightness=0.005,"
        "format=yuv420p"
    )

    run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-framerate",
            "30",
            "-i",
            str(input_path),
            "-t",
            str(duration),
            "-vf",
            video_filter,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )


def create_end_card(
    output_path: Path,
) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            (
                "color="
                "c=0x211713:"
                "s=1080x1920:"
                "r=30:"
                f"d={END_CARD_DURATION}"
            ),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ]
    )


def write_concat_file(
    segment_paths: list[Path],
) -> Path:
    concat_path = WORK_DIR / "segments.txt"

    lines = []

    for path in segment_paths:
        safe_path = str(
            path.resolve()
        ).replace(
            "\\",
            "/",
        )

        lines.append(
            f"file '{safe_path}'"
        )

    concat_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    return concat_path


def concatenate_segments(
    concat_path: Path,
    output_path: Path,
) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "19",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-an",
            str(output_path),
        ]
    )


def write_ass_file() -> Path:
    ass_path = WORK_DIR / "najdi_branding.ass"

    ass_content = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes
WrapStyle: 2
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Brand,Tahoma,46,&H00F6E8D5,&H00F6E8D5,&H001B1210,&HFF000000,-1,0,0,0,100,100,0,0,1,2,1,7,55,55,55,1
Style: Hook,Tahoma,72,&H00FFFFFF,&H00FFFFFF,&H00201511,&HFF000000,-1,0,0,0,100,100,0,0,1,3,1,5,75,75,0,1
Style: Price,Tahoma,94,&H0000D7FF,&H0000D7FF,&H00201511,&HFF000000,-1,0,0,0,100,100,0,0,1,4,1,5,100,100,0,1
Style: Middle,Tahoma,58,&H00FFFFFF,&H00FFFFFF,&H00201511,&HFF000000,-1,0,0,0,100,100,0,0,1,3,1,5,70,70,0,1
Style: EndTitle,Tahoma,68,&H00F6E8D5,&H00F6E8D5,&H00170F0C,&HFF000000,-1,0,0,0,100,100,0,0,1,2,1,5,80,80,0,1
Style: EndProduct,Tahoma,86,&H00FFFFFF,&H00FFFFFF,&H00170F0C,&HFF000000,-1,0,0,0,100,100,0,0,1,3,1,5,80,80,0,1
Style: EndPrice,Tahoma,104,&H0000D7FF,&H0000D7FF,&H00170F0C,&HFF000000,-1,0,0,0,100,100,0,0,1,4,1,5,80,80,0,1
Style: EndCTA,Tahoma,40,&H00F6E8D5,&H00F6E8D5,&H00170F0C,&HFF000000,-1,0,0,0,100,100,0,0,1,2,1,5,50,50,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 5,0:00:00.00,0:00:26.00,Brand,,0,0,0,,{\an7\pos(55,70)\fad(100,150)}مطعم شعبي نجدي
Dialogue: 6,0:00:00.00,0:00:03.20,Hook,,0,0,0,,{\an5\pos(540,1460)\fad(70,180)}اللحم المخصوص
Dialogue: 7,0:00:00.15,0:00:03.20,Price,,0,0,0,,{\an5\pos(540,1600)\fad(80,180)}39 ريال
Dialogue: 6,0:00:04.00,0:00:09.80,Middle,,0,0,0,,{\an5\pos(540,1580)\fad(150,180)}طعم أصيل... بنكهة خاصة
Dialogue: 6,0:00:14.00,0:00:19.80,Middle,,0,0,0,,{\an5\pos(540,1580)\fad(150,180)}اللحم بطل السفرة
Dialogue: 3,0:00:26.00,0:00:30.00,EndTitle,,0,0,0,,{\an5\pos(540,500)\fad(180,200)}مطعم شعبي نجدي
Dialogue: 3,0:00:26.60,0:00:30.00,EndProduct,,0,0,0,,{\an5\pos(540,780)\fad(160,200)}اللحم المخصوص
Dialogue: 4,0:00:27.20,0:00:30.00,EndPrice,,0,0,0,,{\an5\pos(540,1060)\fad(150,200)}39 ريال
Dialogue: 3,0:00:28.00,0:00:30.00,EndCTA,,0,0,0,,{\an5\pos(540,1370)\fad(160,200)}اطلبه الآن عبر
Dialogue: 3,0:00:28.35,0:00:30.00,EndCTA,,0,0,0,,{\an5\pos(540,1460)\fad(160,200)}جاهز - هنقرستيشن - نينجا
"""

    ass_path.write_text(
        ass_content,
        encoding="utf-8-sig",
    )

    return ass_path


def apply_branding(
    input_path: Path,
    ass_path: Path,
    output_path: Path,
) -> None:
    # Run FFmpeg inside WORK_DIR so the subtitle
    # filename has no Windows drive-letter escaping.
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            input_path.name,
            "-vf",
            (
                "subtitles="
                f"filename='{ass_path.name}'"
            ),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            output_path.name,
        ],
        cwd=WORK_DIR,
    )


def add_audio_or_silence(
    input_path: Path,
    output_path: Path,
) -> None:
    impact_path = (
        AUDIO_DIR / "impact.wav"
    )

    steam_path = (
        AUDIO_DIR / "steam.wav"
    )

    serving_path = (
        AUDIO_DIR / "serving.wav"
    )

    logo_hit_path = (
        AUDIO_DIR / "logo_hit.wav"
    )

    audio_assets = [
        ("impact", impact_path),
        ("steam", steam_path),
        ("serving", serving_path),
        ("logo_hit", logo_hit_path),
    ]

    existing = [
        (name, path)
        for name, path in audio_assets
        if path.exists()
        and path.is_file()
        and path.stat().st_size > 0
    ]

    if not existing:
        print(
            "No sound effects found. "
            "Creating a silent AAC track."
        )

        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(input_path),
                "-f",
                "lavfi",
                "-i",
                (
                    "anullsrc="
                    "channel_layout=stereo:"
                    "sample_rate=48000"
                ),
                "-t",
                str(TOTAL_DURATION),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-shortest",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )

        return

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
    ]

    for _, path in existing:
        command.extend(
            [
                "-i",
                str(path),
            ]
        )

    filter_parts: list[str] = []
    mix_labels: list[str] = []

    for input_index, (name, _) in enumerate(
        existing,
        start=1,
    ):
        if name == "impact":
            filter_parts.append(
                f"[{input_index}:a]"
                "atrim=0:1.2,"
                "asetpts=PTS-STARTPTS,"
                "volume=0.48,"
                "afade=t=out:st=0.15:d=0.80"
                "[impact_out]"
            )

            mix_labels.append(
                "[impact_out]"
            )

        elif name == "steam":
            filter_parts.append(
                f"[{input_index}:a]"
                "atrim=0:4,"
                "asetpts=PTS-STARTPTS,"
                "asplit=3"
                "[steam_a][steam_b][steam_c]"
            )

            # Stronger steam in the opening hook.
            filter_parts.append(
                "[steam_a]"
                "adelay=100|100,"
                "volume=0.42,"
                "afade=t=in:st=0:d=0.12,"
                "afade=t=out:st=3.0:d=0.9"
                "[steam_early]"
            )

            # Softer steam during the lamb detail clip.
            filter_parts.append(
                "[steam_b]"
                "adelay=4200|4200,"
                "volume=0.21,"
                "afade=t=in:st=0:d=0.18,"
                "afade=t=out:st=3.0:d=0.9"
                "[steam_detail]"
            )

            # Very subtle steam when lamb returns.
            filter_parts.append(
                "[steam_c]"
                "adelay=10100|10100,"
                "volume=0.15,"
                "afade=t=in:st=0:d=0.20,"
                "afade=t=out:st=2.8:d=1.0"
                "[steam_reprise]"
            )

            mix_labels.extend(
                [
                    "[steam_early]",
                    "[steam_detail]",
                    "[steam_reprise]",
                ]
            )

        elif name == "serving":
            filter_parts.append(
                f"[{input_index}:a]"
                "atrim=0:1,"
                "asetpts=PTS-STARTPTS,"
                "asplit=2"
                "[serve_a][serve_b]"
            )

            # Lamb ribs appear at 14 seconds.
            filter_parts.append(
                "[serve_a]"
                "adelay=14000|14000,"
                "volume=0.30,"
                "afade=t=out:st=0.35:d=0.50"
                "[serving_14]"
            )

            # Lamb feast appears at 17 seconds.
            filter_parts.append(
                "[serve_b]"
                "adelay=17000|17000,"
                "volume=0.24,"
                "afade=t=out:st=0.35:d=0.50"
                "[serving_17]"
            )

            mix_labels.extend(
                [
                    "[serving_14]",
                    "[serving_17]",
                ]
            )

        elif name == "logo_hit":
            filter_parts.append(
                f"[{input_index}:a]"
                "atrim=0:2,"
                "asetpts=PTS-STARTPTS,"
                "adelay=26000|26000,"
                "volume=0.34,"
                "afade=t=in:st=0:d=0.10,"
                "afade=t=out:st=0.75:d=1.0"
                "[logo_out]"
            )

            mix_labels.append(
                "[logo_out]"
            )

    if not mix_labels:
        raise RuntimeError(
            "No audio tracks were prepared."
        )

    mix_inputs = "".join(
        mix_labels
    )

    filter_parts.append(
        mix_inputs
        + f"amix=inputs={len(mix_labels)}:"
        "duration=longest:"
        "normalize=0,"
        "alimiter=limit=0.88,"
        "loudnorm=I=-18:LRA=7:TP=-2.0"
        "[mixed]"
    )

    filter_complex = ";".join(
        filter_parts
    )

    command.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "0:v:0",
            "-map",
            "[mixed]",
            "-t",
            str(TOTAL_DURATION),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )

    run(command)

def main() -> None:
    require_program("ffmpeg")
    require_program("ffprobe")

    for segment in VIDEO_SEGMENTS:
        require_file(segment["path"])

    for segment in IMAGE_SEGMENTS:
        require_file(segment["path"])

    normalized_paths = []

    for segment in VIDEO_SEGMENTS:
        output_path = (
            WORK_DIR
            / f"{segment['id']}.mp4"
        )

        normalize_video(
            input_path=segment["path"],
            output_path=output_path,
            duration=segment["duration"],
        )

        normalized_paths.append(
            output_path
        )

    for segment in IMAGE_SEGMENTS:
        output_path = (
            WORK_DIR
            / f"{segment['id']}.mp4"
        )

        create_image_segment(
            input_path=segment["path"],
            output_path=output_path,
            duration=segment["duration"],
            motion=segment["motion"],
        )

        normalized_paths.append(
            output_path
        )

    end_card_path = (
        WORK_DIR / "08_end_card.mp4"
    )

    create_end_card(
        end_card_path
    )

    normalized_paths.append(
        end_card_path
    )

    concat_path = write_concat_file(
        normalized_paths
    )

    unbranded_path = (
        WORK_DIR / "unbranded.mp4"
    )

    concatenate_segments(
        concat_path=concat_path,
        output_path=unbranded_path,
    )

    ass_path = write_ass_file()

    branded_path = (
        WORK_DIR / "branded_silent.mp4"
    )

    apply_branding(
        input_path=unbranded_path,
        ass_path=ass_path,
        output_path=branded_path,
    )

    add_audio_or_silence(
        input_path=branded_path,
        output_path=OUTPUT_PATH,
    )

    print()
    print("=" * 80)
    print("FINAL VIDEO CREATED")
    print(OUTPUT_PATH)
    print("=" * 80)


if __name__ == "__main__":
    main()