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
    remove_target_from_contest,
    send_followup_text,
    send_target_ppe_list_markdown_followup,
    send_target_quests_followup,
    send_target_season_loot_markdown_followup,
    target_home_embed,
)
from menus.menu_utils import OwnerBoundView
from menus.myquests import open_myquests_menu
from utils.guild_config import get_max_ppes, load_guild_config
from utils.player_records import load_player_records


class ManagePlayerHomeView(OwnerBoundView):
    """Home dashboard for admin management of a specific player."""

    def __init__(self, owner_id: int, *, target: ManagedPlayerTarget, max_ppes: int):
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.target = target
        self.max_ppes = max_ppes

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
        await send_target_quests_followup(interaction, self.target)

    @discord.ui.button(label="List PPEs", style=discord.ButtonStyle.secondary, row=0)
    async def list_ppes(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        player_data = await load_target_player_data(interaction, self.target.user_id)
        if not player_data.ppes:
            await interaction.response.defer()
            await send_followup_text(interaction, f"No PPEs found for {self.target.display_name}.", ephemeral=False)
            return
        await interaction.response.defer()
        await send_target_ppe_list_markdown_followup(interaction, target=self.target, player_data=player_data)

    @discord.ui.button(label="Manage Characters", style=discord.ButtonStyle.success, row=0)
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
                view=ManagePlayerHomeView(owner_id=interaction.user.id, target=self.target, max_ppes=self.max_ppes),
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

    @discord.ui.button(label="Delete All PPEs", style=discord.ButtonStyle.danger, row=1)
    async def delete_all_ppes(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            result = await delete_all_ppes_for_target(interaction, self.target)
            await interaction.response.defer()
            await send_followup_text(interaction, result, ephemeral=False)
            await close_manageplayer_menu(interaction)
        except Exception as e:
            await send_followup_text(interaction, str(e), ephemeral=True)

    @discord.ui.button(label="Remove from Contest", style=discord.ButtonStyle.danger, row=1)
    async def remove_from_contest(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            result = await remove_target_from_contest(interaction, self.target)
            await interaction.response.defer()
            await send_followup_text(interaction, result, ephemeral=False)
            await close_manageplayer_menu(interaction)
        except Exception as e:
            await send_followup_text(interaction, str(e), ephemeral=True)

    @discord.ui.button(label="Make Admin", style=discord.ButtonStyle.secondary, row=1)
    async def make_admin(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            result = await give_target_admin_role(interaction, self.target)
            await interaction.response.defer()
            await send_followup_text(interaction, result, ephemeral=False)
        except Exception as e:
            await send_followup_text(interaction, str(e), ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=1)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_manageplayer_menu(interaction)


class NotInContestView(OwnerBoundView):
    """Fallback view shown when target player is not in the PPE contest."""

    def __init__(self, owner_id: int, *, target: ManagedPlayerTarget):
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.target = target

    @discord.ui.button(label="Add to Contest", style=discord.ButtonStyle.success, row=0)
    async def add_to_contest(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            result = await add_target_to_contest(interaction, self.target)
            await interaction.response.defer()
            await send_followup_text(interaction, result, ephemeral=False)
            await close_manageplayer_menu(interaction)
        except Exception as e:
            await send_followup_text(interaction, str(e), ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=0)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_manageplayer_menu(interaction)
