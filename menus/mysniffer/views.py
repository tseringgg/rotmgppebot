"""Views for the player-facing /mysniffer menu."""

from __future__ import annotations

import discord

from menus.menu_utils import OwnerBoundView
from menus.menu_utils.sniffer_shared import (
    build_realmshark_link_instructions,
    token_preview,
)
from menus.menu_utils.sniffer_core import core as realmshark_core
from menus.mysniffer.common import build_mysniffer_home_embed
from menus.mysniffer.services import generate_user_link_token, load_user_sniffer_state, revoke_user_token


class _UnlinkTokenSelect(discord.ui.Select):
    def __init__(self, owner_id: int, tokens: list[str]) -> None:
        options = [
            discord.SelectOption(label=token_preview(token), value=token, description="Revoke this token")
            for token in tokens[:25]
        ]
        super().__init__(
            placeholder="Select a token to revoke",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This picker belongs to another user.", ephemeral=True)
            return

        token = self.values[0]
        revoked = await revoke_user_token(interaction, token=token)
        if revoked:
            await interaction.response.edit_message(content="✅ Sniffer token revoked.", embed=None, view=None)
        else:
            await interaction.response.edit_message(content="Token was already removed.", embed=None, view=None)


class UnlinkTokenView(OwnerBoundView):
    def __init__(self, owner_id: int, tokens: list[str]) -> None:
        super().__init__(owner_id=owner_id, timeout=180, owner_error="This unlink menu belongs to another user.")
        self.add_item(_UnlinkTokenSelect(owner_id, tokens))


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
        await interaction.followup.send(
            build_realmshark_link_instructions(interaction.guild.id if interaction.guild else None, token),
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
            view=UnlinkTokenView(interaction.user.id, tokens),
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

        await realmshark_core.open_panel(interaction, "show_all")

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._refresh_home(interaction)
