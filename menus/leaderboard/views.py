from __future__ import annotations

import discord

from dataclass import ROTMGClass
from menus.menu_utils import OwnerBoundView
from utils.contest_leaderboards import contest_leaderboard_label

from . import (
    characterleaderboard,
    contestleaderboard,
    ppeleaderboard,
    questleaderboard,
    seasonleaderboard,
    teamleaderboard,
)


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
    return embed


def character_class_embed(selected_class: str | None) -> discord.Embed:
    if selected_class:
        description = (
            "Choose another class from the dropdown or press View Selected Class.\n"
            f"Current class: **{selected_class}**"
        )
    else:
        description = "Select a class from the dropdown, then press View Selected Class."

    return discord.Embed(
        title="Character Leaderboard",
        description=description,
        color=discord.Color.teal(),
    )


class CharacterClassSelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [discord.SelectOption(label=c.value, value=c.value) for c in ROTMGClass]
        super().__init__(placeholder="Pick a class", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, CharacterLeaderboardClassView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return

        view.selected_class = self.values[0]
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class CharacterLeaderboardClassView(OwnerBoundView):
    def __init__(self, owner_id: int, *, contest_settings: dict | None = None) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.selected_class: str | None = None
        self.contest_settings = contest_settings if isinstance(contest_settings, dict) else {}
        self.add_item(CharacterClassSelect())

    def current_embed(self) -> discord.Embed:
        return character_class_embed(self.selected_class)

    @discord.ui.button(label="View Selected Class", style=discord.ButtonStyle.primary, row=1)
    async def view_selected(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not self.selected_class:
            await interaction.response.send_message("Pick a class first.", ephemeral=True)
            return
        await characterleaderboard.command(interaction, self.selected_class)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        home_view = LeaderboardHomeView(owner_id=self.owner_id, contest_settings=self.contest_settings)
        await interaction.response.edit_message(embed=home_view.current_embed(), view=home_view)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/leaderboard` menu.", embed=None, view=None)


class LeaderboardHomeView(OwnerBoundView):
    def __init__(self, owner_id: int, *, contest_settings: dict | None = None) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.contest_settings = contest_settings if isinstance(contest_settings, dict) else {}

    def current_embed(self) -> discord.Embed:
        return leaderboard_home_embed(self.contest_settings)

    @discord.ui.button(label="PPE Leaderboard", style=discord.ButtonStyle.primary, row=0)
    async def ppe(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await ppeleaderboard.command(interaction)

    @discord.ui.button(label="Quest Leaderboard", style=discord.ButtonStyle.primary, row=0)
    async def quest(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await questleaderboard.command(interaction)

    @discord.ui.button(label="Character Leaderboard", style=discord.ButtonStyle.primary, row=1)
    async def character(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        class_view = CharacterLeaderboardClassView(owner_id=interaction.user.id, contest_settings=self.contest_settings)
        await interaction.response.edit_message(embed=class_view.current_embed(), view=class_view)

    @discord.ui.button(label="Season Loot Leaderboard", style=discord.ButtonStyle.primary, row=1)
    async def season(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await seasonleaderboard.command(interaction)

    @discord.ui.button(label="Team Leaderboard", style=discord.ButtonStyle.primary, row=2)
    async def team(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await teamleaderboard.command(interaction)

    @discord.ui.button(label="Contest Leaderboard", style=discord.ButtonStyle.primary, row=2)
    async def contest(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await contestleaderboard.run_default_contest_leaderboard(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=3)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/leaderboard` menu.", embed=None, view=None)
