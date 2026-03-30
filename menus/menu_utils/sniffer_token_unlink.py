"""Reusable token unlink picker components for sniffer menus."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import discord

from menus.menu_utils import OwnerBoundView
from menus.menu_utils.sniffer_shared import token_preview

OnRevoke = Callable[[discord.Interaction, str], Awaitable[bool]]


class TokenUnlinkSelect(discord.ui.Select):
    def __init__(self, owner_id: int, tokens: list[str], on_revoke: OnRevoke) -> None:
        options = [
            discord.SelectOption(label=token_preview(token), value=token, description="Revoke this token")
            for token in tokens[:25]
        ]
        super().__init__(
            placeholder="Select a token to revoke",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.owner_id = owner_id
        self.on_revoke = on_revoke

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This picker belongs to another user.", ephemeral=True)
            return

        token = self.values[0]
        revoked = await self.on_revoke(interaction, token)
        if revoked:
            await interaction.response.edit_message(content="✅ Sniffer token revoked.", embed=None, view=None)
        else:
            await interaction.response.edit_message(content="Token was already removed.", embed=None, view=None)


class TokenUnlinkView(OwnerBoundView):
    def __init__(self, owner_id: int, tokens: list[str], on_revoke: OnRevoke) -> None:
        super().__init__(owner_id=owner_id, timeout=180, owner_error="This unlink menu belongs to another user.")
        self.add_item(TokenUnlinkSelect(owner_id, tokens, on_revoke))


__all__ = ["TokenUnlinkSelect", "TokenUnlinkView"]
