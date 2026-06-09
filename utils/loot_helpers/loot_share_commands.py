"""Utilities for loot share commands."""

import discord

from utils.ppe_types import normalize_ppe_type, ppe_type_short_label
from utils.player_records import ensure_player_exists, get_active_ppe_of_user, load_player_records
from utils.player_records import highest_rarity
from utils.loot_helpers.shareloot_image import generate_loot_share_image
from utils.item_log_timestamps import seasonal_item_key
from utils.season_loot_history import iter_season_variants


async def _send_interaction_text(interaction: discord.Interaction, content: str, *, ephemeral: bool) -> None:
    if not interaction.response.is_done():
        await interaction.response.send_message(content, ephemeral=ephemeral)
        return
    await interaction.followup.send(content, ephemeral=ephemeral)


async def share_active_ppe_loot_image(
    interaction: discord.Interaction,
    *,
    include_skins: bool = False,
    include_limited: bool = False,
    target_user_id: int | None = None,
    target_display_name: str | None = None,
) -> None:
    try:
        active_ppe = await get_active_ppe_of_user(interaction, target_user_id=target_user_id)
    except (ValueError, KeyError) as e:
        await _send_interaction_text(interaction, str(e), ephemeral=True)
        return

    source_items = [
        (loot_item.item_name, bool(loot_item.shiny), str(getattr(loot_item, "rarity", "common")))
        for loot_item in active_ppe.loot
    ]
    ppe_type = ppe_type_short_label(normalize_ppe_type(getattr(active_ppe, "ppe_type", None)))

    if target_display_name:
        embed_description = f"**{target_display_name}** - PPE #{active_ppe.id} ({active_ppe.name}) [{ppe_type}]"
    else:
        embed_description = f"**{active_ppe.name}** PPE #{active_ppe.id} [{ppe_type}]"

    await generate_loot_share_image(
        interaction,
        source_items=source_items,
        include_skins=include_skins,
        include_limited=include_limited,
        filename_suffix=f"ppe{active_ppe.id}_loot",
        embed_title="🎒 PPE Loot Share",
        embed_color=0x00FF00,
        embed_description=embed_description,
        total_items_label="Total Loot",
        all_variant_extra_lines=[f"**Points:** {active_ppe.points:.1f}"],
    )


async def share_season_loot_image(
    interaction: discord.Interaction,
    *,
    include_skins: bool = False,
    include_limited: bool = False,
    target_user_id: int | None = None,
    target_display_name: str | None = None,
    error_ephemeral: bool = True,
) -> None:
    try:
        records = await load_player_records(interaction)
        resolved_target_user_id = int(target_user_id) if target_user_id is not None else int(interaction.user.id)
        resolved_target_display_name = target_display_name or interaction.user.display_name
        key = ensure_player_exists(records, resolved_target_user_id)

        if key not in records or not records[key].is_member:
            await _send_interaction_text(
                interaction,
                f"❌ {resolved_target_display_name} is not part of the PPE contest.",
                ephemeral=error_ephemeral,
            )
            return

        player_data = records[key]

        season_variants = iter_season_variants(player_data)
        if not season_variants:
            await _send_interaction_text(
                interaction,
                (
                    f"{resolved_target_display_name} has no tracked season loot yet.\n"
                    "Use `/addseasonlootfor` to add season loot for this player."
                ),
                ephemeral=error_ephemeral,
            )
            return
    except (ValueError, KeyError) as e:
        await _send_interaction_text(interaction, str(e), ephemeral=error_ephemeral)
        return

    await generate_loot_share_image(
        interaction,
        source_items=[(item_name, shiny, rarity) for item_name, shiny, rarity, _timestamps in season_variants],
        include_skins=include_skins,
        include_limited=include_limited,
        filename_suffix="season_loot",
        embed_title="🎒 Season Loot Share",
        embed_color=0xFFD700,
        embed_description=f"**{resolved_target_display_name}'s** Season Loot Collection",
        total_items_label="Total Unique Items",
    )
