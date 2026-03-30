"""Views for the player-facing /mysniffer menu."""

from __future__ import annotations

import discord

from menus.menu_utils import OwnerBoundView
from menus.menu_utils.sniffer_core.panel_views import open_panel
from menus.menu_utils.sniffer_token_unlink import TokenUnlinkView
from menus.menu_utils.sniffer_shared import (
    build_realmshark_link_instructions,
)
from menus.mysniffer.common import build_mysniffer_home_embed
from menus.mysniffer.services import generate_user_link_token, load_user_sniffer_state, revoke_user_token


class MySnifferHomeView(OwnerBoundView):
    def __init__(self, owner_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")

    async def _refresh_home(self, interaction: discord.Interaction) -> None:
        settings, user_links = await load_user_sniffer_state(interaction, user_id=interaction.user.id)
        embed = build_mysniffer_home_embed(
            user=interaction.user,
            guild_id=interaction.guild.id if interaction.guild else None,
            settings=settings,
            user_links=user_links,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Generate Token", style=discord.ButtonStyle.success)
    async def generate_token(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings, _user_links = await load_user_sniffer_state(interaction, user_id=interaction.user.id)
        if not bool(settings.get("enabled", False)):
            await interaction.response.send_message(
                "Sniffer is disabled for this server. Ask an admin to enable it in `/managesniffer`.",
                ephemeral=True,
            )
            return

        token = await generate_user_link_token(interaction, user_id=interaction.user.id)
        await self._refresh_home(interaction)
        endpoint = settings.get("endpoint", "")
        await interaction.followup.send(
            build_realmshark_link_instructions(interaction.guild.id if interaction.guild else None, token, endpoint),
            ephemeral=True,
        )

    @discord.ui.button(label="Unlink Sniffer", style=discord.ButtonStyle.danger)
    async def unlink_sniffer(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        _settings, user_links = await load_user_sniffer_state(interaction, user_id=interaction.user.id)
        if not user_links:
            await interaction.response.send_message("You do not have any linked sniffer tokens.", ephemeral=True)
            return

        tokens = [token for token, _ in user_links]
        await interaction.response.send_message(
            "Pick which token to unlink.",
            view=TokenUnlinkView(
                interaction.user.id,
                tokens,
                lambda revoke_interaction, token_value: revoke_user_token(revoke_interaction, token=token_value),
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="Configure Characters", style=discord.ButtonStyle.success)
    async def configure_characters(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings, _user_links = await load_user_sniffer_state(interaction, user_id=interaction.user.id)
        if not bool(settings.get("enabled", False)):
            await interaction.response.send_message(
                "Sniffer is disabled for this server. Ask an admin to enable it in `/managesniffer`.",
                ephemeral=True,
            )
            return

        await open_panel(interaction, "show_all")

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._refresh_home(interaction)
