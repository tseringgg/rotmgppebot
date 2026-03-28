"""Shared helpers for sniffer menu views and actions."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

import discord

from utils.guild_config import get_realmshark_settings, set_realmshark_settings
from utils.realmshark_pending_store import clear_all_pending_for_guild

_REALMSHARK_DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "mode": "addloot",
    "links": {},
    "announce_channel_id": 0,
}


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def token_preview(token: str) -> str:
    if len(token) <= 10:
        return token
    return f"{token[:6]}...{token[-4:]}"


def normalize_links(settings: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_links = settings.get("links", {})
    if not isinstance(raw_links, dict):
        return {}

    links: dict[str, dict[str, Any]] = {}
    for token, data in raw_links.items():
        if isinstance(token, str) and isinstance(data, dict):
            links[token] = data
    return links


def iter_user_links(links: dict[str, dict[str, Any]], user_id: int) -> list[tuple[str, dict[str, Any]]]:
    result: list[tuple[str, dict[str, Any]]] = []
    for token, link_data in links.items():
        try:
            linked_user_id = int(link_data.get("user_id"))
        except (TypeError, ValueError):
            continue
        if linked_user_id == int(user_id):
            result.append((token, link_data))
    return result


def linked_character_counts(user_links: list[tuple[str, dict[str, Any]]]) -> tuple[int, int]:
    mapped = 0
    seasonal = 0
    for _token, link_data in user_links:
        bindings = link_data.get("character_bindings", {})
        if isinstance(bindings, dict):
            mapped += len(bindings)

        seasonal_ids = link_data.get("seasonal_character_ids", [])
        if isinstance(seasonal_ids, list):
            seasonal += len(seasonal_ids)

    return mapped, seasonal


async def load_sniffer_settings(interaction: discord.Interaction) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    settings = await get_realmshark_settings(interaction)
    links = normalize_links(settings)
    return settings, links


async def save_sniffer_settings(
    interaction: discord.Interaction,
    settings: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    settings["links"] = normalize_links(settings)
    saved = await set_realmshark_settings(interaction, settings)
    links = normalize_links(saved)
    return saved, links


async def set_sniffer_enabled(interaction: discord.Interaction, enabled: bool) -> dict[str, Any]:
    settings, _links = await load_sniffer_settings(interaction)
    settings["enabled"] = bool(enabled)
    saved, _ = await save_sniffer_settings(interaction, settings)
    return saved


async def set_output_channel(interaction: discord.Interaction, channel_id: int) -> dict[str, Any]:
    settings, _links = await load_sniffer_settings(interaction)
    settings["announce_channel_id"] = int(channel_id)
    saved, _ = await save_sniffer_settings(interaction, settings)
    return saved


async def reset_output_channel(interaction: discord.Interaction) -> dict[str, Any]:
    return await set_output_channel(interaction, 0)


async def generate_link_token_for_user(interaction: discord.Interaction, user_id: int) -> str:
    settings, links = await load_sniffer_settings(interaction)

    token = secrets.token_urlsafe(24)
    links[token] = {
        "user_id": int(user_id),
        "created_at": _utc_iso_now(),
        "last_used_at": "",
        "last_seen_character_id": 0,
        "character_bindings": {},
        "seasonal_character_ids": [],
        "character_metadata": {},
    }

    settings["links"] = links
    await save_sniffer_settings(interaction, settings)
    return token


async def revoke_token(interaction: discord.Interaction, token: str) -> bool:
    settings, links = await load_sniffer_settings(interaction)
    if token not in links:
        return False

    del links[token]
    settings["links"] = links
    await save_sniffer_settings(interaction, settings)
    return True


async def revoke_all_tokens_for_user(interaction: discord.Interaction, user_id: int) -> int:
    settings, links = await load_sniffer_settings(interaction)

    revoked = 0
    to_delete: list[str] = []
    for token, link_data in links.items():
        try:
            linked_user_id = int(link_data.get("user_id"))
        except (TypeError, ValueError):
            continue
        if linked_user_id == int(user_id):
            to_delete.append(token)

    for token in to_delete:
        del links[token]
        revoked += 1

    if revoked > 0:
        settings["links"] = links
        await save_sniffer_settings(interaction, settings)

    return revoked


async def reset_all_sniffer_settings(interaction: discord.Interaction) -> dict[str, int | bool | str]:
    settings, links = await load_sniffer_settings(interaction)
    links_cleared = len(links)
    pending_files_cleared = await clear_all_pending_for_guild(interaction.guild.id)

    saved, _ = await save_sniffer_settings(interaction, dict(_REALMSHARK_DEFAULTS))

    return {
        "enabled": bool(saved.get("enabled", False)),
        "mode": str(saved.get("mode", "addloot")),
        "announce_channel_id": int(saved.get("announce_channel_id", 0)),
        "link_count": len(normalize_links(saved)),
        "revoked_links": links_cleared,
        "pending_files_removed": pending_files_cleared,
    }


def build_realmshark_link_instructions(guild_id: int | None, token: str) -> str:
    guild_id_text = str(guild_id) if guild_id is not None else "unknown"
    return (
        "Sniffer token created. Keep it private.\\n"
        f"guild_id: `{guild_id_text}`\\n"
        f"link_token: `{token}`\\n\\n"
        "Set these in RealmShark properties:\\n"
        "- realmshark.bridge.enabled=true\\n"
        "- realmshark.bridge.guild_id=<your guild id>\\n"
        "- realmshark.bridge.link_token=<token>\\n"
        "- realmshark.bridge.endpoint=http://<bot-host>:8787/realmshark/ingest"
    )


def mention_for_channel(guild: discord.Guild | None, channel_id: int) -> str:
    if guild is None or channel_id <= 0:
        return "Default (system/first writable text channel)"

    channel = guild.get_channel(channel_id)
    if isinstance(channel, discord.TextChannel):
        return channel.mention
    return str(channel_id)


def sniffer_connected_user_count(links: dict[str, dict[str, Any]]) -> int:
    users: set[int] = set()
    for link_data in links.values():
        try:
            users.add(int(link_data.get("user_id")))
        except (TypeError, ValueError):
            continue
    return len(users)


def build_setup_steps() -> str:
    return "\\n".join(
        [
            "1. Click **Generate Token** to create your private link token.",
            "2. In RealmShark, set `realmshark.bridge.enabled=true`.",
            "3. Set `realmshark.bridge.guild_id=<this server id>` and `realmshark.bridge.link_token=<your token>`.",
            "4. Set `realmshark.bridge.endpoint=http://<bot-host>:8787/realmshark/ingest`.",
            "5. Play on your character, then click **Configure Characters** to map to PPEs.",
        ]
    )
