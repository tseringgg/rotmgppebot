import discord

from utils.player_records import (
    get_item_suggestions_enabled,
    set_item_suggestions_enabled,
    toggle_item_suggestions,
)


async def command(interaction: discord.Interaction, action: str):
    # Guild-only
    if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message(
            "❌ This command can only be used in a server channel.",
            ephemeral=True,
        )

    # Require Manage Channel or Administrator
    member = interaction.user
    if not isinstance(member, discord.Member):
        return await interaction.response.send_message(
            "❌ This command can only be used by a server member.",
            ephemeral=True,
        )

    perms = interaction.channel.permissions_for(member)
    if not (perms.manage_channels or perms.administrator):
        return await interaction.response.send_message(
            "❌ You need the **Manage Channel** (or Administrator) permission to use this command.",
            ephemeral=True,
        )

    guild_id = str(interaction.guild.id)
    channel_id = str(interaction.channel.id)

    print(
        f"[itemsuggestions] guild={guild_id} channel={channel_id} "
        f"user={interaction.user.id} action={action}"
    )

    if action == "on":
        await set_item_suggestions_enabled(guild_id, channel_id, True)
        return await interaction.response.send_message(
            "✅ Item suggestions are now **enabled** in this channel.",
            ephemeral=True,
        )

    if action == "off":
        await set_item_suggestions_enabled(guild_id, channel_id, False)
        return await interaction.response.send_message(
            "✅ Item suggestions are now **disabled** in this channel.",
            ephemeral=True,
        )

    if action == "toggle":
        new_state = await toggle_item_suggestions(guild_id, channel_id)
        state_label = "on" if new_state else "off"
        return await interaction.response.send_message(
            f"🔁 Item suggestions have been toggled **{state_label}** in this channel.",
            ephemeral=True,
        )

    if action == "status":
        enabled = await get_item_suggestions_enabled(guild_id, channel_id)
        state_label = "**on**" if enabled else "**off**"
        return await interaction.response.send_message(
            f"ℹ️ Item suggestions are currently {state_label} in this channel.",
            ephemeral=True,
        )

    # Fallback (should never reach here with choices enforced by Discord)
    await interaction.response.send_message(
        "❌ Unknown action. Use `on`, `off`, `toggle`, or `status`.",
        ephemeral=True,
    )
