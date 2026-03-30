"""Player reset submenu views and modals for /managequests."""

from __future__ import annotations

import re

import discord

from menus.managequests.common import load_managequests_settings
from menus.managequests.reset_actions import open_reset_for_member
from menus.menu_utils import OwnerBoundView
from menus.myquests.common import build_myquests_state_for_player
from menus.myquests.views import MyQuestsView


class ManagePlayerQuestsPromptModal(discord.ui.Modal, title="Manage Player's Quests"):
    """Modal to prompt for a player name before showing management options."""

    player_name = discord.ui.TextInput(
        label="Player Name",
        placeholder="Discord display name, username, mention, or ID",
        max_length=100,
    )

    def __init__(self, *, owner_id: int, source_message: discord.Message | None) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        if not interaction.guild:
            await interaction.response.send_message("❌ This action can only be used in a server.", ephemeral=True)
            return

        raw = str(self.player_name.value).strip()
        target = self._resolve_member(interaction.guild, raw)
        if target is None:
            await interaction.response.send_message(
                "❌ Player not found. Use exact display name/username, mention, or user ID.",
                ephemeral=True,
            )
            return

        view = ManagePlayerQuestsView(owner_id=self.owner_id, member=target)
        await interaction.response.send_message(embed=view.current_embed(), view=view, ephemeral=True)

    @staticmethod
    def _resolve_member(guild: discord.Guild, raw_value: str) -> discord.Member | None:
        if not raw_value:
            return None

        mention_match = re.fullmatch(r"<@!?(\d+)>", raw_value)
        if mention_match:
            member = guild.get_member(int(mention_match.group(1)))
            if member is not None:
                return member

        if raw_value.isdigit():
            member = guild.get_member(int(raw_value))
            if member is not None:
                return member

        lowered = raw_value.casefold()
        for member in guild.members:
            if member.display_name.casefold() == lowered or member.name.casefold() == lowered:
                return member
        return None


class ManagePlayerQuestsView(OwnerBoundView):
    """Targeted quest management actions for a specific player from /managequests."""

    def __init__(self, *, owner_id: int, member: discord.Member) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.member = member

    def current_embed(self) -> discord.Embed:
        return discord.Embed(
            title=f"Manage Player Quests - {self.member.display_name}",
            description=(
                "Use **Reset Quests** to run the admin reset flow for this player, "
                "or **Show Quests** to open their quest panel."
            ),
            color=discord.Color.dark_teal(),
        )

    @discord.ui.button(label="Reset Quests", style=discord.ButtonStyle.danger, row=0)
    async def reset_quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await open_reset_for_member(interaction, self.member, actor_id=self.owner_id)

    @discord.ui.button(label="Show Quests", style=discord.ButtonStyle.primary, row=0)
    async def show_quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        async def _show_target_reset_for_member(reset_interaction: discord.Interaction) -> None:
            await open_reset_for_member(reset_interaction, self.member, actor_id=self.owner_id)

        state = await build_myquests_state_for_player(
            interaction,
            player_id=self.member.id,
            display_name=self.member.display_name,
            not_in_contest_message=f"❌ {self.member.display_name} is not part of the PPE contest.",
        )
        view = MyQuestsView(
            owner_id=interaction.user.id,
            display_name=state["display_name"],
            home_embed=state["home_embed"],
            current_regular=state["current_regular"],
            current_shiny=state["current_shiny"],
            current_skin=state["current_skin"],
            current_all=state["current_all"],
            completed_embed=state["completed_embed"],
            global_mode_enabled=state["global_mode_enabled"],
            reset_callback=_show_target_reset_for_member,
        )
        await interaction.response.edit_message(embed=state["home_embed"], view=view, attachments=[])

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.managequests.submenus.home.views import ManageQuestsHomeView

        settings = await load_managequests_settings(interaction)
        view = ManageQuestsHomeView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary, row=1)
    async def close(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/managequests` menu.", embed=None, view=None)


__all__ = ["ManagePlayerQuestsPromptModal", "ManagePlayerQuestsView"]
