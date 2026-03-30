"""Output channel submenu for /managesniffer."""

from __future__ import annotations

import discord

from menus.managesniffer.modals import OutputChannelIdModal
from menus.managesniffer.services import load_sniffer_settings, reset_output_channel
from menus.menu_utils import OwnerBoundView
from menus.menu_utils.sniffer_shared import mention_for_channel


class ManageSnifferOutputChannelView(OwnerBoundView):
    def __init__(self, owner_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=300, owner_error="This menu belongs to another admin.")

    @discord.ui.button(label="Set Channel ID", style=discord.ButtonStyle.success, row=0)
    async def set_channel_id(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(OutputChannelIdModal(self.owner_id))

    @discord.ui.button(label="Reset To Default", style=discord.ButtonStyle.secondary, row=0)
    async def reset_default(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await reset_output_channel(interaction)
        await render_output_channel_view(interaction, owner_id=self.owner_id)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=0)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.managesniffer.submenus.home.views import render_managesniffer_home

        await render_managesniffer_home(interaction, owner_id=self.owner_id)


async def render_output_channel_view(interaction: discord.Interaction, *, owner_id: int) -> None:
    settings, _links = await load_sniffer_settings(interaction)
    channel_id = int(settings.get("announce_channel_id", 0) or 0)

    embed = discord.Embed(
        title="Sniffer Output Channel",
        description="Set the output channel by channel ID (or #channel mention), or reset to default.",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Current Channel", value=mention_for_channel(interaction.guild, channel_id), inline=False)

    view = ManageSnifferOutputChannelView(owner_id=owner_id)
    await interaction.response.edit_message(embed=embed, view=view)


__all__ = ["ManageSnifferOutputChannelView", "render_output_channel_view"]
