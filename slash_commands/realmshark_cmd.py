from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict

import discord

from utils.guild_config import get_realmshark_settings, set_realmshark_settings


_REALMSHARK_DEFAULTS: Dict[str, Any] = {
    "enabled": False,
    "mode": "addloot",
    "links": {},
}


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _token_preview(token: str) -> str:
    if len(token) <= 10:
        return token
    return f"{token[:6]}...{token[-4:]}"


async def generate_link_token(interaction: discord.Interaction) -> None:
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}

    token = secrets.token_urlsafe(24)
    links[token] = {
        "user_id": interaction.user.id,
        "created_at": _utc_iso_now(),
        "last_used_at": "",
    }

    settings["links"] = links
    saved = await set_realmshark_settings(interaction, settings)

    mode = saved.get("mode", "addloot")
    await interaction.response.send_message(
        "RealmShark link token created. Keep it private.\n"
        f"guild_id: `{interaction.guild.id if interaction.guild else 'unknown'}`\n"
        f"mode: `{mode}`\n"
        f"link_token: `{token}`\n\n"
        "Set these in RealmShark properties:\n"
        "- realmshark.bridge.enabled=true\n"
        "- realmshark.bridge.guild_id=<your guild id>\n"
        "- realmshark.bridge.link_token=<token>\n"
        "- realmshark.bridge.endpoint=http://<bot-host>:8787/realmshark/ingest",
        ephemeral=True,
    )


async def set_mode(interaction: discord.Interaction, mode: str) -> None:
    if mode not in {"addloot", "addseasonloot"}:
        return await interaction.response.send_message(
            "Invalid mode. Use `addloot` or `addseasonloot`.",
            ephemeral=True,
        )

    settings = await get_realmshark_settings(interaction)
    settings["mode"] = mode
    settings = await set_realmshark_settings(interaction, settings)

    await interaction.response.send_message(
        f"RealmShark mode set to `{settings['mode']}` for this guild.",
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


async def unlink_token(interaction: discord.Interaction, token: str) -> None:
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}

    if token not in links:
        return await interaction.response.send_message("Token not found for this guild.", ephemeral=True)

    del links[token]
    settings["links"] = links
    await set_realmshark_settings(interaction, settings)

    await interaction.response.send_message("RealmShark link token revoked.", ephemeral=True)


async def status(interaction: discord.Interaction) -> None:
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}

    lines = [
        f"enabled: `{settings.get('enabled', False)}`",
        f"mode: `{settings.get('mode', 'addloot')}`",
        f"link_count: `{len(links)}`",
    ]

    previews = []
    for token, link_data in links.items():
        if not isinstance(link_data, dict):
            continue
        previews.append(
            f"- `{_token_preview(token)}` user_id=`{link_data.get('user_id', 'unknown')}` last_used_at=`{link_data.get('last_used_at', '')}`"
        )

    if previews:
        lines.append("linked_tokens:")
        lines.extend(previews[:15])

    await interaction.response.send_message("\n".join(lines), ephemeral=True)


async def reset_all(interaction: discord.Interaction) -> None:
    saved = await set_realmshark_settings(interaction, dict(_REALMSHARK_DEFAULTS))
    await interaction.response.send_message(
        "Reset all RealmShark data for this guild.\n"
        f"enabled: `{saved.get('enabled', False)}`\n"
        f"mode: `{saved.get('mode', 'addloot')}`\n"
        f"link_count: `{len(saved.get('links', {}))}`",
        ephemeral=True,
    )
