"""Entrypoints for opening /manageplayer views."""

from __future__ import annotations

import discord

from menus.manageplayer.common import (
    active_ppe_for_player,
    add_to_contest_embed,
    target_home_embed,
)
from menus.manageplayer.services import load_target_player_data, target_has_admin_role
from menus.manageplayer.targets import ManagedPlayerTarget, resolve_target
from utils.guild_config import get_max_ppes


async def _refresh_target_member(target: ManagedPlayerTarget, interaction: discord.Interaction) -> None:
    """Refresh the target's member object to ensure roles are up to date."""
    if target.member is not None and interaction.guild is not None:
        try:
            target.member = await interaction.guild.fetch_member(target.user_id)
        except Exception:
            pass


async def open_manageplayer_home(
    interaction: discord.Interaction,
    *,
    owner_id: int,
    target: ManagedPlayerTarget,
    max_ppes: int,
    refresh_member: bool = False,
) -> None:
    from menus.manageplayer.submenus.home.views import ManagePlayerHomeView, NotInContestView

    if refresh_member:
        await _refresh_target_member(target, interaction)

    player_data = await load_target_player_data(interaction, target.user_id)
    active_ppe = active_ppe_for_player(player_data)
    is_target_admin = target_has_admin_role(interaction, target)
    owner_can_manage_admin = bool(interaction.guild and int(owner_id) == int(interaction.guild.owner_id))
    is_in_contest = bool(player_data.is_member or target.has_player_role)

    if target.member is not None and not target.has_player_role:
        view = NotInContestView(owner_id=owner_id, target=target, max_ppes=max_ppes)
        if interaction.response.is_done():
            await interaction.followup.send(embed=add_to_contest_embed(target), view=view, ephemeral=False)
        else:
            await interaction.response.edit_message(embed=add_to_contest_embed(target), view=view)
        return

    embed = target_home_embed(
        target=target,
        player_data=player_data,
        active_ppe=active_ppe,
        max_ppes=max_ppes,
        target_is_admin=is_target_admin,
    )
    view = ManagePlayerHomeView(
        owner_id=owner_id,
        target=target,
        max_ppes=max_ppes,
        target_team_name=player_data.team_name,
        is_target_admin=is_target_admin,
        is_in_contest=is_in_contest,
        owner_can_manage_admin=owner_can_manage_admin,
    )
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view, ephemeral=False)
    else:
        await interaction.response.edit_message(embed=embed, view=view)


async def open_manageplayer_menu(
    interaction: discord.Interaction,
    *,
    member: discord.Member | None = None,
    user_id: str | None = None,
) -> None:
    from menus.manageplayer.submenus.home.views import ManagePlayerHomeView, NotInContestView

    target, error = await resolve_target(interaction, member=member, user_id=user_id)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return

    assert target is not None
    player_data = await load_target_player_data(interaction, target.user_id)
    active_ppe = active_ppe_for_player(player_data)
    max_ppes = await get_max_ppes(interaction)
    is_target_admin = target_has_admin_role(interaction, target)
    owner_can_manage_admin = bool(interaction.guild and int(interaction.user.id) == int(interaction.guild.owner_id))
    is_in_contest = bool(player_data.is_member or target.has_player_role)

    if target.member is not None and not target.has_player_role:
        view = NotInContestView(owner_id=interaction.user.id, target=target, max_ppes=max_ppes)
        await interaction.response.send_message(embed=add_to_contest_embed(target), view=view, ephemeral=False)
        return

    embed = target_home_embed(
        target=target,
        player_data=player_data,
        active_ppe=active_ppe,
        max_ppes=max_ppes,
        target_is_admin=is_target_admin,
    )
    view = ManagePlayerHomeView(
        owner_id=interaction.user.id,
        target=target,
        max_ppes=max_ppes,
        target_team_name=player_data.team_name,
        is_target_admin=is_target_admin,
        is_in_contest=is_in_contest,
        owner_can_manage_admin=owner_can_manage_admin,
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


__all__ = ["open_manageplayer_home", "open_manageplayer_menu"]
