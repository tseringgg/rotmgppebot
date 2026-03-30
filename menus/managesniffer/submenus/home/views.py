"""Home submenu for /managesniffer."""

from __future__ import annotations

import discord

from menus.managesniffer.common import build_managesniffer_home_embed, build_tokens_embed
from menus.managesniffer.modals import ManageSnifferPlayerModal, endpoint_modal_for_settings
from menus.managesniffer.services import load_sniffer_settings, set_sniffer_enabled
from menus.menu_utils import OwnerBoundView
from menus.menu_utils.sniffer_shared import configured_endpoint


class ManageSnifferHomeView(OwnerBoundView):
    def __init__(self, owner_id: int, *, enabled: bool, endpoint: str) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another admin.")
        self.enabled = enabled
        self.endpoint = endpoint

        if enabled:
            self.remove_item(self.enable_sniffer)
        else:
            self.remove_item(self.disable_sniffer)

        self.configure_endpoint.label = "Edit Endpoint" if endpoint else "Add Endpoint"

    @discord.ui.button(label="Enable Sniffer", style=discord.ButtonStyle.success, row=1)
    async def enable_sniffer(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await set_sniffer_enabled(interaction, True)
        await render_managesniffer_home(interaction, owner_id=self.owner_id)

    @discord.ui.button(label="Manage Player's Sniffer", style=discord.ButtonStyle.success, row=0)
    async def manage_player(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(ManageSnifferPlayerModal(self.owner_id))

    @discord.ui.button(label="Manage Tokens", style=discord.ButtonStyle.success, row=0)
    async def manage_tokens(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        _settings, _links = await load_sniffer_settings(interaction)
        from menus.managesniffer.services import load_token_entries
        from menus.managesniffer.submenus.tokens.views import ManageSnifferTokensView

        view = ManageSnifferTokensView(self.owner_id, page=0)
        embed = build_tokens_embed(
            guild=interaction.guild,
            page=0,
            per_page=view.per_page,
            token_entries=await load_token_entries(interaction),
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Change Output Channel", style=discord.ButtonStyle.success, row=0)
    async def change_output_channel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.managesniffer.submenus.output_channel.views import render_output_channel_view

        await render_output_channel_view(interaction, owner_id=self.owner_id)

    @discord.ui.button(label="Add Endpoint", style=discord.ButtonStyle.success, row=0)
    async def configure_endpoint(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings, _links = await load_sniffer_settings(interaction)
        await interaction.response.send_modal(endpoint_modal_for_settings(self.owner_id, settings))

    @discord.ui.button(label="Reset All Sniffer Settings", style=discord.ButtonStyle.danger, row=1)
    async def reset_all(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        embed = discord.Embed(
            title="Confirm Sniffer Reset",
            description=(
                "This will remove all sniffer configuration data for this guild:\n"
                "- revokes all tokens\n"
                "- clears mappings and pending sniffer files\n"
                "- resets enabled state and output channel"
            ),
            color=discord.Color.red(),
        )
        from menus.managesniffer.submenus.danger_confirm.views import SnifferDangerConfirmView

        await interaction.response.edit_message(embed=embed, view=SnifferDangerConfirmView(self.owner_id, "reset"))

    @discord.ui.button(label="Disable Sniffer", style=discord.ButtonStyle.danger, row=1)
    async def disable_sniffer(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        embed = discord.Embed(
            title="Confirm Disable Sniffer",
            description=(
                "Disabling sniffer does not delete existing tokens or mappings.\n"
                "It prevents incoming sniffer ingest requests from being processed and stops monitoring behavior "
                "until re-enabled."
            ),
            color=discord.Color.red(),
        )
        from menus.managesniffer.submenus.danger_confirm.views import SnifferDangerConfirmView

        await interaction.response.edit_message(embed=embed, view=SnifferDangerConfirmView(self.owner_id, "disable"))

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, row=1)
    async def close(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed /managesniffer menu.", embed=None, view=None)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, row=1)
    async def refresh(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await render_managesniffer_home(interaction, owner_id=self.owner_id)


async def render_managesniffer_home(interaction: discord.Interaction, *, owner_id: int) -> None:
    settings, links = await load_sniffer_settings(interaction)
    enabled = bool(settings.get("enabled", False))
    endpoint = configured_endpoint(settings)

    embed = build_managesniffer_home_embed(guild=interaction.guild, settings=settings, links=links)
    view = ManageSnifferHomeView(owner_id=owner_id, enabled=enabled, endpoint=endpoint)
    await interaction.response.edit_message(embed=embed, view=view)


async def send_managesniffer_home(interaction: discord.Interaction) -> None:
    settings, links = await load_sniffer_settings(interaction)
    enabled = bool(settings.get("enabled", False))
    endpoint = configured_endpoint(settings)

    embed = build_managesniffer_home_embed(guild=interaction.guild, settings=settings, links=links)
    view = ManageSnifferHomeView(owner_id=interaction.user.id, enabled=enabled, endpoint=endpoint)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


__all__ = ["ManageSnifferHomeView", "render_managesniffer_home", "send_managesniffer_home"]
