from __future__ import annotations

from typing import Any

import discord

from menus.menu_utils.sniffer_core import services as realmshark_services
from menus.menu_utils.sniffer_core.panel_common import (
    detected_character_info as _detected_character_info,
    iter_user_links as _iter_user_links,
    migrate_legacy_pending_for_user as _migrate_legacy_pending_for_user,
    normalize_bindings as _normalize_bindings,
    normalize_character_metadata as _normalize_character_metadata,
    normalize_seasonal_ids as _normalize_seasonal_ids,
    normalized_class_name as _normalized_class_name,
    player_ppe_classes as _player_ppe_classes,
)
from menus.menu_utils.sniffer_core.common import token_preview as _token_preview
from utils.guild_config import get_realmshark_settings, set_realmshark_settings
from utils.player_records import ensure_player_exists, load_player_records
from utils.realmshark_ingest import _addloot_for_user_with_ppe
from utils.realmshark_pending_store import (
    clear_all_pending_for_guild,
    clear_pending_character,
    get_pending_character_entry,
    load_pending,
    pop_pending_events_for_character,
)

_REALMSHARK_DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "mode": "addloot",
    "links": {},
    "announce_channel_id": 0,
    "endpoint": "",
}

_CONFIG_ACTIONS = {
    "show",
    "map_ppe",
    "set_seasonal",
    "clear_mapping",
    "show_pending",
    "clear_pending",
}


async def generate_link_token(interaction: discord.Interaction) -> None:
    await realmshark_services.generate_link_token(interaction)


async def set_enabled(interaction: discord.Interaction, enabled: bool) -> None:
    await realmshark_services.set_enabled(interaction, enabled)


async def set_announce_channel(
    interaction: discord.Interaction,
    channel: discord.TextChannel | None,
) -> None:
    await realmshark_services.set_announce_channel(interaction, channel)


async def unlink_token(interaction: discord.Interaction, token: str) -> None:
    await realmshark_services.unlink_token(interaction, token)


async def status(interaction: discord.Interaction) -> None:
    await realmshark_services.status(interaction)
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


__all__ = [
    "admin_view",
    "bindings",
    "configure",
    "generate_link_token",
    "reset_all",
    "set_announce_channel",
    "set_enabled",
    "status",
    "unlink_token",
]
