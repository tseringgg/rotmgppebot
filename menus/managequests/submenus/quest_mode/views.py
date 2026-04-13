"""Quest mode submenu views for /managequests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import time
import traceback

import discord

from menus.managequests.common import (
    build_quest_mode_embed,
    ensure_team_quests_state,
    load_managequests_settings,
)
from menus.managequests.services import (
    apply_settings_to_players,
    clear_active_quests_for_all_members,
    migrate_team_completed_to_members_on_disable,
    save_settings,
)
from menus.menu_utils import ConfirmCancelView, OwnerBoundView
from utils.player_records import load_player_records, load_teams, save_player_records


class QuestModeView(OwnerBoundView):
    """Owner-bound quest mode manager with global/team mode controls."""

    def __init__(self, *, owner_id: int, settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings
        self._rebuild_controls()

    def current_embed(self) -> discord.Embed:
        return build_quest_mode_embed(self.settings)

    def _add_button(
        self,
        *,
        label: str,
        style: discord.ButtonStyle,
        row: int,
        handler: Callable[[discord.Interaction], Awaitable[None]],
        disabled: bool = False,
    ) -> None:
        button = discord.ui.Button(label=label, style=style, row=row, disabled=disabled)

        async def _callback(interaction: discord.Interaction) -> None:
            await handler(interaction)

        button.callback = _callback
        self.add_item(button)

    def _rebuild_controls(self) -> None:
        self.clear_items()
        global_enabled = bool(self.settings.get("use_global_quests", False))
        team_enabled = bool(self.settings.get("enable_team_quests", False))

        self._add_button(
            label="Disable Global Quests" if global_enabled else "Enable Global Quests",
            style=discord.ButtonStyle.danger if global_enabled else discord.ButtonStyle.success,
            row=0,
            handler=self._toggle_global_quests,
        )
        if global_enabled:
            self._add_button(
                label="Configure Global Quests",
                style=discord.ButtonStyle.primary,
                row=0,
                handler=self._configure_global_quests,
            )

        self._add_button(
            label="Disable Team Quests" if team_enabled else "Enable Team Quests",
            style=discord.ButtonStyle.danger if team_enabled else discord.ButtonStyle.success,
            row=1,
            handler=self._toggle_team_quests,
            disabled=global_enabled,
        )
        if team_enabled and not global_enabled:
            self._add_button(
                label="Reset Team's Quests",
                style=discord.ButtonStyle.danger,
                row=1,
                handler=self._reset_team_quests,
            )
        self._add_button(label="Back", style=discord.ButtonStyle.secondary, row=2, handler=self._back)

    async def _confirm_disable_action(self, interaction: discord.Interaction, *, message: str) -> bool:
        view = ConfirmCancelView(
            owner_id=self.owner_id,
            timeout=60,
            confirm_label="Confirm Disable",
            cancel_label="Cancel",
            confirm_style=discord.ButtonStyle.danger,
            cancel_style=discord.ButtonStyle.secondary,
            owner_error="This confirmation belongs to another user.",
        )
        await interaction.response.send_message(message, view=view, ephemeral=True)
        await view.wait()

        # Close the ephemeral confirmation prompt after a decision/timeout.
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass

        if not view.confirmed:
            await interaction.followup.send("❌ Action cancelled.", ephemeral=True)
            return False
        return True

    async def _edit_main_panel(self, interaction: discord.Interaction) -> None:
        """Edit the main quest-mode panel whether or not this interaction was already acknowledged."""
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=self.current_embed(), view=self)
            return

        if interaction.message is not None:
            try:
                await interaction.message.edit(embed=self.current_embed(), view=self)
                return
            except discord.NotFound:
                # Ephemeral-origin messages can be unavailable via channel edit routes.
                pass
            except discord.HTTPException:
                pass

        await interaction.followup.send(embed=self.current_embed(), view=self, ephemeral=True)

    async def _send_action_error(self, interaction: discord.Interaction, *, action: str, exc: Exception) -> None:
        error_ref = f"qm-{int(time.time())}"
        print(f"[ERROR][{error_ref}] QuestModeView action '{action}' failed: {exc}")
        print(traceback.format_exc())

        message = (
            f"❌ {action} failed. Error reference: **{error_ref}**.\n"
            "Please check deploy logs and search for this reference."
        )
        if not interaction.response.is_done():
            await interaction.response.send_message(message, ephemeral=True)
            return
        await interaction.followup.send(message, ephemeral=True)

    async def _toggle_global_quests(self, interaction: discord.Interaction) -> None:
        try:
            settings = await load_managequests_settings(interaction)
            current = bool(settings.get("use_global_quests", False))

            if current:
                confirmed = await self._confirm_disable_action(
                    interaction,
                    message=(
                        "⚠️ Disabling Global Quests will reset shared quest mode data.\n"
                        "- Global quest pools will be cleared\n"
                        "- Team shared quest state will be cleared\n"
                        "- Player active quests will be rerolled\n"
                        "Continue?"
                    ),
                )
                if not confirmed:
                    return

            settings["use_global_quests"] = not current
            if settings["use_global_quests"]:
                # Global mode takes precedence; team mode must be off.
                settings["enable_team_quests"] = False
                settings["team_quests_state"] = {}
            else:
                settings["global_regular_quests"] = []
                settings["global_shiny_quests"] = []
                settings["global_skin_quests"] = []
                settings["team_quests_state"] = {}

                # Leaving global mode should force rerolls by clearing active personal quests.
                records = await load_player_records(interaction)
                cleared_players, _ = clear_active_quests_for_all_members(records)
                if cleared_players > 0:
                    await save_player_records(interaction, records)

            await save_settings(interaction, settings)
            players_adjusted, active_removed, _ = await apply_settings_to_players(interaction, settings=settings)

            self.settings = settings
            self._rebuild_controls()

            await self._edit_main_panel(interaction)
            await interaction.followup.send(
                (
                    f"✅ Global quests **{'enabled' if settings['use_global_quests'] else 'disabled'}**.\n"
                    f"Players adjusted: **{players_adjusted}**\n"
                    f"Active entries removed: **{active_removed}**"
                ),
                ephemeral=False,
            )
        except Exception as exc:
            await self._send_action_error(interaction, action="Toggle Global Quests", exc=exc)

    async def _configure_global_quests(self, interaction: discord.Interaction) -> None:
        from menus.managequests.submenus.global_quests.views import GlobalQuestsView

        settings = await load_managequests_settings(interaction)
        view = GlobalQuestsView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    async def _toggle_team_quests(self, interaction: discord.Interaction) -> None:
        try:
            settings = await load_managequests_settings(interaction)

            if bool(settings.get("use_global_quests", False)):
                await interaction.response.send_message(
                    "❌ Disable Global Quests first. Global mode always takes precedence over team mode.",
                    ephemeral=True,
                )
                return

            current = bool(settings.get("enable_team_quests", False))

            if current:
                confirmed = await self._confirm_disable_action(
                    interaction,
                    message=(
                        "⚠️ Disabling Team Quests will reset shared quest mode data.\n"
                        "- Team shared quest state will be cleared\n"
                        "- Team active quests will be rerolled for players\n"
                        "Continue?"
                    ),
                )
                if not confirmed:
                    return

            settings["enable_team_quests"] = not current

            migrated_players = 0
            migrated_entries = 0
            cleared_players = 0
            cleared_entries = 0
            if current and not settings["enable_team_quests"]:
                migrated_players, migrated_entries = await migrate_team_completed_to_members_on_disable(
                    interaction,
                    settings=settings,
                )
                records = await load_player_records(interaction)
                cleared_players, cleared_entries = clear_active_quests_for_all_members(records)
                if cleared_players > 0:
                    await save_player_records(interaction, records)
                settings["team_quests_state"] = {}
            else:
                ensure_team_quests_state(settings)

            await save_settings(interaction, settings)
            players_adjusted, active_removed, _ = await apply_settings_to_players(interaction, settings=settings)

            self.settings = settings
            self._rebuild_controls()

            await self._edit_main_panel(interaction)
            await interaction.followup.send(
                (
                    f"✅ Team quests **{'enabled' if settings['enable_team_quests'] else 'disabled'}**.\n"
                    + (
                        f"Members migrated to personal completed quests: **{migrated_players}**\n"
                        f"Matched completed entries copied: **{migrated_entries}**\n"
                        f"Players with active quests rerolled: **{cleared_players}**\n"
                        f"Active team quest entries cleared: **{cleared_entries}**\n"
                        if current and not settings["enable_team_quests"]
                        else ""
                    )
                    +
                    f"Players adjusted: **{players_adjusted}**\n"
                    f"Active entries removed: **{active_removed}**"
                ),
                ephemeral=False,
            )
        except Exception as exc:
            await self._send_action_error(interaction, action="Toggle Team Quests", exc=exc)

    async def _reset_team_quests(self, interaction: discord.Interaction) -> None:
        try:
            from menus.managequests.submenus.player_reset.views import ManageTeamQuestsSelectView

            teams = await load_teams(interaction)
            view = ManageTeamQuestsSelectView(owner_id=self.owner_id, team_names=list(teams.keys()))
            await interaction.response.send_message(embed=view.current_embed(), view=view, ephemeral=True)
        except Exception as exc:
            await self._send_action_error(interaction, action="Open Reset Team Quests", exc=exc)

    async def _back(self, interaction: discord.Interaction) -> None:
        from menus.managequests.submenus.home.views import ManageQuestsHomeView

        settings = await load_managequests_settings(interaction)
        view = ManageQuestsHomeView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    async def on_timeout(self) -> None:
        return await super().on_timeout()


__all__ = ["QuestModeView"]
