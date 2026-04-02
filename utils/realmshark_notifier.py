from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Awaitable, Callable

import discord

from utils.player_records import ensure_player_exists, load_player_records
from utils.image_utils import overlay_rarity_badge


def _discord_absolute_now() -> str:
    return f"<t:{int(datetime.now(timezone.utc).timestamp())}:f>"


def _with_optional_timestamp(message: str) -> str:
    is_bound_message = message.startswith("RealmShark is successfully bound to")
    is_loot_message = ("It was logged to" in message) or ("It was already logged to" in message)

    if is_bound_message or is_loot_message:
        return f"{message} | {_discord_absolute_now()}"

    return message


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

        channel = None
        if channel_id is not None and channel_id > 0:
            configured_channel = guild.get_channel(channel_id)
            if isinstance(configured_channel, discord.TextChannel):
                if me is not None and configured_channel.permissions_for(me).send_messages:
                    channel = configured_channel
                else:
                    print(
                        f"[REALMSHARK] Configured announce channel {channel_id} is not writable for guild {guild_id}, falling back."
                    )
            else:
                print(
                    f"[REALMSHARK] Configured announce channel {channel_id} not found in guild {guild_id}, falling back."
                )

        if channel is None:
            channel = guild.system_channel
            if channel is None or me is None or not channel.permissions_for(me).send_messages:
                channel = next(
                    (c for c in guild.text_channels if me is not None and c.permissions_for(me).send_messages),
                    None,
                )

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
                await channel.send(
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
            await channel.send(f"[RealmShark] {final_message}", allowed_mentions=allowed_mentions)

    return notifier
