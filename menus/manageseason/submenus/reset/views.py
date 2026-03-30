"""Reset submenu views for /manageseason."""

from __future__ import annotations

import discord

from menus.manageseason.common import (
    build_reset_completion_embed,
    build_reset_mode_embed,
)
from menus.manageseason.services import reset_season_data
from menus.menu_utils import ConfirmCancelView, OwnerBoundView


class ResetSeasonModeView(OwnerBoundView):
    """Reset flow mode picker that branches by RealmShark link handling strategy."""

    def __init__(self, *, owner_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id

    def current_embed(self) -> discord.Embed:
        return build_reset_mode_embed()

    async def _confirm_and_execute(self, interaction: discord.Interaction, *, clear_realmshark_links: bool) -> None:
        mode_text = (
            "unlink all RealmShark links and remove all mappings"
            if clear_realmshark_links
            else "keep RealmShark links and convert PPE mappings to seasonal mappings"
        )

        confirm_view = ConfirmCancelView(
            owner_id=self.owner_id,
            timeout=60,
            confirm_label="Confirm Reset",
            cancel_label="Cancel",
            confirm_style=discord.ButtonStyle.danger,
            cancel_style=discord.ButtonStyle.secondary,
            owner_error="This confirmation belongs to another user.",
        )

        await interaction.response.send_message(
            "WARNING: **Are you sure you want to reset the season?**\n"
            "This will clear all PPE data, season loot, quest progress, and teams.\n"
            f"Mode selected: **{mode_text}**.",
            view=confirm_view,
            ephemeral=True,
        )

        await confirm_view.wait()
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass

        if not confirm_view.confirmed:
            await interaction.followup.send("Season reset cancelled.", ephemeral=True)
            return

        await interaction.followup.send("Running season reset. This may take a few seconds...", ephemeral=True)

        try:
            summary = await reset_season_data(interaction, clear_realmshark_links=clear_realmshark_links)
        except (ValueError, KeyError) as exc:
            await interaction.followup.send(f"ERROR: {exc}", ephemeral=True)
            return
        except Exception as exc:
            await interaction.followup.send(f"ERROR: Unexpected reset failure: {exc}", ephemeral=True)
            return

        embed = build_reset_completion_embed(summary, actor_name=interaction.user.display_name)
        await interaction.followup.send(embed=embed, ephemeral=False)

        if interaction.message is not None:
            from menus.manageseason.submenus.home.views import ManageSeasonHomeView

            home_view = ManageSeasonHomeView(owner_id=self.owner_id)
            try:
                await interaction.message.edit(embed=home_view.current_embed(), view=home_view)
            except discord.HTTPException:
                pass

    @discord.ui.button(label="Keep RealmShark Links", style=discord.ButtonStyle.success, row=0)
    async def keep_links(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._confirm_and_execute(interaction, clear_realmshark_links=False)

    @discord.ui.button(label="Unlink RealmShark Links", style=discord.ButtonStyle.danger, row=0)
    async def clear_links(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._confirm_and_execute(interaction, clear_realmshark_links=True)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.home.views import ManageSeasonHomeView

        home_view = ManageSeasonHomeView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=home_view.current_embed(), view=home_view)


__all__ = ["ResetSeasonModeView"]
