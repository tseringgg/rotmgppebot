"""Shared helper logic for sniffer character configuration and panel flows."""

from __future__ import annotations

from typing import Any

import discord

from menus.menu_utils.sniffer_core import common as realmshark_common
from utils.guild_config import get_realmshark_settings
from utils.realmshark_pending_store import (
    get_pending_character_entry,
    load_pending,
    migrate_legacy_pending_map,
)


def iter_user_links(
    links: dict[str, Any],
    *,
    user_id: int,
    token: str | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    result: list[tuple[str, dict[str, Any]]] = []
    for current_token, link_data in links.items():
        if not isinstance(link_data, dict):
            continue
        if token and current_token != token:
            continue
        try:
            linked_user_id = int(link_data.get("user_id"))
        except (TypeError, ValueError):
            continue
        if linked_user_id != user_id:
            continue
        result.append((current_token, link_data))
    return result


def normalize_bindings(link_data: dict[str, Any]) -> dict[str, int]:
    raw = link_data.get("character_bindings", {})
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, int] = {}
    for raw_character_id, raw_ppe_id in raw.items():
        try:
            character_id = int(raw_character_id)
            ppe_id = int(raw_ppe_id)
        except (TypeError, ValueError):
            continue
        if character_id <= 0 or ppe_id <= 0:
            continue
        normalized[str(character_id)] = ppe_id
    return normalized


def normalize_seasonal_ids(link_data: dict[str, Any]) -> set[str]:
    raw = link_data.get("seasonal_character_ids", [])
    values = raw if isinstance(raw, list) else []
    result: set[str] = set()
    for value in values:
        try:
            character_id = int(value)
        except (TypeError, ValueError):
            continue
        if character_id > 0:
            result.add(str(character_id))
    return result


def normalize_character_metadata(link_data: dict[str, Any]) -> dict[str, dict[str, str]]:
    raw = link_data.get("character_metadata", {})
    if not isinstance(raw, dict):
        return {}

    normalized: dict[str, dict[str, str]] = {}
    for raw_character_id, raw_entry in raw.items():
        try:
            character_id = int(raw_character_id)
        except (TypeError, ValueError):
            continue
        if character_id <= 0 or not isinstance(raw_entry, dict):
            continue

        normalized[str(character_id)] = {
            "character_name": str(raw_entry.get("character_name", "")).strip(),
            "character_class": str(raw_entry.get("character_class", "")).strip(),
        }
    return normalized


def parse_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def collect_character_ids_from_link(link_data: dict[str, Any]) -> set[int]:
    ids: set[int] = set()

    for raw_character_id in normalize_bindings(link_data).keys():
        parsed = parse_positive_int(raw_character_id)
        if parsed is not None:
            ids.add(parsed)

    for raw_character_id in normalize_seasonal_ids(link_data):
        parsed = parse_positive_int(raw_character_id)
        if parsed is not None:
            ids.add(parsed)

    for raw_character_id in normalize_character_metadata(link_data).keys():
        parsed = parse_positive_int(raw_character_id)
        if parsed is not None:
            ids.add(parsed)

    parsed_last_seen = parse_positive_int(link_data.get("last_seen_character_id", 0))
    if parsed_last_seen is not None:
        ids.add(parsed_last_seen)

    return ids


def normalized_class_name(value: Any) -> str:
    if value is None:
        return ""
    raw = str(value).strip()
    return raw.casefold()


def player_ppe_classes(player_data: Any) -> dict[int, str]:
    classes: dict[int, str] = {}
    if not player_data:
        return classes

    for ppe in player_data.ppes:
        ppe_name = getattr(ppe.name, "value", ppe.name)
        classes[int(ppe.id)] = str(ppe_name)
    return classes


async def detected_character_info(
    interaction: discord.Interaction,
    user_links: list[tuple[str, dict[str, Any]]],
    character_id: int,
    target_user_id: int | None = None,
) -> tuple[str, str]:
    key = str(character_id)

    for _token, link_data in user_links:
        metadata = normalize_character_metadata(link_data)
        entry = metadata.get(key)
        if isinstance(entry, dict):
            character_name = str(entry.get("character_name", "")).strip()
            character_class = str(entry.get("character_class", "")).strip()
            if character_name or character_class:
                return character_name, character_class

    resolved_user_id = target_user_id if target_user_id is not None else interaction.user.id
    pending_entry = await get_pending_character_entry(interaction.guild.id, resolved_user_id, character_id)
    if isinstance(pending_entry, dict):
        return (
            str(pending_entry.get("character_name", "")).strip(),
            str(pending_entry.get("character_class", "")).strip(),
        )

    return "", ""


async def migrate_legacy_pending_for_user(
    guild_id: int,
    user_links: list[tuple[str, dict[str, Any]]],
    links: dict[str, Any],
) -> bool:
    changed = False
    for token, link_data in user_links:
        legacy_pending = link_data.get("pending_unmapped_characters", {})
        if not isinstance(legacy_pending, dict) or not legacy_pending:
            continue

        try:
            user_id = int(link_data.get("user_id"))
        except (TypeError, ValueError):
            continue

        await migrate_legacy_pending_map(guild_id, user_id, legacy_pending)
        link_data["pending_unmapped_characters"] = {}
        links[token] = link_data
        changed = True

    return changed


async def player_character_lists(
    interaction: discord.Interaction,
    *,
    user_id: int,
    token: str | None,
) -> tuple[list[int], list[int]]:
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}
    user_links = iter_user_links(links, user_id=user_id, token=token)

    all_ids: set[int] = set()
    mapped_ids: set[int] = set()
    for _token, link_data in user_links:
        all_ids.update(collect_character_ids_from_link(link_data))
        for raw_character_id in normalize_bindings(link_data).keys():
            parsed = parse_positive_int(raw_character_id)
            if parsed is not None:
                mapped_ids.add(parsed)

    pending_data = await load_pending(interaction.guild.id, user_id)
    characters = pending_data.get("characters", {}) if isinstance(pending_data.get("characters"), dict) else {}
    pending_ids: set[int] = set()
    for raw_id in characters.keys():
        parsed = parse_positive_int(raw_id)
        if parsed is not None:
            pending_ids.add(parsed)

    all_ids.update(pending_ids)
    pending_unmapped_ids = sorted(character_id for character_id in pending_ids if character_id not in mapped_ids)
    return sorted(all_ids), pending_unmapped_ids


def resolve_character_id_for_panel(
    mode: str,
    all_character_ids: list[int],
    pending_unmapped_ids: list[int],
    preferred_character_id: int | None = None,
) -> int | None:
    if preferred_character_id is not None and preferred_character_id > 0:
        if mode == "show_pending" and preferred_character_id in pending_unmapped_ids:
            return preferred_character_id
        if mode == "show_all" and preferred_character_id in all_character_ids:
            return preferred_character_id

    if mode == "show_pending":
        if pending_unmapped_ids:
            return pending_unmapped_ids[0]
        return None

    if all_character_ids:
        return all_character_ids[0]

    return None


def format_points(points: float) -> str:
    return realmshark_common.format_points(points)


def build_pending_loot_summary(events: list[dict[str, Any]]) -> str:
    return realmshark_common.build_pending_loot_summary(events)


__all__ = [
    "build_pending_loot_summary",
    "collect_character_ids_from_link",
    "detected_character_info",
    "format_points",
    "iter_user_links",
    "migrate_legacy_pending_for_user",
    "normalize_bindings",
    "normalize_character_metadata",
    "normalize_seasonal_ids",
    "normalized_class_name",
    "parse_positive_int",
    "player_character_lists",
    "player_ppe_classes",
    "resolve_character_id_for_panel",
]
