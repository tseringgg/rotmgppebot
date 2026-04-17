from __future__ import annotations

from typing import Any, Awaitable, Callable

import discord


MINIMUM_RARITY_VALUES = ("common", "uncommon", "rare", "legendary", "divine")


class MinimumRaritySelect(discord.ui.Select):
    def __init__(
        self,
        *,
        selected: str,
        owner_id: int,
        view_type: type,
        on_selected: Callable[[discord.Interaction, str], Awaitable[None]],
        owner_error: str = "This menu belongs to another user.",
        row: int = 0,
    ) -> None:
        selected_value = str(selected or "common").strip().lower()
        if selected_value not in MINIMUM_RARITY_VALUES:
            selected_value = "common"

        options = [
            discord.SelectOption(
                label=value.title(),
                value=value,
                default=selected_value == value,
            )
            for value in MINIMUM_RARITY_VALUES
        ]
        super().__init__(
            placeholder="Select minimum rarity",
            min_values=1,
            max_values=1,
            options=options,
            row=row,
        )
        self._owner_id = owner_id
        self._view_type = view_type
        self._owner_error = owner_error
        self._on_selected = on_selected

    async def callback(self, interaction: discord.Interaction) -> None:
        view: Any = self.view
        if not isinstance(view, self._view_type):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != self._owner_id:
            await interaction.response.send_message(self._owner_error, ephemeral=True)
            return

        await self._on_selected(interaction, self.values[0])


class MinimumRarityContinueButton(discord.ui.Button):
    def __init__(
        self,
        *,
        owner_id: int,
        view_type: type,
        on_continue: Callable[[discord.Interaction], Awaitable[None]],
        owner_error: str = "This menu belongs to another user.",
        row: int = 0,
        label: str = "Continue",
    ) -> None:
        super().__init__(label=label, style=discord.ButtonStyle.success, row=row)
        self._owner_id = owner_id
        self._view_type = view_type
        self._owner_error = owner_error
        self._on_continue = on_continue

    async def callback(self, interaction: discord.Interaction) -> None:
        view: Any = self.view
        if not isinstance(view, self._view_type):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != self._owner_id:
            await interaction.response.send_message(self._owner_error, ephemeral=True)
            return

        await self._on_continue(interaction)
