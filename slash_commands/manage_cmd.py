import discord
from discord import app_commands

from slash_commands import (
    addbonus_cmd,
    addbonusfor_cmd,
    addpenaltiesfor_cmd,
    addpointsfor_cmd,
    refreshallpoints_cmd,
    refreshpointsfor_cmd,
    removebonus_cmd,
    removebonusfrom_cmd,
)
from utils.autocomplete import bonus_autocomplete, class_autocomplete, target_user_bonus_autocomplete, user_bonus_autocomplete
from utils.guild_config import get_points_settings, update_class_points_modifiers, update_global_points_modifiers
from utils.role_checks import require_ppe_roles


manage_group = app_commands.Group(name="manage", description="Unified PPE management commands")
ppe_group = app_commands.Group(name="ppe", description="Manage PPE points and bonuses", parent=manage_group)
points_settings_group = app_commands.Group(name="pointsettings", description="Configure points modifiers", parent=manage_group)


@ppe_group.command(name="addbonus", description="Add a bonus to your active PPE.")
@app_commands.describe(bonus_name="Name of the bonus to add")
@app_commands.autocomplete(bonus_name=bonus_autocomplete)
@require_ppe_roles(player_required=True)
async def manage_ppe_addbonus(interaction: discord.Interaction, bonus_name: str):
    await addbonus_cmd.command(interaction, bonus_name)


@ppe_group.command(name="removebonus", description="Remove a bonus from your active PPE.")
@app_commands.describe(bonus_name="Name of the bonus to remove")
@app_commands.autocomplete(bonus_name=user_bonus_autocomplete)
@require_ppe_roles(player_required=True)
async def manage_ppe_removebonus(interaction: discord.Interaction, bonus_name: str):
    await removebonus_cmd.command(interaction, bonus_name)


@ppe_group.command(name="addbonusfor", description="Add a bonus to another player's PPE. Admin only.")
@app_commands.describe(user="The player to add bonus to", id="The PPE ID to target", bonus_name="Name of the bonus to add")
@app_commands.autocomplete(bonus_name=bonus_autocomplete)
@require_ppe_roles(admin_required=True)
async def manage_ppe_addbonusfor(interaction: discord.Interaction, user: discord.Member, id: int, bonus_name: str):
    await addbonusfor_cmd.command(interaction, user, id, bonus_name)


@ppe_group.command(name="removebonusfrom", description="Remove a bonus from another player's PPE. Admin only.")
@app_commands.describe(user="The player to remove bonus from", id="The PPE ID to target", bonus_name="Name of the bonus to remove")
@app_commands.autocomplete(bonus_name=target_user_bonus_autocomplete)
@require_ppe_roles(admin_required=True)
async def manage_ppe_removebonusfrom(interaction: discord.Interaction, user: discord.Member, id: int, bonus_name: str):
    await removebonusfrom_cmd.command(interaction, user, id, bonus_name)


@ppe_group.command(name="setpenaltiesfor", description="Set penalty bonuses on another player's PPE. Admin only.")
@app_commands.describe(
    user="The player whose PPE to update",
    id="The PPE ID to target",
    pet_level="Pet level (0-100)",
    num_exalts="Number of exalts (0-40)",
    percent_loot="Loot boost percentage (0-25)",
    incombat_reduction="In-combat damage reduction (0, 0.2, 0.4, 0.6, 0.8, 1.0)",
)
@require_ppe_roles(admin_required=True)
async def manage_ppe_setpenaltiesfor(
    interaction: discord.Interaction,
    user: discord.Member,
    id: int,
    pet_level: int,
    num_exalts: int,
    percent_loot: float,
    incombat_reduction: float,
):
    await addpenaltiesfor_cmd.command(interaction, user, id, pet_level, num_exalts, percent_loot, incombat_reduction)


@ppe_group.command(name="addpointsfor", description="Add points to another player's PPE. Admin only.")
@require_ppe_roles(admin_required=True)
async def manage_ppe_addpointsfor(interaction: discord.Interaction, member: discord.Member, ppe_id: int, amount: float):
    await addpointsfor_cmd.command(interaction, member, ppe_id, amount)


@ppe_group.command(name="refreshpointsfor", description="Recalculate points for a specific PPE. Admin only.")
@app_commands.describe(user="The player whose PPE to refresh", id="The PPE ID to recalculate")
@require_ppe_roles(admin_required=True)
async def manage_ppe_refreshpointsfor(interaction: discord.Interaction, user: discord.Member, id: int):
    await refreshpointsfor_cmd.command(interaction, user, id)


@ppe_group.command(name="refreshallpoints", description="Recalculate points for all PPEs in the server. Admin only.")
@require_ppe_roles(admin_required=True)
async def manage_ppe_refreshallpoints(interaction: discord.Interaction):
    await refreshallpoints_cmd.command(interaction)


@points_settings_group.command(name="view", description="Show current points modifier settings.")
@require_ppe_roles(admin_required=True)
async def manage_points_settings_view(interaction: discord.Interaction):
    settings = await get_points_settings(interaction)
    global_settings = settings.get("global", {})
    class_overrides = settings.get("class_overrides", {})

    lines = ["**Global Modifiers (%):**"]
    lines.append(f"• Loot: {global_settings.get('loot_percent', 0.0):.2f}%")
    lines.append(f"• Bonus: {global_settings.get('bonus_percent', 0.0):.2f}%")
    lines.append(f"• Penalty: {global_settings.get('penalty_percent', 0.0):.2f}%")
    lines.append(f"• Total: {global_settings.get('total_percent', 0.0):.2f}%")

    if class_overrides:
        lines.append("")
        lines.append("**Class Overrides:**")
        for class_name in sorted(class_overrides.keys()):
            override = class_overrides[class_name]
            min_total = override.get("minimum_total")
            min_text = "none" if min_total is None else f"{float(min_total):.2f}"
            lines.append(
                f"• {class_name}: loot {float(override.get('loot_percent', 0.0)):.2f}%, "
                f"bonus {float(override.get('bonus_percent', 0.0)):.2f}%, "
                f"penalty {float(override.get('penalty_percent', 0.0)):.2f}%, "
                f"total {float(override.get('total_percent', 0.0)):.2f}%, "
                f"minimum_total {min_text}"
            )
    else:
        lines.append("")
        lines.append("No class overrides configured.")

    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@points_settings_group.command(name="setglobal", description="Set global points modifiers (%).")
@app_commands.describe(
    loot_percent="Percent modifier for loot points",
    bonus_percent="Percent modifier for bonus points",
    penalty_percent="Percent modifier for penalty points",
    total_percent="Percent modifier for final total points",
)
@require_ppe_roles(admin_required=True)
async def manage_points_settings_setglobal(
    interaction: discord.Interaction,
    loot_percent: float | None = None,
    bonus_percent: float | None = None,
    penalty_percent: float | None = None,
    total_percent: float | None = None,
):
    if all(value is None for value in [loot_percent, bonus_percent, penalty_percent, total_percent]):
        return await interaction.response.send_message("❌ Provide at least one modifier to update.", ephemeral=True)

    settings = await update_global_points_modifiers(
        interaction,
        loot_percent=loot_percent,
        bonus_percent=bonus_percent,
        penalty_percent=penalty_percent,
        total_percent=total_percent,
    )

    global_settings = settings.get("global", {})
    await interaction.response.send_message(
        "✅ Updated global point modifiers in this guild config.\n"
        f"Loot: {global_settings.get('loot_percent', 0.0):.2f}%\n"
        f"Bonus: {global_settings.get('bonus_percent', 0.0):.2f}%\n"
        f"Penalty: {global_settings.get('penalty_percent', 0.0):.2f}%\n"
        f"Total: {global_settings.get('total_percent', 0.0):.2f}%",
        ephemeral=True,
    )


@points_settings_group.command(name="setclass", description="Set class-specific points modifiers.")
@app_commands.describe(
    class_name="Class to configure",
    loot_percent="Percent modifier for loot points",
    bonus_percent="Percent modifier for bonus points",
    penalty_percent="Percent modifier for penalty points",
    total_percent="Percent modifier for final total points",
    minimum_total="Minimum final point total floor for this class",
)
@app_commands.autocomplete(class_name=class_autocomplete)
@require_ppe_roles(admin_required=True)
async def manage_points_settings_setclass(
    interaction: discord.Interaction,
    class_name: str,
    loot_percent: float | None = None,
    bonus_percent: float | None = None,
    penalty_percent: float | None = None,
    total_percent: float | None = None,
    minimum_total: float | None = None,
):
    if all(value is None for value in [loot_percent, bonus_percent, penalty_percent, total_percent, minimum_total]):
        return await interaction.response.send_message("❌ Provide at least one modifier to update.", ephemeral=True)

    settings = await update_class_points_modifiers(
        interaction,
        class_name=class_name,
        loot_percent=loot_percent,
        bonus_percent=bonus_percent,
        penalty_percent=penalty_percent,
        total_percent=total_percent,
        minimum_total=minimum_total,
    )

    class_override = settings.get("class_overrides", {}).get(class_name, {})
    if not class_override:
        return await interaction.response.send_message(
            f"✅ Cleared class override for {class_name}.",
            ephemeral=True,
        )

    min_total = class_override.get("minimum_total")
    min_text = "none" if min_total is None else f"{float(min_total):.2f}"
    await interaction.response.send_message(
        f"✅ Updated class override for {class_name}.\n"
        f"Loot: {float(class_override.get('loot_percent', 0.0)):.2f}%\n"
        f"Bonus: {float(class_override.get('bonus_percent', 0.0)):.2f}%\n"
        f"Penalty: {float(class_override.get('penalty_percent', 0.0)):.2f}%\n"
        f"Total: {float(class_override.get('total_percent', 0.0)):.2f}%\n"
        f"Minimum total: {min_text}",
        ephemeral=True,
    )
