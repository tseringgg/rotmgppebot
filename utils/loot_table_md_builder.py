import json

from dataclass import PPEData
from utils.markdown_message_builder import MarkdownMessageBuilder
from utils.points_service import (
    PENALTY_NAMES,
    apply_percent_modifier,
    calculate_bonus_points,
    calculate_item_points as calculate_item_points_service,
    get_effective_modifier_bucket_for_ppe,
    non_default_points_adjustment_lines,
)


def load_dungeon_data():
    """Load the dungeon loot JSON file and create item-to-dungeon mapping."""
    try:
        with open("loot/dungeon_loot.json", "r", encoding="utf-8") as f:
            dungeon_data = json.load(f)

        # Create mapping: item_name -> dungeon_name
        item_to_dungeon = {}
        for dungeon_name, dungeon_info in dungeon_data.items():
            for item in dungeon_info.get("items", []):
                item_to_dungeon[item["name"]] = dungeon_name

        return dungeon_data, item_to_dungeon
    except FileNotFoundError:
        print("Warning: dungeon_loot.json not found, falling back to alphabetical sorting")
        return {}, {}
    except json.JSONDecodeError as e:
        print(f"Warning: Error parsing dungeon_loot.json: {e}, falling back to alphabetical sorting")
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


def calculate_item_points(item_name: str, divine: bool, shiny: bool, quantity: int) -> float:
    return calculate_item_points_service(item_name, divine, shiny, quantity)


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


def _compute_scaled_totals(
    ppe_data: PPEData,
    modifier_bucket: dict[str, float | None],
) -> tuple[float, float, float | None, bool]:
    loot_total = 0.0
    for loot in ppe_data.loot:
        loot_total += calculate_item_points(loot.item_name, loot.divine, loot.shiny, int(loot.quantity))

    bonus_total = 0.0
    penalty_total = 0.0
    for bonus in ppe_data.bonuses:
        raw_bonus_points = calculate_bonus_points(bonus)
        if bonus.name in PENALTY_NAMES:
            penalty_total += raw_bonus_points
        else:
            bonus_total += raw_bonus_points

    adjusted_loot = apply_percent_modifier(loot_total, _as_float(modifier_bucket.get("loot_percent"), 0.0))
    adjusted_bonus = apply_percent_modifier(bonus_total, _as_float(modifier_bucket.get("bonus_percent"), 0.0))
    adjusted_penalty = apply_percent_modifier(penalty_total, _as_float(modifier_bucket.get("penalty_percent"), 0.0))

    total_before_floor = apply_percent_modifier(
        adjusted_loot + adjusted_bonus + adjusted_penalty,
        _as_float(modifier_bucket.get("total_percent"), 0.0),
    )

    minimum_total_raw = modifier_bucket.get("minimum_total")
    minimum_total = _as_float(minimum_total_raw, 0.0) if minimum_total_raw is not None else None
    final_total = total_before_floor
    floor_applied = False
    if minimum_total is not None and final_total < minimum_total:
        final_total = minimum_total
        floor_applied = True

    return total_before_floor, final_total, minimum_total, floor_applied


def create_loot_markdown_file(
    ppe_data: PPEData,
    *,
    guild_config: dict | None = None,
) -> str:
    """Create a temporary markdown file with the loot table and return the file path."""
    class_name = str(getattr(ppe_data.name, "value", ppe_data.name))
    modifier_bucket = get_effective_modifier_bucket_for_ppe(ppe_data, guild_config)
    point_adjustment_lines = non_default_points_adjustment_lines(guild_config, class_names=[class_name])
    total_before_floor, scaled_total, minimum_total, floor_applied = _compute_scaled_totals(ppe_data, modifier_bucket)

    builder = MarkdownMessageBuilder(f"Loot Table: {class_name} (PPE #{ppe_data.id})")
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
                raw_item_points = calculate_item_points(loot.item_name, loot.divine, loot.shiny, int(loot.quantity))
                scaled_item_points = _scaled_loot_entry_points(raw_item_points, modifier_bucket)

                tags: list[str] = []
                if loot.divine:
                    tags.append("divine")
                if loot.shiny:
                    tags.append("shiny")

                line = f"- {loot.item_name} × {loot.quantity} ({_format_points(scaled_item_points)} pts)"
                if tags:
                    line += f" [{', '.join(tags)}]"
                lines.append(line)

            builder.add_section(heading=dungeon_name, lines=lines)

        if unassigned_items:
            lines: list[str] = []
            for loot in sorted(unassigned_items, key=lambda entry: entry.item_name.lower()):
                raw_item_points = calculate_item_points(loot.item_name, loot.divine, loot.shiny, int(loot.quantity))
                scaled_item_points = _scaled_loot_entry_points(raw_item_points, modifier_bucket)

                tags: list[str] = []
                if loot.divine:
                    tags.append("divine")
                if loot.shiny:
                    tags.append("shiny")

                line = f"- {loot.item_name} × {loot.quantity} ({_format_points(scaled_item_points)} pts)"
                if tags:
                    line += f" [{', '.join(tags)}]"
                lines.append(line)

            builder.add_section(heading="Unassigned Items", lines=lines)
    else:
        builder.add_section(heading="Loot Items", lines=["No loot recorded yet."])

    if ppe_data.bonuses:
        bonus_lines: list[str] = []
        for bonus in sorted(ppe_data.bonuses, key=lambda entry: entry.name.lower()):
            total_bonus_points = calculate_bonus_points(bonus)
            scaled_bonus_points = _scaled_bonus_entry_points(
                total_bonus_points,
                is_penalty=(bonus.name in PENALTY_NAMES),
                modifier_bucket=modifier_bucket,
            )
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
    if floor_applied:
        summary_lines.append(
            f"Minimum floor applied: {_format_points(total_before_floor)} -> {_format_points(scaled_total)}"
        )

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
        lines = [
            f"{item_name}{' [shiny]' if shiny else ''}"
            for item_name, shiny in sorted(dungeon_groups[dungeon_name], key=lambda entry: (entry[0].lower(), entry[1]))
        ]
        builder.add_numbered_list(lines, heading=dungeon_name)

    if unassigned_items:
        lines = [
            f"{item_name}{' [shiny]' if shiny else ''}"
            for item_name, shiny in sorted(unassigned_items, key=lambda entry: (entry[0].lower(), entry[1]))
        ]
        builder.add_numbered_list(lines, heading="Unassigned Items")

    return builder.write_temp_file(prefix="season_loot", username=display_name, temp_dir="temp")
