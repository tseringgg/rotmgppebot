from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import discord

from utils.player_records import DATA_DIR, get_lock


@dataclass(slots=True)
class ForceResetSummary:
    deleted_files: int
    deleted_temp_files: int


class ForceResetConfirmView(discord.ui.View):
    def __init__(self, *, owner_id: int) -> None:
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.confirmed: bool | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "This confirmation belongs to another user.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Confirm Force Reset", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.confirmed = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.confirmed = False
        await interaction.response.defer()
        self.stop()


async def _force_reset_guild_files(guild_id: int) -> ForceResetSummary:
    prefix = f"{guild_id}_"
    deleted_files = 0
    deleted_temp_files = 0

    async with get_lock(guild_id):
        try:
            entries = list(os.scandir(DATA_DIR))
        except FileNotFoundError:
            return ForceResetSummary(deleted_files=0, deleted_temp_files=0)

        for entry in entries:
            if not entry.is_file():
                continue

            name = entry.name
            if not name.startswith(prefix):
                continue

            path = entry.path
            try:
                await asyncio.to_thread(os.remove, path)
                if name.endswith(".tmp"):
                    deleted_temp_files += 1
                else:
                    deleted_files += 1
            except FileNotFoundError:
                continue

    return ForceResetSummary(deleted_files=deleted_files, deleted_temp_files=deleted_temp_files)


async def command(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    if interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("Only the server owner can use this command.", ephemeral=True)
        return

    view = ForceResetConfirmView(owner_id=interaction.user.id)
    await interaction.response.send_message(
        (
            "WARNING: This will delete all stored bot data files for this guild.\n"
            "This includes config, teams, player records, sniffer pending files, and guild channel settings.\n"
            "Are you sure you want to continue?"
        ),
        view=view,
        ephemeral=True,
    )

    await view.wait()

    if view.confirmed is not True:
        status = "Force reset cancelled." if view.confirmed is False else "Force reset timed out."
        await interaction.edit_original_response(content=status, view=None)
        return

    summary = await _force_reset_guild_files(interaction.guild.id)
    await interaction.edit_original_response(
        content=(
            "Force reset complete.\n"
            f"Deleted files: `{summary.deleted_files}`\n"
            f"Deleted temp files: `{summary.deleted_temp_files}`\n"
            "Run `/setuproles` to begin bot setup again."
        ),
        view=None,
    )
