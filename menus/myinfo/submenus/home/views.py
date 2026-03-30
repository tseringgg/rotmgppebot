"""Home submenu views for /myinfo."""

from __future__ import annotations

import discord

from menus.menu_utils import OwnerBoundView
from menus.menu_utils.embed_pager_view import OwnerBoundEmbedPagerView
from menus.myquests import open_myquests_menu
from menus.myinfo.common import (
    build_home_embed,
    close_myinfo_menu,
    realmshark_connected_ppe_ids,
    send_ppe_list_markdown_followup,
)
from menus.myinfo.entry import open_myinfo_home
from utils.guild_config import load_guild_config
from utils.player_records import ensure_player_exists, load_player_records


class MyInfoHomeView(OwnerBoundView):
    """Primary dashboard view for opening loot, quest, and character management flows."""

    def __init__(self, owner_id: int, *, max_ppes: int):
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.max_ppes = max_ppes

    @discord.ui.button(label="Show Season Loot", style=discord.ButtonStyle.primary, row=0)
    async def show_season_loot(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.myinfo.submenus.season.views import SeasonLootVariantView

        view = SeasonLootVariantView(owner_id=interaction.user.id, max_ppes=self.max_ppes)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Show Quests", style=discord.ButtonStyle.primary, row=0)
    async def show_quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_myinfo_menu(interaction)
        await open_myquests_menu(interaction)

    @discord.ui.button(label="List PPEs", style=discord.ButtonStyle.primary, row=0)
    async def list_ppes(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        records = await load_player_records(interaction)
        key = ensure_player_exists(records, interaction.user.id)

        if not records[key].ppes:
            view = NoCharactersView(owner_id=interaction.user.id, max_ppes=self.max_ppes)
            await interaction.response.edit_message(embed=view.current_embed(), view=view)
            return

        await close_myinfo_menu(interaction)
        await send_ppe_list_markdown_followup(interaction, records[key])

    @discord.ui.button(label="My Team", style=discord.ButtonStyle.primary, row=0)
    async def my_team(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from slash_commands.myteam_cmd import build_team_embeds

        embeds = await build_team_embeds(
            interaction,
            user_id=interaction.user.id,
            title="My Team",
        )
        view = MyInfoTeamView(owner_id=interaction.user.id, max_ppes=self.max_ppes, embeds=embeds)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Manage Characters", style=discord.ButtonStyle.success, row=1)
    async def manage_characters(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.myinfo.submenus.character.views import ManageCharactersView

        records = await load_player_records(interaction)
        key = ensure_player_exists(records, interaction.user.id)
        player_data = records[key]

        if not player_data.ppes:
            view = NoCharactersView(owner_id=interaction.user.id, max_ppes=self.max_ppes)
            await interaction.response.edit_message(embed=view.current_embed(), view=view)
            return

        guild_config = await load_guild_config(interaction)
        connected_ids = await realmshark_connected_ppe_ids(interaction, interaction.user.id)
        view = ManageCharactersView(
            owner_id=interaction.user.id,
            player_data=player_data,
            connected_ppe_ids=connected_ids,
            guild_config=guild_config,
        )
        await interaction.response.edit_message(embed=view.current_embed(interaction.user), view=view)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/myinfo` menu.", embed=None, view=None)


class MyInfoTeamView(OwnerBoundEmbedPagerView):
    """Team ranking view opened from /myinfo with overflow pagination controls."""

    def __init__(self, owner_id: int, *, max_ppes: int, embeds: list[discord.Embed]) -> None:
        super().__init__(owner_id=owner_id, embeds=embeds, timeout=600)
        self.max_ppes = max_ppes

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await open_myinfo_home(interaction, max_ppes=self.max_ppes)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/myinfo` menu.", embed=None, view=None)


class NoCharactersView(OwnerBoundView):
    """Fallback view shown when a player has no PPE characters yet."""

    def __init__(self, owner_id: int, *, max_ppes: int):
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.max_ppes = max_ppes

    def current_embed(self) -> discord.Embed:
        return discord.Embed(
            title="No Characters",
            description="Create one with **/newppe** to start tracking a character.",
            color=discord.Color.orange(),
        )

    @discord.ui.button(label="New PPE", style=discord.ButtonStyle.success, row=0)
    async def new_ppe(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.myinfo.submenus.character.modals import NewPPEFromMyInfoModal

        await interaction.response.send_modal(
            NewPPEFromMyInfoModal(
                owner_id=interaction.user.id,
                source_message=interaction.message,
                connected_ppe_ids=set(),
            )
        )

    @discord.ui.button(label="Home", style=discord.ButtonStyle.secondary, row=1)
    async def home(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await open_myinfo_home(interaction, max_ppes=self.max_ppes)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/myinfo` menu.", embed=None, view=None)


__all__ = ["MyInfoHomeView", "MyInfoTeamView", "NoCharactersView"]
