import json
from dataclass import PPEData
from utils.markdown_message_builder import MarkdownMessageBuilder
from utils.points_service import calculate_item_points as calculate_item_points_service


def load_dungeon_data():
    """Load the dungeon loot JSON file and create item-to-dungeon mapping."""
    try:
        with open('loot/dungeon_loot.json', 'r', encoding='utf-8') as f:
            dungeon_data = json.load(f)
        
        # Create mapping: item_name -> dungeon_name
        item_to_dungeon = {}
        for dungeon_name, dungeon_info in dungeon_data.items():
            for item in dungeon_info.get('items', []):
                item_to_dungeon[item['name']] = dungeon_name
        
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


def create_loot_markdown_file(ppe_data: PPEData) -> str:
    """Create a temporary markdown file with the loot table and return the file path."""
    display_name = str(getattr(ppe_data.name, "value", ppe_data.name))

    builder = MarkdownMessageBuilder(f"Loot Table: {display_name} (PPE #{ppe_data.id})")
    builder.add_paragraph(f"Total Points: {_format_points(ppe_data.points)}")

    if ppe_data.loot:
        sorted_dungeons, dungeon_groups, unassigned_items = _group_entries_by_dungeon(
            list(ppe_data.loot),
            key_name_fn=lambda loot_entry: loot_entry.item_name,
        )

        for dungeon_name in sorted_dungeons:
            lines: list[str] = []
            for loot in sorted(dungeon_groups[dungeon_name], key=lambda entry: entry.item_name.lower()):
                item_points = calculate_item_points(loot.item_name, loot.divine, loot.shiny, int(loot.quantity))

                tags: list[str] = []
                if loot.divine:
                    tags.append("divine")
                if loot.shiny:
                    tags.append("shiny")

                line = f"- {loot.item_name} × {loot.quantity} ({_format_points(item_points)} pts)"
                if tags:
                    line += f" [{', '.join(tags)}]"
                lines.append(line)

            builder.add_section(heading=dungeon_name, lines=lines)

        if unassigned_items:
            lines: list[str] = []
            for loot in sorted(unassigned_items, key=lambda entry: entry.item_name.lower()):
                item_points = calculate_item_points(loot.item_name, loot.divine, loot.shiny, int(loot.quantity))

                tags: list[str] = []
                if loot.divine:
                    tags.append("divine")
                if loot.shiny:
                    tags.append("shiny")

                line = f"- {loot.item_name} × {loot.quantity} ({_format_points(item_points)} pts)"
                if tags:
                    line += f" [{', '.join(tags)}]"
                lines.append(line)

            builder.add_section(heading="Unassigned Items", lines=lines)
    else:
        builder.add_section(heading="Loot Items", lines=["No loot recorded yet."])

    if ppe_data.bonuses:
        bonus_lines: list[str] = []
        for bonus in sorted(ppe_data.bonuses, key=lambda entry: entry.name.lower()):
            total_bonus_points = float(bonus.points) * int(bonus.quantity)
            points_display = _format_points(total_bonus_points)
            if total_bonus_points > 0:
                points_display = f"+{points_display}"

            line = f"- {bonus.name} × {bonus.quantity} ({points_display} pts)"
            if bonus.repeatable:
                line += " [repeatable]"
            bonus_lines.append(line)

        builder.add_section(heading="Bonuses", lines=bonus_lines)

    total_loot_items = len(ppe_data.loot) if ppe_data.loot else 0
    total_bonus_items = len(ppe_data.bonuses) if ppe_data.bonuses else 0
    total_items = total_loot_items + total_bonus_items
    builder.add_section(
        heading="Summary",
        lines=[
            f"Loot entries: {total_loot_items}",
            f"Bonus entries: {total_bonus_items}",
        ],
    )

    return builder.write_temp_file(
        prefix=f"loot_table_ppe_{ppe_data.id}",
        username=display_name,
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
