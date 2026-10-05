import os
from typing import Any, Mapping

import discord

from dataclass import TeamData
from utils.ppe_types import normalize_ppe_type, ppe_type_short_label
from utils.player_records import ensure_player_exists, get_active_ppe_of_user, load_player_records, load_teams, resolve_team_name
from utils.player_records import highest_rarity
from utils.loot_helpers.shareloot_image import generate_loot_share_image, safe_filename_component
from utils.item_log_timestamps import now_unix_utc, seasonal_item_key, seasonal_item_variant_key
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


def collect_team_season_loot(team: TeamData, records: Mapping[int, Any]) -> tuple[list[tuple[str, bool, str]], int]:
    """Merge every team member's season loot variants.

    Returns ``(source_items, contributing_members)`` where ``source_items`` is suitable for
    ``generate_loot_share_image`` (duplicates are collapsed to highest rarity during rendering).
    """
    source_items: list[tuple[str, bool, str]] = []
    contributing_members = 0
    for member_id in team.members:
        player_data = records.get(member_id)
        if player_data is None and isinstance(member_id, str) and member_id.isdigit():
            player_data = records.get(int(member_id))
        elif player_data is None and isinstance(member_id, int):
            player_data = records.get(str(member_id))

        if player_data is None:
            continue

        member_variants = iter_season_variants(player_data)
        if member_variants:
            contributing_members += 1
            source_items.extend((item_name, shiny, rarity) for item_name, shiny, rarity, _ts in member_variants)
        elif getattr(player_data, "ppes", None):
            # Graceful fallback if character loot was tracked without season history
            has_loot = False
            for ppe in player_data.ppes:
                for loot_item in getattr(ppe, "loot", []):
                    has_loot = True
                    source_items.append((
                        loot_item.item_name,
                        bool(getattr(loot_item, "shiny", False)),
                        str(getattr(loot_item, "rarity", "common")),
                    ))
            if has_loot:
                contributing_members += 1
    return source_items, contributing_members


async def share_team_loot_image(
    interaction: discord.Interaction,
    *,
    team_name: str,
    include_skins: bool = False,
    include_limited: bool = False,
    error_ephemeral: bool = True,
) -> None:
    """Render one combined season loot image for every member of a team."""
    teams = await load_teams(interaction)
    actual_team_name = resolve_team_name(teams, team_name)
    if actual_team_name is None:
        await _send_interaction_text(interaction, f"❌ Team `{team_name}` not found.", ephemeral=error_ephemeral)
        return

    team = teams[actual_team_name]
    records = await load_player_records(interaction)
    source_items, contributing_members = collect_team_season_loot(team, records)
    if not source_items:
        await _send_interaction_text(
            interaction,
            f"Team **{actual_team_name}** has no tracked season loot yet.",
            ephemeral=error_ephemeral,
        )
        return

    await generate_loot_share_image(
        interaction,
        source_items=source_items,
        include_skins=include_skins,
        include_limited=include_limited,
        filename_suffix=f"team_{safe_filename_component(actual_team_name)}_loot",
        embed_title="🎒 Team Loot Share",
        embed_color=0x5865F2,
        embed_description=(
            f"**Team {actual_team_name}'s** Combined Season Loot\n"
            f"Members contributing: **{contributing_members}/{len(team.members)}**"
        ),
        total_items_label="Total Unique Items",
    )


def build_team_season_history(team: TeamData, records: Mapping[int, Any]) -> dict[str, list[int]]:
    """Merge every team member's season loot history into a combined dictionary."""
    combined: dict[str, list[int]] = {}
    for member_id in team.members:
        player_data = records.get(member_id)
        if player_data is None and isinstance(member_id, str) and member_id.isdigit():
            player_data = records.get(int(member_id))
        elif player_data is None and isinstance(member_id, int):
            player_data = records.get(str(member_id))

        if player_data is None:
            continue

        raw_history = getattr(player_data, "season_item_history", None)
        if isinstance(raw_history, dict) and raw_history:
            for key, timestamps in raw_history.items():
                if not isinstance(timestamps, list):
                    timestamps = [timestamps] if timestamps else []
                if key not in combined:
                    combined[key] = []
                for ts in timestamps:
                    try:
                        parsed_ts = int(ts)
                        if parsed_ts > 0:
                            combined[key].append(parsed_ts)
                    except (TypeError, ValueError):
                        continue
        elif getattr(player_data, "ppes", None):
            # Fallback for active PPE loot if season history is empty
            for ppe in player_data.ppes:
                for loot_item in getattr(ppe, "loot", []):
                    item_name = loot_item.item_name
                    shiny = bool(getattr(loot_item, "shiny", False))
                    rarity = str(getattr(loot_item, "rarity", "common"))
                    key = seasonal_item_variant_key(item_name, shiny, rarity)
                    if key not in combined:
                        combined[key] = []
                    combined[key].append(now_unix_utc())

    for key in combined:
        combined[key].sort()

    return combined


async def send_team_season_loot_markdown_followup(
    interaction: discord.Interaction,
    *,
    team_name: str,
    ephemeral: bool = True,
) -> None:
    """Export the team's combined season loot as a downloadable markdown file attachment."""
    teams = await load_teams(interaction)
    actual_team_name = resolve_team_name(teams, team_name)
    if actual_team_name is None:
        await _send_interaction_text(interaction, f"❌ Team `{team_name}` not found.", ephemeral=ephemeral)
        return

    team = teams[actual_team_name]
    records = await load_player_records(interaction)
    combined_history = build_team_season_history(team, records)

    if not combined_history:
        await _send_interaction_text(
            interaction,
            f"Team **{actual_team_name}** has no tracked season loot yet.",
            ephemeral=ephemeral,
        )
        return

    from utils.message_utils.loot_table_md_builder import create_season_loot_markdown_file

    temp_file_path = create_season_loot_markdown_file(
        combined_history,
        display_name=f"Team {actual_team_name}",
        include_dungeon_completion=True,
    )

    try:
        await interaction.followup.send(file=discord.File(temp_file_path), ephemeral=ephemeral)
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError:
                pass
