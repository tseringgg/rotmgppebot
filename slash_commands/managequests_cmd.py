import discord

from utils.player_records import load_player_records, save_player_records
from utils.guild_config import load_guild_config, save_guild_config
from utils.quest_manager import apply_quest_targets


async def command(
    interaction: discord.Interaction,
    regular_quests: int | None = None,
    shiny_quests: int | None = None,
    skin_quests: int | None = None,
    regular_points: int | None = None,
    shiny_points: int | None = None,
    skin_points: int | None = None,
):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)

    for value, label in (
        (regular_quests, "regular_quests"),
        (shiny_quests, "shiny_quests"),
        (skin_quests, "skin_quests"),
        (regular_points, "regular_points"),
        (shiny_points, "shiny_points"),
        (skin_points, "skin_points"),
    ):
        if value is not None and value < 0:
            return await interaction.response.send_message(
                f"❌ `{label}` must be 0 or greater.",
                ephemeral=True,
            )

    try:
        config = await load_guild_config(interaction)
        before = dict(config["quest_settings"])

        if (
            regular_quests is None
            and shiny_quests is None
            and skin_quests is None
            and regular_points is None
            and shiny_points is None
            and skin_points is None
        ):
            settings = config["quest_settings"]
            embed = discord.Embed(
                title="Quest Management",
                description="Current server quest generation and leaderboard scoring settings.",
                color=discord.Color.blurple(),
            )
            embed.add_field(
                name="Quest Generation",
                value=(
                    f"Regular: **{settings['regular_target']}**\n"
                    f"Shiny: **{settings['shiny_target']}**\n"
                    f"Skin: **{settings['skin_target']}**"
                ),
                inline=True,
            )
            embed.add_field(
                name="Leaderboard Points",
                value=(
                    f"Regular: **{settings['regular_points']}**\n"
                    f"Shiny: **{settings['shiny_points']}**\n"
                    f"Skin: **{settings['skin_points']}**"
                ),
                inline=True,
            )
            embed.set_footer(text="Use /managequests with any fields to update values.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        settings = dict(config.get("quest_settings", {}))

        if regular_quests is not None:
            settings["regular_target"] = regular_quests
        if shiny_quests is not None:
            settings["shiny_target"] = shiny_quests
        if skin_quests is not None:
            settings["skin_target"] = skin_quests
        if regular_points is not None:
            settings["regular_points"] = regular_points
        if shiny_points is not None:
            settings["shiny_points"] = shiny_points
        if skin_points is not None:
            settings["skin_points"] = skin_points

        config["quest_settings"] = settings
        updated_config = await save_guild_config(interaction, config)
        settings = updated_config["quest_settings"]

        players_adjusted = 0
        active_entries_removed = 0
        quest_targets_changed = any(v is not None for v in (regular_quests, shiny_quests, skin_quests))

        if quest_targets_changed:
            records = await load_player_records(interaction)

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

        changed_lines = []
        for key, label in (
            ("regular_target", "Regular quests"),
            ("shiny_target", "Shiny quests"),
            ("skin_target", "Skin quests"),
            ("regular_points", "Regular points"),
            ("shiny_points", "Shiny points"),
            ("skin_points", "Skin points"),
        ):
            if before.get(key) != settings.get(key):
                changed_lines.append(f"{label}: **{before.get(key)} → {settings.get(key)}**")

        embed = discord.Embed(
            title="Quest Management Updated",
            description="✅ Settings saved for this server.",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Quest Generation",
            value=(
                f"Regular: **{settings['regular_target']}**\n"
                f"Shiny: **{settings['shiny_target']}**\n"
                f"Skin: **{settings['skin_target']}**"
            ),
            inline=True,
        )
        embed.add_field(
            name="Leaderboard Points",
            value=(
                f"Regular: **{settings['regular_points']}**\n"
                f"Shiny: **{settings['shiny_points']}**\n"
                f"Skin: **{settings['skin_points']}**"
            ),
            inline=True,
        )
        embed.add_field(
            name="Applied Changes",
            value="\n".join(changed_lines) if changed_lines else "No value changes detected.",
            inline=False,
        )
        embed.add_field(
            name="Player Impact",
            value=(
                f"Players adjusted: **{players_adjusted}**\n"
                f"Active quests removed: **{active_entries_removed}**"
            ),
            inline=False,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
