import os

import discord

from utils.embed_builders import build_loot_embed
from utils.guild_config import load_guild_config
from utils.loot_table_md_builder import create_loot_markdown_file


class LootTableMessage:
    """
    Centralized class for handling loot table message generation and delivery.
    Supports markdown-file and embed responses.
    """

    def __init__(self, interaction: discord.Interaction, message_type: str = "markdown", response: str = None, **config):
        self.interaction = interaction
        self.message_type = message_type
        self.response = response
        self.config = config

    async def send_player_loot(self, active_ppe, **kwargs):
        try:
            if self.response:
                await self.interaction.response.send_message(
                    self.response,
                    ephemeral=self.config.get("response_ephemeral", False),
                )

            if self.message_type == "markdown":
                await self._send_markdown_file(active_ppe)
            elif self.message_type == "embed":
                await self._send_embed(active_ppe, **kwargs)
            elif self.message_type == "visual":
                raise NotImplementedError("Visual message type not yet implemented")
            else:
                raise ValueError(f"Unsupported message type: {self.message_type}")
        except (ValueError, KeyError) as e:
            error_msg = str(e)
            if self.response:
                await self.interaction.followup.send(error_msg, ephemeral=True)
            else:
                await self.interaction.response.send_message(error_msg, ephemeral=True)

    async def _send_markdown_file(self, active_ppe):
        guild_config = None
        if self.interaction.guild is not None:
            guild_config = await load_guild_config(self.interaction)

        temp_file_path = create_loot_markdown_file(active_ppe, guild_config=guild_config)

        try:
            if self.response:
                await self.interaction.followup.send(
                    file=discord.File(temp_file_path),
                    ephemeral=self.config.get("ephemeral", True),
                )
            else:
                await self.interaction.response.send_message(
                    file=discord.File(temp_file_path),
                    ephemeral=self.config.get("ephemeral", True),
                )
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    async def _send_embed(self, active_ppe, **kwargs):
        user_id = kwargs.get("user_id", self.interaction.user.id)
        recently_added = kwargs.get("recently_added", None)
        embed = await build_loot_embed(active_ppe, user_id=user_id, recently_added=recently_added)

        content = self.config.get(
            "embed_content",
            f"Your active PPE now has **{active_ppe.points} total points**.",
        )

        if self.response:
            await self.interaction.followup.send(
                content=content,
                view=embed,
                embed=embed.embeds[0],
                ephemeral=self.config.get("ephemeral", True),
            )
        else:
            await self.interaction.response.send_message(
                content=content,
                view=embed,
                embed=embed.embeds[0],
                ephemeral=self.config.get("ephemeral", True),
            )
