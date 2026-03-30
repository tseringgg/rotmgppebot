"""Danger confirmation submenu for /managesniffer."""

from __future__ import annotations

import discord

from menus.managesniffer.services import reset_all_sniffer_settings, set_sniffer_enabled
from menus.menu_utils import OwnerBoundView


class SnifferDangerConfirmView(OwnerBoundView):
    def __init__(self, owner_id: int, action_key: str) -> None:
        super().__init__(owner_id=owner_id, timeout=180, owner_error="This confirmation belongs to another admin.")
        self.action_key = action_key

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, row=0)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if self.action_key == "disable":
            await set_sniffer_enabled(interaction, False)
            from menus.managesniffer.submenus.home.views import render_managesniffer_home

            await render_managesniffer_home(interaction, owner_id=self.owner_id)
            await interaction.followup.send(
                "Sniffer disabled. Existing tokens are preserved, but incoming sniffer ingest and monitoring are now inactive.",
                ephemeral=True,
            )
            return

        if self.action_key == "reset":
            summary = await reset_all_sniffer_settings(interaction)
            from menus.managesniffer.submenus.home.views import render_managesniffer_home

            await render_managesniffer_home(interaction, owner_id=self.owner_id)
            await interaction.followup.send(
                "Reset all sniffer data for this guild.\n"
                f"enabled: `{summary['enabled']}`\n"
                f"mode: `{summary['mode']}`\n"
                f"announce_channel_id: `{summary['announce_channel_id']}`\n"
                f"link_count: `{summary['link_count']}`\n"
                f"revoked_links: `{summary['revoked_links']}`\n"
                f"pending_files_removed: `{summary['pending_files_removed']}`",
                ephemeral=True,
            )
            return

        await interaction.response.send_message("Unknown confirmation action.", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=0)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.managesniffer.submenus.home.views import render_managesniffer_home

        await render_managesniffer_home(interaction, owner_id=self.owner_id)


__all__ = ["SnifferDangerConfirmView"]
