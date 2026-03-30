"""Entry points for the /myquests interactive quest-tracking menu."""

from __future__ import annotations

import discord

from menus.myquests.common import build_myquests_state, build_myquests_state_for_player, send_interaction_message
from menus.myquests.views import MyQuestsView


async def open_myquests_menu(interaction: discord.Interaction, *, ephemeral: bool = False) -> None:
    """Build and send the main /myquests panel for the invoking player."""

    state = await build_myquests_state(interaction)

    view = MyQuestsView(
        owner_id=state["user_id"],
        display_name=state["display_name"],
        home_embed=state["home_embed"],
        current_regular=state["current_regular"],
        current_shiny=state["current_shiny"],
        current_skin=state["current_skin"],
        current_all=state["current_all"],
        completed_embed=state["completed_embed"],
        global_mode_enabled=state["global_mode_enabled"],
    )

    await send_interaction_message(interaction, embed=state["home_embed"], view=view, ephemeral=ephemeral)


async def open_myquests_menu_for_player(
    interaction: discord.Interaction,
    *,
    owner_id: int,
    target_user_id: int,
    target_display_name: str,
    ephemeral: bool = False,
    reset_callback=None,
) -> None:
    """Build and send the quests panel for a specified target player using shared /myquests logic."""

    state = await build_myquests_state_for_player(
        interaction,
        player_id=target_user_id,
        display_name=target_display_name,
        not_in_contest_message=f"❌ {target_display_name} is not part of the PPE contest.",
    )

    view = MyQuestsView(
        owner_id=owner_id,
        display_name=state["display_name"],
        home_embed=state["home_embed"],
        current_regular=state["current_regular"],
        current_shiny=state["current_shiny"],
        current_skin=state["current_skin"],
        current_all=state["current_all"],
        completed_embed=state["completed_embed"],
        global_mode_enabled=state["global_mode_enabled"],
        reset_callback=reset_callback,
    )

    await send_interaction_message(interaction, embed=state["home_embed"], view=view, ephemeral=ephemeral)
