"""Class selection submenu for character leaderboard."""

from __future__ import annotations

import discord

from dataclass import ROTMGClass
from menus.leaderboard import characterleaderboard
from menus.menu_utils import OwnerBoundView


def character_class_embed(selected_class: str | None) -> discord.Embed:
    base_instructions = (
        "Step 1: Select a class from the dropdown.\n"
        "Step 2: Click **View Selected Class** to open that leaderboard."
    )
    if selected_class:
        description = f"{base_instructions}\n\nCurrent class: **{selected_class}**"
    else:
        description = f"{base_instructions}\n\nCurrent class: **None selected yet**"

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
        from menus.leaderboard.views import LeaderboardHomeView

        home_view = LeaderboardHomeView(owner_id=self.owner_id, contest_settings=self.contest_settings)
        await interaction.response.edit_message(embed=home_view.current_embed(), view=home_view)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/leaderboard` menu.", embed=None, view=None)


__all__ = ["CharacterLeaderboardClassView", "character_class_embed"]
