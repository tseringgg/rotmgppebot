from __future__ import annotations

import discord

from menus.manageteams.common import resolve_single_name_query, resolve_team_name_query
from menus.manageteams.services import (
    create_empty_team,
    remove_members_from_team,
    set_team_leader,
)
from utils.team_manager import team_manager


class CreateTeamModal(discord.ui.Modal, title="Create New Team"):
    team_name = discord.ui.TextInput(label="Team Name", max_length=64, placeholder="Enter team name")

    def __init__(self, *, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        new_name = str(self.team_name.value).strip()
        if not new_name:
            await interaction.response.send_message("❌ Team name cannot be empty.", ephemeral=True)
            return

        try:
            team = await create_empty_team(interaction, new_name)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except Exception as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        role_notice = ""
        if interaction.guild:
            try:
                existing_role = discord.utils.get(interaction.guild.roles, name=team.name)
                if not existing_role:
                    await interaction.guild.create_role(name=team.name, reason=f"PPE Team role for {team.name}")
            except discord.Forbidden:
                role_notice = "\n⚠️ Team created, but I cannot create roles in this server."
            except Exception:
                role_notice = "\n⚠️ Team created, but role creation failed."

        from menus.manageteams.entry import open_manage_teams_home

        await open_manage_teams_home(interaction, owner_id=self.owner_id)
        await interaction.followup.send(f"✅ Created team **{team.name}**.{role_notice}", ephemeral=True)


class TeamNameSelect(discord.ui.Select):
    def __init__(self, *, team_names: list[str]) -> None:
        options = [discord.SelectOption(label=name, value=name) for name in team_names[:25]]
        super().__init__(
            placeholder="Select a team to manage...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if view is None or not hasattr(view, "owner_id"):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return

        from menus.manageteams.entry import open_team_manage_view

        await open_team_manage_view(interaction, owner_id=view.owner_id, team_name=self.values[0])


class TeamNameLookupModal(discord.ui.Modal, title="Find Team"):
    team_name = discord.ui.TextInput(
        label="Team Name",
        placeholder="Type full or partial team name",
        max_length=64,
    )

    def __init__(self, *, owner_id: int, team_names: list[str]) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.team_names = list(team_names)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        matched_name, error = resolve_team_name_query(self.team_names, str(self.team_name.value))
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        from menus.manageteams.entry import open_team_manage_view

        assert matched_name is not None
        await open_team_manage_view(interaction, owner_id=self.owner_id, team_name=matched_name)


class RemoveMembersModal(discord.ui.Modal, title="Remove Team Members"):
    members = discord.ui.TextInput(
        label="Members to Remove",
        placeholder="Enter names/mentions/IDs separated by commas",
        style=discord.TextStyle.paragraph,
        max_length=400,
    )

    def __init__(self, *, owner_id: int, team_name: str, member_rows: list[tuple[int, str, float, float, float, str]]) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.team_name = team_name
        self.member_rows = member_rows

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        tokens = [part.strip() for part in str(self.members.value).split(",") if part.strip()]
        if not tokens:
            await interaction.response.send_message("❌ Please provide at least one member to remove.", ephemeral=True)
            return

        candidates = [(member_id, name) for member_id, name, _b, _q, _t, _c in self.member_rows]
        member_ids: list[int] = []
        errors: list[str] = []
        for token in tokens:
            member_id, error = resolve_single_name_query(candidates, token, context_label="team member")
            if error:
                errors.append(error)
                continue
            assert member_id is not None
            if member_id not in member_ids:
                member_ids.append(member_id)

        if errors:
            await interaction.response.send_message("\n".join(errors[:5]), ephemeral=True)
            return

        try:
            actual_name, removed_count, removed_ids, new_leader_id = await remove_members_from_team(
                interaction,
                team_name=self.team_name,
                member_ids=member_ids,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except Exception as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        role_notice = ""
        if interaction.guild and removed_ids:
            team_role = discord.utils.get(interaction.guild.roles, name=actual_name)
            if team_role:
                for member_id in removed_ids:
                    member = interaction.guild.get_member(member_id)
                    if member and team_role in member.roles:
                        try:
                            await member.remove_roles(team_role)
                        except discord.Forbidden:
                            role_notice = "\n⚠️ Member removal succeeded, but role cleanup failed for one or more users."
                            break

        from menus.manageteams.entry import open_team_manage_view

        await open_team_manage_view(interaction, owner_id=self.owner_id, team_name=actual_name)
        leader_text = f" New leader: <@{new_leader_id}>." if new_leader_id else " Leader is now unassigned."
        await interaction.followup.send(
            f"✅ Removed **{removed_count}** member(s) from **{actual_name}**.{leader_text}{role_notice}",
            ephemeral=True,
        )


class SetLeaderModal(discord.ui.Modal, title="Set Team Leader"):
    leader = discord.ui.TextInput(
        label="New Team Leader",
        placeholder="Enter member name, mention, or ID",
        max_length=100,
    )

    def __init__(self, *, owner_id: int, team_name: str, member_rows: list[tuple[int, str, float, float, float, str]]) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.team_name = team_name
        self.member_rows = member_rows

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        candidates = [(member_id, name) for member_id, name, _b, _q, _t, _c in self.member_rows]
        leader_id, error = resolve_single_name_query(candidates, str(self.leader.value), context_label="team member")
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        assert leader_id is not None
        try:
            actual_name, _updated_leader_id = await set_team_leader(
                interaction,
                team_name=self.team_name,
                leader_id=leader_id,
            )
            if interaction.guild:
                leader_member = interaction.guild.get_member(leader_id)
                team_role = discord.utils.get(interaction.guild.roles, name=actual_name)
                if leader_member and team_role and team_role not in leader_member.roles:
                    await leader_member.add_roles(team_role)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except discord.Forbidden:
            await interaction.response.send_message(
                "⚠️ Leader updated, but role assignment failed.",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        from menus.manageteams.entry import open_team_manage_view

        await open_team_manage_view(interaction, owner_id=self.owner_id, team_name=self.team_name)
        await interaction.followup.send(f"✅ Updated leader for **{self.team_name}**.", ephemeral=True)


class AddMemberModal(discord.ui.Modal, title="Add Team Member"):
    member = discord.ui.TextInput(
        label="Member to Add",
        placeholder="Enter member name, mention, or ID",
        max_length=100,
    )

    def __init__(self, *, owner_id: int, team_name: str, eligible_members: list[discord.Member]) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.team_name = team_name
        self.eligible_members = list(eligible_members)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        candidates = [(member.id, member.display_name) for member in self.eligible_members]
        member_id, error = resolve_single_name_query(candidates, str(self.member.value), context_label="eligible player")
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        assert member_id is not None
        try:
            team = await team_manager.add_player_to_team(interaction, member_id, self.team_name)
            if interaction.guild:
                member = interaction.guild.get_member(member_id)
                role = discord.utils.get(interaction.guild.roles, name=team.name)
                if member and role and role not in member.roles:
                    await member.add_roles(role)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except discord.Forbidden:
            await interaction.response.send_message(
                "⚠️ Player added, but I could not update role assignments.",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        from menus.manageteams.entry import open_team_manage_view

        await open_team_manage_view(interaction, owner_id=self.owner_id, team_name=self.team_name)
        await interaction.followup.send(f"✅ Added <@{member_id}> to **{self.team_name}**.", ephemeral=True)


class RenameTeamModal(discord.ui.Modal, title="Rename Team"):
    new_name = discord.ui.TextInput(label="New Team Name", max_length=64, placeholder="Enter new team name")

    def __init__(self, *, owner_id: int, team_name: str) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.team_name = team_name

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        updated_name = str(self.new_name.value).strip()
        if not updated_name:
            await interaction.response.send_message("❌ Team name cannot be empty.", ephemeral=True)
            return

        try:
            await team_manager.update_team_name(interaction, self.team_name, updated_name)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except Exception as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        role_notice = ""
        if interaction.guild:
            try:
                old_role = discord.utils.get(interaction.guild.roles, name=self.team_name)
                if old_role:
                    await old_role.edit(name=updated_name, reason=f"PPE Team rename from {self.team_name} to {updated_name}")
            except discord.Forbidden:
                role_notice = "\n⚠️ Team renamed, but role rename failed due to permissions."
            except discord.HTTPException:
                role_notice = "\n⚠️ Team renamed, but role rename failed."

        from menus.manageteams.entry import open_team_manage_view

        await open_team_manage_view(interaction, owner_id=self.owner_id, team_name=updated_name)
        await interaction.followup.send(f"✅ Renamed **{self.team_name}** to **{updated_name}**.{role_notice}", ephemeral=True)
