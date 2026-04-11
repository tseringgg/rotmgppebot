import csv

from dataclass import PPEData
from utils.ppe_types import normalize_ppe_type, ppe_type_short_label
from utils.markdown_message_builder import MarkdownMessageBuilder
from utils.item_log_timestamps import format_unix_utc, seasonal_item_key
from utils.points_service import (
    PENALTY_NAMES,
    apply_percent_modifier,
    calculate_bonus_points,
    calculate_item_points as calculate_item_points_service,
    get_effective_modifier_bucket_for_ppe,
    get_ppe_type_multiplier_for_ppe,
    non_default_points_adjustment_lines,
    recompute_ppe_points,
    starting_penalty_breakdown_from_bonuses,
)


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
    divine: bool,
    shiny: bool,
    quantity: int,
    *,
    guild_config: dict | None = None,
) -> float:
    return calculate_item_points_service(item_name, divine, shiny, quantity, guild_config=guild_config)


def _scaled_loot_entry_points(raw_points: float, modifier_bucket: dict[str, float | None]) -> float:
    loot_percent = _as_float(modifier_bucket.get("loot_percent"), 0.0)
    total_percent = _as_float(modifier_bucket.get("total_percent"), 0.0)
    return apply_percent_modifier(apply_percent_modifier(raw_points, loot_percent), total_percent)


def _scaled_bonus_entry_points(
    raw_points: float,
    *,
    is_penalty: bool,
    modifier_bucket: dict[str, float | None],
) -> float:
    category_key = "penalty_percent" if is_penalty else "bonus_percent"
    category_percent = _as_float(modifier_bucket.get(category_key), 0.0)
    total_percent = _as_float(modifier_bucket.get("total_percent"), 0.0)
    return apply_percent_modifier(apply_percent_modifier(raw_points, category_percent), total_percent)


def create_loot_markdown_file(
    ppe_data: PPEData,
    *,
    guild_config: dict | None = None,
) -> str:
    """Create a temporary markdown file with the loot table and return the file path."""
    class_name = str(getattr(ppe_data.name, "value", ppe_data.name))
    modifier_bucket = get_effective_modifier_bucket_for_ppe(ppe_data, guild_config)
    type_multiplier = get_ppe_type_multiplier_for_ppe(ppe_data, guild_config)
    point_adjustment_lines = non_default_points_adjustment_lines(guild_config, class_names=[class_name])
    points_breakdown = recompute_ppe_points(ppe_data, guild_config)
    scaled_total = _as_float(points_breakdown.get("total"), 0.0)
    penalty_breakdown = starting_penalty_breakdown_from_bonuses(ppe_data.bonuses, guild_config=guild_config)
    minimum_total_raw = modifier_bucket.get("minimum_total")
    minimum_total = _as_float(minimum_total_raw, 0.0) if minimum_total_raw is not None else None
    ppe_type = ppe_type_short_label(normalize_ppe_type(getattr(ppe_data, "ppe_type", None)))

    builder = MarkdownMessageBuilder(f"Loot Table: {class_name} (PPE #{ppe_data.id}, {ppe_type})")
    builder.add_section(
        heading="Point Adjustments From Defaults",
        lines=point_adjustment_lines or ["No point adjustments from defaults."],
    )
    builder.add_paragraph(f"Total Points: {_format_points(scaled_total)}")

    if ppe_data.loot:
        sorted_dungeons, dungeon_groups, unassigned_items = _group_entries_by_dungeon(
            list(ppe_data.loot),
            key_name_fn=lambda loot_entry: loot_entry.item_name,
        )

        for dungeon_name in sorted_dungeons:
            lines: list[str] = []
            for loot in sorted(dungeon_groups[dungeon_name], key=lambda entry: entry.item_name.lower()):
                raw_item_points = calculate_item_points(
                    loot.item_name,
                    loot.divine,
                    loot.shiny,
                    int(loot.quantity),
                    guild_config=guild_config,
                )
                scaled_item_points = _scaled_loot_entry_points(raw_item_points, modifier_bucket)
                scaled_item_points *= type_multiplier

                tags: list[str] = []
                if loot.divine:
                    tags.append("divine")
                if loot.shiny:
                    tags.append("shiny")

                line = f"- {loot.item_name} × {loot.quantity} ({_format_points(scaled_item_points)} pts)"
                if tags:
                    line += f" [{', '.join(tags)}]"
                logged_text = format_unix_utc(getattr(loot, "last_logged_at", None))
                if logged_text:
                    line += f" [logged: {logged_text}]"
                lines.append(line)

            builder.add_section(heading=dungeon_name, lines=lines)

        if unassigned_items:
            lines: list[str] = []
            for loot in sorted(unassigned_items, key=lambda entry: entry.item_name.lower()):
                raw_item_points = calculate_item_points(
                    loot.item_name,
                    loot.divine,
                    loot.shiny,
                    int(loot.quantity),
                    guild_config=guild_config,
                )
                scaled_item_points = _scaled_loot_entry_points(raw_item_points, modifier_bucket)
                scaled_item_points *= type_multiplier

                tags: list[str] = []
                if loot.divine:
                    tags.append("divine")
                if loot.shiny:
                    tags.append("shiny")

                line = f"- {loot.item_name} × {loot.quantity} ({_format_points(scaled_item_points)} pts)"
                if tags:
                    line += f" [{', '.join(tags)}]"
                logged_text = format_unix_utc(getattr(loot, "last_logged_at", None))
                if logged_text:
                    line += f" [logged: {logged_text}]"
                lines.append(line)

            builder.add_section(heading="Unassigned Items", lines=lines)
    else:
        builder.add_section(heading="Loot Items", lines=["No loot recorded yet."])

    if ppe_data.bonuses:
        bonus_lines: list[str] = []
        for bonus in sorted(ppe_data.bonuses, key=lambda entry: entry.name.lower()):
            total_bonus_points = calculate_bonus_points(bonus)
            if bonus.name in PENALTY_NAMES:
                adjusted_penalty = penalty_breakdown.get(bonus.name, {}).get("signed_adjusted_points")
                total_bonus_points = _as_float(adjusted_penalty, total_bonus_points)
            scaled_bonus_points = _scaled_bonus_entry_points(
                total_bonus_points,
                is_penalty=(bonus.name in PENALTY_NAMES),
                modifier_bucket=modifier_bucket,
            )
            scaled_bonus_points *= type_multiplier
            points_display = _format_signed_points(scaled_bonus_points)

            line = f"- {bonus.name} × {bonus.quantity} ({points_display} pts)"
            if bonus.repeatable:
                line += " [repeatable]"
            bonus_lines.append(line)

        builder.add_section(heading="Bonuses", lines=bonus_lines)

    total_loot_items = len(ppe_data.loot) if ppe_data.loot else 0
    total_bonus_items = len(ppe_data.bonuses) if ppe_data.bonuses else 0
    summary_lines = [
        f"Loot entries: {total_loot_items}",
        f"Bonus entries: {total_bonus_items}",
    ]
    if minimum_total is not None:
        summary_lines.append(f"Minimum total floor: {_format_points(minimum_total)}")
    summary_lines.append(f"PPE type multiplier: {type_multiplier:.2f}x")

    builder.add_section(
        heading="Summary",
        lines=summary_lines,
    )

    return builder.write_temp_file(
        prefix=f"loot_table_ppe_{ppe_data.id}",
        username=class_name,
        temp_dir="temp",
    )


def create_season_loot_markdown_file(
    unique_items: set[tuple[str, bool]],
    *,
    display_name: str,
    item_log_timestamps: dict[str, int] | None = None,
) -> str:
    """Create a markdown file for season loot, grouped by dungeon when possible."""

    sorted_items = sorted(unique_items, key=lambda x: (x[0].lower(), x[1]))
    builder = MarkdownMessageBuilder(f"Season Loot for {display_name}")
    builder.add_paragraph(f"Total unique items: {len(sorted_items)}")

    if not sorted_items:
        builder.add_section(heading="Items", lines=["No season loot recorded yet."])
        return builder.write_temp_file(prefix="season_loot", username=display_name, temp_dir="temp")

    sorted_dungeons, dungeon_groups, unassigned_items = _group_entries_by_dungeon(
        sorted_items,
        key_name_fn=lambda item_entry: item_entry[0],
    )

    for dungeon_name in sorted_dungeons:
        lines = []
        for item_name, shiny in sorted(dungeon_groups[dungeon_name], key=lambda entry: (entry[0].lower(), entry[1])):
            line = f"{item_name}{' [shiny]' if shiny else ''}"
            if item_log_timestamps:
                ts = item_log_timestamps.get(seasonal_item_key(item_name, shiny))
                ts_text = format_unix_utc(ts)
                if ts_text:
                    line += f" (logged: {ts_text})"
            lines.append(line)
        builder.add_numbered_list(lines, heading=dungeon_name)

    if unassigned_items:
        lines = []
        for item_name, shiny in sorted(unassigned_items, key=lambda entry: (entry[0].lower(), entry[1])):
            line = f"{item_name}{' [shiny]' if shiny else ''}"
            if item_log_timestamps:
                ts = item_log_timestamps.get(seasonal_item_key(item_name, shiny))
                ts_text = format_unix_utc(ts)
                if ts_text:
                    line += f" (logged: {ts_text})"
            lines.append(line)
        builder.add_numbered_list(lines, heading="Unassigned Items")

    return builder.write_temp_file(prefix="season_loot", username=display_name, temp_dir="temp")
