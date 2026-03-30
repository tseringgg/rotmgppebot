"""Modal workflows for picture suggestion channel add/remove operations."""

from __future__ import annotations

import discord

from menus.manageseason.submenus.picture_suggestions.services import (
    add_picture_suggestion_channels,
    remove_picture_suggestion_channels,
)
from menus.manageseason.submenus.picture_suggestions.validators import parse_channel_ids


async def _refresh_source_message(*, source_message: discord.Message | None, owner_id: int) -> None:
    if source_message is None:
        return

    from menus.manageseason.submenus.picture_suggestions.views import build_picture_suggestions_panel

    embed, view = await build_picture_suggestions_panel(guild=source_message.guild, owner_id=owner_id)
    try:
        await source_message.edit(embed=embed, view=view)
    except discord.HTTPException:
        pass


def _channel_mentions(guild: discord.Guild | None, channel_ids: list[int]) -> str:
    mentions: list[str] = []
    for channel_id in channel_ids:
        if guild is not None:
            channel = guild.get_channel(channel_id)
            if isinstance(channel, discord.TextChannel):
                mentions.append(channel.mention)
                continue
        mentions.append(f"`{channel_id}`")

    if not mentions:
        return "none"

    return ", ".join(mentions)


class AddItemSuggestionsChannelsModal(discord.ui.Modal, title="Add Item Suggestions Channels"):
    """Modal for adding enabled picture suggestion channels."""

    channel_input = discord.ui.TextInput(
        label="Channels To Add",
        placeholder="Paste #channel mentions or channel IDs, separated by spaces, commas, or new lines.",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=1500,
    )

    def __init__(self, *, owner_id: int, source_message: discord.Message | None) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        try:
            parsed_channel_ids = parse_channel_ids(self.channel_input.value)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        result = await add_picture_suggestion_channels(
            guild=interaction.guild,
            channel_ids=parsed_channel_ids,
        )

        lines: list[str] = []
        added_channel_ids = result["added_channel_ids"]
        if added_channel_ids:
            lines.append(f"✅ Added: {_channel_mentions(interaction.guild, added_channel_ids)}")

        already_enabled_ids = result["already_enabled_ids"]
        if already_enabled_ids:
            lines.append(f"ℹ️ Already enabled: {_channel_mentions(interaction.guild, already_enabled_ids)}")

        missing_channel_ids = result["missing_channel_ids"]
        if missing_channel_ids:
            lines.append(f"⚠️ Not found in this server: {_channel_mentions(interaction.guild, missing_channel_ids)}")

        non_text_channel_ids = result["non_text_channel_ids"]
        if non_text_channel_ids:
            lines.append(
                f"⚠️ Skipped non-text channels: {_channel_mentions(interaction.guild, non_text_channel_ids)}"
            )

        if not lines:
            lines.append("No channels were changed.")

        await interaction.response.send_message("\n".join(lines), ephemeral=True)
        await _refresh_source_message(source_message=self.source_message, owner_id=self.owner_id)


class RemoveItemSuggestionsChannelsModal(discord.ui.Modal, title="Remove Item Suggestions Channels"):
    """Modal for removing enabled picture suggestion channels."""

    channel_input = discord.ui.TextInput(
        label="Channels To Remove",
        placeholder="Paste #channel mentions or channel IDs to disable.",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=1500,
    )

    def __init__(self, *, owner_id: int, source_message: discord.Message | None) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        try:
            parsed_channel_ids = parse_channel_ids(self.channel_input.value)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        result = await remove_picture_suggestion_channels(
            guild=interaction.guild,
            channel_ids=parsed_channel_ids,
        )

        lines: list[str] = []
        removed_channel_ids = result["removed_channel_ids"]
        if removed_channel_ids:
            lines.append(f"✅ Removed: {_channel_mentions(interaction.guild, removed_channel_ids)}")

        not_enabled_ids = result["not_enabled_ids"]
        if not_enabled_ids:
            lines.append(f"ℹ️ Not currently enabled: {_channel_mentions(interaction.guild, not_enabled_ids)}")

        missing_channel_ids = result["missing_channel_ids"]
        if missing_channel_ids:
            lines.append(f"⚠️ Not found in this server: {_channel_mentions(interaction.guild, missing_channel_ids)}")

        non_text_channel_ids = result["non_text_channel_ids"]
        if non_text_channel_ids:
            lines.append(
                f"⚠️ Skipped non-text channels: {_channel_mentions(interaction.guild, non_text_channel_ids)}"
            )

        if not lines:
            lines.append("No channels were changed.")

        await interaction.response.send_message("\n".join(lines), ephemeral=True)
        await _refresh_source_message(source_message=self.source_message, owner_id=self.owner_id)


__all__ = ["AddItemSuggestionsChannelsModal", "RemoveItemSuggestionsChannelsModal"]
