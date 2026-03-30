"""Token management submenus for /managesniffer."""

from __future__ import annotations

import discord

from menus.managesniffer.common import build_tokens_embed
from menus.managesniffer.models import SnifferTokenRow
from menus.managesniffer.services import load_token_entries, revoke_token
from menus.menu_utils import OwnerBoundView
from menus.menu_utils.sniffer_shared import token_preview


async def confirm_token_delete(
    interaction: discord.Interaction,
    *,
    owner_id: int,
    token: str,
) -> bool:
    from menus.menu_utils import ConfirmCancelView

    confirm_view = ConfirmCancelView(
        owner_id=owner_id,
        timeout=60,
        confirm_label="Confirm Delete",
        cancel_label="Cancel",
        confirm_style=discord.ButtonStyle.danger,
        cancel_style=discord.ButtonStyle.secondary,
        owner_error="This confirmation belongs to another admin.",
    )
    await interaction.response.send_message(
        f"⚠️ Delete token `{token_preview(token)}`? This cannot be undone.",
        view=confirm_view,
        ephemeral=True,
    )

    await confirm_view.wait()
    try:
        await interaction.delete_original_response()
    except discord.HTTPException:
        pass

    if not confirm_view.confirmed:
        await interaction.followup.send("Token deletion cancelled.", ephemeral=True)
        return False

    deleted = await revoke_token(interaction, token)
    if deleted:
        await interaction.followup.send("Token revoked.", ephemeral=True)
    else:
        await interaction.followup.send("Token was already removed.", ephemeral=True)
    return deleted


class _DeleteTokenSelect(discord.ui.Select):
    def __init__(self, owner_id: int, token_window: list[SnifferTokenRow]) -> None:
        options = [
            discord.SelectOption(label=token_preview(row.token), value=row.token, description="Delete token")
            for row in token_window[:25]
        ]
        super().__init__(
            placeholder="Select a token to revoke",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This picker belongs to another admin.", ephemeral=True)
            return

        token = self.values[0]
        await confirm_token_delete(interaction, owner_id=self.owner_id, token=token)


class TokenDeletePickerView(OwnerBoundView):
    def __init__(self, owner_id: int, token_window: list[SnifferTokenRow]) -> None:
        super().__init__(owner_id=owner_id, timeout=180, owner_error="This picker belongs to another admin.")
        self.add_item(_DeleteTokenSelect(owner_id, token_window))


class ManageSnifferTokensView(OwnerBoundView):
    def __init__(self, owner_id: int, page: int = 0) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another admin.")
        self.page = page
        self.per_page = 8

    async def _entries(self, interaction: discord.Interaction) -> list[SnifferTokenRow]:
        return await load_token_entries(interaction)

    async def _render(self, interaction: discord.Interaction) -> None:
        entries = await self._entries(interaction)
        total_pages = max(1, (len(entries) + self.per_page - 1) // self.per_page)
        self.page = max(0, min(self.page, total_pages - 1))
        embed = build_tokens_embed(
            guild=interaction.guild,
            page=self.page,
            per_page=self.per_page,
            token_entries=entries,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        entries = await self._entries(interaction)
        total_pages = max(1, (len(entries) + self.per_page - 1) // self.per_page)
        self.page = (self.page - 1) % total_pages
        await self._render(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        entries = await self._entries(interaction)
        total_pages = max(1, (len(entries) + self.per_page - 1) // self.per_page)
        self.page = (self.page + 1) % total_pages
        await self._render(interaction)

    @discord.ui.button(label="Delete Token", style=discord.ButtonStyle.danger)
    async def delete_token_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        entries = await self._entries(interaction)
        if not entries:
            await interaction.response.send_message("No tokens to delete.", ephemeral=True)
            return

        start = self.page * self.per_page
        window = entries[start:start + self.per_page]
        await interaction.response.send_message(
            "Select a token to revoke from this page.",
            view=TokenDeletePickerView(self.owner_id, window),
            ephemeral=True,
        )

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._render(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.managesniffer.submenus.home.views import render_managesniffer_home

        await render_managesniffer_home(interaction, owner_id=self.owner_id)


__all__ = [
    "ManageSnifferTokensView",
    "TokenDeletePickerView",
    "confirm_token_delete",
]
