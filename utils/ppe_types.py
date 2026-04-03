from __future__ import annotations

from typing import Any

PPE_TYPE_REGULAR = "regular"
PPE_TYPE_DUO = "duo"
PPE_TYPE_DIVINE_ONLY = "divine_only"
PPE_TYPE_UT_ONLY = "ut_only"
PPE_TYPE_SHINY_ONLY = "shiny_only"
PPE_TYPE_NO_PET = "no_pet"
PPE_TYPE_DIVINE_SHINY = "divine_shiny"

PPE_TYPE_ORDER = [
    PPE_TYPE_REGULAR,
    PPE_TYPE_DUO,
    PPE_TYPE_DIVINE_ONLY,
    PPE_TYPE_UT_ONLY,
    PPE_TYPE_SHINY_ONLY,
    PPE_TYPE_NO_PET,
    PPE_TYPE_DIVINE_SHINY,
]

PPE_TYPE_LABELS = {
    PPE_TYPE_REGULAR: "Regular PPE",
    PPE_TYPE_DUO: "Duo PPE",
    PPE_TYPE_DIVINE_ONLY: "Divine Only PPE",
    PPE_TYPE_UT_ONLY: "UT Only PPE",
    PPE_TYPE_SHINY_ONLY: "Shiny Only PPE",
    PPE_TYPE_NO_PET: "No Pet PPE (NPE)",
    PPE_TYPE_DIVINE_SHINY: "Divine & Shiny PPE",
}

PPE_TYPE_SHORT_LABELS = {
    PPE_TYPE_REGULAR: "PPE",
    PPE_TYPE_DUO: "Duo PPE",
    PPE_TYPE_DIVINE_ONLY: "DPE",
    PPE_TYPE_UT_ONLY: "UPE",
    PPE_TYPE_SHINY_ONLY: "SPE",
    PPE_TYPE_NO_PET: "NPE",
    PPE_TYPE_DIVINE_SHINY: "D+SPE",
}

DEFAULT_PPE_TYPE = PPE_TYPE_REGULAR

DEFAULT_PPE_TYPE_MULTIPLIERS = {
    PPE_TYPE_REGULAR: 1.0,
    PPE_TYPE_DUO: 0.7,
    PPE_TYPE_DIVINE_ONLY: 1.5,
    PPE_TYPE_UT_ONLY: 1.3,
    PPE_TYPE_SHINY_ONLY: 1.5,
    PPE_TYPE_NO_PET: 1.3,
    PPE_TYPE_DIVINE_SHINY: 2.0,
}


def ppe_type_label(ppe_type: str) -> str:
    return PPE_TYPE_LABELS.get(str(ppe_type), PPE_TYPE_LABELS[DEFAULT_PPE_TYPE])


def ppe_type_short_label(ppe_type: str) -> str:
    return PPE_TYPE_SHORT_LABELS.get(str(ppe_type), PPE_TYPE_SHORT_LABELS[DEFAULT_PPE_TYPE])


def ppe_type_display_label(ppe_type: str, *, compact: bool = False) -> str:
    if compact:
        return ppe_type_short_label(ppe_type)
    return ppe_type_label(ppe_type)


def normalize_ppe_type(value: Any) -> str:
    text = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    text = text.replace("&", "and").replace("+", "plus")
    text = text.replace("(", "").replace(")", "").replace(",", "")
    if not text:
        return DEFAULT_PPE_TYPE

    aliases = {
        PPE_TYPE_REGULAR: PPE_TYPE_REGULAR,
        "ppe": PPE_TYPE_REGULAR,
        "regular_ppe": PPE_TYPE_REGULAR,
        "regularppe": PPE_TYPE_REGULAR,
        PPE_TYPE_DUO: PPE_TYPE_DUO,
        "duo_ppe": PPE_TYPE_DUO,
        "duoppe": PPE_TYPE_DUO,
        PPE_TYPE_DIVINE_ONLY: PPE_TYPE_DIVINE_ONLY,
        "dpe": PPE_TYPE_DIVINE_ONLY,
        "divineonly": PPE_TYPE_DIVINE_ONLY,
        "divine_only_ppe": PPE_TYPE_DIVINE_ONLY,
        PPE_TYPE_UT_ONLY: PPE_TYPE_UT_ONLY,
        "upe": PPE_TYPE_UT_ONLY,
        "utonly": PPE_TYPE_UT_ONLY,
        "ut_only_ppe": PPE_TYPE_UT_ONLY,
        PPE_TYPE_SHINY_ONLY: PPE_TYPE_SHINY_ONLY,
        "spe": PPE_TYPE_SHINY_ONLY,
        "shinyonly": PPE_TYPE_SHINY_ONLY,
        "shiny_only_ppe": PPE_TYPE_SHINY_ONLY,
        PPE_TYPE_NO_PET: PPE_TYPE_NO_PET,
        "npe": PPE_TYPE_NO_PET,
        "no_pet_ppe": PPE_TYPE_NO_PET,
        PPE_TYPE_DIVINE_SHINY: PPE_TYPE_DIVINE_SHINY,
        "dspe": PPE_TYPE_DIVINE_SHINY,
        "dplusspe": PPE_TYPE_DIVINE_SHINY,
        "d_plus_spe": PPE_TYPE_DIVINE_SHINY,
        "d+spe": PPE_TYPE_DIVINE_SHINY,
        "divine_shiny_ppe": PPE_TYPE_DIVINE_SHINY,
        "divine&shiny": PPE_TYPE_DIVINE_SHINY,
        "divine_and_shiny": PPE_TYPE_DIVINE_SHINY,
        "divine_and_shiny_ppe": PPE_TYPE_DIVINE_SHINY,
    }

    return aliases.get(text, DEFAULT_PPE_TYPE)


def all_ppe_types() -> list[str]:
    return list(PPE_TYPE_ORDER)


def normalize_allowed_ppe_types(value: Any) -> list[str]:
    if not isinstance(value, list):
        return all_ppe_types()

    allowed: list[str] = []
    for raw in value:
        normalized = normalize_ppe_type(raw)
        if normalized not in PPE_TYPE_ORDER:
            continue
        if normalized in allowed:
            continue
        allowed.append(normalized)

    return allowed or [DEFAULT_PPE_TYPE]


def normalize_ppe_type_multipliers(value: Any) -> dict[str, float]:
    raw = value if isinstance(value, dict) else {}
    normalized: dict[str, float] = {}

    for ppe_type in PPE_TYPE_ORDER:
        default_value = float(DEFAULT_PPE_TYPE_MULTIPLIERS[ppe_type])
        try:
            parsed = float(raw.get(ppe_type, default_value))
        except (TypeError, ValueError):
            parsed = default_value
        if parsed <= 0:
            parsed = default_value
        normalized[ppe_type] = parsed

    return normalized


def resolve_creation_ppe_type(
    requested_type: Any,
    *,
    enabled: bool,
    allowed_types: list[str],
) -> tuple[str, str | None]:
    if not enabled:
        return DEFAULT_PPE_TYPE, None

    allowed = normalize_allowed_ppe_types(allowed_types)
    selected = normalize_ppe_type(requested_type)

    if requested_type is None or str(requested_type).strip() == "":
        selected = DEFAULT_PPE_TYPE

    if selected not in allowed:
        allowed_labels = ", ".join(ppe_type_label(t) for t in allowed)
        return DEFAULT_PPE_TYPE, (
            f"ERROR: That PPE type is not allowed in this server. Allowed types: {allowed_labels}."
        )

    return selected, None


def resolve_edit_ppe_type(
    requested_type: Any,
    *,
    current_type: Any,
    enabled: bool,
    allowed_types: list[str],
) -> tuple[str, str | None]:
    if requested_type is None or str(requested_type).strip() == "":
        selected = normalize_ppe_type(current_type)
    else:
        selected = normalize_ppe_type(requested_type)

    if not enabled:
        return DEFAULT_PPE_TYPE, None

    allowed = normalize_allowed_ppe_types(allowed_types)
    if selected not in allowed:
        allowed_labels = ", ".join(ppe_type_label(t) for t in allowed)
        return normalize_ppe_type(current_type), (
            f"ERROR: That PPE type is not allowed in this server. Allowed types: {allowed_labels}."
        )

    return selected, None
