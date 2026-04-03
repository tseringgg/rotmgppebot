import discord

from menus.leaderboard.common import build_ranked_entry_lines, send_error_response, send_leaderboard
from menus.leaderboard.services import member_display_name, require_guild
from utils.ppe_types import normalize_ppe_type, ppe_type_short_label
from utils.player_records import load_player_records


async def command(interaction: discord.Interaction, class_name: str):
    guild = await require_guild(interaction)
    if guild is None:
        return

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
                    player = member_display_name(guild, pid)
                    is_inactive = data.active_ppe != ppe.id
                    ppe_type = ppe_type_short_label(normalize_ppe_type(getattr(ppe, "ppe_type", None)))
                    character_data.append((player, ppe.id, ppe.points, ppe_type, pid, is_inactive))

        character_data.sort(key=lambda x: x[2], reverse=True)

        rows = []
        for player, ppe_id, points, ppe_type, _pid, is_inactive in character_data:
            marker = " • (inactive)" if is_inactive else ""
            rows.append(f"**{player.title()}** — PPE #{ppe_id} [{ppe_type}]: **{points:.1f}** pts{marker}")

        await send_leaderboard(
            interaction,
            title=f"{class_name} Leaderboard",
            entries=build_ranked_entry_lines(rows),
            color=discord.Color.teal(),
            empty_message=f"No `{class_name}` characters found on the leaderboard yet.",
        )
    except Exception as e:
        await send_error_response(interaction, str(e))
