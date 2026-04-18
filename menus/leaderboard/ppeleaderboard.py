import discord
import traceback
from typing import Any

from menus.leaderboard.common import build_ranked_entry_lines, send_error_response, send_leaderboard
from menus.leaderboard.services import member_display_name, require_guild
from utils.ppe_types import normalize_ppe_type, ppe_type_compact_summary
from utils.team_contest_scoring import (
    TeamContestScoring,
    compute_ppe_points,
    compute_quest_points_from_quests_and_active_ppe,
    compute_quest_points_from_quests,
    compute_team_shared_quest_points,
    get_best_ppe,
    load_team_contest_scoring,
)
from utils.guild_config import get_contest_settings, get_quest_points
from utils.guild_config import load_guild_config
from utils.points_service import compute_effective_ppe_points
from utils.player_records import load_player_records


def _duo_options(ppe: Any) -> dict[str, Any]:
    options = getattr(ppe, "ppe_type_options", None)
    return options if isinstance(options, dict) else {}


def _duo_partner_id(ppe: Any) -> int | None:
    options = _duo_options(ppe)
    if not bool(options.get("duo_enabled", False)):
        return None
    raw_partner = options.get("duo_partner_id")
    try:
        partner_id = int(raw_partner)
    except (TypeError, ValueError):
        return None
    return partner_id if partner_id > 0 else None


def _duo_player_label(guild: discord.Guild, player_name: str, ppe: Any) -> str:
    partner_id = _duo_partner_id(ppe)
    if partner_id is None:
        partner_name = "None"
    else:
        partner_name = member_display_name(guild, partner_id).title()
    return f"{player_name.title()} + {partner_name}"


def _find_matching_duo_partner_ppe(player_id: int, player_ppe: Any, partner_data: Any) -> Any | None:
    """Resolve the partner PPE linked to a specific duo PPE pairing."""
    if partner_data is None:
        return None

    from menus.myinfo.common import duo_link_id_for_ppe, duo_partner_id_from_options

    player_link_id = duo_link_id_for_ppe(player_ppe)
    for ppe in getattr(partner_data, "ppes", []):
        if duo_partner_id_from_options(getattr(ppe, "ppe_type_options", None)) != int(player_id):
            continue
        if player_link_id and duo_link_id_for_ppe(ppe) != player_link_id:
            continue
        return ppe
    return None


async def command(interaction: discord.Interaction):
    guild = await require_guild(interaction)
    if guild is None:
        return
    try:
        records = await load_player_records(interaction)
        scoring = await load_team_contest_scoring(interaction)
        contest_settings = await get_contest_settings(interaction)
        guild_config = await load_guild_config(interaction)
        ppe_settings = guild_config.get("ppe_settings", {}) if isinstance(guild_config.get("ppe_settings", {}), dict) else {}
        quest_settings = guild_config.get("quest_settings", {}) if isinstance(guild_config.get("quest_settings", {}), dict) else {}
        team_mode_effective = bool(quest_settings.get("enable_team_quests", False)) and not bool(
            quest_settings.get("use_global_quests", False)
        )
        include_ppe_quest_points = bool(contest_settings.get("ppe_contest_include_quest_points", False))
        require_active_ppe_items_for_quests = bool(contest_settings.get("ppe_contest_require_active_ppe_quest_items", True))
        ppe_quest_scoring = TeamContestScoring(include_quest_points=False)
        if include_ppe_quest_points:
            regular_quest_points, shiny_quest_points, skin_quest_points = await get_quest_points(interaction)
            ppe_quest_scoring = TeamContestScoring(
                include_quest_points=True,
                regular_quest_points=int(regular_quest_points),
                shiny_quest_points=int(shiny_quest_points),
                skin_quest_points=int(skin_quest_points),
            )

        leaderboard_data = []
        player_totals: dict[int, dict[str, Any]] = {}
        for pid, data in records.items():
            if not data.is_member:
                continue
            ppes = getattr(data, "ppes", [])
            if not isinstance(ppes, list) or not ppes:
                continue

            player = member_display_name(guild, pid)
            ppe_points = compute_ppe_points(
                data,
                aggregate=scoring.ppe_aggregate_points,
                guild_config=guild_config,
            )
            quest_points = 0.0
            if include_ppe_quest_points:
                if require_active_ppe_items_for_quests:
                    active_ppe_id = getattr(data, "active_ppe", None)
                    active_ppe = next((ppe for ppe in ppes if ppe.id == active_ppe_id), None)
                    quest_points = compute_quest_points_from_quests_and_active_ppe(
                        getattr(data, "quests", None),
                        active_ppe,
                        scoring=ppe_quest_scoring,
                    )
                elif team_mode_effective and isinstance(getattr(data, "team_name", None), str) and data.team_name:
                    quest_points = compute_team_shared_quest_points(
                        team_name=data.team_name,
                        quest_settings=quest_settings,
                        scoring=ppe_quest_scoring,
                    )
                else:
                    quest_points = compute_quest_points_from_quests(
                        getattr(data, "quests", None),
                        scoring=ppe_quest_scoring,
                    )

            points = ppe_points + quest_points
            best_ppe = get_best_ppe(data, guild_config=guild_config)
            leaderboard_data.append((int(pid), player, best_ppe, ppe_points, quest_points, points, len(ppes), data.active_ppe))
            player_totals[int(pid)] = {
                "player": player,
                "best_ppe": best_ppe,
                "ppe_points": ppe_points,
                "quest_points": quest_points,
                "points": points,
                "ppe_count": len(ppes),
                "active_ppe_id": data.active_ppe,
            }

        leaderboard_data.sort(key=lambda x: (x[5], x[3]), reverse=True)

        ranked_rows: list[tuple[float, str]] = []

        if scoring.ppe_aggregate_points:
            for pid, player, best_ppe, ppe_points, quest_points, points, ppe_count, active_ppe_id in leaderboard_data:
                count_label = "character" if ppe_count == 1 else "characters"
                if include_ppe_quest_points:
                    ranked_rows.append(
                        (
                            float(points),
                            f"**{player.title()}** — All PPEs ({ppe_count} {count_label}) + Quest: "
                            f"{ppe_points:.1f} + {quest_points:.1f} = **{points:.1f}** pts",
                        )
                    )
                else:
                    ranked_rows.append(
                        (
                            float(points),
                            f"**{player.title()}** — All PPEs ({ppe_count} {count_label}): **{points:.1f}** pts",
                        )
                    )
        else:
            processed_duo_keys: set[str] = set()
            for pid, player, best_ppe, ppe_points, quest_points, points, ppe_count, active_ppe_id in leaderboard_data:
                if best_ppe is None:
                    continue

                is_inactive = active_ppe_id != best_ppe.id
                marker = " • (inactive)" if is_inactive else ""
                ppe_type = ppe_type_compact_summary(
                    getattr(best_ppe, "ppe_type_options", None),
                    fallback_type=normalize_ppe_type(getattr(best_ppe, "ppe_type", None)),
                    ppe_settings=ppe_settings,
                )
                class_label = f"{best_ppe.name} [{ppe_type}]"
                options = _duo_options(best_ppe)
                if bool(options.get("duo_enabled", False)):
                    partner_id = _duo_partner_id(best_ppe)
                    if partner_id is None:
                        print(
                            "[WARN][ppeleaderboard] duo_enabled PPE has no valid partner_id "
                            f"guild_id={guild.id} player_id={pid} ppe_id={getattr(best_ppe, 'id', '?')} options={options}"
                        )
                        display_player = player.title()
                    else:
                        pair_ids = sorted((int(pid), int(partner_id)))
                        duo_link_key = str(options.get("duo_link_id", "")).strip() or "none"
                        pair_key = f"{pair_ids[0]}:{pair_ids[1]}:{duo_link_key}"
                        if pair_key in processed_duo_keys:
                            continue
                        partner_name = member_display_name(guild, int(partner_id)).title()
                        partner_total = player_totals.get(int(partner_id))
                        partner_data = records.get(int(partner_id))
                        partner_ppe = _find_matching_duo_partner_ppe(int(pid), best_ppe, partner_data)

                        if partner_ppe is None:
                            print(
                                "[WARN][ppeleaderboard] skipping duo aggregation due to missing linked partner PPE "
                                f"guild_id={guild.id} player_id={pid} partner_id={partner_id} "
                                f"ppe_id={getattr(best_ppe, 'id', '?')} pair_key={pair_key}"
                            )
                            display_player = player.title()
                        elif not isinstance(partner_total, dict):
                            print(
                                "[WARN][ppeleaderboard] skipping duo aggregation due to missing partner totals "
                                f"guild_id={guild.id} player_id={pid} partner_id={partner_id} pair_key={pair_key}"
                            )
                            display_player = player.title()
                        else:
                            processed_duo_keys.add(pair_key)
                            display_player = f"{player.title()} + {partner_name}"
                            partner_ppe_type = ppe_type_compact_summary(
                                getattr(partner_ppe, "ppe_type_options", None),
                                fallback_type=normalize_ppe_type(getattr(partner_ppe, "ppe_type", None)),
                                ppe_settings=ppe_settings,
                            )
                            partner_class_name = getattr(partner_ppe, "name", "?")
                            if partner_ppe_type == ppe_type:
                                class_label = f"{best_ppe.name} + {partner_class_name} [{ppe_type}]"
                            else:
                                class_label = (
                                    f"{best_ppe.name} [{ppe_type}] + {partner_class_name} [{partner_ppe_type}]"
                                )

                            player_duo_ppe_points = float(compute_effective_ppe_points(best_ppe, guild_config=guild_config))
                            partner_duo_ppe_points = float(compute_effective_ppe_points(partner_ppe, guild_config=guild_config))
                            ppe_points = player_duo_ppe_points + partner_duo_ppe_points
                            quest_points += float(partner_total.get("quest_points", 0.0))
                            points = ppe_points + quest_points
                            marker = ""
                else:
                    display_player = player.title()
                if include_ppe_quest_points:
                    ranked_rows.append(
                        (
                            float(points),
                            f"**{display_player}** — {class_label}: "
                            f"{ppe_points:.1f} + {quest_points:.1f} = **{points:.1f}** pts{marker}",
                        )
                    )
                else:
                    ranked_rows.append(
                        (float(points), f"**{display_player}** — {class_label}: **{points:.1f}** pts{marker}")
                    )

        ranked_rows.sort(key=lambda item: item[0], reverse=True)
        rows = [item[1] for item in ranked_rows]

        await send_leaderboard(
            interaction,
            title="PPE Leaderboard",
            entries=build_ranked_entry_lines(rows),
            color=discord.Color.gold(),
            empty_message="No PPE data available yet.\nPlayers can use `/newppe` to start competing.",
        )
    except Exception as e:
        guild_id = interaction.guild.id if interaction.guild is not None else "dm"
        print(
            "[ERROR][ppeleaderboard] command failed "
            f"guild_id={guild_id} user_id={interaction.user.id} error={type(e).__name__}: {e}"
        )
        print(traceback.format_exc())
        await send_error_response(interaction, str(e))
