from __future__ import annotations

from typing import Any

from utils.loot_constants import normalize_rarity

PPE_TYPE_REGULAR = "regular"
PPE_TYPE_DUO = "duo"
PPE_TYPE_DUO_NO_PET = "duo_no_pet"
PPE_TYPE_DIVINE_ONLY = "divine_only"
PPE_TYPE_DIVINE_NO_PET = "divine_no_pet"
PPE_TYPE_UT_ONLY = "ut_only"
PPE_TYPE_UT_NO_PET = "ut_no_pet"
PPE_TYPE_SHINY_ONLY = "shiny_only"
PPE_TYPE_SHINY_NO_PET = "shiny_no_pet"
PPE_TYPE_LEGENDARY_OR_SHINY = "legendary_or_shiny"
PPE_TYPE_LEGENDARY_OR_SHINY_NO_PET = "legendary_or_shiny_no_pet"
PPE_TYPE_NO_PET = "no_pet"
PPE_TYPE_DIVINE_SHINY = "divine_shiny"
PPE_TYPE_DIVINE_SHINY_NO_PET = "divine_shiny_no_pet"

PPE_TYPE_ORDER = [
    PPE_TYPE_REGULAR,
    PPE_TYPE_DUO,
    PPE_TYPE_DUO_NO_PET,
    PPE_TYPE_DIVINE_ONLY,
    PPE_TYPE_DIVINE_NO_PET,
    PPE_TYPE_UT_ONLY,
    PPE_TYPE_UT_NO_PET,
    PPE_TYPE_SHINY_ONLY,
    PPE_TYPE_SHINY_NO_PET,
    PPE_TYPE_LEGENDARY_OR_SHINY,
    PPE_TYPE_LEGENDARY_OR_SHINY_NO_PET,
    PPE_TYPE_NO_PET,
    PPE_TYPE_DIVINE_SHINY,
    PPE_TYPE_DIVINE_SHINY_NO_PET,
]

PPE_TYPE_LABELS = {
    PPE_TYPE_REGULAR: "Regular PPE",
    PPE_TYPE_DUO: "Duo PPE",
    PPE_TYPE_DUO_NO_PET: "Duo No Pet PPE",
    PPE_TYPE_DIVINE_ONLY: "Divine Only PPE",
    PPE_TYPE_DIVINE_NO_PET: "Divine Only & No Pet PPE",
    PPE_TYPE_UT_ONLY: "UT Only PPE",
    PPE_TYPE_UT_NO_PET: "UT Only & No Pet PPE",
    PPE_TYPE_SHINY_ONLY: "Shiny Only PPE",
    PPE_TYPE_SHINY_NO_PET: "Shiny Only & No Pet PPE",
    PPE_TYPE_LEGENDARY_OR_SHINY: "Legendary or Shiny PPE",
    PPE_TYPE_LEGENDARY_OR_SHINY_NO_PET: "Legendary or Shiny & No Pet PPE",
    PPE_TYPE_NO_PET: "No Pet PPE (NPE)",
    PPE_TYPE_DIVINE_SHINY: "Divine & Shiny PPE",
    PPE_TYPE_DIVINE_SHINY_NO_PET: "Divine & Shiny & No Pet PPE",
}

PPE_TYPE_SHORT_LABELS = {
    PPE_TYPE_REGULAR: "PPE",
    PPE_TYPE_DUO: "Duo PPE",
    PPE_TYPE_DUO_NO_PET: "Duo NPE",
    PPE_TYPE_DIVINE_ONLY: "DPE",
    PPE_TYPE_DIVINE_NO_PET: "Div NPE",
    PPE_TYPE_UT_ONLY: "UPE",
    PPE_TYPE_UT_NO_PET: "UNPE",
    PPE_TYPE_SHINY_ONLY: "SPE",
    PPE_TYPE_SHINY_NO_PET: "SNPE",
    PPE_TYPE_LEGENDARY_OR_SHINY: "All_SH|LPE",
    PPE_TYPE_LEGENDARY_OR_SHINY_NO_PET: "All_SH|LNPE",
    PPE_TYPE_NO_PET: "NPE",
    PPE_TYPE_DIVINE_SHINY: "D+SPE",
    PPE_TYPE_DIVINE_SHINY_NO_PET: "DSNPE",
}

DEFAULT_PPE_TYPE = PPE_TYPE_REGULAR


def is_duo_ppe_type(value: Any) -> bool:
    return normalize_ppe_type(value) in {PPE_TYPE_DUO, PPE_TYPE_DUO_NO_PET}

DEFAULT_PPE_TYPE_MULTIPLIERS = {
    PPE_TYPE_REGULAR: 1.0,
    PPE_TYPE_DUO: 0.7,
    PPE_TYPE_DUO_NO_PET: 0.91,
    PPE_TYPE_DIVINE_ONLY: 1.5,
    PPE_TYPE_DIVINE_NO_PET: 1.95,
    PPE_TYPE_UT_ONLY: 1.3,
    PPE_TYPE_UT_NO_PET: 1.69,
    PPE_TYPE_SHINY_ONLY: 1.5,
    PPE_TYPE_SHINY_NO_PET: 1.95,
    PPE_TYPE_LEGENDARY_OR_SHINY: 1.3,
    PPE_TYPE_LEGENDARY_OR_SHINY_NO_PET: 1.69,
    PPE_TYPE_NO_PET: 1.3,
    PPE_TYPE_DIVINE_SHINY: 2.0,
    PPE_TYPE_DIVINE_SHINY_NO_PET: 2.6,
}

PPE_MIN_RARITY_ORDER = ["common", "uncommon", "rare", "legendary", "divine"]
PPE_MIN_RARITY_VALUES = [*PPE_MIN_RARITY_ORDER, "all_shinies_allowed"]

DEFAULT_ITERATIVE_OPTION_MULTIPLIERS = {
    "no_pet": 1.3,
    "no_tiered": 1.3,
    "minimum_rarity": {
        "common": 1.0,
        "uncommon": 1.1,
        "rare": 1.2,
        "legendary": 1.4,
        "divine": 1.5,
    },
    "shiny_only": 1.5,
    "enforce_shiny_rarity": 0.9,
    "duo": 0.6,
}


def default_ppe_type_options() -> dict[str, Any]:
    return {
        "regular": True,
        "uses_pet": True,
        "allows_tiered": True,
        "minimum_rarity": "common",
        "shiny_only": False,
        "enforce_rarity_on_shiny": False,
        "duo_enabled": False,
        "duo_partner_id": None,
        "duo_link_id": None,
    }


def _normalize_discord_id(value: Any) -> int | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.startswith("<@") and raw.endswith(">"):
        raw = raw[2:-1].lstrip("!")
    if not raw.isdigit():
        return None
    parsed = int(raw)
    return parsed if parsed > 0 else None


def _normalize_duo_link_id(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw or raw.lower() == "none":
        return None
    return raw


def _disable_unpaired_duo(options: dict[str, Any]) -> dict[str, Any]:
    if not bool(options.get("duo_enabled", False)):
        return options
    if _normalize_discord_id(options.get("duo_partner_id")) is not None:
        return options
    normalized = dict(options)
    normalized["duo_enabled"] = False
    normalized["duo_partner_id"] = None
    normalized["duo_link_id"] = None
    return normalized


def parse_yes_no(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if not text:
        return default
    if text in {"yes", "y", "true", "1", "on"}:
        return True
    if text in {"no", "n", "false", "0", "off"}:
        return False
    return default


def build_ppe_type_options(
    *,
    regular: Any,
    uses_pet: Any,
    allows_tiered: Any,
    minimum_rarity: Any,
    shiny_only: Any,
    enforce_rarity_on_shiny: Any,
    duo_enabled: Any,
    duo_partner_id: Any,
    duo_link_id: Any = None,
) -> dict[str, Any]:
    normalized_duo_link_id = _normalize_duo_link_id(duo_link_id)
    options = {
        "regular": parse_yes_no(regular, default=True),
        "uses_pet": parse_yes_no(uses_pet, default=True),
        "allows_tiered": parse_yes_no(allows_tiered, default=True),
        "minimum_rarity": normalize_minimum_rarity(minimum_rarity),
        "shiny_only": parse_yes_no(shiny_only, default=False),
        "enforce_rarity_on_shiny": parse_yes_no(enforce_rarity_on_shiny, default=False),
        "duo_enabled": parse_yes_no(duo_enabled, default=False),
        "duo_partner_id": _normalize_discord_id(duo_partner_id),
        "duo_link_id": normalized_duo_link_id,
    }
    return normalize_ppe_type_options(options)


def options_from_signature(signature: Any, *, duo_partner_id: Any = None) -> dict[str, Any] | None:
    text = str(signature or "").strip().lower()
    if not text:
        return None
    if text == "regular":
        return normalize_ppe_type_options({"regular": True, "duo_enabled": False})

    raw_parts = [segment.strip() for segment in text.split("|") if segment.strip()]
    token_map: dict[str, str] = {}
    for segment in raw_parts:
        if ":" not in segment:
            continue
        key, value = segment.split(":", 1)
        token_map[key.strip()] = value.strip()

    required_keys = {
        "pet",
        "tiered",
        "minimum",
        "shiny",
        "enforce_shiny_rarity",
        "duo",
    }
    if not required_keys.issubset(set(token_map.keys())):
        return None

    return build_ppe_type_options(
        regular=False,
        uses_pet=token_map.get("pet"),
        allows_tiered=token_map.get("tiered"),
        minimum_rarity=token_map.get("minimum"),
        shiny_only=token_map.get("shiny"),
        enforce_rarity_on_shiny=token_map.get("enforce_shiny_rarity"),
        duo_enabled=token_map.get("duo"),
        duo_partner_id=duo_partner_id,
        duo_link_id=None,
    )


def normalize_minimum_rarity(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"all_shinies_allowed", "all_shinies", "allshiniesallowed"}:
        return "all_shinies_allowed"
    rarity = normalize_rarity(value, "common")
    if rarity not in PPE_MIN_RARITY_ORDER:
        return "common"
    return rarity


def minimum_rarity_effective(value: Any) -> str:
    """Return rarity bucket used for multiplier calculations."""
    normalized = normalize_minimum_rarity(value)
    if normalized == "all_shinies_allowed":
        return "common"
    return normalized


def requires_enforce_shiny_rarity_choice(minimum_rarity: Any) -> bool:
    return minimum_rarity_effective(minimum_rarity) in {"legendary", "divine"}


def legacy_ppe_type_to_options(value: Any) -> dict[str, Any]:
    ppe_type = normalize_ppe_type(value)
    options = default_ppe_type_options()
    if ppe_type == PPE_TYPE_REGULAR:
        return options
    options["regular"] = False

    if ppe_type in {PPE_TYPE_DUO, PPE_TYPE_DUO_NO_PET}:
        options["duo_enabled"] = True
    if ppe_type in {
        PPE_TYPE_NO_PET,
        PPE_TYPE_DUO_NO_PET,
        PPE_TYPE_DIVINE_NO_PET,
        PPE_TYPE_UT_NO_PET,
        PPE_TYPE_SHINY_NO_PET,
        PPE_TYPE_LEGENDARY_OR_SHINY_NO_PET,
        PPE_TYPE_DIVINE_SHINY_NO_PET,
    }:
        options["uses_pet"] = False
    if ppe_type in {PPE_TYPE_UT_ONLY, PPE_TYPE_UT_NO_PET, PPE_TYPE_DIVINE_SHINY, PPE_TYPE_DIVINE_SHINY_NO_PET, PPE_TYPE_SHINY_ONLY, PPE_TYPE_SHINY_NO_PET,}:
        options["allows_tiered"] = False
    if ppe_type in {PPE_TYPE_DIVINE_ONLY, PPE_TYPE_DIVINE_NO_PET, PPE_TYPE_DIVINE_SHINY, PPE_TYPE_DIVINE_SHINY_NO_PET}:
        options["minimum_rarity"] = "divine"
    elif ppe_type in {PPE_TYPE_LEGENDARY_OR_SHINY, PPE_TYPE_LEGENDARY_OR_SHINY_NO_PET}:
        options["minimum_rarity"] = "legendary"
    if ppe_type in {PPE_TYPE_SHINY_ONLY, PPE_TYPE_SHINY_NO_PET, PPE_TYPE_DIVINE_SHINY, PPE_TYPE_DIVINE_SHINY_NO_PET}:
        options["shiny_only"] = True
    if ppe_type in {PPE_TYPE_DIVINE_SHINY, PPE_TYPE_DIVINE_SHINY_NO_PET}:
        options["enforce_rarity_on_shiny"] = True
    return options


def normalize_ppe_type_options(value: Any, *, current_type: Any = None) -> dict[str, Any]:
    if isinstance(value, dict):
        raw = value
        options = default_ppe_type_options()
        options["regular"] = bool(raw.get("regular", options["regular"]))
        options["uses_pet"] = bool(raw.get("uses_pet", options["uses_pet"]))
        options["allows_tiered"] = bool(raw.get("allows_tiered", options["allows_tiered"]))
        options["minimum_rarity"] = normalize_minimum_rarity(raw.get("minimum_rarity", options["minimum_rarity"]))
        options["shiny_only"] = bool(raw.get("shiny_only", options["shiny_only"]))
        options["enforce_rarity_on_shiny"] = bool(raw.get("enforce_rarity_on_shiny", options["enforce_rarity_on_shiny"]))
        options["duo_enabled"] = bool(raw.get("duo_enabled", options["duo_enabled"]))
        options["duo_partner_id"] = _normalize_discord_id(raw.get("duo_partner_id"))
        options["duo_link_id"] = _normalize_duo_link_id(raw.get("duo_link_id"))
    else:
        options = legacy_ppe_type_to_options(current_type)

    if options["regular"]:
        options["uses_pet"] = True
        options["allows_tiered"] = True
        options["minimum_rarity"] = "common"
        options["shiny_only"] = False
        options["enforce_rarity_on_shiny"] = False

    if not options["shiny_only"] and options["minimum_rarity"] == "all_shinies_allowed":
        options["minimum_rarity"] = "common"

    if not requires_enforce_shiny_rarity_choice(options["minimum_rarity"]):
        options["enforce_rarity_on_shiny"] = True

    if not options["duo_enabled"]:
        options["duo_partner_id"] = None
        options["duo_link_id"] = None

    return options


def infer_legacy_ppe_type_from_options(options_value: Any) -> str:
    options = _disable_unpaired_duo(normalize_ppe_type_options(options_value))
    effective_minimum = minimum_rarity_effective(options["minimum_rarity"])
    if options["regular"] and not options["duo_enabled"]:
        return PPE_TYPE_REGULAR
    if options["duo_enabled"] and options["uses_pet"] and effective_minimum == "common" and options["allows_tiered"] and not options["shiny_only"]:
        return PPE_TYPE_DUO
    if options["duo_enabled"] and not options["uses_pet"] and effective_minimum == "common" and options["allows_tiered"] and not options["shiny_only"]:
        return PPE_TYPE_DUO_NO_PET
    if not options["uses_pet"] and effective_minimum == "common" and options["allows_tiered"] and not options["shiny_only"] and not options["duo_enabled"]:
        return PPE_TYPE_NO_PET
    if not options["allows_tiered"] and options["uses_pet"] and effective_minimum == "common" and not options["shiny_only"] and not options["duo_enabled"]:
        return PPE_TYPE_UT_ONLY
    if not options["allows_tiered"] and not options["uses_pet"] and effective_minimum == "common" and not options["shiny_only"] and not options["duo_enabled"]:
        return PPE_TYPE_UT_NO_PET
    if effective_minimum == "divine" and options["shiny_only"] and options["uses_pet"] and not options["duo_enabled"]:
        return PPE_TYPE_DIVINE_SHINY
    if effective_minimum == "divine" and options["shiny_only"] and not options["uses_pet"] and not options["duo_enabled"]:
        return PPE_TYPE_DIVINE_SHINY_NO_PET
    if effective_minimum == "divine" and not options["shiny_only"] and options["uses_pet"] and not options["duo_enabled"]:
        return PPE_TYPE_DIVINE_ONLY
    if effective_minimum == "divine" and not options["shiny_only"] and not options["uses_pet"] and not options["duo_enabled"]:
        return PPE_TYPE_DIVINE_NO_PET
    if effective_minimum == "legendary" and not options["shiny_only"] and options["uses_pet"] and not options["duo_enabled"]:
        return PPE_TYPE_LEGENDARY_OR_SHINY
    if effective_minimum == "legendary" and not options["shiny_only"] and not options["uses_pet"] and not options["duo_enabled"]:
        return PPE_TYPE_LEGENDARY_OR_SHINY_NO_PET
    if options["shiny_only"] and effective_minimum == "common" and options["uses_pet"] and not options["duo_enabled"]:
        return PPE_TYPE_SHINY_ONLY
    if options["shiny_only"] and effective_minimum == "common" and not options["uses_pet"] and not options["duo_enabled"]:
        return PPE_TYPE_SHINY_NO_PET
    return DEFAULT_PPE_TYPE


def ppe_type_option_signature(options_value: Any, *, include_regular: bool = False) -> str:
    options = _disable_unpaired_duo(normalize_ppe_type_options(options_value))
    if options["regular"] and not options["duo_enabled"]:
        return "regular"

    tokens: list[str] = []
    if include_regular:
        tokens.append(f"regular:{'yes' if options['regular'] else 'no'}")
    tokens.extend(
        [
            f"pet:{'yes' if options['uses_pet'] else 'no'}",
            f"tiered:{'yes' if options['allows_tiered'] else 'no'}",
            f"minimum:{options['minimum_rarity']}",
            f"shiny:{'yes' if options['shiny_only'] else 'no'}",
            f"enforce_shiny_rarity:{'yes' if options['enforce_rarity_on_shiny'] else 'no'}",
            f"duo:{'yes' if options['duo_enabled'] else 'no'}",
        ]
    )
    return "|".join(tokens)


def normalize_iterative_option_multipliers(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}

    def _positive_float(input_value: Any, fallback: float) -> float:
        try:
            parsed = float(input_value)
        except (TypeError, ValueError):
            return fallback
        return parsed if parsed > 0 else fallback

    rarity_defaults = DEFAULT_ITERATIVE_OPTION_MULTIPLIERS["minimum_rarity"]
    raw_rarities = raw.get("minimum_rarity", {}) if isinstance(raw.get("minimum_rarity", {}), dict) else {}
    normalized_rarity: dict[str, float] = {}
    for rarity in PPE_MIN_RARITY_ORDER:
        normalized_rarity[rarity] = _positive_float(raw_rarities.get(rarity), rarity_defaults[rarity])
    normalized_rarity["all_shinies_allowed"] = normalized_rarity["common"]

    return {
        "no_pet": _positive_float(raw.get("no_pet"), DEFAULT_ITERATIVE_OPTION_MULTIPLIERS["no_pet"]),
        "no_tiered": _positive_float(raw.get("no_tiered"), DEFAULT_ITERATIVE_OPTION_MULTIPLIERS["no_tiered"]),
        "minimum_rarity": normalized_rarity,
        "shiny_only": _positive_float(raw.get("shiny_only"), DEFAULT_ITERATIVE_OPTION_MULTIPLIERS["shiny_only"]),
        "enforce_shiny_rarity": _positive_float(raw.get("enforce_shiny_rarity"), DEFAULT_ITERATIVE_OPTION_MULTIPLIERS["enforce_shiny_rarity"]),
        "duo": _positive_float(raw.get("duo"), DEFAULT_ITERATIVE_OPTION_MULTIPLIERS["duo"]),
    }


def _as_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _format_multiplier(value: float) -> str:
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return f"{int(rounded)}x"
    return f"{rounded:.2f}".rstrip("0").rstrip(".") + "x"


def normalize_combo_signature(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if text == "regular":
        return "regular"

    parsed = options_from_signature(text)
    if isinstance(parsed, dict):
        return ppe_type_option_signature(parsed)
    return text


def normalize_cleared_combo_signatures(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    seen: set[str] = set()
    normalized: list[str] = []
    for raw_signature in value:
        signature = normalize_combo_signature(raw_signature)
        if not signature or signature in seen:
            continue
        seen.add(signature)
        normalized.append(signature)
    return sorted(normalized)


def normalize_iterative_combo_overrides(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, float] = {}
    for raw_signature, raw_multiplier in value.items():
        if not isinstance(raw_signature, str):
            continue
        signature = normalize_combo_signature(raw_signature)
        if not signature:
            continue
        try:
            multiplier = float(raw_multiplier)
        except (TypeError, ValueError):
            continue
        if multiplier <= 0:
            continue
        normalized[signature] = multiplier
    return normalized


def normalize_ppe_type_label_overrides(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for raw_key, raw_label in value.items():
        ppe_type = normalize_ppe_type(raw_key)
        if ppe_type not in PPE_TYPE_ORDER:
            continue
        label = str(raw_label or "").strip()
        if not label:
            continue
        normalized[ppe_type] = label
    return normalized


def normalize_ppe_type_short_label_overrides(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for raw_key, raw_label in value.items():
        ppe_type = normalize_ppe_type(raw_key)
        if ppe_type not in PPE_TYPE_ORDER:
            continue
        label = str(raw_label or "").strip()
        if not label:
            continue
        normalized[ppe_type] = label
    return normalized


def normalize_ppe_combo_label_overrides(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, dict[str, str]] = {}
    for raw_signature, raw_entry in value.items():
        if not isinstance(raw_signature, str):
            continue
        signature = normalize_combo_signature(raw_signature)
        if not signature:
            continue
        entry = raw_entry if isinstance(raw_entry, dict) else {}
        name = str(entry.get("name", "")).strip()
        short = str(entry.get("short", "")).strip()
        if not name and not short:
            continue
        normalized[signature] = {"name": name, "short": short}
    return normalized


def find_combo_label_override(value: Any, ppe_settings: Any = None) -> tuple[str, dict[str, str]] | None:
    settings = _ppe_settings_dict(ppe_settings)
    overrides = normalize_ppe_combo_label_overrides(settings.get("combo_label_overrides"))
    needle = str(value or "").strip().lower()
    if not needle:
        return None

    if needle in overrides:
        return needle, overrides[needle]

    for signature, entry in overrides.items():
        if not isinstance(entry, dict):
            continue
        short_label = str(entry.get("short", "")).strip().lower()
        display_name = str(entry.get("name", "")).strip().lower()
        if needle == short_label or needle == display_name:
            return signature, entry

    return None


def find_ppe_type_by_label(value: Any, ppe_settings: Any = None) -> str | None:
    settings = _ppe_settings_dict(ppe_settings)
    needle = str(value or "").strip().casefold()
    if not needle:
        return None

    for ppe_type in all_ppe_types():
        if needle == ppe_type_label_with_overrides(ppe_type, settings).strip().casefold():
            return ppe_type
        if needle == ppe_type_short_label_with_overrides(ppe_type, settings).strip().casefold():
            return ppe_type

    return None


def _ppe_settings_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _combo_display_override(signature: str, ppe_settings: Any, *, compact: bool) -> str | None:
    settings = _ppe_settings_dict(ppe_settings)
    overrides = normalize_ppe_combo_label_overrides(settings.get("combo_label_overrides"))
    entry = overrides.get(normalize_combo_signature(signature))
    if not isinstance(entry, dict):
        return None
    key = "short" if compact else "name"
    value = str(entry.get(key, "")).strip()
    if value:
        return value
    fallback_key = "name" if compact else "short"
    fallback = str(entry.get(fallback_key, "")).strip()
    return fallback or None


def ppe_type_compact_summary(options_value: Any, *, fallback_type: Any = None, ppe_settings: Any = None) -> str:
    options = normalize_ppe_type_options(options_value, current_type=fallback_type)
    if options["duo_enabled"]:
        options_without_duo = dict(options)
        options_without_duo["duo_enabled"] = False
        options_without_duo["duo_partner_id"] = None
        options_without_duo["duo_link_id"] = None

        base_signature = ppe_type_option_signature(options_without_duo)
        custom_combo_short = _combo_display_override(base_signature, ppe_settings, compact=True)
        if custom_combo_short:
            return f"Duo {custom_combo_short}"

        base_short = ppe_type_compact_summary(options_without_duo, ppe_settings=ppe_settings)
        return f"Duo {base_short}"

    signature = ppe_type_option_signature(options)
    custom_combo_short = _combo_display_override(signature, ppe_settings, compact=True)
    if custom_combo_short:
        return custom_combo_short

    legacy_type = infer_legacy_ppe_type_from_options(options)

    base = ppe_type_short_label(legacy_type, ppe_settings=ppe_settings)
    minimum_effective = minimum_rarity_effective(options.get("minimum_rarity"))
    base_without_shiny = {
        PPE_TYPE_LEGENDARY_OR_SHINY: "LPE",
        PPE_TYPE_LEGENDARY_OR_SHINY_NO_PET: "LNPE",
    }.get(legacy_type, base)

    # For legendary/divine minimums, surface the All_SH prefix only when shiny
    # items bypass the rarity floor (enforce_rarity_on_shiny = False).
    if (
        legacy_type in {PPE_TYPE_LEGENDARY_OR_SHINY, PPE_TYPE_LEGENDARY_OR_SHINY_NO_PET}
        and minimum_effective in {"legendary", "divine"}
        and options["enforce_rarity_on_shiny"]
    ):
        base = base_without_shiny

    show_all_sh_prefix = (
        (not options["shiny_only"])
        and (not options["enforce_rarity_on_shiny"])
        and minimum_effective in {"legendary", "divine"}
    )
    if show_all_sh_prefix:
        # No dedicated preset exists for "minimum rarity + all shinies allowed" variants,
        # so surface it explicitly in the compact display.
        return f"All_SH|{base_without_shiny}"

    if legacy_type != DEFAULT_PPE_TYPE:
        return base

    shorthand = {
        "uncommon": "Unc",
        "rare": "Rare",
        "legendary": "Leg",
        "divine": "Div",
    }
    tokens: list[str] = []
    if not options["uses_pet"]:
        tokens.append("NPE")
    if not options["allows_tiered"]:
        tokens.append("UT")
    rarity = normalize_minimum_rarity(options.get("minimum_rarity"))
    if options["shiny_only"] and options["enforce_rarity_on_shiny"]:
        rarity_label = shorthand.get(rarity, rarity.capitalize())
        tokens.append(f"SH_Only_{rarity_label}+")
    elif options["shiny_only"]:
        tokens.append("SH_Only")
    else:
        # Rule 3: Not Shiny Only - check rarity and add "or SH" if ERS is missing
        if rarity != "common":
            if not options["enforce_rarity_on_shiny"]:
                label = shorthand.get(rarity, rarity.capitalize())
                tokens.append(f"{label}/All_SH")
            else: # Regular PPE with minimum rarity but no shiny rules.
                rarity_token = {
                    "uncommon": "Unc+",
                    "rare": "Rare+",
                    "legendary": "Leg+",
                    "divine": "DivOnly",
                }.get(rarity, rarity[:1].upper())
                tokens.append(f"{rarity_token}")
    if not tokens:
        return base
    return f"{base}|{'|'.join(tokens)}"


def compute_iterative_multiplier(
    options_value: Any,
    multipliers_value: Any,
) -> tuple[float, str, str]:
    breakdown = iterative_multiplier_breakdown(options_value, multipliers_value)
    return float(breakdown["multiplier"]), "base", str(breakdown["signature"])


def iterative_multiplier_breakdown(
    options_value: Any,
    multipliers_value: Any,
) -> dict[str, Any]:
    options = _disable_unpaired_duo(normalize_ppe_type_options(options_value))
    signature = ppe_type_option_signature(options)
    multipliers = normalize_iterative_option_multipliers(multipliers_value)

    components: list[dict[str, Any]] = []
    multiplier = 1.0

    if not options["uses_pet"]:
        value = float(multipliers["no_pet"])
        multiplier *= value
        components.append({"key": "no_pet", "label": "No Pet", "multiplier": value})

    if not options["allows_tiered"]:
        value = float(multipliers["no_tiered"])
        multiplier *= value
        components.append({"key": "no_tiered", "label": "No Tiered", "multiplier": value})

    minimum_rarity = normalize_minimum_rarity(options.get("minimum_rarity"))
    minimum_rarity_effective_value = minimum_rarity_effective(minimum_rarity)
    rarity_multiplier = float(multipliers["minimum_rarity"][minimum_rarity_effective_value])
    minimum_rarity_label = "All Shinies Allowed" if minimum_rarity == "all_shinies_allowed" else minimum_rarity.title()
    multiplier *= rarity_multiplier
    if minimum_rarity_effective_value != "common" or rarity_multiplier != 1.0:
        components.append(
            {
                "key": "minimum_rarity",
                "label": f"Minimum Rarity ({minimum_rarity_label})",
                "multiplier": rarity_multiplier,
            }
        )

    if options["shiny_only"]:
        shiny_multiplier = float(multipliers["shiny_only"])
        multiplier *= shiny_multiplier
        components.append(
            {
                "key": "shiny_only",
                "label": "Shiny Only",
                "multiplier": shiny_multiplier,
            }
        )

    enforce_power = 0
    if not options["enforce_rarity_on_shiny"]:
        if minimum_rarity_effective_value == "legendary":
            enforce_power = 1
        elif minimum_rarity_effective_value == "divine":
            enforce_power = 2

    if enforce_power > 0:
        enforce_base = float(multipliers["enforce_shiny_rarity"])
        enforce_multiplier = float(enforce_base ** enforce_power)
        multiplier *= enforce_multiplier
        apply_label = "once" if enforce_power == 1 else "twice"
        components.append(
            {
                "key": "enforce_shiny_rarity",
                "label": f"Enforce Shiny Rarity Off ({minimum_rarity_label}, {apply_label})",
                "multiplier": enforce_multiplier,
            }
        )

    if options["duo_enabled"]:
        value = float(multipliers["duo"])
        multiplier *= value
        components.append({"key": "duo", "label": "Duo", "multiplier": value})

    return {
        "multiplier": float(multiplier),
        "signature": signature,
        "components": components,
    }


def resolve_legacy_ppe_type_from_options(options_value: Any, *, current_type: Any = None) -> str | None:
    options = _disable_unpaired_duo(normalize_ppe_type_options(options_value, current_type=current_type))

    # For shiny-only presets at common/all-shinies, enforcing rarity on shinies is
    # a wizard-side toggle that should not block legacy preset resolution.
    effective_minimum = minimum_rarity_effective(options.get("minimum_rarity"))
    if options.get("shiny_only") and effective_minimum == "common":
        options = dict(options)
        options["enforce_rarity_on_shiny"] = False

    legacy_type = infer_legacy_ppe_type_from_options(options)
    canonical_options = legacy_ppe_type_to_options(legacy_type)
    if ppe_type_option_signature(options) == ppe_type_option_signature(canonical_options):
        return legacy_type
    return None


def get_ppe_type_multiplier_details_from_options(
    options_value: Any,
    ppe_settings: Any = None,
    *,
    current_type: Any = None,
) -> dict[str, Any]:
    settings = ppe_settings if isinstance(ppe_settings, dict) else {}
    normalized_options = _disable_unpaired_duo(normalize_ppe_type_options(options_value, current_type=current_type))
    signature = ppe_type_option_signature(normalized_options)
    cleared_signatures = set(normalize_cleared_combo_signatures(settings.get("iterative_cleared_signatures")))

    if normalized_options["duo_enabled"]:
        options_without_duo = dict(normalized_options)
        options_without_duo["duo_enabled"] = False
        options_without_duo["duo_partner_id"] = None
        options_without_duo["duo_link_id"] = None
        base_signature = ppe_type_option_signature(options_without_duo)
        base_legacy_type = resolve_legacy_ppe_type_from_options(options_without_duo, current_type=current_type)

        base_source = "base"
        base_components: list[dict[str, Any]] = []
        base_component_lines: list[str] = []
        normalized_overrides = normalize_iterative_combo_overrides(settings.get("iterative_combo_overrides"))
        override_multiplier = normalized_overrides.get(base_signature)
        if override_multiplier is not None:
            base_source = "override"
            base_breakdown = iterative_multiplier_breakdown(options_without_duo, settings.get("iterative_base_multipliers"))
            base_multiplier = float(override_multiplier)
            base_components = list(base_breakdown.get("components", []))
            base_component_lines = [
                "Base Combo Override Applied (duo flag ignored for override lookup).",
                f"Base Override Multiplier: {_format_multiplier(base_multiplier)}",
            ]
        elif base_legacy_type is not None and base_signature not in cleared_signatures:
            base_source = "preset"
            legacy_multipliers = normalize_ppe_type_multipliers(settings.get("ppe_type_multipliers"))
            base_multiplier = float(legacy_multipliers.get(base_legacy_type, DEFAULT_PPE_TYPE_MULTIPLIERS[DEFAULT_PPE_TYPE]))
            base_component_lines = [
                "Base legacy PPE preset applied (duo flag ignored for preset lookup).",
                f"Base Preset Multiplier: {_format_multiplier(base_multiplier)}",
            ]
        else:
            base_breakdown = iterative_multiplier_breakdown(options_without_duo, settings.get("iterative_base_multipliers"))
            base_multiplier = float(base_breakdown["multiplier"])
            base_components = list(base_breakdown.get("components", []))
            base_component_lines = [
                f"Base {str(component.get('label', 'Component')).strip()}: {_format_multiplier(_as_float(component.get('multiplier'), 1.0))}"
                for component in base_components
                if isinstance(component, dict)
            ]

        duo_multiplier = float(normalize_iterative_option_multipliers(settings.get("iterative_base_multipliers"))["duo"])
        final_multiplier = float(base_multiplier * duo_multiplier)
        components = [
            *base_components,
            {"key": "duo", "label": "Duo", "multiplier": duo_multiplier},
        ]
        component_lines = [
            *base_component_lines,
            f"Duo: {_format_multiplier(duo_multiplier)}",
            f"Final Type Multiplier: {_format_multiplier(base_multiplier)} × {_format_multiplier(duo_multiplier)} = {_format_multiplier(final_multiplier)}",
        ]
        return {
            "multiplier": final_multiplier,
            "source": base_source,
            "signature": signature,
            "legacy_type": base_legacy_type,
            "components": components,
            "component_lines": component_lines,
        }

    legacy_type = resolve_legacy_ppe_type_from_options(normalized_options, current_type=current_type)

    normalized_overrides = normalize_iterative_combo_overrides(settings.get("iterative_combo_overrides"))
    override_multiplier = normalized_overrides.get(signature)
    if override_multiplier is not None:
        base_breakdown = iterative_multiplier_breakdown(normalized_options, settings.get("iterative_base_multipliers"))
        return {
            "multiplier": float(override_multiplier),
            "source": "override",
            "signature": signature,
            "legacy_type": legacy_type,
            "components": base_breakdown.get("components", []),
            "component_lines": [
                "Combo Override Applied (replaces iterative stack).",
                f"Override Multiplier: {_format_multiplier(float(override_multiplier))}",
            ],
        }

    if legacy_type is not None and signature not in cleared_signatures:
        legacy_multipliers = normalize_ppe_type_multipliers(settings.get("ppe_type_multipliers"))
        multiplier = float(legacy_multipliers.get(legacy_type, DEFAULT_PPE_TYPE_MULTIPLIERS[DEFAULT_PPE_TYPE]))
        return {
            "multiplier": multiplier,
            "source": "preset",
            "signature": signature,
            "legacy_type": legacy_type,
            "components": [],
            "component_lines": [
                "Legacy PPE type preset applied.",
                f"Preset Multiplier: {_format_multiplier(multiplier)}",
            ],
        }

    base_breakdown = iterative_multiplier_breakdown(normalized_options, settings.get("iterative_base_multipliers"))
    component_lines = [
        f"{str(component.get('label', 'Component')).strip()}: {_format_multiplier(_as_float(component.get('multiplier'), 1.0))}"
        for component in base_breakdown.get("components", [])
        if isinstance(component, dict)
    ]
    return {
        "multiplier": float(base_breakdown["multiplier"]),
        "source": "base",
        "signature": str(base_breakdown["signature"]),
        "legacy_type": legacy_type,
        "components": base_breakdown.get("components", []),
        "component_lines": component_lines,
    }


def ppe_type_label(ppe_type: str, ppe_settings: Any = None) -> str:
    return ppe_type_label_with_overrides(ppe_type, ppe_settings=ppe_settings)


def ppe_type_short_label(ppe_type: str, ppe_settings: Any = None) -> str:
    return ppe_type_short_label_with_overrides(ppe_type, ppe_settings=ppe_settings)


def ppe_type_label_with_overrides(ppe_type: Any, ppe_settings: Any) -> str:
    normalized = normalize_ppe_type(ppe_type)
    settings = _ppe_settings_dict(ppe_settings)
    overrides = normalize_ppe_type_label_overrides(settings.get("type_label_overrides"))
    if normalized in overrides:
        return overrides[normalized]
    return PPE_TYPE_LABELS.get(normalized, PPE_TYPE_LABELS[DEFAULT_PPE_TYPE])


def ppe_type_short_label_with_overrides(ppe_type: Any, ppe_settings: Any) -> str:
    normalized = normalize_ppe_type(ppe_type)
    settings = _ppe_settings_dict(ppe_settings)
    overrides = normalize_ppe_type_short_label_overrides(settings.get("type_short_label_overrides"))
    if normalized in overrides:
        return overrides[normalized]
    return PPE_TYPE_SHORT_LABELS.get(normalized, PPE_TYPE_SHORT_LABELS[DEFAULT_PPE_TYPE])


def ppe_type_display_label(ppe_type: str, *, compact: bool = False) -> str:
    if compact:
        return ppe_type_short_label_with_overrides(ppe_type, ppe_settings=None)
    return ppe_type_label_with_overrides(ppe_type, ppe_settings=None)


def ppe_type_display_from_options(
    options_value: Any,
    *,
    fallback_type: Any = None,
    ppe_settings: Any = None,
    compact: bool = False,
) -> str:
    options = normalize_ppe_type_options(options_value, current_type=fallback_type)
    signature = ppe_type_option_signature(options)
    combo_override = _combo_display_override(signature, ppe_settings, compact=compact)
    if combo_override:
        return combo_override

    legacy_type = infer_legacy_ppe_type_from_options(options)
    if compact:
        return ppe_type_compact_summary(options, fallback_type=legacy_type, ppe_settings=ppe_settings)

    resolved_legacy = resolve_legacy_ppe_type_from_options(options, current_type=fallback_type)
    full = "Custom PPE" if resolved_legacy is None else ppe_type_label_with_overrides(resolved_legacy, ppe_settings)
    short = ppe_type_compact_summary(options, fallback_type=legacy_type, ppe_settings=ppe_settings)
    if full == short:
        return full
    return f"{full} ({short})"


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
        PPE_TYPE_DUO_NO_PET: PPE_TYPE_DUO_NO_PET,
        "duo_no_pet_ppe": PPE_TYPE_DUO_NO_PET,
        "duo_no_pet": PPE_TYPE_DUO_NO_PET,
        "duonopet": PPE_TYPE_DUO_NO_PET,
        PPE_TYPE_DIVINE_ONLY: PPE_TYPE_DIVINE_ONLY,
        "dpe": PPE_TYPE_DIVINE_ONLY,
        "divineonly": PPE_TYPE_DIVINE_ONLY,
        "divine_only_ppe": PPE_TYPE_DIVINE_ONLY,
        PPE_TYPE_DIVINE_NO_PET: PPE_TYPE_DIVINE_NO_PET,
        "divine_no_pet_ppe": PPE_TYPE_DIVINE_NO_PET,
        "divine_no_pet": PPE_TYPE_DIVINE_NO_PET,
        "divinenopet": PPE_TYPE_DIVINE_NO_PET,
        PPE_TYPE_UT_ONLY: PPE_TYPE_UT_ONLY,
        "upe": PPE_TYPE_UT_ONLY,
        "utonly": PPE_TYPE_UT_ONLY,
        "ut_only_ppe": PPE_TYPE_UT_ONLY,
        PPE_TYPE_UT_NO_PET: PPE_TYPE_UT_NO_PET,
        "ut_no_pet_ppe": PPE_TYPE_UT_NO_PET,
        "ut_only_and_no_pet_ppe": PPE_TYPE_UT_NO_PET,
        "ut_no_pet": PPE_TYPE_UT_NO_PET,
        "utnopet": PPE_TYPE_UT_NO_PET,
        PPE_TYPE_SHINY_ONLY: PPE_TYPE_SHINY_ONLY,
        "spe": PPE_TYPE_SHINY_ONLY,
        "shinyonly": PPE_TYPE_SHINY_ONLY,
        "shiny_only_ppe": PPE_TYPE_SHINY_ONLY,
        PPE_TYPE_SHINY_NO_PET: PPE_TYPE_SHINY_NO_PET,
        "shiny_no_pet_ppe": PPE_TYPE_SHINY_NO_PET,
        "shiny_no_pet": PPE_TYPE_SHINY_NO_PET,
        "shinynopet": PPE_TYPE_SHINY_NO_PET,
        PPE_TYPE_LEGENDARY_OR_SHINY: PPE_TYPE_LEGENDARY_OR_SHINY,
        "legendary_or_shiny_ppe": PPE_TYPE_LEGENDARY_OR_SHINY,
        "legendary_or_shiny": PPE_TYPE_LEGENDARY_OR_SHINY,
        "legendaryorshiny": PPE_TYPE_LEGENDARY_OR_SHINY,
        "slpe": PPE_TYPE_LEGENDARY_OR_SHINY,
        PPE_TYPE_LEGENDARY_OR_SHINY_NO_PET: PPE_TYPE_LEGENDARY_OR_SHINY_NO_PET,
        "legendary_or_shiny_no_pet": PPE_TYPE_LEGENDARY_OR_SHINY_NO_PET,
        "legendary_or_shiny_no_pet_ppe": PPE_TYPE_LEGENDARY_OR_SHINY_NO_PET,
        "legendary_or_shiny_and_no_pet": PPE_TYPE_LEGENDARY_OR_SHINY_NO_PET,
        "legendaryorshinynopet": PPE_TYPE_LEGENDARY_OR_SHINY_NO_PET,
        "slnpe": PPE_TYPE_LEGENDARY_OR_SHINY_NO_PET,
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
        PPE_TYPE_DIVINE_SHINY_NO_PET: PPE_TYPE_DIVINE_SHINY_NO_PET,
        "divine_shiny_no_pet_ppe": PPE_TYPE_DIVINE_SHINY_NO_PET,
        "divine_shiny_no_pet": PPE_TYPE_DIVINE_SHINY_NO_PET,
        "divine_and_shiny_and_no_pet": PPE_TYPE_DIVINE_SHINY_NO_PET,
        "divine_and_shiny_no_pet_ppe": PPE_TYPE_DIVINE_SHINY_NO_PET,
        "divineshynopet": PPE_TYPE_DIVINE_SHINY_NO_PET,
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
