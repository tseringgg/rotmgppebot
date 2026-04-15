import discord
from dataclass import Bonus
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.bonus_data import load_bonuses
from utils.guild_config import load_guild_config
from utils.loot_ops import send_ppe_markdown_followup
from utils.points_service import recompute_ppe_points


def _format_points(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{float(value):.1f}".rstrip("0").rstrip(".")

async def command(interaction: discord.Interaction, bonus_name: str):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    # Load available bonuses
    available_bonuses = load_bonuses()
    
    # Validate bonus name
    if bonus_name not in available_bonuses:
        return await interaction.response.send_message(
            f"❌ `{bonus_name}` is not a valid bonus.\n"
            f"Use the autocomplete list to choose one.",
            ephemeral=True
        )

    # Acknowledge quickly before record/config I/O to avoid interaction timeout.
    await interaction.response.defer(thinking=True)
    
    # Load player records
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, interaction.user.id)
    player_data = records[key]
    
    # Check if player has an active PPE
    if player_data.active_ppe is None:
        return await interaction.followup.send(
            "❌ You don't have an active PPE. Create one first with `/newppe`.",
            ephemeral=True
        )
    
    # Find the active PPE
    active_ppe = None
    for ppe in player_data.ppes:
        if ppe.id == player_data.active_ppe:
            active_ppe = ppe
            break
    
    if not active_ppe:
        return await interaction.followup.send(
            "❌ Could not find your active PPE.",
            ephemeral=True
        )
    
    bonus_data = available_bonuses[bonus_name]
    old_points = float(active_ppe.points)
    
    # Check if bonus already exists
    existing_bonus = None
    for bonus in active_ppe.bonuses:
        if bonus.name == bonus_name:
            existing_bonus = bonus
            break
    
    if existing_bonus:
        if not bonus_data.repeatable:
            return await interaction.followup.send(
                f"❌ You already have the `{bonus_name}` bonus and it is not repeatable.",
                ephemeral=True
            )
        # Increment quantity for repeatable bonus
        existing_bonus.quantity += 1
        quantity_text = f" (quantity: {existing_bonus.quantity})"
    else:
        # Create new bonus instance
        new_bonus = Bonus(
            name=bonus_data.name,
            points=bonus_data.points,
            repeatable=bonus_data.repeatable,
            quantity=1
        )
        # Add bonus to PPE
        active_ppe.bonuses.append(new_bonus)
        quantity_text = ""

    old_points = round(float(active_ppe.points), 2)
    guild_config = await load_guild_config(interaction)
    recompute_ppe_points(active_ppe, guild_config)
    new_points = round(float(active_ppe.points), 2)
    
    # Save records
    await save_player_records(interaction=interaction, records=records)
    
    # Create response message
    repeatable_text = " (repeatable)" if bonus_data.repeatable else " (one-time)"
    response_msg = (
        f"✅ Bonus logged for PPE #{active_ppe.id} ({active_ppe.name})!{quantity_text}\n"
        f"Logged bonus: **{bonus_data.name}**\n"
        f"Bonus value: **+{bonus_data.points} points**{repeatable_text}\n"
        f"Points: {_format_points(old_points)} -> {_format_points(new_points)}"
    )

    await interaction.followup.send(response_msg, ephemeral=False)
    await send_ppe_markdown_followup(interaction, ppe=active_ppe, ephemeral=True)
