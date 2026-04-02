"""Helpers for contest join embed reaction handling."""

from __future__ import annotations

import discord

from utils.guild_config import load_guild_config_by_id


async def handle_join_contest_reaction(bot: discord.Client, payload: discord.RawReactionActionEvent) -> None:
    """Grant PPE Player role and DM instructions when user reacts to configured join embed."""
    if payload.guild_id is None:
        return

    user_id = int(payload.user_id)
    if bot.user is not None and user_id == int(bot.user.id):
        return

    config = await load_guild_config_by_id(int(payload.guild_id))
    contest_settings = config.get("contest_settings", {}) if isinstance(config.get("contest_settings"), dict) else {}

    target_channel_id = int(contest_settings.get("join_contest_channel_id", 0) or 0)
    target_message_id = int(contest_settings.get("join_contest_message_id", 0) or 0)
    target_emoji = str(contest_settings.get("join_contest_emoji", "✅") or "✅").strip() or "✅"

    if target_channel_id <= 0 or target_message_id <= 0:
        return

    if int(payload.channel_id) != target_channel_id or int(payload.message_id) != target_message_id:
        return

    if str(payload.emoji) != target_emoji:
        return

    guild = bot.get_guild(int(payload.guild_id))
    if guild is None:
        return

    role = discord.utils.get(guild.roles, name="PPE Player")
    if role is None:
        return

    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

    if role not in member.roles:
        try:
            await member.add_roles(role, reason="Joined PPE contest via join embed reaction")
        except (discord.Forbidden, discord.HTTPException):
            return

    try:
        await member.send(
            "✅ You now have the PPE Player role.\n"
            "Use `/ppehelp` for setup steps and command guidance."
        )
    except (discord.Forbidden, discord.HTTPException):
        pass
