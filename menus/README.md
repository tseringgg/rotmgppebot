# Menus Architecture Guide

This document defines how interactive Discord menu modules under `menus/` should be structured and refactored.

## Core Interaction Flow

Use this flow for all menu workflows:

`slash command -> menu entrypoint -> submenu entry/view -> services -> embed builder -> response`

Rules:
- Entrypoints perform permission/context validation and open initial screens.
- Views route interactions only.
- Services own mutations and data retrieval.
- Common modules build embeds/formatting and hold pure helpers.

## Package Roles

Command menus should live in **their own top-level package** under `menus/`.

Current command packages:
- `menus/myinfo`
- `menus/manageplayer`
- `menus/myquests`
- `menus/managequests`
- `menus/manageteams`
- `menus/manageseason`
- `menus/leaderboard`
- `menus/mysniffer`
- `menus/managesniffer`

Shared/support packages:
- `menus/menu_utils`: reusable UI and menu helpers used by multiple domains.
- `menus/menu_utils/sniffer_core`: shared RealmShark panel/admin core used by `/mysniffer` and `/managesniffer`.

## Menu and Submenu Model

### Menu Package

A menu package is one command workflow domain.

Minimum:
- `entry.py` for public open functions (`open_*_menu`).
- `__init__.py` exports only public entrypoints.
- `views.py` for primary top-level view(s), unless package is small enough to keep views in one clearly named file.

A submenu package is one screen cluster with its own behavior contract (for example: `home`, `character`, `season`).

Use submenu packages when a screen has meaningful state, handlers, modals, or mutations.

Target shape:

```text
menus/<menu_name>/
  __init__.py
  entry.py
  submenus/
    <submenu_name>/
      __init__.py
      entry.py       # open_<submenu>(...)
      views.py       # View classes and routing only
      modals.py      # Modal classes only
      services.py    # Mutations + data operations
      common.py      # Embed builders + pure helpers
      validators.py  # Optional parsing/validation helpers
```

Small menus can stay flat, but complex/large flows should migrate to `submenus/`.

### Naming Rules

- Prefer `views.py` over `<name>_view.py`.
- Prefer `entry.py` over placing entrypoint code in `__init__.py`.
- Keep `__init__.py` export-only.

## Manage Menu Extension Pattern

Default pattern for user/admin pairs:
- Build the canonical submenu behavior in the user-facing menu (or a neutral shared module).
- Have the manage/admin submenu extend it with policy/permission overrides and manage-only actions.
- Keep target resolution and authorization in manage-specific modules.

Example target direction:

```text
menus/myinfo/submenus/character/...
menus/manageplayer/submenus/character/...
```

`manageplayer` should subclass or compose the `myinfo` character submenu behavior, adding admin-only actions without duplicating base carousel/render logic.

If inheritance becomes awkward, use composition with a shared controller + injected policy hooks.

## Responsibilities by File

- `entry.py`: public open functions, guard checks, initial view handoff.
- `views.py`: UI wiring, callbacks, navigation, lightweight orchestration.
- `modals.py`: user input capture and validation dispatch.
- `services.py`: all persistence mutations, cross-entity updates, and data loading helpers.
- `common.py`: pure/side-effect-light embed builders, labels, formatting helpers.
- `validators.py`: parse/validate raw inputs; no business side effects.

## Button Color Semantics

- Blue (`primary`): informational view/open/read actions.
- Green (`success`): beneficial mutations (add/enable/configure/apply).
- Red (`danger`): destructive/reset/remove operations.
- Grey (`secondary`): neutral navigation/utility actions (next/prev/back/refresh/close/cancel).

Keep similar colors grouped when practical. Keep `Close`/`Cancel` at the end of row layout.

## Existing Shared Utilities

- `menus/menu_utils/base_views.py`: owner-bound interaction safety views.
- `menus/menu_utils/confirm_views.py`: reusable confirm/cancel patterns.
- `menus/menu_utils/character_carousel.py`: shared carousel index behavior.
- `menus/menu_utils/season_loot_variants.py`: shared season loot variant action view.
- `menus/menu_utils/sniffer_shared.py`: shared `/mysniffer` + `/managesniffer` settings/token helpers.
