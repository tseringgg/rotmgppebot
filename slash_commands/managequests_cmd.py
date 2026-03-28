from __future__ import annotations

import discord

from menus.menu_utils import OwnerBoundView
from utils.guild_config import load_guild_config, save_guild_config
from utils.player_records import load_player_records, save_player_records
from utils.quest_manager import refresh_player_quests


def _global_payload(settings: dict) -> dict:
    return {
        "enabled": bool(settings.get("use_global_quests", False)),
        "regular": list(settings.get("global_regular_quests", [])),
        "shiny": list(settings.get("global_shiny_quests", [])),
        "skin": list(settings.get("global_skin_quests", [])),
    }


def _coerce_non_negative_int(raw_value: str, field_name: str) -> int:
    try:
        value = int(str(raw_value).strip())
    except (TypeError, ValueError):
        raise ValueError(f"❌ `{field_name}` must be a whole number.")
    if value < 0:
        raise ValueError(f"❌ `{field_name}` must be 0 or greater.")
    return value


def _dedupe_items(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(text)
    return output


async def _apply_settings_to_players(
    interaction: discord.Interaction,
    *,
    settings: dict,
    reset_limit_changed: bool = False,
) -> tuple[int, int, int]:
    records = await load_player_records(interaction)

    players_adjusted = 0
    active_entries_removed = 0
    reset_counters_updated = 0

    for player_data in records.values():
        if not player_data.is_member:
            continue

        before_count = (
            len(player_data.quests.current_items)
            + len(player_data.quests.current_shinies)
            + len(player_data.quests.current_skins)
        )

        changed = refresh_player_quests(
            player_data,
            target_item_quests=int(settings["regular_target"]),
            target_shiny_quests=int(settings["shiny_target"]),
            target_skin_quests=int(settings["skin_target"]),
            global_quests=_global_payload(settings),
        )

        after_count = (
            len(player_data.quests.current_items)
            + len(player_data.quests.current_shinies)
            + len(player_data.quests.current_skins)
        )

        if after_count < before_count:
            active_entries_removed += before_count - after_count
        if changed:
            players_adjusted += 1

        if reset_limit_changed:
            player_data.quest_resets_remaining = int(settings["num_resets"])
            reset_counters_updated += 1

    if players_adjusted > 0 or reset_counters_updated > 0:
        await save_player_records(interaction, records)

    return players_adjusted, active_entries_removed, reset_counters_updated


async def _load_settings(interaction: discord.Interaction) -> dict:
    config = await load_guild_config(interaction)
    return dict(config["quest_settings"])


def _build_home_embed(settings: dict) -> discord.Embed:
    global_enabled = bool(settings.get("use_global_quests", False))
    regular_global = len(settings.get("global_regular_quests", []))
    shiny_global = len(settings.get("global_shiny_quests", []))
    skin_global = len(settings.get("global_skin_quests", []))

    embed = discord.Embed(
        title="Manage Quests",
        description="Admin quest controls for this server.",
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="Quest Generation",
        value=(
            f"Regular target: **{settings['regular_target']}**\n"
            f"Shiny target: **{settings['shiny_target']}**\n"
            f"Skin target: **{settings['skin_target']}**\n"
            f"Resets per player: **{settings['num_resets']}**"
        ),
        inline=True,
    )
    embed.add_field(
        name="Quest Points",
        value=(
            f"Regular: **{settings['regular_points']}**\n"
            f"Shiny: **{settings['shiny_points']}**\n"
            f"Skin: **{settings['skin_points']}**"
        ),
        inline=True,
    )
    embed.add_field(
        name="Global Quests",
        value=(
            f"Enabled: **{'Yes' if global_enabled else 'No'}**\n"
            f"Regular pool: **{regular_global}**\n"
            f"Shiny pool: **{shiny_global}**\n"
            f"Skin pool: **{skin_global}**"
        ),
        inline=False,
    )
    embed.set_footer(text="Use Edit Quest Settings to update targets/points, or Set Global Quests to enforce shared quests.")
    return embed


def _build_global_embed(settings: dict) -> discord.Embed:
    enabled = bool(settings.get("use_global_quests", False))
    if not enabled:
        return discord.Embed(
            title="Set Global Quests",
            description=(
                "Global quests are currently **disabled**.\n"
                "Enable this mode to force one shared quest list for everyone."
            ),
            color=discord.Color.orange(),
        )

    regular = list(settings.get("global_regular_quests", []))
    shiny = list(settings.get("global_shiny_quests", []))
    skin = list(settings.get("global_skin_quests", []))

    def _format_list(items: list[str]) -> str:
        if not items:
            return "• None"
        text = "\n".join(f"• {item}" for item in items)
        if len(text) > 1024:
            text = text[:1000].rstrip() + "\n..."
        return text

    embed = discord.Embed(
        title="Set Global Quests",
        description=(
            "Global quests are **enabled**.\n"
            "Completing a quest removes it from the active list and does not auto-generate replacements."
        ),
        color=discord.Color.green(),
    )
    embed.add_field(name="Regular Global Quests", value=_format_list(regular), inline=False)
    embed.add_field(name="Shiny Global Quests", value=_format_list(shiny), inline=False)
    embed.add_field(name="Skin Global Quests", value=_format_list(skin), inline=False)
    return embed


class EditQuestSettingsModal(discord.ui.Modal, title="Edit Quest Settings"):
    regular_quests = discord.ui.TextInput(label="Regular Quest Target", max_length=4)
    shiny_quests = discord.ui.TextInput(label="Shiny Quest Target", max_length=4)
    skin_quests = discord.ui.TextInput(label="Skin Quest Target", max_length=4)
    num_resets = discord.ui.TextInput(label="Quest Resets Per Player", max_length=4)
    points = discord.ui.TextInput(
        label="Points (regular, shiny, skin)",
        placeholder="Example: 5, 10, 15",
        max_length=30,
    )

    def __init__(self, *, owner_id: int, settings: dict, source_message: discord.Message | None) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message

        self.regular_quests.default = str(settings["regular_target"])
        self.shiny_quests.default = str(settings["shiny_target"])
        self.skin_quests.default = str(settings["skin_target"])
        self.num_resets.default = str(settings["num_resets"])
        self.points.default = f"{settings['regular_points']}, {settings['shiny_points']}, {settings['skin_points']}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        try:
            regular = _coerce_non_negative_int(self.regular_quests.value, "regular_quests")
            shiny = _coerce_non_negative_int(self.shiny_quests.value, "shiny_quests")
            skin = _coerce_non_negative_int(self.skin_quests.value, "skin_quests")
            num_resets = _coerce_non_negative_int(self.num_resets.value, "num_resets")

            parts = [part.strip() for part in str(self.points.value).split(",")]
            if len(parts) != 3:
                raise ValueError("❌ Points must be entered as exactly: regular, shiny, skin.")
            regular_points = _coerce_non_negative_int(parts[0], "regular_points")
            shiny_points = _coerce_non_negative_int(parts[1], "shiny_points")
            skin_points = _coerce_non_negative_int(parts[2], "skin_points")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        config = await load_guild_config(interaction)
        settings = dict(config["quest_settings"])

        before_resets = int(settings.get("num_resets", 0))
        settings["regular_target"] = regular
        settings["shiny_target"] = shiny
        settings["skin_target"] = skin
        settings["num_resets"] = num_resets
        settings["regular_points"] = regular_points
        settings["shiny_points"] = shiny_points
        settings["skin_points"] = skin_points

        config["quest_settings"] = settings
        await save_guild_config(interaction, config)

        players_adjusted, active_removed, reset_counters_updated = await _apply_settings_to_players(
            interaction,
            settings=settings,
            reset_limit_changed=(before_resets != num_resets),
        )

        await interaction.response.send_message(
            (
                "✅ Quest settings updated.\n"
                f"Players adjusted: **{players_adjusted}**\n"
                f"Active quest entries removed: **{active_removed}**\n"
                f"Reset counters updated: **{reset_counters_updated}**"
            ),
            ephemeral=True,
        )

        if self.source_message is not None:
            refreshed = await _load_settings(interaction)
            view = ManageQuestsHomeView(owner_id=self.owner_id, settings=refreshed)
            try:
                await self.source_message.edit(embed=view.current_embed(), view=view)
            except discord.HTTPException:
                pass


class AddGlobalQuestItemsModal(discord.ui.Modal):
    items = discord.ui.TextInput(
        label="Quest Items",
        placeholder="Enter one item per line or comma-separated",
        style=discord.TextStyle.paragraph,
        max_length=1800,
    )

    def __init__(self, *, owner_id: int, category: str, source_message: discord.Message | None) -> None:
        super().__init__(title=f"Add Global {category.title()} Quests", timeout=300)
        self.owner_id = owner_id
        self.category = category
        self.source_message = source_message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        raw_text = str(self.items.value)
        parsed = [segment.strip() for chunk in raw_text.splitlines() for segment in chunk.split(",")]
        parsed = [item for item in parsed if item]
        if not parsed:
            await interaction.response.send_message("❌ Provide at least one quest item name.", ephemeral=True)
            return

        if self.category == "shiny":
            normalized: list[str] = []
            for item in parsed:
                if item.lower().endswith("(shiny)"):
                    normalized.append(item)
                else:
                    normalized.append(f"{item} (shiny)")
            parsed = normalized

        config = await load_guild_config(interaction)
        settings = dict(config["quest_settings"])
        key = f"global_{self.category}_quests"

        merged = _dedupe_items(list(settings.get(key, [])) + parsed)
        settings[key] = merged
        config["quest_settings"] = settings
        await save_guild_config(interaction, config)

        players_adjusted, active_removed, _resets = await _apply_settings_to_players(interaction, settings=settings)

        await interaction.response.send_message(
            (
                f"✅ Added **{len(parsed)}** {self.category} global quest item(s).\n"
                f"Total in pool: **{len(merged)}**\n"
                f"Players adjusted: **{players_adjusted}**\n"
                f"Active entries removed: **{active_removed}**"
            ),
            ephemeral=True,
        )

        if self.source_message is not None:
            view = GlobalQuestsView(owner_id=self.owner_id, settings=settings)
            try:
                await self.source_message.edit(embed=view.current_embed(), view=view)
            except discord.HTTPException:
                pass


class GlobalQuestsView(OwnerBoundView):
    def __init__(self, *, owner_id: int, settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings

    def current_embed(self) -> discord.Embed:
        return _build_global_embed(self.settings)

    async def _refresh(self, interaction: discord.Interaction) -> None:
        self.settings = await _load_settings(interaction)
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Enable/Disable", style=discord.ButtonStyle.success, row=0)
    async def toggle_enabled(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        config = await load_guild_config(interaction)
        settings = dict(config["quest_settings"])
        settings["use_global_quests"] = not bool(settings.get("use_global_quests", False))
        config["quest_settings"] = settings
        await save_guild_config(interaction, config)

        players_adjusted, active_removed, _resets = await _apply_settings_to_players(interaction, settings=settings)
        self.settings = settings
        await interaction.response.edit_message(embed=self.current_embed(), view=self)
        await interaction.followup.send(
            (
                f"✅ Global quests {'enabled' if settings['use_global_quests'] else 'disabled'}.\n"
                f"Players adjusted: **{players_adjusted}**\n"
                f"Active entries removed: **{active_removed}**"
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="Add Regular", style=discord.ButtonStyle.primary, row=1)
    async def add_regular(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not bool(self.settings.get("use_global_quests", False)):
            await interaction.response.send_message("Global quests are disabled. Enable them first.", ephemeral=True)
            return
        await interaction.response.send_modal(
            AddGlobalQuestItemsModal(owner_id=self.owner_id, category="regular", source_message=interaction.message)
        )

    @discord.ui.button(label="Add Shiny", style=discord.ButtonStyle.primary, row=1)
    async def add_shiny(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not bool(self.settings.get("use_global_quests", False)):
            await interaction.response.send_message("Global quests are disabled. Enable them first.", ephemeral=True)
            return
        await interaction.response.send_modal(
            AddGlobalQuestItemsModal(owner_id=self.owner_id, category="shiny", source_message=interaction.message)
        )

    @discord.ui.button(label="Add Skin", style=discord.ButtonStyle.primary, row=1)
    async def add_skin(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not bool(self.settings.get("use_global_quests", False)):
            await interaction.response.send_message("Global quests are disabled. Enable them first.", ephemeral=True)
            return
        await interaction.response.send_modal(
            AddGlobalQuestItemsModal(owner_id=self.owner_id, category="skin", source_message=interaction.message)
        )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        home_settings = await _load_settings(interaction)
        view = ManageQuestsHomeView(owner_id=self.owner_id, settings=home_settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class ManageQuestsHomeView(OwnerBoundView):
    def __init__(self, *, owner_id: int, settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings

    def current_embed(self) -> discord.Embed:
        return _build_home_embed(self.settings)

    @discord.ui.button(label="Reset All Quests", style=discord.ButtonStyle.danger, row=0)
    async def reset_all(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from slash_commands import resetquests_cmd

        await resetquests_cmd.command(interaction)

    @discord.ui.button(label="Edit Quest Settings", style=discord.ButtonStyle.primary, row=0)
    async def edit_settings(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await _load_settings(interaction)
        await interaction.response.send_modal(
            EditQuestSettingsModal(owner_id=self.owner_id, settings=self.settings, source_message=interaction.message)
        )

    @discord.ui.button(label="Set Global Quests", style=discord.ButtonStyle.success, row=1)
    async def set_global_quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await _load_settings(interaction)
        view = GlobalQuestsView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary, row=2)
    async def close(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/managequests` menu.", embed=None, view=None)


async def command(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)

    settings = await _load_settings(interaction)
    view = ManageQuestsHomeView(owner_id=interaction.user.id, settings=settings)
    await interaction.response.send_message(embed=view.current_embed(), view=view, ephemeral=True)
