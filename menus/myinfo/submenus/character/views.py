"""Character submenu views for /myinfo."""

from __future__ import annotations

import traceback
import time

import discord

from dataclass import PPEData, PlayerData
from menus.menu_utils.character_carousel import CharacterCarouselPolicy
from menus.menu_utils import OwnerBoundView
from menus.myinfo.common import (
    build_character_embed,
    close_myinfo_menu,
    display_class_name,
    duo_link_id_for_ppe,
    duo_partner_details_for_ppe,
    duo_partner_id_from_options,
    find_ppe_or_raise,
    format_points,
    penalty_input_defaults,
    ppe_type_text,
    refresh_player_data,
    send_myloot_markdown_followup,
    temporarily_switch_active_ppe_and_share,
)
from menus.myinfo.entry import open_myinfo_home
from menus.myinfo.submenus.character.modals import ManageCharacterDuoPartnerModal, ManagePPEPenaltiesModal, launch_new_ppe_modal_flow
from utils.bot_cost_tracking import capture_runtime_snapshot, log_cost_event
from utils.guild_config import get_max_ppes, load_guild_config
from utils.ppe_types import is_duo_ppe_type, normalize_ppe_type
from utils.loot_helpers.shareloot_image import variant_image_label
from utils.player_statistics import build_character_wrapped_embed
from utils.time_graphs import build_character_point_graph
from utils.player_records import ensure_player_exists, load_player_records, save_player_records


class ManageCharactersView(OwnerBoundView):
    """Carousel-style character management view for navigating a player's PPE list."""

    def __init__(
        self,
        *,
        owner_id: int,
        player_data: PlayerData,
        connected_ppe_ids: set[int],
        all_player_records: dict[int, PlayerData] | None = None,
        preferred_ppe_id: int | None = None,
        guild_config: dict | None = None,
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.player_data = player_data
        self.connected_ppe_ids = connected_ppe_ids
        self.all_player_records = all_player_records
        self.ppes = sorted(player_data.ppes, key=lambda p: int(p.id))
        self.guild_config = guild_config
        best = max(self.ppes, key=lambda p: float(p.points), default=None)
        self.best_ppe_id = int(best.id) if best else None
        self.carousel_policy = CharacterCarouselPolicy(
            preferred_ppe_id=preferred_ppe_id,
            active_ppe_id=self.player_data.active_ppe,
        )
        self.index = self.carousel_policy.initial_index(self.ppes)
        self._update_duo_button_visibility()

    def _initial_index(self, preferred_ppe_id: int | None) -> int:
        """Select starting carousel index using preferred ID or active PPE."""
        return self.carousel_policy.initial_index(self.ppes)

    def current_ppe(self) -> PPEData:
        return self.ppes[self.index]

    def _update_duo_button_visibility(self) -> None:
        """Update duo-related button visibility based on current PPE."""
        ppe = self.current_ppe()
        ppe_type_options = getattr(ppe, "ppe_type_options", None)
        is_duo_type = is_duo_ppe_type(normalize_ppe_type(getattr(ppe, "ppe_type", None)))
        has_duo_flag = bool(ppe_type_options.get("duo_enabled", False)) if isinstance(ppe_type_options, dict) else False
        is_duo = is_duo_type or has_duo_flag
        has_partner = duo_partner_id_from_options(ppe_type_options) is not None

        # Remove existing duo buttons if they exist
        for item in list(self.children):
            if hasattr(item, 'label') and item.label in ("Duos Stats", "Set Duo Partner"):
                self.remove_item(item)

        # Add buttons based on conditions
        if is_duo:
            # Add "Duos Stats" button only if partner is configured
            if has_partner:
                duos_stats_btn = _DuosStatsButton()
                self.add_item(duos_stats_btn)

            # Add "Set Duo Partner" button only if partner is NOT configured
            if not has_partner:
                set_duo_btn = _SetDuoPartnerButton()
                self.add_item(set_duo_btn)

    def current_embed(self, user: discord.abc.User, guild: discord.Guild | None = None) -> discord.Embed:
        ppe = self.current_ppe()
        duo_partner_details = duo_partner_details_for_ppe(
            ppe,
            owner_user_id=self.owner_id,
            records=self.all_player_records,
            guild=guild,
            guild_config=self.guild_config,
        )
        return build_character_embed(
            user=user,
            player_data=self.player_data,
            ppe=ppe,
            index=self.index + 1,
            total=len(self.ppes),
            is_active=(self.player_data.active_ppe == ppe.id),
            is_best=(self.best_ppe_id is not None and int(ppe.id) == self.best_ppe_id),
            is_realmshark_connected=(int(ppe.id) in self.connected_ppe_ids),
            duo_partner_details=duo_partner_details,
            guild_config=self.guild_config,
            guild=guild,
        )

    @discord.ui.button(label="Prev Char", style=discord.ButtonStyle.secondary, row=0)
    async def prev(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = self.carousel_policy.next_index(self.index, total=len(self.ppes), step=-1)
        self._update_duo_button_visibility()
        await interaction.response.edit_message(embed=self.current_embed(interaction.user, interaction.guild), view=self)

    @discord.ui.button(label="Next Char", style=discord.ButtonStyle.secondary, row=0)
    async def next(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = self.carousel_policy.next_index(self.index, total=len(self.ppes), step=1)
        self._update_duo_button_visibility()
        await interaction.response.edit_message(embed=self.current_embed(interaction.user, interaction.guild), view=self)

    @discord.ui.button(label="Home", style=discord.ButtonStyle.secondary, row=0)
    async def home(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        max_ppes = await get_max_ppes(interaction)
        await open_myinfo_home(interaction, max_ppes=max_ppes)

    @discord.ui.button(label="Statistics", style=discord.ButtonStyle.primary, row=0)
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
        await interaction.response.edit_message(embed=self.current_embed(interaction.user, interaction.guild), view=self)

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
        await launch_new_ppe_modal_flow(
            interaction,
            owner_id=interaction.user.id,
            source_message=interaction.message,
            connected_ppe_ids=self.connected_ppe_ids,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/myinfo` menu.", embed=None, view=None)


class CharacterLootVariantView(OwnerBoundView):
    """Variant picker view for sharing a PPE's loot image or text exports."""

    def __init__(
        self,
        *,
        owner_id: int,
        ppe_id: int,
        preferred_ppe_id: int,
        target_user_id: int | None = None,
        target_display_name: str | None = None,
    ):
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.ppe_id = ppe_id
        self.preferred_ppe_id = preferred_ppe_id
        self.target_user_id = int(target_user_id) if target_user_id is not None else int(owner_id)
        self.target_display_name = target_display_name

    def current_embed(self, ppe: PPEData) -> discord.Embed:
        embed = discord.Embed(
            title=f"Statistics for PPE #{ppe.id}",
            description="Choose an action.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Character", value=f"{display_class_name(ppe)}", inline=True)
        embed.add_field(name="Type", value=ppe_type_text(ppe, compact=True), inline=True)
        embed.add_field(name="Points", value=f"{format_points(ppe.points)}", inline=True)
        return embed

    async def _share(self, interaction: discord.Interaction, *, include_skins: bool, include_limited: bool) -> None:
        started_monotonic = time.monotonic()
        snapshot_before = capture_runtime_snapshot()
        await temporarily_switch_active_ppe_and_share(
            interaction,
            self.ppe_id,
            include_skins=include_skins,
            include_limited=include_limited,
            target_user_id=self.target_user_id,
            target_display_name=self.target_display_name,
        )
        await interaction.followup.send(
            f"Generated: **{variant_image_label(include_skins, include_limited)}**",
            ephemeral=True,
        )

        variant_name = "character loot image"
        if include_skins and include_limited:
            variant_name = "character loot image (all loot)"
        elif include_skins:
            variant_name = "character loot image (normal + skins)"
        elif include_limited:
            variant_name = "character loot image (normal + limited)"
        else:
            variant_name = "character loot image (normal only)"

        await log_cost_event(
            interaction,
            command_name=f"/myinfo show image {variant_name}",
            started_monotonic=started_monotonic,
            snapshot_before=snapshot_before,
            source="menu_action",
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
        started_monotonic = time.monotonic()
        snapshot_before = capture_runtime_snapshot()
        await close_myinfo_menu(interaction)
        refreshed = await refresh_player_data(interaction, self.target_user_id)
        selected = find_ppe_or_raise(refreshed, self.ppe_id)
        await send_myloot_markdown_followup(interaction, selected)
        await log_cost_event(
            interaction,
            command_name="/myinfo list loot",
            started_monotonic=started_monotonic,
            snapshot_before=snapshot_before,
            source="menu_action",
        )

    @discord.ui.button(label="Show Character Statistics", style=discord.ButtonStyle.success, row=2)
    async def show_character_statistics(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        started_monotonic = time.monotonic()
        snapshot_before = capture_runtime_snapshot()
        refreshed = await refresh_player_data(interaction, self.target_user_id)
        selected = find_ppe_or_raise(refreshed, self.ppe_id)
        guild_config = await load_guild_config(interaction)
        embed = build_character_wrapped_embed(
            player_data=refreshed,
            ppe=selected,
            display_name=self.target_display_name or interaction.user.display_name,
            guild_config=guild_config,
        )
        await close_myinfo_menu(interaction)
        await interaction.followup.send(embed=embed, ephemeral=False)
        await log_cost_event(
            interaction,
            command_name="/myinfo statistics (character)",
            started_monotonic=started_monotonic,
            snapshot_before=snapshot_before,
            source="menu_action",
        )

    @discord.ui.button(label="Point Graph", style=discord.ButtonStyle.success, row=2)
    async def point_graph(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        started_monotonic = time.monotonic()
        snapshot_before = capture_runtime_snapshot()
        refreshed = await refresh_player_data(interaction, self.target_user_id)
        selected = find_ppe_or_raise(refreshed, self.ppe_id)
        guild_config = await load_guild_config(interaction)
        graph_image = build_character_point_graph(
            selected,
            display_name=self.target_display_name or interaction.user.display_name,
            guild_config=guild_config,
        )
        if graph_image is None:
            await interaction.response.send_message(
                "No loot timestamps found for this character yet. Add loot first to generate a point graph.",
                ephemeral=True,
            )
            return

        await close_myinfo_menu(interaction)
        await interaction.followup.send(
            file=discord.File(graph_image, filename=f"ppe_{selected.id}_point_graph.png"),
            ephemeral=False,
        )
        await log_cost_event(
            interaction,
            command_name="/myinfo character point graph",
            started_monotonic=started_monotonic,
            snapshot_before=snapshot_before,
            source="menu_action",
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=3)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_myinfo_menu(interaction)


__all__ = ["CharacterLootVariantView", "ManageCharactersView"]


class _DuosStatsButton(discord.ui.Button):
    """Button to view duo partner's stats."""

    def __init__(self) -> None:
        super().__init__(label="Duos Stats", style=discord.ButtonStyle.primary, row=2)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManageCharactersView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        selected = view.current_ppe()
        partner_id = duo_partner_id_from_options(getattr(selected, "ppe_type_options", None))
        if partner_id is None:
            await interaction.response.send_message("This PPE is not part of a confirmed duo.", ephemeral=True)
            return

        records = await load_player_records(interaction)
        partner_data = records.get(int(partner_id))
        if partner_data is None:
            await interaction.response.send_message("Could not find your duo partner's player record.", ephemeral=True)
            return

        partner_link_id = duo_link_id_for_ppe(selected)
        partner_ppe = None
        for ppe in getattr(partner_data, "ppes", []):
            if duo_partner_id_from_options(getattr(ppe, "ppe_type_options", None)) != interaction.user.id:
                continue
            if partner_link_id and duo_link_id_for_ppe(ppe) != partner_link_id:
                continue
            partner_ppe = ppe
            break

        if partner_ppe is None:
            await interaction.response.send_message("Could not find the paired duo PPE for your partner.", ephemeral=True)
            return

        ppe_view = CharacterLootVariantView(
            owner_id=interaction.user.id,
            ppe_id=int(partner_ppe.id),
            preferred_ppe_id=int(partner_ppe.id),
            target_user_id=int(partner_id),
            target_display_name=(
                interaction.guild.get_member(int(partner_id)).display_name
                if interaction.guild is not None and interaction.guild.get_member(int(partner_id)) is not None
                else f"<@{partner_id}>"
            ),
        )
        await interaction.response.edit_message(embed=ppe_view.current_embed(partner_ppe), view=ppe_view)


class _SetDuoPartnerButton(discord.ui.Button):
    """Button to set a duo partner for a duo PPE without one configured."""

    def __init__(self) -> None:
        super().__init__(label="Set Duo Partner", style=discord.ButtonStyle.primary, row=2)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManageCharactersView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        selected = view.current_ppe()
        selected_type = normalize_ppe_type(getattr(selected, "ppe_type", None))
        selected_options = getattr(selected, "ppe_type_options", None)
        selected_has_duo_flag = bool(selected_options.get("duo_enabled", False)) if isinstance(selected_options, dict) else False
        if not is_duo_ppe_type(selected_type) and not selected_has_duo_flag:
            await interaction.response.send_message(
                "This character is not a Duo PPE type."
                " Use Manage PPE if you want to change its type first.",
                ephemeral=True,
            )
            return

        try:
            print(
                "[MYINFO_DUO] open modal "
                f"owner_id={interaction.user.id} ppe_id={int(selected.id)} "
                f"ppe_type={getattr(selected, 'ppe_type', None)!r} "
                f"partner_id={duo_partner_id_from_options(getattr(selected, 'ppe_type_options', None))!r} "
                f"link_id={duo_link_id_for_ppe(selected)!r}"
            )
            await interaction.response.send_modal(
                ManageCharacterDuoPartnerModal(
                    owner_id=interaction.user.id,
                    ppe_id=int(selected.id),
                    class_name=display_class_name(selected),
                    source_message=interaction.message,
                    connected_ppe_ids=view.connected_ppe_ids,
                )
            )
        except Exception:
            print("[MYINFO_DUO][ERROR] failed to open modal")
            print(traceback.format_exc())
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Failed to open the duo partner prompt. Check the Railway logs.",
                    ephemeral=True,
                )
