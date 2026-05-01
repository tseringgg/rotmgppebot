"""Shared Discord views for menu ownership and interaction safety."""

from __future__ import annotations

import traceback
import logging

import discord

logger = logging.getLogger(__name__)


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

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        item_label = getattr(item, "label", None) or getattr(item, "placeholder", None) or item.__class__.__name__
        logger.error(
            "[VIEW_ERROR] view=%s item=%s owner_id=%s user_id=%s error=%s",
            self.__class__.__name__,
            item_label,
            self.owner_id,
            getattr(interaction.user, "id", None),
            error,
        )
        logger.debug(traceback.format_exc())

        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "This interaction failed due to an internal error. The traceback was logged.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "This interaction failed due to an internal error. The traceback was logged.",
                    ephemeral=True,
                )
        except Exception:
            # Avoid raising from on_error and masking the original exception.
            pass
