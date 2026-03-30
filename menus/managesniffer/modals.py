"""Modal classes for /managesniffer workflows."""

from __future__ import annotations

import discord

from menus.managesniffer.services import set_endpoint, set_output_channel
from menus.managesniffer.validators import parse_channel_id, resolve_member_from_input
from menus.menu_utils.sniffer_shared import configured_endpoint


class ManageSnifferPlayerModal(discord.ui.Modal, title="Manage Player's Sniffer"):
    player_id = discord.ui.TextInput(
        label="Player Name",
        placeholder="Discord display name, username, mention, or ID",
        required=True,
        max_length=64,
    )

    def __init__(self, owner_id: int) -> None:
        super().__init__(timeout=180)
        self.owner_id = owner_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This form belongs to another admin.", ephemeral=True)
            return

        if interaction.guild is None:
            await interaction.response.send_message("❌ This action can only be used in a server.", ephemeral=True)
            return

        target_member = resolve_member_from_input(interaction.guild, str(self.player_id.value))
        if target_member is None:
            await interaction.response.send_message(
                "❌ Player not found. Use exact display name/username, mention, or user ID.",
                ephemeral=True,
            )
            return

        from menus.managesniffer.submenus.player_manage.views import render_manage_player_sniffer_home

        await render_manage_player_sniffer_home(
            interaction,
            owner_id=self.owner_id,
            target_user_id=int(target_member.id),
        )


class OutputChannelIdModal(discord.ui.Modal, title="Set Sniffer Output Channel"):
    channel_id = discord.ui.TextInput(
        label="Channel ID or #mention",
        placeholder="123456789012345678 or #channel",
        required=True,
        max_length=64,
    )

    def __init__(self, owner_id: int) -> None:
        super().__init__(timeout=180)
        self.owner_id = owner_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This form belongs to another admin.", ephemeral=True)
            return

        parsed_channel_id = parse_channel_id(str(self.channel_id.value))
        if parsed_channel_id is None:
            await interaction.response.send_message("Provide a valid text channel ID or #channel mention.", ephemeral=True)
            return

        if interaction.guild is None:
            await interaction.response.send_message("This action can only be used in a server.", ephemeral=True)
            return

        channel = interaction.guild.get_channel(parsed_channel_id)
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Channel ID must resolve to a text channel in this server.", ephemeral=True)
            return

        await set_output_channel(interaction, parsed_channel_id)

        from menus.managesniffer.submenus.output_channel.views import render_output_channel_view

        await render_output_channel_view(interaction, owner_id=self.owner_id)


class EndpointUrlModal(discord.ui.Modal, title="Configure Sniffer Endpoint"):
    def __init__(self, owner_id: int, current_endpoint: str) -> None:
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.allow_empty = bool(current_endpoint)
        self.endpoint = discord.ui.TextInput(
            label="Endpoint URL",
            placeholder="http://<bot-host>:8080/realmshark/ingest",
            default=current_endpoint,
            required=not self.allow_empty,
            max_length=300,
        )
        self.add_item(self.endpoint)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This form belongs to another admin.", ephemeral=True)
            return

        endpoint_value = str(self.endpoint.value).strip()
        if not self.allow_empty and not endpoint_value:
            await interaction.response.send_message("Provide an endpoint URL.", ephemeral=True)
            return

        await set_endpoint(interaction, endpoint_value)

        from menus.managesniffer.submenus.home.views import render_managesniffer_home

        await render_managesniffer_home(interaction, owner_id=self.owner_id)

        if endpoint_value:
            await interaction.followup.send(f"Endpoint set to `{endpoint_value}`.", ephemeral=True)
            return

        await interaction.followup.send(
            "Endpoint cleared. The button is now **Add Endpoint** and step 3 falls back to generic setup text.",
            ephemeral=True,
        )


def endpoint_modal_for_settings(owner_id: int, settings: dict) -> EndpointUrlModal:
    """Create the endpoint modal prefilled from current settings."""
    return EndpointUrlModal(owner_id, configured_endpoint(settings))


__all__ = [
    "EndpointUrlModal",
    "ManageSnifferPlayerModal",
    "OutputChannelIdModal",
    "endpoint_modal_for_settings",
]
