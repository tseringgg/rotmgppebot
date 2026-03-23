import discord
import os

from utils.loot_table_md_builder import create_loot_markdown_file
from utils.embed_builders import build_loot_embed


class LootTableMessage:
    """
    Centralized class for handling loot table message generation and delivery across commands.
    Supports different message types and configurations for various use cases.
    """
    
    def __init__(self, interaction: discord.Interaction, message_type: str = "markdown", response: str = None, **config):
        """
        Initialize loot table message handler.
        
        Args:
            interaction: Discord interaction object for sending messages
            message_type: Type of message to send ("markdown", "embed", "visual")
            response: Optional initial response message. If provided, loot table will be sent as followup
            **config: Additional configuration options for message formatting
        """
        self.interaction = interaction
        self.message_type = message_type
        self.response = response
        self.config = config
    
    async def send_player_loot(self, active_ppe, **kwargs):
        """
        Send loot table based on configured message type.
        
        Args:
            active_ppe: The active PPE data object
            **kwargs: Additional arguments specific to message type
        """
        try:
            # Send initial response message if provided
            if self.response:
                await self.interaction.response.send_message(
                    self.response, 
                    ephemeral=self.config.get('response_ephemeral', False)
                )
            
            # Send loot table (either as response or followup)
            if self.message_type == "markdown":
                await self._send_markdown_file(active_ppe)
            elif self.message_type == "embed":
                await self._send_embed(active_ppe, **kwargs)
            elif self.message_type == "visual":
                await self._send_visual(active_ppe, **kwargs)
            else:
                raise ValueError(f"Unsupported message type: {self.message_type}")
        except (ValueError, KeyError) as e:
            # Handle errors - use response if not already used, otherwise followup
            error_msg = str(e)
            if self.response:
                await self.interaction.followup.send(error_msg, ephemeral=True)
            else:
                await self.interaction.response.send_message(error_msg, ephemeral=True)
    
    async def _send_markdown_file(self, active_ppe):
        """Send loot table as a markdown file attachment."""
        temp_file_path = create_loot_markdown_file(active_ppe)
        
        try:
            # Send the file as attachment (response or followup based on whether response was already sent)
            if self.response:
                # Use followup since response was already sent
                await self.interaction.followup.send(
                    file=discord.File(temp_file_path), 
                    ephemeral=self.config.get('ephemeral', True)
                )
            else:
                # Use response since no initial response was sent
                await self.interaction.response.send_message(
                    file=discord.File(temp_file_path), 
                    ephemeral=self.config.get('ephemeral', True)
                )
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    
    async def _send_embed(self, active_ppe, **kwargs):
        """Send loot table as a Discord embed."""
        # Build the loot embed using existing utility
        user_id = kwargs.get('user_id', self.interaction.user.id)
        recently_added = kwargs.get('recently_added', None)
        embed = await build_loot_embed(active_ppe, user_id=user_id, recently_added=recently_added)
        
        # Prepare content message
        content = self.config.get('embed_content', f"Your active PPE now has **{active_ppe.points} total points**.")
        
        # Send embed (response or followup based on whether response was already sent)
        if self.response:
            # Use followup since response was already sent
            await self.interaction.followup.send(
                content=content,
                view=embed,
                embed=embed.embeds[0],
                ephemeral=self.config.get('ephemeral', True)
            )
        else:
            # Use response since no initial response was sent
            await self.interaction.response.send_message(
                content=content,
                view=embed,
                embed=embed.embeds[0],
                ephemeral=self.config.get('ephemeral', True)
            )
    
    async def _send_visual(self, active_ppe, **kwargs):
        """Send loot table as a visual image (placeholder for future implementation)."""
        # TODO: Implement visual loot table similar to shareloot_cmd
        # This would handle visual loot table generation and sending
        # Will need to handle response vs followup like _send_markdown_file
        raise NotImplementedError("Visual message type not yet implemented")
