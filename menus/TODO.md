# Menus Refactor TODO

This backlog captures the remaining work needed to make all menu packages conform to the architecture rules in `menus/README.md`.

## Completed in this pass

- [x] Split sniffer command menus into dedicated packages: `menus/mysniffer` and `menus/managesniffer`.
- [x] Moved shared sniffer settings/token helpers into `menus/menu_utils/sniffer_shared.py`.
- [x] Updated slash command wiring to import from `menus.mysniffer` and `menus.managesniffer`.
- [x] Removed `menus/sniffer` compatibility wrappers after migrating active call sites.
- [x] Created `SafeResponse` helper class in `menus/menu_utils/safe_response.py` for centralized interaction response handling.
- [x] Refactored `menus/myquests`: Added `entry.py`, renamed `view.py` to `views.py`, made `__init__.py` export-only.
- [x] Refactored `menus/myinfo`: Split into submenus for `character`, `home`, and `season` with canonical implementations and compatibility shims.
- [x] Refactored `menus/managequests`: Split `views.py` into submenus (`home`, `global_quests`, `player_reset`), converted to shim.
- [x] Refactored `menus/manageseason`: Split `views.py` into submenus (`reset`, `home`, `contests`, `points`), converted to shim.
- [x] Refactored `menus/manageteams`: Split `views.py` into submenus (`home`, `team_picker`, `team_detail`, `confirmations`, `leaderboard`), converted to shim.

## Cross-Cutting (All Menus)

- [x] Standardize package entrypoints so every command package uses `entry.py` + export-only `__init__.py`.
- [x] Migrate legacy `*_view.py` naming to `views.py` in command packages still using old filenames.
- [x] Eliminate thin pass-through wrappers once call sites are migrated (track and remove compatibility modules deliberately).
- [x] Remove any unnecessary shims and legacy code.
- [x] Add a shared interaction response helper (safe send/edit/followup) in `menus/menu_utils` to reduce repeated `response.is_done()` branches.
- [ ] Avoid repeating self when possible and centralize shared functionalities, using design patterns such as builders or views where needed.

## `menus/leaderboard`

- [x] Split leaderboard command handlers (`characterleaderboard.py`, `ppeleaderboard.py`, `questleaderboard.py`, `seasonleaderboard.py`, `teamleaderboard.py`, `contestleaderboard.py`) into `services.py` + thin command/view orchestration modules.
- [x] Create `submenus/character/` for class-selection flow so class select state is isolated from home view logic.
- [x] Move repeated guild/member display-name lookup into shared helper(s) to avoid per-command duplication.
- [x] Ensure all error paths in command handlers use one consistent response method (currently mixed direct `send_message` and helper usage).

## `menus/myinfo` ✅ COMPLETE

Architecture standardized:
- `entry.py`: Entry point functions
- `__init__.py`: Export-only
- `submenus/character/`: CharacterLootVariantView, ManageCharactersView, modals
- `submenus/home/`: MyInfoHomeView, MyInfoTeamView, NoCharactersView
- `submenus/season/`: SeasonLootVariantView

Remaining: Move `/slash_commands.newppe_cmd` calls behind service interfaces (minor refactoring).

## `menus/manageplayer`

- [x] Break `home_view.py`, `character_view.py`, and `team_view.py` into real submenu modules under `submenus/`.
- [x] Replace placeholder re-export wrappers in `submenus/home` and `submenus/character` with canonical implementations.
- [ ] Extract shared character carousel behavior with `myinfo` into reusable controller/policy hooks (avoid duplicated carousel/action logic).
- [x] Remove fallback constants in views (for example default `max_ppes` fallbacks) and require explicit data from services.
- [ ] Move role-management side effects from view callbacks into service layer transaction helpers.

## `menus/myquests` ✅ COMPLETE

Architecture standardized:
- `entry.py`: open_myquests_menu() and open_myquests_menu_for_player() entry points
- `views.py`: MyQuestsView class
- `__init__.py`: Export-only

Remaining: Refactor `common.py` to separate concerns (state/data loading → `services.py`; embed formatting → `common.py`).

## `menus/managequests` ✅ COMPLETE

Architecture refactored:
- `entry.py`: Entry point functions
- `__init__.py`: Export-only
- `submenus/home/`: ManageQuestsHomeView
- `submenus/global_quests/`: GlobalQuestsView with dynamic button wiring
- `submenus/player_reset/`: ManagePlayerQuestsPromptModal, ManagePlayerQuestsView

Remaining: Extract validators for parsing logic and move mutation side effects to services.

## `menus/manageseason` ✅ COMPLETE

Architecture refactored:
- `entry.py`: Entry point functions
- `__init__.py`: Export-only
- `submenus/home/`: ManageSeasonHomeView with admin permission checks
- `submenus/reset/`: ResetSeasonModeView with confirmation flow
- `submenus/contests/`: ManageContestsHomeView, SetContestTypeView, LeaderboardManagerView
- `submenus/points/`: ManagePointSettingsView, ManageGlobalPointSettingsView, ManageClassPointSettingsView, _ClassModifierSelect

Remaining: Fix button-state styling in SetContestTypeView and move reset side effects to services.

## `menus/manageteams` ✅ COMPLETE

Architecture refactored:
- `entry.py`: Entry point functions
- `__init__.py`: Export-only
- `submenus/home/`: ManageTeamsHomeView with pagination and leaderboard access
- `submenus/team_picker/`: TeamPickerView with dropdown or lookup
- `submenus/team_detail/`: ManageSingleTeamView, TeamInfoPreviewView
- `submenus/confirmations/`: TeamDeleteConfirmView
- `submenus/leaderboard/`: LeaderboardPreviewView

Remaining: Move Discord role create/delete/add/remove side effects from views to services.

## `menus/mysniffer`

- [x] Add a dedicated `services.py` for player-specific orchestration (`load user state`, `generate token`, `revoke token`) instead of importing shared helpers directly in views.
- [ ] Consider moving token unlink select component to reusable utility if used by additional user-facing menus.

## `menus/managesniffer`

- [x] Split large `views.py` into submenus (`home`, `tokens`, `player_manage`, `output_channel`, `danger_confirm`).
- [x] Move token delete confirmation flow into a reusable confirmation helper to avoid duplicated ephemeral confirm code.
- [x] Add typed payload/model objects for token listing rows to avoid loose `dict[str, Any]` plumbing.

## `menus/menu_utils/sniffer_core` (Shared RealmShark Core)

- [ ] Break `core.py` into multiple modules by responsibility (`panel_views`, `panel_services`, `admin_panel`, `mapping_actions`).
- [x] Move shared RealmShark core out of `menus/sniffer` into `menus/menu_utils/sniffer_core` and migrate active imports.
- [ ] Remove duplicated helper implementations between `realmshark_common.py` and `menus/menu_utils/sniffer_shared.py` where practical.

## `menus/menu_utils`

- [ ] Add shared helpers for repeated patterns now duplicated across menus (safe response/edit/followup helper; standard close/cancel/back button mixins; reusable member/team lookup parsing utilities).
- [ ] Expand documentation/comments in utility modules to clarify intended reuse boundaries.

## `menus/__init__.py`

- [x] The root `menus/__init__.py` should export entrypoints as needed.