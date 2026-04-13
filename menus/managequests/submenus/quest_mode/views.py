"""Quest mode submenu views for /managequests."""

from __future__ import annotations

import discord

from menus.managequests.common import (
    build_quest_mode_embed,
    ensure_team_quests_state,
    load_managequests_settings,
)
from menus.managequests.services import apply_settings_to_players, migrate_team_completed_to_members_on_disable, save_settings
from menus.menu_utils import ConfirmCancelView, OwnerBoundView


class QuestModeView(OwnerBoundView):
    """Owner-bound quest mode manager with global/team mode controls."""

    def __init__(self, *, owner_id: int, settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings
        self._sync_labels()

    def current_embed(self) -> discord.Embed:
        return build_quest_mode_embed(self.settings)

    def _sync_labels(self) -> None:
        global_enabled = bool(self.settings.get("use_global_quests", False))
        team_enabled = bool(self.settings.get("enable_team_quests", False))

        self.toggle_global_quests.label = "Disable Global Quests" if global_enabled else "Enable Global Quests"
        self.toggle_team_quests.label = "Disable Team Quests" if team_enabled else "Enable Team Quests"
        self.toggle_team_quests.disabled = global_enabled

    @discord.ui.button(label="Enable Global Quests", style=discord.ButtonStyle.success, row=0)
    async def toggle_global_quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await load_managequests_settings(interaction)
        current = bool(settings.get("use_global_quests", False))
        settings["use_global_quests"] = not current
        if settings["use_global_quests"]:
            # Global mode takes precedence; team mode must be off.
            settings["enable_team_quests"] = False

        await save_settings(interaction, settings)
        players_adjusted, active_removed, _ = await apply_settings_to_players(interaction, settings=settings)

        self.settings = settings
        self._sync_labels()

        await interaction.response.edit_message(embed=self.current_embed(), view=self)
        await interaction.followup.send(
            (
                f"✅ Global quests **{'enabled' if settings['use_global_quests'] else 'disabled'}**.\n"
                f"Players adjusted: **{players_adjusted}**\n"
                f"Active entries removed: **{active_removed}**"
            ),
            ephemeral=False,
        )

    @discord.ui.button(label="Configure Global Quests", style=discord.ButtonStyle.primary, row=0)
    async def configure_global_quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.managequests.submenus.global_quests.views import GlobalQuestsView

        settings = await load_managequests_settings(interaction)
        view = GlobalQuestsView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Enable Team Quests", style=discord.ButtonStyle.success, row=1)
    async def toggle_team_quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await load_managequests_settings(interaction)

        if bool(settings.get("use_global_quests", False)):
            await interaction.response.send_message(
                "❌ Disable Global Quests first. Global mode always takes precedence over team mode.",
                ephemeral=True,
            )
            return

        current = bool(settings.get("enable_team_quests", False))
        settings["enable_team_quests"] = not current
        ensure_team_quests_state(settings)

        migrated_players = 0
        migrated_entries = 0
        if current and not settings["enable_team_quests"]:
            migrated_players, migrated_entries = await migrate_team_completed_to_members_on_disable(
                interaction,
                settings=settings,
            )

        await save_settings(interaction, settings)
        players_adjusted, active_removed, _ = await apply_settings_to_players(interaction, settings=settings)

        self.settings = settings
        self._sync_labels()

        await interaction.response.edit_message(embed=self.current_embed(), view=self)
        await interaction.followup.send(
            (
                f"✅ Team quests **{'enabled' if settings['enable_team_quests'] else 'disabled'}**.\n"
                + (
                    f"Members migrated to personal completed quests: **{migrated_players}**\n"
                    f"Matched completed entries copied: **{migrated_entries}**\n"
                    if current and not settings["enable_team_quests"]
                    else ""
                )
                +
                f"Players adjusted: **{players_adjusted}**\n"
                f"Active entries removed: **{active_removed}**"
            ),
            ephemeral=False,
        )

    @discord.ui.button(label="Clear Team Quest State", style=discord.ButtonStyle.danger, row=1)
    async def clear_team_state(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        view = ConfirmCancelView(
            owner_id=self.owner_id,
            timeout=60,
            confirm_label="Confirm Clear",
            cancel_label="Cancel",
            confirm_style=discord.ButtonStyle.danger,
            cancel_style=discord.ButtonStyle.secondary,
            owner_error="This confirmation belongs to another user.",
        )
        await interaction.response.send_message(
            "⚠️ Clear all saved shared team quest progress for this server?",
            view=view,
            ephemeral=True,
        )
        await view.wait()
        if not view.confirmed:
            await interaction.followup.send("❌ Action cancelled.", ephemeral=True)
            return

        settings = await load_managequests_settings(interaction)
        settings["team_quests_state"] = {}
        await save_settings(interaction, settings)
        self.settings = settings
        self._sync_labels()

        if interaction.message is not None:
            try:
                await interaction.message.edit(embed=self.current_embed(), view=self)
            except discord.HTTPException:
                pass

        await interaction.followup.send("✅ Cleared all team shared quest state.", ephemeral=True)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.managequests.submenus.home.views import ManageQuestsHomeView

        settings = await load_managequests_settings(interaction)
        view = ManageQuestsHomeView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    async def on_timeout(self) -> None:
        return await super().on_timeout()


__all__ = ["QuestModeView"]
