"""Target resolution and role helpers for /manageplayer workflows."""

from __future__ import annotations

from dataclasses import dataclass

import discord

from utils.player_records import ensure_player_exists, load_player_records, save_player_records


@dataclass
class ManagedPlayerTarget:
    user_id: int
    display_name: str
    mention_text: str
    member: discord.Member | None
    has_player_role: bool


def player_role(guild: discord.Guild) -> discord.Role | None:
    return discord.utils.get(guild.roles, name="PPE Player")


def admin_role(guild: discord.Guild) -> discord.Role | None:
    return discord.utils.get(guild.roles, name="PPE Admin")


def safe_display_name(member: discord.Member | None, user_id: int) -> str:
    if member is not None:
        return member.display_name
    return f"User {user_id}"


async def resolve_target(
    interaction: discord.Interaction,
    *,
    member: discord.Member | None,
    user_id: str | None,
) -> tuple[ManagedPlayerTarget | None, str | None]:
    if not interaction.guild:
        return None, "❌ This command can only be used in a server."

    if member is None and not user_id:
        return None, "❌ Provide either a server member or a Discord user ID."

    if member is not None and user_id:
        return None, "❌ Provide only one target: member OR user_id."

    target_member = member
    if member is not None:
        target_id = int(member.id)
    else:
        assert user_id is not None
        if not user_id.isdigit():
            return None, "❌ user_id must be a numeric Discord ID."

        target_id = int(user_id)
        target_member = interaction.guild.get_member(target_id)
        if target_member is None:
            try:
                target_member = await interaction.guild.fetch_member(target_id)
            except Exception:
                target_member = None

    records = await load_player_records(interaction)
    has_record = int(target_id) in records

    # Allow direct management by ID only when data already exists.
    if target_member is None and not has_record:
        return None, f"❌ No PPE data found for Discord user ID {target_id}."

    if target_member is not None:
        key = ensure_player_exists(records, int(target_id))
        records[key].is_member = records[key].is_member and True
        await save_player_records(interaction, records)

    role = player_role(interaction.guild)
    has_player_role = bool(target_member and role and role in target_member.roles)

    display_name = safe_display_name(target_member, target_id)
    mention_text = target_member.mention if target_member is not None else f"User {target_id}"
    return (
        ManagedPlayerTarget(
            user_id=int(target_id),
            display_name=display_name,
            mention_text=mention_text,
            member=target_member,
            has_player_role=has_player_role,
        ),
        None,
    )


__all__ = ["ManagedPlayerTarget", "admin_role", "player_role", "resolve_target"]
