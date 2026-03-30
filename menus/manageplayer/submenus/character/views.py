"""Character management views for the /manageplayer admin menu."""

from __future__ import annotations

import discord

from dataclass import PPEData, PlayerData
from menus.menu_utils.character_carousel import CharacterCarouselPolicy
from menus.manageplayer.common import (
    character_embed_for_target,
    close_manageplayer_menu,
    penalty_input_defaults,
    realmshark_connected_ppe_ids,
    send_followup_text,
    send_target_loot_markdown_followup,
)
from menus.manageplayer.entry import open_manageplayer_home
from menus.manageplayer.services import delete_single_ppe_for_target, find_ppe_or_raise, load_target_player_data
from menus.manageplayer.targets import ManagedPlayerTarget
from menus.menu_utils import OwnerBoundView
from utils.guild_config import load_guild_config
from utils.helpers.shareloot_image import generate_loot_share_image, variant_image_label
from utils.penalty_embed import build_penalty_infographic_embed
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.points_service import apply_penalties_to_ppe, parse_penalty_inputs, recompute_ppe_points


class ManagePlayerPenaltiesModal(discord.ui.Modal, title="Set PPE Penalties"):
    """Modal form for admin to edit a player's PPE penalties."""

    pet_level = discord.ui.TextInput(label="Pet Level (0-100)", required=True, max_length=3)
    num_exalts = discord.ui.TextInput(label="Exalts (0-40)", required=True, max_length=3)
    percent_loot = discord.ui.TextInput(label="Loot Boost % (0-25)", required=True, max_length=5)
    incombat_reduction = discord.ui.TextInput(
        label="In-Combat Reduction (0/0.2/0.4/0.6/0.8/1.0)",
        placeholder="Enter one of: 0, 0.2, 0.4, 0.6, 0.8, 1.0",
        required=True,
        max_length=3,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        target: ManagedPlayerTarget,
        ppe_id: int,
        defaults: dict[str, float],
        max_ppes: int,
        source_message: discord.Message | None,
        connected_ppe_ids: set[int],
    ) -> None:
        super().__init__()
        self.owner_id = owner_id
        self.target = target
        self.ppe_id = ppe_id
        self.max_ppes = max_ppes
        self.source_message = source_message
        self.connected_ppe_ids = connected_ppe_ids
        self.pet_level.default = str(int(defaults["pet_level"]))
        self.num_exalts.default = str(int(defaults["num_exalts"]))
        self.percent_loot.default = f"{float(defaults['percent_loot']):g}"
        self.incombat_reduction.default = f"{float(defaults['incombat_reduction']):g}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        parsed_inputs, error = parse_penalty_inputs(
            self.pet_level.value,
            self.num_exalts.value,
            self.percent_loot.value,
            self.incombat_reduction.value,
        )
        if error:
            await interaction.response.send_message(error, ephemeral=False)
            return

        assert parsed_inputs is not None

        records = await load_player_records(interaction)
        key = ensure_player_exists(records, self.target.user_id)
        player_data = records[key]
        ppe = find_ppe_or_raise(player_data, self.ppe_id)

        guild_config = await load_guild_config(interaction)

        penalty_result = apply_penalties_to_ppe(
            ppe,
            pet_level=int(parsed_inputs["pet_level"]),
            num_exalts=int(parsed_inputs["num_exalts"]),
            percent_loot=float(parsed_inputs["percent_loot"]),
            incombat_reduction=float(parsed_inputs["incombat_reduction"]),
            guild_config=guild_config,
        )
        points_breakdown = recompute_ppe_points(ppe, guild_config)
        await save_player_records(interaction=interaction, records=records)

        components = penalty_result["components"]
        embed = build_penalty_infographic_embed(
            pet_level=int(parsed_inputs["pet_level"]),
            num_exalts=int(parsed_inputs["num_exalts"]),
            percent_loot=float(parsed_inputs["percent_loot"]),
            incombat_reduction=float(parsed_inputs["incombat_reduction"]),
            pet_penalty=components["Pet Level Penalty"],
            exalt_penalty=components["Exalts Penalty"],
            loot_penalty=components["Loot Boost Penalty"],
            incombat_penalty=components["In-Combat Reduction Penalty"],
            total_points=points_breakdown["total"],
        )

        from menus.manageplayer.common import display_class_name, format_points

        await interaction.response.send_message(
            f"✅ Updated penalties for PPE #{ppe.id} ({display_class_name(ppe)}). "
            f"New total: {format_points(points_breakdown['total'])} points.",
            embed=embed,
            ephemeral=False,
        )

        if self.source_message is not None:
            refreshed = await load_target_player_data(interaction, self.target.user_id)
            guild_config = await load_guild_config(interaction)
            connected_ids = await realmshark_connected_ppe_ids(interaction, self.target.user_id)
            refreshed_view = ManagePlayerCharactersView(
                owner_id=self.owner_id,
                target=self.target,
                max_ppes=self.max_ppes,
                player_data=refreshed,
                connected_ppe_ids=connected_ids,
                guild_config=guild_config,
                preferred_ppe_id=self.ppe_id,
            )
            try:
                await self.source_message.edit(embed=refreshed_view.current_embed(), view=refreshed_view)
            except discord.HTTPException:
                pass


class ManagePlayerCharactersView(OwnerBoundView):
    """Carousel-style character management view for admin to manage a player's PPEs."""

    def __init__(
        self,
        *,
        owner_id: int,
        target: ManagedPlayerTarget,
        max_ppes: int,
        player_data: PlayerData,
        connected_ppe_ids: set[int],
        guild_config: dict | None = None,
        preferred_ppe_id: int | None = None,
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.target = target
        self.max_ppes = max_ppes
        self.player_data = player_data
        self.connected_ppe_ids = connected_ppe_ids
        self.guild_config = guild_config
        self.ppes = sorted(player_data.ppes, key=lambda p: int(p.id))
        best = max(self.ppes, key=lambda p: float(p.points), default=None)
        self.best_ppe_id = int(best.id) if best else None
        self.carousel_policy = CharacterCarouselPolicy(
            preferred_ppe_id=preferred_ppe_id,
            active_ppe_id=self.player_data.active_ppe,
        )
        self.index = self.carousel_policy.initial_index(self.ppes)

    def _initial_index(self, preferred_ppe_id: int | None) -> int:
        return self.carousel_policy.initial_index(self.ppes)

    def current_ppe(self) -> PPEData:
        return self.ppes[self.index]

    def current_embed(self) -> discord.Embed:
        ppe = self.current_ppe()
        return character_embed_for_target(
            target=self.target,
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
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Next Char", style=discord.ButtonStyle.secondary, row=0)
    async def next(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = self.carousel_policy.next_index(self.index, total=len(self.ppes), step=1)
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Home", style=discord.ButtonStyle.secondary, row=0)
    async def home(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await open_manageplayer_home(interaction, owner_id=interaction.user.id, target=self.target, max_ppes=self.max_ppes)

    @discord.ui.button(label="Show Loot", style=discord.ButtonStyle.primary, row=0)
    async def show_loot(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        selected = self.current_ppe()
        view = ManagePlayerCharacterLootView(
            owner_id=interaction.user.id,
            target=self.target,
            ppe_id=int(selected.id),
            preferred_ppe_id=int(selected.id),
        )
        await interaction.response.edit_message(embed=view.current_embed(selected), view=view)

    @discord.ui.button(label="Set As Active", style=discord.ButtonStyle.success, row=1)
    async def set_as_active(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        selected = self.current_ppe()
        records = await load_player_records(interaction)
        key = ensure_player_exists(records, self.target.user_id)
        records[key].active_ppe = int(selected.id)
        await save_player_records(interaction, records)

        self.player_data.active_ppe = int(selected.id)
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Manage PPE", style=discord.ButtonStyle.success, row=1)
    async def modify_ppe(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        selected = self.current_ppe()
        defaults = penalty_input_defaults(selected, self.guild_config)
        modal = ManagePlayerPenaltiesModal(
            owner_id=interaction.user.id,
            target=self.target,
            ppe_id=int(selected.id),
            defaults=defaults,
            max_ppes=self.max_ppes,
            source_message=interaction.message,
            connected_ppe_ids=self.connected_ppe_ids,
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Delete PPE", style=discord.ButtonStyle.danger, row=1)
    async def delete_ppe(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        selected = self.current_ppe()
        confirm_view = ManagePlayerDeletePpeConfirmView(
            owner_id=interaction.user.id,
            target=self.target,
            ppe_id=int(selected.id),
            max_ppes=self.max_ppes,
        )
        await interaction.response.edit_message(embed=confirm_view.current_embed(), view=confirm_view)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=2)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_manageplayer_menu(interaction)


class ManagePlayerCharacterLootView(OwnerBoundView):
    """Variant picker view for admin to share a player's loot."""

    def __init__(self, *, owner_id: int, target: ManagedPlayerTarget, ppe_id: int, preferred_ppe_id: int):
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.target = target
        self.ppe_id = ppe_id
        self.preferred_ppe_id = preferred_ppe_id

    def current_embed(self, ppe: PPEData) -> discord.Embed:
        from menus.manageplayer.common import display_class_name, format_points

        embed = discord.Embed(
            title=f"Show Loot for PPE #{ppe.id}",
            description="Choose an action.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Character", value=f"{display_class_name(ppe)}", inline=True)
        embed.add_field(name="Points", value=f"{format_points(ppe.points)}", inline=True)
        return embed

    async def _share(self, interaction: discord.Interaction, *, include_skins: bool, include_limited: bool) -> None:
        from menus.manageplayer.common import display_class_name, format_points

        refreshed = await load_target_player_data(interaction, self.target.user_id)
        selected = find_ppe_or_raise(refreshed, self.ppe_id)
        source_items = [(loot_item.item_name, bool(loot_item.shiny)) for loot_item in selected.loot]

        await generate_loot_share_image(
            interaction,
            source_items=source_items,
            include_skins=include_skins,
            include_limited=include_limited,
            filename_suffix=f"target_{self.target.user_id}_ppe{selected.id}_loot",
            embed_title="🎒 PPE Loot Share",
            embed_color=0x00FF00,
            embed_description=(
                f"**{self.target.display_name}'s** {display_class_name(selected)} PPE #{selected.id}"
            ),
            total_items_label="Total Loot",
            all_variant_extra_lines=[f"**Points:** {format_points(selected.points)}"],
        )

        await interaction.followup.send(
            f"Generated: **{variant_image_label(include_skins, include_limited)}**",
            ephemeral=False,
        )

    async def _close_and_share(
        self,
        interaction: discord.Interaction,
        *,
        include_skins: bool,
        include_limited: bool,
    ) -> None:
        await close_manageplayer_menu(interaction)
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
    async def show_list(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_manageplayer_menu(interaction)
        refreshed = await load_target_player_data(interaction, self.target.user_id)
        selected = find_ppe_or_raise(refreshed, self.ppe_id)
        await send_target_loot_markdown_followup(interaction, ppe=selected)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=2)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_manageplayer_menu(interaction)


class ManagePlayerDeletePpeConfirmView(OwnerBoundView):
    """Confirmation menu shown before deleting a specific PPE."""

    def __init__(self, *, owner_id: int, target: ManagedPlayerTarget, ppe_id: int, max_ppes: int) -> None:
        super().__init__(owner_id=owner_id, timeout=120, owner_error="This confirmation belongs to another user.")
        self.target = target
        self.ppe_id = ppe_id
        self.max_ppes = max_ppes

    def current_embed(self) -> discord.Embed:
        return discord.Embed(
            title="Delete PPE",
            description=f"Are you sure you want to delete **PPE #{self.ppe_id}** for **{self.target.display_name}**?",
            color=discord.Color.orange(),
        )

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, row=0)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            result = await delete_single_ppe_for_target(interaction, self.target, self.ppe_id)
            await interaction.response.defer()
            await send_followup_text(interaction, result, ephemeral=False)
            await close_manageplayer_menu(interaction)
        except Exception as e:
            await send_followup_text(interaction, str(e), ephemeral=False)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=0)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        refreshed = await load_target_player_data(interaction, self.target.user_id)
        guild_config = await load_guild_config(interaction)
        connected_ids = await realmshark_connected_ppe_ids(interaction, self.target.user_id)
        view = ManagePlayerCharactersView(
            owner_id=interaction.user.id,
            target=self.target,
            max_ppes=self.max_ppes,
            player_data=refreshed,
            connected_ppe_ids=connected_ids,
            guild_config=guild_config,
            preferred_ppe_id=self.ppe_id,
        )
        await interaction.response.edit_message(embed=view.current_embed(), view=view)
