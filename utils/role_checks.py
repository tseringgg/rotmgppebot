"""Utilities for role checks."""

import discord
from discord import Member, User, app_commands


def ppe_player_role(guild: discord.Guild | None) -> discord.Role | None:
    """Return the configured PPE Player role when present."""
    if guild is None:
        return None
    return discord.utils.get(guild.roles, name="PPE Player")


def has_ppe_player_role(member: Member | User | None, guild: discord.Guild | None) -> bool:
    """Check whether a guild member currently has the PPE Player role."""
    if not isinstance(member, Member):
        return False
    role = ppe_player_role(guild)
    return role is not None and role in member.roles

def require_ppe_roles(admin_required: bool = False, player_required: bool = False):
    async def predicate(inter: discord.Interaction):

        # Safety: interaction may already have responded (autocomplete, modal, etc.)
        async def safe_respond(message: str):
            try:
                if not inter.response.is_done():
                    await inter.response.send_message(message, ephemeral=True)
                else:
                    # Fallback for autocomplete or after-response cases
                    await inter.followup.send(message, ephemeral=True)
            except Exception:
                pass  # Never allow a response failure to break the check
        if not isinstance(inter.user, Member):
            await safe_respond("❌ This command can only be used by a server member.")
            return False
        guild = inter.guild
        member = inter.user

        if guild is None:
            await safe_respond("❌ This command can only be used in a server.")
            return False

        admin_role = discord.utils.get(guild.roles, name="PPE Admin")
        player_role = discord.utils.get(guild.roles, name="PPE Player")

        if not admin_role or not player_role:
            await safe_respond(
                "⚠️ Required roles are missing!\n"
                "Please ensure **PPE Admin** and **PPE Player** exist."
            )
            return False
        member.roles

        if admin_required and admin_role not in member.roles:
            await safe_respond("🚫 You need the **PPE Admin** role to use this command.")
            return False

        if player_required and player_role not in member.roles:
            await safe_respond("🚫 You need the **PPE Player** role to use this command.")
            return False

        return True

    return app_commands.check(predicate)


def require_server_owner():
    async def predicate(inter: discord.Interaction):
        async def safe_respond(message: str):
            try:
                if not inter.response.is_done():
                    await inter.response.send_message(message, ephemeral=True)
                else:
                    await inter.followup.send(message, ephemeral=True)
            except Exception:
                pass

        guild = inter.guild
        if guild is None:
            await safe_respond("❌ This command can only be used in a server.")
            return False

        if inter.user.id != guild.owner_id:
            await safe_respond("🚫 Only the server owner can use this command.")
            return False

        return True

    return app_commands.check(predicate)
