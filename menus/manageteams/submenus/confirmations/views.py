"""Confirmation views for /manageteams admin menu."""

from __future__ import annotations

import discord

from menus.menu_utils import OwnerBoundView
from menus.manageteams.services import delete_team


class TeamDeleteConfirmView(OwnerBoundView):
    """Confirmation dialog for team deletion."""

    def __init__(self, *, owner_id: int, team_name: str) -> None:
        super().__init__(owner_id=owner_id, timeout=180, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.team_name = team_name

    def current_embed(self) -> discord.Embed:
        return discord.Embed(
            title="Delete Team",
            description=(
                f"Are you sure you want to delete **{self.team_name}**?\n"
                "All members will be removed from the team."
            ),
            color=discord.Color.red(),
        )

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger, row=0)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            actual_name, removed_count, removed_ids = await delete_team(interaction, self.team_name)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except Exception as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        role_notice = ""
        if interaction.guild:
            try:
                team_role = discord.utils.get(interaction.guild.roles, name=actual_name)
                if team_role:
                    await team_role.delete(reason=f"PPE Team {actual_name} deleted")

                for member_id in removed_ids:
                    member = interaction.guild.get_member(member_id)
                    if member and team_role and team_role in member.roles:
                        await member.remove_roles(team_role)
            except discord.Forbidden:
                role_notice = "\n⚠️ Team deleted, but I could not clean up one or more role assignments."
            except Exception:
                role_notice = "\n⚠️ Team deleted, but role cleanup was partial."

        from menus.manageteams.entry import open_manage_teams_home

        await open_manage_teams_home(interaction, owner_id=self.owner_id)
        await interaction.followup.send(
            f"✅ Deleted **{actual_name}** and removed **{removed_count}** member assignments.{role_notice}",
            ephemeral=True,
        )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=0)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageteams.entry import open_team_manage_view

        await open_team_manage_view(interaction, owner_id=self.owner_id, team_name=self.team_name)
