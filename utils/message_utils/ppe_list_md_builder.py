"""Utilities for ppe list md builder."""

from __future__ import annotations

from dataclass import PlayerData
from utils.ppe_types import normalize_ppe_type
from utils.ppe_display import format_ppe_label_from_options
from utils.message_utils.markdown_message_builder import MarkdownMessageBuilder
from utils.points_service import compute_effective_ppe_points
from utils.points_service import non_default_points_adjustment_lines


def _format_points(value: float) -> str:
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def _display_class_name(ppe) -> str:
    return _inline_code(str(getattr(ppe.name, "value", ppe.name)))


def _display_ppe_type(ppe, *, guild_config: dict | None = None) -> str:
    normalized = normalize_ppe_type(getattr(ppe, "ppe_type", None))
    options = getattr(ppe, "ppe_type_options", None)
    ppe_settings = {}
    if isinstance(guild_config, dict):
        raw_settings = guild_config.get("ppe_settings", {})
        if isinstance(raw_settings, dict):
            ppe_settings = raw_settings
    summary = format_ppe_label_from_options(
        options,
        compact=True,
        guild_config={"ppe_settings": ppe_settings},
        fallback_type=normalized,
    )
    return _inline_code(summary)


def _inline_code(text: str) -> str:
    value = str(text).replace("`", "\\`")
    return f"`{value}`"


def _effective_points(ppe, *, guild_config: dict | None = None) -> float:
    if not isinstance(guild_config, dict):
        return float(getattr(ppe, "points", 0.0) or 0.0)
    return float(compute_effective_ppe_points(ppe, guild_config=guild_config))


def create_ppe_list_markdown_file(
    player_data: PlayerData,
    *,
    display_name: str,
    include_best_marker: bool,
    guild_config: dict | None = None,
) -> str:
    sorted_ppes = sorted(player_data.ppes, key=lambda p: int(p.id))
    effective_points_by_id = {
        int(ppe.id): _effective_points(ppe, guild_config=guild_config)
        for ppe in sorted_ppes
    }
    best_ppe = max(
        sorted_ppes,
        key=lambda p: effective_points_by_id.get(int(p.id), 0.0),
        default=None,
    )
    best_ppe_id = int(best_ppe.id) if best_ppe else None

    builder = MarkdownMessageBuilder(f"PPE List for {display_name}")
    class_names = [_display_class_name(ppe) for ppe in sorted_ppes]
    point_adjustment_lines = non_default_points_adjustment_lines(guild_config, class_names=class_names)
    builder.add_section(
        heading="Point Adjustments From Defaults",
        lines=point_adjustment_lines or ["No point adjustments from defaults."],
    )

    if not sorted_ppes:
        builder.add_section(heading="Characters", lines=["No PPEs found."])
    else:
        lines: list[str] = []
        for ppe in sorted_ppes:
            labels: list[str] = []
            if int(ppe.id) == int(player_data.active_ppe or -1):
                labels.append("ACTIVE")
            if include_best_marker and best_ppe_id is not None and int(ppe.id) == best_ppe_id:
                labels.append("BEST")

            suffix = f" [{' | '.join(labels)}]" if labels else ""
            effective_points = effective_points_by_id.get(int(ppe.id), float(getattr(ppe, "points", 0.0) or 0.0))
            lines.append(
                f"PPE #{ppe.id} | Class: {_display_class_name(ppe)} | Type: {_display_ppe_type(ppe, guild_config=guild_config)} "
                f"| Points: {_format_points(effective_points)}{suffix}"
            )

        builder.add_numbered_list(lines, heading="Characters")

    return builder.write_temp_file(prefix="ppe_list", username=display_name)
