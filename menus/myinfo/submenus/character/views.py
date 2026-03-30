"""Character submenu views for /myinfo."""

from __future__ import annotations

import discord

from dataclass import PPEData, PlayerData
from menus.menu_utils.character_carousel import CharacterCarouselPolicy
from menus.menu_utils import OwnerBoundView
from menus.myinfo.common import (
    build_character_embed,
    close_myinfo_menu,
    display_class_name,
    find_ppe_or_raise,
    format_points,
    penalty_input_defaults,
    refresh_player_data,
    send_myloot_markdown_followup,
    temporarily_switch_active_ppe_and_share,
)
from menus.myinfo.entry import open_myinfo_home
from menus.myinfo.submenus.character.modals import ManagePPEPenaltiesModal, NewPPEFromMyInfoModal
from utils.guild_config import get_max_ppes, load_guild_config
from utils.helpers.shareloot_image import variant_image_label
from utils.player_records import ensure_player_exists, load_player_records, save_player_records


class ManageCharactersView(OwnerBoundView):
    """Carousel-style character management view for navigating a player's PPE list."""

    def __init__(
        self,
        *,
        owner_id: int,
        player_data: PlayerData,
        connected_ppe_ids: set[int],
        preferred_ppe_id: int | None = None,
        guild_config: dict | None = None,
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.player_data = player_data
        self.connected_ppe_ids = connected_ppe_ids
        self.ppes = sorted(player_data.ppes, key=lambda p: int(p.id))
        self.guild_config = guild_config
        best = max(self.ppes, key=lambda p: float(p.points), default=None)
        self.best_ppe_id = int(best.id) if best else None
        self.carousel_policy = CharacterCarouselPolicy(
            preferred_ppe_id=preferred_ppe_id,
            active_ppe_id=self.player_data.active_ppe,
        )
        self.index = self.carousel_policy.initial_index(self.ppes)

    def _initial_index(self, preferred_ppe_id: int | None) -> int:
        """Select starting carousel index using preferred ID or active PPE."""
        return self.carousel_policy.initial_index(self.ppes)

    def current_ppe(self) -> PPEData:
        return self.ppes[self.index]

    def current_embed(self, user: discord.abc.User) -> discord.Embed:
        ppe = self.current_ppe()
        return build_character_embed(
            user=user,
            player_data=self.player_data,
            ppe=ppe,
            index=self.index + 1,
            total=len(self.ppes),
            is_active=(self.player_data.active_ppe == ppe.id),
            is_best=(self.best_ppe_id is not None and int(ppe.id) == self.best_ppe_id),
            is_realmshark_connected=(int(ppe.id) in self.connected_ppe_ids),
            guild_config=self.guild_config,
        )

    @discord.ui.button(label="Prev Char", style=discord.ButtonStyle.secondary, row=0)
    async def prev(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = self.carousel_policy.next_index(self.index, total=len(self.ppes), step=-1)
        await interaction.response.edit_message(embed=self.current_embed(interaction.user), view=self)

    @discord.ui.button(label="Next Char", style=discord.ButtonStyle.secondary, row=0)
    async def next(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = self.carousel_policy.next_index(self.index, total=len(self.ppes), step=1)
        await interaction.response.edit_message(embed=self.current_embed(interaction.user), view=self)

    @discord.ui.button(label="Home", style=discord.ButtonStyle.secondary, row=0)
    async def home(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        max_ppes = await get_max_ppes(interaction)
        await open_myinfo_home(interaction, max_ppes=max_ppes)

    @discord.ui.button(label="Show Loot", style=discord.ButtonStyle.primary, row=0)
    async def show_loot(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        selected = self.current_ppe()
        view = CharacterLootVariantView(
            owner_id=interaction.user.id,
            ppe_id=int(selected.id),
            preferred_ppe_id=int(selected.id),
        )
        await interaction.response.edit_message(embed=view.current_embed(selected), view=view)

    @discord.ui.button(label="Set As Active", style=discord.ButtonStyle.success, row=1)
    async def set_as_active(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        selected = self.current_ppe()
        records = await load_player_records(interaction)
        key = ensure_player_exists(records, interaction.user.id)
        records[key].active_ppe = int(selected.id)
        await save_player_records(interaction, records)

        self.player_data.active_ppe = int(selected.id)
        await interaction.response.edit_message(embed=self.current_embed(interaction.user), view=self)

    @discord.ui.button(label="Manage PPE", style=discord.ButtonStyle.success, row=1)
    async def modify_ppe(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        """Open a penalty form for the selected PPE and prefill current values."""

        selected = self.current_ppe()
        defaults = penalty_input_defaults(selected, self.guild_config)
        modal = ManagePPEPenaltiesModal(
            owner_id=interaction.user.id,
            ppe_id=int(selected.id),
            defaults=defaults,
            source_message=interaction.message,
            connected_ppe_ids=self.connected_ppe_ids,
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="New PPE", style=discord.ButtonStyle.success, row=1)
    async def new_ppe(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        modal = NewPPEFromMyInfoModal(
            owner_id=interaction.user.id,
            source_message=interaction.message,
            connected_ppe_ids=self.connected_ppe_ids,
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/myinfo` menu.", embed=None, view=None)


class CharacterLootVariantView(OwnerBoundView):
    """Variant picker view for sharing a PPE's loot image or text exports."""

    def __init__(self, *, owner_id: int, ppe_id: int, preferred_ppe_id: int):
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.ppe_id = ppe_id
        self.preferred_ppe_id = preferred_ppe_id

    def current_embed(self, ppe: PPEData) -> discord.Embed:
        embed = discord.Embed(
            title=f"Show Loot for PPE #{ppe.id}",
            description="Choose an action.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Character", value=f"{display_class_name(ppe)}", inline=True)
        embed.add_field(name="Points", value=f"{format_points(ppe.points)}", inline=True)
        return embed

    async def _share(self, interaction: discord.Interaction, *, include_skins: bool, include_limited: bool) -> None:
        await temporarily_switch_active_ppe_and_share(
            interaction,
            self.ppe_id,
            include_skins=include_skins,
            include_limited=include_limited,
        )
        await interaction.followup.send(
            f"Generated: **{variant_image_label(include_skins, include_limited)}**",
            ephemeral=True,
        )

    async def _close_and_share(
        self,
        interaction: discord.Interaction,
        *,
        include_skins: bool,
        include_limited: bool,
    ) -> None:
        # Close the menu before generating output so this panel doesn't linger.
        await close_myinfo_menu(interaction)
        await self._share(interaction, include_skins=include_skins, include_limited=include_limited)

    @discord.ui.button(label="Show Image: Normal Only", style=discord.ButtonStyle.primary, row=0)
    async def normal_only(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._close_and_share(interaction, include_skins=False, include_limited=False)

    @discord.ui.button(label="Show Image: Normal + Limited", style=discord.ButtonStyle.primary, row=0)
    async def normal_limited(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._close_and_share(interaction, include_skins=False, include_limited=True)

    @discord.ui.button(label="Show Image: Normal + Skins", style=discord.ButtonStyle.primary, row=1)
    async def normal_skins(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._close_and_share(interaction, include_skins=True, include_limited=False)

    @discord.ui.button(label="Show Image: All Loot", style=discord.ButtonStyle.primary, row=1)
    async def all_loot(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._close_and_share(interaction, include_skins=True, include_limited=True)

    @discord.ui.button(label="List Loot", style=discord.ButtonStyle.primary, row=1)
    async def list_loot(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_myinfo_menu(interaction)
        refreshed = await refresh_player_data(interaction, interaction.user.id)
        selected = find_ppe_or_raise(refreshed, self.ppe_id)
        await send_myloot_markdown_followup(interaction, selected)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=2)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_myinfo_menu(interaction)


__all__ = ["CharacterLootVariantView", "ManageCharactersView"]
