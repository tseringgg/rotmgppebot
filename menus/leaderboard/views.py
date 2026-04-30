from __future__ import annotations

import time
import discord

from menus.menu_utils import OwnerBoundView
from menus.leaderboard.submenus.character.views import CharacterLeaderboardClassView
from utils.contest_leaderboards import contest_leaderboard_label
from utils.bot_cost_tracking import capture_runtime_snapshot, log_background_cost_event

from . import (
    conteststats,
    contestleaderboard,
    ppeleaderboard,
    questleaderboard,
    seasonleaderboard,
    teamleaderboard,
)


async def _log_leaderboard_cost(
    interaction: discord.Interaction,
    operation_name: str,
    started_monotonic: float,
    started_unix: float,
    snapshot_before: dict,
) -> None:
    """Helper to log leaderboard query costs."""
    try:
        if interaction.guild_id:
            await log_background_cost_event(
                int(interaction.guild_id),
                operation_name=operation_name,
                status="ok",
                started_monotonic=started_monotonic,
                started_unix=started_unix,
                snapshot_before=snapshot_before,
                source="leaderboard_query",
            )
    except Exception:
        pass  # Non-blocking: don't let cost logging failures affect user experience


def leaderboard_home_embed(contest_settings: dict | None = None) -> discord.Embed:
    settings = contest_settings if isinstance(contest_settings, dict) else {}
    default_contest_type = settings.get("default_contest_leaderboard")
    default_contest_label = contest_leaderboard_label(default_contest_type, fallback="Not Set")

    embed = discord.Embed(
        title="Leaderboards",
        description="Choose which leaderboard to view.",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="PPE Leaderboard", value="Best PPE per player.", inline=False)
    embed.add_field(name="Quest Leaderboard", value="Weighted quest points.", inline=False)
    embed.add_field(name="Character Leaderboard", value="Highest scoring characters by class.", inline=False)
    embed.add_field(name="Season Loot Leaderboard", value="Unique seasonal item counts.", inline=False)
    embed.add_field(name="Team Leaderboard", value="Combined team standings.", inline=False)
    embed.add_field(name="Contest Leaderboard", value=f"Configured default: **{default_contest_label}**", inline=False)
    embed.add_field(name="Contest Stats", value="Contest-wide wrapped stats across all players.", inline=False)
    return embed


class LeaderboardHomeView(OwnerBoundView):
    def __init__(self, owner_id: int, *, contest_settings: dict | None = None) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.contest_settings = contest_settings if isinstance(contest_settings, dict) else {}

    def current_embed(self) -> discord.Embed:
        return leaderboard_home_embed(self.contest_settings)

    @discord.ui.button(label="Contest Leaderboard", style=discord.ButtonStyle.primary, row=0)
    async def contest(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        started_monotonic = time.monotonic()
        started_unix = time.time()
        snapshot_before = capture_runtime_snapshot()
        await contestleaderboard.run_default_contest_leaderboard(interaction)
        await _log_leaderboard_cost(interaction, "contest_leaderboard", started_monotonic, started_unix, snapshot_before)

    @discord.ui.button(label="PPE Leaderboard", style=discord.ButtonStyle.primary, row=0)
    async def ppe(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        started_monotonic = time.monotonic()
        started_unix = time.time()
        snapshot_before = capture_runtime_snapshot()
        await ppeleaderboard.command(interaction)
        await _log_leaderboard_cost(interaction, "ppe_leaderboard", started_monotonic, started_unix, snapshot_before)

    @discord.ui.button(label="Quest Leaderboard", style=discord.ButtonStyle.primary, row=0)
    async def quest(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        started_monotonic = time.monotonic()
        started_unix = time.time()
        snapshot_before = capture_runtime_snapshot()
        await questleaderboard.command(interaction)
        await _log_leaderboard_cost(interaction, "quest_leaderboard", started_monotonic, started_unix, snapshot_before)

    @discord.ui.button(label="Character Leaderboard", style=discord.ButtonStyle.primary, row=1)
    async def character(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        started_monotonic = time.monotonic()
        started_unix = time.time()
        snapshot_before = capture_runtime_snapshot()
        class_view = CharacterLeaderboardClassView(owner_id=interaction.user.id, contest_settings=self.contest_settings)
        await interaction.response.edit_message(embed=class_view.current_embed(), view=class_view)
        await _log_leaderboard_cost(interaction, "character_leaderboard_selector", started_monotonic, started_unix, snapshot_before)

    @discord.ui.button(label="Season Loot Leaderboard", style=discord.ButtonStyle.primary, row=1)
    async def season(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        started_monotonic = time.monotonic()
        started_unix = time.time()
        snapshot_before = capture_runtime_snapshot()
        await seasonleaderboard.command(interaction)
        await _log_leaderboard_cost(interaction, "season_loot_leaderboard", started_monotonic, started_unix, snapshot_before)

    @discord.ui.button(label="Team Leaderboard", style=discord.ButtonStyle.primary, row=2)
    async def team(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        started_monotonic = time.monotonic()
        started_unix = time.time()
        snapshot_before = capture_runtime_snapshot()
        await teamleaderboard.command(interaction)
        await _log_leaderboard_cost(interaction, "team_leaderboard", started_monotonic, started_unix, snapshot_before)

    @discord.ui.button(label="Contest Stats", style=discord.ButtonStyle.success, row=2)
    async def contest_stats(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        started_monotonic = time.monotonic()
        started_unix = time.time()
        snapshot_before = capture_runtime_snapshot()
        await conteststats.command(interaction)
        await _log_leaderboard_cost(interaction, "contest_stats", started_monotonic, started_unix, snapshot_before)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=3)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/leaderboard` menu.", embed=None, view=None)
