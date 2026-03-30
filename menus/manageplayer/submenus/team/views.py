"""Team assignment/removal submenus used by the /manageplayer home panel."""

from __future__ import annotations

import discord

from dataclass import TeamData
from menus.manageplayer.common import (
    send_followup_text,
)
from menus.manageplayer.entry import open_manageplayer_home
from menus.manageplayer.services import assign_target_to_team, load_target_player_data, remove_target_from_team
from menus.manageplayer.targets import ManagedPlayerTarget
from menus.menu_utils import OwnerBoundView


class _TeamChoiceSelect(discord.ui.Select):
    """Dropdown that lets an admin pick one existing team for assignment."""

    def __init__(self, teams: dict[str, TeamData], ordered_team_names: list[str]):
        if ordered_team_names:
            ordered_entries = [(name, teams[name]) for name in ordered_team_names if name in teams]
        else:
            ordered_entries = sorted(teams.items(), key=lambda entry: (len(entry[1].members), entry[0].lower()))

        options = [
            discord.SelectOption(
                label=team_name,
                value=team_name,
                description=f"{len(team_data.members)} members",
            )
            for team_name, team_data in ordered_entries[:25]
        ]

        super().__init__(
            placeholder="Choose a team...",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManagePlayerAddToTeamView):
            await interaction.response.send_message("Invalid team selection state.", ephemeral=True)
            return

        selected_team_name = self.values[0]

        try:
            result = await assign_target_to_team(interaction, view.target, selected_team_name)
            await open_manageplayer_home(
                interaction,
                owner_id=interaction.user.id,
                target=view.target,
                max_ppes=view.max_ppes,
            )
            await send_followup_text(interaction, result, ephemeral=False)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=False)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I do not have permission to manage team roles.",
                ephemeral=False,
            )
        except Exception as exc:
            await interaction.response.send_message(str(exc), ephemeral=False)


class ManagePlayerAddToTeamView(OwnerBoundView):
    """Menu that allows admins to add a target player to an existing team."""

    def __init__(
        self,
        *,
        owner_id: int,
        target: ManagedPlayerTarget,
        max_ppes: int,
        teams: dict[str, TeamData],
        ordered_team_names: list[str] | None = None,
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.target = target
        self.max_ppes = max_ppes
        self.teams = teams
        self.ordered_team_names = ordered_team_names or []

        if self.teams:
            self.add_item(_TeamChoiceSelect(self.teams, self.ordered_team_names))

    def current_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"Add to Team - {self.target.display_name}",
            description="Choose an existing team from the dropdown below.",
            color=discord.Color.green(),
        )

        if not self.teams:
            embed.add_field(
                name="No Teams Found",
                value="Create a team first with `/manageteams`.",
                inline=False,
            )
            return embed

        lines = []
        if self.ordered_team_names:
            ordered_entries = [(name, self.teams[name]) for name in self.ordered_team_names if name in self.teams]
        else:
            ordered_entries = sorted(self.teams.items(), key=lambda entry: (len(entry[1].members), entry[0].lower()))

        for team_name, team_data in ordered_entries:
            lines.append(f"• {team_name}: {len(team_data.members)} members")

        text = "\n".join(lines)
        if len(text) > 1024:
            text = text[:1000].rstrip() + "\n..."

        embed.add_field(
            name="Team Sizes",
            value=(
                "Use this list to balance teams by picking smaller groups first.\n"
                f"{text}"
            ),
            inline=False,
        )
        return embed

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await open_manageplayer_home(
            interaction,
            owner_id=interaction.user.id,
            target=self.target,
            max_ppes=self.max_ppes,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=2)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed /manageplayer menu.", embed=None, view=None)


class ManagePlayerTeamOverviewView(ManagePlayerAddToTeamView):
    """Backward-compatible alias for older imports."""


class ManagePlayerRemoveFromTeamConfirmView(OwnerBoundView):
    """Confirmation menu before removing a target player from their current team."""

    def __init__(
        self,
        *,
        owner_id: int,
        target: ManagedPlayerTarget,
        max_ppes: int,
        team_name: str,
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=120, owner_error="This menu belongs to another user.")
        self.target = target
        self.max_ppes = max_ppes
        self.team_name = team_name

    def current_embed(self) -> discord.Embed:
        return discord.Embed(
            title="Remove from Team",
            description=(
                f"Are you sure you want to remove **{self.target.display_name}** "
                f"from team **{self.team_name}**?"
            ),
            color=discord.Color.orange(),
        )

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, row=0)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            result = await remove_target_from_team(interaction, self.target)
            await open_manageplayer_home(
                interaction,
                owner_id=interaction.user.id,
                target=self.target,
                max_ppes=self.max_ppes,
            )
            await send_followup_text(interaction, result, ephemeral=False)
        except Exception as exc:
            await interaction.response.send_message(str(exc), ephemeral=False)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=0)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        player_data = await load_target_player_data(interaction, self.target.user_id)
        self.team_name = player_data.team_name or "N/A"
        await open_manageplayer_home(
            interaction,
            owner_id=interaction.user.id,
            target=self.target,
            max_ppes=self.max_ppes,
        )
