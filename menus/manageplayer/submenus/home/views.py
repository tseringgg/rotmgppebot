"""Home screen views for the /manageplayer admin menu."""

from __future__ import annotations

import discord

from menus.manageplayer.common import (
    close_manageplayer_menu,
    send_followup_text,
    send_target_ppe_list_markdown_followup,
    target_home_embed,
)
from menus.manageplayer.entry import open_manageplayer_home
from menus.manageplayer.layout import reorder_manageplayer_home_rows
from menus.manageplayer.services import (
    add_target_to_contest,
    delete_all_ppes_for_target,
    give_target_admin_role,
    load_target_player_data,
    remove_target_admin_role,
    remove_target_from_contest,
    send_target_quests_followup,
    target_has_admin_role,
)
from slash_commands.newppe_cmd import create_new_ppe_for_user
from menus.manageplayer.targets import ManagedPlayerTarget
from menus.menu_utils import OwnerBoundView
from menus.menu_utils.embed_pager_view import OwnerBoundEmbedPagerView
from menus.myquests import open_myquests_menu_for_player
from utils.guild_config import load_guild_config, get_max_ppes
from utils.player_records import load_teams
from dataclass import ROTMGClass


class CreateCharacterModal(discord.ui.Modal, title="Create New Character"):
    """Modal for admin to create a new PPE character for another player."""

    def __init__(
        self,
        *,
        owner_id: int,
        target: ManagedPlayerTarget,
        max_ppes: int,
    ) -> None:
        super().__init__()
        self.owner_id = owner_id
        self.target = target
        self.max_ppes = max_ppes

        self.class_name = discord.ui.TextInput(
            label="Class Name",
            required=True,
            max_length=20,
            placeholder="e.g., Wizard",
        )
        self.add_item(self.class_name)

        self.pet_level = discord.ui.TextInput(
            label="Pet Level (0-100)",
            required=True,
            max_length=3,
            placeholder="e.g., 50",
        )
        self.add_item(self.pet_level)

        self.num_exalts = discord.ui.TextInput(
            label="Exalts (0-40)",
            required=True,
            max_length=3,
            placeholder="e.g., 10",
        )
        self.add_item(self.num_exalts)

        self.percent_loot = discord.ui.TextInput(
            label="Loot Boost % (0-25)",
            required=True,
            max_length=5,
            placeholder="e.g., 5",
        )
        self.add_item(self.percent_loot)

        self.incombat_reduction = discord.ui.TextInput(
            label="In-Combat Reduction (0/0.2/0.4/0.6/0.8/1.0)",
            placeholder="Enter one of: 0, 0.2, 0.4, 0.6, 0.8, 1.0",
            required=True,
            max_length=3,
        )
        self.add_item(self.incombat_reduction)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Modals only support text inputs, so normalize free-text class names
        # to one of the canonical ROTMG class values before creating the PPE.
        raw_class_name = (self.class_name.value or "").strip()
        class_name = next(
            (cls.value for cls in ROTMGClass if cls.value.lower() == raw_class_name.lower()),
            raw_class_name,
        )

        try:
            result = await create_new_ppe_for_user(
                interaction,
                class_name=class_name,
                pet_level=int(self.pet_level.value),
                num_exalts=int(self.num_exalts.value),
                percent_loot=float(self.percent_loot.value),
                incombat_reduction=float(self.incombat_reduction.value),
                target_user_id=self.target.user_id,
            )
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        await interaction.response.send_message(
            f"✅ Created `PPE #{result['next_id']}` for **{self.target.display_name}** "
            f"(`{result['class_name']}`) and set it as their active PPE.\n"
            f"They now have {result['ppe_count']}/{result['max_ppes']} PPEs.",
            embed=result["embed"],
            ephemeral=False,
        )

        # Refresh to home view
        await open_manageplayer_home(
            interaction,
            owner_id=self.owner_id,
            target=self.target,
            max_ppes=self.max_ppes,
        )


class NoCharactersView(OwnerBoundView):
    """View shown when a player has no characters, with options to create one or go back."""

    def __init__(
        self,
        owner_id: int,
        *,
        target: ManagedPlayerTarget,
        max_ppes: int,
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.target = target
        self.max_ppes = max_ppes

    @discord.ui.button(label="Create Character", style=discord.ButtonStyle.success, row=0)
    async def create_character(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        modal = CreateCharacterModal(
            owner_id=interaction.user.id,
            target=self.target,
            max_ppes=self.max_ppes,
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Go Back", style=discord.ButtonStyle.secondary, row=0)
    async def go_back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await open_manageplayer_home(
            interaction,
            owner_id=interaction.user.id,
            target=self.target,
            max_ppes=self.max_ppes,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_manageplayer_menu(interaction)


class _AddToTeamButton(discord.ui.Button):
    """Open the team selection submenu to assign a player to an existing team."""

    def __init__(self) -> None:
        super().__init__(label="Add to Team", style=discord.ButtonStyle.success, row=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManagePlayerHomeView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=False)
            return

        from menus.manageplayer.submenus.team.views import ManagePlayerAddToTeamView
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
        super().__init__(label="Remove From Team", style=discord.ButtonStyle.danger, row=3)

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

        from menus.manageplayer.submenus.team.views import ManagePlayerRemoveFromTeamConfirmView

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
                "This also removes their PPE record, team assignment, and PPE Admin role (if they have it)."
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
                    refresh_member=True,
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
        reorder_manageplayer_home_rows(
            children=self.children,
            team_action_button=self.team_action_button,
            reset_quests_button=self.reset_quests,
            delete_all_ppes_button=self.delete_all_ppes,
            remove_admin_button=self.remove_admin,
            remove_from_contest_button=self.remove_from_contest,
            cancel_button=self.cancel,
            remove_item=self.remove_item,
            add_item=self.add_item,
        )

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
        from menus.manageplayer.submenus.season.views import ManagePlayerSeasonLootView

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
        from menus.manageplayer.submenus.character.views import ManagePlayerCharactersView

        player_data = await load_target_player_data(interaction, self.target.user_id)

        if not player_data.ppes:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="No Characters",
                    description=f"{self.target.display_name} has no PPE characters.",
                    color=discord.Color.orange(),
                ),
                view=NoCharactersView(
                    owner_id=interaction.user.id,
                    target=self.target,
                    max_ppes=self.max_ppes,
                ),
            )
            return

        guild_config = await load_guild_config(interaction)
        from menus.manageplayer.common import realmshark_connected_ppe_ids

        connected_ids = await realmshark_connected_ppe_ids(interaction, self.target.user_id)
        view = ManagePlayerCharactersView(
            owner_id=interaction.user.id,
            target=self.target,
            max_ppes=self.max_ppes,
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
                refresh_member=True,
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

    @discord.ui.button(label="Remove From Contest", style=discord.ButtonStyle.danger, row=2)
    async def remove_from_contest(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        confirm_view = _ManagePlayerActionConfirmView(
            owner_id=interaction.user.id,
            target=self.target,
            max_ppes=self.max_ppes,
            action_key="remove_contest",
        )
        await interaction.response.edit_message(embed=confirm_view.current_embed(), view=confirm_view)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=3)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_manageplayer_menu(interaction)


class ManagePlayerTeamView(OwnerBoundEmbedPagerView):
    """Team ranking view opened from /manageplayer with overflow pagination controls."""

    def __init__(
        self,
        *,
        owner_id: int,
        target: ManagedPlayerTarget,
        max_ppes: int,
        embeds: list[discord.Embed],
    ) -> None:
        super().__init__(owner_id=owner_id, embeds=embeds, timeout=600)
        self.target = target
        self.max_ppes = max_ppes

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
