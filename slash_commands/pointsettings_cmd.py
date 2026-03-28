from __future__ import annotations

import discord

from utils.guild_config import get_points_settings, update_class_points_modifiers, update_global_points_modifiers


async def view(interaction: discord.Interaction) -> None:
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


async def set_global(
    interaction: discord.Interaction,
    *,
    loot_percent: float | None = None,
    bonus_percent: float | None = None,
    penalty_percent: float | None = None,
    total_percent: float | None = None,
) -> None:
    if all(value is None for value in [loot_percent, bonus_percent, penalty_percent, total_percent]):
        await interaction.response.send_message("❌ Provide at least one modifier to update.", ephemeral=True)
        return

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


async def set_class(
    interaction: discord.Interaction,
    *,
    class_name: str,
    loot_percent: float | None = None,
    bonus_percent: float | None = None,
    penalty_percent: float | None = None,
    total_percent: float | None = None,
    minimum_total: float | None = None,
) -> None:
    if all(value is None for value in [loot_percent, bonus_percent, penalty_percent, total_percent, minimum_total]):
        await interaction.response.send_message("❌ Provide at least one modifier to update.", ephemeral=True)
        return

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
        await interaction.response.send_message(
            f"✅ Cleared class override for {class_name}.",
            ephemeral=True,
        )
        return

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
