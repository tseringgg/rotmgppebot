from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Set

import discord

from utils.guild_config import get_realmshark_settings, set_realmshark_settings
from utils.realmshark_pending_store import clear_pending_character, clear_pending_for_user


def _as_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _normalize_bindings(link_data: Dict[str, Any]) -> Dict[str, int]:
    raw = link_data.get("character_bindings", {})
    if not isinstance(raw, dict):
        return {}

    normalized: Dict[str, int] = {}
    for raw_character_id, raw_ppe_id in raw.items():
        character_id = _as_positive_int(raw_character_id)
        ppe_id = _as_positive_int(raw_ppe_id)
        if character_id is None or ppe_id is None:
            continue
        normalized[str(character_id)] = ppe_id
    return normalized


def _normalize_seasonal_ids(link_data: Dict[str, Any]) -> Set[str]:
    raw = link_data.get("seasonal_character_ids", [])
    values = raw if isinstance(raw, list) else []

    normalized: Set[str] = set()
    for value in values:
        parsed = _as_positive_int(value)
        if parsed is None:
            continue
        normalized.add(str(parsed))
    return normalized


def _normalize_metadata(link_data: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    raw = link_data.get("character_metadata", {})
    if not isinstance(raw, dict):
        return {}

    normalized: Dict[str, Dict[str, str]] = {}
    for raw_character_id, raw_entry in raw.items():
        character_id = _as_positive_int(raw_character_id)
        if character_id is None or not isinstance(raw_entry, dict):
            continue
        normalized[str(character_id)] = {
            "character_name": str(raw_entry.get("character_name", "")),
            "character_class": str(raw_entry.get("character_class", "")),
        }
    return normalized


@dataclass
class RealmSharkCleanupResult:
    tokens_updated: int = 0
    ppe_mappings_removed: int = 0
    seasonal_mappings_removed: int = 0
    metadata_entries_removed: int = 0
    pending_entries_removed: int = 0
    pending_file_removed: bool = False


async def clear_member_character_links(
    interaction: discord.Interaction,
    member_id: int,
) -> RealmSharkCleanupResult:
    """Remove all RealmShark character connections for a specific user."""
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}
    result = RealmSharkCleanupResult()

    for token, link_data in links.items():
        if not isinstance(link_data, dict):
            continue

        linked_user_id = _as_positive_int(link_data.get("user_id"))
        if linked_user_id != member_id:
            continue

        character_bindings = _normalize_bindings(link_data)
        seasonal_ids = _normalize_seasonal_ids(link_data)
        metadata = _normalize_metadata(link_data)

        if not character_bindings and not seasonal_ids and not metadata:
            continue

        result.ppe_mappings_removed += len(character_bindings)
        result.seasonal_mappings_removed += len(seasonal_ids)
        result.metadata_entries_removed += len(metadata)

        link_data["character_bindings"] = {}
        link_data["seasonal_character_ids"] = []
        link_data["character_metadata"] = {}
        link_data["last_seen_character_id"] = 0
        links[token] = link_data
        result.tokens_updated += 1

    if result.tokens_updated > 0:
        settings["links"] = links
        await set_realmshark_settings(interaction, settings)

    result.pending_file_removed = await clear_pending_for_user(interaction.guild.id, member_id)
    return result


async def clear_ppe_character_links(
    interaction: discord.Interaction,
    member_id: int,
    ppe_id: int,
) -> RealmSharkCleanupResult:
    """Remove RealmShark character connections that point to a specific PPE ID."""
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}
    result = RealmSharkCleanupResult()

    removed_character_ids: Set[str] = set()

    for token, link_data in links.items():
        if not isinstance(link_data, dict):
            continue

        linked_user_id = _as_positive_int(link_data.get("user_id"))
        if linked_user_id != member_id:
            continue

        character_bindings = _normalize_bindings(link_data)
        seasonal_ids = _normalize_seasonal_ids(link_data)
        metadata = _normalize_metadata(link_data)

        targeted_ids = {character_id for character_id, bound_ppe_id in character_bindings.items() if bound_ppe_id == ppe_id}
        if not targeted_ids:
            continue

        for character_id in targeted_ids:
            character_bindings.pop(character_id, None)
            if character_id in seasonal_ids:
                seasonal_ids.discard(character_id)
                result.seasonal_mappings_removed += 1
            if character_id in metadata:
                metadata.pop(character_id, None)
                result.metadata_entries_removed += 1

        result.ppe_mappings_removed += len(targeted_ids)
        removed_character_ids.update(targeted_ids)

        last_seen = _as_positive_int(link_data.get("last_seen_character_id", 0))
        if last_seen is not None and str(last_seen) in targeted_ids:
            link_data["last_seen_character_id"] = 0

        link_data["character_bindings"] = character_bindings
        link_data["seasonal_character_ids"] = sorted(seasonal_ids, key=int)
        link_data["character_metadata"] = metadata
        links[token] = link_data
        result.tokens_updated += 1

    if result.tokens_updated > 0:
        settings["links"] = links
        await set_realmshark_settings(interaction, settings)

    for character_id in removed_character_ids:
        cleared = await clear_pending_character(interaction.guild.id, member_id, int(character_id))
        if cleared:
            result.pending_entries_removed += 1

    return result
