import discord

from menus.leaderboard.common import build_ranked_entry_lines, send_error_response, send_leaderboard
from utils.player_records import load_player_records


async def command(interaction: discord.Interaction, class_name: str):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")

    try:
        records = await load_player_records(interaction)

        character_data = []
        for pid, data in records.items():
            if not data.is_member:
                continue
            ppes = getattr(data, "ppes", [])
            if not isinstance(ppes, list) or not ppes:
                continue

            for ppe in ppes:
                if str(ppe.name).lower() == class_name.lower():
                    player = next((m.display_name for m in interaction.guild.members if m.id == pid), f"Unknown User ({pid})")
                    is_inactive = data.active_ppe != ppe.id
                    character_data.append((player, ppe.id, ppe.points, pid, is_inactive))

        character_data.sort(key=lambda x: x[2], reverse=True)

        rows = []
        for player, ppe_id, points, _pid, is_inactive in character_data:
            marker = " • (inactive)" if is_inactive else ""
            rows.append(f"**{player.title()}** — PPE #{ppe_id}: **{points:.1f}** pts{marker}")

        await send_leaderboard(
            interaction,
            title=f"{class_name} Leaderboard",
            entries=build_ranked_entry_lines(rows),
            color=discord.Color.teal(),
            empty_message=f"No `{class_name}` characters found on the leaderboard yet.",
        )
    except Exception as e:
        await send_error_response(interaction, str(e))
