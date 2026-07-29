from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

CAMPAIGN_DIR = (
    BACKEND_DIR
    / "assets"
    / "najdi_campaign"
)

INCOMING_DIR = CAMPAIGN_DIR / "_incoming"

REPORT_DIR = CAMPAIGN_DIR / "_reports"


@dataclass(frozen=True)
class AssetRule:
    destination_folder: str
    destination_name: str
    category: str
    veo_priority: str
    notes: str


ASSET_RULES: dict[str, AssetRule] = {
    # =========================================================
    # Brand, person reference, and exterior
    # =========================================================
    "aboudawass.jpeg": AssetRule(
        "14_character_original",
        "chef_character_original_reference.jpeg",
        "character_reference",
        "reference_only",
        "Original person reference; do not use as a food shot.",
    ),

    "13.jpg": AssetRule(
        "11_restaurant_exterior",
        "restaurant_exterior_day_02.jpg",
        "restaurant_exterior",
        "medium",
        "Day exterior establishing shot.",
    ),

    "29.jpg": AssetRule(
        "11_restaurant_exterior",
        "restaurant_exterior_night_02.jpg",
        "restaurant_exterior",
        "medium",
        "Night exterior alternative.",
    ),

    "32.jpg": AssetRule(
        "11_restaurant_exterior",
        "restaurant_exterior_day_01.jpg",
        "restaurant_exterior",
        "medium",
        "Day exterior with restaurant identity.",
    ),

    "42.jpg": AssetRule(
        "11_restaurant_exterior",
        "restaurant_exterior_night_01.jpg",
        "restaurant_exterior",
        "high",
        "Preferred night exterior identity shot.",
    ),

    # =========================================================
    # Restaurant interior
    # =========================================================
    "27.jpg": AssetRule(
        "12_restaurant_interior",
        "restaurant_interior_hallway_01.jpg",
        "restaurant_interior",
        "low",
        "Use in CapCut with a subtle zoom.",
    ),

    "34.jpg": AssetRule(
        "12_restaurant_interior",
        "restaurant_interior_screens_01.jpg",
        "restaurant_interior",
        "medium",
        "Interior screens and kitchen opening.",
    ),

    "35.jpg": AssetRule(
        "12_restaurant_interior",
        "restaurant_kitchen_window_01.jpg",
        "restaurant_interior",
        "low",
        "Kitchen service-area reference.",
    ),

    # =========================================================
    # Lamb hero and lamb feasts
    # =========================================================
    "38.jpg": AssetRule(
        "02_lamb_hero",
        "lamb_hero_whole_01.jpg",
        "lamb_hero",
        "highest",
        "Primary lamb hook for client prototype.",
    ),

    "39.jpg": AssetRule(
        "02_lamb_hero",
        "lamb_rice_closeup_01.jpg",
        "lamb_detail",
        "highest",
        "Second main lamb shot.",
    ),

    "41.jpg": AssetRule(
        "03_lamb_feasts",
        "lamb_rice_real_01.jpg",
        "lamb_feast",
        "medium",
        "Realistic lamb and two-color rice tray.",
    ),

    "15.jpg": AssetRule(
        "03_lamb_feasts",
        "lamb_feast_table_01.jpg",
        "lamb_feast",
        "high",
        "Large table spread with lamb dishes.",
    ),

    # =========================================================
    # Original chicken and rice
    # =========================================================
    "11.jpeg": AssetRule(
        "04_chicken_rice_original",
        "chicken_yellow_rice_original_01.jpeg",
        "chicken_rice",
        "high",
        "Strong yellow-rice chicken product shot.",
    ),

    "10.jpeg": AssetRule(
        "04_chicken_rice_original",
        "chicken_white_rice_original_01.jpeg",
        "chicken_rice",
        "medium",
        "White-rice chicken product shot.",
    ),

    "9.jpeg": AssetRule(
        "04_chicken_rice_original",
        "chicken_yellow_rice_original_02.jpeg",
        "chicken_rice",
        "medium",
        "Second yellow-rice chicken angle.",
    ),

    "8.jpeg": AssetRule(
        "04_chicken_rice_original",
        "chicken_white_rice_original_02.jpeg",
        "chicken_rice",
        "medium",
        "Second white-rice chicken angle.",
    ),

    "12.jpg": AssetRule(
        "04_chicken_rice_original",
        "chicken_yellow_rice_real_03.jpg",
        "chicken_rice",
        "medium",
        "Additional yellow-rice chicken shot.",
    ),

    "30.jpg": AssetRule(
        "04_chicken_rice_original",
        "chicken_white_rice_real_03.jpg",
        "chicken_rice",
        "medium",
        "Chicken and white rice.",
    ),

    "36.jpg": AssetRule(
        "04_chicken_rice_original",
        "chicken_white_rice_real_04.jpg",
        "chicken_rice",
        "medium",
        "Additional white-rice chicken product shot.",
    ),

    "40.jpg": AssetRule(
        "04_chicken_rice_original",
        "chicken_rice_table_real_01.jpg",
        "chicken_rice",
        "low",
        "Crowded table shot; use mostly in editing.",
    ),

    "26.jpg": AssetRule(
        "18_reference_only",
        "chicken_rice_customer_table_01.jpg",
        "customer_table",
        "reference_only",
        "Real table context; do not prioritize for Veo.",
    ),

    # =========================================================
    # Grill
    # =========================================================
    "14.jpg": AssetRule(
        "06_grill",
        "grilled_meat_cubes_01.jpg",
        "grill",
        "medium",
        "Grilled meat pieces.",
    ),

    "17.jpg": AssetRule(
        "06_grill",
        "charcoal_grilled_chicken_01.jpg",
        "kitchen_action",
        "high",
        "Smoke and charcoal action shot.",
    ),

    "20.jpg": AssetRule(
        "06_grill",
        "mixed_grill_feast_01.jpg",
        "grill_feast",
        "high",
        "Large grill feast reveal.",
    ),

    "23.jpg": AssetRule(
        "06_grill",
        "grilled_lamb_ribs_01.jpg",
        "lamb_grill",
        "high",
        "Strong lamb ribs shot.",
    ),

    "31.jpg": AssetRule(
        "06_grill",
        "grilled_chicken_pieces_01.jpg",
        "grill",
        "medium",
        "Grilled chicken pieces.",
    ),

    "37.jpg": AssetRule(
        "06_grill",
        "mixed_grill_platter_01.jpg",
        "grill",
        "high",
        "Mixed grill platter.",
    ),

    # =========================================================
    # Rotisserie
    # =========================================================
    "22.jpg": AssetRule(
        "07_rotisserie",
        "rotisserie_chicken_closeup_01.jpg",
        "rotisserie",
        "medium",
        "Close rotisserie chicken shot.",
    ),

    "28.jpg": AssetRule(
        "07_rotisserie",
        "rotisserie_chicken_wall_01.jpg",
        "kitchen_action",
        "highest",
        "Strong motion and action candidate.",
    ),

    # =========================================================
    # Hot sides
    # =========================================================
    "7.jpeg": AssetRule(
        "08_hot_sides",
        "vegetable_stew_original_01.jpeg",
        "hot_side",
        "medium",
        "Hot vegetable stew.",
    ),

    "6.jpeg": AssetRule(
        "08_hot_sides",
        "vegetable_stew_original_02.jpeg",
        "hot_side",
        "low",
        "Second hot stew view; check for duplication.",
    ),

    "4.jpeg": AssetRule(
        "08_hot_sides",
        "okra_stew_original_01.jpeg",
        "hot_side",
        "medium",
        "Okra stew.",
    ),

    # =========================================================
    # Cold sides
    # =========================================================
    "1.jpeg": AssetRule(
        "09_cold_sides",
        "cucumber_yogurt_02.jpeg",
        "cold_side",
        "low",
        "Second cucumber-yogurt angle.",
    ),

    "2.jpeg": AssetRule(
        "09_cold_sides",
        "green_salad_original_01.jpeg",
        "cold_side",
        "medium",
        "Green salad.",
    ),

    "3.jpeg": AssetRule(
        "09_cold_sides",
        "tahini_01.jpeg",
        "cold_side",
        "low",
        "Tahini.",
    ),

    "5.jpeg": AssetRule(
        "09_cold_sides",
        "cucumber_yogurt_01.jpeg",
        "cold_side",
        "medium",
        "Primary cucumber-yogurt shot.",
    ),

    "18.jpg": AssetRule(
        "09_cold_sides",
        "hummus_01.jpg",
        "cold_side",
        "low",
        "Hummus.",
    ),

    "21.jpg": AssetRule(
        "09_cold_sides",
        "stuffed_grape_leaves_01.jpg",
        "cold_side",
        "low",
        "Stuffed grape leaves.",
    ),

    # =========================================================
    # Sauces
    # =========================================================
    "24.jpg": AssetRule(
        "10_sauces",
        "red_sauce_01.jpg",
        "sauce",
        "low",
        "Red sauce.",
    ),

    "25.jpg": AssetRule(
        "10_sauces",
        "green_sauce_01.jpg",
        "sauce",
        "low",
        "Green sauce.",
    ),

    # =========================================================
    # AI-generated chicken stills
    # =========================================================
    "chat5.png": AssetRule(
        "05_chicken_rice_ai",
        "chicken_ai_steam_hook_01.png",
        "chicken_ai",
        "highest",
        "Strong steam hook.",
    ),

    "chat6.png": AssetRule(
        "05_chicken_rice_ai",
        "chicken_ai_presentation_01.png",
        "chicken_ai",
        "high",
        "Plate presentation shot.",
    ),

    "chat4.png": AssetRule(
        "05_chicken_rice_ai",
        "chicken_ai_detail_01.png",
        "chicken_ai",
        "high",
        "Close food detail.",
    ),

    "chat2.png": AssetRule(
        "05_chicken_rice_ai",
        "chicken_ai_sprinkle_01.png",
        "chicken_ai",
        "medium",
        "Sprinkle action; hand artifact risk.",
    ),

    # =========================================================
    # Gemini-generated boards and heroes
    # =========================================================
    "Gemini_Generated_Image_xj4949xj4949xj49.png": AssetRule(
        "16_storyboards_to_split",
        "chicken_ai_storyboard_4panel_01.png",
        "storyboard",
        "split_required",
        "Four-panel chicken board; split before video.",
    ),

    "Gemini_Generated_Image_w812t7w812t7w812.png": AssetRule(
        "16_storyboards_to_split",
        "stew_ai_storyboard_4panel_01.png",
        "storyboard",
        "split_required",
        "Four-panel stew board; split before video.",
    ),

    "Gemini_Generated_Image_qexnnqqexnnqqexn.png": AssetRule(
        "08_hot_sides",
        "stew_ai_hero_01.png",
        "hot_side_ai",
        "high",
        "Strong generated stew hero.",
    ),

    "Gemini_Generated_Image_xze4q4xze4q4xze4.png": AssetRule(
        "17_menu_spreads_ai",
        "menu_spread_ai_overhead_01.png",
        "menu_spread",
        "high",
        "Overhead menu spread.",
    ),

    # =========================================================
    # ChatGPT-generated images
    # =========================================================
    "ChatGPT Image Jul 21, 2026, 06_33_22 PM.png": AssetRule(
        "16_storyboards_to_split",
        "chicken_ai_storyboard_6panel_01.png",
        "storyboard",
        "split_required",
        "Multi-panel chicken board; split before video.",
    ),

    "ChatGPT Image Jul 21, 2026, 06_33_13 PM.png": AssetRule(
        "05_chicken_rice_ai",
        "chicken_ai_vertical_hero_01.png",
        "chicken_ai",
        "high",
        "Vertical chicken hero.",
    ),

    "ChatGPT Image Jul 21, 2026, 06_33_03 PM.png": AssetRule(
        "09_cold_sides",
        "salad_ai_vertical_hero_01.png",
        "cold_side_ai",
        "medium",
        "Vertical salad hero.",
    ),

    "ChatGPT Image Jul 21, 2026, 06_32_58 PM.png": AssetRule(
        "05_chicken_rice_ai",
        "chicken_ai_vertical_hero_02.png",
        "chicken_ai",
        "high",
        "Second vertical chicken hero.",
    ),

    "ChatGPT Image Jul 21, 2026, 06_32_49 PM.png": AssetRule(
        "15_character_ai",
        "chef_character_ai_kitchen_01.png",
        "character_ai",
        "medium",
        "Generated character image; use subtle motion only.",
    ),
}


SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".pdf",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Organize Najdi campaign assets from the "
            "_incoming directory."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Copy and rename files into final folders. "
            "Without this flag, perform a dry run."
        ),
    )

    return parser.parse_args()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file_obj:
        for chunk in iter(
            lambda: file_obj.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def normalized_name(name: str) -> str:
    return " ".join(
        name.strip().lower().split()
    )


def get_rule_for_file(path: Path) -> AssetRule | None:
    exact_rule = ASSET_RULES.get(
        path.name
    )

    if exact_rule is not None:
        return exact_rule

    normalized = normalized_name(
        path.name
    )

    for source_name, rule in ASSET_RULES.items():
        if normalized_name(source_name) == normalized:
            return rule

    return None


def destination_path(
    rule: AssetRule,
) -> Path:
    return (
        CAMPAIGN_DIR
        / rule.destination_folder
        / rule.destination_name
    )


def make_directories() -> None:
    destination_folders = {
        rule.destination_folder
        for rule in ASSET_RULES.values()
    }

    for folder_name in destination_folders:
        (
            CAMPAIGN_DIR
            / folder_name
        ).mkdir(
            parents=True,
            exist_ok=True,
        )

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def inspect_assets() -> list[dict]:
    if not INCOMING_DIR.exists():
        raise FileNotFoundError(
            f"Incoming directory not found: {INCOMING_DIR}"
        )

    rows: list[dict] = []

    incoming_files = sorted(
        (
            path
            for path in INCOMING_DIR.iterdir()
            if path.is_file()
            and path.suffix.lower()
            in SUPPORTED_EXTENSIONS
        ),
        key=lambda path: path.name.lower(),
    )

    seen_hashes: dict[str, Path] = {}

    for source_path in incoming_files:
        sha256 = file_hash(
            source_path
        )

        duplicate_of = seen_hashes.get(
            sha256
        )

        if duplicate_of is None:
            seen_hashes[sha256] = source_path

        rule = get_rule_for_file(
            source_path
        )

        if rule is None:
            rows.append(
                {
                    "source_name": source_path.name,
                    "source_path": str(source_path),
                    "status": "UNMATCHED",
                    "destination_folder": "",
                    "destination_name": "",
                    "destination_path": "",
                    "category": "",
                    "veo_priority": "",
                    "notes": (
                        "No automatic classification rule."
                    ),
                    "duplicate_of": (
                        duplicate_of.name
                        if duplicate_of
                        else ""
                    ),
                    "sha256": sha256,
                    "size_bytes": source_path.stat().st_size,
                }
            )
            continue

        target_path = destination_path(
            rule
        )

        status = "READY"

        if duplicate_of is not None:
            status = "DUPLICATE"

        elif target_path.exists():
            source_hash = sha256
            destination_hash = file_hash(
                target_path
            )

            if source_hash == destination_hash:
                status = "ALREADY_ORGANIZED"
            else:
                status = "TARGET_CONFLICT"

        rows.append(
            {
                "source_name": source_path.name,
                "source_path": str(source_path),
                "status": status,
                "destination_folder": (
                    rule.destination_folder
                ),
                "destination_name": (
                    rule.destination_name
                ),
                "destination_path": str(
                    target_path
                ),
                "category": rule.category,
                "veo_priority": (
                    rule.veo_priority
                ),
                "notes": rule.notes,
                "duplicate_of": (
                    duplicate_of.name
                    if duplicate_of
                    else ""
                ),
                "sha256": sha256,
                "size_bytes": source_path.stat().st_size,
            }
        )

    return rows


def write_report(rows: list[dict]) -> Path:
    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path = (
        REPORT_DIR
        / "asset_organization_manifest.csv"
    )

    fieldnames = [
        "source_name",
        "source_path",
        "status",
        "destination_folder",
        "destination_name",
        "destination_path",
        "category",
        "veo_priority",
        "notes",
        "duplicate_of",
        "sha256",
        "size_bytes",
    ]

    with report_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file_obj:
        writer = csv.DictWriter(
            file_obj,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)

    unmatched_path = (
        REPORT_DIR
        / "unmatched_files.txt"
    )

    unmatched_names = [
        row["source_name"]
        for row in rows
        if row["status"] == "UNMATCHED"
    ]

    unmatched_path.write_text(
        "\n".join(unmatched_names),
        encoding="utf-8",
    )

    return report_path


def print_summary(
    rows: list[dict],
    apply_changes: bool,
) -> None:
    statuses: dict[str, int] = {}

    for row in rows:
        status = row["status"]
        statuses[status] = (
            statuses.get(status, 0) + 1
        )

    print("=" * 80)

    print(
        "MODE:",
        "APPLY" if apply_changes else "DRY RUN",
    )

    print("Incoming:", INCOMING_DIR)
    print("Campaign:", CAMPAIGN_DIR)

    print("=" * 80)

    for status in sorted(statuses):
        print(
            f"{status}: {statuses[status]}"
        )

    print("=" * 80)

    for row in rows:
        source = row["source_name"]
        status = row["status"]

        if row["destination_path"]:
            print(
                f"[{status}] {source}"
                f"\n    -> {row['destination_path']}"
            )
        else:
            print(
                f"[{status}] {source}"
            )

        if row["duplicate_of"]:
            print(
                "    duplicate of:",
                row["duplicate_of"],
            )


def apply_organization(
    rows: list[dict],
) -> None:
    make_directories()

    for row in rows:
        if row["status"] != "READY":
            continue

        source_path = Path(
            row["source_path"]
        )

        target_path = Path(
            row["destination_path"]
        )

        target_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source_path,
            target_path,
        )

        print(
            f"[COPIED] {source_path.name}"
            f"\n    -> {target_path}"
        )


def main() -> None:
    args = parse_args()

    make_directories()

    rows = inspect_assets()

    report_path = write_report(
        rows
    )

    print_summary(
        rows=rows,
        apply_changes=args.apply,
    )

    if not args.apply:
        print()
        print(
            "No files were copied."
        )
        print(
            "Review the report, then run again "
            "with --apply."
        )
        print(
            f"Report: {report_path}"
        )
        return

    apply_organization(
        rows
    )

    final_rows = inspect_assets()

    final_report = write_report(
        final_rows
    )

    print()
    print(
        "Organization completed."
    )
    print(
        "Original files remain in _incoming."
    )
    print(
        f"Final report: {final_report}"
    )


if __name__ == "__main__":
    main()