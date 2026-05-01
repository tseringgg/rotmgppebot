"""Views for bot-cost telemetry management in /manageseason."""

from __future__ import annotations

import io
import os

import discord

from menus.manageseason.common import build_manage_bot_cost_embeds
from menus.manageseason.services import (
    build_bot_cost_summary_markdown_for_menu,
    clear_bot_cost_log_for_menu,
    load_bot_cost_summary_for_menu,
)
from menus.menu_utils import ConfirmCancelView, OwnerBoundView


class ManageBotCostView(OwnerBoundView):
    """Owner-bound panel for per-command bot-cost telemetry and exports."""

    def __init__(self, *, owner_id: int, summary: dict, window_hours: int = 24) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.summary = dict(summary)
        self.window_hours = max(1, int(window_hours))
        self.page_index = 0
        self.embeds = build_manage_bot_cost_embeds(self.summary)
        self._sync_window_buttons()
        self._sync_logging_button()

    def _sync_window_buttons(self) -> None:
        self.window_24h.style = (
            discord.ButtonStyle.primary if self.window_hours == 24 else discord.ButtonStyle.secondary
        )
        self.window_7d.style = (
            discord.ButtonStyle.primary if self.window_hours == 168 else discord.ButtonStyle.secondary
        )
        self.prev_page.disabled = self.page_index == 0
        self.next_page.disabled = self.page_index >= len(self.embeds) - 1

    def current_embed(self) -> discord.Embed:
        if not self.embeds:
            return discord.Embed(title="Manage Bot Cost", description="No telemetry data.")
        return self.embeds[self.page_index]

    async def _reload(self, interaction: discord.Interaction, *, window_hours: int | None = None) -> None:
        if window_hours is not None:
            self.window_hours = max(1, int(window_hours))
        self.summary = await load_bot_cost_summary_for_menu(
            interaction,
            window_hours=self.window_hours,
            top_n=50,
        )
        self.embeds = build_manage_bot_cost_embeds(self.summary)
        self.page_index = 0
        self._sync_window_buttons()
        self._sync_logging_button()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Last 24h", style=discord.ButtonStyle.primary, row=0)
    async def window_24h(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._reload(interaction, window_hours=24)

    @discord.ui.button(label="Last 7d", style=discord.ButtonStyle.secondary, row=0)
    async def window_7d(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._reload(interaction, window_hours=168)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.success, row=0)
    async def refresh(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._reload(interaction)

    @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.secondary, row=1)
    async def prev_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.page_index = max(0, self.page_index - 1)
        self._sync_window_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Enable/Disable Logging", style=discord.ButtonStyle.blurple, row=1)
    async def toggle_logging(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.services import toggle_bot_cost_logging_for_menu
        
        new_state = await toggle_bot_cost_logging_for_menu(interaction)
        await self._reload(interaction)
        
        status = "**enabled**" if new_state else "**disabled**"
        await interaction.followup.send(
            f"Cost logging is now {status}.",
            ephemeral=True,
        )

    @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.secondary, row=1)
    async def next_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.page_index = min(len(self.embeds) - 1, self.page_index + 1)
        self._sync_window_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    def _sync_logging_button(self) -> None:
        """Update the logging button label/style to reflect current state."""
        try:
            enabled = bool(self.summary.get("logging_enabled", True))
        except Exception:
            enabled = True

        label = "Disable Logging" if enabled else "Enable Logging"
        style = discord.ButtonStyle.danger if enabled else discord.ButtonStyle.success

        # The button attribute is named after the callback function: `toggle_logging`
        try:
            btn = getattr(self, "toggle_logging", None)
            if btn is not None:
                btn.label = label
                btn.style = style
        except Exception:
            pass

    @discord.ui.button(label="Export Summary", style=discord.ButtonStyle.success, row=2)
    async def export_summary(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        summary_markdown = await build_bot_cost_summary_markdown_for_menu(
            interaction,
            window_hours=self.window_hours,
            top_n=20,
        )

        guild_id = interaction.guild.id if interaction.guild is not None else 0
        file_name = f"bot_cost_summary_{guild_id}_{self.window_hours}h.md"
        payload = io.BytesIO(summary_markdown.encode("utf-8"))
        await interaction.response.send_message(
            "Bot-cost summary report generated.",
            file=discord.File(payload, filename=file_name),
            ephemeral=True,
        )

    @discord.ui.button(label="Export Raw Log", style=discord.ButtonStyle.secondary, row=2)
    async def export_raw_log(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        log_path = str(self.summary.get("log_path", "")).strip()
        if not log_path or not os.path.exists(log_path):
            await interaction.response.send_message(
                "No per-guild bot-cost log file exists yet for this server.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Per-guild raw bot-cost log:",
            file=discord.File(log_path, filename=os.path.basename(log_path)),
            ephemeral=True,
        )

    @discord.ui.button(label="Clear Log", style=discord.ButtonStyle.danger, row=2)
    async def clear_log(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        confirm_view = ConfirmCancelView(
            owner_id=self.owner_id,
            timeout=60,
            confirm_label="Clear Log",
            cancel_label="Cancel",
            confirm_style=discord.ButtonStyle.danger,
            cancel_style=discord.ButtonStyle.secondary,
            owner_error="This confirmation belongs to another user.",
        )

        await interaction.response.send_message(
            "Clear this server's bot-cost log file? This cannot be undone.",
            ephemeral=True,
            view=confirm_view,
        )

        await confirm_view.wait()
        if confirm_view.confirmed is not True:
            status = "Log clear cancelled." if confirm_view.confirmed is False else "Log clear timed out."
            await interaction.edit_original_response(content=status, view=None)
            return

        deleted = await clear_bot_cost_log_for_menu(interaction)
        self.summary = await load_bot_cost_summary_for_menu(
            interaction,
            window_hours=self.window_hours,
            top_n=10,
        )
        self._sync_window_buttons()

        if interaction.message is not None:
            try:
                await interaction.message.edit(embed=self.current_embed(), view=self)
            except discord.HTTPException:
                pass

        await interaction.edit_original_response(
            content=(
                "Bot-cost log cleared for this guild."
                if deleted
                else "No bot-cost log file existed for this guild."
            ),
            view=None,
        )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=3)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.home.views import ManageSeasonHomeView

        home_view = ManageSeasonHomeView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=home_view.current_embed(), view=home_view)


__all__ = ["ManageBotCostView"]
