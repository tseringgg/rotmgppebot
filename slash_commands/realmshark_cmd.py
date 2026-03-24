from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict

import discord

from utils.guild_config import get_realmshark_settings, set_realmshark_settings
from utils.player_records import ensure_player_exists, load_player_records
from utils.realmshark_ingest import _addloot_for_user_with_ppe
from utils.realmshark_pending_store import (
    clear_all_pending_for_guild,
    clear_pending_character,
    get_pending_character_entry,
    load_pending,
    migrate_legacy_pending_map,
    pop_pending_events_for_character,
)


_REALMSHARK_DEFAULTS: Dict[str, Any] = {
    "enabled": False,
    "mode": "addloot",
    "links": {},
    "announce_channel_id": 0,
}

_CONFIG_ACTIONS = {
    "show",
    "map_ppe",
    "set_seasonal",
    "clear_mapping",
    "show_pending",
    "clear_pending",
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
        "- realmshark.bridge.endpoint=http://<bot-host>:8787/realmshark/ingest",
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
        return await interaction.response.send_message(
            "RealmShark announcement channel reset to default (system channel or first writable text channel).",
            ephemeral=True,
        )

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
            f"- `{_token_preview(token)}` -> {user_display} last_used_at=`{link_data.get('last_used_at', '')}`"
        )

    if previews:
        lines.append("linked_tokens:")
        lines.extend(previews[:15])

    await interaction.response.send_message("\n".join(lines), ephemeral=True)


def _iter_user_links(
    links: Dict[str, Any],
    *,
    user_id: int,
    token: str | None = None,
) -> list[tuple[str, Dict[str, Any]]]:
    result: list[tuple[str, Dict[str, Any]]] = []
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


def _normalize_bindings(link_data: Dict[str, Any]) -> Dict[str, int]:
    raw = link_data.get("character_bindings", {})
    if not isinstance(raw, dict):
        return {}
    normalized: Dict[str, int] = {}
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


def _normalize_seasonal_ids(link_data: Dict[str, Any]) -> set[str]:
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


def _normalize_character_metadata(link_data: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    raw = link_data.get("character_metadata", {})
    if not isinstance(raw, dict):
        return {}

    normalized: Dict[str, Dict[str, str]] = {}
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


def _parse_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _collect_character_ids_from_link(link_data: Dict[str, Any]) -> set[int]:
    ids: set[int] = set()

    for raw_character_id in _normalize_bindings(link_data).keys():
        parsed = _parse_positive_int(raw_character_id)
        if parsed is not None:
            ids.add(parsed)

    for raw_character_id in _normalize_seasonal_ids(link_data):
        parsed = _parse_positive_int(raw_character_id)
        if parsed is not None:
            ids.add(parsed)

    for raw_character_id in _normalize_character_metadata(link_data).keys():
        parsed = _parse_positive_int(raw_character_id)
        if parsed is not None:
            ids.add(parsed)

    parsed_last_seen = _parse_positive_int(link_data.get("last_seen_character_id", 0))
    if parsed_last_seen is not None:
        ids.add(parsed_last_seen)

    return ids


def _normalized_class_name(value: Any) -> str:
    if value is None:
        return ""
    raw = str(value).strip()
    return raw.casefold()


def _player_ppe_classes(player_data: Any) -> Dict[int, str]:
    classes: Dict[int, str] = {}
    if not player_data:
        return classes

    for ppe in player_data.ppes:
        ppe_name = getattr(ppe.name, "value", ppe.name)
        classes[int(ppe.id)] = str(ppe_name)
    return classes


async def _detected_character_info(
    interaction: discord.Interaction,
    user_links: list[tuple[str, Dict[str, Any]]],
    character_id: int,
    target_user_id: int | None = None,
) -> tuple[str, str]:
    key = str(character_id)

    # Prefer metadata sent directly by RealmShark/Tomato.
    for _, link_data in user_links:
        metadata = _normalize_character_metadata(link_data)
        entry = metadata.get(key)
        if isinstance(entry, dict):
            character_name = str(entry.get("character_name", "")).strip()
            character_class = str(entry.get("character_class", "")).strip()
            if character_name or character_class:
                return character_name, character_class

    # Fallback to pending store metadata if this ID is pending.
    resolved_user_id = target_user_id if target_user_id is not None else interaction.user.id
    pending_entry = await get_pending_character_entry(interaction.guild.id, resolved_user_id, character_id)
    if isinstance(pending_entry, dict):
        return (
            str(pending_entry.get("character_name", "")).strip(),
            str(pending_entry.get("character_class", "")).strip(),
        )

    return "", ""


async def _migrate_legacy_pending_for_user(
    guild_id: int,
    user_links: list[tuple[str, Dict[str, Any]]],
    links: Dict[str, Any],
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


async def bindings(interaction: discord.Interaction) -> None:
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}
    user_links = _iter_user_links(links, user_id=interaction.user.id, token=None)

    migrated = await _migrate_legacy_pending_for_user(interaction.guild.id, user_links, links)
    if migrated:
        settings["links"] = links
        await set_realmshark_settings(interaction, settings)
        user_links = _iter_user_links(links, user_id=interaction.user.id, token=None)

    pending_data = await load_pending(interaction.guild.id, interaction.user.id)
    pending_chars = pending_data.get("characters", {}) if isinstance(pending_data.get("characters", {}), dict) else {}

    user_lines = []
    for token, link_data in user_links:

        character_bindings = _normalize_bindings(link_data)
        seasonal_ids = _normalize_seasonal_ids(link_data)
        metadata = _normalize_character_metadata(link_data)

        raw_last_seen = link_data.get("last_seen_character_id", 0)
        try:
            last_seen = int(raw_last_seen or 0)
        except (TypeError, ValueError):
            last_seen = 0
        preview = _token_preview(token)
        user_lines.append(
            f"- token=`{preview}` last_seen_character_id=`{last_seen}` "
            f"ppe_bindings=`{len(character_bindings)}` seasonal_ids=`{len(seasonal_ids)}` pending_unmapped=`{len(pending_chars)}`"
        )
        for character_id, ppe_id in sorted(character_bindings.items(), key=lambda kv: str(kv[0]))[:20]:
            meta = metadata.get(str(character_id), {})
            class_suffix = f" class=`{meta.get('character_class', '')}`" if meta.get("character_class", "") else ""
            name_suffix = f" name=`{meta.get('character_name', '')}`" if meta.get("character_name", "") else ""
            user_lines.append(f"  character_id `{character_id}` -> PPE `#{ppe_id}`{class_suffix}{name_suffix}")
        for character_id in sorted(seasonal_ids, key=int)[:20]:
            meta = metadata.get(str(character_id), {})
            class_suffix = f" class=`{meta.get('character_class', '')}`" if meta.get("character_class", "") else ""
            name_suffix = f" name=`{meta.get('character_name', '')}`" if meta.get("character_name", "") else ""
            user_lines.append(f"  character_id `{character_id}` -> seasonal{class_suffix}{name_suffix}")

    if not user_lines:
        return await interaction.response.send_message(
            "No RealmShark character bindings found for your linked token(s).",
            ephemeral=True,
        )

    await interaction.response.send_message("RealmShark character bindings:\n" + "\n".join(user_lines), ephemeral=True)


async def configure(
    interaction: discord.Interaction,
    action: str,
    character_id: int | None = None,
    ppe_id: int | None = None,
    token: str | None = None,
    target_user_id: int | None = None,
) -> None:
    if action not in _CONFIG_ACTIONS:
        return await interaction.response.send_message("Invalid action.", ephemeral=True)

    managed_user_id = int(target_user_id) if target_user_id is not None else interaction.user.id

    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}
    user_links = _iter_user_links(links, user_id=managed_user_id, token=token)

    if not user_links:
        return await interaction.response.send_message(
            "No linked RealmShark token found for that user.",
            ephemeral=True,
        )

    migrated = await _migrate_legacy_pending_for_user(interaction.guild.id, user_links, links)
    if migrated:
        settings["links"] = links
        await set_realmshark_settings(interaction, settings)
        user_links = _iter_user_links(links, user_id=managed_user_id, token=token)

    if action == "show":
        return await bindings(interaction)

    if character_id is None or character_id <= 0:
        last_seen_candidates: list[int] = []
        for _token, link_data in user_links:
            try:
                last_seen = int(link_data.get("last_seen_character_id", 0) or 0)
            except (TypeError, ValueError):
                last_seen = 0
            if last_seen > 0:
                last_seen_candidates.append(last_seen)
        if last_seen_candidates:
            character_id = last_seen_candidates[-1]

    if character_id is None or character_id <= 0:
        return await interaction.response.send_message(
            "Please provide `character_id` (or play once so there is a last seen character).",
            ephemeral=True,
        )

    character_key = str(character_id)

    records = await load_player_records(interaction)
    key = ensure_player_exists(records, managed_user_id)
    player_data = records.get(key)
    user_ppe_ids = {ppe.id for ppe in (player_data.ppes if player_data else [])}
    ppe_class_by_id = _player_ppe_classes(player_data)
    detected_character_name, detected_character_class = await _detected_character_info(
        interaction,
        user_links,
        character_id,
    )

    if action == "map_ppe":
        if ppe_id is None or ppe_id <= 0:
            return await interaction.response.send_message("Please provide a valid `ppe_id`.", ephemeral=True)
        if ppe_id not in user_ppe_ids:
            return await interaction.response.send_message(
                f"You do not own PPE #{ppe_id}. Use `/myppes` to check your IDs.",
                ephemeral=True,
            )

        if detected_character_class:
            ppe_class = ppe_class_by_id.get(int(ppe_id), "")
            if _normalized_class_name(ppe_class) and _normalized_class_name(detected_character_class):
                if _normalized_class_name(ppe_class) != _normalized_class_name(detected_character_class):
                    return await interaction.response.send_message(
                        (
                            "❌ Class mismatch. "
                            f"Character `{character_id}` is `{detected_character_class}`"
                            + (f" ({detected_character_name})" if detected_character_name else "")
                            + f", but PPE `#{ppe_id}` is `{ppe_class}`."
                        ),
                        ephemeral=True,
                    )

    changed = 0
    applied_events_total = 0
    cleared_pending_total = 0

    for current_token, link_data in user_links:
        character_bindings = _normalize_bindings(link_data)
        seasonal_ids = _normalize_seasonal_ids(link_data)
        if action == "map_ppe":
            assert ppe_id is not None
            character_bindings[character_key] = ppe_id
            seasonal_ids.discard(character_key)
            events = await pop_pending_events_for_character(interaction.guild.id, managed_user_id, character_id)
            for event in events:
                if not isinstance(event, dict):
                    continue
                item_name = str(event.get("item_name", "")).strip()
                if not item_name:
                    continue
                item_shiny = bool(event.get("shiny", False))
                item_divine = bool(event.get("divine", False))
                await _addloot_for_user_with_ppe(
                    interaction.guild.id,
                    managed_user_id,
                    item_name,
                    item_divine,
                    item_shiny,
                    ppe_id,
                )
                applied_events_total += 1
            changed += 1
        elif action == "set_seasonal":
            seasonal_ids.add(character_key)
            if character_key in character_bindings:
                del character_bindings[character_key]
            cleared = await clear_pending_character(interaction.guild.id, managed_user_id, character_id)
            if cleared:
                cleared_pending_total += 1
                changed += 1
            changed += 1
        elif action == "clear_mapping":
            if character_key in character_bindings:
                del character_bindings[character_key]
                changed += 1
            if character_key in seasonal_ids:
                seasonal_ids.discard(character_key)
                changed += 1
        elif action == "clear_pending":
            cleared = await clear_pending_character(interaction.guild.id, managed_user_id, character_id)
            if cleared:
                changed += 1
        elif action == "show_pending":
            entry = await get_pending_character_entry(interaction.guild.id, managed_user_id, character_id)
            if not isinstance(entry, dict):
                continue
            events = entry.get("events", []) if isinstance(entry.get("events", []), list) else []
            lines = [
                f"token `{_token_preview(current_token)}` pending events: `{len(events)}`",
                f"first_seen: `{entry.get('first_seen_at', '')}`",
                f"last_seen: `{entry.get('last_seen_at', '')}`",
                f"character_name: `{entry.get('character_name', '')}`",
                f"character_class: `{entry.get('character_class', '')}`",
            ]
            for event in events[-20:]:
                if not isinstance(event, dict):
                    continue
                lines.append(
                    f"- {event.get('item_rarity', 'rare')} {event.get('item_name', '')} "
                    f"(shiny={bool(event.get('shiny', False))}, divine={bool(event.get('divine', False))})"
                )
            await interaction.response.send_message(
                f"Pending unmapped log for character_id `{character_id}`:\n" + "\n".join(lines),
                ephemeral=True,
            )
            return

        link_data["character_bindings"] = character_bindings
        link_data["seasonal_character_ids"] = sorted(seasonal_ids, key=int)
        links[current_token] = link_data

    if action == "show_pending":
        return await interaction.response.send_message(
            f"No pending events found for character_id `{character_id}`.",
            ephemeral=True,
        )

    if changed <= 0:
        return await interaction.response.send_message("No changes were needed.", ephemeral=True)

    settings["links"] = links
    await set_realmshark_settings(interaction, settings)

    action_label = {
        "map_ppe": (
            f"Mapped character_id `{character_id}` to PPE `#{ppe_id}`"
            + (
                f" and applied `{applied_events_total}` pending loot event(s)"
                if applied_events_total > 0
                else ""
            )
        ),
        "set_seasonal": f"Mapped character_id `{character_id}` to seasonal and cleared pending data",
        "clear_mapping": f"Cleared mapping for character_id `{character_id}`",
        "clear_pending": f"Cleared pending log for character_id `{character_id}`",
    }.get(action, "Updated configuration")

    if action == "set_seasonal" and cleared_pending_total == 0:
        action_label = f"Mapped character_id `{character_id}` to seasonal"

    await interaction.response.send_message(
        f"✅ {action_label}.",
        ephemeral=True,
    )


async def admin_view(interaction: discord.Interaction, member: discord.Member) -> None:
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}
    user_links = _iter_user_links(links, user_id=member.id, token=None)

    if not user_links:
        return await interaction.response.send_message(
            f"No RealmShark links found for {member.mention}.",
            ephemeral=True,
        )

    migrated = await _migrate_legacy_pending_for_user(interaction.guild.id, user_links, links)
    if migrated:
        settings["links"] = links
        await set_realmshark_settings(interaction, settings)
        user_links = _iter_user_links(links, user_id=member.id, token=None)

    pending_data = await load_pending(interaction.guild.id, member.id)
    pending_chars = pending_data.get("characters", {}) if isinstance(pending_data.get("characters", {}), dict) else {}

    lines = [f"RealmShark admin view for {member.mention}:"]
    for token, link_data in user_links:
        bindings = _normalize_bindings(link_data)
        seasonal_ids = _normalize_seasonal_ids(link_data)
        metadata = _normalize_character_metadata(link_data)
        lines.append(
            f"- token `{_token_preview(token)}` ppe_bindings=`{len(bindings)}` "
            f"seasonal=`{len(seasonal_ids)}` pending=`{len(pending_chars)}` "
            f"last_seen=`{link_data.get('last_seen_character_id', 0)}`"
        )
        for character_id, ppe_id in sorted(bindings.items(), key=lambda kv: str(kv[0]))[:10]:
            meta = metadata.get(str(character_id), {})
            class_suffix = f" class=`{meta.get('character_class', '')}`" if meta.get("character_class", "") else ""
            name_suffix = f" name=`{meta.get('character_name', '')}`" if meta.get("character_name", "") else ""
            lines.append(f"  character_id `{character_id}` -> PPE `#{ppe_id}`{class_suffix}{name_suffix}")
        for character_id in sorted(seasonal_ids, key=int)[:10]:
            meta = metadata.get(str(character_id), {})
            class_suffix = f" class=`{meta.get('character_class', '')}`" if meta.get("character_class", "") else ""
            name_suffix = f" name=`{meta.get('character_name', '')}`" if meta.get("character_name", "") else ""
            lines.append(f"  character_id `{character_id}` -> seasonal{class_suffix}{name_suffix}")
        for character_id, entry in sorted(pending_chars.items(), key=lambda kv: int(kv[0]))[:10]:
            events = entry.get("events", []) if isinstance(entry.get("events", []), list) else []
            lines.append(f"  pending character_id `{character_id}` events=`{len(events)}`")

    await interaction.response.send_message("\n".join(lines), ephemeral=True)


async def _admin_clear_all_mappings_for_member(
    interaction: discord.Interaction,
    member_id: int,
) -> tuple[int, int, int, int]:
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}

    tokens_updated = 0
    ppe_mappings_removed = 0
    seasonal_mappings_removed = 0
    metadata_entries_removed = 0

    for token, link_data in links.items():
        if not isinstance(link_data, dict):
            continue

        try:
            linked_user_id = int(link_data.get("user_id"))
        except (TypeError, ValueError):
            continue
        if linked_user_id != member_id:
            continue

        character_bindings = _normalize_bindings(link_data)
        seasonal_ids = _normalize_seasonal_ids(link_data)
        metadata = _normalize_character_metadata(link_data)

        removed_for_token = len(character_bindings) + len(seasonal_ids) + len(metadata)
        if removed_for_token <= 0:
            continue

        ppe_mappings_removed += len(character_bindings)
        seasonal_mappings_removed += len(seasonal_ids)
        metadata_entries_removed += len(metadata)

        link_data["character_bindings"] = {}
        link_data["seasonal_character_ids"] = []
        link_data["character_metadata"] = {}
        links[token] = link_data
        tokens_updated += 1

    if tokens_updated > 0:
        settings["links"] = links
        await set_realmshark_settings(interaction, settings)

    return tokens_updated, ppe_mappings_removed, seasonal_mappings_removed, metadata_entries_removed


class _RealmSharkAdminConfirmClearMappingsView(discord.ui.View):
    def __init__(self, owner_id: int, target_member_id: int) -> None:
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.target_member_id = target_member_id

    async def _ensure_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This confirmation belongs to another admin.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm Remove All Mappings", style=discord.ButtonStyle.danger)
    async def confirm(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        if not await self._ensure_owner(interaction):
            return

        tokens_updated, ppe_removed, seasonal_removed, metadata_removed = await _admin_clear_all_mappings_for_member(
            interaction,
            self.target_member_id,
        )

        if tokens_updated <= 0:
            await interaction.response.edit_message(
                content="No mappings were found to remove for this player.",
                view=None,
            )
            return

        await interaction.response.edit_message(
            content=(
                "✅ Removed all RealmShark mappings for this player.\n"
                f"Tokens updated: `{tokens_updated}`\n"
                f"PPE mappings removed: `{ppe_removed}`\n"
                f"Seasonal mappings removed: `{seasonal_removed}`\n"
                f"Character metadata entries removed: `{metadata_removed}`"
            ),
            view=None,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        if not await self._ensure_owner(interaction):
            return
        await interaction.response.edit_message(content="Cancelled mapping removal.", view=None)


async def _admin_character_entries(interaction: discord.Interaction, mode: str) -> list[tuple[int, int]]:
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}

    user_to_links: Dict[int, list[dict[str, Any]]] = {}
    for _token, link_data in links.items():
        if not isinstance(link_data, dict):
            continue
        linked_user_id = _parse_positive_int(link_data.get("user_id"))
        if linked_user_id is None:
            continue
        user_to_links.setdefault(linked_user_id, []).append(link_data)

    entries: list[tuple[int, int]] = []
    for user_id, link_data_list in user_to_links.items():
        all_ids: set[int] = set()
        mapped_ids: set[int] = set()

        for link_data in link_data_list:
            all_ids.update(_collect_character_ids_from_link(link_data))
            for raw_character_id in _normalize_bindings(link_data).keys():
                parsed = _parse_positive_int(raw_character_id)
                if parsed is not None:
                    mapped_ids.add(parsed)

        pending_data = await load_pending(interaction.guild.id, user_id)
        pending_chars = pending_data.get("characters", {}) if isinstance(pending_data.get("characters"), dict) else {}
        pending_ids: set[int] = set()
        for raw_character_id in pending_chars.keys():
            parsed = _parse_positive_int(raw_character_id)
            if parsed is not None:
                pending_ids.add(parsed)

        all_ids.update(pending_ids)
        pending_unmapped_ids = sorted(character_id for character_id in pending_ids if character_id not in mapped_ids)
        active_ids = pending_unmapped_ids if mode == "show_pending" else sorted(all_ids)

        for character_id in active_ids:
            entries.append((user_id, character_id))

    return sorted(entries, key=lambda item: (item[0], item[1]))


async def _build_admin_panel_embed(
    interaction: discord.Interaction,
    *,
    target_user_id: int,
    character_id: int,
    mode: str,
    index: int,
    total: int,
) -> discord.Embed:
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}
    user_links = _iter_user_links(links, user_id=target_user_id, token=None)

    mapped_ppe: int | None = None
    seasonal = False
    for _, link_data in user_links:
        bindings = _normalize_bindings(link_data)
        seasonal_ids = _normalize_seasonal_ids(link_data)
        key = str(character_id)
        if key in bindings:
            mapped_ppe = bindings[key]
        if key in seasonal_ids:
            seasonal = True

    detected_name, detected_class = await _detected_character_info(
        interaction,
        user_links,
        character_id,
        target_user_id=target_user_id,
    )

    pending_entry = await get_pending_character_entry(interaction.guild.id, target_user_id, character_id)
    pending_count = 0
    if isinstance(pending_entry, dict):
        events = pending_entry.get("events", []) if isinstance(pending_entry.get("events", []), list) else []
        pending_count = len(events)

    status = "Unmapped (currently seasonal by default)"
    if mapped_ppe is not None:
        status = f"Mapped to PPE #{mapped_ppe}"
    elif seasonal:
        status = "Explicitly set to seasonal"

    records = await load_player_records(interaction)
    player_data = records.get(str(target_user_id))
    ppe_list = sorted([ppe.id for ppe in (player_data.ppes if player_data else [])])
    ppe_text = ", ".join(f"#{ppe_id}" for ppe_id in ppe_list) if ppe_list else "No PPEs yet"

    member = interaction.guild.get_member(target_user_id) if interaction.guild else None
    member_label = member.display_name if member else f"User {target_user_id}"
    member_mention = member.mention if member else str(target_user_id)

    links_summary: list[str] = []
    for token, link_data in user_links:
        bindings = _normalize_bindings(link_data)
        seasonal_ids = _normalize_seasonal_ids(link_data)
        links_summary.append(
            f"`{_token_preview(token)}` - {len(bindings)} PPE bindings, {len(seasonal_ids)} seasonal"
        )
    links_text = "\n".join(links_summary) if links_summary else "No active links"

    embed = discord.Embed(
        title="RealmShark Admin Panel",
        description=(
            f"Current Mode: **{'Show Pending' if mode == 'show_pending' else 'Show All'}**\n"
            f"Player: **{member_label}** ({member_mention})\n"
            f"Character ID: **{character_id}**\n"
            f"Detected Character: **{detected_name or 'Unknown'}**\n"
            f"Detected Class: **{detected_class or 'Unknown'}**\n"
            f"Current status: **{status}**\n"
            f"Pending Loot Events: **{pending_count}**"
        ),
        color=discord.Color.blurple(),
    )
    embed.add_field(name=f"{member_label}'s PPE IDs", value=ppe_text, inline=False)
    embed.add_field(name="RealmShark Links", value=links_text, inline=False)
    embed.set_footer(text=f"Entry {index + 1}/{total}. Remove mappings applies to the current player.")
    return embed


class RealmSharkAdminPanelView(discord.ui.View):
    def __init__(self, owner_id: int, mode: str, entries: list[tuple[int, int]]) -> None:
        super().__init__(timeout=600)
        self.owner_id = owner_id
        self.mode = mode
        self.entries = entries
        self.index = 0

    async def _ensure_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This admin panel belongs to another admin.", ephemeral=True)
            return False
        return True

    async def _refresh_entries(self, interaction: discord.Interaction) -> bool:
        current = self.entries[self.index] if self.entries and 0 <= self.index < len(self.entries) else None
        self.entries = await _admin_character_entries(interaction, self.mode)
        if not self.entries:
            label = "pending unmapped" if self.mode == "show_pending" else "known"
            await interaction.response.edit_message(
                content=f"No {label} RealmShark character entries found.",
                embed=None,
                view=None,
            )
            return False

        if current in self.entries:
            self.index = self.entries.index(current)
        else:
            self.index = 0
        return True

    async def _render(self, interaction: discord.Interaction) -> None:
        target_user_id, character_id = self.entries[self.index]
        embed = await _build_admin_panel_embed(
            interaction,
            target_user_id=target_user_id,
            character_id=character_id,
            mode=self.mode,
            index=self.index,
            total=len(self.entries),
        )
        await interaction.response.edit_message(content=None, embed=embed, view=self)

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._ensure_owner(interaction):
            return
        if not await self._refresh_entries(interaction):
            return
        self.index = (self.index - 1) % len(self.entries)
        await self._render(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._ensure_owner(interaction):
            return
        if not await self._refresh_entries(interaction):
            return
        self.index = (self.index + 1) % len(self.entries)
        await self._render(interaction)

    @discord.ui.button(label="Show Pending", style=discord.ButtonStyle.primary)
    async def show_pending(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._ensure_owner(interaction):
            return
        self.mode = "show_pending"
        if not await self._refresh_entries(interaction):
            return
        await self._render(interaction)

    @discord.ui.button(label="Show All", style=discord.ButtonStyle.primary)
    async def show_all(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._ensure_owner(interaction):
            return
        self.mode = "show_all"
        if not await self._refresh_entries(interaction):
            return
        await self._render(interaction)

    @discord.ui.button(label="Remove All Mappings", style=discord.ButtonStyle.danger)
    async def remove_all_mappings(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._ensure_owner(interaction):
            return
        if not self.entries:
            return await interaction.response.send_message("No active player selection to clear.", ephemeral=True)

        target_user_id, _character_id = self.entries[self.index]
        await interaction.response.send_message(
            "⚠️ This will remove all PPE/seasonal character mappings and stored character metadata for the selected player across all linked tokens.",
            view=_RealmSharkAdminConfirmClearMappingsView(self.owner_id, target_user_id),
            ephemeral=True,
        )

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._ensure_owner(interaction):
            return
        if not await self._refresh_entries(interaction):
            return
        await self._render(interaction)


async def admin_panel(interaction: discord.Interaction, member: discord.Member, mode: str) -> None:
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)

    if mode not in {"show_all", "show_pending"}:
        return await interaction.response.send_message("Invalid panel mode. Use Show All or Show Pending.", ephemeral=True)

    all_ids, pending_unmapped_ids = await _player_character_lists(
        interaction,
        user_id=member.id,
        token=None,
    )
    active_ids = pending_unmapped_ids if mode == "show_pending" else all_ids

    resolved_character_id = await _resolve_character_id_for_panel(
        interaction,
        mode,
        active_ids,
        pending_unmapped_ids,
    )

    if resolved_character_id is None:
        if mode == "show_pending":
            return await interaction.response.send_message(
                f"No pending unmapped character IDs found for {member.mention}.",
                ephemeral=True,
            )
        return await interaction.response.send_message(
            f"No character IDs found yet for {member.mention}.",
            ephemeral=True,
        )

    view = RealmSharkConfigurePanelView(
        interaction.user.id,
        member.id,
        resolved_character_id,
        None,
        mode,
    )
    embed = await _build_panel_embed(
        interaction,
        resolved_character_id,
        None,
        mode=mode,
        all_character_ids=active_ids,
        pending_ids=pending_unmapped_ids,
        target_user_id=member.id,
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def _resolve_character_id_for_panel(
    interaction: discord.Interaction,
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


async def _player_character_lists(
    interaction: discord.Interaction,
    *,
    user_id: int,
    token: str | None,
)-> tuple[list[int], list[int]]:
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}
    user_links = _iter_user_links(links, user_id=user_id, token=token)

    all_ids: set[int] = set()
    mapped_ids: set[int] = set()
    for _, link_data in user_links:
        all_ids.update(_collect_character_ids_from_link(link_data))
        for raw_character_id in _normalize_bindings(link_data).keys():
            parsed = _parse_positive_int(raw_character_id)
            if parsed is not None:
                mapped_ids.add(parsed)

    pending_data = await load_pending(interaction.guild.id, user_id)
    characters = pending_data.get("characters", {}) if isinstance(pending_data.get("characters"), dict) else {}
    pending_ids: set[int] = set()
    for raw_id in characters.keys():
        parsed = _parse_positive_int(raw_id)
        if parsed is not None:
            pending_ids.add(parsed)

    all_ids.update(pending_ids)
    pending_unmapped_ids = sorted(character_id for character_id in pending_ids if character_id not in mapped_ids)
    return sorted(all_ids), pending_unmapped_ids


async def _build_panel_embed(
    interaction: discord.Interaction,
    character_id: int,
    token: str | None,
    mode: str,
    all_character_ids: list[int],
    pending_ids: list[int] | None = None,
    target_user_id: int | None = None,
) -> discord.Embed:
    managed_user_id = int(target_user_id) if target_user_id is not None else interaction.user.id
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}
    user_links = _iter_user_links(links, user_id=managed_user_id, token=token)

    mapped_ppe: int | None = None
    seasonal = False
    detected_name = ""
    detected_class = ""
    for _, link_data in user_links:
        bindings = _normalize_bindings(link_data)
        seasonal_ids = _normalize_seasonal_ids(link_data)
        metadata = _normalize_character_metadata(link_data)
        key = str(character_id)
        if key in bindings:
            mapped_ppe = bindings[key]
        meta = metadata.get(key)
        if isinstance(meta, dict):
            detected_name = detected_name or str(meta.get("character_name", "")).strip()
            detected_class = detected_class or str(meta.get("character_class", "")).strip()
        if key in seasonal_ids:
            seasonal = True

    pending_entry = await get_pending_character_entry(interaction.guild.id, managed_user_id, character_id)
    pending_count = 0
    if isinstance(pending_entry, dict):
        events = pending_entry.get("events", []) if isinstance(pending_entry.get("events", []), list) else []
        pending_count = len(events)
        detected_name = detected_name or str(pending_entry.get("character_name", "")).strip()
        detected_class = detected_class or str(pending_entry.get("character_class", "")).strip()

    records = await load_player_records(interaction)
    key = ensure_player_exists(records, managed_user_id)
    player_data = records.get(key)
    ppe_list = sorted([ppe.id for ppe in (player_data.ppes if player_data else [])])
    ppe_text = ", ".join(f"#{ppe_id}" for ppe_id in ppe_list) if ppe_list else "No PPEs yet"

    managed_header = ""
    ppe_field_name = "Your PPE IDs"
    if managed_user_id != interaction.user.id:
        managed_member = interaction.guild.get_member(managed_user_id) if interaction.guild else None
        managed_display = managed_member.display_name if managed_member is not None else str(managed_user_id)
        managed_header = f"Managing User: **{managed_display}**\n"
        ppe_field_name = f"{managed_display}'s PPE IDs"

    status = "Unmapped (currently seasonal by default)"
    if mapped_ppe is not None:
        status = f"Mapped to PPE #{mapped_ppe}"
    elif seasonal:
        status = "Explicitly set to seasonal"

    pending_position = "Not in pending list"
    pending_id_list = pending_ids if isinstance(pending_ids, list) else []
    if pending_id_list:
        if character_id in pending_id_list:
            idx = pending_id_list.index(character_id) + 1
            pending_position = f"{idx}/{len(pending_id_list)}"
        else:
            pending_position = f"{len(pending_id_list)} pending IDs available"

    embed = discord.Embed(
        title="RealmShark Character Mapping Panel",
        description=(
            managed_header
            +
            f"Current Mode: **{'Show Pending' if mode == 'show_pending' else 'Show All'}**\n"
            f"Character ID: **{character_id}**\n"
            f"Detected Character: **{detected_name or 'Unknown'}**\n"
            f"Detected Class: **{detected_class or 'Unknown'}**\n"
            f"Current status: **{status}**\n"
            f"Pending unmapped loot events: **{pending_count}**\n"
            f"Pending queue position: **{pending_position}**\n"
            f"Characters in this mode: **{len(all_character_ids)}**"
        ),
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name=ppe_field_name,
        value=ppe_text,
        inline=False,
    )
    embed.add_field(
        name="How to use this panel",
        value=(
            "• Use `Prev` / `Next` to cycle character IDs.\n"
            "• `Map To PPE` routes this character and auto-applies pending loot.\n"
            "• `Set Seasonal` keeps this character as seasonal only.\n"
            "• `Show Pending` and `Show All` switch panel modes.\n"
            "• `Clear Pending` discards all pending events for this character.\n"
            "• `Refresh` reloads the panel status."
        ),
        inline=False,
    )
    return embed


def _format_points(points: float) -> str:
    return str(int(points)) if points == int(points) else f"{points:.1f}"


def _build_pending_loot_summary(events: list[dict[str, Any]]) -> str:
    if not events:
        return "No pending unmapped loot for this character yet."

    by_name: Dict[str, int] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        item_name = str(event.get("item_name", "")).strip() or "Unknown Item"
        by_name[item_name] = by_name.get(item_name, 0) + 1

    top_items = sorted(by_name.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    top_items_text = ", ".join(f"{name} x{count}" for name, count in top_items)

    recent_names: list[str] = []
    for event in events[-3:]:
        if not isinstance(event, dict):
            continue
        item_name = str(event.get("item_name", "")).strip() or "Unknown Item"
        recent_names.append(item_name)

    recent_text = ", ".join(recent_names) if recent_names else "None"
    return (
        f"{len(events)} pending drop(s). "
        f"Top loot: {top_items_text or 'None'}. "
        f"Most recent: {recent_text}."
    )


class _MapToPPESelect(discord.ui.Select):
    def __init__(
        self,
        owner_id: int,
        target_user_id: int,
        character_id: int,
        token: str | None,
        ppe_options: list[tuple[int, str, float]],
    ) -> None:
        options: list[discord.SelectOption] = []
        for ppe_id, ppe_name, ppe_points in ppe_options[:25]:
            options.append(
                discord.SelectOption(
                    label=f"PPE #{ppe_id}: {ppe_name}",
                    value=str(ppe_id),
                    description=f"Current points: {_format_points(float(ppe_points))}",
                )
            )

        super().__init__(
            placeholder="Select which PPE this character should map to",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.owner_id = owner_id
        self.target_user_id = target_user_id
        self.character_id = character_id
        self.token = token

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("This picker belongs to another user.", ephemeral=True)

        try:
            ppe_id = int(self.values[0])
        except (TypeError, ValueError, IndexError):
            return await interaction.response.send_message("Please choose a valid PPE option.", ephemeral=True)

        # Mapping now also auto-applies all pending events for this character.
        await configure(
            interaction,
            "map_ppe",
            character_id=self.character_id,
            ppe_id=ppe_id,
            token=self.token,
            target_user_id=self.target_user_id,
        )


class RealmSharkMapToPPEView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        target_user_id: int,
        character_id: int,
        token: str | None,
        ppe_options: list[tuple[int, str, float]],
    ) -> None:
        super().__init__(timeout=300)
        self.add_item(_MapToPPESelect(owner_id, target_user_id, character_id, token, ppe_options))


class RealmSharkConfigurePanelView(discord.ui.View):
    def __init__(self, owner_id: int, target_user_id: int, character_id: int, token: str | None, mode: str) -> None:
        super().__init__(timeout=600)
        self.owner_id = owner_id
        self.target_user_id = target_user_id
        self.character_id = character_id
        self.token = token
        self.mode = mode

    async def _active_character_ids(self, interaction: discord.Interaction) -> tuple[list[int], list[int], list[int]]:
        all_ids, pending_unmapped_ids = await _player_character_lists(
            interaction,
            user_id=self.target_user_id,
            token=self.token,
        )
        active_ids = pending_unmapped_ids if self.mode == "show_pending" else all_ids
        return active_ids, all_ids, pending_unmapped_ids

    async def _refresh_panel(self, interaction: discord.Interaction) -> None:
        active_ids, _all_ids, pending_unmapped_ids = await self._active_character_ids(interaction)
        resolved_character_id = await _resolve_character_id_for_panel(
            interaction,
            self.mode,
            active_ids,
            pending_unmapped_ids,
            preferred_character_id=self.character_id,
        )
        if resolved_character_id is None:
            if self.mode == "show_pending":
                return await interaction.response.edit_message(
                    content="No pending unmapped character IDs found for this user yet.",
                    embed=None,
                    view=None,
                )
            return await interaction.response.edit_message(
                content="No character ID found yet for this user. Play on a character first so RealmShark can detect one.",
                embed=None,
                view=None,
            )

        self.character_id = resolved_character_id
        embed = await _build_panel_embed(
            interaction,
            self.character_id,
            self.token,
            self.mode,
            active_ids,
            pending_ids=pending_unmapped_ids,
            target_user_id=self.target_user_id,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary)
    async def prev_pending(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._check_owner(interaction):
            return

        active_ids, _all_ids, pending_unmapped_ids = await self._active_character_ids(interaction)
        if not active_ids:
            label = "pending unmapped" if self.mode == "show_pending" else "known"
            return await interaction.response.send_message(f"No {label} character IDs to cycle.", ephemeral=True)

        if self.character_id not in active_ids:
            self.character_id = active_ids[-1]
        else:
            idx = active_ids.index(self.character_id)
            self.character_id = active_ids[(idx - 1) % len(active_ids)]

        embed = await _build_panel_embed(
            interaction,
            self.character_id,
            self.token,
            self.mode,
            active_ids,
            pending_ids=pending_unmapped_ids,
            target_user_id=self.target_user_id,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_pending(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._check_owner(interaction):
            return

        active_ids, _all_ids, pending_unmapped_ids = await self._active_character_ids(interaction)
        if not active_ids:
            label = "pending unmapped" if self.mode == "show_pending" else "known"
            return await interaction.response.send_message(f"No {label} character IDs to cycle.", ephemeral=True)

        if self.character_id not in active_ids:
            self.character_id = active_ids[0]
        else:
            idx = active_ids.index(self.character_id)
            self.character_id = active_ids[(idx + 1) % len(active_ids)]

        embed = await _build_panel_embed(
            interaction,
            self.character_id,
            self.token,
            self.mode,
            active_ids,
            pending_ids=pending_unmapped_ids,
            target_user_id=self.target_user_id,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def _check_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This panel belongs to another user.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Map To PPE", style=discord.ButtonStyle.success)
    async def map_to_ppe(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._check_owner(interaction):
            return

        records = await load_player_records(interaction)
        key = ensure_player_exists(records, self.target_user_id)
        player_data = records.get(key)
        player_ppes = sorted(player_data.ppes if player_data else [], key=lambda ppe: int(ppe.id))

        if not player_ppes:
            return await interaction.response.send_message(
                "This user does not have any PPEs yet. Create one with `/newppe` first.",
                ephemeral=True,
            )

        ppe_options: list[tuple[int, str, float]] = []
        ppe_lines: list[str] = []
        for ppe in player_ppes:
            ppe_id = int(ppe.id)
            ppe_name = str(getattr(ppe.name, "value", ppe.name))
            ppe_points = float(getattr(ppe, "points", 0.0))
            ppe_options.append((ppe_id, ppe_name, ppe_points))
            ppe_lines.append(f"• PPE #{ppe_id} ({ppe_name}) - {_format_points(ppe_points)} points")

        pending_entry = await get_pending_character_entry(interaction.guild.id, self.target_user_id, self.character_id)
        pending_events = []
        if isinstance(pending_entry, dict):
            pending_events = pending_entry.get("events", []) if isinstance(pending_entry.get("events", []), list) else []

        settings = await get_realmshark_settings(interaction)
        links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}
        user_links = _iter_user_links(links, user_id=self.target_user_id, token=self.token)
        detected_name, detected_class = await _detected_character_info(
            interaction,
            user_links,
            self.character_id,
        )

        embed = discord.Embed(
            title="Map Character To PPE",
            description=(
                f"Character ID: **{self.character_id}**\n"
                f"Detected Character: **{detected_name or 'Unknown'}**\n"
                f"Detected Class: **{detected_class or 'Unknown'}**"
            ),
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Pending Loot Summary",
            value=_build_pending_loot_summary(pending_events),
            inline=False,
        )
        embed.add_field(
            name="Available PPE Options",
            value="\n".join(ppe_lines[:10]),
            inline=False,
        )
        embed.set_footer(text="Pick a PPE from the dropdown to map this character.")

        await interaction.response.send_message(
            embed=embed,
            view=RealmSharkMapToPPEView(
                self.owner_id,
                self.target_user_id,
                self.character_id,
                self.token,
                ppe_options,
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="Set Seasonal", style=discord.ButtonStyle.secondary)
    async def set_seasonal(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._check_owner(interaction):
            return
        await configure(
            interaction,
            "set_seasonal",
            character_id=self.character_id,
            token=self.token,
            target_user_id=self.target_user_id,
        )

    @discord.ui.button(label="Show Pending", style=discord.ButtonStyle.primary)
    async def show_pending(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._check_owner(interaction):
            return
        self.mode = "show_pending"
        await self._refresh_panel(interaction)

    @discord.ui.button(label="Show All", style=discord.ButtonStyle.primary)
    async def show_all(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._check_owner(interaction):
            return
        self.mode = "show_all"
        await self._refresh_panel(interaction)

    @discord.ui.button(label="Clear Pending", style=discord.ButtonStyle.danger)
    async def clear_pending(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._check_owner(interaction):
            return
        await configure(
            interaction,
            "clear_pending",
            character_id=self.character_id,
            token=self.token,
            target_user_id=self.target_user_id,
        )

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._check_owner(interaction):
            return
        await self._refresh_panel(interaction)


async def open_panel(
    interaction: discord.Interaction,
    mode: str,
    token: str | None = None,
) -> None:
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)

    if mode not in {"show_all", "show_pending"}:
        return await interaction.response.send_message("Invalid panel mode. Use Show All or Show Pending.", ephemeral=True)

    all_ids, pending_unmapped_ids = await _player_character_lists(
        interaction,
        user_id=interaction.user.id,
        token=token,
    )
    active_ids = pending_unmapped_ids if mode == "show_pending" else all_ids

    resolved_character_id = await _resolve_character_id_for_panel(
        interaction,
        mode,
        active_ids,
        pending_unmapped_ids,
    )
    if resolved_character_id is None:
        if mode == "show_pending":
            return await interaction.response.send_message(
                "No pending unmapped character IDs found for your account yet.",
                ephemeral=True,
            )
        return await interaction.response.send_message(
            "No character ID found yet. Play on a character first so RealmShark can detect one, then open this panel again.",
            ephemeral=True,
        )

    view = RealmSharkConfigurePanelView(interaction.user.id, interaction.user.id, resolved_character_id, token, mode)
    embed = await _build_panel_embed(
        interaction,
        resolved_character_id,
        token,
        mode,
        active_ids,
        pending_ids=pending_unmapped_ids,
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def reset_all(interaction: discord.Interaction) -> None:
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}
    links_cleared = len(links)
    pending_files_cleared = await clear_all_pending_for_guild(interaction.guild.id)

    saved = await set_realmshark_settings(interaction, dict(_REALMSHARK_DEFAULTS))
    await interaction.response.send_message(
        "Reset all RealmShark data for this guild.\n"
        f"enabled: `{saved.get('enabled', False)}`\n"
        f"mode: `{saved.get('mode', 'addloot')}`\n"
        f"announce_channel_id: `{saved.get('announce_channel_id', 0)}`\n"
        f"link_count: `{len(saved.get('links', {}))}`\n"
        f"revoked_links: `{links_cleared}`\n"
        f"pending_files_removed: `{pending_files_cleared}`",
        ephemeral=True,
    )
