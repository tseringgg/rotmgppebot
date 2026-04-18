from __future__ import annotations

from typing import Any, Awaitable, Callable

import discord

from utils.ppe_types import minimum_rarity_effective, requires_enforce_shiny_rarity_choice


MINIMUM_RARITY_VALUES = ("common", "uncommon", "rare", "legendary", "divine")
SHINY_ONLY_MINIMUM_RARITY_VALUES = ("all_shinies_allowed", "legendary", "divine")


def enforce_shiny_rarity_prompt(minimum_rarity: Any, enforce_multiplier: float = 0.9) -> str:
    effective_rarity = minimum_rarity_effective(minimum_rarity)
    if effective_rarity not in {"legendary", "divine"}:
        return "Enforce shiny rarity is auto-set to Yes because shiny items already meet this minimum rarity."

    threshold_text = "Legendary+" if effective_rarity == "legendary" else "Divine"
    penalty_power = 2 if effective_rarity == "divine" else 1
    penalty_multiplier = float(enforce_multiplier) ** penalty_power

    if penalty_power == 1:
        no_line = (
            f"No: shiny drops can ignore that minimum and apply the enforce modifier once "
            f"(x{penalty_multiplier:.2f} with default x{float(enforce_multiplier):.2f})."
        )
    else:
        no_line = (
            f"No: shiny drops can ignore that minimum and apply the enforce modifier twice "
            f"(x{penalty_multiplier:.2f} with default x{float(enforce_multiplier):.2f})."
        )

    return (
        f"Enforce shiny rarity is available because minimum rarity is {effective_rarity.title()}.\n"
        f"Yes: minimum rarity also applies to shiny drops, so shiny items must be {threshold_text}.\n"
        f"{no_line}"
    )


def build_minimum_rarity_handlers(
    *,
    state: dict[str, object],
    refresh: Callable[[discord.Interaction], Awaitable[None]],
    advance: Callable[[discord.Interaction], Awaitable[None]],
) -> tuple[
    Callable[[discord.Interaction, str], Awaitable[None]],
    Callable[[discord.Interaction], Awaitable[None]],
]:
    async def _on_selected(interaction: discord.Interaction, rarity: str) -> None:
        state["minimum_rarity"] = str(rarity).strip().lower() or "common"
        if not requires_enforce_shiny_rarity_choice(state["minimum_rarity"]):
            state["enforce_rarity_on_shiny"] = True
        await refresh(interaction)

    async def _on_continue(interaction: discord.Interaction) -> None:
        await advance(interaction)

    return _on_selected, _on_continue


def get_minimum_rarity_options(shiny_only: bool) -> tuple[str, ...]:
    """Get the available minimum rarity options based on shiny_only setting."""
    if shiny_only:
        return SHINY_ONLY_MINIMUM_RARITY_VALUES
    return MINIMUM_RARITY_VALUES


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
        shiny_only: bool = False,
    ) -> None:
        selected_value = str(selected or "common").strip().lower()
        available_values = get_minimum_rarity_options(shiny_only)
        
        # Adjust selected value if needed based on available options
        if selected_value not in available_values:
            selected_value = available_values[0]

        options = [
            discord.SelectOption(
                label=_rarity_option_label(value),
                value=value,
                default=selected_value == value,
            )
            for value in available_values
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

        selected_value = str(self.values[0]).strip().lower()
        for option in self.options:
            option.default = option.value == selected_value

        await self._on_selected(interaction, selected_value)


def _rarity_option_label(value: str) -> str:
    """Get the display label for a minimum rarity option."""
    labels = {
        "common": "Common",
        "uncommon": "Uncommon",
        "rare": "Rare",
        "legendary": "Legendary",
        "divine": "Divine",
        "all_shinies_allowed": "All Shinies Allowed",
    }
    return labels.get(value.lower(), value.title())


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
