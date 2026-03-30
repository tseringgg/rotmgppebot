from __future__ import annotations

import discord

from menus.manageteams.services import build_team_detail, build_team_summary_pages
from menus.manageteams.submenus.home.views import ManageTeamsHomeView
from menus.manageteams.submenus.team_detail.views import ManageSingleTeamView


async def open_manage_teams_home(interaction: discord.Interaction, *, owner_id: int) -> None:
    pages = await build_team_summary_pages(interaction)
    view = ManageTeamsHomeView(owner_id=owner_id, pages=pages)
    await interaction.response.edit_message(embed=view.current_embed(), view=view)


async def open_team_manage_view(interaction: discord.Interaction, *, owner_id: int, team_name: str) -> None:
    try:
        actual_name, team, member_rows, include_quest_points = await build_team_detail(interaction, team_name=team_name)
    except ValueError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return

    view = ManageSingleTeamView(
        owner_id=owner_id,
        team_name=actual_name,
        team=team,
        member_rows=member_rows,
        include_quest_points=include_quest_points,
    )
    await interaction.response.edit_message(embed=view.current_embed(), view=view)


async def open_manage_teams_menu(interaction: discord.Interaction) -> None:
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return

    pages = await build_team_summary_pages(interaction)
    view = ManageTeamsHomeView(owner_id=interaction.user.id, pages=pages)
    await interaction.response.send_message(embed=view.current_embed(), view=view, ephemeral=True)
