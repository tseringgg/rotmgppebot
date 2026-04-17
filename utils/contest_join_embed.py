"""Helpers for contest join embed reaction handling."""

from __future__ import annotations

import time

import discord

from utils.guild_config import load_guild_config_by_id


_CONTEST_SETTINGS_CACHE_TTL_SECONDS = 15.0
_CONTEST_SETTINGS_CACHE: dict[int, tuple[dict, float]] = {}
_CONTEST_SETTINGS_CACHE_MAX_ENTRIES = 5000
_CONTEST_SETTINGS_CACHE_PRUNE_EVERY = 64
_contest_cache_op_count = 0


def _prune_contest_settings_cache(now: float | None = None) -> None:
    now_monotonic = time.monotonic() if now is None else now
    expired_keys = [
        guild_id
        for guild_id, (_settings, expires_at) in _CONTEST_SETTINGS_CACHE.items()
        if now_monotonic > expires_at
    ]
    for guild_id in expired_keys:
        _CONTEST_SETTINGS_CACHE.pop(guild_id, None)

    overflow = len(_CONTEST_SETTINGS_CACHE) - _CONTEST_SETTINGS_CACHE_MAX_ENTRIES
    if overflow > 0:
        # Drop oldest-to-expire entries first when above cap.
        entries_by_expiry = sorted(_CONTEST_SETTINGS_CACHE.items(), key=lambda entry: entry[1][1])
        for guild_id, _value in entries_by_expiry[:overflow]:
            _CONTEST_SETTINGS_CACHE.pop(guild_id, None)


def _maybe_prune_contest_settings_cache() -> None:
    global _contest_cache_op_count
    _contest_cache_op_count += 1
    if _contest_cache_op_count % _CONTEST_SETTINGS_CACHE_PRUNE_EVERY == 0:
        _prune_contest_settings_cache()


def clear_contest_settings_cache(guild_id: int) -> None:
    _CONTEST_SETTINGS_CACHE.pop(int(guild_id), None)


def get_cache_size() -> int:
    return len(_CONTEST_SETTINGS_CACHE)


async def _get_contest_settings(guild_id: int) -> dict:
    _maybe_prune_contest_settings_cache()

    cached = _CONTEST_SETTINGS_CACHE.get(guild_id)
    now = time.monotonic()
    if cached is not None:
        contest_settings, expires_at = cached
        if now <= expires_at:
            return dict(contest_settings)

    config = await load_guild_config_by_id(guild_id)
    contest_settings = config.get("contest_settings", {}) if isinstance(config.get("contest_settings"), dict) else {}
    _CONTEST_SETTINGS_CACHE[guild_id] = (dict(contest_settings), now + _CONTEST_SETTINGS_CACHE_TTL_SECONDS)
    return dict(contest_settings)


async def handle_join_contest_reaction(bot: discord.Client, payload: discord.RawReactionActionEvent) -> None:
    """Grant PPE Player role and DM instructions when user reacts to configured join embed."""
    if payload.guild_id is None:
        return

    user_id = int(payload.user_id)
    if bot.user is not None and user_id == int(bot.user.id):
        return

    contest_settings = await _get_contest_settings(int(payload.guild_id))

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

    member = payload.member if isinstance(payload.member, discord.Member) else guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

    granted_role = False
    if role not in member.roles:
        try:
            await member.add_roles(role, reason="Joined PPE contest via join embed reaction")
            granted_role = True
        except (discord.Forbidden, discord.HTTPException):
            return

    if granted_role:
        try:
            await member.send(
                "✅ You now have the PPE Player role.\n"
                "Use `/ppehelp` for setup steps and command guidance."
            )
        except (discord.Forbidden, discord.HTTPException):
            pass


async def handle_leave_contest_reaction(bot: discord.Client, payload: discord.RawReactionActionEvent) -> None:
    """Remove PPE Player role when user removes their reaction from the configured join embed."""
    if payload.guild_id is None:
        return

    user_id = int(payload.user_id)
    if bot.user is not None and user_id == int(bot.user.id):
        return

    contest_settings = await _get_contest_settings(int(payload.guild_id))

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

    if role in member.roles:
        try:
            await member.remove_roles(role, reason="Left PPE contest via join embed reaction removal")
        except (discord.Forbidden, discord.HTTPException):
            return
