"""Utilities for team manager."""

import asyncio
from typing import Dict, Optional

import discord
from dataclass import TeamData
from utils.guild_config import load_guild_config, save_guild_config
from utils.points_service import compute_effective_ppe_points
from utils.player_records import ensure_player_exists, load_player_records, load_teams, save_player_records, save_teams
from utils.quest_modes import normalize_team_key
from utils.team_contest_scoring import compute_team_member_points, compute_team_shared_quest_points, get_best_ppe, load_team_contest_scoring

class TeamManager:
    """Centralized manager for team data operations."""
    
    def __init__(self):
        self._locks: Dict[int, asyncio.Lock] = {}
    
    def _get_lock(self, guild_id: int) -> asyncio.Lock:
        """Get or create a lock for a specific guild."""
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()
        return self._locks[guild_id]

    def clear_guild_state(self, guild_id: int) -> None:
        """Release lock state for a guild when the bot leaves it."""
        self._locks.pop(int(guild_id), None)

    def get_lock_count(self) -> int:
        return len(self._locks)

    async def _rename_team_quest_state(self, interaction: discord.Interaction, *, old_name: str, new_name: str) -> None:
        config = await load_guild_config(interaction)
        quest_settings = config.get("quest_settings", {}) if isinstance(config.get("quest_settings", {}), dict) else {}
        state_map = quest_settings.get("team_quests_state")
        if not isinstance(state_map, dict):
            return

        old_key = normalize_team_key(old_name)
        new_key = normalize_team_key(new_name)
        if not old_key or not new_key or old_key == new_key:
            return
        if old_key not in state_map:
            return

        state_map[new_key] = state_map.pop(old_key)
        quest_settings["team_quests_state"] = state_map
        config["quest_settings"] = quest_settings
        await save_guild_config(interaction, config)

    async def _remove_team_quest_state(self, interaction: discord.Interaction, *, team_name: str) -> None:
        config = await load_guild_config(interaction)
        quest_settings = config.get("quest_settings", {}) if isinstance(config.get("quest_settings", {}), dict) else {}
        state_map = quest_settings.get("team_quests_state")
        if not isinstance(state_map, dict):
            return

        team_key = normalize_team_key(team_name)
        if not team_key or team_key not in state_map:
            return

        state_map.pop(team_key, None)
        quest_settings["team_quests_state"] = state_map
        config["quest_settings"] = quest_settings
        await save_guild_config(interaction, config)
    
    async def execute_transaction(self, interaction: discord.Interaction, operation):
        """Execute a data operation atomically with proper locking."""
        if not interaction.guild:
            raise ValueError("❌ This command can only be used in a server.")
        
        guild_id = interaction.guild.id
        async with self._get_lock(guild_id):
            # Load data
            teams = await load_teams(interaction)
            records = await load_player_records(interaction)
            
            # Execute the operation
            result = await operation(teams, records, interaction)
            
            # Save data
            await save_teams(interaction, teams)
            await save_player_records(interaction, records)
            
            return result
    
    async def add_team(self, interaction: discord.Interaction, team_name: str, leader_id: int) -> TeamData:
        """Create a new team."""
        
        async def operation(teams, records, interaction):
            # Check if team already exists (case-insensitive)
            for existing_team_name in teams:
                if existing_team_name.lower() == team_name.lower():
                    raise ValueError(f"❌ Team `{existing_team_name}` already exists.")
            
            # Ensure team leader is a PPE player
            leader_key = ensure_player_exists(records, leader_id)
            if leader_key not in records or not records[leader_key].is_member:
                raise ValueError("❌ Team leader must be a PPE player.")
            
            # Create new team
            new_team = TeamData(name=team_name, leader_id=leader_id, members=[leader_id])
            teams[team_name] = new_team
            
            # Add team to leader
            records[leader_key].team_name = team_name
            
            return new_team
        
        return await self.execute_transaction(interaction, operation)
    
    async def add_player_to_team(self, interaction: discord.Interaction, player_id: int, team_name: str) -> TeamData:
        """Add a player to a team."""
        
        async def operation(teams, records, interaction):
            # Find team (case-insensitive)
            actual_team_name = None
            for team_key in teams:
                if team_key.lower() == team_name.lower():
                    actual_team_name = team_key
                    break
            
            if not actual_team_name:
                raise ValueError(f"❌ Team `{team_name}` not found.")
            
            team = teams[actual_team_name]
            
            # Ensure player exists and is a PPE player
            player_key = ensure_player_exists(records, player_id)
            if player_key not in records or not records[player_key].is_member:
                raise ValueError("❌ Player must be a PPE player to join a team.")
            
            player_data = records[player_key]
            
            # Check if player is already on a team
            if player_data.team_name is not None:
                raise ValueError(f"❌ Player is already on team `{player_data.team_name}`. Remove them from that team first.")
            
            # Add player to team
            if player_id not in team.members:
                team.members.append(player_id)
            player_data.team_name = actual_team_name
            
            return team
        
        return await self.execute_transaction(interaction, operation)
    
    async def remove_player_from_teams(self, interaction: discord.Interaction, player_id: int):
        """Remove a player from all teams they're on."""
        
        async def operation(teams, records, interaction):
            # Ensure player exists
            player_key = ensure_player_exists(records, player_id)
            player_data = records[player_key]
            
            if player_data.team_name:
                team_name = player_data.team_name
                if team_name in teams:
                    team = teams[team_name]
                    if player_id in team.members:
                        team.members.remove(player_id)
                    if not team.members:
                        teams.pop(team_name, None)
                        await self._remove_team_quest_state(interaction, team_name=team_name)
                    
                    # If player was the last member (besides might not be applicable), can optionally delete team
                    # But for now, we'll leave empty teams as is
                
                player_data.team_name = None
                return team_name
            return None
        
        return await self.execute_transaction(interaction, operation)
    
    async def force_remove_player_from_teams(self, interaction: discord.Interaction, player_id: int):
        """Force remove a player from all teams they're on, even if they're not a PPE player.
        
        This is useful for removing players who were already deleted from the PPE system
        but may still be in team member lists.
        """
        
        async def operation(teams, records, interaction):
            found_team = None
            
            # Search through all teams and remove the player from any team they're in
            for team_name, team in teams.items():
                if player_id in team.members:
                    team.members.remove(player_id)
                    found_team = team_name

            if found_team and found_team in teams and not teams[found_team].members:
                teams.pop(found_team, None)
                await self._remove_team_quest_state(interaction, team_name=found_team)
            
            # Also try to update their player record if it already exists.
            if player_id in records:
                records[player_id].team_name = None
            
            return found_team
        
        return await self.execute_transaction(interaction, operation)
    
    async def update_team_name(self, interaction: discord.Interaction, old_name: str, new_name: str) -> TeamData:
        """Update a team's name."""
        
        async def operation(teams, records, interaction):
            # Find old team (case-insensitive)
            actual_old_name = None
            for team_key in teams:
                if team_key.lower() == old_name.lower():
                    actual_old_name = team_key
                    break
            
            if not actual_old_name:
                raise ValueError(f"❌ Team `{old_name}` not found.")
            
            # Check if new name already exists (case-insensitive)
            for team_key in teams:
                if team_key.lower() == new_name.lower() and team_key != actual_old_name:
                    raise ValueError(f"❌ Team `{team_key}` already exists.")
            
            # Update team name in teams dict
            team = teams.pop(actual_old_name)
            team.name = new_name
            teams[new_name] = team
            
            # Update team_name in all members
            for member_id in team.members:
                if member_id in records:
                    records[member_id].team_name = new_name

            await self._rename_team_quest_state(interaction, old_name=actual_old_name, new_name=new_name)
            
            return team
        
        return await self.execute_transaction(interaction, operation)
    
    async def get_team_leaderboard_data(self, interaction: discord.Interaction) -> list:
        """Get team leaderboard data sorted by total points.
        
        Returns a list of tuples:
        (team_name, leader_id, ppe_points, quest_points, total_points, member_count)
        """
        
        async def operation(teams, records, interaction):
            leaderboard_data = []
            scoring = await load_team_contest_scoring(interaction)
            guild_config = await load_guild_config(interaction)
            quest_settings = guild_config.get("quest_settings", {}) if isinstance(guild_config.get("quest_settings", {}), dict) else {}
            team_mode_effective = bool(quest_settings.get("enable_team_quests", False)) and not bool(
                quest_settings.get("use_global_quests", False)
            )
            
            for team_name, team in teams.items():
                ppe_points = 0.0
                quest_points = 0.0

                # Sum each member's PPE contribution plus optional quest contribution.
                for member_id in team.members:
                    if member_id in records:
                        player_data = records[member_id]
                        member_ppe_points, member_quest_points, _member_total = compute_team_member_points(
                            player_data,
                            scoring=scoring,
                            aggregate=scoring.team_aggregate_points,
                            guild_config=guild_config,
                        )
                        ppe_points += member_ppe_points
                        if not team_mode_effective:
                            quest_points += member_quest_points

                if scoring.include_quest_points and team_mode_effective:
                    quest_points = compute_team_shared_quest_points(
                        team_name=team_name,
                        quest_settings=quest_settings,
                        scoring=scoring,
                    )

                total_points = ppe_points + quest_points
                
                leaderboard_data.append((team_name, team.leader_id, ppe_points, quest_points, total_points, len(team.members)))
            
            # Sort by combined points descending, then PPE points as tie-breaker.
            leaderboard_data.sort(key=lambda x: (x[4], x[2]), reverse=True)
            
            return leaderboard_data
        
        return await self.execute_transaction(interaction, operation)
    
    async def get_team_members_info(self, interaction: discord.Interaction, team_name: str) -> Optional[tuple]:
        """Get detailed information about a team's members.
        
        Returns a tuple: (team_name, leader_id, [(member_id, member_name, top_ppe_points, ppe_class), ...])
        Members without PPE characters are included with 0 points and None class.
        """
        
        async def operation(teams, records, interaction):
            # Find team (case-insensitive)
            actual_team_name = None
            for team_key in teams:
                if team_key.lower() == team_name.lower():
                    actual_team_name = team_key
                    break
            
            if not actual_team_name:
                return None
            
            team = teams[actual_team_name]
            members_info = []
            guild_config = await load_guild_config(interaction)
            
            for member_id in team.members:
                # Try to get member display name
                try:
                    member = await interaction.guild.fetch_member(member_id)
                    member_name = member.display_name
                except:
                    member_name = f"Unknown ({member_id})"
                
                # Check if member has player records and PPEs
                if member_id in records:
                    player_data = records[member_id]
                    if player_data.ppes:
                        # Resolve best PPE from effective points (with current overrides).
                        best_ppe = get_best_ppe(player_data, guild_config=guild_config)
                        best_points = compute_effective_ppe_points(best_ppe, guild_config=guild_config)
                        members_info.append((member_id, member_name, best_points, best_ppe.name))
                    else:
                        # Member has no PPE characters - include them with 0 points
                        members_info.append((member_id, member_name, 0.0, None))
                else:
                    # Member not in records - include them with 0 points
                    members_info.append((member_id, member_name, 0.0, None))
            
            return (actual_team_name, team.leader_id, members_info)
        
        return await self.execute_transaction(interaction, operation)


# Global instance
team_manager = TeamManager()


def clear_guild_state(guild_id: int) -> None:
    team_manager.clear_guild_state(guild_id)


def get_lock_count() -> int:
    return team_manager.get_lock_count()
