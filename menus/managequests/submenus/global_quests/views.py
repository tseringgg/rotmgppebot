"""Global quests submenu views for /managequests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import discord

from menus.managequests.common import build_global_quests_embed, load_managequests_settings
from menus.managequests.modals import AddGlobalQuestItemsModal, RemoveGlobalQuestItemsModal
from menus.managequests.services import apply_settings_to_players, clear_all_quests_and_global_pools, save_settings
from menus.menu_utils import ConfirmCancelView, OwnerBoundView


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
        from menus.managequests.submenus.home.views import ManageQuestsHomeView
        
        settings = await load_managequests_settings(interaction)
        view = ManageQuestsHomeView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


__all__ = ["GlobalQuestsView"]
