"""Interactive views for the /managequests admin menu."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import re

import discord

from menus.managequests.common import build_global_quests_embed, build_managequests_home_embed, load_managequests_settings
from menus.managequests.modals import AddGlobalQuestItemsModal, EditQuestSettingsModal, RemoveGlobalQuestItemsModal
from menus.managequests.services import apply_settings_to_players, clear_all_quests_and_global_pools, save_settings
from menus.menu_utils import ConfirmCancelView, OwnerBoundView
from menus.myquests.common import build_myquests_state_for_player
from menus.myquests.view import MyQuestsView


class GlobalQuestsView(OwnerBoundView):
    """Owner-bound global quest manager with dynamic controls by global-mode state."""

    def __init__(self, *, owner_id: int, settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings
        self._rebuild_controls()

    def current_embed(self) -> discord.Embed:
        return build_global_quests_embed(self.settings)

    def _add_button(
        self,
        *,
        label: str,
        style: discord.ButtonStyle,
        row: int,
        handler: Callable[[discord.Interaction], Awaitable[None]],
    ) -> None:
        button = discord.ui.Button(label=label, style=style, row=row)

        async def _callback(interaction: discord.Interaction) -> None:
            await handler(interaction)

        button.callback = _callback
        self.add_item(button)

    def _rebuild_controls(self) -> None:
        self.clear_items()
        enabled = bool(self.settings.get("use_global_quests", False))

        if not enabled:
            self._add_button(
                label="Enable Global Quests",
                style=discord.ButtonStyle.success,
                row=0,
                handler=self._enable_global_quests,
            )
            self._add_button(label="Back", style=discord.ButtonStyle.secondary, row=0, handler=self._back)
            return

        self._add_button(label="Add Regular Quest", style=discord.ButtonStyle.primary, row=0, handler=self._add_regular)
        self._add_button(label="Add Shiny Quest", style=discord.ButtonStyle.primary, row=0, handler=self._add_shiny)
        self._add_button(label="Add Skin Quest", style=discord.ButtonStyle.primary, row=0, handler=self._add_skin)

        self._add_button(label="Remove Regular Quest", style=discord.ButtonStyle.danger, row=1, handler=self._remove_regular)
        self._add_button(label="Remove Shiny Quest", style=discord.ButtonStyle.danger, row=1, handler=self._remove_shiny)
        self._add_button(label="Remove Skin Quest", style=discord.ButtonStyle.danger, row=1, handler=self._remove_skin)

        self._add_button(label="Remove All Quests", style=discord.ButtonStyle.danger, row=2, handler=self._remove_all)
        self._add_button(label="Disable Global Quests", style=discord.ButtonStyle.danger, row=2, handler=self._disable_global)
        self._add_button(label="Back", style=discord.ButtonStyle.secondary, row=2, handler=self._back)

    async def _enable_global_quests(self, interaction: discord.Interaction) -> None:
        settings = await load_managequests_settings(interaction)
        settings["use_global_quests"] = True
        await save_settings(interaction, settings)

        players_adjusted, active_removed, _ = await apply_settings_to_players(interaction, settings=settings)
        self.settings = settings
        self._rebuild_controls()

        await interaction.response.edit_message(embed=self.current_embed(), view=self)
        await interaction.followup.send(
            (
                f"✅ Global quests enabled by **{interaction.user.display_name}**.\n"
                f"Players adjusted: **{players_adjusted}**\n"
                f"Active entries removed: **{active_removed}**"
            ),
            ephemeral=False,
        )

    async def _confirm_action(
        self,
        interaction: discord.Interaction,
        *,
        message: str,
        confirm_label: str,
    ) -> bool:
        view = ConfirmCancelView(
            owner_id=self.owner_id,
            timeout=60,
            confirm_label=confirm_label,
            cancel_label="Cancel",
            confirm_style=discord.ButtonStyle.danger,
            cancel_style=discord.ButtonStyle.secondary,
            owner_error="This confirmation belongs to another user.",
        )
        await interaction.response.send_message(message, view=view, ephemeral=True)
        await view.wait()
        if not view.confirmed:
            await interaction.followup.send("❌ Action cancelled.", ephemeral=True)
            return False
        return True

    async def _add_regular(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            AddGlobalQuestItemsModal(owner_id=self.owner_id, category="regular", source_message=interaction.message)
        )

    async def _add_shiny(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            AddGlobalQuestItemsModal(owner_id=self.owner_id, category="shiny", source_message=interaction.message)
        )

    async def _add_skin(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            AddGlobalQuestItemsModal(owner_id=self.owner_id, category="skin", source_message=interaction.message)
        )

    async def _remove_regular(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            RemoveGlobalQuestItemsModal(owner_id=self.owner_id, category="regular", source_message=interaction.message)
        )

    async def _remove_shiny(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            RemoveGlobalQuestItemsModal(owner_id=self.owner_id, category="shiny", source_message=interaction.message)
        )

    async def _remove_skin(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            RemoveGlobalQuestItemsModal(owner_id=self.owner_id, category="skin", source_message=interaction.message)
        )

    async def _remove_all(self, interaction: discord.Interaction) -> None:
        confirmed = await self._confirm_action(
            interaction,
            message=(
                "⚠️ **Remove all global quests?**\n"
                "This will remove all global quest pools and clear current/completed quests for every player."
            ),
            confirm_label="Confirm Remove All",
        )
        if not confirmed:
            return

        settings, players_updated, entries_cleared = await clear_all_quests_and_global_pools(
            interaction,
            refill_random_quests=False,
            disable_global_mode=False,
        )
        self.settings = settings
        self._rebuild_controls()

        if interaction.message is not None:
            try:
                await interaction.message.edit(embed=self.current_embed(), view=self)
            except discord.HTTPException:
                pass

        await interaction.followup.send(
            (
                "✅ Removed all global quests and cleared player quest data.\n"
                f"Players updated: **{players_updated}**\n"
                f"Quest entries cleared: **{entries_cleared}**"
            ),
            ephemeral=True,
        )

    async def _disable_global(self, interaction: discord.Interaction) -> None:
        confirmed = await self._confirm_action(
            interaction,
            message=(
                "⚠️ **Disable global quests?**\n"
                "This will clear all global quest pools and switch players back to random quests.\n"
                "Completed quests will be preserved."
            ),
            confirm_label="Confirm Disable",
        )
        if not confirmed:
            return

        settings = await load_managequests_settings(interaction)
        settings["global_regular_quests"] = []
        settings["global_shiny_quests"] = []
        settings["global_skin_quests"] = []
        settings["use_global_quests"] = False
        await save_settings(interaction, settings)
        players_updated, active_removed, _ = await apply_settings_to_players(interaction, settings=settings)
        self.settings = settings
        self._rebuild_controls()

        if interaction.message is not None:
            try:
                await interaction.message.edit(embed=self.current_embed(), view=self)
            except discord.HTTPException:
                pass

        await interaction.followup.send(
            (
                f"✅ Global quests disabled by **{interaction.user.display_name}**.\n"
                "Cleared all global quest pools and switched players to random quests.\n"
                f"Players updated: **{players_updated}**\n"
                f"Active entries removed: **{active_removed}**"
            ),
            ephemeral=False,
        )

    async def _back(self, interaction: discord.Interaction) -> None:
        settings = await load_managequests_settings(interaction)
        view = ManageQuestsHomeView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class ManageQuestsHomeView(OwnerBoundView):
    """Top-level /managequests admin controls."""

    def __init__(self, *, owner_id: int, settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings

    def current_embed(self) -> discord.Embed:
        return build_managequests_home_embed(self.settings)

    @discord.ui.button(label="Reset All Quests", style=discord.ButtonStyle.danger, row=0)
    async def reset_all(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from slash_commands import resetquests_cmd

        await resetquests_cmd.command(interaction)

    @discord.ui.button(label="Edit Quest Settings", style=discord.ButtonStyle.primary, row=0)
    async def edit_settings(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_managequests_settings(interaction)
        await interaction.response.send_modal(
            EditQuestSettingsModal(owner_id=self.owner_id, settings=self.settings, source_message=interaction.message)
        )

    @discord.ui.button(label="Set Global Quests", style=discord.ButtonStyle.success, row=0)
    async def set_global_quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await load_managequests_settings(interaction)
        view = GlobalQuestsView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Manage Player's Quests", style=discord.ButtonStyle.success, row=1)
    async def manage_player_quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(
            ManagePlayerQuestsPromptModal(owner_id=self.owner_id, source_message=interaction.message)
        )

    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary, row=1)
    async def close(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/managequests` menu.", embed=None, view=None)


class ManagePlayerQuestsPromptModal(discord.ui.Modal, title="Manage Player's Quests"):
    player_name = discord.ui.TextInput(
        label="Player Name",
        placeholder="Discord display name, username, mention, or ID",
        max_length=100,
    )

    def __init__(self, *, owner_id: int, source_message: discord.Message | None) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        if not interaction.guild:
            await interaction.response.send_message("❌ This action can only be used in a server.", ephemeral=True)
            return

        raw = str(self.player_name.value).strip()
        target = self._resolve_member(interaction.guild, raw)
        if target is None:
            await interaction.response.send_message(
                "❌ Player not found. Use exact display name/username, mention, or user ID.",
                ephemeral=True,
            )
            return

        if self.source_message is not None:
            view = ManagePlayerQuestsView(owner_id=self.owner_id, member=target)
            try:
                await self.source_message.edit(embed=view.current_embed(), view=view)
            except discord.HTTPException:
                pass

        await interaction.response.send_message(
            f"Opened quest manager for **{target.display_name}**.",
            ephemeral=True,
        )

    @staticmethod
    def _resolve_member(guild: discord.Guild, raw_value: str) -> discord.Member | None:
        if not raw_value:
            return None

        mention_match = re.fullmatch(r"<@!?(\d+)>", raw_value)
        if mention_match:
            member = guild.get_member(int(mention_match.group(1)))
            if member is not None:
                return member

        if raw_value.isdigit():
            member = guild.get_member(int(raw_value))
            if member is not None:
                return member

        lowered = raw_value.casefold()
        for member in guild.members:
            if member.display_name.casefold() == lowered or member.name.casefold() == lowered:
                return member
        return None


class ManagePlayerQuestsView(OwnerBoundView):
    """Targeted quest management actions for a specific player from /managequests."""

    def __init__(self, *, owner_id: int, member: discord.Member) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.member = member

    def current_embed(self) -> discord.Embed:
        return discord.Embed(
            title=f"Manage Player Quests - {self.member.display_name}",
            description=(
                "Use **Reset Quests** to run the admin reset flow for this player, "
                "or **Show Quests** to open their quest panel."
            ),
            color=discord.Color.dark_teal(),
        )

    @discord.ui.button(label="Reset Quests", style=discord.ButtonStyle.danger, row=0)
    async def reset_quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from slash_commands import resetquestfor_cmd

        await resetquestfor_cmd.command(interaction, self.member)

    @discord.ui.button(label="Show Quests", style=discord.ButtonStyle.primary, row=0)
    async def show_quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        async def _show_target_reset_for_member(reset_interaction: discord.Interaction) -> None:
            from slash_commands import resetquestfor_cmd

            await resetquestfor_cmd.command(reset_interaction, self.member)

        state = await build_myquests_state_for_player(
            interaction,
            player_id=self.member.id,
            display_name=self.member.display_name,
            not_in_contest_message=f"❌ {self.member.display_name} is not part of the PPE contest.",
        )
        view = MyQuestsView(
            owner_id=interaction.user.id,
            display_name=state["display_name"],
            home_embed=state["home_embed"],
            current_regular=state["current_regular"],
            current_shiny=state["current_shiny"],
            current_skin=state["current_skin"],
            current_all=state["current_all"],
            completed_embed=state["completed_embed"],
            global_mode_enabled=state["global_mode_enabled"],
            reset_callback=_show_target_reset_for_member,
        )
        await interaction.response.edit_message(embed=state["home_embed"], view=view, attachments=[])

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await load_managequests_settings(interaction)
        view = ManageQuestsHomeView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary, row=1)
    async def close(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/managequests` menu.", embed=None, view=None)
