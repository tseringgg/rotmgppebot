from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict

import discord

from utils.guild_config import get_realmshark_settings, set_realmshark_settings
from utils.player_records import ensure_player_exists, load_player_records
from utils.realmshark_ingest import _addloot_for_user_with_ppe
from utils.realmshark_pending_store import (
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
    "apply_pending_to_ppe",
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
        f"mode: `{settings.get('mode', 'addloot')}`",
        f"announce_channel_id: `{settings.get('announce_channel_id', 0)}`",
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
            user_lines.append(f"  character_id `{character_id}` -> PPE `#{ppe_id}`")
        for character_id in sorted(seasonal_ids, key=int)[:20]:
            user_lines.append(f"  character_id `{character_id}` -> seasonal")

    if not user_lines:
        return await interaction.response.send_message(
            "No RealmShark character bindings found for your linked token(s).",
            ephemeral=True,
        )

    await interaction.response.send_message("RealmShark character bindings:\n" + "\n".join(user_lines), ephemeral=True)


async def unbind_character(interaction: discord.Interaction, character_id: int, token: str | None = None) -> None:
    if character_id <= 0:
        return await interaction.response.send_message("character_id must be a positive integer.", ephemeral=True)

    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}

    removed_from = 0
    key = str(character_id)
    for current_token, link_data in links.items():
        if not isinstance(link_data, dict):
            continue
        if token and current_token != token:
            continue

        try:
            linked_user_id = int(link_data.get("user_id"))
        except (TypeError, ValueError):
            continue
        if linked_user_id != interaction.user.id:
            continue

        character_bindings = _normalize_bindings(link_data)
        seasonal_ids = _normalize_seasonal_ids(link_data)

        if key in character_bindings:
            del character_bindings[key]
            link_data["character_bindings"] = character_bindings
            seasonal_ids.discard(key)
            link_data["seasonal_character_ids"] = sorted(seasonal_ids, key=int)
            links[current_token] = link_data
            removed_from += 1

        if key in seasonal_ids:
            seasonal_ids.discard(key)
            link_data["seasonal_character_ids"] = sorted(seasonal_ids, key=int)
            links[current_token] = link_data
            removed_from += 1

    if removed_from == 0:
        return await interaction.response.send_message(
            f"No mapping found for character_id `{character_id}` on your linked token(s).",
            ephemeral=True,
        )

    settings["links"] = links
    await set_realmshark_settings(interaction, settings)
    await interaction.response.send_message(
        f"Removed character_id `{character_id}` mapping from `{removed_from}` token(s).",
        ephemeral=True,
    )


async def configure(
    interaction: discord.Interaction,
    action: str,
    character_id: int | None = None,
    ppe_id: int | None = None,
    token: str | None = None,
) -> None:
    if action not in _CONFIG_ACTIONS:
        return await interaction.response.send_message("Invalid action.", ephemeral=True)

    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}
    user_links = _iter_user_links(links, user_id=interaction.user.id, token=token)

    if not user_links:
        return await interaction.response.send_message(
            "No linked RealmShark token found. Run `/realmsharklink` first.",
            ephemeral=True,
        )

    migrated = await _migrate_legacy_pending_for_user(interaction.guild.id, user_links, links)
    if migrated:
        settings["links"] = links
        await set_realmshark_settings(interaction, settings)
        user_links = _iter_user_links(links, user_id=interaction.user.id, token=token)

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
    key = ensure_player_exists(records, interaction.user.id)
    player_data = records.get(key)
    user_ppe_ids = {ppe.id for ppe in (player_data.ppes if player_data else [])}

    if action in {"map_ppe", "apply_pending_to_ppe"}:
        if ppe_id is None or ppe_id <= 0:
            return await interaction.response.send_message("Please provide a valid `ppe_id`.", ephemeral=True)
        if ppe_id not in user_ppe_ids:
            return await interaction.response.send_message(
                f"You do not own PPE #{ppe_id}. Use `/myppes` to check your IDs.",
                ephemeral=True,
            )

    changed = 0
    applied_events_total = 0

    for current_token, link_data in user_links:
        character_bindings = _normalize_bindings(link_data)
        seasonal_ids = _normalize_seasonal_ids(link_data)
        if action == "map_ppe":
            assert ppe_id is not None
            character_bindings[character_key] = ppe_id
            seasonal_ids.discard(character_key)
            changed += 1
        elif action == "set_seasonal":
            seasonal_ids.add(character_key)
            if character_key in character_bindings:
                del character_bindings[character_key]
            changed += 1
        elif action == "clear_mapping":
            if character_key in character_bindings:
                del character_bindings[character_key]
                changed += 1
            if character_key in seasonal_ids:
                seasonal_ids.discard(character_key)
                changed += 1
        elif action == "clear_pending":
            cleared = await clear_pending_character(interaction.guild.id, interaction.user.id, character_id)
            if cleared:
                changed += 1
        elif action == "apply_pending_to_ppe":
            assert ppe_id is not None
            events = await pop_pending_events_for_character(interaction.guild.id, interaction.user.id, character_id)
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
                    interaction.user.id,
                    item_name,
                    item_divine,
                    item_shiny,
                    ppe_id,
                )
                applied_events_total += 1

            character_bindings[character_key] = ppe_id
            seasonal_ids.discard(character_key)
            changed += 1
        elif action == "show_pending":
            entry = await get_pending_character_entry(interaction.guild.id, interaction.user.id, character_id)
            if not isinstance(entry, dict):
                continue
            events = entry.get("events", []) if isinstance(entry.get("events", []), list) else []
            lines = [
                f"token `{_token_preview(current_token)}` pending events: `{len(events)}`",
                f"first_seen: `{entry.get('first_seen_at', '')}`",
                f"last_seen: `{entry.get('last_seen_at', '')}`",
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
        "map_ppe": f"Mapped character_id `{character_id}` to PPE `#{ppe_id}`",
        "set_seasonal": f"Mapped character_id `{character_id}` to seasonal",
        "clear_mapping": f"Cleared mapping for character_id `{character_id}`",
        "clear_pending": f"Cleared pending log for character_id `{character_id}`",
        "apply_pending_to_ppe": (
            f"Applied `{applied_events_total}` pending loot event(s) to PPE `#{ppe_id}` "
            f"and mapped character_id `{character_id}` to that PPE"
        ),
    }.get(action, "Updated configuration")

    await interaction.response.send_message(
        f"✅ {action_label}.\nUse `/realmsharkbindings` to review your mappings.",
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
        lines.append(
            f"- token `{_token_preview(token)}` ppe_bindings=`{len(bindings)}` "
            f"seasonal=`{len(seasonal_ids)}` pending=`{len(pending_chars)}` "
            f"last_seen=`{link_data.get('last_seen_character_id', 0)}`"
        )
        for character_id, ppe_id in sorted(bindings.items(), key=lambda kv: str(kv[0]))[:10]:
            lines.append(f"  character_id `{character_id}` -> PPE `#{ppe_id}`")
        for character_id in sorted(seasonal_ids, key=int)[:10]:
            lines.append(f"  character_id `{character_id}` -> seasonal")
        for character_id, entry in sorted(pending_chars.items(), key=lambda kv: int(kv[0]))[:10]:
            events = entry.get("events", []) if isinstance(entry.get("events", []), list) else []
            lines.append(f"  pending character_id `{character_id}` events=`{len(events)}`")

    await interaction.response.send_message("\n".join(lines), ephemeral=True)


async def _resolve_character_id_for_panel(
    interaction: discord.Interaction,
    mode: str,
    token: str | None,
    requested_character_id: int | None,
) -> int | None:
    pending_data = await load_pending(interaction.guild.id, interaction.user.id)
    characters = pending_data.get("characters", {}) if isinstance(pending_data.get("characters", {}), dict) else {}
    pending_ids = sorted(
        [int(raw_id) for raw_id in characters.keys() if str(raw_id).isdigit() and int(raw_id) > 0]
    )

    if mode == "show_pending":
        if requested_character_id is not None and requested_character_id > 0 and requested_character_id in pending_ids:
            return requested_character_id
        if pending_ids:
            return pending_ids[0]
        return None

    if requested_character_id is not None and requested_character_id > 0:
        return requested_character_id

    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}
    user_links = _iter_user_links(links, user_id=interaction.user.id, token=token)

    last_seen_values: list[int] = []
    for _, link_data in user_links:
        try:
            seen = int(link_data.get("last_seen_character_id", 0) or 0)
        except (TypeError, ValueError):
            seen = 0
        if seen > 0:
            last_seen_values.append(seen)

    if last_seen_values:
        return last_seen_values[-1]

    if pending_ids:
        return pending_ids[-1]

    return None


async def _build_panel_embed(
    interaction: discord.Interaction,
    character_id: int,
    token: str | None,
    pending_ids: list[int] | None = None,
) -> discord.Embed:
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}
    user_links = _iter_user_links(links, user_id=interaction.user.id, token=token)

    mapped_ppe: int | None = None
    seasonal = False
    for _, link_data in user_links:
        bindings = _normalize_bindings(link_data)
        seasonal_ids = _normalize_seasonal_ids(link_data)
        key = str(character_id)
        if key in bindings:
            mapped_ppe = bindings[key]
            break
        if key in seasonal_ids:
            seasonal = True

    pending_entry = await get_pending_character_entry(interaction.guild.id, interaction.user.id, character_id)
    pending_count = 0
    if isinstance(pending_entry, dict):
        events = pending_entry.get("events", []) if isinstance(pending_entry.get("events", []), list) else []
        pending_count = len(events)

    records = await load_player_records(interaction)
    key = ensure_player_exists(records, interaction.user.id)
    player_data = records.get(key)
    ppe_list = sorted([ppe.id for ppe in (player_data.ppes if player_data else [])])
    ppe_text = ", ".join(f"#{ppe_id}" for ppe_id in ppe_list) if ppe_list else "No PPEs yet"

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
            f"Character ID: **{character_id}**\n"
            f"Current status: **{status}**\n"
            f"Pending unmapped loot events: **{pending_count}**\n"
            f"Pending queue position: **{pending_position}**"
        ),
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="Your PPE IDs",
        value=ppe_text,
        inline=False,
    )
    embed.add_field(
        name="How to use this panel",
        value=(
            "0. Use `Prev Pending` / `Next Pending` to cycle pending character IDs.\n"
            "1. `Map To PPE` to make future loot use addloot for this character.\n"
            "2. `Set Seasonal` to keep this character as seasonal.\n"
            "3. `Apply Pending To PPE` if you want already-logged pending seasonal loot moved into a PPE.\n"
            "4. `Refresh` anytime to reload status."
        ),
        inline=False,
    )
    return embed


class _PPEIdModal(discord.ui.Modal):
    def __init__(self, action: str, character_id: int, token: str | None) -> None:
        title = "Map Character To PPE" if action == "map_ppe" else "Apply Pending Loot To PPE"
        super().__init__(title=title)
        self.action = action
        self.character_id = character_id
        self.token = token
        self.ppe_id_input = discord.ui.TextInput(
            label="PPE ID",
            placeholder="Enter your PPE ID, for example: 3",
            required=True,
            max_length=8,
        )
        self.add_item(self.ppe_id_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            ppe_id = int(str(self.ppe_id_input.value).strip())
        except ValueError:
            return await interaction.response.send_message("Please enter a valid numeric PPE ID.", ephemeral=True)

        await configure(
            interaction,
            self.action,
            character_id=self.character_id,
            ppe_id=ppe_id,
            token=self.token,
        )


class RealmSharkConfigurePanelView(discord.ui.View):
    def __init__(self, owner_id: int, character_id: int, token: str | None) -> None:
        super().__init__(timeout=600)
        self.owner_id = owner_id
        self.character_id = character_id
        self.token = token

    async def _pending_ids(self, interaction: discord.Interaction) -> list[int]:
        pending_data = await load_pending(interaction.guild.id, self.owner_id)
        characters = pending_data.get("characters", {}) if isinstance(pending_data.get("characters", {}), dict) else {}
        ids: list[int] = []
        for raw_id in characters.keys():
            try:
                parsed = int(raw_id)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                ids.append(parsed)
        return sorted(set(ids))

    async def _refresh_panel(self, interaction: discord.Interaction) -> None:
        pending_ids = await self._pending_ids(interaction)
        embed = await _build_panel_embed(
            interaction,
            self.character_id,
            self.token,
            pending_ids=pending_ids,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Prev Pending", style=discord.ButtonStyle.secondary)
    async def prev_pending(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._check_owner(interaction):
            return

        pending_ids = await self._pending_ids(interaction)
        if not pending_ids:
            return await interaction.response.send_message("No pending character IDs to cycle.", ephemeral=True)

        if self.character_id not in pending_ids:
            self.character_id = pending_ids[-1]
        else:
            idx = pending_ids.index(self.character_id)
            self.character_id = pending_ids[(idx - 1) % len(pending_ids)]

        embed = await _build_panel_embed(
            interaction,
            self.character_id,
            self.token,
            pending_ids=pending_ids,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next Pending", style=discord.ButtonStyle.secondary)
    async def next_pending(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._check_owner(interaction):
            return

        pending_ids = await self._pending_ids(interaction)
        if not pending_ids:
            return await interaction.response.send_message("No pending character IDs to cycle.", ephemeral=True)

        if self.character_id not in pending_ids:
            self.character_id = pending_ids[0]
        else:
            idx = pending_ids.index(self.character_id)
            self.character_id = pending_ids[(idx + 1) % len(pending_ids)]

        embed = await _build_panel_embed(
            interaction,
            self.character_id,
            self.token,
            pending_ids=pending_ids,
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
        await interaction.response.send_modal(_PPEIdModal("map_ppe", self.character_id, self.token))

    @discord.ui.button(label="Set Seasonal", style=discord.ButtonStyle.secondary)
    async def set_seasonal(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._check_owner(interaction):
            return
        await configure(interaction, "set_seasonal", character_id=self.character_id, token=self.token)

    @discord.ui.button(label="Show Pending", style=discord.ButtonStyle.primary)
    async def show_pending(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._check_owner(interaction):
            return
        await configure(interaction, "show_pending", character_id=self.character_id, token=self.token)

    @discord.ui.button(label="Apply Pending To PPE", style=discord.ButtonStyle.success)
    async def apply_pending_to_ppe(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._check_owner(interaction):
            return
        await interaction.response.send_modal(_PPEIdModal("apply_pending_to_ppe", self.character_id, self.token))

    @discord.ui.button(label="Clear Pending", style=discord.ButtonStyle.danger)
    async def clear_pending(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._check_owner(interaction):
            return
        await configure(interaction, "clear_pending", character_id=self.character_id, token=self.token)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._check_owner(interaction):
            return
        await self._refresh_panel(interaction)


async def open_panel(
    interaction: discord.Interaction,
    mode: str,
    character_id: int | None = None,
    token: str | None = None,
) -> None:
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)

    if mode not in {"show_all", "show_pending"}:
        return await interaction.response.send_message("Invalid panel mode. Use Show All or Show Pending.", ephemeral=True)

    resolved_character_id = await _resolve_character_id_for_panel(interaction, mode, token, character_id)
    if resolved_character_id is None:
        if mode == "show_pending":
            return await interaction.response.send_message(
                "No pending character IDs found for your account yet.",
                ephemeral=True,
            )
        return await interaction.response.send_message(
            "No character ID found yet. Play on a character first so RealmShark can detect one, then open this panel again.",
            ephemeral=True,
        )

    view = RealmSharkConfigurePanelView(interaction.user.id, resolved_character_id, token)
    pending_data = await load_pending(interaction.guild.id, interaction.user.id)
    pending_chars = pending_data.get("characters", {}) if isinstance(pending_data.get("characters", {}), dict) else {}
    pending_ids: list[int] = []
    for raw_id in pending_chars.keys():
        try:
            parsed = int(raw_id)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            pending_ids.append(parsed)
    pending_ids = sorted(set(pending_ids))

    embed = await _build_panel_embed(interaction, resolved_character_id, token, pending_ids=pending_ids)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def reset_all(interaction: discord.Interaction) -> None:
    saved = await set_realmshark_settings(interaction, dict(_REALMSHARK_DEFAULTS))
    await interaction.response.send_message(
        "Reset all RealmShark data for this guild.\n"
        f"enabled: `{saved.get('enabled', False)}`\n"
        f"mode: `{saved.get('mode', 'addloot')}`\n"
        f"announce_channel_id: `{saved.get('announce_channel_id', 0)}`\n"
        f"link_count: `{len(saved.get('links', {}))}`",
        ephemeral=True,
    )
