import discord

from menus.leaderboard.common import send_error_response
from menus.leaderboard.services import require_guild
from utils.team_manager import team_manager

async def command(interaction: discord.Interaction):
    if await require_guild(interaction) is None:
        return

    try:
        data = await team_manager.get_additional_team_leaderboards_data(interaction)

        embed = discord.Embed(
            title="Additional Team Leaderboards",
            color=discord.Color.gold(),
            description="Top 3 teams in various categories."
        )

        def format_top_3(entries, formatter, empty_msg="No data"):
            if not entries:
                return empty_msg
            lines = []
            for i, entry in enumerate(entries):
                lines.append(f"**{i+1}.** " + formatter(entry))
            return "\n".join(lines)

        regular_points = format_top_3(
            data["regular_points"], 
            lambda x: f"{x[0]}: {x[1]:g} pts"
        )
        embed.add_field(name="Regular Points", value=regular_points, inline=False)

        most_different = format_top_3(
            data["most_different_items"], 
            lambda x: f"{x[0]}: {x[1]} unique items"
        )
        embed.add_field(name="Most Different Items", value=most_different, inline=False)

        most_total = format_top_3(
            data["most_items_total"], 
            lambda x: f"{x[0]}: {x[1]} total items"
        )
        embed.add_field(name="Most Items Total", value=most_total, inline=False)

        most_of_one = format_top_3(
            data["most_of_one_item"], 
            lambda x: f"{x[0]}: {x[1]}x {x[2]}" if x[1] > 0 else f"{x[0]}: 0 items"
        )
        embed.add_field(name="Most of One Item", value=most_of_one, inline=False)

        most_dungeons = format_top_3(
            data["most_dungeons"], 
            lambda x: f"{x[0]}: {x[1]} dungeons"
        )
        embed.add_field(name="Whites from Most Dungeons", value=most_dungeons, inline=False)

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)
    except Exception as e:
        await send_error_response(interaction, str(e))
