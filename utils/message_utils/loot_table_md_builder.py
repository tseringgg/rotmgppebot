"""Utilities for loot table md builder."""

import csv

from dataclass import Loot, PPEData
from utils.ppe_types import normalize_ppe_type
from utils.ppe_display import format_ppe_label_from_options
from utils.message_utils.markdown_message_builder import MarkdownMessageBuilder
from utils.item_log_timestamps import format_unix_utc
from utils.loot_constants import rarity_rank
from utils.season_loot_history import iter_season_variants, normalize_rarity
from utils.points_service import (
    PENALTY_NAMES,
    calculate_bonus_points,
    calculate_item_points as calculate_item_points_service,
    get_effective_modifier_bucket_for_ppe,
    format_starting_penalty_line,
    loot_adjustment_detail_lines,
    loot_adjustments_for_ppe,
    non_default_points_adjustment_lines,
    recompute_ppe_points,
    penalty_inputs_from_bonuses,
    starting_penalty_breakdown_from_inputs,
)
from utils.player_records import highest_rarity
from utils.guild_config import get_set_bonuses


from functools import lru_cache

@lru_cache(maxsize=1)
def load_dungeon_data():
    """Load the loot CSV and create item-to-dungeon mapping from the Dungeon column."""
    try:
        item_to_dungeon: dict[str, str] = {}
        with open("rotmg_loot_drops_updated.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                item_name = (row.get("Item Name") or "").strip()
                dungeon = (row.get("Dungeon") or "").strip()
                if item_name and dungeon:
                    item_to_dungeon[item_name] = dungeon
        return {}, item_to_dungeon
    except FileNotFoundError:
        print("Warning: rotmg_loot_drops_updated.csv not found, falling back to alphabetical sorting")
        return {}, {}


def _format_points(value: float) -> str:
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def _loot_last_logged_text(loot: Loot) -> str:
    raw_times = getattr(loot, "logged_times", [])
    if isinstance(raw_times, list) and raw_times:
        try:
            latest = max(int(ts) for ts in raw_times if int(ts) > 0)
        except (TypeError, ValueError):
            return ""
        return format_unix_utc(latest)
    return ""


def _format_signed_points(value: float) -> str:
    points_text = _format_points(value)
    if value > 0:
        return f"+{points_text}"
    return points_text


def _as_float(value: object, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _group_entries_by_dungeon(entries: list, key_name_fn):
    _, item_to_dungeon = load_dungeon_data()
    dungeon_groups: dict[str, list] = {}
    unassigned: list = []

    for entry in entries:
        item_name = key_name_fn(entry)
        dungeon_name = item_to_dungeon.get(item_name)
        if dungeon_name:
            dungeon_groups.setdefault(dungeon_name, []).append(entry)
        else:
            unassigned.append(entry)

    sorted_dungeons = sorted(dungeon_groups.keys(), key=lambda name: name.lower())
    return sorted_dungeons, dungeon_groups, unassigned


def calculate_item_points(
    item_name: str,
    shiny: bool,
    quantity: int,
    rarity: str = "common",
    *,
    guild_config: dict | None = None,
) -> float:
    return calculate_item_points_service(item_name, shiny, quantity, rarity=rarity, guild_config=guild_config)


def _scaled_bonus_entry_points(
    raw_points: float,
    *,
    is_penalty: bool,
    modifier_bucket: dict[str, float | None],
) -> float:
    category_key = "penalty_percent" if is_penalty else "bonus_percent"
    category_percent = _as_float(modifier_bucket.get(category_key), 0.0)
    return raw_points * (1.0 + (category_percent / 100.0))


def create_loot_markdown_file(
    ppe_data: PPEData,
    *,
    guild_config: dict | None = None,
) -> str:
    """Create a temporary markdown file with the loot table and return the file path."""
    class_name = str(getattr(ppe_data.name, "value", ppe_data.name))
    modifier_bucket = get_effective_modifier_bucket_for_ppe(ppe_data, guild_config)
    point_adjustment_lines = non_default_points_adjustment_lines(guild_config, class_names=[class_name])
    points_breakdown = recompute_ppe_points(ppe_data, guild_config)
    loot_adjustments = loot_adjustments_for_ppe(ppe_data, guild_config)
    scaled_total = _as_float(points_breakdown.get("total"), 0.0)
    unweighted_total = (
        _as_float(points_breakdown.get("loot_raw"), 0.0)
        + _as_float(points_breakdown.get("bonus_raw"), 0.0)
        + _as_float(points_breakdown.get("penalty_raw"), 0.0)
        + _as_float(points_breakdown.get("set_bonus_raw"), 0.0)
    )
    penalty_inputs = penalty_inputs_from_bonuses(ppe_data.bonuses, guild_config=guild_config)
    penalty_input_breakdown = starting_penalty_breakdown_from_inputs(
        int(penalty_inputs["pet_level"]),
        int(penalty_inputs["num_exalts"]),
        float(penalty_inputs["percent_loot"]),
        float(penalty_inputs["incombat_reduction"]),
        guild_config=guild_config,
    )
    total_item_multiplier = float(loot_adjustments["combined_item_multiplier"])
    minimum_total_raw = modifier_bucket.get("minimum_total")
    minimum_total = _as_float(minimum_total_raw, 0.0) if minimum_total_raw is not None else None
    ppe_settings = guild_config.get("ppe_settings", {}) if isinstance(guild_config, dict) and isinstance(guild_config.get("ppe_settings", {}), dict) else {}
    ppe_type = format_ppe_label_from_options(
        getattr(ppe_data, "ppe_type_options", None),
        compact=True,
        guild_config={"ppe_settings": ppe_settings},
        fallback_type=normalize_ppe_type(getattr(ppe_data, "ppe_type", None)),
    )

    builder = MarkdownMessageBuilder(f"Loot Table: {class_name} (PPE #{ppe_data.id}, {ppe_type})")
    builder.add_section(
        heading="Point Adjustments From Defaults",
        lines=point_adjustment_lines or ["No point adjustments from defaults."],
    )
    builder.add_section(
        lines=[
            f"Total Unweighted Points: {_format_points(unweighted_total)}",
            f"Total Points: {_format_points(scaled_total)}",
        ]
    )

    if ppe_data.loot:
        sorted_dungeons, dungeon_groups, unassigned_items = _group_entries_by_dungeon(
            list(ppe_data.loot),
            key_name_fn=lambda loot_entry: loot_entry.item_name,
        )

        for dungeon_name in sorted_dungeons:
            lines: list[str] = []
            for loot in sorted(
                dungeon_groups[dungeon_name],
                key=lambda entry: (
                    entry.item_name.lower(),
                    bool(getattr(entry, "shiny", False)),
                    rarity_rank(str(getattr(entry, "rarity", "common"))),
                ),
            ):
                rarity = str(getattr(loot, "rarity", "common")).strip().lower()
                raw_item_points = calculate_item_points(
                    loot.item_name,
                    loot.shiny,
                    int(loot.quantity),
                    rarity=rarity,
                    guild_config=guild_config,
                )

                tags: list[str] = [rarity]
                if loot.shiny:
                    tags.append("shiny")

                line = f"- {loot.item_name} × {loot.quantity} ({_format_points(raw_item_points)} pts)"
                if tags:
                    line += f" [{', '.join(tags)}]"
                logged_text = _loot_last_logged_text(loot)
                if logged_text:
                    line += f" [logged: {logged_text}]"
                lines.append(line)

            builder.add_section(heading=dungeon_name, lines=lines)

        if unassigned_items:
            lines = []
            for loot in sorted(
                unassigned_items,
                key=lambda entry: (
                    entry.item_name.lower(),
                    bool(getattr(entry, "shiny", False)),
                    rarity_rank(str(getattr(entry, "rarity", "common"))),
                ),
            ):
                rarity = str(getattr(loot, "rarity", "common")).strip().lower()
                raw_item_points = calculate_item_points(
                    loot.item_name,
                    loot.shiny,
                    int(loot.quantity),
                    rarity=rarity,
                    guild_config=guild_config,
                )

                tags: list[str] = [rarity]
                if loot.shiny:
                    tags.append("shiny")

                line = f"- {loot.item_name} × {loot.quantity} ({_format_points(raw_item_points)} pts)"
                if tags:
                    line += f" [{', '.join(tags)}]"
                logged_text = _loot_last_logged_text(loot)
                if logged_text:
                    line += f" [logged: {logged_text}]"
                lines.append(line)

            builder.add_section(heading="Unassigned Items", lines=lines)
    else:
        builder.add_section(heading="Loot Items", lines=["No loot recorded yet."])

    if ppe_data.completed_sets:
        from utils.set_operations import load_item_sets

        all_sets = load_item_sets()
        set_lines: list[str] = []
        for set_name in sorted(ppe_data.completed_sets):
            if set_name in all_sets:
                set_type = all_sets[set_name]["type"]
                set_bonuses = get_set_bonuses(guild_config)
                points = 0.0
                if set_type in set_bonuses and set_name in set_bonuses[set_type]:
                    points = float(set_bonuses[set_type][set_name])
                set_lines.append(f"- {set_name} ({set_type}) - {_format_points(points)} pts")

        if set_lines:
            builder.add_section(heading="Sets", lines=set_lines)

    if ppe_data.bonuses:
        bonus_lines: list[str] = []
        for bonus in sorted(ppe_data.bonuses, key=lambda entry: entry.name.lower()):
            if bonus.name == "Set Completion Bonus":
                continue

            total_bonus_points = calculate_bonus_points(bonus)
            if bonus.name in PENALTY_NAMES:
                if bonus.name == "Pet Level Penalty":
                    detail = format_starting_penalty_line(
                        "Pet Level",
                        str(int(penalty_inputs["pet_level"])),
                        penalty_input_breakdown["Pet Level Penalty"],
                        bold_values=False,
                    )
                    line = f"- {bonus.name} x {bonus.quantity} ({detail})"
                elif bonus.name == "Exalts Penalty":
                    detail = format_starting_penalty_line(
                        "Exalts",
                        str(int(penalty_inputs["num_exalts"])),
                        penalty_input_breakdown["Exalts Penalty"],
                        bold_values=False,
                    )
                    line = f"- {bonus.name} x {bonus.quantity} ({detail})"
                elif bonus.name == "Loot Boost Penalty":
                    detail = format_starting_penalty_line(
                        "Loot Boost",
                        f"{float(penalty_inputs['percent_loot']):g}%",
                        penalty_input_breakdown["Loot Boost Penalty"],
                        bold_values=False,
                    )
                    line = f"- {bonus.name} x {bonus.quantity} ({detail})"
                elif bonus.name == "In-Combat Reduction Penalty":
                    detail = format_starting_penalty_line(
                        "In-Combat Reduction",
                        f"{float(penalty_inputs['incombat_reduction']):g}s",
                        penalty_input_breakdown["In-Combat Reduction Penalty"],
                        bold_values=False,
                    )
                    line = f"- {bonus.name} x {bonus.quantity} ({detail})"
                else:
                    line = f"- {bonus.name} x {bonus.quantity} ({_format_points(total_bonus_points)} pts)"
            else:
                scaled_bonus_points = _scaled_bonus_entry_points(
                    total_bonus_points,
                    is_penalty=False,
                    modifier_bucket=modifier_bucket,
                )
                line = f"- {bonus.name} x {bonus.quantity} ({_format_signed_points(scaled_bonus_points)} pts)"
            if bonus.repeatable:
                line += " [repeatable]"
            bonus_lines.append(line)

        builder.add_section(heading="Bonuses", lines=bonus_lines)

    total_loot_items = len(ppe_data.loot) if ppe_data.loot else 0
    total_bonus_items = len(ppe_data.bonuses) if ppe_data.bonuses else 0
    summary_lines = [
        f"Loot entries: {total_loot_items}",
        f"Bonus entries: {total_bonus_items}\n\n",
        "",
        f"Minimum total floor: {_format_points(minimum_total)}" if minimum_total is not None else "",
        "Loot Adjustments:",
        "",
    ]
    summary_lines = [line for line in summary_lines if line != ""]
    summary_lines.extend(loot_adjustment_detail_lines(loot_adjustments))
    summary_lines.append("")
    summary_lines.append(f"All items are worth {total_item_multiplier:.2f}x for this character.")

    builder.add_section(heading="Summary", lines=summary_lines)
    return builder.write_temp_file(
        prefix=f"loot_table_ppe_{ppe_data.id}",
        username=class_name,
        temp_dir="temp",
    )


def create_season_loot_markdown_file(
    season_item_history: dict[str, list[int]] | None,
    *,
    display_name: str,
) -> str:
    """Create a markdown file for season loot variants, grouped by dungeon when possible."""
    class _SeasonHistoryProxy:
        def __init__(self, history: dict[str, list[int]] | None):
            self.season_item_history = history if isinstance(history, dict) else {}

    variant_rows = iter_season_variants(_SeasonHistoryProxy(season_item_history))
    builder = MarkdownMessageBuilder(f"Season Loot for {display_name}")
    unique_items = {(item_name, shiny) for item_name, shiny, _rarity, _timestamps in variant_rows}
    total_logs = sum(len(timestamps) for _item_name, _shiny, _rarity, timestamps in variant_rows)
    builder.add_paragraph(f"Total unique items: {len(unique_items)}")
    builder.add_paragraph(f"Total variant entries: {len(variant_rows)}")
    builder.add_paragraph(f"Total logged pickups: {total_logs}")

    if not variant_rows:
        builder.add_section(heading="Items", lines=["No season loot recorded yet."])
        return builder.write_temp_file(prefix="season_loot", username=display_name, temp_dir="temp")

    sorted_dungeons, dungeon_groups, unassigned_items = _group_entries_by_dungeon(
        variant_rows,
        key_name_fn=lambda item_entry: item_entry[0],
    )

    for dungeon_name in sorted_dungeons:
        lines = []
        for item_name, shiny, rarity, timestamps in sorted(
            dungeon_groups[dungeon_name], key=lambda entry: (entry[0].lower(), entry[1], entry[2])
        ):
            line = f"{item_name}{' [shiny]' if shiny else ''} [{rarity}] x{len(timestamps)}"
            if timestamps:
                formatted = [format_unix_utc(ts) for ts in timestamps]
                cleaned = [text for text in formatted if text]
                if cleaned:
                    line += f" (times: {', '.join(cleaned)})"
            lines.append(line)
        builder.add_numbered_list(lines, heading=dungeon_name)

    if unassigned_items:
        lines = []
        for item_name, shiny, rarity, timestamps in sorted(
            unassigned_items, key=lambda entry: (entry[0].lower(), entry[1], entry[2])
        ):
            line = f"{item_name}{' [shiny]' if shiny else ''} [{rarity}] x{len(timestamps)}"
            if timestamps:
                formatted = [format_unix_utc(ts) for ts in timestamps]
                cleaned = [text for text in formatted if text]
                if cleaned:
                    line += f" (times: {', '.join(cleaned)})"
            lines.append(line)
        builder.add_numbered_list(lines, heading="Unassigned Items")

    return builder.write_temp_file(prefix="season_loot", username=display_name, temp_dir="temp")