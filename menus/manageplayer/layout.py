"""Layout policies for /manageplayer views."""

from __future__ import annotations

import discord


def reorder_manageplayer_home_rows(
    *,
    children: list[discord.ui.Item],
    team_action_button: discord.ui.Item | None,
    reset_quests_button: discord.ui.Item,
    delete_all_ppes_button: discord.ui.Item,
    remove_admin_button: discord.ui.Item,
    remove_from_contest_button: discord.ui.Item,
    cancel_button: discord.ui.Item,
    remove_item,
    add_item,
) -> None:
    """Keep destructive actions grouped and preserve stable row ordering."""

    row_two_buttons: list[discord.ui.Item] = []
    row_three_buttons: list[discord.ui.Item] = []

    if team_action_button is not None and team_action_button in children and getattr(team_action_button, "label", "") == "Remove From Team":
        row_two_buttons.append(team_action_button)

    for candidate in (reset_quests_button, delete_all_ppes_button):
        if candidate in children:
            row_two_buttons.append(candidate)

    for candidate in (remove_admin_button, remove_from_contest_button, cancel_button):
        if candidate in children:
            row_three_buttons.append(candidate)

    if not row_two_buttons and not row_three_buttons:
        return

    for button in row_two_buttons + row_three_buttons:
        if button in children:
            remove_item(button)

    for button in row_two_buttons:
        button.row = 2
        add_item(button)

    for button in row_three_buttons:
        button.row = 3
        add_item(button)
