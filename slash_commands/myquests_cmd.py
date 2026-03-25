from __future__ import annotations

import glob
import json
import os
from typing import Dict, Sequence

import discord

from slash_commands import resetquestfor_cmd
from utils.calc_points import normalize_item_name
from utils.generate_board import generate_quest_board
from utils.guild_config import get_quest_points, get_quest_targets, load_guild_config
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.quest_manager import refresh_player_quests


_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DUNGEONS_DIR = os.path.join(_BASE_DIR, "dungeons")
_DUNGEON_LOOT_PATH = os.path.join(_BASE_DIR, "loot", "dungeon_loot.json")
_MISSING_IMAGE_PATH = os.path.join(_BASE_DIR, "image_missing.png")

_ITEM_IMAGE_INDEX: Dict[str, str] = {}
_ITEM_IMAGE_INDEX_READY = False
_ITEM_DUNGEON_INDEX: Dict[str, str] = {}
_ITEM_DUNGEON_INDEX_READY = False


def _strip_shiny_suffix(item_name: str) -> str:
    normalized = normalize_item_name(item_name)
    if normalized.lower().endswith("(shiny)"):
        return normalized[: -len("(shiny)")].strip()
    return normalized


def _build_item_image_index_if_needed() -> None:
    global _ITEM_IMAGE_INDEX_READY
    if _ITEM_IMAGE_INDEX_READY:
        return

    _ITEM_IMAGE_INDEX.clear()
    for png_file in glob.glob(os.path.join(_DUNGEONS_DIR, "**", "*.png"), recursive=True):
        base_name = os.path.splitext(os.path.basename(png_file))[0]
        normalized = normalize_item_name(base_name).lower()
        if normalized and normalized not in _ITEM_IMAGE_INDEX:
            _ITEM_IMAGE_INDEX[normalized] = png_file

    _ITEM_IMAGE_INDEX_READY = True


def _resolve_item_image_path(item_name: str) -> str | None:
    _build_item_image_index_if_needed()

    full_name = normalize_item_name(item_name)
    base_name = _strip_shiny_suffix(item_name)

    candidates = [full_name, base_name]
    if not full_name.lower().endswith("(shiny)"):
        candidates.append(f"{base_name} (shiny)")

    for candidate in candidates:
        key = normalize_item_name(candidate).lower()
        path = _ITEM_IMAGE_INDEX.get(key)
        if path:
            return path

    return _MISSING_IMAGE_PATH if os.path.exists(_MISSING_IMAGE_PATH) else None


def _build_dungeon_lookup_if_needed() -> None:
    global _ITEM_DUNGEON_INDEX_READY
    if _ITEM_DUNGEON_INDEX_READY:
        return

    _ITEM_DUNGEON_INDEX.clear()
    try:
        with open(_DUNGEON_LOOT_PATH, "r", encoding="utf-8") as file_handle:
            payload = json.load(file_handle)
    except (OSError, json.JSONDecodeError):
        _ITEM_DUNGEON_INDEX_READY = True
        return

    if isinstance(payload, dict):
        for dungeon_name, dungeon_data in payload.items():
            if not isinstance(dungeon_data, dict):
                continue
            items = dungeon_data.get("items", [])
            if not isinstance(items, list):
                continue

            for entry in items:
                if not isinstance(entry, dict):
                    continue
                item_name = str(entry.get("name", "")).strip()
                if not item_name:
                    continue

                full_norm = normalize_item_name(item_name).lower()
                base_norm = normalize_item_name(_strip_shiny_suffix(item_name)).lower()
                if full_norm and full_norm not in _ITEM_DUNGEON_INDEX:
                    _ITEM_DUNGEON_INDEX[full_norm] = str(dungeon_name)
                if base_norm and base_norm not in _ITEM_DUNGEON_INDEX:
                    _ITEM_DUNGEON_INDEX[base_norm] = str(dungeon_name)

    _ITEM_DUNGEON_INDEX_READY = True


def _dungeon_for_item(item_name: str) -> str:
    _build_dungeon_lookup_if_needed()
    full_norm = normalize_item_name(item_name).lower()
    base_norm = normalize_item_name(_strip_shiny_suffix(item_name)).lower()
    return _ITEM_DUNGEON_INDEX.get(full_norm) or _ITEM_DUNGEON_INDEX.get(base_norm) or "Dungeon unknown"


def _coerce_resets_remaining(player_data, default_reset_limit: int) -> int:
    value = player_data.quest_resets_remaining
    if value is None:
        return max(0, default_reset_limit)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return max(0, default_reset_limit)


def _board_file(item_names: Sequence[str], title: str, filename: str) -> discord.File:
    buffer = generate_quest_board(
        item_names,
        _resolve_item_image_path,
        title=title,
        missing_image_path=_MISSING_IMAGE_PATH if os.path.exists(_MISSING_IMAGE_PATH) else None,
        columns=None,
        icon_size=34,
    )
    return discord.File(buffer, filename=filename)


def _build_quest_lines(item_names: Sequence[str]) -> str:
    if not item_names:
        return "• None"
    return "\n".join(f"• {item_name} - {_dungeon_for_item(item_name)}" for item_name in item_names)


def _build_home_embed(
    display_name: str,
    quests,
    resets_remaining: int,
    reset_limit: int,
    points_regular: int,
    points_shiny: int,
    points_skin: int,
    target_regular: int,
    target_shiny: int,
    target_skin: int,
) -> discord.Embed:
    completed_regular = len(quests.completed_items)
    completed_shiny = len(quests.completed_shinies)
    completed_skin = len(quests.completed_skins)

    active_regular = len(quests.current_items)
    active_shiny = len(quests.current_shinies)
    active_skin = len(quests.current_skins)

    total_completed = completed_regular + completed_shiny + completed_skin
    total_points = (
        (completed_regular * points_regular)
        + (completed_shiny * points_shiny)
        + (completed_skin * points_skin)
    )

    embed = discord.Embed(
        title=f"My Quests - {display_name}",
        description=(
            f"Resets remaining: **{resets_remaining}/{reset_limit}**\n"
            "Use the menu below to view quest boards, completed quests, or reset your quest progress."
        ),
        color=discord.Color.from_rgb(54, 57, 63),
    )
    embed.add_field(
        name="Quest Progress",
        value=(
            f"Active: **{active_regular}** Regular, **{active_shiny}** Shiny, **{active_skin}** Skin\n"
            f"Targets: **{target_regular}** Regular, **{target_shiny}** Shiny, **{target_skin}** Skin\n"
            f"Completed: **{total_completed}** total"
        ),
        inline=False,
    )
    embed.add_field(
        name="Points",
        value=(
            f"Regular: **{points_regular}** each\n"
            f"Shiny: **{points_shiny}** each\n"
            f"Skin: **{points_skin}** each\n"
            f"Completed quest points: **{total_points}**"
        ),
        inline=False,
    )
    embed.set_footer(text="Boards render only when selected to keep this panel clean.")
    return embed


def _build_category_embed(title: str, item_names: Sequence[str], attachment_name: str) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=_build_quest_lines(item_names),
        color=discord.Color.from_rgb(88, 101, 242),
    )
    embed.set_image(url=f"attachment://{attachment_name}")
    return embed


def _build_completed_embed(quests, points_regular: int, points_shiny: int, points_skin: int) -> discord.Embed:
    lines = ["**Completed Quests**", ""]

    total_points = 0
    if quests.completed_items:
        lines.append("Regular:")
        for item_name in quests.completed_items:
            total_points += points_regular
            lines.append(f"• {item_name} - +{points_regular} pts")
        lines.append("")

    if quests.completed_shinies:
        lines.append("Shiny:")
        for item_name in quests.completed_shinies:
            total_points += points_shiny
            lines.append(f"• {item_name} - +{points_shiny} pts")
        lines.append("")

    if quests.completed_skins:
        lines.append("Skins:")
        for item_name in quests.completed_skins:
            total_points += points_skin
            lines.append(f"• {item_name} - +{points_skin} pts")
        lines.append("")

    if total_points == 0:
        lines = ["• No completed quests yet."]

    description = "\n".join(lines)
    if len(description) > 3900:
        description = description[:3850].rstrip() + "\n... (truncated)"

    embed = discord.Embed(
        title="Completed Quest Log",
        description=description,
        color=discord.Color.green(),
    )
    embed.add_field(name="Total Completed Quest Points", value=f"**{total_points}**", inline=False)
    return embed


class MyQuestsView(discord.ui.View):
    def __init__(
        self,
        *,
        owner_id: int,
        display_name: str,
        home_embed: discord.Embed,
        current_regular: Sequence[str],
        current_shiny: Sequence[str],
        current_skin: Sequence[str],
        current_all: Sequence[str],
        completed_embed: discord.Embed,
    ) -> None:
        super().__init__(timeout=600)
        self.owner_id = owner_id
        self.display_name = display_name
        self.home_embed = home_embed
        self.current_regular = list(current_regular)
        self.current_shiny = list(current_shiny)
        self.current_skin = list(current_skin)
        self.current_all = list(current_all)
        self.completed_embed = completed_embed

    async def _edit_with_board(
        self,
        interaction: discord.Interaction,
        *,
        embed_title: str,
        board_title_suffix: str,
        item_names: Sequence[str],
        attachment_name: str,
    ) -> None:
        board_file = _board_file(
            item_names,
            f"{self.display_name}'s {board_title_suffix}",
            attachment_name,
        )
        embed = _build_category_embed(embed_title, item_names, attachment_name)
        await interaction.response.edit_message(embed=embed, attachments=[board_file], view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This panel belongs to another user.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Home", style=discord.ButtonStyle.secondary)
    async def home(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(embed=self.home_embed, attachments=[], view=self)

    @discord.ui.button(label="Regular", style=discord.ButtonStyle.primary)
    async def regular(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._edit_with_board(
            interaction,
            embed_title="Regular Quest Targets",
            board_title_suffix="Missing Regular Quests",
            item_names=self.current_regular,
            attachment_name="myquests_regular.png",
        )

    @discord.ui.button(label="Shiny", style=discord.ButtonStyle.primary)
    async def shiny(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._edit_with_board(
            interaction,
            embed_title="Shiny Quest Targets",
            board_title_suffix="Missing Shinies",
            item_names=self.current_shiny,
            attachment_name="myquests_shiny.png",
        )

    @discord.ui.button(label="Skins", style=discord.ButtonStyle.primary)
    async def skins(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._edit_with_board(
            interaction,
            embed_title="Skin Quest Targets",
            board_title_suffix="Missing Skins",
            item_names=self.current_skin,
            attachment_name="myquests_skins.png",
        )

    @discord.ui.button(label="Show All", style=discord.ButtonStyle.success)
    async def show_all(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._edit_with_board(
            interaction,
            embed_title="All Current Quest Targets",
            board_title_suffix="All Missing Quests",
            item_names=self.current_all,
            attachment_name="myquests_all.png",
        )

    @discord.ui.button(label="Completed", style=discord.ButtonStyle.success)
    async def completed(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(embed=self.completed_embed, attachments=[], view=self)

    @discord.ui.button(label="Reset Quests", style=discord.ButtonStyle.danger)
    async def reset_quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await resetquestfor_cmd.command_self(interaction)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary)
    async def close(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.stop()
        await interaction.response.edit_message(
            content="Quest panel closed.",
            embed=None,
            attachments=[],
            view=None,
        )


async def command(interaction: discord.Interaction):
    try:
        records = await load_player_records(interaction)
        user_id = interaction.user.id
        key = ensure_player_exists(records, user_id)

        if key not in records or not records[key].is_member:
            raise KeyError("❌ You're not part of the PPE contest.")

        player_data = records[key]
        config = await load_guild_config(interaction)
        default_reset_limit = int(config["quest_settings"]["num_resets"])
        resets_remaining = _coerce_resets_remaining(player_data, default_reset_limit)

        regular_target, shiny_target, skin_target = await get_quest_targets(interaction)
        regular_points, shiny_points, skin_points = await get_quest_points(interaction)

        changed = refresh_player_quests(
            player_data,
            target_item_quests=regular_target,
            target_shiny_quests=shiny_target,
            target_skin_quests=skin_target,
        )

        if player_data.quest_resets_remaining != resets_remaining:
            player_data.quest_resets_remaining = resets_remaining
            changed = True

        if changed:
            await save_player_records(interaction, records)

        quests = player_data.quests

        current_regular = list(quests.current_items)
        current_shiny = list(quests.current_shinies)
        current_skin = list(quests.current_skins)
        current_all = current_regular + current_shiny + current_skin

        home_embed = _build_home_embed(
            interaction.user.display_name,
            quests,
            resets_remaining,
            default_reset_limit,
            regular_points,
            shiny_points,
            skin_points,
            regular_target,
            shiny_target,
            skin_target,
        )
        completed_embed = _build_completed_embed(quests, regular_points, shiny_points, skin_points)

        view = MyQuestsView(
            owner_id=user_id,
            display_name=interaction.user.display_name,
            home_embed=home_embed,
            current_regular=current_regular,
            current_shiny=current_shiny,
            current_skin=current_skin,
            current_all=current_all,
            completed_embed=completed_embed,
        )

        await interaction.response.send_message(
            embed=home_embed,
            view=view,
            ephemeral=False,
        )

    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
