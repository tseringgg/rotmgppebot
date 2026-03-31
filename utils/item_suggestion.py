"""
Item-suggestion flow for PNG attachments.

Detection is performed by utils/item_detector/item_detector.py.
If detection returns None (no anchor found, low confidence, etc.) the
suggestion flow is silently skipped for that upload.
"""

import asyncio
import os
import tempfile
from typing import Optional
from urllib import response

import discord

from utils.player_manager import player_manager
from utils.calc_points import calc_points
from slash_commands.helpers.loot_table_message import LootTableMessage

# ---------------------------------------------------------------------------
# Paths resolved once, relative to this file's location
# ---------------------------------------------------------------------------

_DETECTOR_DIR = os.path.join(os.path.dirname(__file__), "item_detector")
_TEMPLATE_DIR = os.path.join(_DETECTOR_DIR, "feed_power_templates")
_DESCRIPTIONS_CSV = os.path.join(_DETECTOR_DIR, "descriptions", "rotmg_item_descriptions.csv")
# Tesseract: use the Windows default when running locally, fall back to PATH on Linux/Railway
_TESSERACT_WIN = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_TESSERACT_CMD: Optional[str] = _TESSERACT_WIN if os.path.exists(_TESSERACT_WIN) else None


# ---------------------------------------------------------------------------
# Detection helper
# ---------------------------------------------------------------------------

async def detect_item_from_attachment(attachment: discord.Attachment) -> Optional[str]:
    """
    Download the PNG attachment to a temp file, run the item detector in a
    background thread, and return the matched item name or None.
    """
    from utils.item_detector.item_detector import detect_item_from_image_path

    # Write bytes to a named temp file so OpenCV can read it
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await attachment.save(tmp_path)
        result = await asyncio.to_thread(
            detect_item_from_image_path,
            tmp_path,
            _TEMPLATE_DIR,
            _DESCRIPTIONS_CSV,
            _TESSERACT_CMD,
        )
        if result:
            print(f"[detector] matched item={result['item_name']} score={result['score']:.1f}")
            return result["item_name"]
        print("[detector] no item detected")
        return None
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

class ItemSuggestionView(discord.ui.View):
    """Suggestion prompt shown after a PNG is uploaded in an enabled channel."""

    def __init__(self, target_user_id: int, suggested_item: str):
        super().__init__(timeout=180)
        self.target_user_id = target_user_id
        self.suggested_item = suggested_item
        self.is_shiny = False
        self.is_divine = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _check_authorized(self, interaction: discord.Interaction) -> bool:
        """Return True if the responder is the original uploader, else deny."""
        if interaction.user.id != self.target_user_id:
            print(
                f"[item_suggestion] unauthorized button click "
                f"by user={interaction.user.id} (expected {self.target_user_id})"
            )
            await interaction.response.send_message(
                "Only the original uploader can respond to this suggestion.",
                ephemeral=True,
            )
            return False
        return True

    async def _finish(self, interaction: discord.Interaction, result_text: str):
        """Edit the original suggestion message, strip the buttons, stop the view."""
        self.stop()
        await interaction.response.edit_message(content=result_text, view=None)

    # ------------------------------------------------------------------
    # Toggle buttons + action buttons (all on row 0)
    # ------------------------------------------------------------------

    @discord.ui.button(label="Shiny: No", style=discord.ButtonStyle.secondary, row=0)
    async def shiny_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_authorized(interaction):
            return
        self.is_shiny = not self.is_shiny
        button.label = "Shiny: Yes" if self.is_shiny else "Shiny: No"
        button.style = discord.ButtonStyle.success if self.is_shiny else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Divine: No", style=discord.ButtonStyle.secondary, row=0)
    async def divine_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_authorized(interaction):
            return
        self.is_divine = not self.is_divine
        button.label = "Divine: Yes" if self.is_divine else "Divine: No"
        button.style = discord.ButtonStyle.success if self.is_divine else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Add", style=discord.ButtonStyle.success, row=0)
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_authorized(interaction):
            return

        guild_id = interaction.guild.id if interaction.guild else "?"
        print(
            f"[item_suggestion] ADD clicked "
            f"guild={guild_id} user={interaction.user.id} item={self.suggested_item}"
        )

        member = interaction.user
        if not isinstance(member, discord.Member):
            await self._finish(interaction, f"Could not add **{self.suggested_item}** to your active PPE.")
            return

        try:
            points = calc_points(self.suggested_item, divine=self.is_divine, shiny=self.is_shiny)
            # Resolve the active PPE id first (raises if none)
            from utils.player_records import load_player_records, ensure_player_exists, get_active_ppe
            records = await load_player_records(interaction)
            key = ensure_player_exists(records, member.id)
            player_data = records[key]
            if not player_data.active_ppe:
                raise LookupError("no active PPE")
            ppe_id = player_data.active_ppe

            final_key, points_added, active_ppe, quest_update = await player_manager.add_loot_and_points(
                interaction,
                user=member,
                ppe_id=ppe_id,
                item_name=self.suggested_item,
                divine=self.is_divine,
                shiny=self.is_shiny,
                points=points,
            )
            print(
                f"[item_suggestion] add succeeded "
                f"guild={guild_id} user={member.id} item={self.suggested_item}"
            )
            tags = ""
            if self.is_shiny:
                tags += " (shiny)"
            if self.is_divine:
                tags += " (divine)"
            await self._finish(
                interaction,
                f"> ✅ Added **{final_key}**{tags} to your active PPE for {points_added} points.",
            )

            loot_message = LootTableMessage(
                interaction=interaction,
                message_type="markdown",
                already_responded=True,
                ephemeral=True,
                embed_content=f"Your active PPE now has **{active_ppe.points} total points**.",
            )
            await loot_message.send_player_loot(active_ppe, user_id=member.id, recently_added=final_key)

        except LookupError:
            print(
                f"[item_suggestion] no active PPE "
                f"guild={guild_id} user={member.id}"
            )
            await self._finish(
                interaction,
                f"You do not have an active PPE set, so **{self.suggested_item}** was not added.",
            )
        except Exception as e:
            print(
                f"[item_suggestion] add failed "
                f"guild={guild_id} user={member.id} error={e}"
            )
            await self._finish(
                interaction,
                f"Could not add **{self.suggested_item}** to your active PPE.",
            )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=0)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_authorized(interaction):
            return

        guild_id = interaction.guild.id if interaction.guild else "?"
        print(
            f"[item_suggestion] CANCEL clicked "
            f"guild={guild_id} user={interaction.user.id} item={self.suggested_item}"
        )
        await self._finish(
            interaction,
            f"Did not add **{self.suggested_item}**.",
        )

    # ------------------------------------------------------------------
    # Timeout
    # ------------------------------------------------------------------

    async def on_timeout(self):
        print(f"[item_suggestion] suggestion timed out for item={self.suggested_item}")
        # `self.message` is set automatically by discord.py when the view is
        # attached via `reply(..., view=self)`.
        if hasattr(self, "message") and self.message:
            try:
                await self.message.edit(
                    content=f"Suggestion expired for **{self.suggested_item}**.",
                    view=None,
                )
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Helper called from on_message
# ---------------------------------------------------------------------------

async def handle_item_suggestion(
    message: discord.Message,
    attachments: list[discord.Attachment],
) -> None:
    """
    Download each image attachment, run the detector on all of them
    concurrently, and (for each detected item) prompt the uploader with
    a Yes / No confirmation.
    """
    guild_id = message.guild.id if message.guild else "?"
    channel_id = message.channel.id
    user_id = message.author.id

    print(
        f"[item_suggestion] detection started "
        f"guild={guild_id} channel={channel_id} user={user_id} "
        f"files={[a.filename for a in attachments]}"
    )

    async def _process_one(attachment: discord.Attachment) -> None:
        suggested_item = await detect_item_from_attachment(attachment)

        if suggested_item is None:
            print(
                f"[item_suggestion] no item detected — skipping suggestion "
                f"guild={guild_id} channel={channel_id} user={user_id} file={attachment.filename}"
            )
            return

        print(
            f"[item_suggestion] suggestion triggered "
            f"guild={guild_id} channel={channel_id} user={user_id} item={suggested_item}"
        )

        view = ItemSuggestionView(target_user_id=user_id, suggested_item=suggested_item)
        sent = await message.reply(
            f"Found **{suggested_item}**. Add it to your active PPE?",
            view=view,
        )
        view.message = sent

    await asyncio.gather(*(_process_one(a) for a in attachments))
