import discord

from menus.leaderboard.common import build_ranked_entry_lines, send_error_response, send_leaderboard
from menus.leaderboard.services import member_display_name, require_guild
from utils.player_records import load_player_records


async def command(interaction: discord.Interaction):
    guild = await require_guild(interaction)
    if guild is None:
        return

    try:
        records = await load_player_records(interaction)

        leaderboard_data = []
        for pid, data in records.items():
            if not data.is_member:
                continue

            if hasattr(data, "get_unique_item_count"):
                unique_count = int(data.get_unique_item_count())
            else:
                unique_items = getattr(data, "unique_items", set())
                unique_count = len(unique_items) if isinstance(unique_items, (set, list, tuple)) else 0
            if unique_count == 0:
                continue

            player = member_display_name(guild, pid)
            leaderboard_data.append((player, unique_count))

        leaderboard_data.sort(key=lambda x: x[1], reverse=True)

        rows = [f"**{player}** — {count} unique items" for player, count in leaderboard_data]
        await send_leaderboard(
            interaction,
            title="Season Loot Leaderboard",
            entries=build_ranked_entry_lines(rows),
            color=discord.Color.gold(),
            empty_message=(
                "No season loot data available yet.\n"
                "Players can use `/addseasonloot` to start tracking unique items."
            ),
        )
    except Exception as e:
        await send_error_response(interaction, str(e))
