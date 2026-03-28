from __future__ import annotations

from typing import Sequence

import discord

from menus.menu_utils import OwnerBoundView
from menus.myquests.common import board_file, build_category_embed
from slash_commands import resetquestfor_cmd


class MyQuestsView(OwnerBoundView):
    def __init__(
        self,
        *,
        owner_id: int,
        display_name: str,
        home_embed: discord.Embed,
        current_regular: Sequence[str],
        current_shiny: Sequence[str],
        current_skin: Sequence[str],
        current_all: Sequence[str],
        completed_embed: discord.Embed,
    ) -> None:
        super().__init__(
            owner_id=owner_id,
            timeout=600,
            owner_error="This panel belongs to another user.",
        )
        self.display_name = display_name
        self.home_embed = home_embed
        self.current_regular = list(current_regular)
        self.current_shiny = list(current_shiny)
        self.current_skin = list(current_skin)
        self.current_all = list(current_all)
        self.completed_embed = completed_embed

    async def _edit_with_board(
        self,
        interaction: discord.Interaction,
        *,
        embed_title: str,
        board_title_suffix: str,
        item_names: Sequence[str],
        attachment_name: str,
    ) -> None:
        img = board_file(item_names, f"{self.display_name}'s {board_title_suffix}", attachment_name)
        embed = build_category_embed(embed_title, item_names, attachment_name)
        await interaction.response.edit_message(embed=embed, attachments=[img], view=self)

    @discord.ui.button(label="Home", style=discord.ButtonStyle.secondary)
    async def home(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(embed=self.home_embed, attachments=[], view=self)

    @discord.ui.button(label="Regular", style=discord.ButtonStyle.primary)
    async def regular(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._edit_with_board(
            interaction,
            embed_title="Regular Quest Targets",
            board_title_suffix="Missing Regular Quests",
            item_names=self.current_regular,
            attachment_name="myquests_regular.png",
        )

    @discord.ui.button(label="Shiny", style=discord.ButtonStyle.primary)
    async def shiny(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._edit_with_board(
            interaction,
            embed_title="Shiny Quest Targets",
            board_title_suffix="Missing Shinies",
            item_names=self.current_shiny,
            attachment_name="myquests_shiny.png",
        )

    @discord.ui.button(label="Skins", style=discord.ButtonStyle.primary)
    async def skins(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._edit_with_board(
            interaction,
            embed_title="Skin Quest Targets",
            board_title_suffix="Missing Skins",
            item_names=self.current_skin,
            attachment_name="myquests_skins.png",
        )

    @discord.ui.button(label="Show All", style=discord.ButtonStyle.success)
    async def show_all(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._edit_with_board(
            interaction,
            embed_title="All Current Quest Targets",
            board_title_suffix="All Missing Quests",
            item_names=self.current_all,
            attachment_name="myquests_all.png",
        )

    @discord.ui.button(label="Completed", style=discord.ButtonStyle.success)
    async def completed(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(embed=self.completed_embed, attachments=[], view=self)

    @discord.ui.button(label="Reset Quests", style=discord.ButtonStyle.danger)
    async def reset_quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await resetquestfor_cmd.command_self(interaction)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary)
    async def close(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.stop()
        await interaction.response.edit_message(
            content="Quest panel closed.",
            embed=None,
            attachments=[],
            view=None,
        )
