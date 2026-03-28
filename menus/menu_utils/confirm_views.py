"""Reusable confirmation views for menu actions that need explicit user consent."""

from __future__ import annotations

import discord

from menus.menu_utils.base_views import OwnerBoundView


class _ConfirmActionButton(discord.ui.Button):
    def __init__(self, label: str, style: discord.ButtonStyle, is_confirm: bool) -> None:
        super().__init__(label=label, style=style)
        self.is_confirm = is_confirm

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ConfirmCancelView):
            await interaction.response.send_message("Invalid confirmation state.", ephemeral=True)
            return

        # Persist the selected outcome so the caller can read it after wait().
        view.confirmed = self.is_confirm
        await interaction.response.defer()
        view.stop()


class ConfirmCancelView(OwnerBoundView):
    """Generic owner-bound confirmation view for yes/no flows."""

    def __init__(
        self,
        *,
        owner_id: int,
        timeout: float | None = 60,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        confirm_style: discord.ButtonStyle = discord.ButtonStyle.danger,
        cancel_style: discord.ButtonStyle = discord.ButtonStyle.secondary,
        owner_error: str = "This confirmation belongs to another user.",
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=timeout, owner_error=owner_error)
        self.confirmed = False
        self.add_item(_ConfirmActionButton(confirm_label, confirm_style, is_confirm=True))
        self.add_item(_ConfirmActionButton(cancel_label, cancel_style, is_confirm=False))
