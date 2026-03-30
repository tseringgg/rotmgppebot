"""Modal flows for editing /managequests settings and global quest item pools."""

from __future__ import annotations

import discord

from menus.managequests.common import coerce_non_negative_int, dedupe_items, load_managequests_settings
from menus.managequests.services import apply_settings_to_players, save_settings
from menus.managequests.validators import parse_item_input, validate_items_for_category


class EditQuestSettingsModal(discord.ui.Modal, title="Edit Quest Settings"):
    regular_quests = discord.ui.TextInput(label="Regular Quest Target", max_length=4)
    shiny_quests = discord.ui.TextInput(label="Shiny Quest Target", max_length=4)
    skin_quests = discord.ui.TextInput(label="Skin Quest Target", max_length=4)
    num_resets = discord.ui.TextInput(label="Quest Resets Per Player", max_length=4)
    points = discord.ui.TextInput(
        label="Points (regular, shiny, skin)",
        placeholder="Example: 5, 10, 15",
        max_length=30,
    )

    def __init__(self, *, owner_id: int, settings: dict, source_message: discord.Message | None) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message

        self.regular_quests.default = str(settings["regular_target"])
        self.shiny_quests.default = str(settings["shiny_target"])
        self.skin_quests.default = str(settings["skin_target"])
        self.num_resets.default = str(settings["num_resets"])
        self.points.default = f"{settings['regular_points']}, {settings['shiny_points']}, {settings['skin_points']}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        try:
            regular = coerce_non_negative_int(self.regular_quests.value, "regular_quests")
            shiny = coerce_non_negative_int(self.shiny_quests.value, "shiny_quests")
            skin = coerce_non_negative_int(self.skin_quests.value, "skin_quests")
            num_resets = coerce_non_negative_int(self.num_resets.value, "num_resets")

            parts = [part.strip() for part in str(self.points.value).split(",")]
            if len(parts) != 3:
                raise ValueError("❌ Points must be entered as exactly: regular, shiny, skin.")
            regular_points = coerce_non_negative_int(parts[0], "regular_points")
            shiny_points = coerce_non_negative_int(parts[1], "shiny_points")
            skin_points = coerce_non_negative_int(parts[2], "skin_points")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        settings = await load_managequests_settings(interaction)
        before_resets = int(settings.get("num_resets", 0))

        settings["regular_target"] = regular
        settings["shiny_target"] = shiny
        settings["skin_target"] = skin
        settings["num_resets"] = num_resets
        settings["regular_points"] = regular_points
        settings["shiny_points"] = shiny_points
        settings["skin_points"] = skin_points
        await save_settings(interaction, settings)

        players_adjusted, active_removed, reset_counters_updated = await apply_settings_to_players(
            interaction,
            settings=settings,
            reset_limit_changed=(before_resets != num_resets),
        )

        await interaction.response.send_message(
            (
                "✅ Quest settings updated.\n"
                f"Players adjusted: **{players_adjusted}**\n"
                f"Active quest entries removed: **{active_removed}**\n"
                f"Reset counters updated: **{reset_counters_updated}**"
            ),
            ephemeral=True,
        )

        if self.source_message is not None:
            from menus.managequests.submenus.home.views import ManageQuestsHomeView

            refreshed = await load_managequests_settings(interaction)
            view = ManageQuestsHomeView(owner_id=self.owner_id, settings=refreshed)
            try:
                await self.source_message.edit(embed=view.current_embed(), view=view)
            except discord.HTTPException:
                pass


class AddGlobalQuestItemsModal(discord.ui.Modal):
    items = discord.ui.TextInput(
        label="Quest Items",
        placeholder="Enter one item per line or comma-separated",
        style=discord.TextStyle.paragraph,
        max_length=1800,
    )

    def __init__(self, *, owner_id: int, category: str, source_message: discord.Message | None) -> None:
        super().__init__(title=f"Add Global {category.title()} Quests", timeout=300)
        self.owner_id = owner_id
        self.category = category
        self.source_message = source_message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        parsed = parse_item_input(str(self.items.value))
        if not parsed:
            await interaction.response.send_message("❌ Provide at least one quest item name.", ephemeral=True)
            return

        validation = validate_items_for_category(self.category, parsed)
        if validation.errors:
            error_preview = "\n".join(validation.errors[:15])
            if len(validation.errors) > 15:
                error_preview += "\n..."
            await interaction.response.send_message(
                "❌ Some items are invalid:\n"
                f"{error_preview}",
                ephemeral=True,
            )
            return

        settings = await load_managequests_settings(interaction)
        key = f"global_{self.category}_quests"
        merged = dedupe_items(list(settings.get(key, [])) + validation.valid_items)
        settings[key] = merged
        await save_settings(interaction, settings)

        players_adjusted, active_removed, _resets = await apply_settings_to_players(interaction, settings=settings)

        await interaction.response.send_message(
            (
                f"✅ Added **{len(validation.valid_items)}** {self.category} global quest item(s).\n"
                f"Total in pool: **{len(merged)}**\n"
                f"Players adjusted: **{players_adjusted}**\n"
                f"Active entries removed: **{active_removed}**"
            ),
            ephemeral=True,
        )

        if self.source_message is not None:
            from menus.managequests.submenus.global_quests.views import GlobalQuestsView

            view = GlobalQuestsView(owner_id=self.owner_id, settings=settings)
            try:
                await self.source_message.edit(embed=view.current_embed(), view=view)
            except discord.HTTPException:
                pass


class RemoveGlobalQuestItemsModal(discord.ui.Modal):
    items = discord.ui.TextInput(
        label="Quest Items to Remove",
        placeholder="Enter one item per line or comma-separated",
        style=discord.TextStyle.paragraph,
        max_length=1800,
    )

    def __init__(self, *, owner_id: int, category: str, source_message: discord.Message | None) -> None:
        super().__init__(title=f"Remove Global {category.title()} Quests", timeout=300)
        self.owner_id = owner_id
        self.category = category
        self.source_message = source_message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        parsed = parse_item_input(str(self.items.value))
        if not parsed:
            await interaction.response.send_message("❌ Provide at least one quest item name.", ephemeral=True)
            return

        validation = validate_items_for_category(self.category, parsed)
        if validation.errors:
            error_preview = "\n".join(validation.errors[:15])
            if len(validation.errors) > 15:
                error_preview += "\n..."
            await interaction.response.send_message(
                "❌ Some items are invalid:\n"
                f"{error_preview}",
                ephemeral=True,
            )
            return

        settings = await load_managequests_settings(interaction)
        key = f"global_{self.category}_quests"
        existing = list(settings.get(key, []))
        existing_by_norm = {item.lower(): item for item in existing}

        requested = validation.valid_items
        missing = [item for item in requested if item.lower() not in existing_by_norm]
        if missing:
            preview = "\n".join(f"• `{item}`" for item in missing[:15])
            if len(missing) > 15:
                preview += "\n..."
            await interaction.response.send_message(
                "❌ These items are not in the current global pool:\n"
                f"{preview}",
                ephemeral=True,
            )
            return

        from menus.menu_utils import ConfirmCancelView

        confirm_view = ConfirmCancelView(
            owner_id=self.owner_id,
            timeout=60,
            confirm_label="Confirm Remove",
            cancel_label="Cancel",
            confirm_style=discord.ButtonStyle.danger,
            cancel_style=discord.ButtonStyle.secondary,
            owner_error="This confirmation belongs to another user.",
        )

        await interaction.response.send_message(
            (
                f"⚠️ Remove **{len(requested)}** {self.category} global quest item(s)?\n"
                "This action updates all players immediately."
            ),
            view=confirm_view,
            ephemeral=True,
        )

        await confirm_view.wait()
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass

        if not confirm_view.confirmed:
            await interaction.followup.send("❌ Removal cancelled.", ephemeral=True)
            return

        remove_norms = {item.lower() for item in requested}
        settings[key] = [item for item in existing if item.lower() not in remove_norms]
        await save_settings(interaction, settings)

        players_adjusted, active_removed, _resets = await apply_settings_to_players(interaction, settings=settings)
        await interaction.followup.send(
            (
                f"✅ Removed **{len(requested)}** {self.category} global quest item(s).\n"
                f"Total in pool: **{len(settings[key])}**\n"
                f"Players adjusted: **{players_adjusted}**\n"
                f"Active entries removed: **{active_removed}**"
            ),
            ephemeral=True,
        )

        if self.source_message is not None:
            from menus.managequests.submenus.global_quests.views import GlobalQuestsView

            view = GlobalQuestsView(owner_id=self.owner_id, settings=settings)
            try:
                await self.source_message.edit(embed=view.current_embed(), view=view)
            except discord.HTTPException:
                pass
