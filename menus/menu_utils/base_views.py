"""Shared Discord views for menu ownership and interaction safety."""

from __future__ import annotations

import discord


class OwnerBoundView(discord.ui.View):
    """A reusable view that restricts interactions to one owner user."""

    def __init__(
        self,
        *,
        owner_id: int,
        timeout: float | None = 600,
        owner_error: str = "This panel belongs to another user.",
    ) -> None:
        super().__init__(timeout=timeout)
        self.owner_id = owner_id
        self.owner_error = owner_error

    async def ensure_owner(self, interaction: discord.Interaction) -> bool:
        # Prevent other users from interacting with someone else's menu panel.
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(self.owner_error, ephemeral=True)
            return False
        return True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self.ensure_owner(interaction)
