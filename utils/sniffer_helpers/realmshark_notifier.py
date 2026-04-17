"""Utilities for realmshark notifier."""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable

import discord

from utils.player_records import ensure_player_exists, load_player_records
from utils.image_utils import overlay_rarity_badge


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return max(minimum, default)

    try:
        parsed = float(raw_value)
    except ValueError:
        return max(minimum, default)

    return max(minimum, parsed)


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return max(minimum, default)

    try:
        parsed = int(raw_value)
    except ValueError:
        return max(minimum, default)

    return max(minimum, parsed)


_CHANNEL_CACHE_TTL_SECONDS = _env_float("REALMSHARK_CHANNEL_CACHE_TTL_SECONDS", default=300.0, minimum=5.0)
_MIN_SEND_INTERVAL_SECONDS = _env_float("REALMSHARK_MIN_SEND_INTERVAL_SECONDS", default=0.35, minimum=0.0)
_CHANNEL_CACHE_MAX_ENTRIES = _env_int("REALMSHARK_CHANNEL_CACHE_MAX_ENTRIES", default=5000, minimum=100)
_CHANNEL_CACHE_PRUNE_EVERY = _env_int("REALMSHARK_CHANNEL_CACHE_PRUNE_EVERY", default=128, minimum=1)
_CHANNEL_CACHE: dict[int, tuple[int, float]] = {}
_channel_cache_op_count = 0
_SEND_LOCK = asyncio.Lock()
_NEXT_ALLOWED_SEND_MONOTONIC = 0.0
_GuildMessageChannel = discord.TextChannel | discord.Thread


def _discord_absolute_now() -> str:
    return f"<t:{int(datetime.now(timezone.utc).timestamp())}:f>"


def _with_optional_timestamp(message: str) -> str:
    is_bound_message = message.startswith("RealmShark is successfully bound to")
    is_loot_message = ("It was logged to" in message) or ("It was already logged to" in message)

    if is_bound_message or is_loot_message:
        return f"{message} | {_discord_absolute_now()}"

    return message


def _is_writable_message_channel(
    channel: discord.abc.GuildChannel | discord.Thread | None,
    me: discord.Member | None,
) -> bool:
    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        return False
    if me is None:
        return False
    perms = channel.permissions_for(me)
    if isinstance(channel, discord.Thread):
        return bool(perms.send_messages_in_threads or perms.send_messages)
    return bool(perms.send_messages)


def _prune_announce_channel_cache(now: float | None = None) -> None:
    now_monotonic = time.monotonic() if now is None else now

    expired_keys = [
        guild_id
        for guild_id, (_channel_id, cached_at) in _CHANNEL_CACHE.items()
        if (now_monotonic - cached_at) > _CHANNEL_CACHE_TTL_SECONDS
    ]
    for guild_id in expired_keys:
        _CHANNEL_CACHE.pop(guild_id, None)

    overflow = len(_CHANNEL_CACHE) - _CHANNEL_CACHE_MAX_ENTRIES
    if overflow > 0:
        # Keep the most recent channel resolutions when above cap.
        entries_by_recency = sorted(_CHANNEL_CACHE.items(), key=lambda entry: entry[1][1], reverse=True)
        _CHANNEL_CACHE.clear()
        for guild_id, value in entries_by_recency[:_CHANNEL_CACHE_MAX_ENTRIES]:
            _CHANNEL_CACHE[guild_id] = value


def _maybe_prune_announce_channel_cache() -> None:
    global _channel_cache_op_count
    _channel_cache_op_count += 1
    if _channel_cache_op_count % _CHANNEL_CACHE_PRUNE_EVERY == 0:
        _prune_announce_channel_cache()


def clear_cached_announce_channel(guild_id: int) -> None:
    _CHANNEL_CACHE.pop(int(guild_id), None)


def get_channel_cache_size() -> int:
    return len(_CHANNEL_CACHE)


def _get_cached_announce_channel(guild: discord.Guild, me: discord.Member | None) -> _GuildMessageChannel | None:
    _maybe_prune_announce_channel_cache()

    cached = _CHANNEL_CACHE.get(guild.id)
    if cached is None:
        return None

    channel_id, cached_at = cached
    if (time.monotonic() - cached_at) > _CHANNEL_CACHE_TTL_SECONDS:
        _CHANNEL_CACHE.pop(guild.id, None)
        return None

    resolver = getattr(guild, "get_channel_or_thread", guild.get_channel)
    channel = resolver(channel_id)
    if not _is_writable_message_channel(channel, me):
        _CHANNEL_CACHE.pop(guild.id, None)
        return None

    return channel


def _cache_announce_channel(guild_id: int, channel_id: int) -> None:
    _maybe_prune_announce_channel_cache()
    _CHANNEL_CACHE[guild_id] = (channel_id, time.monotonic())


async def _throttled_send(
    channel: _GuildMessageChannel,
    *,
    content: str,
    file: discord.File | None = None,
    allowed_mentions: discord.AllowedMentions | None = None,
) -> None:
    global _NEXT_ALLOWED_SEND_MONOTONIC

    async with _SEND_LOCK:
        if _MIN_SEND_INTERVAL_SECONDS > 0:
            wait_for = _NEXT_ALLOWED_SEND_MONOTONIC - time.monotonic()
            if wait_for > 0:
                await asyncio.sleep(wait_for)

        if file is None:
            await channel.send(content=content, allowed_mentions=allowed_mentions)
        else:
            await channel.send(content=content, file=file, allowed_mentions=allowed_mentions)

        if _MIN_SEND_INTERVAL_SECONDS > 0:
            _NEXT_ALLOWED_SEND_MONOTONIC = time.monotonic() + _MIN_SEND_INTERVAL_SECONDS


async def _get_target_ppe(
    guild_id: int,
    user_id: int,
    ppe_id: int,
):
    class _SyntheticGuild:
        def __init__(self, gid: int) -> None:
            self.id = gid

    class _SyntheticInteraction:
        def __init__(self, gid: int) -> None:
            self.guild = _SyntheticGuild(gid)

    interaction = _SyntheticInteraction(guild_id)
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, user_id)
    player_data = records.get(key)
    if not player_data:
        return None

    return next((ppe for ppe in player_data.ppes if int(ppe.id) == int(ppe_id)), None)


def _resolve_announce_channel(
    guild: discord.Guild,
    me: discord.Member | None,
    channel_id: int | None,
) -> _GuildMessageChannel | None:
    cached_channel = _get_cached_announce_channel(guild, me)
    if cached_channel is not None:
        return cached_channel

    if channel_id is not None and channel_id > 0:
        resolver = getattr(guild, "get_channel_or_thread", guild.get_channel)
        configured_channel = resolver(channel_id)
        if _is_writable_message_channel(configured_channel, me):
            _cache_announce_channel(guild.id, configured_channel.id)
            return configured_channel

        if configured_channel is not None:
            print(
                f"[REALMSHARK] Configured announce channel {channel_id} is not writable for guild {guild.id}, falling back."
            )
        else:
            print(
                f"[REALMSHARK] Configured announce channel {channel_id} not found in guild {guild.id}, falling back."
            )

    if _is_writable_message_channel(guild.system_channel, me):
        _cache_announce_channel(guild.id, guild.system_channel.id)
        return guild.system_channel

    channel = next(
        (c for c in guild.text_channels if _is_writable_message_channel(c, me)),
        None,
    )
    if channel is not None:
        _cache_announce_channel(guild.id, channel.id)
    return channel


def build_realmshark_notifier(
    bot: discord.Client,
) -> Callable[[int, str, int | None, int | None, str | None, bool, int | None, bool, str | None], Awaitable[None]]:
    async def notifier(
        guild_id: int,
        message: str,
        channel_id: int | None = None,
        user_id: int | None = None,
        image_path: str | None = None,
        allow_user_ping: bool = False,
        ppe_id: int | None = None,
        include_ppe_sheet: bool = False,
        rarity: str | None = None,
    ) -> None:
        guild = bot.get_guild(guild_id)
        if guild is None:
            print(f"[REALMSHARK] Could not announce test event: guild {guild_id} not found in bot cache.")
            return

        me = guild.me
        if me is None and bot.user is not None:
            me = guild.get_member(bot.user.id)

        channel = _resolve_announce_channel(guild, me, channel_id)

        if channel is None:
            print(f"[REALMSHARK] Could not announce test event: no writable text channel in guild {guild_id}.")
            return

        player_name = "Unknown Player"
        player_mention = ""
        if user_id is not None:
            member = guild.get_member(user_id)
            if member is not None:
                player_name = member.display_name
                player_mention = member.mention
            else:
                player_name = f"User {user_id}"
                player_mention = f"<@{user_id}>"

        final_message = message.replace("{player}", player_name).replace("{mention}", player_mention)
        final_message = _with_optional_timestamp(final_message)
        allowed_mentions = discord.AllowedMentions.none()
        if allow_user_ping and user_id is not None:
            allowed_mentions = discord.AllowedMentions(users=True)

        if include_ppe_sheet and user_id is not None and ppe_id is not None:
            target_ppe = await _get_target_ppe(guild_id, user_id, ppe_id)
            if target_ppe is not None:
                class_name = str(getattr(target_ppe.name, "value", target_ppe.name)).strip()
                if class_name:
                    final_message = final_message.replace(
                        f"PPE #{ppe_id}.",
                        f"PPE #{ppe_id} - {class_name} PPE.",
                    )

        sent_public_message = False
        overlay_image_path: str | None = None
        
        if image_path:
            # Apply rarity overlay if rarity is provided
            if rarity and rarity.lower() != "common":
                overlay_image_path = overlay_rarity_badge(image_path, rarity)
            
            image_to_send = overlay_image_path if overlay_image_path else image_path
            
            try:
                await _throttled_send(
                    channel,
                    content=f"[RealmShark] {final_message}",
                    file=discord.File(image_to_send),
                    allowed_mentions=allowed_mentions,
                )
                sent_public_message = True
            except Exception as e:
                print(
                    f"[REALMSHARK] Failed to attach image '{image_path}' for guild {guild_id}: {e}. Sending message without image."
                )
            finally:
                # Clean up overlay image if it was created
                if overlay_image_path and os.path.exists(overlay_image_path):
                    try:
                        os.remove(overlay_image_path)
                    except Exception as e:
                        print(f"[REALMSHARK] Failed to clean up overlay image: {e}")

        if not sent_public_message:
            await _throttled_send(
                channel,
                content=f"[RealmShark] {final_message}",
                allowed_mentions=allowed_mentions,
            )

    return notifier
