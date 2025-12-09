import asyncio
from typing import Dict, Optional
import discord
from dataclass import Loot, PPEData, PlayerData
from utils.player_records import load_player_records, save_player_records, ensure_player_exists, get_active_ppe

class PlayerManager:
    """Centralized manager for player data operations to prevent race conditions."""
    
    def __init__(self):
        self._locks: Dict[int, asyncio.Lock] = {}
    
    def _get_lock(self, guild_id: int) -> asyncio.Lock:
        """Get or create a lock for a specific guild."""
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()
        return self._locks[guild_id]
    
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
                                divine: bool = False, shiny: bool = False, points: float = 0) -> tuple:
        """Add loot and points atomically."""
        
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
            
            # Add loot
            from utils.player_records import get_item_from_ppe
            match = get_item_from_ppe(active_ppe, item_name, divine, shiny)
            will_be_duplicate = match is not None
            if will_be_duplicate and points != 1:
                points_to_add = points / 2
            else:
                points_to_add = points
            if match:
                match.quantity += 1
            else:
                active_ppe.loot.append(Loot(item_name=item_name, quantity=1, divine=divine, shiny=shiny))
            
            # Add points
            import math
            points_rounded = math.floor(points_to_add * 2) / 2
            active_ppe.points += points_rounded
            
            return item_name, points_rounded, active_ppe
        
        return await self.execute_transaction(interaction, operation)
    
    async def remove_loot_and_points(self, interaction: discord.Interaction, user: discord.Member, ppe_id: int, item_name: str, 
                                   divine: bool = False, shiny: bool = False, points: float = 0) -> tuple:
        """Remove loot and points atomically."""
        
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
            
            from utils.player_records import get_item_from_ppe
            item = get_item_from_ppe(active_ppe, item_name, divine, shiny)
            if not item:
                raise ValueError(f"❌ You don't have any **{item_name}** in your active PPE's loot.")
            
            # Calculate points to remove based on duplicate logic
            # If this is the only one (quantity will be 0 after removal), use full points
            # If there will still be more (quantity > 1), use halved points (unless base points = 1)
            will_be_duplicate = item.quantity > 1
            
            if points != 1 and will_be_duplicate:
                points_to_remove = points / 2
            else:
                points_to_remove = points
            
            item.quantity -= 1
            if item.quantity <= 0:
                active_ppe.loot.remove(item)
            
            # Remove points
            import math
            points_rounded = math.floor(points_to_remove * 2) / 2
            active_ppe.points -= points_rounded
            
            return item_name, points_rounded, active_ppe
        
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
            
            # PPE limit check
            if len(player_data.ppes) >= 10:
                raise ValueError("⚠️ You've reached the limit of 10 PPEs.")
            
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