

import discord

from dataclass import Loot, PPEData


async def build_loot_embed(active_ppe: PPEData, recently_added: str = "") -> discord.Embed:
    loot_dict = active_ppe.loot
        
    loot_lines = []
    if not loot_dict:
        loot_lines.append("• _No loot recorded yet._")
    else:
        for loot in loot_dict:
            name_with_tags = loot.item_name
            if loot.divine:
                name_with_tags += " (divine)"
            if loot.shiny:
                name_with_tags += " (shiny)"
            if loot.item_name == recently_added:
                loot_lines.append(f"• **{name_with_tags} × {loot.quantity}**")
            else:
                loot_lines.append(f"• *{name_with_tags} × {loot.quantity}*")

    embed = discord.Embed(
        title=f"Loot for your {active_ppe.name} (PPE #{active_ppe.id}) ({int(active_ppe.points) if active_ppe.points == int(active_ppe.points) else f'{active_ppe.points:.1f}'} points)",
        description="\n".join(loot_lines),
        color=discord.Color.blue()
    )
    return embed