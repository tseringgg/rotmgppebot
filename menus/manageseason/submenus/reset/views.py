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
    reset_all_seasonal_information,
    reset_all_teams,
    reset_sniffer_data,
)
from menus.menu_utils import ConfirmCancelView, OwnerBoundView


def _build_reset_actions_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Reset Season",
        description=(
            "Choose one reset action at a time. Every action asks for confirmation before it runs.\n"
            "These actions are granular and do not force a full season wipe."
        ),
        color=discord.Color.orange(),
    )
    embed.add_field(
        name="Data Resets",
        value=(
            "• **Reset PPE Characters**: remove all PPE characters and character loot only.\n"
            "• **Reset Seasonal Information**: clear season uniques + quest progress for everyone.\n"
            "• **Reset Teams**: clear team assignments/records and delete matching team roles."
        ),
        inline=False,
    )
    embed.add_field(
        name="Sniffer + Settings",
        value=(
            "• **Reset Sniffer Information**: select exactly what to clear.\n"
            "• **Reset Settings to Defaults**: reset admin-tunable settings, while preserving sniffer endpoint"
            " and join embed message settings."
        ),
        inline=False,
    )
    embed.add_field(
        name="Role Actions",
        value=(
            "• **PPE Player Role / Join Embed**: role removal + optional join-embed clearing actions.\n"
            "• **Remove PPE Admin Roles**: remove PPE Admin from all members.\n"
            "• **Delete PPE/Team Role Objects**: delete PPE Admin/PPE Player and known team roles if they exist."
        ),
        inline=False,
    )
    embed.set_footer(text="This panel is owner-bound and admin-only.")
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
            f"• Clear character mappings: **{_state(options.clear_character_mappings)}**\n"
            f"• Revoke all tokens: **{_state(options.revoke_tokens)}**\n"
            f"• Clear pending files: **{_state(options.clear_pending_files)}**\n"
            f"• Clear output channel: **{_state(options.clear_output_channel)}**\n"
            f"• Clear endpoint: **{_state(options.clear_endpoint)}**\n"
            f"• Disable sniffer: **{_state(options.disable_sniffer)}**"
        ),
        inline=False,
    )
    embed.add_field(
        name="Notes",
        value=(
            "When **Revoke all tokens** is OFF, player tokens are preserved.\n"
            "When **Clear endpoint** is ON, the configured sniffer endpoint is removed."
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
            "• Remove PPE Player role from everyone.\n"
            "• If join embed is configured, clear join embed info only.\n"
            "• If join embed is configured, clear both in one action."
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


class ResetSnifferOptionsView(OwnerBoundView):
    """Sniffer reset options submenu with toggleable actions."""

    def __init__(self, *, owner_id: int, options: ResetSnifferOptions | None = None) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
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

    @discord.ui.button(label="Mappings: ON", style=discord.ButtonStyle.primary, row=0)
    async def toggle_character_mappings(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.options.clear_character_mappings = not self.options.clear_character_mappings
        await self._refresh_message(interaction)

    @discord.ui.button(label="Revoke Tokens: OFF", style=discord.ButtonStyle.primary, row=0)
    async def toggle_revoke_tokens(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.options.revoke_tokens = not self.options.revoke_tokens
        await self._refresh_message(interaction)

    @discord.ui.button(label="Clear Pending: OFF", style=discord.ButtonStyle.primary, row=1)
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

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=3)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        view = ResetSeasonActionsView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class ResetPlayerRoleJoinEmbedView(OwnerBoundView):
    """Submenu for PPE Player role and contest-join embed cleanup actions."""

    def __init__(self, *, owner_id: int, join_embed_configured: bool) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.join_embed_configured = bool(join_embed_configured)

        if not self.join_embed_configured:
            self.remove_item(self.clear_join_embed)
            self.remove_item(self.clear_both)

    def current_embed(self) -> discord.Embed:
        return _build_player_role_join_embed_embed(join_embed_configured=self.join_embed_configured)

    async def _refresh_from_settings(self, interaction: discord.Interaction) -> None:
        settings = await load_contest_settings_for_menu(interaction)
        join_embed_configured = (
            int(settings.get("join_contest_channel_id", 0) or 0) > 0
            and int(settings.get("join_contest_message_id", 0) or 0) > 0
        )
        refreshed_view = ResetPlayerRoleJoinEmbedView(
            owner_id=self.owner_id,
            join_embed_configured=join_embed_configured,
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
            warning_text="WARNING: Remove the PPE Player role from everyone in this server?",
            confirm_label="Confirm Role Removal",
        )
        if not confirmed:
            await interaction.followup.send("Action cancelled.", ephemeral=True)
            return

        summary = await remove_ppe_player_role_from_everyone(interaction)
        await interaction.followup.send(
            f"PPE Player role removal complete. role_found: `{summary.role_found}` | "
            f"members_updated: `{summary.members_updated}` | members_failed: `{summary.members_failed}`",
            ephemeral=True,
        )
        await self._refresh_from_settings(interaction)

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

    @discord.ui.button(label="Clear Both", style=discord.ButtonStyle.danger, row=1)
    async def clear_both(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        confirmed = await _ask_confirmation(
            interaction,
            owner_id=self.owner_id,
            warning_text=(
                "WARNING: Remove PPE Player role from everyone and clear join embed information in one action?"
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
            f"join_embed_was_configured: `{join_summary.join_embed_was_configured}`\n"
            f"join_embed_message_deleted: `{join_summary.join_embed_message_deleted}`",
            ephemeral=True,
        )
        await self._refresh_from_settings(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        view = ResetSeasonActionsView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class ResetSeasonActionsView(OwnerBoundView):
    """Granular reset menu where each action has its own confirmation."""

    def __init__(self, *, owner_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id

    def current_embed(self) -> discord.Embed:
        return _build_reset_actions_embed()

    @discord.ui.button(label="Reset PPE Characters", style=discord.ButtonStyle.danger, row=0)
    async def reset_ppe_characters(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        confirmed = await _ask_confirmation(
            interaction,
            owner_id=self.owner_id,
            warning_text=(
                "WARNING: Reset all PPE characters?\n"
                "This removes all characters and character loot info, but leaves other systems intact."
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
            f"ppes_cleared: `{summary.ppes_cleared}`\n"
            f"unique_items_cleared: `{summary.unique_items_cleared}`",
            ephemeral=True,
        )

    @discord.ui.button(label="Reset Seasonal Information", style=discord.ButtonStyle.danger, row=0)
    async def reset_seasonal_information(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        confirmed = await _ask_confirmation(
            interaction,
            owner_id=self.owner_id,
            warning_text=(
                "WARNING: Reset all seasonal information?\n"
                "This clears unique season items and quest progress for all players."
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

    @discord.ui.button(label="Reset Teams", style=discord.ButtonStyle.danger, row=1)
    async def reset_teams(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        confirmed = await _ask_confirmation(
            interaction,
            owner_id=self.owner_id,
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

    @discord.ui.button(label="Reset Sniffer Information", style=discord.ButtonStyle.danger, row=1)
    async def reset_sniffer(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        view = ResetSnifferOptionsView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Reset Settings to Defaults", style=discord.ButtonStyle.danger, row=2)
    async def reset_settings(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        confirmed = await _ask_confirmation(
            interaction,
            owner_id=self.owner_id,
            warning_text=(
                "WARNING: Reset all admin-tunable settings to default values?\n"
                "This preserves sniffer endpoint and join-embed message settings only."
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

    @discord.ui.button(label="PPE Player Role / Join Embed", style=discord.ButtonStyle.danger, row=2)
    async def player_role_join_embed(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await load_contest_settings_for_menu(interaction)
        join_embed_configured = (
            int(settings.get("join_contest_channel_id", 0) or 0) > 0
            and int(settings.get("join_contest_message_id", 0) or 0) > 0
        )
        view = ResetPlayerRoleJoinEmbedView(
            owner_id=self.owner_id,
            join_embed_configured=join_embed_configured,
        )
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Remove PPE Admin Roles", style=discord.ButtonStyle.danger, row=3)
    async def remove_admin_roles(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        confirmed = await _ask_confirmation(
            interaction,
            owner_id=self.owner_id,
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

    @discord.ui.button(label="Delete PPE/Team Role Objects", style=discord.ButtonStyle.danger, row=3)
    async def delete_roles(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        confirmed = await _ask_confirmation(
            interaction,
            owner_id=self.owner_id,
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

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=4)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.home.views import ManageSeasonHomeView

        home_view = ManageSeasonHomeView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=home_view.current_embed(), view=home_view)


__all__ = [
    "ResetPlayerRoleJoinEmbedView",
    "ResetSeasonActionsView",
    "ResetSnifferOptionsView",
]
