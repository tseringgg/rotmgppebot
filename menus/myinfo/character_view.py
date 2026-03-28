"""Character-focused /myinfo views for PPE browsing, loot sharing, and penalty edits."""

from __future__ import annotations

import discord

from dataclass import PPEData, PlayerData
from menus.menu_utils import OwnerBoundView
from menus.myinfo.common import (
    build_character_embed,
    close_myinfo_menu,
    display_class_name,
    find_ppe_or_raise,
    format_points,
    open_myinfo_home,
    penalty_input_defaults,
    refresh_player_data,
    send_myloot_markdown_followup,
    temporarily_switch_active_ppe_and_share,
)
from utils.guild_config import get_max_ppes, load_guild_config
from utils.helpers.shareloot_image import variant_image_label
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.points_service import apply_penalties_to_ppe, recompute_ppe_points, validate_penalty_inputs


class ManagePPEPenaltiesModal(discord.ui.Modal, title="Manage PPE Penalties"):
    """Modal form used by the myinfo character view to edit penalty inputs."""

    pet_level = discord.ui.TextInput(label="Pet Level (0-100)", required=True, max_length=3)
    num_exalts = discord.ui.TextInput(label="Exalts (0-40)", required=True, max_length=3)
    percent_loot = discord.ui.TextInput(label="Loot Boost % (0-25)", required=True, max_length=5)
    incombat_reduction = discord.ui.TextInput(
        label="In-Combat Reduction",
        placeholder="0, 0.2, 0.4, 0.6, 0.8, or 1.0",
        required=True,
        max_length=3,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        ppe_id: int,
        defaults: dict[str, float],
        source_message: discord.Message | None,
        connected_ppe_ids: set[int],
    ) -> None:
        super().__init__()
        self.owner_id = owner_id
        self.ppe_id = ppe_id
        self.source_message = source_message
        self.connected_ppe_ids = connected_ppe_ids
        self.pet_level.default = str(int(defaults["pet_level"]))
        self.num_exalts.default = str(int(defaults["num_exalts"]))
        self.percent_loot.default = f"{float(defaults['percent_loot']):g}"
        self.incombat_reduction.default = f"{float(defaults['incombat_reduction']):g}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Validate modal values, persist penalties, and refresh the open character panel."""

        try:
            pet_level = int(str(self.pet_level.value).strip())
            num_exalts = int(str(self.num_exalts.value).strip())
            percent_loot = float(str(self.percent_loot.value).strip())
            incombat_reduction = float(str(self.incombat_reduction.value).strip())
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid values. Use numbers for all fields.",
                ephemeral=True,
            )
            return

        error = validate_penalty_inputs(pet_level, num_exalts, percent_loot, incombat_reduction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        # Re-load records at submit time to avoid writing stale menu state.
        records = await load_player_records(interaction)
        key = ensure_player_exists(records, self.owner_id)
        player_data = records[key]
        ppe = find_ppe_or_raise(player_data, self.ppe_id)

        apply_penalties_to_ppe(
            ppe,
            pet_level=pet_level,
            num_exalts=num_exalts,
            percent_loot=percent_loot,
            incombat_reduction=incombat_reduction,
        )
        guild_config = await load_guild_config(interaction)
        recompute_ppe_points(ppe, guild_config)
        await save_player_records(interaction=interaction, records=records)

        await interaction.response.send_message(
            f"✅ Updated penalties for PPE #{ppe.id} ({display_class_name(ppe)}). "
            f"New total: **{format_points(ppe.points)}** points.",
            ephemeral=True,
        )

        # Refresh the character panel message so penalty stats and points are immediately visible.
        if self.source_message is not None:
            refreshed = await refresh_player_data(interaction, self.owner_id)
            refreshed_view = ManageCharactersView(
                owner_id=self.owner_id,
                player_data=refreshed,
                connected_ppe_ids=self.connected_ppe_ids,
                preferred_ppe_id=self.ppe_id,
            )
            try:
                await self.source_message.edit(embed=refreshed_view.current_embed(interaction.user), view=refreshed_view)
            except discord.HTTPException:
                pass


class ManageCharactersView(OwnerBoundView):
    """Carousel-style character management view for navigating a player's PPE list."""

    def __init__(
        self,
        *,
        owner_id: int,
        player_data: PlayerData,
        connected_ppe_ids: set[int],
        preferred_ppe_id: int | None = None,
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.player_data = player_data
        self.connected_ppe_ids = connected_ppe_ids
        self.ppes = sorted(player_data.ppes, key=lambda p: int(p.id))
        best = max(self.ppes, key=lambda p: float(p.points), default=None)
        self.best_ppe_id = int(best.id) if best else None
        self.index = self._initial_index(preferred_ppe_id)

    def _initial_index(self, preferred_ppe_id: int | None) -> int:
        """Select starting carousel index using preferred ID or active PPE."""

        target_id = preferred_ppe_id if preferred_ppe_id is not None else self.player_data.active_ppe
        for idx, ppe in enumerate(self.ppes):
            if int(ppe.id) == int(target_id or -1):
                return idx
        return 0

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
        )

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary, row=0)
    async def prev(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = (self.index - 1) % len(self.ppes)
        await interaction.response.edit_message(embed=self.current_embed(interaction.user), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, row=0)
    async def next(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = (self.index + 1) % len(self.ppes)
        await interaction.response.edit_message(embed=self.current_embed(interaction.user), view=self)

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

    @discord.ui.button(label="Manage PPE", style=discord.ButtonStyle.secondary, row=1)
    async def modify_ppe(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        """Open a penalty form for the selected PPE and prefill current values."""

        selected = self.current_ppe()
        defaults = penalty_input_defaults(selected)
        modal = ManagePPEPenaltiesModal(
            owner_id=interaction.user.id,
            ppe_id=int(selected.id),
            defaults=defaults,
            source_message=interaction.message,
            connected_ppe_ids=self.connected_ppe_ids,
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Home", style=discord.ButtonStyle.secondary, row=1)
    async def home(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        max_ppes = await get_max_ppes(interaction)
        await open_myinfo_home(interaction, max_ppes=max_ppes)

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

    @discord.ui.button(label="Generate Image: Normal Only", style=discord.ButtonStyle.primary, row=0)
    async def normal_only(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._close_and_share(interaction, include_skins=False, include_limited=False)

    @discord.ui.button(label="Generate Image: Normal + Limited", style=discord.ButtonStyle.primary, row=0)
    async def normal_limited(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._close_and_share(interaction, include_skins=False, include_limited=True)

    @discord.ui.button(label="Generate Image: Normal + Skins", style=discord.ButtonStyle.primary, row=1)
    async def normal_skins(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._close_and_share(interaction, include_skins=True, include_limited=False)

    @discord.ui.button(label="Generate Image: All Loot", style=discord.ButtonStyle.success, row=1)
    async def all_loot(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._close_and_share(interaction, include_skins=True, include_limited=True)

    @discord.ui.button(label="List Loot", style=discord.ButtonStyle.secondary, row=2)
    async def list_loot(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_myinfo_menu(interaction)
        refreshed = await refresh_player_data(interaction, interaction.user.id)
        selected = find_ppe_or_raise(refreshed, self.ppe_id)
        await send_myloot_markdown_followup(interaction, selected)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=2)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_myinfo_menu(interaction)
