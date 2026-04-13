"""Reset submenu views for /manageseason."""

from __future__ import annotations

import discord

from menus.manageseason.services import (
    ResetSnifferOptions,
    clear_join_embed_information,
    delete_ppe_and_team_roles,
    load_contest_settings_for_menu,
    remove_ppe_admin_role_from_everyone,
    remove_ppe_player_role_from_everyone,
    reset_admin_tunable_settings_to_defaults,
    reset_all_ppe_characters,
    reset_all_quests,
    reset_all_seasonal_information,
    reset_all_teams,
    reset_sniffer_data,
)
from menus.menu_utils import ConfirmCancelView, OwnerBoundView


_RESET_SEQUENCE: tuple[tuple[str, str, str], ...] = (
    (
        "reset_ppe_characters",
        "Reset PPE Characters",
        "Removes all PPE characters and per-character loot while preserving seasonal and quest progress.",
    ),
    (
        "reset_seasonal_information",
        "Reset Seasonal Information",
        "Clears seasonal uniques and season-wide progression data for everyone.",
    ),
    (
        "reset_teams",
        "Reset Teams",
        "Clears team assignments, deletes team records, and removes matching team roles.",
    ),
    (
        "reset_sniffer_information",
        "Reset Sniffer Information",
        "Opens sniffer reset options so you can choose exactly what to clear.",
    ),
    (
        "reset_quests",
        "Reset Quests",
        "Clears quest progress and restores each player's quest reset counter.",
    ),
    (
        "reset_settings",
        "Reset Settings to Defaults",
        "Resets admin-tunable settings to defaults while preserving sniffer endpoint and join embed message settings.",
    ),
    (
        "player_role_join_embed",
        "PPE Player Role / Join Embed",
        "Opens options to remove all PPE Players and/or clear join embed references.",
    ),
    (
        "remove_admin_roles",
        "Remove PPE Admin Roles",
        "Removes PPE Admin role from all members.",
    ),
    (
        "delete_role_objects",
        "Delete PPE/Team Role Objects",
        "Deletes PPE Admin, PPE Player, and known team roles if they still exist.",
    ),
)


def _max_step_index() -> int:
    return len(_RESET_SEQUENCE) - 1


def _clamp_step(step_index: int) -> int:
    return max(0, min(_max_step_index(), int(step_index)))


def _build_sequence_step_embed(step_index: int) -> discord.Embed:
    safe_index = _clamp_step(step_index)
    key, title, summary = _RESET_SEQUENCE[safe_index]

    embed = discord.Embed(
        title=f"Reset Season - Step {safe_index + 1}/{len(_RESET_SEQUENCE)}",
        description=f"**{title}**",
        color=discord.Color.orange(),
    )
    embed.add_field(name="Summary", value=summary, inline=False)

    if key == "reset_sniffer_information":
        embed.add_field(
            name="How This Step Works",
            value=(
                "Use the Sniffer options panel to choose exactly what to reset. "
                "After running it, the sequence auto-continues to the next step."
            ),
            inline=False,
        )
    elif key == "player_role_join_embed":
        embed.add_field(
            name="How This Step Works",
            value=(
                "Open the role/join-embed panel, pick one action, then the sequence continues."
            ),
            inline=False,
        )

    embed.set_footer(text="Each step requires confirmation before execution.")
    return embed


def _build_sniffer_reset_embed(options: ResetSnifferOptions) -> discord.Embed:
    def _state(flag: bool) -> str:
        return "ON" if flag else "OFF"

    embed = discord.Embed(
        title="Reset Sniffer Information",
        description="Toggle the exact sniffer reset actions you want, then run reset.",
        color=discord.Color.orange(),
    )
    embed.add_field(
        name="Current Selection",
        value=(
            f"- Clear character mappings: **{_state(options.clear_character_mappings)}**\n"
            f"- Revoke all tokens: **{_state(options.revoke_tokens)}**\n"
            f"- Clear pending files: **{_state(options.clear_pending_files)}**\n"
            f"- Clear output channel: **{_state(options.clear_output_channel)}**\n"
            f"- Clear endpoint: **{_state(options.clear_endpoint)}**\n"
            f"- Disable sniffer: **{_state(options.disable_sniffer)}**"
        ),
        inline=False,
    )
    embed.add_field(
        name="Notes",
        value=(
            "- Pending file cleanup is ON by default.\n"
            "- When Revoke all tokens is OFF, player tokens are preserved.\n"
            "- When Clear endpoint is ON, the configured sniffer endpoint is removed."
        ),
        inline=False,
    )
    return embed


def _build_player_role_join_embed_embed(*, join_embed_configured: bool) -> discord.Embed:
    status_text = "Configured" if join_embed_configured else "Not configured"
    embed = discord.Embed(
        title="PPE Player Role / Join Embed",
        description="Choose how to handle PPE Player role assignments and join embed references.",
        color=discord.Color.orange(),
    )
    embed.add_field(
        name="Join Embed Status",
        value=f"Current join embed: **{status_text}**",
        inline=False,
    )
    embed.add_field(
        name="Available Actions",
        value=(
            "- Remove PPE Player role from everyone.\n"
            "- If join embed is configured, clear join embed info only.\n"
            "- If join embed is configured, clear both in one action."
        ),
        inline=False,
    )
    embed.add_field(
        name="Important Note",
        value=(
            "Removing all PPE Players also revokes all sniffer tokens and fully clears the stored player loot records file."
        ),
        inline=False,
    )
    return embed


async def _ask_confirmation(
    interaction: discord.Interaction,
    *,
    owner_id: int,
    warning_text: str,
    confirm_label: str = "Confirm",
) -> bool:
    confirm_view = ConfirmCancelView(
        owner_id=owner_id,
        timeout=60,
        confirm_label=confirm_label,
        cancel_label="Cancel",
        confirm_style=discord.ButtonStyle.danger,
        cancel_style=discord.ButtonStyle.secondary,
        owner_error="This confirmation belongs to another user.",
    )

    await interaction.response.send_message(warning_text, view=confirm_view, ephemeral=True)
    await confirm_view.wait()

    try:
        await interaction.delete_original_response()
    except discord.HTTPException:
        pass

    return bool(confirm_view.confirmed)


async def _show_sequence_step_on_message(
    message: discord.Message | None,
    *,
    owner_id: int,
    step_index: int,
    interaction: discord.Interaction | None = None,
) -> None:
    next_view = ResetSeasonActionsView(owner_id=owner_id, step_index=step_index)

    if message is not None:
        try:
            await message.edit(embed=next_view.current_embed(), view=next_view)
            return
        except discord.HTTPException:
            pass

    if interaction is not None:
        try:
            await interaction.followup.send(embed=next_view.current_embed(), view=next_view, ephemeral=True)
        except discord.HTTPException:
            pass


class ResetSnifferOptionsView(OwnerBoundView):
    """Sniffer reset options submenu with toggleable actions."""

    def __init__(self, *, owner_id: int, next_step_index: int, options: ResetSnifferOptions | None = None) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.next_step_index = _clamp_step(next_step_index)
        self.options = options if isinstance(options, ResetSnifferOptions) else ResetSnifferOptions()
        self._refresh_labels()

    def _refresh_labels(self) -> None:
        self.toggle_character_mappings.label = f"Mappings: {'ON' if self.options.clear_character_mappings else 'OFF'}"
        self.toggle_revoke_tokens.label = f"Revoke Tokens: {'ON' if self.options.revoke_tokens else 'OFF'}"
        self.toggle_pending_files.label = f"Clear Pending: {'ON' if self.options.clear_pending_files else 'OFF'}"
        self.toggle_output_channel.label = f"Clear Output: {'ON' if self.options.clear_output_channel else 'OFF'}"
        self.toggle_endpoint.label = f"Clear Endpoint: {'ON' if self.options.clear_endpoint else 'OFF'}"
        self.toggle_disable_sniffer.label = f"Disable Sniffer: {'ON' if self.options.disable_sniffer else 'OFF'}"

    def current_embed(self) -> discord.Embed:
        return _build_sniffer_reset_embed(self.options)

    async def _refresh_message(self, interaction: discord.Interaction) -> None:
        self._refresh_labels()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    async def _continue_sequence(self, interaction: discord.Interaction) -> None:
        await _show_sequence_step_on_message(
            interaction.message,
            owner_id=self.owner_id,
            step_index=self.next_step_index,
            interaction=interaction,
        )

    @discord.ui.button(label="Mappings: ON", style=discord.ButtonStyle.primary, row=0)
    async def toggle_character_mappings(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.options.clear_character_mappings = not self.options.clear_character_mappings
        await self._refresh_message(interaction)

    @discord.ui.button(label="Revoke Tokens: OFF", style=discord.ButtonStyle.primary, row=0)
    async def toggle_revoke_tokens(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.options.revoke_tokens = not self.options.revoke_tokens
        await self._refresh_message(interaction)

    @discord.ui.button(label="Clear Pending: ON", style=discord.ButtonStyle.primary, row=1)
    async def toggle_pending_files(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.options.clear_pending_files = not self.options.clear_pending_files
        await self._refresh_message(interaction)

    @discord.ui.button(label="Clear Output: OFF", style=discord.ButtonStyle.primary, row=1)
    async def toggle_output_channel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.options.clear_output_channel = not self.options.clear_output_channel
        await self._refresh_message(interaction)

    @discord.ui.button(label="Clear Endpoint: OFF", style=discord.ButtonStyle.primary, row=2)
    async def toggle_endpoint(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.options.clear_endpoint = not self.options.clear_endpoint
        await self._refresh_message(interaction)

    @discord.ui.button(label="Disable Sniffer: OFF", style=discord.ButtonStyle.primary, row=2)
    async def toggle_disable_sniffer(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.options.disable_sniffer = not self.options.disable_sniffer
        await self._refresh_message(interaction)

    @discord.ui.button(label="Run Sniffer Reset", style=discord.ButtonStyle.danger, row=3)
    async def run_reset(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        selected_count = sum(
            [
                bool(self.options.clear_character_mappings),
                bool(self.options.revoke_tokens),
                bool(self.options.clear_pending_files),
                bool(self.options.clear_output_channel),
                bool(self.options.clear_endpoint),
                bool(self.options.disable_sniffer),
            ]
        )
        if selected_count == 0:
            await interaction.response.send_message("Select at least one sniffer reset option first.", ephemeral=True)
            return

        confirmed = await _ask_confirmation(
            interaction,
            owner_id=self.owner_id,
            warning_text=(
                "WARNING: Run the selected sniffer reset actions?\n"
                "Only the options currently toggled ON will be applied."
            ),
            confirm_label="Confirm Sniffer Reset",
        )
        if not confirmed:
            await interaction.followup.send("Sniffer reset cancelled.", ephemeral=True)
            return

        summary = await reset_sniffer_data(interaction, options=self.options)
        await interaction.followup.send(
            "Sniffer reset complete.\n"
            f"links_before: `{summary.links_before}`\n"
            f"links_after: `{summary.links_after}`\n"
            f"tokens_revoked: `{summary.tokens_revoked}`\n"
            f"bindings_cleared: `{summary.character_bindings_cleared}`\n"
            f"seasonal_ids_cleared: `{summary.seasonal_ids_cleared}`\n"
            f"metadata_entries_cleared: `{summary.metadata_entries_cleared}`\n"
            f"pending_files_cleared: `{summary.pending_files_cleared}`\n"
            f"endpoint_cleared: `{summary.endpoint_cleared}`\n"
            f"output_channel_cleared: `{summary.output_channel_cleared}`\n"
            f"sniffer_disabled: `{summary.sniffer_disabled}`",
            ephemeral=True,
        )
        await self._continue_sequence(interaction)

    @discord.ui.button(label="Continue Sequence", style=discord.ButtonStyle.success, row=3)
    async def continue_sequence(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        await self._continue_sequence(interaction)


class ResetPlayerRoleJoinEmbedView(OwnerBoundView):
    """Submenu for PPE Player role and contest-join embed cleanup actions."""

    def __init__(self, *, owner_id: int, join_embed_configured: bool, next_step_index: int) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.join_embed_configured = bool(join_embed_configured)
        self.next_step_index = _clamp_step(next_step_index)

        if not self.join_embed_configured:
            self.remove_item(self.clear_join_embed)
            self.remove_item(self.clear_both)

    def current_embed(self) -> discord.Embed:
        return _build_player_role_join_embed_embed(join_embed_configured=self.join_embed_configured)

    async def _continue_sequence(self, interaction: discord.Interaction) -> None:
        await _show_sequence_step_on_message(
            interaction.message,
            owner_id=self.owner_id,
            step_index=self.next_step_index,
            interaction=interaction,
        )

    async def _refresh_from_settings(self, interaction: discord.Interaction) -> None:
        settings = await load_contest_settings_for_menu(interaction)
        join_embed_configured = (
            int(settings.get("join_contest_channel_id", 0) or 0) > 0
            and int(settings.get("join_contest_message_id", 0) or 0) > 0
        )
        refreshed_view = ResetPlayerRoleJoinEmbedView(
            owner_id=self.owner_id,
            join_embed_configured=join_embed_configured,
            next_step_index=self.next_step_index,
        )
        if interaction.message is not None:
            try:
                await interaction.message.edit(embed=refreshed_view.current_embed(), view=refreshed_view)
            except discord.HTTPException:
                pass

    @discord.ui.button(label="Remove PPE Player Role", style=discord.ButtonStyle.danger, row=0)
    async def remove_player_role(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        confirmed = await _ask_confirmation(
            interaction,
            owner_id=self.owner_id,
            warning_text=(
                "WARNING: Remove PPE Player role from everyone? "
                "This also removes their reaction from the join embed, revokes all sniffer tokens, "
                "and fully clears stored loot records."
            ),
            confirm_label="Confirm Role Removal",
        )
        if not confirmed:
            await interaction.followup.send("Action cancelled.", ephemeral=True)
            return

        summary = await remove_ppe_player_role_from_everyone(interaction)
        await interaction.followup.send(
            "PPE Player cleanup complete.\n"
            f"role_found: `{summary.role_found}`\n"
            f"members_updated: `{summary.members_updated}`\n"
            f"members_failed: `{summary.members_failed}`\n"
            f"records_cleared: `{summary.records_cleared}`\n"
            f"tokens_revoked: `{summary.tokens_revoked}`",
            ephemeral=True,
        )
        await self._refresh_from_settings(interaction)
        await self._continue_sequence(interaction)

    @discord.ui.button(label="Clear Join Embed Info", style=discord.ButtonStyle.danger, row=0)
    async def clear_join_embed(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        confirmed = await _ask_confirmation(
            interaction,
            owner_id=self.owner_id,
            warning_text="WARNING: Clear configured join embed information?",
            confirm_label="Confirm Clear",
        )
        if not confirmed:
            await interaction.followup.send("Action cancelled.", ephemeral=True)
            return

        summary = await clear_join_embed_information(interaction)
        await interaction.followup.send(
            f"Join embed clear complete. was_configured: `{summary.join_embed_was_configured}` | "
            f"message_deleted: `{summary.join_embed_message_deleted}`",
            ephemeral=True,
        )
        await self._refresh_from_settings(interaction)
        await self._continue_sequence(interaction)

    @discord.ui.button(label="Clear Both", style=discord.ButtonStyle.danger, row=1)
    async def clear_both(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        confirmed = await _ask_confirmation(
            interaction,
            owner_id=self.owner_id,
            warning_text=(
                "WARNING: Remove PPE Player role from everyone (including join reaction, token, and records cleanup) "
                "and clear join embed information?"
            ),
            confirm_label="Confirm Clear Both",
        )
        if not confirmed:
            await interaction.followup.send("Action cancelled.", ephemeral=True)
            return

        role_summary = await remove_ppe_player_role_from_everyone(interaction)
        join_summary = await clear_join_embed_information(interaction)
        await interaction.followup.send(
            "Combined cleanup complete.\n"
            f"role_found: `{role_summary.role_found}`\n"
            f"members_updated: `{role_summary.members_updated}`\n"
            f"members_failed: `{role_summary.members_failed}`\n"
            f"records_cleared: `{role_summary.records_cleared}`\n"
            f"tokens_revoked: `{role_summary.tokens_revoked}`\n"
            f"join_embed_was_configured: `{join_summary.join_embed_was_configured}`\n"
            f"join_embed_message_deleted: `{join_summary.join_embed_message_deleted}`",
            ephemeral=True,
        )
        await self._refresh_from_settings(interaction)
        await self._continue_sequence(interaction)

    @discord.ui.button(label="Continue Sequence", style=discord.ButtonStyle.success, row=2)
    async def continue_sequence(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        await self._continue_sequence(interaction)


class ResetSeasonActionsView(OwnerBoundView):
    """Step-by-step reset menu with per-step summaries and confirmations."""

    def __init__(self, *, owner_id: int, step_index: int = 0) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.step_index = _clamp_step(step_index)
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        _key, title, _summary = _RESET_SEQUENCE[self.step_index]
        self.execute_step.label = f"Execute: {title}"
        self.previous_step.disabled = self.step_index <= 0
        self.next_step.disabled = self.step_index >= _max_step_index()

    def current_embed(self) -> discord.Embed:
        return _build_sequence_step_embed(self.step_index)

    async def _go_to_step(self, interaction: discord.Interaction, *, step_index: int) -> None:
        view = ResetSeasonActionsView(owner_id=self.owner_id, step_index=step_index)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    async def _auto_advance(self, interaction: discord.Interaction) -> None:
        if self.step_index >= _max_step_index():
            return
        await _show_sequence_step_on_message(
            interaction.message,
            owner_id=self.owner_id,
            step_index=self.step_index + 1,
            interaction=interaction,
        )

    async def _run_confirmed_reset(self, interaction: discord.Interaction, *, warning_text: str, confirm_label: str) -> bool:
        confirmed = await _ask_confirmation(
            interaction,
            owner_id=self.owner_id,
            warning_text=warning_text,
            confirm_label=confirm_label,
        )
        return bool(confirmed)

    @discord.ui.button(label="Execute Step", style=discord.ButtonStyle.danger, row=0)
    async def execute_step(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        key, _title, _summary = _RESET_SEQUENCE[self.step_index]

        if key == "reset_ppe_characters":
            confirmed = await self._run_confirmed_reset(
                interaction,
                warning_text=(
                    "WARNING: Reset all PPE characters?\n"
                    "This removes all characters and character loot, and keeps seasonal/quest information."
                ),
                confirm_label="Confirm Character Reset",
            )
            if not confirmed:
                await interaction.followup.send("Character reset cancelled.", ephemeral=True)
                return

            summary = await reset_all_ppe_characters(interaction)
            await interaction.followup.send(
                "Reset PPE characters complete.\n"
                f"players_updated: `{summary.players_updated}`\n"
                f"ppes_cleared: `{summary.ppes_cleared}`",
                ephemeral=True,
            )
            await self._auto_advance(interaction)
            return

        if key == "reset_seasonal_information":
            confirmed = await self._run_confirmed_reset(
                interaction,
                warning_text=(
                    "WARNING: Reset all seasonal information?\n"
                    "This clears unique season items and season-wide progress for all players."
                ),
                confirm_label="Confirm Seasonal Reset",
            )
            if not confirmed:
                await interaction.followup.send("Seasonal reset cancelled.", ephemeral=True)
                return

            summary = await reset_all_seasonal_information(interaction)
            await interaction.followup.send(
                "Reset seasonal information complete.\n"
                f"players_updated: `{summary.players_updated}`\n"
                f"unique_items_cleared: `{summary.unique_items_cleared}`\n"
                f"quest_entries_cleared: `{summary.quest_entries_cleared}`\n"
                f"default_reset_limit: `{summary.default_reset_limit}`",
                ephemeral=True,
            )
            await self._auto_advance(interaction)
            return

        if key == "reset_teams":
            confirmed = await self._run_confirmed_reset(
                interaction,
                warning_text=(
                    "WARNING: Reset all team data?\n"
                    "This clears team records and assignments, and deletes matching team roles."
                ),
                confirm_label="Confirm Team Reset",
            )
            if not confirmed:
                await interaction.followup.send("Team reset cancelled.", ephemeral=True)
                return

            summary = await reset_all_teams(interaction)
            await interaction.followup.send(
                "Reset teams complete.\n"
                f"teams_deleted: `{summary.teams_deleted}`\n"
                f"team_roles_deleted: `{summary.team_roles_deleted}`\n"
                f"players_unassigned: `{summary.players_unassigned}`",
                ephemeral=True,
            )
            await self._auto_advance(interaction)
            return

        if key == "reset_sniffer_information":
            view = ResetSnifferOptionsView(
                owner_id=self.owner_id,
                next_step_index=self.step_index + 1,
            )
            await interaction.response.edit_message(embed=view.current_embed(), view=view)
            return

        if key == "reset_quests":
            confirmed = await self._run_confirmed_reset(
                interaction,
                warning_text=(
                    "WARNING: Reset all quests?\n"
                    "This clears quest progress and restores each player's quest reset counter."
                ),
                confirm_label="Confirm Quest Reset",
            )
            if not confirmed:
                await interaction.followup.send("Quest reset cancelled.", ephemeral=True)
                return

            summary = await reset_all_quests(interaction)
            await interaction.followup.send(
                "Reset quests complete.\n"
                f"players_updated: `{summary.players_updated}`\n"
                f"quest_entries_cleared: `{summary.quest_entries_cleared}`\n"
                f"default_reset_limit: `{summary.default_reset_limit}`",
                ephemeral=True,
            )
            await self._auto_advance(interaction)
            return

        if key == "reset_settings":
            confirmed = await self._run_confirmed_reset(
                interaction,
                warning_text=(
                    "WARNING: Reset all admin-tunable settings to defaults?\n"
                    "This preserves sniffer endpoint and join embed message settings only."
                ),
                confirm_label="Confirm Settings Reset",
            )
            if not confirmed:
                await interaction.followup.send("Settings reset cancelled.", ephemeral=True)
                return

            summary = await reset_admin_tunable_settings_to_defaults(interaction)
            await interaction.followup.send(
                "Settings reset complete.\n"
                f"endpoint_preserved: `{summary.endpoint_preserved}`\n"
                f"join_embed_preserved: `{summary.join_embed_preserved}`\n"
                f"picture_suggestion_channels_cleared: `{summary.picture_suggestion_channels_cleared}`",
                ephemeral=True,
            )
            await self._auto_advance(interaction)
            return

        if key == "player_role_join_embed":
            settings = await load_contest_settings_for_menu(interaction)
            join_embed_configured = (
                int(settings.get("join_contest_channel_id", 0) or 0) > 0
                and int(settings.get("join_contest_message_id", 0) or 0) > 0
            )
            view = ResetPlayerRoleJoinEmbedView(
                owner_id=self.owner_id,
                join_embed_configured=join_embed_configured,
                next_step_index=self.step_index + 1,
            )
            await interaction.response.edit_message(embed=view.current_embed(), view=view)
            return

        if key == "remove_admin_roles":
            confirmed = await self._run_confirmed_reset(
                interaction,
                warning_text="WARNING: Remove the PPE Admin role from everyone in this server?",
                confirm_label="Confirm Admin Role Removal",
            )
            if not confirmed:
                await interaction.followup.send("Admin role removal cancelled.", ephemeral=True)
                return

            summary = await remove_ppe_admin_role_from_everyone(interaction)
            await interaction.followup.send(
                "PPE Admin role removal complete.\n"
                f"role_found: `{summary.role_found}`\n"
                f"members_updated: `{summary.members_updated}`\n"
                f"members_failed: `{summary.members_failed}`",
                ephemeral=True,
            )
            await self._auto_advance(interaction)
            return

        if key == "delete_role_objects":
            confirmed = await self._run_confirmed_reset(
                interaction,
                warning_text=(
                    "WARNING: Delete PPE Admin, PPE Player, and known team role objects if they exist?"
                ),
                confirm_label="Confirm Role Deletion",
            )
            if not confirmed:
                await interaction.followup.send("Role deletion cancelled.", ephemeral=True)
                return

            summary = await delete_ppe_and_team_roles(interaction)
            await interaction.followup.send(
                "Role deletion complete.\n"
                f"ppe_roles_deleted: `{summary.ppe_roles_deleted}`\n"
                f"ppe_roles_failed: `{summary.ppe_roles_failed}`\n"
                f"team_roles_deleted: `{summary.team_roles_deleted}`\n"
                f"team_roles_failed: `{summary.team_roles_failed}`",
                ephemeral=True,
            )
            return

        await interaction.response.send_message("Unknown reset step.", ephemeral=True)

    @discord.ui.button(label="Previous Step", style=discord.ButtonStyle.secondary, row=1)
    async def previous_step(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._go_to_step(interaction, step_index=self.step_index - 1)

    @discord.ui.button(label="Next Step", style=discord.ButtonStyle.success, row=1)
    async def next_step(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._go_to_step(interaction, step_index=self.step_index + 1)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.home.views import ManageSeasonHomeView

        home_view = ManageSeasonHomeView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=home_view.current_embed(), view=home_view)


__all__ = [
    "ResetPlayerRoleJoinEmbedView",
    "ResetSeasonActionsView",
    "ResetSnifferOptionsView",
]
