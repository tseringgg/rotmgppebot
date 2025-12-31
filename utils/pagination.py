"""
Discord pagination utility for handling large embeds.
"""
import discord
from typing import List

from sqlalchemy import Null


def chunk_lines_to_pages(lines: List[str], max_chars: int) -> List[List[str]]:
    """
    Split lines into pages, ensuring no page exceeds max_chars limit.
    Never breaks a line, only splits on line boundaries.
    """
    if not lines:
        return [[]]
        
    pages = []
    current_page = []
    current_length = 0
    
    for line in lines:
        # Account for newline character when joining (except for first line)
        line_length = len(line)
        if current_page:  # Add newline length if not first line in page
            line_length += 1
        
        # If adding this line would exceed the limit, start a new page
        if current_length + line_length > max_chars and current_page:
            pages.append(current_page)
            current_page = [line]
            current_length = len(line)
        else:
            current_page.append(line)
            current_length += line_length
    
    # Don't forget the last page
    if current_page:
        pages.append(current_page)
    
    # Ensure we always return at least one page
    if not pages:
        return [[]]
    
    return pages


class LootPaginationView(discord.ui.View):
    """Discord UI View for paginating through loot embeds."""
    
    def __init__(self, embeds: List[discord.Embed], user_id: int):
        super().__init__(timeout=120.0)
        self.embeds = embeds
        self.current_page = 0
        self.user_id = user_id
        # self.message: discord.Message # Will be set after sending the message
        
        # Update button states
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current page."""
        # Disable prev button on first page
        self.prev_button.disabled = self.current_page == 0
        # Disable next button on last page
        self.next_button.disabled = self.current_page == len(self.embeds) - 1
    
    async def on_timeout(self):
        """Called when the view times out."""
        # Disable all buttons when timed out
        # for item in self.children:
        #     if isinstance(item, discord.ui.Button):
        #         item.disabled = True
        self.prev_button.disabled = True
        self.next_button.disabled = True
        
        # # Try to update the message to show disabled buttons
        # if self.message:
        #     try:
        #         await self.message.edit(view=self)
        #     except discord.NotFound:
        #         pass  # Message was deleted
        #     except discord.Forbidden:
        #         pass  # No permission to edit
        #     except Exception:
        #         pass  # Other errors
    
    @discord.ui.button(label='◀ Prev', style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle previous page button click."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your menu!", ephemeral=True)
            return
        
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
    
    @discord.ui.button(label='Next ▶', style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle next page button click."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your menu!", ephemeral=True)
            return
        
        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
