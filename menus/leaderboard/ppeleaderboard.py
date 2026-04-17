import discord
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


def _duo_link_id(ppe: Any) -> str | None:
    options = _duo_options(ppe)
    raw = str(options.get("duo_link_id", "")).strip()
    return raw or None


def _find_confirmed_duo_pair(records: dict[int, Any], owner_id: int, owner_ppe: Any) -> tuple[int, Any, tuple[Any, ...]] | None:
    partner_id = _duo_partner_id(owner_ppe)
    if partner_id is None or partner_id == owner_id:
        return None

    partner_data = records.get(partner_id)
    if partner_data is None or not bool(getattr(partner_data, "is_member", False)):
        return None

    partner_ppes = getattr(partner_data, "ppes", None)
    if not isinstance(partner_ppes, list) or not partner_ppes:
        return None

    owner_link_id = _duo_link_id(owner_ppe)
    owner_ppe_id = int(getattr(owner_ppe, "id", 0) or 0)
    for partner_ppe in partner_ppes:
        if _duo_partner_id(partner_ppe) != owner_id:
            continue

        partner_link_id = _duo_link_id(partner_ppe)
        if owner_link_id and partner_link_id and owner_link_id == partner_link_id:
            pair_key = ("link", min(owner_id, partner_id), max(owner_id, partner_id), owner_link_id)
            return partner_id, partner_ppe, pair_key

        partner_ppe_id = int(getattr(partner_ppe, "id", 0) or 0)
        if owner_ppe_id > 0 and owner_ppe_id == partner_ppe_id:
            pair_key = ("id", min(owner_id, partner_id), max(owner_id, partner_id), owner_ppe_id)
            return partner_id, partner_ppe, pair_key

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
        selected_duo_rows: dict[int, tuple[int, Any, tuple[Any, ...]]] = {}
        paired_member_ids: set[int] = set()
        seen_duo_pairs: set[tuple[Any, ...]] = set()

        for pid, _player, best_ppe, _ppe_points, _quest_points, _points, _ppe_count, _active_ppe_id in leaderboard_data:
            if scoring.ppe_aggregate_points or best_ppe is None:
                continue
            if int(pid) in paired_member_ids:
                continue

            duo_pair = _find_confirmed_duo_pair(records, int(pid), best_ppe)
            if duo_pair is None:
                continue

            partner_id, partner_ppe, pair_key = duo_pair
            if pair_key in seen_duo_pairs or int(partner_id) in paired_member_ids:
                continue

            selected_duo_rows[int(pid)] = (int(partner_id), partner_ppe, pair_key)
            paired_member_ids.add(int(pid))
            paired_member_ids.add(int(partner_id))
            seen_duo_pairs.add(pair_key)

        for pid, player, best_ppe, ppe_points, quest_points, points, ppe_count, active_ppe_id in leaderboard_data:
            if scoring.ppe_aggregate_points:
                count_label = "character" if ppe_count == 1 else "characters"
                if include_ppe_quest_points:
                    ranked_rows.append((
                        float(points),
                        f"**{player.title()}** — All PPEs ({ppe_count} {count_label}) + Quest: "
                        f"{ppe_points:.1f} + {quest_points:.1f} = **{points:.1f}** pts"
                    ))
                else:
                    ranked_rows.append((
                        float(points),
                        f"**{player.title()}** — All PPEs ({ppe_count} {count_label}): **{points:.1f}** pts",
                    ))
                continue

            if best_ppe is None:
                continue

            if int(pid) in paired_member_ids and int(pid) not in selected_duo_rows:
                continue

            duo_pair = selected_duo_rows.get(int(pid))
            if duo_pair is not None:
                partner_id, partner_ppe, _pair_key = duo_pair

                partner_summary = player_totals.get(int(partner_id))
                partner_name = member_display_name(guild, int(partner_id))
                owner_ppe_points = float(compute_effective_ppe_points(best_ppe, guild_config=guild_config))
                partner_ppe_points = float(compute_effective_ppe_points(partner_ppe, guild_config=guild_config))
                owner_quest_points = float(quest_points)
                partner_quest_points = float(partner_summary.get("quest_points", 0.0)) if isinstance(partner_summary, dict) else 0.0
                total_ppe_points = owner_ppe_points + partner_ppe_points
                total_quest_points = owner_quest_points + partner_quest_points
                duo_total = total_ppe_points + total_quest_points

                owner_inactive = active_ppe_id != getattr(best_ppe, "id", None)
                partner_active = partner_summary.get("active_ppe_id") if isinstance(partner_summary, dict) else None
                partner_inactive = partner_active != getattr(partner_ppe, "id", None)
                inactive_marker = " • (inactive)" if owner_inactive or partner_inactive else ""

                duo_type_left = ppe_type_compact_summary(
                    getattr(best_ppe, "ppe_type_options", None),
                    fallback_type=normalize_ppe_type(getattr(best_ppe, "ppe_type", None)),
                    ppe_settings=ppe_settings,
                )
                duo_type_right = ppe_type_compact_summary(
                    getattr(partner_ppe, "ppe_type_options", None),
                    fallback_type=normalize_ppe_type(getattr(partner_ppe, "ppe_type", None)),
                    ppe_settings=ppe_settings,
                )
                class_label = f"{best_ppe.name} [{duo_type_left}] + {partner_ppe.name} [{duo_type_right}]"

                if include_ppe_quest_points:
                    ranked_rows.append((
                        float(duo_total),
                        f"**{player.title()} + {partner_name.title()}** — {class_label}: "
                        f"{total_ppe_points:.1f} + {total_quest_points:.1f} = **{duo_total:.1f}** pts{inactive_marker}"
                    ))
                else:
                    ranked_rows.append((
                        float(total_ppe_points),
                        f"**{player.title()} + {partner_name.title()}** — {class_label}: **{total_ppe_points:.1f}** pts{inactive_marker}"
                    ))
                continue

            is_inactive = active_ppe_id != best_ppe.id
            marker = " • (inactive)" if is_inactive else ""
            ppe_type = ppe_type_compact_summary(
                getattr(best_ppe, "ppe_type_options", None),
                fallback_type=normalize_ppe_type(getattr(best_ppe, "ppe_type", None)),
                ppe_settings=ppe_settings,
            )
            class_label = f"{best_ppe.name} [{ppe_type}]"
            if include_ppe_quest_points:
                ranked_rows.append((
                    float(points),
                    f"**{player.title()}** — {class_label}: "
                    f"{ppe_points:.1f} + {quest_points:.1f} = **{points:.1f}** pts{marker}"
                ))
            else:
                ranked_rows.append((float(points), f"**{player.title()}** — {class_label}: **{points:.1f}** pts{marker}"))

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
        await send_error_response(interaction, str(e))
