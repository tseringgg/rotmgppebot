from __future__ import annotations

from typing import Any

import discord

from menus.menu_utils import OwnerBoundView
from menus.menu_utils.sniffer_core import common as realmshark_common
from menus.menu_utils.sniffer_core.panel_common import (
    collect_character_ids_from_link as _collect_character_ids_from_link,
    detected_character_info as _detected_character_info,
    iter_user_links as _iter_user_links,
    normalize_bindings as _normalize_bindings,
    normalize_character_metadata as _normalize_character_metadata,
    normalize_seasonal_ids as _normalize_seasonal_ids,
    parse_positive_int as _parse_positive_int,
)
from menus.menu_utils.sniffer_core.mapping_actions import configure
from utils.guild_config import get_realmshark_settings
from utils.player_records import ensure_player_exists, load_player_records
from utils.realmshark_pending_store import get_pending_character_entry, load_pending
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
    return realmshark_common.format_points(points)


def _build_pending_loot_summary(events: list[dict[str, Any]]) -> str:
    return realmshark_common.build_pending_loot_summary(events)


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


class RealmSharkConfigurePanelView(OwnerBoundView):
    def __init__(self, owner_id: int, target_user_id: int, character_id: int, token: str | None, mode: str) -> None:
        super().__init__(
            owner_id=owner_id,
            timeout=600,
            owner_error="This panel belongs to another user.",
        )
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

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary, row=0)
    async def prev_pending(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
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

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, row=0)
    async def next_pending(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
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

    @discord.ui.button(label="Map To PPE", style=discord.ButtonStyle.success, row=0)
    async def map_to_ppe(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
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
            ppe_lines.append(f"• PPE #{ppe_id} ({ppe_name}): {_format_points(ppe_points)} points")

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

    @discord.ui.button(label="Set Seasonal", style=discord.ButtonStyle.success, row=0)
    async def set_seasonal(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return
        await configure(
            interaction,
            "set_seasonal",
            character_id=self.character_id,
            token=self.token,
            target_user_id=self.target_user_id,
        )

    @discord.ui.button(label="Show Pending", style=discord.ButtonStyle.primary, row=1)
    async def show_pending(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return
        self.mode = "show_pending"
        await self._refresh_panel(interaction)

    @discord.ui.button(label="Show All", style=discord.ButtonStyle.primary, row=1)
    async def show_all(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return
        self.mode = "show_all"
        await self._refresh_panel(interaction)

    @discord.ui.button(label="Clear Pending", style=discord.ButtonStyle.danger, row=2)
    async def clear_pending(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return
        await configure(
            interaction,
            "clear_pending",
            character_id=self.character_id,
            token=self.token,
            target_user_id=self.target_user_id,
        )

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, row=2)
    async def refresh(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return
        await self._refresh_panel(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return
        await interaction.response.edit_message(
            content="Closed configure characters menu.",
            embed=None,
            view=None,
        )


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




__all__ = [
    "RealmSharkConfigurePanelView",
    "RealmSharkMapToPPEView",
    "open_panel",
    "render_panel_embed",
]


# Back-compat export alias.
render_panel_embed = _build_panel_embed
