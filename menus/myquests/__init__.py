from __future__ import annotations

import discord

from menus.myquests.common import build_myquests_state, send_interaction_message
from menus.myquests.view import MyQuestsView


async def open_myquests_menu(interaction: discord.Interaction, *, ephemeral: bool = False) -> None:
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
    )

    await send_interaction_message(interaction, embed=state["home_embed"], view=view, ephemeral=ephemeral)


__all__ = ["open_myquests_menu", "MyQuestsView"]
