from __future__ import annotations

from typing import Any, Dict

import discord

from menus.menu_utils import OwnerBoundView
from menus.menu_utils.sniffer_core.panel_common import (
    collect_character_ids_from_link as _collect_character_ids_from_link,
    detected_character_info as _detected_character_info,
    iter_user_links as _iter_user_links,
    normalize_bindings as _normalize_bindings,
    normalize_character_metadata as _normalize_character_metadata,
    normalize_seasonal_ids as _normalize_seasonal_ids,
    parse_positive_int as _parse_positive_int,
    player_character_lists as _player_character_lists,
    resolve_character_id_for_panel as _resolve_character_id_for_panel,
)
from menus.menu_utils.sniffer_core.panel_views import RealmSharkConfigurePanelView, render_panel_embed
from utils.guild_config import get_realmshark_settings, set_realmshark_settings
from utils.player_records import load_player_records
from utils.realmshark_pending_store import load_pending
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


class _RealmSharkAdminConfirmClearMappingsView(OwnerBoundView):
    def __init__(self, owner_id: int, target_member_id: int) -> None:
        super().__init__(
            owner_id=owner_id,
            timeout=60,
            owner_error="This confirmation belongs to another admin.",
        )
        self.target_member_id = target_member_id

    @discord.ui.button(label="Confirm Remove All Mappings", style=discord.ButtonStyle.danger)
    async def confirm(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        if not await self.ensure_owner(interaction):
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
        if not await self.ensure_owner(interaction):
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


class RealmSharkAdminPanelView(OwnerBoundView):
    def __init__(self, owner_id: int, mode: str, entries: list[tuple[int, int]]) -> None:
        super().__init__(
            owner_id=owner_id,
            timeout=600,
            owner_error="This admin panel belongs to another admin.",
        )
        self.mode = mode
        self.entries = entries
        self.index = 0

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
        if not await self.ensure_owner(interaction):
            return
        if not await self._refresh_entries(interaction):
            return
        self.index = (self.index - 1) % len(self.entries)
        await self._render(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return
        if not await self._refresh_entries(interaction):
            return
        self.index = (self.index + 1) % len(self.entries)
        await self._render(interaction)

    @discord.ui.button(label="Show Pending", style=discord.ButtonStyle.primary)
    async def show_pending(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return
        self.mode = "show_pending"
        if not await self._refresh_entries(interaction):
            return
        await self._render(interaction)

    @discord.ui.button(label="Show All", style=discord.ButtonStyle.primary)
    async def show_all(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return
        self.mode = "show_all"
        if not await self._refresh_entries(interaction):
            return
        await self._render(interaction)

    @discord.ui.button(label="Remove All Mappings", style=discord.ButtonStyle.danger)
    async def remove_all_mappings(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
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
        if not await self.ensure_owner(interaction):
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

    resolved_character_id = _resolve_character_id_for_panel(
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
    embed = await render_panel_embed(
        interaction,
        resolved_character_id,
        None,
        mode=mode,
        all_character_ids=active_ids,
        pending_ids=pending_unmapped_ids,
        target_user_id=member.id,
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)




__all__ = ["RealmSharkAdminPanelView", "admin_panel"]
