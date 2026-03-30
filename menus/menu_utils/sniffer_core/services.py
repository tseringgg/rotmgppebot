"""Service actions used by legacy RealmShark core command handlers."""

from __future__ import annotations

import secrets

import discord

from menus.menu_utils.sniffer_core.common import token_preview, utc_iso_now
from utils.guild_config import get_realmshark_settings, set_realmshark_settings


async def generate_link_token(interaction: discord.Interaction) -> None:
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}

    token = secrets.token_urlsafe(24)
    links[token] = {
        "user_id": interaction.user.id,
        "created_at": utc_iso_now(),
        "last_used_at": "",
        "last_seen_character_id": 0,
        "character_bindings": {},
        "seasonal_character_ids": [],
        "character_metadata": {},
    }

    settings["links"] = links
    await set_realmshark_settings(interaction, settings)

    await interaction.response.send_message(
        "RealmShark link token created. Keep it private.\n"
        f"guild_id: `{interaction.guild.id if interaction.guild else 'unknown'}`\n"
        f"link_token: `{token}`\n\n"
        "Set these in RealmShark properties:\n"
        "- realmshark.bridge.enabled=true\n"
        "- realmshark.bridge.guild_id=<your guild id>\n"
        "- realmshark.bridge.link_token=<token>\n"
        "- realmshark.bridge.endpoint=http://<bot-host>:8080/realmshark/ingest",
        ephemeral=True,
    )


async def set_enabled(interaction: discord.Interaction, enabled: bool) -> None:
    settings = await get_realmshark_settings(interaction)
    settings["enabled"] = bool(enabled)
    settings = await set_realmshark_settings(interaction, settings)

    await interaction.response.send_message(
        f"RealmShark integration is now `{'enabled' if settings['enabled'] else 'disabled'}`.",
        ephemeral=True,
    )


async def set_announce_channel(
    interaction: discord.Interaction,
    channel: discord.TextChannel | None,
) -> None:
    settings = await get_realmshark_settings(interaction)

    if channel is None:
        settings["announce_channel_id"] = 0
        settings = await set_realmshark_settings(interaction, settings)
        await interaction.response.send_message(
            "RealmShark announcement channel reset to default (system channel or first writable text channel).",
            ephemeral=True,
        )
        return

    settings["announce_channel_id"] = int(channel.id)
    settings = await set_realmshark_settings(interaction, settings)

    await interaction.response.send_message(
        f"RealmShark announcement channel set to {channel.mention}.",
        ephemeral=True,
    )


async def unlink_token(interaction: discord.Interaction, token: str) -> None:
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}

    if token not in links:
        await interaction.response.send_message("Token not found for this guild.", ephemeral=True)
        return

    del links[token]
    settings["links"] = links
    await set_realmshark_settings(interaction, settings)

    await interaction.response.send_message("RealmShark link token revoked.", ephemeral=True)


async def status(interaction: discord.Interaction) -> None:
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}

    lines = [
        f"enabled: `{settings.get('enabled', False)}`",
        f"announce_channel_id: `{settings.get('announce_channel_id', 0)}`",
        f"link_count: `{len(links)}`",
    ]

    previews = []
    for token, link_data in links.items():
        if not isinstance(link_data, dict):
            continue
        user_display = f"user_id={link_data.get('user_id', 'unknown')}"
        try:
            linked_user_id = int(link_data.get("user_id"))
            member = interaction.guild.get_member(linked_user_id) if interaction.guild else None
            if member is not None:
                user_display = f"{member.display_name} ({member.mention})"
        except (TypeError, ValueError):
            pass

        previews.append(
            f"- `{token_preview(token)}` -> {user_display} last_used_at=`{link_data.get('last_used_at', '')}`"
        )

    if previews:
        lines.append("linked_tokens:")
        lines.extend(previews[:15])

    await interaction.response.send_message("\n".join(lines), ephemeral=True)
