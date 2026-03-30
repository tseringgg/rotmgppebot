"""Player management submenu for /managesniffer."""

from __future__ import annotations

import discord

from menus.managesniffer.common import build_manage_player_sniffer_embed
from menus.managesniffer.services import (
    generate_link_token_for_user,
    load_sniffer_settings,
    revoke_all_tokens_for_user,
)
from menus.managesniffer.validators import resolve_member
from menus.menu_utils import OwnerBoundView
from menus.menu_utils.sniffer_core import core as realmshark_core
from menus.menu_utils.sniffer_shared import build_realmshark_link_instructions


class ManagePlayerSnifferView(OwnerBoundView):
    def __init__(self, owner_id: int, target_user_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This panel belongs to another admin.")
        self.target_user_id = int(target_user_id)

    async def _target_user(self, interaction: discord.Interaction) -> discord.abc.User | None:
        if interaction.guild is None:
            return None
        return interaction.guild.get_member(self.target_user_id)

    @discord.ui.button(label="Generate Token", style=discord.ButtonStyle.success)
    async def generate_token(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        target_user = await self._target_user(interaction)
        if target_user is None:
            await interaction.response.send_message("Player is no longer in this server.", ephemeral=True)
            return

        token = await generate_link_token_for_user(interaction, self.target_user_id)
        await render_manage_player_sniffer_home(
            interaction,
            owner_id=self.owner_id,
            target_user_id=self.target_user_id,
        )
        await interaction.followup.send(
            "Generated token for selected player:\n"
            + build_realmshark_link_instructions(interaction.guild.id if interaction.guild else None, token),
            ephemeral=True,
        )

    @discord.ui.button(label="Unlink Sniffer", style=discord.ButtonStyle.danger)
    async def unlink(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        revoked = await revoke_all_tokens_for_user(interaction, self.target_user_id)
        await render_manage_player_sniffer_home(
            interaction,
            owner_id=self.owner_id,
            target_user_id=self.target_user_id,
        )
        await interaction.followup.send(f"Revoked `{revoked}` token(s) for this player.", ephemeral=True)

    @discord.ui.button(label="Configure Characters", style=discord.ButtonStyle.success)
    async def configure(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        target_member = resolve_member(interaction.guild, self.target_user_id)
        if target_member is None:
            await interaction.response.send_message("Player is no longer in this server.", ephemeral=True)
            return
        await realmshark_core.admin_panel(interaction, target_member, "show_all")

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.managesniffer.submenus.home.views import render_managesniffer_home

        await render_managesniffer_home(interaction, owner_id=self.owner_id)


async def render_manage_player_sniffer_home(
    interaction: discord.Interaction,
    *,
    owner_id: int,
    target_user_id: int,
) -> None:
    target_user = resolve_member(interaction.guild, target_user_id)
    if target_user is None:
        await interaction.response.send_message(
            "Player not found in this server. Provide a valid server member ID/mention.",
            ephemeral=True,
        )
        return

    settings, links = await load_sniffer_settings(interaction)
    embed = build_manage_player_sniffer_embed(
        guild_id=interaction.guild.id if interaction.guild else None,
        target_user=target_user,
        settings=settings,
        links=links,
    )
    view = ManagePlayerSnifferView(owner_id=owner_id, target_user_id=target_user_id)
    await interaction.response.edit_message(embed=embed, view=view)


__all__ = ["ManagePlayerSnifferView", "render_manage_player_sniffer_home"]
