"""Character-focused /myinfo views for PPE browsing, loot sharing, and bonus edits."""

from __future__ import annotations

import discord

from dataclass import Bonus, PPEData, PlayerData
from menus.menu_utils import OwnerBoundView
from menus.myinfo.common import (
    build_character_embed,
    close_myinfo_menu,
    display_class_name,
    find_ppe_or_raise,
    format_points,
    open_myinfo_home,
    refresh_player_data,
    send_myloot_markdown_followup,
    temporarily_switch_active_ppe_and_share,
)
from utils.bonus_data import load_bonuses
from utils.guild_config import get_max_ppes, load_guild_config
from utils.helpers.shareloot_image import variant_image_label
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.points_service import recompute_ppe_points


class _BonusChoiceSelect(discord.ui.Select):
    """Dropdown selector for choosing which bonus to add or remove."""

    def __init__(self, owner_id: int, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="Select a bonus",
            min_values=1,
            max_values=1,
            options=options[:25] if options else [discord.SelectOption(label="No options", value="")],
            disabled=not bool(options),
        )
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ModifyPPEView):
            await interaction.response.send_message("Could not update selection.", ephemeral=True)
            return

        view.selected_bonus_name = self.values[0]
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class ModifyPPEView(OwnerBoundView):
    """Menu view for adding or removing bonuses on a specific PPE."""

    def __init__(
        self,
        *,
        owner_id: int,
        ppe: PPEData,
        player_data: PlayerData,
        connected_ppe_ids: set[int],
        action: str = "add",
        selected_bonus_name: str | None = None,
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.ppe_id = int(ppe.id)
        self.player_data = player_data
        self.connected_ppe_ids = connected_ppe_ids
        self.action = action
        self.selected_bonus_name = selected_bonus_name

        options = self._build_options(ppe)
        self.add_item(_BonusChoiceSelect(owner_id, options))

    def _build_options(self, ppe: PPEData) -> list[discord.SelectOption]:
        if self.action == "add":
            options: list[discord.SelectOption] = []
            for bonus_name, bonus in sorted(load_bonuses().items()):
                repeat_text = "repeatable" if bonus.repeatable else "one-time"
                options.append(
                    discord.SelectOption(
                        label=bonus_name[:100],
                        value=bonus_name,
                        description=f"{bonus.points:+g} pts, {repeat_text}"[:100],
                    )
                )
            return options

        remove_counts: dict[str, int] = {}
        for bonus in ppe.bonuses:
            qty = max(1, int(getattr(bonus, "quantity", 1)))
            remove_counts[bonus.name] = remove_counts.get(bonus.name, 0) + qty

        options = []
        for bonus_name, quantity in sorted(remove_counts.items()):
            options.append(
                discord.SelectOption(
                    label=bonus_name[:100],
                    value=bonus_name,
                    description=f"Owned: {quantity}"[:100],
                )
            )
        return options

    def current_embed(self) -> discord.Embed:
        mode_name = "Add Bonus" if self.action == "add" else "Remove Bonus"
        selected_line = self.selected_bonus_name or "Nothing selected"

        embed = discord.Embed(
            title=f"Modify PPE #{self.ppe_id}",
            description=f"Mode: **{mode_name}**\nSelected bonus: **{selected_line}**",
            color=discord.Color.orange(),
        )
        embed.add_field(
            name="How this works",
            value=(
                "1) Pick add/remove mode.\n"
                "2) Select a bonus from the dropdown.\n"
                "3) Click Confirm to apply and announce the update publicly."
            ),
            inline=False,
        )
        return embed

    @discord.ui.button(label="Add Mode", style=discord.ButtonStyle.success, row=1)
    async def switch_add_mode(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        refreshed = await refresh_player_data(interaction, interaction.user.id)
        view = ModifyPPEView(
            owner_id=self.owner_id,
            ppe=find_ppe_or_raise(refreshed, self.ppe_id),
            player_data=refreshed,
            connected_ppe_ids=self.connected_ppe_ids,
            action="add",
        )
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Remove Mode", style=discord.ButtonStyle.secondary, row=1)
    async def switch_remove_mode(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        refreshed = await refresh_player_data(interaction, interaction.user.id)
        view = ModifyPPEView(
            owner_id=self.owner_id,
            ppe=find_ppe_or_raise(refreshed, self.ppe_id),
            player_data=refreshed,
            connected_ppe_ids=self.connected_ppe_ids,
            action="remove",
        )
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.primary, row=1)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not self.selected_bonus_name:
            await interaction.response.send_message("Pick a bonus from the dropdown first.", ephemeral=True)
            return

        records = await load_player_records(interaction)
        key = ensure_player_exists(records, interaction.user.id)
        player_data = records[key]
        ppe = find_ppe_or_raise(player_data, self.ppe_id)

        guild_config = await load_guild_config(interaction)

        if self.action == "add":
            available = load_bonuses()
            bonus_data = available.get(self.selected_bonus_name)
            if bonus_data is None:
                await interaction.response.send_message("Selected bonus is no longer available.", ephemeral=True)
                return

            existing = next((b for b in ppe.bonuses if b.name == self.selected_bonus_name), None)
            if existing:
                if not bonus_data.repeatable:
                    await interaction.response.send_message(
                        "That bonus already exists and is not repeatable.",
                        ephemeral=True,
                    )
                    return
                existing.quantity += 1
            else:
                ppe.bonuses.append(
                    Bonus(
                        name=bonus_data.name,
                        points=float(bonus_data.points),
                        repeatable=bool(bonus_data.repeatable),
                        quantity=1,
                    )
                )

            recompute_ppe_points(ppe, guild_config)
            await save_player_records(interaction, records)

            public_message = (
                f"✅ {interaction.user.mention} updated PPE #{ppe.id} ({display_class_name(ppe)}): "
                f"added bonus **{self.selected_bonus_name}**. "
                f"New total: **{format_points(ppe.points)}** points."
            )
        else:
            existing = next((b for b in ppe.bonuses if b.name.lower() == self.selected_bonus_name.lower()), None)
            if existing is None:
                await interaction.response.send_message("That bonus is not currently on this PPE.", ephemeral=True)
                return

            if int(existing.quantity) > 1:
                existing.quantity -= 1
            else:
                ppe.bonuses.remove(existing)

            recompute_ppe_points(ppe, guild_config)
            await save_player_records(interaction, records)

            public_message = (
                f"✅ {interaction.user.mention} updated PPE #{ppe.id} ({display_class_name(ppe)}): "
                f"removed bonus **{self.selected_bonus_name}**. "
                f"New total: **{format_points(ppe.points)}** points."
            )

        await interaction.response.edit_message(content="PPE updated. Menu closed.", embed=None, view=None)
        await interaction.followup.send(public_message, ephemeral=False)

    @discord.ui.button(label="Home", style=discord.ButtonStyle.secondary, row=1)
    async def home(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        max_ppes = await get_max_ppes(interaction)
        await open_myinfo_home(interaction, max_ppes=max_ppes)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/myinfo` menu.", embed=None, view=None)


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

    @discord.ui.button(label="Modify PPE", style=discord.ButtonStyle.secondary, row=1)
    async def modify_ppe(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        selected = self.current_ppe()
        view = ModifyPPEView(
            owner_id=interaction.user.id,
            ppe=selected,
            player_data=self.player_data,
            connected_ppe_ids=self.connected_ppe_ids,
            action="add",
        )
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

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
