"""Utilities for player manager."""

import asyncio
from typing import Dict, Optional, List, Tuple
import discord
from dataclass import Loot, PPEData, PlayerData
from utils.player_records import load_player_records, save_player_records, ensure_player_exists, get_active_ppe
from utils.player_records import get_item_from_ppe, highest_rarity, load_teams
from utils.quest_manager import update_quests_for_item
from utils.guild_config import get_max_ppes, get_quest_targets
from utils.guild_config import load_guild_config, save_guild_config
from utils.quest_modes import build_global_quests_payload, build_team_quests_context
from utils.points_service import recompute_ppe_points
from utils.item_log_timestamps import now_unix_utc
from utils.season_loot_history import add_season_item_log, normalize_rarity, remove_season_item_log
from utils.set_operations import get_newly_completed_sets, get_no_longer_completed_sets


def _remove_most_recent_timestamp(times: list[int]) -> list[int]:
    if not times:
        return []

    sorted_times = sorted(int(ts) for ts in times)
    sorted_times.pop()
    return sorted_times

class PlayerManager:
    """Centralized manager for player data operations to prevent race conditions."""
    
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
    
    async def execute_transaction(self, interaction: discord.Interaction, operation):
        """Execute a data operation atomically with proper locking."""
        if not interaction.guild:
            raise ValueError("❌ This command can only be used in a server.")
        
        guild_id = interaction.guild.id
        async with self._get_lock(guild_id):
            # Load data
            records = await load_player_records(interaction)
            
            # Execute the operation
            result = await operation(records, interaction)
            
            # Save data
            await save_player_records(interaction, records)
            
            return result
    
    async def add_loot_and_points(self, interaction: discord.Interaction, user: discord.Member, ppe_id:int, item_name: str,
                                shiny: bool = False, rarity: str = "common", points: float = 0) -> tuple:
        """Add loot and points atomically. Returns (item_name, points_rounded, active_ppe, quest_update, newly_completed_sets)."""
        effective_rarity = normalize_rarity(rarity, "common")
        
        async def operation(records, interaction):
            user_id = user.id
            key = ensure_player_exists(records, user_id)
            
            # Check if user is member
            if key not in records or not records[key].is_member:
                raise KeyError("❌ You're not part of the PPE contest.")
            
            player_data = records[key]
            if not player_data.active_ppe:
                raise LookupError("❌ You don't have an active PPE.")
            
            
            active_ppe = None
            for ppe in player_data.ppes:
                if ppe.id == ppe_id:
                    active_ppe = ppe
                    break
            if not active_ppe:
                raise LookupError("❌ Could not find your active PPE record.")
            
            old_total = active_ppe.points
            
            # Store previously completed sets before adding loot
            previously_completed_sets = list(active_ppe.completed_sets) if active_ppe.completed_sets else []

            # Add loot
            match = get_item_from_ppe(active_ppe, item_name, shiny, rarity=effective_rarity)
            logged_at = now_unix_utc()
            if match:
                match.quantity += 1
                times = list(getattr(match, "logged_times", []))
                times.append(logged_at)
                times.sort()
                setattr(match, "logged_times", times)
            else:
                active_ppe.loot.append(
                    Loot(
                        item_name=item_name,
                        quantity=1,
                        shiny=shiny,
                        rarity=effective_rarity,
                        logged_times=[logged_at],
                    )
                )

            add_season_item_log(
                player_data,
                item_name=item_name,
                shiny=shiny,
                rarity=effective_rarity,
                timestamp=logged_at,
            )
            
            guild_config = await load_guild_config(interaction)
            
            # Check for newly completed sets
            newly_completed = get_newly_completed_sets(active_ppe, previously_completed_sets)
            
            if newly_completed:
                from utils.guild_config import get_set_bonuses
                from utils.set_operations import load_item_sets
                set_bonuses = get_set_bonuses(guild_config)
                all_sets = load_item_sets()
                
                # Add newly completed sets to the tracking list
                for set_name, set_type in newly_completed:
                    if set_name not in active_ppe.completed_sets:
                        active_ppe.completed_sets.append(set_name)
                
                # Recalculate TOTAL set bonus based on ALL completed sets (not just newly completed)
                # This ensures we have one consolidated "Set Completion Bonus" entry
                total_set_bonus = 0.0
                for set_name in active_ppe.completed_sets:
                    if set_name in all_sets:
                        set_type = all_sets[set_name]["type"]
                        if set_type in set_bonuses and set_name in set_bonuses[set_type]:
                            total_set_bonus += set_bonuses[set_type][set_name]
                
                # Remove all existing "Set Completion Bonus" entries
                active_ppe.bonuses = [b for b in active_ppe.bonuses if b.name != "Set Completion Bonus"]
                
                # Add new consolidated set bonus if there are any points
                if total_set_bonus > 0:
                    from dataclass import Bonus
                    bonus = Bonus(
                        name="Set Completion Bonus",
                        points=total_set_bonus,
                        repeatable=False,
                        quantity=1
                    )
                    active_ppe.bonuses.append(bonus)
            
            recompute_ppe_points(active_ppe, guild_config)
            points_rounded = round(active_ppe.points - old_total, 2)

            regular_target, shiny_target, skin_target = await get_quest_targets(interaction)
            quest_settings = guild_config["quest_settings"]
            teams = await load_teams(interaction)
            team_context = build_team_quests_context(
                settings=quest_settings,
                player_data=player_data,
                records=records,
                teams=teams,
            )
            quest_update = update_quests_for_item(
                player_data,
                item_name,
                shiny,
                target_item_quests=regular_target,
                target_shiny_quests=shiny_target,
                target_skin_quests=skin_target,
                global_quests=build_global_quests_payload(quest_settings),
                team_quests=team_context,
            )

            if quest_update.get("team_state_changed"):
                await save_guild_config(interaction, guild_config)
            
            return item_name, points_rounded, active_ppe, quest_update, newly_completed
        
        return await self.execute_transaction(interaction, operation)
    
    async def remove_loot_and_points(self, interaction: discord.Interaction, user: discord.Member, ppe_id: int, item_name: str, 
                                   shiny: bool = False, rarity: str = "common", points: float = 0) -> tuple:
        """Remove loot and points atomically. Returns (item_name, points_rounded, active_ppe, removed_sets)."""
        effective_rarity = normalize_rarity(rarity, "common")
        
        async def operation(records, interaction):
            user_id = user.id
            key = ensure_player_exists(records, user_id)
            
            player_data = records[key]
            active_ppe = None
            for ppe in player_data.ppes:
                if ppe.id == ppe_id:
                    active_ppe = ppe
                    break

            if not active_ppe:
                raise LookupError("❌ Could not find your active PPE record.")
            
            item = get_item_from_ppe(active_ppe, item_name, shiny, rarity=effective_rarity)
            if not item:
                raise ValueError(f"❌ You don't have any **{item_name}** in your active PPE's loot.")
            
            old_total = active_ppe.points
            
            # Store previously completed sets before removing loot
            previously_completed_sets = list(active_ppe.completed_sets) if active_ppe.completed_sets else []
            
            item.quantity -= 1
            times = list(getattr(item, "logged_times", []))
            if times:
                setattr(item, "logged_times", _remove_most_recent_timestamp(times))
            if item.quantity <= 0:
                active_ppe.loot.remove(item)
                
                # Check if this item still exists in any other PPE
                item_key = (item_name, shiny)
                item_exists_elsewhere = False
                for ppe in player_data.ppes:
                    for loot in ppe.loot:
                        if (loot.item_name, loot.shiny) == item_key and loot.quantity > 0:
                            item_exists_elsewhere = True
                            break
                    if item_exists_elsewhere:
                        break

            remove_season_item_log(
                player_data,
                item_name=item_name,
                shiny=shiny,
                rarity=effective_rarity,
                remove_all=False,
            )
            
            # Check for sets that are no longer completed and remove their bonuses
            no_longer_completed_sets = get_no_longer_completed_sets(active_ppe, previously_completed_sets)
            if no_longer_completed_sets:
                from utils.set_operations import load_item_sets
                from utils.guild_config import get_set_bonuses
                
                guild_config = await load_guild_config(interaction)
                set_bonuses = get_set_bonuses(guild_config)
                all_sets = load_item_sets()
                
                # Remove sets from tracking
                for removed_set_name, _ in no_longer_completed_sets:
                    if removed_set_name in active_ppe.completed_sets:
                        active_ppe.completed_sets.remove(removed_set_name)
                
                # Recalculate total set bonus based on remaining completed sets
                remaining_set_bonus = 0.0
                for set_name in active_ppe.completed_sets:
                    if set_name in all_sets:
                        set_type = all_sets[set_name]["type"]
                        if set_type in set_bonuses and set_name in set_bonuses[set_type]:
                            remaining_set_bonus += set_bonuses[set_type][set_name]
                
                # Remove all "Set Completion Bonus" entries
                active_ppe.bonuses = [b for b in active_ppe.bonuses if b.name != "Set Completion Bonus"]
                
                # Re-add the new set bonus amount if there are any remaining sets
                if remaining_set_bonus > 0:
                    from dataclass import Bonus
                    bonus = Bonus(
                        name="Set Completion Bonus",
                        points=remaining_set_bonus,
                        repeatable=False,
                        quantity=1
                    )
                    active_ppe.bonuses.append(bonus)
            
            guild_config = await load_guild_config(interaction)
            recompute_ppe_points(active_ppe, guild_config)
            points_rounded = round(old_total - active_ppe.points, 2)
            
            return item_name, points_rounded, active_ppe, no_longer_completed_sets
        
        return await self.execute_transaction(interaction, operation)

    async def add_points_only(self, interaction: discord.Interaction, amount: float) -> float:
        """Add points only (for admin commands)."""
        
        async def operation(records, interaction):
            user_id = interaction.user.id
            key = ensure_player_exists(records, user_id)
            
            player_data = records[key]
            active_ppe = get_active_ppe(player_data)
            
            import math
            amount_rounded = math.floor(amount * 2) / 2
            active_ppe.points += amount_rounded
            
            return amount_rounded
        
        return await self.execute_transaction(interaction, operation)
    
    async def create_ppe(self, interaction: discord.Interaction, class_enum) -> int:
        """Create a new PPE atomically."""
        
        async def operation(records, interaction):
            user_id = interaction.user.id
            key = ensure_player_exists(records, user_id)
            
            player_data = records[key]
            max_ppes = await get_max_ppes(interaction)
            
            # PPE limit check
            if len(player_data.ppes) >= max_ppes:
                raise ValueError(f"⚠️ You've reached the limit of {max_ppes} PPEs.")
            
            # Create new PPE
            next_id = max((ppe.id for ppe in player_data.ppes), default=0) + 1
            new_ppe = PPEData(id=next_id, name=class_enum, points=0, loot=[])
            
            player_data.ppes.append(new_ppe)
            player_data.active_ppe = next_id
            
            return next_id, len(player_data.ppes)
        
        return await self.execute_transaction(interaction, operation)
    
    async def add_points_to_member(self, interaction: discord.Interaction, member_id: int, ppe_id: int, amount: float) -> tuple:
        """Add points to a specific member's active PPE (admin command)."""
        
        async def operation(records, interaction):
            key = ensure_player_exists(records, member_id)
            
            if key not in records or not records[key].is_member:
                raise KeyError("❌ This member is not part of the PPE contest.")
            
            player_data = records[key]
            if not player_data.active_ppe:
                raise LookupError("❌ This member does not have an active PPE.")
            
            active_ppe = next((ppe for ppe in player_data.ppes if ppe.id == ppe_id), None)
            if not active_ppe:
                raise LookupError("❌ Could not find the member's active PPE record.")
            
            import math
            amount_rounded = math.floor(amount * 2) / 2
            active_ppe.points += amount_rounded
            
            return amount_rounded, active_ppe.id, active_ppe.points
        
        return await self.execute_transaction(interaction, operation)
    
    async def set_active_ppe(self, interaction: discord.Interaction, ppe_id: int) -> tuple:
        """Set which PPE is active for a user."""
        
        async def operation(records, interaction):
            user_id = interaction.user.id
            key = ensure_player_exists(records, user_id)
            
            player_data = records[key]
            ppe_ids = [ppe.id for ppe in player_data.ppes]
            if ppe_id not in ppe_ids:
                raise ValueError(f"❌ You don't have a PPE #{ppe_id}.")
            
            player_data.active_ppe = ppe_id
            active_ppe = get_active_ppe(player_data)
            
            return active_ppe, player_data.ppes
        
        return await self.execute_transaction(interaction, operation)
    
    async def add_player_to_contest(self, interaction: discord.Interaction, member_id: int) -> bool:
        """Add a player to the PPE contest."""
        
        async def operation(records, interaction):
            key = ensure_player_exists(records, member_id)
            records[key].is_member = True
            return key in records
        
        return await self.execute_transaction(interaction, operation)
    
    async def remove_player_from_contest(self, interaction: discord.Interaction, member_id: int) -> bool:
        """Remove a player from the PPE contest."""
        
        async def operation(records, interaction):
            key = ensure_player_exists(records, member_id)
            records[key].is_member = False
            return True
        
        return await self.execute_transaction(interaction, operation)
    
    async def delete_all_ppes(self, interaction: discord.Interaction, member_id: int) -> bool:
        """Delete all PPEs for a member."""
        
        async def operation(records, interaction):
            key = ensure_player_exists(records, member_id)
            
            if key not in records or not records[key].ppes:
                raise ValueError("❌ This member doesn't have any PPEs to delete.")
            
            records[key].ppes = []
            records[key].active_ppe = None
            return True
        
        return await self.execute_transaction(interaction, operation)

    async def delete_ppe(self, interaction: discord.Interaction, member_id: int, ppe_id: int) -> bool:
        """Delete a specific PPE for a member."""
        
        async def operation(records, interaction):
            key = ensure_player_exists(records, member_id)
            
            player_data = records[key]
            ppe_to_delete = next((ppe for ppe in player_data.ppes if ppe.id == ppe_id), None)
            if not ppe_to_delete:
                raise ValueError(f"❌ PPE #{ppe_id} not found for this member.")
            
            player_data.ppes.remove(ppe_to_delete)
            if player_data.active_ppe == ppe_id:
                player_data.active_ppe = player_data.ppes[0].id if player_data.ppes else None
            
            return True
        
        return await self.execute_transaction(interaction, operation)

# Global instance
player_manager = PlayerManager()


def clear_guild_state(guild_id: int) -> None:
    player_manager.clear_guild_state(guild_id)


def get_lock_count() -> int:
    return player_manager.get_lock_count()
