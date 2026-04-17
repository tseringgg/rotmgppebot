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

import discord

from utils.loot_helpers.loot_table_message import LootTableMessage
from utils.loot_ops import add_ppe_loot
from utils.loot_constants import normalize_rarity


class RaritySelect(discord.ui.Select):
    def __init__(self, selected: str = "common"):
        selected_value = normalize_rarity(selected)
        options = [
            discord.SelectOption(label="Common", value="common", default=selected_value == "common"),
            discord.SelectOption(label="Uncommon", value="uncommon", default=selected_value == "uncommon"),
            discord.SelectOption(label="Rare", value="rare", default=selected_value == "rare"),
            discord.SelectOption(label="Legendary", value="legendary", default=selected_value == "legendary"),
            discord.SelectOption(label="Divine", value="divine", default=selected_value == "divine"),
        ]
        super().__init__(
            placeholder=f"Rarity: {selected_value.title()}",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
        )

    def sync_selected(self, rarity: str) -> None:
        selected_value = normalize_rarity(rarity)
        self.placeholder = f"Rarity: {selected_value.title()}"
        for option in self.options:
            option.default = option.value == selected_value

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, ItemSuggestionView):
            return
        if not await view._check_authorized(interaction):
            return

        view.rarity = normalize_rarity(self.values[0])
        self.sync_selected(view.rarity)
        await interaction.response.edit_message(view=view)

# ---------------------------------------------------------------------------
# Paths resolved once, relative to this file's location
# ---------------------------------------------------------------------------

_DETECTOR_DIR = os.path.join(os.path.dirname(__file__), "item_detector")
_TEMPLATE_DIR = os.path.join(_DETECTOR_DIR, "feed_power_templates")
_DESCRIPTIONS_CSV = os.path.join(_DETECTOR_DIR, "descriptions", "rotmg_item_descriptions.csv")
# Tesseract: use the Windows default when running locally, fall back to PATH on Linux/Railway
_TESSERACT_WIN = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_TESSERACT_CMD: Optional[str] = _TESSERACT_WIN if os.path.exists(_TESSERACT_WIN) else None
_ITEM_SUGGESTION_DEBUG = os.getenv("ITEM_SUGGESTION_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}


def _debug_log(message: str) -> None:
    if _ITEM_SUGGESTION_DEBUG:
        print(f"[item_suggestion][debug] {message}")


def _warn_log(message: str) -> None:
    print(f"[item_suggestion][warn] {message}")


def _error_log(message: str) -> None:
    print(f"[item_suggestion][error] {message}")


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
            _debug_log(f"detector matched item={result['item_name']} score={result['score']:.1f}")
            return result["item_name"]
        _debug_log("detector no item detected")
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
        self.rarity = "common"
        self.rarity_select = RaritySelect(self.rarity)
        self.add_item(self.rarity_select)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _check_authorized(self, interaction: discord.Interaction) -> bool:
        """Return True if the responder is the original uploader, else deny."""
        if interaction.user.id != self.target_user_id:
            _warn_log(
                f"unauthorized button click by user={interaction.user.id} "
                f"(expected {self.target_user_id})"
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
        self.rarity_select.sync_selected(self.rarity)
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Add", style=discord.ButtonStyle.success, row=0)
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_authorized(interaction):
            return

        guild_id = interaction.guild.id if interaction.guild else "?"
        _debug_log(
            f"ADD clicked guild={guild_id} user={interaction.user.id} item={self.suggested_item}"
        )

        member = interaction.user
        if not isinstance(member, discord.Member):
            await self._finish(interaction, f"Could not add **{self.suggested_item}** to your active PPE.")
            return

        try:
            # Resolve the active PPE id first (raises if none)
            from utils.player_records import load_player_records, ensure_player_exists
            records = await load_player_records(interaction)
            key = ensure_player_exists(records, member.id)
            player_data = records[key]
            if not player_data.active_ppe:
                raise LookupError("no active PPE")
            ppe_id = player_data.active_ppe

            result = await add_ppe_loot(
                interaction,
                user=member,
                ppe_id=ppe_id,
                item_name=self.suggested_item,
                shiny=self.is_shiny,
                rarity=self.rarity,
            )
            _debug_log(
                f"add succeeded guild={guild_id} user={member.id} item={self.suggested_item}"
            )
            tags = ""
            if self.is_shiny:
                tags += " (shiny)"
            if self.rarity and self.rarity != "common":
                tags += f" ({self.rarity})"
            await self._finish(
                interaction,
                f"> ✅ Added **{result.item_name}**{tags} to your active PPE for {result.points_delta} points.",
            )

            loot_message = LootTableMessage(
                interaction=interaction,
                message_type="markdown",
                already_responded=True,
                ephemeral=True,
                embed_content=f"Your active PPE now has **{result.ppe.points} total points**.",
            )
            await loot_message.send_player_loot(result.ppe, user_id=member.id, recently_added=result.item_name)

        except LookupError:
            _warn_log(f"no active PPE guild={guild_id} user={member.id}")
            await self._finish(
                interaction,
                f"You do not have an active PPE set, so **{self.suggested_item}** was not added.",
            )
        except Exception as e:
            _error_log(f"add failed guild={guild_id} user={member.id} error={e}")
            await self._finish(
                interaction,
                f"Could not add **{self.suggested_item}** to your active PPE.",
            )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=0)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_authorized(interaction):
            return

        guild_id = interaction.guild.id if interaction.guild else "?"
        _debug_log(
            f"CANCEL clicked guild={guild_id} user={interaction.user.id} item={self.suggested_item}"
        )
        await self._finish(
            interaction,
            f"Did not add **{self.suggested_item}**.",
        )

    # ------------------------------------------------------------------
    # Timeout
    # ------------------------------------------------------------------

    async def on_timeout(self):
        _debug_log(f"suggestion timed out for item={self.suggested_item}")
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

    _debug_log(
        f"detection started guild={guild_id} channel={channel_id} user={user_id} "
        f"files={[a.filename for a in attachments]}"
    )

    async def _process_one(attachment: discord.Attachment) -> None:
        suggested_item = await detect_item_from_attachment(attachment)

        if suggested_item is None:
            _debug_log(
                f"no item detected; skipping suggestion guild={guild_id} "
                f"channel={channel_id} user={user_id} file={attachment.filename}"
            )
            return

        _debug_log(
            f"suggestion triggered guild={guild_id} channel={channel_id} "
            f"user={user_id} item={suggested_item}"
        )

        view = ItemSuggestionView(target_user_id=user_id, suggested_item=suggested_item)
        sent = await message.reply(
            f"Found **{suggested_item}**. Add it to your active PPE?",
            view=view,
        )
        view.message = sent

    await asyncio.gather(*(_process_one(a) for a in attachments))
