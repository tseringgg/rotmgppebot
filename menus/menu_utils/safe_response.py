"""Centralized helpers for safe Discord interaction response handling.

Provides consistent methods to send, edit, and close messages safely
regardless of whether the interaction response has already been deferred
or sent.

Usage:
    from menus.menu_utils.safe_response import SafeResponse
    
    # Send a text message
    await SafeResponse.send_text(interaction, "Hello", ephemeral=True)
    
    # Edit the response message
    await SafeResponse.edit_message(interaction, ...)
    
    # Close a menu message
    await SafeResponse.close(interaction, close_message="Menu closed.")
"""

from __future__ import annotations

import discord


class SafeResponse:
    """Safe interaction response methods that handle deferred/sent state."""

    @staticmethod
    async def send_text(
        interaction: discord.Interaction,
        content: str,
        *,
        ephemeral: bool = False,
    ) -> None:
        """Send a text message, using followup if response already handled.
        
        Args:
            interaction: The Discord interaction.
            content: The message text to send.
            ephemeral: Whether the message should be visible only to the user.
        """
        if not interaction.response.is_done():
            await interaction.response.send_message(content, ephemeral=ephemeral)
        else:
            await interaction.followup.send(content, ephemeral=ephemeral)

    @staticmethod
    async def send_embed(
        interaction: discord.Interaction,
        embed: discord.Embed,
        *,
        ephemeral: bool = False,
        view: discord.ui.View | None = None,
    ) -> None:
        """Send an embed message, using followup if response already handled.
        
        Args:
            interaction: The Discord interaction.
            embed: The embed to send.
            ephemeral: Whether the message should be visible only to the user.
            view: Optional view with buttons/select menus.
        """
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral, view=view)
        else:
            await interaction.followup.send(embed=embed, ephemeral=ephemeral, view=view)

    @staticmethod
    async def send_embeds(
        interaction: discord.Interaction,
        embeds: list[discord.Embed],
        *,
        ephemeral: bool = False,
        view: discord.ui.View | None = None,
    ) -> None:
        """Send multiple embeds, using followup if response already handled.
        
        Args:
            interaction: The Discord interaction.
            embeds: List of embeds to send.
            ephemeral: Whether the message should be visible only to the user.
            view: Optional view with buttons/select menus.
        """
        if not interaction.response.is_done():
            await interaction.response.send_message(embeds=embeds, ephemeral=ephemeral, view=view)
        else:
            await interaction.followup.send(embeds=embeds, ephemeral=ephemeral, view=view)

    @staticmethod
    async def edit_message(
        interaction: discord.Interaction,
        content: str | None = None,
        *,
        embed: discord.Embed | None = None,
        embeds: list[discord.Embed] | None = None,
        view: discord.ui.View | None = None,
    ) -> None:
        """Edit the response message if it hasn't been sent yet, or defer if already sent.
        
        Only works if the response hasn't been sent. If already sent, will defer.
        
        Args:
            interaction: The Discord interaction.
            content: Updated message content (use None to clear).
            embed: Updated single embed (ignored if embeds provided).
            embeds: Updated list of embeds.
            view: Updated view with buttons/select menus.
        """
        if interaction.response.is_done():
            await interaction.response.defer()
            return

        await interaction.response.edit_message(
            content=content, embed=embed, embeds=embeds, view=view
        )

    @staticmethod
    async def close(
        interaction: discord.Interaction,
        close_message: str = "Menu closed.",
        *,
        defer_if_sent: bool = False,
    ) -> None:
        """Close a menu by editing the response or deferring if already sent.
        
        Attempts to edit the response message to show a closure message.
        If the response is already sent/deferred, optionally defer instead.
        If the message is no longer found, silently defer.
        
        Args:
            interaction: The Discord interaction.
            close_message: Message to display when closing.
            defer_if_sent: If True, defer when response already sent. 
                          If False, do nothing.
        """
        if interaction.response.is_done():
            if defer_if_sent:
                try:
                    await interaction.response.defer()
                except discord.errors.InteractionResponded:
                    pass
            return

        try:
            await interaction.response.edit_message(
                content=close_message, embed=None, view=None
            )
        except discord.NotFound:
            await interaction.response.defer()
        except discord.errors.InteractionResponded:
            pass
