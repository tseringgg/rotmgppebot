from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import discord

from menus.leaderboard.common import send_error_response
from menus.leaderboard.services import member_display_name, require_guild
from utils.calc_points import normalize_item_name
from utils.guild_config import get_quest_points
from utils.player_records import load_player_records
from utils.ppe_types import ppe_type_short_label
from utils.season_loot_history import season_unique_items

_LOOT_CSV_PATH = Path("rotmg_loot_drops_updated.csv")
_ITEM_TO_DUNGEON: dict[str, str] | None = None


def _load_item_to_dungeon() -> dict[str, str]:
    global _ITEM_TO_DUNGEON
    if _ITEM_TO_DUNGEON is not None:
        return _ITEM_TO_DUNGEON

    mapping: dict[str, str] = {}
    try:
        with _LOOT_CSV_PATH.open("r", encoding="utf-8", newline="") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                item_name = normalize_item_name(str(row.get("Item Name", "")).strip())
                dungeon_name = str(row.get("Dungeon", "")).strip()
                if not item_name or not dungeon_name:
                    continue
                mapping.setdefault(item_name, dungeon_name)
    except OSError:
        mapping = {}

    _ITEM_TO_DUNGEON = mapping
    return mapping


def _format_points(value: float) -> str:
    rounded = round(float(value), 1)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.1f}"


async def command(interaction: discord.Interaction) -> None:
    guild = await require_guild(interaction)
    if guild is None:
        return

    try:
        records = await load_player_records(interaction)
        regular_points, shiny_points, skin_points = await get_quest_points(interaction)
        item_to_dungeon = _load_item_to_dungeon()

        members: list[tuple[int, object]] = [
            (user_id, data)
            for user_id, data in records.items()
            if bool(getattr(data, "is_member", False))
        ]

        if not members:
            embed = discord.Embed(
                title="Contest Stats",
                description="No contest members found yet.",
                color=discord.Color.green(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        player_totals: list[dict[str, object]] = []
        class_counts: Counter[str] = Counter()
        ppe_type_counts: Counter[str] = Counter()
        dungeon_counts_by_player: dict[int, Counter[str]] = {}

        total_characters = 0
        total_points = 0.0
        total_unique_season = 0
        total_completed_quests = 0

        for user_id, data in members:
            ppes = list(getattr(data, "ppes", []) or [])
            quest_data = getattr(data, "quests", None)

            display_name = member_display_name(guild, user_id)
            player_points = sum(float(getattr(ppe, "points", 0.0) or 0.0) for ppe in ppes)
            player_character_count = len(ppes)
            player_unique_season = len(season_unique_items(data))

            completed_regular = len(getattr(quest_data, "completed_items", []) or [])
            completed_shiny = len(getattr(quest_data, "completed_shinies", []) or [])
            completed_skins = len(getattr(quest_data, "completed_skins", []) or [])
            completed_total = completed_regular + completed_shiny + completed_skins
            weighted_quest_points = (
                completed_regular * int(regular_points)
                + completed_shiny * int(shiny_points)
                + completed_skins * int(skin_points)
            )

            player_classes: Counter[str] = Counter()
            player_dungeons: Counter[str] = Counter()
            mapped_drops = 0

            for ppe in ppes:
                class_name = str(getattr(getattr(ppe, "name", "Unknown"), "value", getattr(ppe, "name", "Unknown")))
                class_counts[class_name] += 1
                player_classes[class_name] += 1

                ppe_type = str(getattr(ppe, "ppe_type", "") or "")
                ppe_type_counts[ppe_type_short_label(ppe_type)] += 1

                for loot in list(getattr(ppe, "loot", []) or []):
                    item_name = normalize_item_name(str(getattr(loot, "item_name", "")))
                    if not item_name:
                        continue
                    dungeon_name = item_to_dungeon.get(item_name)
                    if not dungeon_name:
                        continue
                    try:
                        qty = max(1, int(getattr(loot, "quantity", 1)))
                    except (TypeError, ValueError):
                        qty = 1
                    player_dungeons[dungeon_name] += qty
                    mapped_drops += qty

            dungeon_counts_by_player[user_id] = player_dungeons

            if player_classes:
                main_class, main_count = sorted(player_classes.items(), key=lambda item: (-item[1], item[0].lower()))[0]
                class_focus_pct = round((main_count / max(1, player_character_count)) * 100)
            else:
                main_class, class_focus_pct = "None", 0

            player_totals.append(
                {
                    "user_id": user_id,
                    "display_name": display_name,
                    "points": player_points,
                    "characters": player_character_count,
                    "unique_season": player_unique_season,
                    "completed_total": completed_total,
                    "weighted_quest_points": weighted_quest_points,
                    "main_class": main_class,
                    "class_focus_pct": class_focus_pct,
                    "mapped_drops": mapped_drops,
                }
            )

            total_characters += player_character_count
            total_points += player_points
            total_unique_season += player_unique_season
            total_completed_quests += completed_total

        def by_metric(metric: str) -> list[dict[str, object]]:
            return sorted(
                player_totals,
                key=lambda row: (-float(row[metric]), str(row["display_name"]).lower(), int(row["user_id"])),
            )

        touch_grass = by_metric("points")[0]
        collector = by_metric("unique_season")[0]
        quester = by_metric("weighted_quest_points")[0]
        character_spammer = by_metric("characters")[0]
        class_specialist = by_metric("class_focus_pct")[0]

        obsessed_rows: list[tuple[int, float, str, str]] = []
        for row in player_totals:
            user_id = int(row["user_id"])
            dungeons = dungeon_counts_by_player.get(user_id, Counter())
            if not dungeons:
                continue
            top_dungeon, top_count = sorted(dungeons.items(), key=lambda item: (-item[1], item[0].lower()))[0]
            mapped = max(1, int(row["mapped_drops"]))
            pct = (top_count / mapped) * 100
            obsessed_rows.append((top_count, pct, str(row["display_name"]), top_dungeon))

        obsessed_rows.sort(key=lambda item: (-item[0], -item[1], item[2].lower(), item[3].lower()))
        obsessed = obsessed_rows[0] if obsessed_rows else None

        top_classes = sorted(class_counts.items(), key=lambda item: (-item[1], item[0].lower()))
        class_lines = [f"- **{name}**: {count}" for name, count in top_classes[:5]]
        if not class_lines:
            class_lines.append("- No character classes logged yet.")

        top_ppe_types = sorted(ppe_type_counts.items(), key=lambda item: (-item[1], item[0].lower()))
        ppe_type_lines = [f"- **{name}**: {count}" for name, count in top_ppe_types[:6]]
        if not ppe_type_lines:
            ppe_type_lines.append("- No PPE types logged yet.")

        least_line = ""
        if top_classes:
            least_name, least_count = sorted(top_classes, key=lambda item: (item[1], item[0].lower()))[0]
            least_line = f"\nLeast picked: **{least_name}** ({least_count})"

        player_count = len(player_totals)
        avg_chars = round(total_characters / max(1, player_count), 2)

        embed = discord.Embed(
            title="Contest Stats",
            description="Server-wide contest wrap-up with consistent weekly-style callouts.",
            color=discord.Color.green(),
        )

        embed.add_field(
            name="Contest Snapshot",
            value=(
                f"Players: **{player_count}**\n"
                f"Characters: **{total_characters}** (avg **{avg_chars}**/player)\n"
                f"Total points: **{_format_points(total_points)}**\n"
                f"Unique season items (sum): **{total_unique_season}**\n"
                f"Completed quests (sum): **{total_completed_quests}**"
            ),
            inline=False,
        )

        embed.add_field(
            name="Needs to touch grass.",
            value=(
                f"**{touch_grass['display_name']}** leads with **{_format_points(float(touch_grass['points']))}** points "
                f"across **{touch_grass['characters']}** characters."
            ),
            inline=False,
        )

        if obsessed is None:
            obsessed_value = "Not enough mapped dungeon drops yet to call this one."
        else:
            obsessed_value = (
                f"**{obsessed[2]}** is farming **{obsessed[3]}** the hardest with "
                f"**{obsessed[0]}** mapped drops there"
                f" ({obsessed[1]:.0f}% of their mapped drops)."
            )

        embed.add_field(name="Obsessed with one dungeon.", value=obsessed_value, inline=False)

        embed.add_field(
            name="Character Type Meta",
            value="\n".join(class_lines) + least_line,
            inline=False,
        )

        embed.add_field(
            name="PPE Types",
            value="\n".join(ppe_type_lines),
            inline=False,
        )

        embed.add_field(
            name="Roster Hoarder",
            value=(
                f"**{character_spammer['display_name']}** has the biggest stable: "
                f"**{character_spammer['characters']}** characters."
            ),
            inline=True,
        )

        embed.add_field(
            name="Class Specialist",
            value=(
                f"**{class_specialist['display_name']}** is locked in on **{class_specialist['main_class']}** "
                f"(**{class_specialist['class_focus_pct']}%** of their roster)."
            ),
            inline=True,
        )

        embed.add_field(
            name="Season Collector",
            value=(
                f"**{collector['display_name']}** has the deepest season museum: "
                f"**{collector['unique_season']}** unique items."
            ),
            inline=True,
        )

        embed.add_field(
            name="Quest Goblin",
            value=(
                f"**{quester['display_name']}** leads quest scoring with "
                f"**{quester['weighted_quest_points']}** weighted quest points "
                f"from **{quester['completed_total']}** completions."
            ),
            inline=False,
        )

        embed.set_footer(text="PPE Wrapped: Contest Edition")
        await interaction.response.send_message(embed=embed)
    except Exception as exc:
        await send_error_response(interaction, str(exc))
