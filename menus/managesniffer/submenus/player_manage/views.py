"""Player management submenu for /managesniffer."""

from __future__ import annotations

import discord

from menus.managesniffer.common import build_manage_player_sniffer_embed
from menus.managesniffer.services import (
    generate_link_token_for_user,
    load_sniffer_settings,
    revoke_token,
)
from menus.managesniffer.validators import resolve_member
from menus.menu_utils import OwnerBoundView
from menus.menu_utils.sniffer_core.admin_panel import admin_panel
from menus.menu_utils.sniffer_shared import (
    build_realmshark_link_instructions,
    iter_user_links,
    token_preview,
)


class _UnlinkTokenSelect(discord.ui.Select):
    """Select menu for choosing which token to unlink for a player."""

    def __init__(self, owner_id: int, target_user_id: int, user_links: list[tuple[str, dict]]) -> None:
        options = []
        for token, link_data in user_links:
            bindings = link_data.get("character_bindings", {})
            seasonal_ids = link_data.get("seasonal_character_ids", [])
            mapped_count = len(bindings) if isinstance(bindings, dict) else 0
            seasonal_count = len(seasonal_ids) if isinstance(seasonal_ids, list) else 0
            char_info = f"{mapped_count} mapped"
            if seasonal_count > 0:
                char_info += f", {seasonal_count} seasonal"

            options.append(
                discord.SelectOption(
                    label=token_preview(token),
                    value=token,
                    description=f"Unlink this token ({char_info} chars)",
                )
            )

        super().__init__(
            placeholder="Select a token to unlink",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.owner_id = owner_id
        self.target_user_id = target_user_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This selection belongs to another admin.", ephemeral=True)
            return

        token = self.values[0]
        # Show confirmation for the selected token
        confirm_view = _UnlinkTokenConfirmView(
            owner_id=self.owner_id,
            target_user_id=self.target_user_id,
            token=token,
        )
        await interaction.response.edit_message(
            embed=confirm_view.current_embed(),
            view=confirm_view,
        )


class _UnlinkTokenConfirmView(OwnerBoundView):
    """Confirmation view for unlinking a specific token."""

    def __init__(self, owner_id: int, target_user_id: int, token: str) -> None:
        super().__init__(owner_id=owner_id, timeout=120, owner_error="This confirmation belongs to another admin.")
        self.target_user_id = target_user_id
        self.token = token

    def current_embed(self) -> discord.Embed:
        return discord.Embed(
            title="⚠️ Confirm Token Unlink",
            description=(
                f"Are you sure you want to unlink token `{token_preview(self.token)}`?\n\n"
                f"**This will:**\n"
                f"- Remove this token from the player\n"
                f"- Remove all character mappings attached to this token\n"
                f"- Remove all seasonal character IDs attached to this token\n\n"
                "The player will need to generate a new token and reconfigure their characters."
            ),
            color=discord.Color.orange(),
        )

    @discord.ui.button(label="Confirm Unlink", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return

        deleted = await revoke_token(interaction, self.token)
        if deleted:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="✅ Token Unlinked",
                    description=f"Token `{token_preview(self.token)}` has been revoked.",
                    color=discord.Color.green(),
                ),
                view=None,
            )
        else:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="❌ Token Not Found",
                    description="The token was already removed.",
                    color=discord.Color.red(),
                ),
                view=None,
            )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return
        # Go back to the token selection
        settings, links = await load_sniffer_settings(interaction)
        user_links = iter_user_links(links, self.target_user_id)
        if not user_links:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="No Tokens",
                    description="This player has no linked tokens.",
                    color=discord.Color.orange(),
                ),
                view=None,
            )
            return

        select_view = _UnlinkTokenSelectView(
            owner_id=self.owner_id,
            target_user_id=self.target_user_id,
            user_links=user_links,
        )
        await interaction.response.edit_message(
            embed=select_view.current_embed(),
            view=select_view,
        )


class _UnlinkTokenSelectView(OwnerBoundView):
    """View for selecting which token to unlink."""

    def __init__(self, owner_id: int, target_user_id: int, user_links: list[tuple[str, dict]]) -> None:
        super().__init__(owner_id=owner_id, timeout=120, owner_error="This selection belongs to another admin.")
        self.target_user_id = target_user_id
        self.add_item(_UnlinkTokenSelect(owner_id, target_user_id, user_links))

    def current_embed(self) -> discord.Embed:
        return discord.Embed(
            title="Select Token to Unlink",
            description=(
                "Choose which token to unlink for this player.\n\n"
                "⚠️ **Warning:** Unlinking a token will remove all character mappings "
                "and seasonal character IDs attached to that token."
            ),
            color=discord.Color.orange(),
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return
        await render_manage_player_sniffer_home(
            interaction,
            owner_id=self.owner_id,
            target_user_id=self.target_user_id,
        )


class ManagePlayerSnifferView(OwnerBoundView):
    def __init__(self, owner_id: int, target_user_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This panel belongs to another admin.")
        self.target_user_id = int(target_user_id)

    async def _target_user(self, interaction: discord.Interaction) -> discord.abc.User | None:
        if interaction.guild is None:
            return None
        return interaction.guild.get_member(self.target_user_id)

    @discord.ui.button(label="Generate Token", style=discord.ButtonStyle.success)
    async def generate_token(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        target_user = await self._target_user(interaction)
        if target_user is None:
            await interaction.response.send_message("Player is no longer in this server.", ephemeral=True)
            return

        token = await generate_link_token_for_user(interaction, self.target_user_id)
        settings, _links = await load_sniffer_settings(interaction)
        endpoint = settings.get("endpoint", "")
        await render_manage_player_sniffer_home(
            interaction,
            owner_id=self.owner_id,
            target_user_id=self.target_user_id,
        )
        await interaction.followup.send(
            "Generated token for selected player:\n"
            + build_realmshark_link_instructions(interaction.guild.id if interaction.guild else None, token, endpoint),
            ephemeral=True,
        )

    @discord.ui.button(label="Unlink Sniffer", style=discord.ButtonStyle.danger)
    async def unlink(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings, links = await load_sniffer_settings(interaction)
        user_links = iter_user_links(links, self.target_user_id)

        if not user_links:
            await interaction.response.send_message(
                "This player has no linked tokens.",
                ephemeral=True,
            )
            return

        # If only one token, go straight to confirmation
        if len(user_links) == 1:
            token = user_links[0][0]
            confirm_view = _UnlinkTokenConfirmView(
                owner_id=self.owner_id,
                target_user_id=self.target_user_id,
                token=token,
            )
            await interaction.response.send_message(
                embed=confirm_view.current_embed(),
                view=confirm_view,
                ephemeral=True,
            )
            return

        # Multiple tokens: show selection view
        select_view = _UnlinkTokenSelectView(
            owner_id=self.owner_id,
            target_user_id=self.target_user_id,
            user_links=user_links,
        )
        await interaction.response.send_message(
            embed=select_view.current_embed(),
            view=select_view,
            ephemeral=True,
        )

    @discord.ui.button(label="Configure Characters", style=discord.ButtonStyle.success)
    async def configure(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        target_member = resolve_member(interaction.guild, self.target_user_id)
        if target_member is None:
            await interaction.response.send_message("Player is no longer in this server.", ephemeral=True)
            return
        await admin_panel(interaction, target_member, "show_all")

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.managesniffer.submenus.home.views import render_managesniffer_home

        await render_managesniffer_home(interaction, owner_id=self.owner_id)


async def render_manage_player_sniffer_home(
    interaction: discord.Interaction,
    *,
    owner_id: int,
    target_user_id: int,
) -> None:
    target_user = resolve_member(interaction.guild, target_user_id)
    if target_user is None:
        await interaction.response.send_message(
            "Player not found in this server. Provide a valid server member ID/mention.",
            ephemeral=True,
        )
        return

    settings, links = await load_sniffer_settings(interaction)
    embed = build_manage_player_sniffer_embed(
        guild_id=interaction.guild.id if interaction.guild else None,
        target_user=target_user,
        settings=settings,
        links=links,
    )
    view = ManagePlayerSnifferView(owner_id=owner_id, target_user_id=target_user_id)
    await interaction.response.edit_message(embed=embed, view=view)


__all__ = ["ManagePlayerSnifferView", "render_manage_player_sniffer_home"]