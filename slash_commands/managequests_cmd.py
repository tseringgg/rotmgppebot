import discord

from utils.player_records import load_player_records, save_player_records
from utils.guild_config import get_quest_targets, set_quest_targets
from utils.quest_manager import apply_quest_targets


async def command(
    interaction: discord.Interaction,
    regular_quests: int | None = None,
    shiny_quests: int | None = None,
    skin_quests: int | None = None,
):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)

    for value, label in (
        (regular_quests, "regular_quests"),
        (shiny_quests, "shiny_quests"),
        (skin_quests, "skin_quests"),
    ):
        if value is not None and value < 0:
            return await interaction.response.send_message(
                f"❌ `{label}` must be 0 or greater.",
                ephemeral=True,
            )

    try:
        if regular_quests is None and shiny_quests is None and skin_quests is None:
            regular_target, shiny_target, skin_target = await get_quest_targets(interaction)
            return await interaction.response.send_message(
                "Current quest settings:\n"
                f"- Regular quests: {regular_target}\n"
                f"- Shiny quests: {shiny_target}\n"
                f"- Skin quests: {skin_target}",
                ephemeral=True,
            )

        updated_config = await set_quest_targets(
            interaction,
            regular_target=regular_quests,
            shiny_target=shiny_quests,
            skin_target=skin_quests,
        )
        settings = updated_config["quest_settings"]

        records = await load_player_records(interaction)

        players_adjusted = 0
        active_entries_removed = 0

        for player_data in records.values():
            result = apply_quest_targets(
                player_data,
                target_item_quests=settings["regular_target"],
                target_shiny_quests=settings["shiny_target"],
                target_skin_quests=settings["skin_target"],
            )
            if result["changed"]:
                players_adjusted += 1
                active_entries_removed += (
                    len(result["removed_current_items"])
                    + len(result["removed_current_shinies"])
                    + len(result["removed_current_skins"])
                )

        if players_adjusted > 0:
            await save_player_records(interaction, records)

        await interaction.response.send_message(
            "✅ Quest settings updated.\n"
            f"- Regular quests: {settings['regular_target']}\n"
            f"- Shiny quests: {settings['shiny_target']}\n"
            f"- Skin quests: {settings['skin_target']}\n"
            f"- Players adjusted: {players_adjusted}\n"
            f"- Active quests removed due to lower limits: {active_entries_removed}",
            ephemeral=False,
        )
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
