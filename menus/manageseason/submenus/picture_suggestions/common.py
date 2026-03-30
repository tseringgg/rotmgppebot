"""Embed builders for /manageseason picture suggestions submenu."""

from __future__ import annotations

import discord


def _channel_display(guild: discord.Guild | None, channel_id: int) -> str:
    if guild is not None:
        channel = guild.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel.mention
    return f"`{channel_id}`"


def _format_enabled_channels(guild: discord.Guild | None, channel_ids: list[int]) -> str:
    if not channel_ids:
        return "No channels are enabled yet. Use **Add Channels** to start accepting picture suggestions."

    lines = [f"• {_channel_display(guild, channel_id)}" for channel_id in channel_ids]
    rendered = "\n".join(lines)
    if len(rendered) <= 1024:
        return rendered

    truncated = rendered[:1018].rstrip()
    return truncated + "\n..."


def build_picture_suggestions_off_embed() -> discord.Embed:
    """Build the pre-enable landing embed."""
    embed = discord.Embed(
        title="Picture Suggestions",
        description=(
            "Picture Suggestions lets players post a screenshot of an item while hovering it so the item text is visible.\n"
            "When posted in enabled channels, the bot can use that screenshot to suggest matching items."
        ),
        color=discord.Color.dark_teal(),
    )
    embed.add_field(
        name="Turn Item Suggestions On",
        value="Enable this feature for your server and open channel management options.",
        inline=False,
    )
    embed.add_field(
        name="Back",
        value="Return to the main **Manage Season** menu.",
        inline=False,
    )
    return embed


def build_picture_suggestions_manage_embed(
    *,
    guild: discord.Guild | None,
    enabled_channel_ids: list[int],
    missing_channel_ids: list[int],
    non_text_channel_ids: list[int],
) -> discord.Embed:
    """Build the enabled-state management embed."""
    embed = discord.Embed(
        title="Picture Suggestions",
        description=(
            "Picture Suggestions is enabled.\n"
            "Players can post screenshots of hovered items (with item text visible) in the channels below."
        ),
        color=discord.Color.dark_teal(),
    )
    embed.add_field(
        name="Buttons",
        value=(
            "• **Add Channels**: Open a form to add channel mentions/IDs.\n"
            "• **Remove Channels**: Confirm, then open a form to remove selected channels.\n"
            "• **Disable Item Suggestions**: Confirm to clear all enabled channels and turn the feature off.\n"
            "• **Back**: Return to **Manage Season**.\n"
            "• **Close**: Close this menu message."
        ),
        inline=False,
    )

    if missing_channel_ids:
        stale_preview = ", ".join(f"`{channel_id}`" for channel_id in missing_channel_ids[:8])
        suffix = "" if len(missing_channel_ids) <= 8 else f", and {len(missing_channel_ids) - 8} more"
        embed.add_field(
            name="Missing Channels Detected",
            value=(
                "These stored channel IDs no longer exist in this server and are ignored until removed:\n"
                f"{stale_preview}{suffix}"
            ),
            inline=False,
        )

    if non_text_channel_ids:
        wrong_type_preview = ", ".join(f"`{channel_id}`" for channel_id in non_text_channel_ids[:8])
        suffix = "" if len(non_text_channel_ids) <= 8 else f", and {len(non_text_channel_ids) - 8} more"
        embed.add_field(
            name="Non-Text Channels Detected",
            value=(
                "These stored channels are not regular text channels and are ignored:\n"
                f"{wrong_type_preview}{suffix}"
            ),
            inline=False,
        )

    embed.add_field(
        name="Enabled Channels",
        value=_format_enabled_channels(guild, enabled_channel_ids),
        inline=False,
    )
    return embed


def build_remove_channels_confirm_embed() -> discord.Embed:
    """Build the remove-channel confirmation embed."""
    return discord.Embed(
        title="Confirm Remove Channels",
        description=(
            "You are about to remove channels from Picture Suggestions.\n"
            "Press **Continue** to open the removal form, or **Cancel** to return."
        ),
        color=discord.Color.red(),
    )


def build_disable_picture_suggestions_confirm_embed(*, enabled_channel_count: int) -> discord.Embed:
    """Build the disable confirmation embed."""
    return discord.Embed(
        title="Confirm Disable Item Suggestions",
        description=(
            "Disabling Picture Suggestions will clear all enabled channels and turn this feature off.\n"
            f"Channels that will be cleared right now: **{enabled_channel_count}**"
        ),
        color=discord.Color.red(),
    )
