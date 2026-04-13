import discord

from menus.leaderboard.common import build_ranked_entry_lines, send_error_response, send_leaderboard
from menus.leaderboard.services import member_display_name, require_guild
from utils.team_contest_scoring import compute_ppe_points, get_best_ppe, load_team_contest_scoring
from utils.guild_config import get_contest_settings, get_quest_points
from utils.player_records import load_player_records


async def command(interaction: discord.Interaction):
    guild = await require_guild(interaction)
    if guild is None:
        return
    try:
        records = await load_player_records(interaction)
        scoring = await load_team_contest_scoring(interaction)
        contest_settings = await get_contest_settings(interaction)
        include_ppe_quest_points = bool(contest_settings.get("ppe_contest_include_quest_points", False))

        regular_quest_points = 0
        shiny_quest_points = 0
        skin_quest_points = 0
        if include_ppe_quest_points:
            regular_quest_points, shiny_quest_points, skin_quest_points = await get_quest_points(interaction)

        leaderboard_data = []
        for pid, data in records.items():
            if not data.is_member:
                continue
            ppes = getattr(data, "ppes", [])
            if not isinstance(ppes, list) or not ppes:
                continue

            player = member_display_name(guild, pid)
            ppe_points = compute_ppe_points(data, aggregate=scoring.ppe_aggregate_points)
            quest_points = 0.0
            if include_ppe_quest_points:
                quests = getattr(data, "quests", None)
                if quests is not None:
                    quest_points = float(
                        len(getattr(quests, "completed_items", [])) * int(regular_quest_points)
                        + len(getattr(quests, "completed_shinies", [])) * int(shiny_quest_points)
                        + len(getattr(quests, "completed_skins", [])) * int(skin_quest_points)
                    )

            points = ppe_points + quest_points
            best_ppe = get_best_ppe(data)
            leaderboard_data.append((player, best_ppe, ppe_points, quest_points, points, len(ppes), data.active_ppe))

        leaderboard_data.sort(key=lambda x: (x[4], x[2]), reverse=True)

        rows = []
        for player, best_ppe, ppe_points, quest_points, points, ppe_count, active_ppe_id in leaderboard_data:
            if scoring.ppe_aggregate_points:
                count_label = "character" if ppe_count == 1 else "characters"
                if include_ppe_quest_points:
                    rows.append(
                        f"**{player.title()}** — All PPEs ({ppe_count} {count_label}) + Quest: "
                        f"{ppe_points:.1f} + {quest_points:.1f} = **{points:.1f}** pts"
                    )
                else:
                    rows.append(f"**{player.title()}** — All PPEs ({ppe_count} {count_label}): **{points:.1f}** pts")
                continue

            if best_ppe is None:
                continue

            is_inactive = active_ppe_id != best_ppe.id
            marker = " • (inactive)" if is_inactive else ""
            if include_ppe_quest_points:
                rows.append(
                    f"**{player.title()}** — {best_ppe.name}: "
                    f"{ppe_points:.1f} + {quest_points:.1f} = **{points:.1f}** pts{marker}"
                )
            else:
                rows.append(f"**{player.title()}** — {best_ppe.name}: **{points:.1f}** pts{marker}")

        await send_leaderboard(
            interaction,
            title="PPE Leaderboard",
            entries=build_ranked_entry_lines(rows),
            color=discord.Color.gold(),
            empty_message="No PPE data available yet.\nPlayers can use `/newppe` to start competing.",
        )
    except Exception as e:
        await send_error_response(interaction, str(e))
