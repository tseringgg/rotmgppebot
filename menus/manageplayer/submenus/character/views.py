"""Character management views for the /manageplayer admin menu."""

from __future__ import annotations

import time

import discord

from dataclass import PPEData, PlayerData
from menus.menu_utils.character_carousel import CharacterCarouselPolicy
from utils.ppe_types import (
    build_ppe_type_options,
    infer_legacy_ppe_type_from_options,
    is_duo_ppe_type,
    normalize_ppe_type,
    normalize_ppe_type_options,
    options_from_signature,
    ppe_type_option_signature,
    ppe_type_option_signature,
    ppe_type_short_label,
    resolve_edit_ppe_type,
)
from menus.manageplayer.common import (
    character_embed_for_target,
    close_manageplayer_menu,
    penalty_input_defaults,
    ppe_type_text,
    realmshark_connected_ppe_ids,
    send_followup_text,
    send_target_loot_markdown_followup,
)
from utils.ppe_display import format_ppe_label_from_options
from menus.manageplayer.entry import open_manageplayer_home
from menus.manageplayer.services import delete_single_ppe_for_target, find_ppe_or_raise, load_target_player_data
from menus.manageplayer.targets import ManagedPlayerTarget
from menus.menu_utils import OwnerBoundView
from utils.bot_cost_tracking import capture_runtime_snapshot, log_cost_event
from utils.guild_config import load_guild_config
from utils.group_ppes import clear_duo_partner
from utils.loot_helpers.shareloot_image import generate_loot_share_image, variant_image_label
from utils.player_statistics import build_character_wrapped_embed
from utils.penalty_embed import build_penalty_infographic_embed
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.points_service import apply_penalties_to_ppe, parse_penalty_inputs, recompute_ppe_points
from utils.role_checks import has_ppe_player_role
from utils.wizard_components import (
    MinimumRarityContinueButton,
    MinimumRaritySelect,
    build_minimum_rarity_handlers,
    enforce_shiny_rarity_prompt,
    get_minimum_rarity_options,
    requires_enforce_shiny_rarity_choice,
)


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
    ppe_type = discord.ui.TextInput(
        label="PPE Type",
        placeholder="Examples: PPE, Duo PPE, DPE, UPE, SPE, SLPE, UNPE",
        required=True,
        max_length=32,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        target: ManagedPlayerTarget,
        ppe_id: int,
        current_ppe_type: str,
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
        self.ppe_type.default = ppe_type_short_label(current_ppe_type)

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
        ppe_settings = guild_config.get("ppe_settings", {}) if isinstance(guild_config.get("ppe_settings", {}), dict) else {}
        resolved_type, type_error = resolve_edit_ppe_type(
            self.ppe_type.value,
            current_type=getattr(ppe, "ppe_type", None),
            enabled=bool(ppe_settings.get("enable_ppe_types", True)),
            allowed_types=ppe_settings.get("allowed_ppe_types", []),
        )
        if type_error:
            current_options = getattr(ppe, "ppe_type_options", {})
            duo_partner_id = current_options.get("duo_partner_id") if isinstance(current_options, dict) else None
            signature_options = options_from_signature(
                self.ppe_type.value,
                duo_partner_id=duo_partner_id,
            )
            if signature_options is None:
                await interaction.response.send_message(type_error, ephemeral=False)
                return
            ppe.ppe_type_options = signature_options
            ppe.ppe_type = infer_legacy_ppe_type_from_options(signature_options)
        else:
            ppe.ppe_type = resolved_type
            ppe.ppe_type_options = normalize_ppe_type_options(None, current_type=resolved_type)

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
            guild_config=guild_config,
        )

        from menus.manageplayer.common import display_class_name, format_points

        await interaction.response.send_message(
                f"✅ Updated PPE #{ppe.id} ({display_class_name(ppe)}, {ppe_type_text(ppe, compact=True)}). "
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

    @discord.ui.button(label="Statistics", style=discord.ButtonStyle.primary, row=0)
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
            current_ppe_type=str(getattr(selected, "ppe_type", "regular")),
            defaults=defaults,
            max_ppes=self.max_ppes,
            source_message=interaction.message,
            connected_ppe_ids=self.connected_ppe_ids,
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Manage PPE Type", style=discord.ButtonStyle.primary, row=2)
    async def manage_ppe_type(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        selected = self.current_ppe()
        guild_config = self.guild_config or await load_guild_config(interaction)
        ppe_settings = guild_config.get("ppe_settings", {}) if isinstance(guild_config.get("ppe_settings", {}), dict) else {}
        wizard = ManagePlayerPpeTypeWizardView(
            owner_id=interaction.user.id,
            target=self.target,
            ppe_id=int(selected.id),
            max_ppes=self.max_ppes,
            source_message=interaction.message,
            connected_ppe_ids=self.connected_ppe_ids,
            ppe_settings=ppe_settings,
            initial_options=normalize_ppe_type_options(
                getattr(selected, "ppe_type_options", None),
                current_type=getattr(selected, "ppe_type", None),
            ),
        )
        await interaction.response.send_message(
            wizard.prompt_text(),
            view=wizard,
            ephemeral=True,
        )

    @discord.ui.button(label="Set Duo Partner", style=discord.ButtonStyle.primary, row=2)
    async def set_duo_partner(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.myinfo.submenus.character.modals import ManageCharacterDuoPartnerModal
        from menus.myinfo.common import display_class_name

        selected = self.current_ppe()
        selected_type = normalize_ppe_type(getattr(selected, "ppe_type", None))
        if not is_duo_ppe_type(selected_type):
            await interaction.response.send_message(
                "This character is not a Duo PPE type."
                " Use Manage PPE Type if you want to change its type first.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            ManageCharacterDuoPartnerModal(
                owner_id=interaction.user.id,
                ppe_id=int(selected.id),
                class_name=display_class_name(selected),
            )
        )

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
        from menus.manageplayer.common import display_class_name, format_points

        refreshed = await load_target_player_data(interaction, self.target.user_id)
        selected = find_ppe_or_raise(refreshed, self.ppe_id)
        source_items = [
            (loot_item.item_name, bool(loot_item.shiny), str(getattr(loot_item, "rarity", "common")))
            for loot_item in selected.loot
        ]

        await generate_loot_share_image(
            interaction,
            source_items=source_items,
            include_skins=include_skins,
            include_limited=include_limited,
            filename_suffix=f"target_{self.target.user_id}_ppe{selected.id}_loot",
            embed_title="🎒 PPE Loot Share",
            embed_color=0x00FF00,
            embed_description=(
                f"**{self.target.display_name}'s** {display_class_name(selected)} PPE #{selected.id} "
                f"[{ppe_type_text(selected, compact=True)}]"
            ),
            total_items_label="Total Loot",
            all_variant_extra_lines=[f"**Points:** {format_points(selected.points)}"],
        )

        await interaction.followup.send(
            f"Generated: **{variant_image_label(include_skins, include_limited)}**",
            ephemeral=False,
        )

        variant_name = "admin character loot image"
        if include_skins and include_limited:
            variant_name = "admin character loot image (all loot)"
        elif include_skins:
            variant_name = "admin character loot image (normal + skins)"
        elif include_limited:
            variant_name = "admin character loot image (normal + limited)"
        else:
            variant_name = "admin character loot image (normal only)"

        await log_cost_event(
            interaction,
            command_name=f"/manageplayer show image {variant_name}",
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
        started_monotonic = time.monotonic()
        snapshot_before = capture_runtime_snapshot()
        await close_manageplayer_menu(interaction)
        refreshed = await load_target_player_data(interaction, self.target.user_id)
        selected = find_ppe_or_raise(refreshed, self.ppe_id)
        await send_target_loot_markdown_followup(interaction, ppe=selected)
        await log_cost_event(
            interaction,
            command_name="/manageplayer list loot",
            started_monotonic=started_monotonic,
            snapshot_before=snapshot_before,
            source="menu_action",
        )

    @discord.ui.button(label="Show Character Statistics", style=discord.ButtonStyle.success, row=2)
    async def show_character_statistics(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        started_monotonic = time.monotonic()
        snapshot_before = capture_runtime_snapshot()
        refreshed = await load_target_player_data(interaction, self.target.user_id)
        selected = find_ppe_or_raise(refreshed, self.ppe_id)
        guild_config = await load_guild_config(interaction)
        embed = build_character_wrapped_embed(
            player_data=refreshed,
            ppe=selected,
            display_name=self.target.display_name,
            guild_config=guild_config,
        )
        await close_manageplayer_menu(interaction)
        await interaction.followup.send(embed=embed, ephemeral=False)
        await log_cost_event(
            interaction,
            command_name="/manageplayer statistics (character)",
            started_monotonic=started_monotonic,
            snapshot_before=snapshot_before,
            source="menu_action",
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=3)
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


def _clear_duo_flags_for_ppe(*, options_value: object, current_type: object) -> dict[str, object]:
    """Return PPE type options with only duo linkage disabled."""
    options = normalize_ppe_type_options(options_value, current_type=current_type)
    updated = dict(options)
    updated["duo_enabled"] = False
    updated["duo_partner_id"] = None
    updated["duo_link_id"] = None
    return normalize_ppe_type_options(updated, current_type=current_type)


def _matching_partner_duo_ppe(
    *,
    partner_ppes: list[PPEData],
    owner_user_id: int,
    expected_link_id: str | None,
) -> PPEData | None:
    """Find the partner-side PPE that is linked back to the owner's duo PPE."""
    fallback: PPEData | None = None
    for candidate in partner_ppes:
        candidate_options = normalize_ppe_type_options(
            getattr(candidate, "ppe_type_options", None),
            current_type=getattr(candidate, "ppe_type", None),
        )
        if not bool(candidate_options.get("duo_enabled", False)):
            continue
        if int(candidate_options.get("duo_partner_id") or 0) != int(owner_user_id):
            continue
        if fallback is None:
            fallback = candidate
        candidate_link_id = str(candidate_options.get("duo_link_id") or "").strip() or None
        if expected_link_id is not None and candidate_link_id == expected_link_id:
            return candidate
    return fallback


def _break_duo_for_linked_partner(
    *,
    records: dict[int, PlayerData],
    owner_user_id: int,
    previous_options: dict[str, object],
    guild_config: dict,
) -> tuple[int, int] | None:
    """Disable duo linkage on the partner's matching PPE while preserving all other tags."""
    partner_id = int(previous_options.get("duo_partner_id") or 0)
    if partner_id <= 0:
        return None

    partner_player = records.get(partner_id)
    if partner_player is None:
        return None

    partner_ppes = getattr(partner_player, "ppes", [])
    if not isinstance(partner_ppes, list) or not partner_ppes:
        return None

    expected_link_id = str(previous_options.get("duo_link_id") or "").strip() or None
    partner_ppe = _matching_partner_duo_ppe(
        partner_ppes=partner_ppes,
        owner_user_id=owner_user_id,
        expected_link_id=expected_link_id,
    )
    if partner_ppe is None:
        return None

    partner_ppe.ppe_type_options = _clear_duo_flags_for_ppe(
        options_value=getattr(partner_ppe, "ppe_type_options", None),
        current_type=getattr(partner_ppe, "ppe_type", None),
    )
    partner_ppe.ppe_type = infer_legacy_ppe_type_from_options(partner_ppe.ppe_type_options)
    recompute_ppe_points(partner_ppe, guild_config)
    return partner_id, int(getattr(partner_ppe, "id", 0))


class ManagePlayerDuoPartnerIdModal(discord.ui.Modal, title="Set Duo Partner Discord ID"):
    partner_id = discord.ui.TextInput(
        label="Discord User ID",
        placeholder="Example: 123456789012345678",
        required=True,
        max_length=24,
    )

    def __init__(self, *, wizard: "ManagePlayerPpeTypeWizardView") -> None:
        super().__init__(timeout=180)
        self.wizard = wizard

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.wizard.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        partner_text = str(self.partner_id.value or "").strip()
        if not partner_text.isdigit() or int(partner_text) <= 0:
            await interaction.response.send_message("Please enter a valid numeric Discord ID.", ephemeral=True)
            return

        partner_id = int(partner_text)
        
        # Validate that partner exists in guild
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        guild_member = interaction.guild.get_member(partner_id)
        if guild_member is None:
            await interaction.response.send_message(
                f"❌ User <@{partner_id}> is not in this server.",
                ephemeral=True,
            )
            return
        if not has_ppe_player_role(guild_member, interaction.guild):
            await interaction.response.send_message(
                f"❌ <@{partner_id}> is not a PPE Player.",
                ephemeral=True,
            )
            return
        
        # Validate that partner is already a PPE player
        records = await load_player_records(interaction)
        partner_player = records.get(partner_id)
        if partner_player is None or not getattr(partner_player, "ppes", []):
            await interaction.response.send_message(
                f"❌ <@{partner_id}> is not a PPE player yet. They need to create their first PPE before you can pair with them.",
                ephemeral=True,
            )
            return

        self.wizard.state["duo_partner_id"] = partner_id
        await interaction.response.send_message(
            f"✅ Duo partner set to <@{partner_id}>.",
            ephemeral=True,
        )

        await self.wizard.advance_from_modal()


class ManagePlayerPpeTypeWizardView(discord.ui.View):
    def __init__(
        self,
        *,
        owner_id: int,
        target: ManagedPlayerTarget,
        ppe_id: int,
        max_ppes: int,
        source_message: discord.Message | None,
        connected_ppe_ids: set[int],
        ppe_settings: dict,
        initial_options: dict,
    ) -> None:
        super().__init__(timeout=600)
        self.owner_id = owner_id
        self.target = target
        self.ppe_id = ppe_id
        self.max_ppes = max_ppes
        self.source_message = source_message
        self.connected_ppe_ids = connected_ppe_ids
        self.ppe_settings = ppe_settings if isinstance(ppe_settings, dict) else {}
        self.base_multipliers = self.ppe_settings.get("iterative_base_multipliers", {}) if isinstance(self.ppe_settings.get("iterative_base_multipliers", {}), dict) else {}
        self.state: dict[str, object] = dict(initial_options)
        self.step = "regular"

        async def _refresh_minimum_rarity(interaction: discord.Interaction) -> None:
            await interaction.response.edit_message(content=self.prompt_text(), view=self)

        (
            self._minimum_rarity_on_selected,
            self._minimum_rarity_on_continue,
        ) = build_minimum_rarity_handlers(
            state=self.state,
            refresh=_refresh_minimum_rarity,
            advance=self.advance,
        )

        self._rebuild_items()

    def _multiplier_hint(self, key: str, fallback: float) -> str:
        try:
            value = float(self.base_multipliers.get(key, fallback))
        except (TypeError, ValueError):
            value = fallback
        return f"x{value:.2f}"

    def _rarity_hint(self) -> str:
        bucket = self.base_multipliers.get("minimum_rarity", {}) if isinstance(self.base_multipliers.get("minimum_rarity", {}), dict) else {}

        shiny_only = bool(self.state.get("shiny_only", False))
        available_options = get_minimum_rarity_options(shiny_only)

        fallback_map = {
            "all_shinies_allowed": 1.0,
            "common": 1.0,
            "uncommon": 1.1,
            "rare": 1.2,
            "legendary": 1.4,
            "divine": 1.5,
        }

        def _value(name: str, fallback: float) -> str:
            try:
                parsed = float(bucket.get(name, fallback))
            except (TypeError, ValueError):
                parsed = fallback
            if name == "all_shinies_allowed":
                return f"All Shinies Allowed {parsed:.2f}x"
            return f"{name.title()} {parsed:.2f}x"

        return ", ".join([_value(opt, fallback_map.get(opt, 1.0)) for opt in available_options])

    def prompt_text(self) -> str:
        if self.step == "regular":
            return "Are you going to do a regular PPE?"
        if self.step == "uses_pet":
            return f"Are you gonna use a pet? (No pet: {self._multiplier_hint('no_pet', 1.3)})"
        if self.step == "allows_tiered":
            return f"Do you allow yourself to use tiered items? (No tiered: {self._multiplier_hint('no_tiered', 1.3)})"
        if self.step == "shiny_only":
            return f"Is this character shiny only? (Yes: {self._multiplier_hint('shiny_only', 1.5)})"
        if self.step == "minimum_rarity":
            return f"What is the minimum rarity for this character? ({self._rarity_hint()})"
        if self.step == "enforce_shiny":
            try:
                enforce_value = float(self.base_multipliers.get("enforce_shiny_rarity", 0.9))
            except (TypeError, ValueError):
                enforce_value = 0.9
            return enforce_shiny_rarity_prompt(self.state.get("minimum_rarity", "common"), enforce_value)
        if self.step == "duo":
            return f"Would you like to do a duo PPE? (Yes: {self._multiplier_hint('duo', 0.6)})"
        if self.step == "duo_partner":
            partner_id = self.state.get("duo_partner_id")
            partner_line = f"Current duo partner: <@{partner_id}>" if isinstance(partner_id, int) else "Current duo partner: not set"
            return (
                "Enter duo partner Discord ID.\n"
                "How to find it: User Settings -> Advanced -> Developer Mode ON, then right click user and Copy User ID.\n"
                f"{partner_line}"
            )
        if self.step == "confirm":
            options = build_ppe_type_options(
                regular=self.state.get("regular", True),
                uses_pet=self.state.get("uses_pet", True),
                allows_tiered=self.state.get("allows_tiered", True),
                minimum_rarity=self.state.get("minimum_rarity", "common"),
                shiny_only=self.state.get("shiny_only", False),
                enforce_rarity_on_shiny=self.state.get("enforce_rarity_on_shiny", False),
                duo_enabled=self.state.get("duo_enabled", False),
                duo_partner_id=self.state.get("duo_partner_id"),
            )
            signature = ppe_type_option_signature(options)
            summary = format_ppe_label_from_options(
                options,
                compact=True,
                guild_config={"ppe_settings": self.ppe_settings},
            )
            partner_line = "None"
            if options.get("duo_enabled"):
                partner_id = options.get("duo_partner_id")
                partner_line = f"<@{partner_id}>" if partner_id else "Missing"
            return (
                f"Confirm PPE type update for PPE #{self.ppe_id}.\n"
                f"Summary: {summary}\n"
                f"Signature: `{signature}`\n"
                f"Duo Partner: {partner_line}\n"
                "Click Confirm Update to save."
            )
        return "Continue setup."

    def _set_yes_no(self, value: bool) -> None:
        if self.step == "regular":
            self.state["regular"] = value
        elif self.step == "uses_pet":
            self.state["uses_pet"] = value
        elif self.step == "allows_tiered":
            self.state["allows_tiered"] = value
            if value:
                # If tiered items are allowed, shiny-only restrictions are irrelevant.
                self.state["shiny_only"] = False
                self.state["enforce_rarity_on_shiny"] = False
        elif self.step == "shiny_only":
            self.state["shiny_only"] = value
        elif self.step == "enforce_shiny":
            self.state["enforce_rarity_on_shiny"] = value
        elif self.step == "duo":
            self.state["duo_enabled"] = value
            if not value:
                self.state["duo_partner_id"] = None

    def _next_step(self) -> str:
        if self.step == "regular":
            return "duo" if bool(self.state.get("regular")) else "uses_pet"
        if self.step == "uses_pet":
            return "allows_tiered"
        if self.step == "allows_tiered":
            return "minimum_rarity" if bool(self.state.get("allows_tiered", True)) else "shiny_only"
        if self.step == "shiny_only":
            return "minimum_rarity"
        if self.step == "minimum_rarity":
            if requires_enforce_shiny_rarity_choice(self.state.get("minimum_rarity", "common")):
                return "enforce_shiny"
            self.state["enforce_rarity_on_shiny"] = True
            return "duo"
        if self.step == "enforce_shiny":
            return "duo"
        if self.step == "duo":
            return "duo_partner" if bool(self.state.get("duo_enabled")) else "confirm"
        if self.step == "duo_partner":
            return "confirm"
        return "confirm"

    async def advance(self, interaction: discord.Interaction) -> None:
        self.step = self._next_step()
        self._rebuild_items()
        await interaction.response.edit_message(content=self.prompt_text(), view=self)

    async def advance_from_modal(self) -> None:
        self.step = self._next_step()
        self._rebuild_items()
        if self.source_message is not None:
            await self.source_message.edit(content=self.prompt_text(), view=self)

    def _rebuild_items(self) -> None:
        self.clear_items()
        if self.step in {"regular", "uses_pet", "allows_tiered", "shiny_only", "enforce_shiny", "duo"}:
            self.add_item(_ManagePlayerWizardYesButton())
            self.add_item(_ManagePlayerWizardNoButton())
            self.add_item(_ManagePlayerWizardCancelButton())
            return
        if self.step == "minimum_rarity":
            self.add_item(
                MinimumRaritySelect(
                    selected=str(self.state.get("minimum_rarity", "common")),
                    owner_id=self.owner_id,
                    view_type=ManagePlayerPpeTypeWizardView,
                    on_selected=self._minimum_rarity_on_selected,
                    shiny_only=bool(self.state.get("shiny_only", False)),
                )
            )
            self.add_item(
                MinimumRarityContinueButton(
                    owner_id=self.owner_id,
                    view_type=ManagePlayerPpeTypeWizardView,
                    on_continue=self._minimum_rarity_on_continue,
                    row=1,
                )
            )
            self.add_item(_ManagePlayerWizardCancelButton())
            return
        if self.step == "duo_partner":
            self.add_item(_ManagePlayerWizardSetDuoIdButton())
            self.add_item(_ManagePlayerWizardContinueButton())
            self.add_item(_ManagePlayerWizardCancelButton())
            return
        if self.step == "confirm":
            self.add_item(_ManagePlayerWizardConfirmButton())
            self.add_item(_ManagePlayerWizardCancelButton())


class _ManagePlayerWizardYesButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Yes", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManagePlayerPpeTypeWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        view._set_yes_no(True)
        await view.advance(interaction)


class _ManagePlayerWizardNoButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="No", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManagePlayerPpeTypeWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        view._set_yes_no(False)
        await view.advance(interaction)


class _ManagePlayerWizardSetDuoIdButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Set Duo Partner ID", style=discord.ButtonStyle.primary, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManagePlayerPpeTypeWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        await interaction.response.send_modal(ManagePlayerDuoPartnerIdModal(wizard=view))


class _ManagePlayerWizardContinueButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Continue", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManagePlayerPpeTypeWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        if bool(view.state.get("duo_enabled")) and not isinstance(view.state.get("duo_partner_id"), int):
            await interaction.response.send_message("Please set a valid duo partner Discord ID first.", ephemeral=True)
            return
        await view.advance(interaction)


class _ManagePlayerWizardConfirmButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Confirm Update", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManagePlayerPpeTypeWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        records = await load_player_records(interaction)
        key = ensure_player_exists(records, view.target.user_id)
        player_data = records[key]
        ppe = find_ppe_or_raise(player_data, view.ppe_id)
        guild_config = await load_guild_config(interaction)

        options = build_ppe_type_options(
            regular=view.state.get("regular", True),
            uses_pet=view.state.get("uses_pet", True),
            allows_tiered=view.state.get("allows_tiered", True),
            minimum_rarity=view.state.get("minimum_rarity", "common"),
            shiny_only=view.state.get("shiny_only", False),
            enforce_rarity_on_shiny=view.state.get("enforce_rarity_on_shiny", False),
            duo_enabled=view.state.get("duo_enabled", False),
            duo_partner_id=view.state.get("duo_partner_id"),
        )
        previous_options = normalize_ppe_type_options(
            getattr(ppe, "ppe_type_options", None),
            current_type=getattr(ppe, "ppe_type", None),
        )
        was_duo = bool(previous_options.get("duo_enabled", False))
        now_duo = bool(options.get("duo_enabled", False))

        ppe.ppe_type_options = options
        ppe.ppe_type = infer_legacy_ppe_type_from_options(options)
        points = recompute_ppe_points(ppe, guild_config).get("total", getattr(ppe, "points", 0.0))

        partner_break_result: tuple[int, int] | None = None
        if was_duo and not now_duo:
            partner_break_result = _break_duo_for_linked_partner(
                records=records,
                owner_user_id=view.target.user_id,
                previous_options=previous_options,
                guild_config=guild_config,
            )
            try:
                await clear_duo_partner(interaction, view.target.user_id)
            except Exception:
                pass

        await save_player_records(interaction=interaction, records=records)

        summary = format_ppe_label_from_options(
            options,
            compact=True,
            guild_config={"ppe_settings": guild_config.get("ppe_settings", {}) if isinstance(guild_config, dict) else {}},
            fallback_type=ppe.ppe_type,
        )
        await interaction.response.edit_message(content="PPE type updated.", view=None)
        duo_break_suffix = ""
        if partner_break_result is not None:
            partner_user_id, partner_ppe_id = partner_break_result
            duo_break_suffix = (
                f" Duo link removed and partner PPE #{partner_ppe_id} for <@{partner_user_id}> "
                "was converted to an individual PPE."
            )
        await interaction.followup.send(
            f"✅ Updated PPE #{ppe.id} type for {view.target.display_name} to **{summary}**. "
            f"New total: {float(points):.2f} points.{duo_break_suffix}",
            ephemeral=False,
        )

        if view.source_message is not None:
            refreshed = await load_target_player_data(interaction, view.target.user_id)
            refreshed_guild_config = await load_guild_config(interaction)
            connected_ids = await realmshark_connected_ppe_ids(interaction, view.target.user_id)
            refreshed_view = ManagePlayerCharactersView(
                owner_id=view.owner_id,
                target=view.target,
                max_ppes=view.max_ppes,
                player_data=refreshed,
                connected_ppe_ids=connected_ids,
                guild_config=refreshed_guild_config,
                preferred_ppe_id=view.ppe_id,
            )
            try:
                await view.source_message.edit(embed=refreshed_view.current_embed(), view=refreshed_view)
            except discord.HTTPException:
                pass


class _ManagePlayerWizardCancelButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Cancel", style=discord.ButtonStyle.danger, row=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManagePlayerPpeTypeWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        await interaction.response.edit_message(content="Cancelled PPE type update.", view=None)
