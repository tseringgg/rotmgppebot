import csv
import glob
import os
from collections.abc import Sequence

import discord
from PIL import Image

from utils.calc_points import normalize_item_name


LootSourceItems = Sequence[tuple[str, bool]]

_LOOTSUMMARY_DIR = os.path.join("helper_pics", "lootsummary_pics")
_DUNGEONS_PATH = os.path.join("helper_pics", "dungeon_pics")

VARIANT_DISPLAY_NAMES = {
    "normal": "Normal loot",
    "normal_skins": "Normal + Skins loot",
    "normal_limited": "Normal + Limited loot",
    "all": "All loot",
}

VARIANT_SUMMARY_PREFIX = {
    "normal": "Normal",
    "normal_skins": "Normal + Skin",
    "normal_limited": "Normal + Limited",
}

VARIANT_IMAGE_LABELS = {
    "normal": "Normal Loot Image",
    "normal_skins": "Normal + Skins Loot Image",
    "normal_limited": "Normal + Limited Loot Image",
    "all": "All Loot Image",
}


def variant_from_flags(include_skins: bool, include_limited: bool) -> str:
    if include_skins and include_limited:
        return "all"
    if include_skins:
        return "normal_skins"
    if include_limited:
        return "normal_limited"
    return "normal"


def variant_image_label(include_skins: bool, include_limited: bool) -> str:
    variant = variant_from_flags(include_skins, include_limited)
    return VARIANT_IMAGE_LABELS.get(variant, "Loot Image")


async def _send_interaction_text(interaction: discord.Interaction, content: str, *, ephemeral: bool) -> None:
    if not interaction.response.is_done():
        await interaction.response.send_message(content, ephemeral=ephemeral)
        return
    await interaction.followup.send(content, ephemeral=ephemeral)


async def _defer_if_needed(interaction: discord.Interaction) -> None:
    if not interaction.response.is_done():
        await interaction.response.defer()


def _is_in_variant(item_type: str, variant: str) -> bool:
    if variant == "all":
        return True
    if variant == "normal":
        return item_type not in {"skin", "limited"}
    if variant == "normal_skins":
        return item_type != "limited"
    if variant == "normal_limited":
        return item_type != "skin"
    return True


def _load_sprite_positions(sprite_csv: str) -> dict[str, dict[str, int]]:
    sprite_positions: dict[str, dict[str, int]] = {}
    with open(sprite_csv, "r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            normalized_name = normalize_item_name(row["item_name"])
            sprite_positions[normalized_name] = {
                "pixel_x": int(row["pixel_x"]),
                "pixel_y": int(row["pixel_y"]),
            }
    return sprite_positions


def _load_item_type_lookup() -> dict[str, str]:
    item_type_lookup: dict[str, str] = {}
    with open("rotmg_loot_drops_updated.csv", "r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            normalized_name = normalize_item_name(row["Item Name"])
            item_type_lookup[normalized_name] = row["Loot Type"].strip().lower()
    return item_type_lookup


def _load_sprite_images() -> dict[str, Image.Image]:
    sprite_images: dict[str, Image.Image] = {}

    dungeons_path = _DUNGEONS_PATH
    ignored_folders = {"Forging", "Tiered Garbage", "_misc"}

    pattern = os.path.join(dungeons_path, "**", "*.png")
    all_png_files = glob.glob(pattern, recursive=True)

    for png_file in all_png_files:
        rel_path = os.path.relpath(png_file, dungeons_path)
        folder_parts = rel_path.split(os.sep)
        if any(part in ignored_folders for part in folder_parts):
            continue

        item_name = normalize_item_name(os.path.splitext(os.path.basename(png_file))[0])
        try:
            img = Image.open(png_file)
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            if img.size != (40, 40):
                img = img.resize((40, 40), Image.Resampling.LANCZOS)
            sprite_images[item_name] = img
        except Exception as e:
            print(f"Error loading sprite {png_file}: {e}")

    return sprite_images


def _safe_username(display_name: str) -> str:
    username = display_name.replace(" ", "_")
    return "".join(c for c in username if c.isalnum() or c in "_-")


async def generate_loot_share_image(
    interaction: discord.Interaction,
    *,
    source_items: LootSourceItems,
    include_skins: bool,
    include_limited: bool,
    filename_suffix: str,
    embed_title: str,
    embed_color: int,
    embed_description: str,
    total_items_label: str,
    all_variant_extra_lines: Sequence[str] | None = None,
) -> None:
    variant = variant_from_flags(include_skins, include_limited)
    sprite_csv = os.path.join(_LOOTSUMMARY_DIR, f"sprite_positions_{variant}.csv")
    background_file = os.path.join(_LOOTSUMMARY_DIR, f"loot_background_{variant}.png")

    if not os.path.exists(sprite_csv):
        await _send_interaction_text(interaction, f"❌ Sprite mapping not found! ({sprite_csv})", ephemeral=True)
        return

    if not os.path.exists(background_file):
        await _send_interaction_text(interaction, f"❌ Loot background not found! ({background_file})", ephemeral=True)
        return

    try:
        sprite_positions = _load_sprite_positions(sprite_csv)
        item_type_lookup = _load_item_type_lookup()
    except Exception as e:
        await _send_interaction_text(interaction, f"❌ Failed loading loot metadata: {e}", ephemeral=True)
        return

    total_variant_items = 0
    items_excluded_from_variant: list[str] = []

    normalized_items: list[tuple[str, str, bool, str]] = []
    for raw_name, shiny in source_items:
        normalized_name = normalize_item_name(raw_name)
        display_name = f"{raw_name} (shiny)" if shiny else raw_name
        item_type = item_type_lookup.get(normalized_name, "")
        normalized_items.append((raw_name, normalized_name, shiny, item_type))

        if _is_in_variant(item_type, variant):
            total_variant_items += 1
        else:
            items_excluded_from_variant.append(display_name)

    background = None
    sprite_images: dict[str, Image.Image] = {}
    filename = ""

    try:
        with Image.open(background_file) as base:
            background = base.copy()

        sprite_images = _load_sprite_images()
        await _defer_if_needed(interaction)

        items_placed = 0
        items_not_found: list[str] = []

        for raw_name, normalized_name, shiny, item_type in normalized_items:
            if not _is_in_variant(item_type, variant):
                continue

            display_name = f"{raw_name} (shiny)" if shiny else raw_name

            if shiny:
                shiny_name = f"{normalized_name} (shiny)"
                if shiny_name in sprite_positions and shiny_name in sprite_images:
                    pos = sprite_positions[shiny_name]
                    sprite = sprite_images[shiny_name]
                    background.paste(sprite, (pos["pixel_x"], pos["pixel_y"]), sprite)
                    items_placed += 1
                else:
                    items_not_found.append(display_name)
            else:
                if normalized_name in sprite_positions and normalized_name in sprite_images:
                    pos = sprite_positions[normalized_name]
                    sprite = sprite_images[normalized_name]
                    background.paste(sprite, (pos["pixel_x"], pos["pixel_y"]), sprite)
                    items_placed += 1
                else:
                    items_not_found.append(display_name)

        safe_username = _safe_username(interaction.user.display_name)
        filename = f"{safe_username}_{filename_suffix}.png"
        background.save(filename, "PNG")

        embed = discord.Embed(title=embed_title, color=embed_color, description=embed_description)
        embed.add_field(
            name="🖼️ Picture",
            value=f"**Showing:** {VARIANT_DISPLAY_NAMES.get(variant, variant)}",
            inline=True,
        )

        if variant == "all":
            summary_lines = [
                f"**Items Placed:** {items_placed}",
                f"**{total_items_label}:** {len(source_items)}",
            ]
            if all_variant_extra_lines:
                summary_lines.extend(all_variant_extra_lines)
            summary_value = "\n".join(summary_lines)
        else:
            summary_prefix = VARIANT_SUMMARY_PREFIX.get(variant, "Selected")
            summary_value = (
                f"**{summary_prefix} Items Placed:** {items_placed}\n"
                f"**Total {summary_prefix} Items:** {total_variant_items}"
            )

        embed.add_field(name="📊 Summary", value=summary_value, inline=True)

        if variant != "all" and items_excluded_from_variant:
            excluded_text = ", ".join(items_excluded_from_variant[:5])
            if len(items_excluded_from_variant) > 5:
                excluded_text += f" (+{len(items_excluded_from_variant) - 5} more)"
            embed.add_field(
                name="📦 Items Not Shown In This Picture",
                value=excluded_text,
                inline=False,
            )

        if items_not_found:
            not_found_text = ", ".join(items_not_found[:5])
            if len(items_not_found) > 5:
                not_found_text += f" (+{len(items_not_found) - 5} more)"
            embed.add_field(
                name="⚠️ Items Missing Sprites",
                value=not_found_text,
                inline=False,
            )

        embed.set_footer(text=f"Generated for {interaction.user.display_name}")

        with open(filename, "rb") as f:
            file = discord.File(f, filename=filename)
            await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        print(f"Error generating loot share image: {e}")
        await _send_interaction_text(interaction, f"❌ An error occurred: {str(e)}", ephemeral=True)
    finally:
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except OSError:
                pass

        for img in sprite_images.values():
            try:
                img.close()
            except Exception:
                pass

        if background is not None:
            try:
                background.close()
            except Exception:
                pass
