from __future__ import annotations

import os
from typing import Any

import discord

from dataclass import Bonus, PPEData, PlayerData
from menus.menu_utils import OwnerBoundView
from slash_commands import myquests_cmd, shareloot_cmd, shareseasonloot_cmd
from utils.bonus_data import load_bonuses
from utils.guild_config import get_realmshark_settings, load_guild_config
from utils.loot_table_md_builder import create_loot_markdown_file
from utils.pagination import LootPaginationView, chunk_lines_to_pages
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.points_service import recompute_ppe_points


def _display_class_name(ppe: PPEData) -> str:
    return str(getattr(ppe.name, "value", ppe.name))


def _format_points(value: float) -> str:
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def _get_penalty_map(ppe: PPEData) -> dict[str, float]:
    result = {
        "pet": 0.0,
        "exalts": 0.0,
        "loot": 0.0,
        "incombat": 0.0,
    }

    for bonus in ppe.bonuses:
        total = float(bonus.points) * max(1, int(getattr(bonus, "quantity", 1)))
        if bonus.name == "Pet Level Penalty":
            result["pet"] += total
        elif bonus.name == "Exalts Penalty":
            result["exalts"] += total
        elif bonus.name == "Loot Boost Penalty":
            result["loot"] += total
        elif bonus.name == "In-Combat Reduction Penalty":
            result["incombat"] += total

    return result


def _penalty_stats_text(ppe: PPEData) -> str:
    penalties = _get_penalty_map(ppe)

    pet_level = int(round(-4.0 * penalties["pet"])) if penalties["pet"] != 0 else 0
    exalts = int(round(-2.0 * penalties["exalts"])) if penalties["exalts"] != 0 else 0
    loot_boost = round(-0.5 * penalties["loot"], 1) if penalties["loot"] != 0 else 0.0
    incombat = round(-0.1 * penalties["incombat"], 1) if penalties["incombat"] != 0 else 0.0

    return (
        f"Pet Level: **{pet_level}**\\n"
        f"Exalts: **{exalts}**\\n"
        f"Loot Boost: **{loot_boost}%**\\n"
        f"In-Combat Reduction: **{incombat}s**"
    )


def _team_type_text(player_data: PlayerData) -> str:
    return "Team PPE" if player_data.team_name else "Regular PPE"


def _build_home_embed(user: discord.abc.User, player_data: PlayerData, active_ppe: PPEData | None) -> discord.Embed:
    sorted_ppes = sorted(player_data.ppes, key=lambda p: int(p.id))
    best_ppe = max(sorted_ppes, key=lambda p: float(p.points), default=None)

    if best_ppe:
        best_line = f"PPE #{best_ppe.id} ({_display_class_name(best_ppe)}) - **{_format_points(best_ppe.points)}**"
    else:
        best_line = "None"

    if active_ppe:
        active_line = (
            f"PPE #{active_ppe.id} | {_display_class_name(active_ppe)} | "
            f"**{_format_points(active_ppe.points)} points**"
        )
    else:
        active_line = "No active PPE"

    embed = discord.Embed(
        title=f"My Info Dashboard - {user.display_name}",
        description="Everything for your PPE tracking in one place.",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Number of PPEs", value=f"**{len(player_data.ppes)}**", inline=True)
    embed.add_field(name="Best PPE", value=best_line, inline=True)
    embed.add_field(name="Number of Season Items", value=f"**{len(player_data.unique_items)}**", inline=True)
    embed.add_field(name="Current Active PPE", value=active_line, inline=False)

    help_lines = [
        "Use **/newppe** to create a new PPE.",
        "Use **/addloot** and **/addseasonloot** to log loot.",
        "Use **/removeloot** and **/removeseasonloot** to remove loot.",
        "Use **Manage Characters -> Modify PPE** to add or remove bonuses.",
        "Use **/setactiveppe** if you prefer quick switching from slash commands.",
    ]
    embed.add_field(name="How To Use The Bot", value="\n".join(help_lines), inline=False)
    embed.set_footer(text="Buttons below open actions and dashboards.")
    return embed


def _build_character_embed(
    *,
    user: discord.abc.User,
    player_data: PlayerData,
    ppe: PPEData,
    index: int,
    total: int,
    is_active: bool,
    is_realmshark_connected: bool,
) -> discord.Embed:
    character_type = _team_type_text(player_data)
    distinct_loot_items = len([loot for loot in ppe.loot if int(loot.quantity) > 0])

    title = f"PPE #{ppe.id} - {_display_class_name(ppe)}"
    embed = discord.Embed(
        title=title,
        description=(
            f"{user.display_name}'s Character Panel\\n"
            f"Character {index}/{total}"
        ),
        color=discord.Color.teal(),
    )

    embed.add_field(name="Points", value=f"**{_format_points(ppe.points)}**", inline=True)
    embed.add_field(name="RealmShark Connected", value="Yes" if is_realmshark_connected else "No", inline=True)
    embed.add_field(name="Different Loot Items", value=str(distinct_loot_items), inline=True)
    embed.add_field(name="Starting Penalty Stats", value=_penalty_stats_text(ppe), inline=False)
    embed.add_field(name="Character Type", value=character_type, inline=True)
    embed.add_field(name="Active Status", value="Active PPE" if is_active else "Not Active", inline=True)

    embed.set_footer(text="Use Show Loot, Set As Active, or Modify PPE from the buttons below.")
    return embed


async def _realmshark_connected_ppe_ids(interaction: discord.Interaction, user_id: int) -> set[int]:
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}

    connected: set[int] = set()
    for link_data in links.values():
        if not isinstance(link_data, dict):
            continue

        try:
            linked_user_id = int(link_data.get("user_id"))
        except (TypeError, ValueError):
            continue

        if linked_user_id != int(user_id):
            continue

        bindings = link_data.get("character_bindings", {})
        if not isinstance(bindings, dict):
            continue

        for raw_ppe_id in bindings.values():
            try:
                parsed = int(raw_ppe_id)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                connected.add(parsed)

    return connected


async def _send_season_loot_ephemeral_followup(interaction: discord.Interaction) -> None:
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, interaction.user.id)

    if key not in records or not records[key].is_member:
        await interaction.followup.send("❌ You're not part of the PPE contest.", ephemeral=True)
        return

    player_data = records[key]
    items_list = sorted(player_data.unique_items, key=lambda x: (x[0].lower(), x[1]))

    if not items_list:
        await interaction.followup.send(
            "You haven't collected any season loot yet!\\nUse `/addseasonloot` to start tracking your unique items.",
            ephemeral=True,
        )
        return

    lines = []
    for item_name, shiny in items_list:
        marker = " ✨" if shiny else ""
        lines.append(f"• {item_name}{marker}")
    lines.append(f"\\n**Total: {len(items_list)} unique items**")

    pages = chunk_lines_to_pages(lines, 4000)
    embeds: list[discord.Embed] = []
    for idx, page_lines in enumerate(pages, start=1):
        embed = discord.Embed(
            title="Your Season Loot Collection",
            description="\n".join(page_lines),
            color=discord.Color.gold(),
        )
        if len(pages) > 1:
            embed.set_footer(text=f"Page {idx}/{len(pages)}")
        embeds.append(embed)

    if len(embeds) == 1:
        await interaction.followup.send(embed=embeds[0], ephemeral=True)
    else:
        view = LootPaginationView(embeds=embeds, user_id=interaction.user.id)
        await interaction.followup.send(embed=embeds[0], view=view, ephemeral=True)


async def _send_myloot_markdown_followup(interaction: discord.Interaction, ppe: PPEData) -> None:
    temp_file_path = create_loot_markdown_file(ppe)
    try:
        await interaction.followup.send(file=discord.File(temp_file_path), ephemeral=True)
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


async def _temporarily_switch_active_ppe_and_share(interaction: discord.Interaction, ppe_id: int) -> None:
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, interaction.user.id)
    player_data = records[key]
    old_active = player_data.active_ppe

    if old_active == ppe_id:
        await shareloot_cmd.command(interaction, include_skins=False, include_limited=False)
        return

    player_data.active_ppe = ppe_id
    await save_player_records(interaction, records)

    try:
        await shareloot_cmd.command(interaction, include_skins=False, include_limited=False)
    finally:
        records_restore = await load_player_records(interaction)
        restore_key = ensure_player_exists(records_restore, interaction.user.id)
        records_restore[restore_key].active_ppe = old_active
        await save_player_records(interaction, records_restore)


class MyInfoHomeView(OwnerBoundView):
    def __init__(self, owner_id: int):
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")

    @discord.ui.button(label="Show Season Loot", style=discord.ButtonStyle.primary, row=0)
    async def show_season_loot(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await shareseasonloot_cmd.command(interaction, include_skins=False, include_limited=False)
        await _send_season_loot_ephemeral_followup(interaction)

    @discord.ui.button(label="Show Quests", style=discord.ButtonStyle.primary, row=0)
    async def show_quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if interaction.message:
            await interaction.message.edit(view=None)
        await myquests_cmd.command(interaction)

    @discord.ui.button(label="Manage Characters", style=discord.ButtonStyle.success, row=0)
    async def manage_characters(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        records = await load_player_records(interaction)
        key = ensure_player_exists(records, interaction.user.id)
        player_data = records[key]

        if not player_data.ppes:
            await interaction.response.send_message(
                "❌ You do not have any PPEs yet. Use `/newppe` first.",
                ephemeral=True,
            )
            return

        connected_ids = await _realmshark_connected_ppe_ids(interaction, interaction.user.id)
        view = ManageCharactersView(
            owner_id=interaction.user.id,
            player_data=player_data,
            connected_ppe_ids=connected_ids,
        )
        embed = view.current_embed(interaction.user)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=0)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/myinfo` menu.", embed=None, view=None)


class _BonusChoiceSelect(discord.ui.Select):
    def __init__(self, owner_id: int, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="Select a bonus",
            min_values=1,
            max_values=1,
            options=options[:25] if options else [discord.SelectOption(label="No options", value="")],
            disabled=not bool(options),
        )
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ModifyPPEView):
            await interaction.response.send_message("Could not update selection.", ephemeral=True)
            return

        view.selected_bonus_name = self.values[0]
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class ModifyPPEView(OwnerBoundView):
    def __init__(
        self,
        *,
        owner_id: int,
        ppe: PPEData,
        player_data: PlayerData,
        connected_ppe_ids: set[int],
        action: str = "add",
        selected_bonus_name: str | None = None,
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.ppe_id = int(ppe.id)
        self.player_data = player_data
        self.connected_ppe_ids = connected_ppe_ids
        self.action = action
        self.selected_bonus_name = selected_bonus_name

        options = self._build_options(ppe)
        self.add_item(_BonusChoiceSelect(owner_id, options))

    def _build_options(self, ppe: PPEData) -> list[discord.SelectOption]:
        if self.action == "add":
            options: list[discord.SelectOption] = []
            for bonus_name, bonus in sorted(load_bonuses().items()):
                repeat_text = "repeatable" if bonus.repeatable else "one-time"
                options.append(
                    discord.SelectOption(
                        label=bonus_name[:100],
                        value=bonus_name,
                        description=f"{bonus.points:+g} pts, {repeat_text}"[:100],
                    )
                )
            return options

        remove_counts: dict[str, int] = {}
        for bonus in ppe.bonuses:
            qty = max(1, int(getattr(bonus, "quantity", 1)))
            remove_counts[bonus.name] = remove_counts.get(bonus.name, 0) + qty

        options = []
        for bonus_name, quantity in sorted(remove_counts.items()):
            options.append(
                discord.SelectOption(
                    label=bonus_name[:100],
                    value=bonus_name,
                    description=f"Owned: {quantity}"[:100],
                )
            )
        return options

    def current_embed(self) -> discord.Embed:
        mode_name = "Add Bonus" if self.action == "add" else "Remove Bonus"
        selected_line = self.selected_bonus_name or "Nothing selected"

        embed = discord.Embed(
            title=f"Modify PPE #{self.ppe_id}",
            description=f"Mode: **{mode_name}**\\nSelected bonus: **{selected_line}**",
            color=discord.Color.orange(),
        )
        embed.add_field(
            name="How this works",
            value=(
                "1) Pick add/remove mode.\\n"
                "2) Select a bonus from the dropdown.\\n"
                "3) Click Confirm to apply and announce the update publicly."
            ),
            inline=False,
        )
        return embed

    @discord.ui.button(label="Add Mode", style=discord.ButtonStyle.success, row=1)
    async def switch_add_mode(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        refreshed = await _refresh_player_data(interaction, interaction.user.id)
        view = ModifyPPEView(
            owner_id=self.owner_id,
            ppe=_find_ppe_or_raise(refreshed, self.ppe_id),
            player_data=refreshed,
            connected_ppe_ids=self.connected_ppe_ids,
            action="add",
        )
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Remove Mode", style=discord.ButtonStyle.secondary, row=1)
    async def switch_remove_mode(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        refreshed = await _refresh_player_data(interaction, interaction.user.id)
        view = ModifyPPEView(
            owner_id=self.owner_id,
            ppe=_find_ppe_or_raise(refreshed, self.ppe_id),
            player_data=refreshed,
            connected_ppe_ids=self.connected_ppe_ids,
            action="remove",
        )
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.primary, row=1)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not self.selected_bonus_name:
            await interaction.response.send_message("Pick a bonus from the dropdown first.", ephemeral=True)
            return

        records = await load_player_records(interaction)
        key = ensure_player_exists(records, interaction.user.id)
        player_data = records[key]
        ppe = _find_ppe_or_raise(player_data, self.ppe_id)

        guild_config = await load_guild_config(interaction)

        if self.action == "add":
            available = load_bonuses()
            bonus_data = available.get(self.selected_bonus_name)
            if bonus_data is None:
                await interaction.response.send_message("Selected bonus is no longer available.", ephemeral=True)
                return

            existing = next((b for b in ppe.bonuses if b.name == self.selected_bonus_name), None)
            if existing:
                if not bonus_data.repeatable:
                    await interaction.response.send_message(
                        "That bonus already exists and is not repeatable.",
                        ephemeral=True,
                    )
                    return
                existing.quantity += 1
            else:
                ppe.bonuses.append(
                    Bonus(
                        name=bonus_data.name,
                        points=float(bonus_data.points),
                        repeatable=bool(bonus_data.repeatable),
                        quantity=1,
                    )
                )

            recompute_ppe_points(ppe, guild_config)
            await save_player_records(interaction, records)

            public_message = (
                f"✅ {interaction.user.mention} updated PPE #{ppe.id} ({_display_class_name(ppe)}): "
                f"added bonus **{self.selected_bonus_name}**. "
                f"New total: **{_format_points(ppe.points)}** points."
            )
        else:
            existing = next((b for b in ppe.bonuses if b.name.lower() == self.selected_bonus_name.lower()), None)
            if existing is None:
                await interaction.response.send_message(
                    "That bonus is not currently on this PPE.",
                    ephemeral=True,
                )
                return

            if int(existing.quantity) > 1:
                existing.quantity -= 1
            else:
                ppe.bonuses.remove(existing)

            recompute_ppe_points(ppe, guild_config)
            await save_player_records(interaction, records)

            public_message = (
                f"✅ {interaction.user.mention} updated PPE #{ppe.id} ({_display_class_name(ppe)}): "
                f"removed bonus **{self.selected_bonus_name}**. "
                f"New total: **{_format_points(ppe.points)}** points."
            )

        await interaction.response.edit_message(content="PPE updated. Menu closed.", embed=None, view=None)
        await interaction.followup.send(public_message, ephemeral=False)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        refreshed = await _refresh_player_data(interaction, interaction.user.id)
        connected_ids = await _realmshark_connected_ppe_ids(interaction, interaction.user.id)
        view = ManageCharactersView(
            owner_id=interaction.user.id,
            player_data=refreshed,
            connected_ppe_ids=connected_ids,
            preferred_ppe_id=self.ppe_id,
        )
        await interaction.response.edit_message(embed=view.current_embed(interaction.user), view=view)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/myinfo` menu.", embed=None, view=None)


class ManageCharactersView(OwnerBoundView):
    def __init__(
        self,
        *,
        owner_id: int,
        player_data: PlayerData,
        connected_ppe_ids: set[int],
        preferred_ppe_id: int | None = None,
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.player_data = player_data
        self.connected_ppe_ids = connected_ppe_ids
        self.ppes = sorted(player_data.ppes, key=lambda p: int(p.id))
        self.index = self._initial_index(preferred_ppe_id)

    def _initial_index(self, preferred_ppe_id: int | None) -> int:
        target_id = preferred_ppe_id if preferred_ppe_id is not None else self.player_data.active_ppe
        for idx, ppe in enumerate(self.ppes):
            if int(ppe.id) == int(target_id or -1):
                return idx
        return 0

    def current_ppe(self) -> PPEData:
        return self.ppes[self.index]

    def current_embed(self, user: discord.abc.User) -> discord.Embed:
        ppe = self.current_ppe()
        return _build_character_embed(
            user=user,
            player_data=self.player_data,
            ppe=ppe,
            index=self.index + 1,
            total=len(self.ppes),
            is_active=(self.player_data.active_ppe == ppe.id),
            is_realmshark_connected=(int(ppe.id) in self.connected_ppe_ids),
        )

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary, row=0)
    async def prev(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = (self.index - 1) % len(self.ppes)
        await interaction.response.edit_message(embed=self.current_embed(interaction.user), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, row=0)
    async def next(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = (self.index + 1) % len(self.ppes)
        await interaction.response.edit_message(embed=self.current_embed(interaction.user), view=self)

    @discord.ui.button(label="Show Loot", style=discord.ButtonStyle.primary, row=1)
    async def show_loot(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        selected = self.current_ppe()
        await _temporarily_switch_active_ppe_and_share(interaction, int(selected.id))
        await _send_myloot_markdown_followup(interaction, selected)

    @discord.ui.button(label="Set As Active", style=discord.ButtonStyle.success, row=1)
    async def set_as_active(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        selected = self.current_ppe()
        records = await load_player_records(interaction)
        key = ensure_player_exists(records, interaction.user.id)
        records[key].active_ppe = int(selected.id)
        await save_player_records(interaction, records)

        self.player_data.active_ppe = int(selected.id)
        await interaction.response.edit_message(embed=self.current_embed(interaction.user), view=self)

    @discord.ui.button(label="Modify PPE", style=discord.ButtonStyle.secondary, row=1)
    async def modify_ppe(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        selected = self.current_ppe()
        view = ModifyPPEView(
            owner_id=interaction.user.id,
            ppe=selected,
            player_data=self.player_data,
            connected_ppe_ids=self.connected_ppe_ids,
            action="add",
        )
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/myinfo` menu.", embed=None, view=None)


async def _refresh_player_data(interaction: discord.Interaction, user_id: int) -> PlayerData:
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, user_id)
    return records[key]


def _find_ppe_or_raise(player_data: PlayerData, ppe_id: int) -> PPEData:
    for ppe in player_data.ppes:
        if int(ppe.id) == int(ppe_id):
            return ppe
    raise LookupError(f"PPE #{ppe_id} not found.")


async def command(interaction: discord.Interaction) -> None:
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return

    records = await load_player_records(interaction)
    key = ensure_player_exists(records, interaction.user.id)
    player_data = records[key]

    if not player_data.ppes:
        await interaction.response.send_message(
            "❌ You do not have any PPEs yet. Use `/newppe` to create one first.",
            ephemeral=True,
        )
        return

    active_ppe = None
    for ppe in player_data.ppes:
        if ppe.id == player_data.active_ppe:
            active_ppe = ppe
            break

    embed = _build_home_embed(interaction.user, player_data, active_ppe)
    view = MyInfoHomeView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
