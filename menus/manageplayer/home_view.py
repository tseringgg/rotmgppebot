"""Home screen views for the /manageplayer admin menu."""

from __future__ import annotations

import discord

from menus.manageplayer.common import (
    ManagedPlayerTarget,
    add_target_to_contest,
    close_manageplayer_menu,
    delete_all_ppes_for_target,
    give_target_admin_role,
    load_target_player_data,
    open_manageplayer_home,
    remove_target_admin_role,
    remove_target_from_contest,
    send_followup_text,
    send_target_ppe_list_markdown_followup,
    target_has_admin_role,
    target_home_embed,
)
from menus.menu_utils import OwnerBoundView
from menus.myquests import open_myquests_menu_for_player
from utils.guild_config import load_guild_config
from utils.player_records import load_teams


class _AddToTeamButton(discord.ui.Button):
    """Open the team selection submenu to assign a player to an existing team."""

    def __init__(self) -> None:
        super().__init__(label="Add to Team", style=discord.ButtonStyle.success, row=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManagePlayerHomeView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=False)
            return

        from menus.manageplayer.team_view import ManagePlayerAddToTeamView
        from utils.autocomplete import team_name_autocomplete

        teams = await load_teams(interaction)
        team_choices = await team_name_autocomplete(interaction, "")
        ordered_team_names = [choice.value for choice in team_choices]
        team_view = ManagePlayerAddToTeamView(
            owner_id=interaction.user.id,
            target=view.target,
            max_ppes=view.max_ppes,
            teams=teams,
            ordered_team_names=ordered_team_names,
        )
        await interaction.response.edit_message(embed=team_view.current_embed(), view=team_view)


class _RemoveFromTeamButton(discord.ui.Button):
    """Open a confirmation submenu before removing a player from their team."""

    def __init__(self) -> None:
        super().__init__(label="Remove from Team", style=discord.ButtonStyle.danger, row=3)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManagePlayerHomeView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=False)
            return

        player_data = await load_target_player_data(interaction, view.target.user_id)
        current_team_name = player_data.team_name
        if not current_team_name:
            await interaction.response.send_message(
                f"{view.target.display_name} is not on a team.",
                ephemeral=True,
            )
            return

        from menus.manageplayer.team_view import ManagePlayerRemoveFromTeamConfirmView

        confirm_view = ManagePlayerRemoveFromTeamConfirmView(
            owner_id=interaction.user.id,
            target=view.target,
            max_ppes=view.max_ppes,
            team_name=current_team_name,
        )
        await interaction.response.edit_message(embed=confirm_view.current_embed(), view=confirm_view)


class _ManagePlayerActionConfirmView(OwnerBoundView):
    """Confirmation submenu used for destructive /manageplayer actions."""

    def __init__(
        self,
        *,
        owner_id: int,
        target: ManagedPlayerTarget,
        max_ppes: int,
        action_key: str,
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=120, owner_error="This confirmation belongs to another user.")
        self.target = target
        self.max_ppes = max_ppes
        self.action_key = action_key

    def current_embed(self) -> discord.Embed:
        descriptions = {
            "delete_all": f"Are you sure you want to delete all PPEs for **{self.target.display_name}**?",
            "remove_contest": (
                f"Are you sure you want to remove **{self.target.display_name}** from the contest?\n"
                "This also removes their PPE record and team assignment."
            ),
            "remove_admin": f"Are you sure you want to remove PPE Admin from **{self.target.display_name}**?",
        }
        return discord.Embed(
            title="Confirm Action",
            description=descriptions.get(self.action_key, "Are you sure?"),
            color=discord.Color.orange(),
        )

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, row=0)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            if self.action_key == "delete_all":
                result = await delete_all_ppes_for_target(interaction, self.target)
                await interaction.response.defer()
                await send_followup_text(interaction, result, ephemeral=False)
                await close_manageplayer_menu(interaction)
                return

            if self.action_key == "remove_contest":
                result = await remove_target_from_contest(interaction, self.target)
                await interaction.response.defer()
                await send_followup_text(interaction, result, ephemeral=False)
                await close_manageplayer_menu(interaction)
                return

            if self.action_key == "remove_admin":
                if not interaction.guild or interaction.user.id != interaction.guild.owner_id:
                    await interaction.response.send_message("❌ Only the server owner can remove PPE Admin.", ephemeral=True)
                    return

                result = await remove_target_admin_role(interaction, self.target)
                await open_manageplayer_home(
                    interaction,
                    owner_id=interaction.user.id,
                    target=self.target,
                    max_ppes=self.max_ppes,
                )
                await send_followup_text(interaction, result, ephemeral=False)
                return

            await interaction.response.send_message("❌ Unknown confirmation action.", ephemeral=True)
        except Exception as e:
            await send_followup_text(interaction, str(e), ephemeral=False)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=0)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await open_manageplayer_home(
            interaction,
            owner_id=interaction.user.id,
            target=self.target,
            max_ppes=self.max_ppes,
        )


class ManagePlayerHomeView(OwnerBoundView):
    """Home dashboard for admin management of a specific player."""

    def __init__(
        self,
        owner_id: int,
        *,
        target: ManagedPlayerTarget,
        max_ppes: int,
        target_team_name: str | None,
        is_target_admin: bool,
        is_in_contest: bool,
        owner_can_manage_admin: bool,
    ):
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.target = target
        self.max_ppes = max_ppes
        self.target_team_name = target_team_name
        self.is_target_admin = is_target_admin
        self.is_in_contest = is_in_contest
        self.owner_can_manage_admin = owner_can_manage_admin
        self.team_action_button: discord.ui.Button | None = None

        # The team action is context-sensitive: add when teamless, remove when already assigned.
        if self.is_in_contest:
            if self.target_team_name:
                self.team_action_button = _RemoveFromTeamButton()
            else:
                self.team_action_button = _AddToTeamButton()
            self.add_item(self.team_action_button)

        if self.is_in_contest or self.target.member is None:
            self.remove_item(self.add_to_contest)

        if not self.is_in_contest or self.target.member is None:
            self.remove_item(self.reset_quests)

        if not self.owner_can_manage_admin or self.target.member is None:
            self.remove_item(self.make_admin)
            self.remove_item(self.remove_admin)
        elif self.is_target_admin:
            self.remove_item(self.make_admin)
        else:
            self.remove_item(self.remove_admin)

        self._reorder_row_two_buttons()

    def _reorder_row_two_buttons(self) -> None:
        row_two_buttons: list[discord.ui.Item] = []
        row_three_buttons: list[discord.ui.Item] = []

        if isinstance(self.team_action_button, _RemoveFromTeamButton) and self.team_action_button in self.children:
            row_two_buttons.append(self.team_action_button)

        for candidate in (self.reset_quests, self.delete_all_ppes, self.cancel):
            if candidate in self.children:
                row_two_buttons.append(candidate)

        for candidate in (self.remove_admin, self.remove_from_contest):
            if candidate in self.children:
                row_three_buttons.append(candidate)

        if not row_two_buttons and not row_three_buttons:
            return

        for button in row_two_buttons + row_three_buttons:
            if button in self.children:
                self.remove_item(button)

        for button in row_two_buttons:
            button.row = 2
            self.add_item(button)

        for button in row_three_buttons:
            button.row = 3
            self.add_item(button)

    async def refresh_embed(self, interaction: discord.Interaction) -> discord.Embed:
        player_data = await load_target_player_data(interaction, self.target.user_id)
        active_ppe = None
        for ppe in player_data.ppes:
            if ppe.id == player_data.active_ppe:
                active_ppe = ppe
                break
        return target_home_embed(
            target=self.target,
            player_data=player_data,
            active_ppe=active_ppe,
            max_ppes=self.max_ppes,
            target_is_admin=target_has_admin_role(interaction, self.target),
        )

    @discord.ui.button(label="Show Season Loot", style=discord.ButtonStyle.primary, row=0)
    async def show_season_loot(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageplayer.season_view import ManagePlayerSeasonLootView

        view = ManagePlayerSeasonLootView(owner_id=interaction.user.id, target=self.target, max_ppes=self.max_ppes)
        embed = view.current_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Show Quests", style=discord.ButtonStyle.primary, row=0)
    async def show_quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_manageplayer_menu(interaction)

        async def _show_target_reset_for_member(reset_interaction: discord.Interaction) -> None:
            if self.target.member is None:
                await reset_interaction.response.send_message(
                    "❌ Quest reset is only available when the target is still a member of this server.",
                    ephemeral=True,
                )
                return
            from menus.managequests.reset_actions import open_reset_for_member

            await open_reset_for_member(reset_interaction, self.target.member, actor_id=interaction.user.id)

        await open_myquests_menu_for_player(
            interaction,
            owner_id=interaction.user.id,
            target_user_id=self.target.user_id,
            target_display_name=self.target.display_name,
            ephemeral=False,
            reset_callback=_show_target_reset_for_member,
        )

    @discord.ui.button(label="List PPEs", style=discord.ButtonStyle.primary, row=0)
    async def list_ppes(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        player_data = await load_target_player_data(interaction, self.target.user_id)
        if not player_data.ppes:
            await interaction.response.defer()
            await send_followup_text(interaction, f"No PPEs found for {self.target.display_name}.", ephemeral=True)
            return
        await interaction.response.defer()
        await send_target_ppe_list_markdown_followup(interaction, target=self.target, player_data=player_data)

    @discord.ui.button(label="My Team", style=discord.ButtonStyle.primary, row=0)
    async def my_team(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from slash_commands.myteam_cmd import build_team_embeds

        embeds = await build_team_embeds(
            interaction,
            user_id=self.target.user_id,
            title=f"Team View - {self.target.display_name}",
        )
        view = ManagePlayerTeamView(
            owner_id=interaction.user.id,
            target=self.target,
            max_ppes=self.max_ppes,
            embeds=embeds,
        )
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Manage Characters", style=discord.ButtonStyle.success, row=1)
    async def manage_characters(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageplayer.character_view import ManagePlayerCharactersView

        player_data = await load_target_player_data(interaction, self.target.user_id)

        if not player_data.ppes:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="No Characters",
                    description=f"{self.target.display_name} has no PPE characters.",
                    color=discord.Color.orange(),
                ),
                view=ManagePlayerHomeView(
                    owner_id=interaction.user.id,
                    target=self.target,
                    max_ppes=self.max_ppes,
                    target_team_name=player_data.team_name,
                    is_target_admin=target_has_admin_role(interaction, self.target),
                    is_in_contest=bool(player_data.is_member or self.target.has_player_role),
                    owner_can_manage_admin=bool(
                        interaction.guild and int(interaction.user.id) == int(interaction.guild.owner_id)
                    ),
                ),
            )
            return

        guild_config = await load_guild_config(interaction)
        from menus.manageplayer.common import realmshark_connected_ppe_ids

        connected_ids = await realmshark_connected_ppe_ids(interaction, self.target.user_id)
        view = ManagePlayerCharactersView(
            owner_id=interaction.user.id,
            target=self.target,
            player_data=player_data,
            connected_ppe_ids=connected_ids,
            guild_config=guild_config,
        )
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


    @discord.ui.button(label="Add to Contest", style=discord.ButtonStyle.success, row=1)
    async def add_to_contest(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            result = await add_target_to_contest(interaction, self.target)
            await interaction.response.defer()
            await send_followup_text(interaction, result, ephemeral=False)
            await close_manageplayer_menu(interaction)
        except Exception as e:
            await send_followup_text(interaction, str(e), ephemeral=False)

    @discord.ui.button(label="Make Admin", style=discord.ButtonStyle.success, row=1)
    async def make_admin(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not interaction.guild or interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ Only the server owner can make PPE Admin.", ephemeral=True)
            return
        try:
            result = await give_target_admin_role(interaction, self.target)
            await open_manageplayer_home(
                interaction,
                owner_id=interaction.user.id,
                target=self.target,
                max_ppes=self.max_ppes,
            )
            await send_followup_text(interaction, result, ephemeral=False)
        except Exception as e:
            await send_followup_text(interaction, str(e), ephemeral=False)

    @discord.ui.button(label="Remove Admin", style=discord.ButtonStyle.danger, row=2)
    async def remove_admin(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not interaction.guild or interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ Only the server owner can remove PPE Admin.", ephemeral=True)
            return

        confirm_view = _ManagePlayerActionConfirmView(
            owner_id=interaction.user.id,
            target=self.target,
            max_ppes=self.max_ppes,
            action_key="remove_admin",
        )
        await interaction.response.edit_message(embed=confirm_view.current_embed(), view=confirm_view)

    @discord.ui.button(label="Delete All PPEs", style=discord.ButtonStyle.danger, row=2)
    async def delete_all_ppes(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        confirm_view = _ManagePlayerActionConfirmView(
            owner_id=interaction.user.id,
            target=self.target,
            max_ppes=self.max_ppes,
            action_key="delete_all",
        )
        await interaction.response.edit_message(embed=confirm_view.current_embed(), view=confirm_view)

    @discord.ui.button(label="Reset Quests", style=discord.ButtonStyle.danger, row=2)
    async def reset_quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if self.target.member is None:
            await interaction.response.send_message(
                "❌ Quest reset is only available when the target is still a member of this server.",
                ephemeral=True,
            )
            return
        from menus.managequests.reset_actions import open_reset_for_member

        await open_reset_for_member(interaction, self.target.member, actor_id=interaction.user.id)

    @discord.ui.button(label="Remove from Contest", style=discord.ButtonStyle.danger, row=2)
    async def remove_from_contest(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        confirm_view = _ManagePlayerActionConfirmView(
            owner_id=interaction.user.id,
            target=self.target,
            max_ppes=self.max_ppes,
            action_key="remove_contest",
        )
        await interaction.response.edit_message(embed=confirm_view.current_embed(), view=confirm_view)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=2)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_manageplayer_menu(interaction)


class ManagePlayerTeamView(OwnerBoundView):
    """Team ranking view opened from /manageplayer with overflow pagination controls."""

    def __init__(
        self,
        *,
        owner_id: int,
        target: ManagedPlayerTarget,
        max_ppes: int,
        embeds: list[discord.Embed],
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.target = target
        self.max_ppes = max_ppes
        self.embeds = embeds
        self.index = 0

        if len(self.embeds) <= 1:
            self.remove_item(self.prev_page)
            self.remove_item(self.next_page)

    def current_embed(self) -> discord.Embed:
        return self.embeds[self.index]

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary, row=0)
    async def prev_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = (self.index - 1) % len(self.embeds)
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, row=0)
    async def next_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = (self.index + 1) % len(self.embeds)
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await open_manageplayer_home(
            interaction,
            owner_id=interaction.user.id,
            target=self.target,
            max_ppes=self.max_ppes,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_manageplayer_menu(interaction)


class NotInContestView(OwnerBoundView):
    """Fallback view shown when target player is not in the PPE contest."""

    def __init__(self, owner_id: int, *, target: ManagedPlayerTarget, max_ppes: int):
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.target = target
        self.max_ppes = max_ppes

    @discord.ui.button(label="Add to Contest", style=discord.ButtonStyle.success, row=0)
    async def add_to_contest(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            result = await add_target_to_contest(interaction, self.target)
            await open_manageplayer_home(
                interaction,
                owner_id=interaction.user.id,
                target=self.target,
                max_ppes=self.max_ppes,
            )
            await send_followup_text(interaction, result, ephemeral=False)
        except Exception as e:
            await send_followup_text(interaction, str(e), ephemeral=False)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=0)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_manageplayer_menu(interaction)
