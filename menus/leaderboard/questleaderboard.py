import discord

from utils.guild_config import get_quest_points
from menus.leaderboard.common import build_ranked_entry_lines, send_error_response, send_leaderboard
from menus.leaderboard.services import member_display_name, require_guild
from utils.player_records import load_player_records


def _safe_bucket_len(raw_value: object) -> int:
    return len(raw_value) if isinstance(raw_value, (list, tuple, set)) else 0


async def command(interaction: discord.Interaction):
    guild = await require_guild(interaction)
    if guild is None:
        return

    try:
        records = await load_player_records(interaction)
        regular_points, shiny_points, skin_points = await get_quest_points(interaction)

        leaderboard_data = []
        for pid, data in records.items():
            if not data.is_member:
                continue

            quests = getattr(data, "quests", None)
            completed_regular = _safe_bucket_len(getattr(quests, "completed_items", [])) if quests is not None else 0
            completed_shiny = _safe_bucket_len(getattr(quests, "completed_shinies", [])) if quests is not None else 0
            completed_skin = _safe_bucket_len(getattr(quests, "completed_skins", [])) if quests is not None else 0

            total_completed = completed_regular + completed_shiny + completed_skin
            total_points = (
                completed_regular * regular_points
                + completed_shiny * shiny_points
                + completed_skin * skin_points
            )

            if total_completed <= 0 and total_points <= 0:
                continue

            player_name = member_display_name(guild, pid)
            leaderboard_data.append((player_name, completed_regular, completed_shiny, completed_skin, total_points))

        leaderboard_data.sort(key=lambda x: (x[4], x[1] + x[2] + x[3]), reverse=True)

        rows = []
        for player_name, completed_regular, completed_shiny, completed_skin, total_points in leaderboard_data:
            rows.append(
                f"**{player_name}** — {completed_regular} Reg, {completed_shiny} Shiny, {completed_skin} Skin • **{total_points} pts**"
            )

        await send_leaderboard(
            interaction,
            title="Quest Leaderboard",
            entries=build_ranked_entry_lines(rows),
            color=discord.Color.gold(),
            header_lines=[f"Reg {regular_points} | Shiny {shiny_points} | Skin {skin_points}"],
            empty_message=(
                "No quest completions recorded yet.\n"
                "Players can use `/myquests` and complete objectives to appear here."
            ),
        )
    except Exception as e:
        await send_error_response(interaction, str(e))
