"""
env_manager.py

The only module in epidex that reads or writes .env. Every other module
receives configuration as a SeriesConfig instance handed down from cli.py.
Nothing outside this file, and no code in cli.py besides constructing one
EnvManager and calling its public methods, should ever touch ENV_FILE or
call dotenv directly.

Public API:
    EnvManager().load() -> SeriesConfig
        Entry point. Ensures a valid .env exists for the current OS and
        returns its contents as a SeriesConfig. Internally this is where
        first-run setup, OS-change handling, and the optional edit menu
        all happen - callers don't need to know which case applied.

    EnvManager().set_download_dir(path: str) -> None
        Writes DOWNLOAD_DIR only. For callers that already have a value
        and don't need the interactive prompt flow.

    EnvManager().set_tool_path(key: str, path: str) -> None
        Writes one of YT_DLP_PATH / DENO_PATH / MKVMERGE_PATH /
        MKVPROPEDIT_PATH. Called by cli.py after dependencies.py resolves
        a binary (via PATH lookup or auto-download), so the next run
        skips resolution for that tool entirely.

How a run resolves its config (see load()):
    1. No .env file at all       -> first-run setup, all fields prompted
                                     except tool paths, which stay blank
                                     for dependencies.py to resolve.
    2. .env exists, same OS      -> optionally open the edit menu.
    3. .env exists, different OS -> if a backup exists for the current OS,
                                     offer to restore it as-is; otherwise
                                     build a fresh .env for this OS,
                                     carrying series identity over but
                                     resetting tool paths.

Backups:
    One slot per OS, filename .env.<OSName>, always overwritten - no
    timestamps, no history beyond that single slot. A backup is written
    right before the live .env for that OS is about to be replaced,
    whether by an OS switch or an in-place series-identity edit.
    Backups are checked for corruption (a line that failed to parse)
    before ever being offered as a restore target, so a hand-broken
    backup can be viewed and diagnosed but never silently restored.

Notes on optional fields:
    Tool paths can be None/unset - that's expected, not an error, since
    dependencies.py resolves them via PATH lookup or auto-download rather
    than requiring the user to type them in. LAST_OS can also be None,
    since a .env file can predate that key or be hand-edited. Unrecognized
    platform.system() output (not Linux/Windows/Darwin) is never used as
    an OS label directly; the user is asked to name it, and that name is
    sanitized since it becomes part of a filename.
"""

import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, set_key

from epidex import paths

# TODO Separate Series and App variables in .show.env and .app.env
# TODO Backup system will change too
# Its a internal module change issue so it should not ripple through other modules

@dataclass
class SeriesConfig:
    """Immutable snapshot of everything .env holds, handed to cli.py once
    per run. Required project-identity fields (series, season, series_id,
    tmdb_api_key) are always strings/ints because first-run setup forces
    them before a .env can exist at all. Everything else is optional and
    may be None - tool paths because dependencies.py self-heals them,
    download_dir because it falls back to a computed default, last_os
    because a .env could predate that key or be hand-edited."""
    series: str
    series_id: str
    season: int
    tmdb_api_key: str
    download_dir: str | None
    yt_dlp_path: str | None
    ffmpeg_path: str | None
    deno_path: str | None
    mkvmerge_path: str | None
    mkvpropedit_path: str | None
    last_os: str | None

class EnvManager:
    """Owns all reads/writes of the project's .env file.

    Usage from cli.py:
        env_manager = EnvManager()
        config = env_manager.load()            # returns SeriesConfig
        env_manager.set_tool_path("YT_DLP_PATH", resolved_path)  # after dependencies.py resolves it
    """

    ENV_FILE: Path = paths.ENV_FILE
    KNOWN_OS = frozenset({"Linux", "Windows", "Darwin"}) # immutable, shared across all instances, never meant to be mutated
    def __init__(self):
        detected = platform.system()   # 'Linux', 'Windows', 'Darwin', or possibly '' / something unrecognized
        self.current_os = detected if detected in self.KNOWN_OS else self._prompt_unknown_os(detected)
    
    def _prompt_unknown_os(self, detected: str) -> str:
        """platform.system() returned something we don't recognize (or
        nothing at all). Rather than silently using a blank/weird string as
        an OS label - which would corrupt backup filenames and LAST_OS
        comparisons - ask the user to name it themselves. The name is
        sanitized before use since it becomes a literal filename fragment
        (.env.<label>) in _backup_env()."""
        label = detected or "unrecognized"
        print(f"\nCouldn't confidently detect your OS (got: '{label}').")
        while True:
            raw = input("What would you like to call this OS? (e.g. Linux, Windows, BSD):> ").strip()
            name = self._sanitize_os_label(raw)
            if name:
                return name
            print("Enter a valid name (letters/numbers only) - it's used to tag your .env backups.")
    
    def _sanitize_os_label(self, name: str) -> str:
        """OS labels end up as literal parts of backup filenames
        (.env.<label>) and as the LAST_OS value, so filesystem-illegal
        characters must be stripped - same character set paths.py excludes
        when slugifying series names."""
        return re.sub(r'[<>:"/\\|?*]', "", name).strip()

    # ==================================================================
    # Public API
    # ==================================================================

    def load(self) -> SeriesConfig:
        """Entry point. Ensures a usable, up-to-date .env exists for the
        current OS, then returns it as a SeriesConfig.

        Branches:
          - No .env at all               -> _first_run_setup()
          - .env exists, OS unchanged    -> _edit_menu() (optional edits)
          - .env exists, OS changed      -> _os_change_setup() (fresh setup,
                                             or restore a previously-backed-
                                             up session for this OS)
        """

        if not self.ENV_FILE.exists():
            data = self._first_run_setup()                      # First run setup
        else:
            data = dotenv_values(self.ENV_FILE)                 # Pulling data from existing .env.
            saved_os = (data.get("LAST_OS") or "").strip()      # Extracting last used OS from extracted data, to compare later
            if saved_os != self.current_os:
                data = self._os_change_setup(data, saved_os)    # Sending Existing data and Last Saved OS to translate into new OS form, and keep a backup of old OS .env.
            else:
                data = self._maybe_edit(data)                   # If same OS as previous run then asks user if he want to edit. User can edit in OS change setup too
                
        return self._to_config(data)

    def set_download_dir(self, path: str) -> None:
        """Single-key update for DOWNLOAD_DIR. Intended for callers outside
        this module (e.g. a future in-app settings action) that already
        have a value in hand and don't need the interactive prompt flow."""
        set_key(str(self.ENV_FILE), "DOWNLOAD_DIR", path)

    def set_tool_path(self, key: str, path: str) -> None:
        """TLDR; managed by cli.py after dependencies.py resolves the path 
        for each applications. 
        
        Single-key update for one of YT_DLP_PATH / DENO_PATH /
        MKVMERGE_PATH / MKVPROPEDIT_PATH. Called from cli.py after
        dependencies.py resolves a binary (via PATH lookup or auto-download)
        so the next run skips resolution entirely - this is the
        self-healing writeback path. dependencies.py itself never imports
        or calls EnvManager directly; cli.py is the only orchestrator that
        talks to both modules."""
        set_key(str(self.ENV_FILE), key, path)

    def _clear_screen(self) -> None:
        """cls on Windows, clear everywhere else. Used to keep the console
        readable across the edit menu's repeated redraws and the backups
        viewer, without wiping context mid-prompt-sequence elsewhere."""
        if platform.system() == "Windows":
            subprocess.run(["cmd", "/c", "cls"], check=False)
        else:
            subprocess.run(["clear"], check=False)

    # ==================================================================
    # Internal: prompting helpers (pure input-gathering, no file I/O)
    # ==================================================================

    def _prompt_series_name(self) -> str:
        """Only inputs the Series name."""
        return input("Series name:> ").strip()

    def _prompt_full_series_info(self) -> dict:
        """Called from _first_run_setup() and from _os_change_setup() when the 
        user opts not to keep prior series identity. SEASON/SERIES_ID/API key 
        are project identity and are never blank-able here - the loop forces 
        digits for SEASON before returning."""
        print("\nSeries setup (first run):\n")
        data = {
            "TMDB_API_KEY": input("TMDB API Key:> ").strip(),
            "SERIES": self._prompt_series_name(),
            "SERIES_ID": input("TMDB Series ID:> ").strip(),
        }
        while True:
            season = input("Season number:> ").strip()
            if season.isdigit():
                data["SEASON"] = season
                break
            print("Enter digits only.")
        return data

    def _prompt_tool_paths(self, existing: dict | None = None) -> dict:
        """All four entries are optional - blank input keeps whatever was
        already in `existing` (which may itself be blank/unset, in which
        case dependencies.py's self-healing resolves it later)."""
        existing = existing or {}
        print("\nDependency paths (optional - leave blank to keep current / auto-detect):\n")
        result = {}
        for key, name in [("YT_DLP_PATH", "yt-dlp"), ("DENO_PATH", "deno"),
                           ("MKVMERGE_PATH", "mkvmerge"), ("MKVPROPEDIT_PATH", "mkvpropedit")]:
            current = existing.get(key, "") or ""
            hint = f" [{current}]" if current else ""
            entered = input(f"Enter {name}'s full path{hint}:> ").strip()
            result[key] = entered or current
        return result

    def _prompt_download_dir(self, existing: str = "") -> str:
        """Optional - blank keeps `existing`, or falls back to
        paths.get_download_dir()'s computed default (~/Downloads/<series>
        S<season>) if existing is also empty."""
        hint = f" [{existing}]" if existing else " [default: ~/Downloads/<series> S<season>]"
        entered = input(f"Download folder{hint}, leave blank to keep as it is:> ").strip()
        return entered or existing

    # ==================================================================
    # Internal: setup flows
    # ==================================================================

    def _first_run_setup(self) -> dict:
        """No .env exists at all. This is unavoidable, there's nothing to
        carry over or ask "edit or not?" about. Tool paths are deliberately
        NOT prompted for here: on a genuine first run there's nothing to
        show as a hint anyway, and dependencies.py's self-healing
        (PATH lookup -> auto-download -> only then ask) is strictly better
        than guessing blind. Those four keys stay blank and get filled in
        by cli.py calling check_dependencies() right after load() returns."""

        print("No .env found! Let's set one up!\n")
        data = self._prompt_full_series_info()
        data["YT_DLP_PATH"] = ""
        data["DENO_PATH"] = ""
        data["MKVMERGE_PATH"] = ""
        data["MKVPROPEDIT_PATH"] = ""
        data["DOWNLOAD_DIR"] = self._prompt_download_dir()
        data["LAST_OS"] = self.current_os
        self._write_full(data)
        print(f"\n.env created for {self.current_os}.\n")
        return data

    def _os_change_setup(self, data: dict, saved_os: str) -> dict:
        """Reached when LAST_OS in the existing .env doesn't match the OS
        we're currently running on. Two possible outcomes:

          1. This OS has been used before, has its own backup slot, and
             that backup parses cleanly (e.g. Linux -> Windows -> back to
             Linux) -> offer to either carry that old session over as-is,
             or set up fresh.
          2. No usable backup for this OS exists (none was ever made, or
             the one that exists is hand-corrupted) -> back up the
             outgoing OS's data into its own slot, then build a fresh .env
             for this OS (tool paths reset to blank/unverified; series
             identity optionally carried over), then hand off to
             _edit_menu() for any further changes in the same run.
        """
        self._clear_screen()
        print(f"\nLast time you launched on {saved_os or 'an unrecorded OS\n'} "
              f"> you're currently on {self.current_os}!")

        backup = self._find_usable_backup_for_os(self.current_os)
        if backup:
            print(f"Found a previous .env from your last {self.current_os} session.")
            choice = input(
                f"[1] Set up fresh with values from your {saved_os or 'last'} session "
                f"(you'll re-enter tool paths for {self.current_os})\n"
                f"[2] Carry over your old {self.current_os} setup as-is "
                f"(no need to re-enter tool paths or API key) [default]\n> "
            ).strip()
            if choice != "1":
                return self._carry_over_previous_session(backup, saved_os)
            # choice == "1" (explicit): already decided to set up fresh, fall
            # straight through to the fresh-setup steps below, no re-asking.
        else:
            # No usable backup for this OS at all. This actually IS a fresh
            # decision point, so ask before touching anything.
            nter = input("No Previous backup/Never existed backup available!\nSet up a new environment for this OS? [Y/n]:> ").strip().lower()
            if nter not in ("y", ""):
                print("Keeping the existing .env as-is (dependency paths may be wrong for this OS).\n")
                return data

        self._backup_env(saved_os or "unknown")
        keep = input("Keep the old series name, season, TMDB ID, and API key? [Y/n]:> ").strip().lower()
        fresh = {}
        if keep in ("y", ""):
            series, season, series_id = data.get("SERIES", ""), data.get("SEASON", ""), data.get("SERIES_ID", "")
        else:
            fresh = self._prompt_full_series_info()
            series, season, series_id = fresh["SERIES"], fresh["SEASON"], fresh["SERIES_ID"]

        new_data = {
            "SERIES": series,
            "SEASON": season,
            "SERIES_ID": series_id,
            "TMDB_API_KEY": fresh["TMDB_API_KEY"] if keep not in ("y", "") else data.get("TMDB_API_KEY", ""),
            "DOWNLOAD_DIR": data.get("DOWNLOAD_DIR", ""),    # user preference, NOT machine-tied. carried over regardless
            "YT_DLP_PATH": "", "FFMPEG_PATH": "", "DENO_PATH": "", "MKVMERGE_PATH": "", "MKVPROPEDIT_PATH": "",  # machine-tied, reset, unverified for this OS
            "LAST_OS": self.current_os,
        }
        self._write_full(new_data)
        print(f".env created for {self.current_os}.\n")
        return self._maybe_edit(new_data)

    def _carry_over_previous_session(self, backup_path: Path, saved_os: str) -> dict:
        """A known-good .env for self.current_os is already sitting in its
        backup slot from a previous visit to this OS, already verified
        parseable by the caller (_find_usable_backup_for_os), so this never
        restores a corrupted file. Preserve the session being left
        (saved_os) into its own backup slot first, giving it the same
        safety net a fresh-setup switch would get, then restore the
        current_os backup verbatim as the new working .env. Tool paths and
        API key come back intact, so nothing needs re-entering.

        From here it's handled exactly like a normal unchanged-OS load:
        straight into _edit_menu(), the restored data simply becomes the 
        current env."""
        self._backup_env(saved_os or "unknown")
        restored = dotenv_values(backup_path)
        restored["LAST_OS"] = self.current_os
        self._write_full(restored)
        print(f"Carried over your previous {self.current_os} setup,\n"
              f"tool paths and API key are already in place.\n")
        
        return self._maybe_edit(restored)

    # ==================================================================
    # Internal: the edit menu (unchanged-OS path, and post-restore landing)
    # ==================================================================

    def _maybe_edit(self, data: dict) -> dict:
        """A way to skip edit menu on every run. 
        Gate before opening the edit menu. Most runs are just launching
        the app, not reconfiguring it, so ask once, up front, instead of
        dropping straight into the menu every time. [y/N], default no."""
        nter = input("\nWant to change anything (API key, series info, "
                      "download folder, dependency paths)? [y/N]:> ").strip().lower()
        if nter != "y":
            return data
        return self._edit_menu(data)

    def _edit_menu(self, data: dict) -> dict:
        """Interactive menu shown whenever a valid .env for the current OS
        is already in hand; either because the OS genuinely didn't change,
        or because an OS-change flow just finished setting up / restoring
        one and wants to offer the same "anything else?" opportunity
        without a special wrapper. Loops until the user picks 'continue'.

        Only option 2 (series info) triggers a backup, since SERIES/SEASON/
        SERIES_ID are project identity; overwriting them without a
        recovery point would be a real loss. API key, download dir, and
        tool-path edits are treated as low-stakes and just overwrite.
        Option 5 is read-only and never touches `data` or triggers a save.
        """
        while True:
            self._clear_screen()
            print("Existing .env found. What would you like to edit?")
            print("  1. TMDB API key")
            print("  2. Series info (name / season / TMDB ID) - backs up current .env first")
            print("  3. Download folder")
            print("  4. Dependency paths")
            print("  5. View backups")
            print("  6. Continue - no changes")
            choice = input("> ").strip()
            if choice == "1":
                hint = " [unchanged]" if data.get("TMDB_API_KEY") else ""
                entered = input(f"TMDB API Key{hint}:> ").strip()
                if entered:
                    data["TMDB_API_KEY"] = entered
            elif choice == "2":
                self._backup_env(self.current_os)
                new_name = input(f"Series name [{data.get('SERIES', '')}], leave blank to keep:> ").strip()
                if new_name:
                    data["SERIES"] = new_name

                while True:
                    new_season = input(f"Season number [{data.get('SEASON', '')}], leave blank to keep:> ").strip()
                    if not new_season or new_season.isdigit():
                        break
                    print("Enter digits only.")
                if new_season:
                    data["SEASON"] = new_season

                new_id = input(f"TMDB Series ID [{data.get('SERIES_ID', '')}], leave blank to keep:> ").strip()
                if new_id:
                    data["SERIES_ID"] = new_id
            elif choice == "3":
                data["DOWNLOAD_DIR"] = self._prompt_download_dir(existing=data.get("DOWNLOAD_DIR", ""))

            elif choice == "4":
                data.update(self._prompt_tool_paths(existing=data))

            elif choice == "5":
                self._view_backups()
                continue   # re-loop without touching data/LAST_OS; this is read-only

            elif choice in ("6", ""):
                break

            else:
                print("Enter a number 1-6.")
                input("Press Enter to continue...")
                continue
        data["LAST_OS"] = self.current_os   # Designed to stay unsetable by user
        self._write_full(data)
        return data

    # ==================================================================
    # Internal: file I/O
    # ==================================================================
    
    def _backup_env(self, os_label: str) -> None:
        """Save the currently-active .env into that OS's single backup
        slot (.env.<os_label>), overwriting whatever was there before.
        There is exactly one slot per OS; no timestamps, no history.
        Called right before the file is about to be replaced, either by:
          - an in-place series-identity edit (self.current_os as the label), or
          - an OS switch (the outgoing/saved_os as the label).
        os_label is sanitized since it's used as a literal filename part;
        matters for the unknown-OS path where the label came from free
        user input.
        """
        label = self._sanitize_os_label(os_label) or "unknown"
        backup_name = self.ENV_FILE.parent / f".env.{label}"
        shutil.copy2(self.ENV_FILE, backup_name)
        print(f"Old .env preserved as {backup_name.name}.")

    def _find_backup_for_os(self, os_name: str) -> Path | None:
        """Return the single backup slot's path for this OS if it exists,
        else None. Used to detect "we've been on this OS before"."""
        if not os_name: # Unnecessary Check but still a safety net.
            return None
        candidate = self.ENV_FILE.parent / f".env.{os_name}"
        return candidate if candidate.exists() else None
    
    def _find_usable_backup_for_os(self, os_name: str) -> Path | None:
        """TLDR a Safety Layer from backup corruption.
        Like _find_backup_for_os, but also rejects a backup that fails
        the corruption check. A hand-corrupted backup should never be
        silently offered as a carry-over source; restoring it would write
        the literal text "None" into the live .env for any value that
        failed to parse. If a backup exists but is corrupted, this returns
        None so the caller falls back to normal fresh setup instead."""

        candidate = self._find_backup_for_os(os_name)
        if candidate is None:
            return None
        parsed = dotenv_values(candidate)
        if self._looks_hand_corrupted(candidate, parsed):
            print(f"Found a backup for {os_name}, but it looks hand-corrupted "
                  f"(a line couldn't be parsed); skipping it.\n"
                  f"You can inspect or fix it manually at: {candidate}\n")
            return None
        return candidate

    def _view_backups(self) -> None:
        """Read-only: list every OS that has a backup slot, let the user
        pick one to view its contents, then wait before clearing back to
        the menu. Never writes anything. Flags corruption for whichever
        backup is viewed, but does not filter the list; even a corrupted
        backup should be viewable/diagnosable here, unlike in the
        carry-over path where a corrupted backup is refused outright."""
        backups = sorted(self.ENV_FILE.parent.glob(".env.*"))

        self._clear_screen()
        if not backups:
            print("No backups found yet.\n")
            input("Press Enter to go back...")
            return

        print("Available backups:\n")
        for i, path in enumerate(backups, start=1):
            os_label = path.name.removeprefix(".env.")
            print(f"  {i}. {os_label}")
        print("  0. Back")
        choice = input("\nView which one?:> ").strip()
        if not choice.isdigit() or choice == "0":
            return

        index = int(choice) - 1
        if not (0 <= index < len(backups)):
            print("Invalid choice.")
            input("Press Enter to go back...")
            return
        selected = backups[index]
        contents = dotenv_values(selected)
        self._clear_screen()
        print(f"--- {selected.name} ---\n")
        if self._looks_hand_corrupted(selected, contents):
            print("⚠ This backup looks hand-corrupted (a line couldn't be parsed).")
            print(f"  You can manually fix it in a text/code editor: {selected}\n")

        for key, value in contents.items():
            print(f"{key} = {value}")   # Prints the contents
        print()
        input("Press Enter to go back...")

    def _looks_hand_corrupted(self, path: Path, parsed: dict) -> bool:
        """Heuristic only; dotenv_values() doesn't raise on malformed
        lines, it just quietly drops them or maps them to None. So if the
        file has more non-blank lines than parsed keys, at least one line
        failed to parse as KEY = value, which almost always means someone
        edited the file by hand and broke the format."""
        raw_lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return len(raw_lines) > len(parsed)

    def _write_full(self, data: dict) -> None:
        """Reset .env to exactly this set of keys: unlink the old file,
        touch a fresh empty one, then write each key via dotenv's set_key
        (keeps formatting/quoting consistent with what dotenv_values
        expects to read back). This is the ONLY method that ever writes
        the live .env file, and every save path in this class funnels
        through it; first run, every edit-menu save, every OS-change
        fresh setup, every carried-over restore.

        Callers are expected to hand in a dict of plain strings; the
        corruption guard in _find_usable_backup_for_os() is what keeps a
        None-laced parsed backup from ever reaching this method via the
        carry-over path."""
        if self.ENV_FILE.exists():
            self.ENV_FILE.unlink()
        self.ENV_FILE.touch()
        for key, value in data.items():
            set_key(str(self.ENV_FILE), key, str(value))

    def _to_config(self, data: dict) -> SeriesConfig:
        """Convert the final flat dict into a SeriesConfig instance. Pure
        mapping; no prompting, no file I/O, no validation beyond the type
        coercion SEASON needs (str -> int)."""
        return SeriesConfig(
            series=data.get("SERIES", ""),
            series_id=data.get("SERIES_ID", ""),
            season=int(data.get("SEASON", "") or 0),
            tmdb_api_key=data.get("TMDB_API_KEY", ""),
            download_dir=data.get("DOWNLOAD_DIR") or None,
            yt_dlp_path=data.get("YT_DLP_PATH") or None,
            ffmpeg_path=data.get("FFMPEG_PATH") or None,
            deno_path=data.get("DENO_PATH") or None,
            mkvmerge_path=data.get("MKVMERGE_PATH") or None,
            mkvpropedit_path=data.get("MKVPROPEDIT_PATH") or None,
            last_os=data.get("LAST_OS") or None,
        )