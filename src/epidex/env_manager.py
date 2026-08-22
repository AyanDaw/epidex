"""
env_manager.py — the ONLY module that reads or writes .env.
Returns a plain SeriesConfig snapshot; never mutates globals.
"""

import platform
import shutil
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, set_key

from epidex import paths


@dataclass
class SeriesConfig:
    series: str
    season: int
    series_id: str
    tmdb_api_key: str
    download_dir: str | None
    yt_dlp_path: str | None
    deno_path: str | None
    mkvmerge_path: str | None
    mkvpropedit_path: str | None
    last_os: str | None


class EnvManager:
    ENV_FILE: Path = paths.ENV_FILE

    def __init__(self):
        self.current_os = platform.system()   # 'Linux', 'Windows', 'Darwin'

    # ---------- public API ----------

    def load(self) -> SeriesConfig:
        """Ensure a usable .env exists for this OS (first run / OS change /
        unchanged-OS-optional-edit), then hand back a SeriesConfig."""
        if not self.ENV_FILE.exists():
            data = self._first_run_setup()
        else:
            data = dotenv_values(self.ENV_FILE)
            saved_os = (data.get("LAST_OS") or "").strip()
            if saved_os == self.current_os:
                data = self._maybe_edit_existing(data)
            else:
                data = self._os_change_setup(data, saved_os)
        return self._to_config(data)

    def set_download_dir(self, path: str) -> None:
        """Single-key update, e.g. changed via the app later — doesn't touch anything else."""
        set_key(str(self.ENV_FILE), "DOWNLOAD_DIR", path)

    def set_tool_path(self, key: str, path: str) -> None:
        """key: one of YT_DLP_PATH / DENO_PATH / MKVMERGE_PATH / MKVPROPEDIT_PATH.
        dependencies.py calls this after resolving a binary via PATH, so next
        run skips the PATH lookup."""
        set_key(str(self.ENV_FILE), key, path)

    # ---------- internal: prompting ----------

    def _prompt_series_name(self) -> str:
        return input("Series name:> ").strip()

    def _prompt_full_series_info(self) -> dict:
        print("\nSeries setup (first run):\n")
        data = {
            "SERIES": self._prompt_series_name(),
            "TMDB_API_KEY": input("TMDB API Key:> ").strip(),
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
        existing = existing or {}
        print("\nDependency paths (optional — leave blank to keep current / auto-detect from PATH):\n")
        result = {}
        for key, name in [("YT_DLP_PATH", "yt-dlp"), ("DENO_PATH", "deno"),
                           ("MKVMERGE_PATH", "mkvmerge"), ("MKVPROPEDIT_PATH", "mkvpropedit")]:
            current = existing.get(key, "")
            hint = f" [{current}]" if current else ""
            entered = input(f"{name} full path{hint}:> ").strip()
            result[key] = entered or current
        return result

    def _prompt_download_dir(self, existing: str = "") -> str:
        hint = f" [{existing}]" if existing else " [default: ~/Downloads/<series> S<season>]"
        entered = input(f"Download folder{hint}, leave blank to keep/default:> ").strip()
        return entered or existing

    # ---------- internal: setup flows ----------

    def _first_run_setup(self) -> dict:
        print("No .env found — let's set one up.\n")
        data = self._prompt_full_series_info()
        data.update(self._prompt_tool_paths())
        data["DOWNLOAD_DIR"] = self._prompt_download_dir()
        data["LAST_OS"] = self.current_os
        self._write_full(data)
        print(f"\n.env created for {self.current_os}.\n")
        return data

    def _maybe_edit_existing(self, data: dict) -> dict:
        nter = input("Existing .env found for this OS. Change series name, "
                      "dependency paths, or download folder? [y/N]:> ").strip().lower()
        if nter == "y":
            hint = f" [{data.get('SERIES', '')}]" if data.get("SERIES") else ""
            new_name = input(f"Series name{hint}, leave blank to keep:> ").strip()
            if new_name:
                data["SERIES"] = new_name
            data.update(self._prompt_tool_paths(existing=data))
            data["DOWNLOAD_DIR"] = self._prompt_download_dir(existing=data.get("DOWNLOAD_DIR", ""))
            data["LAST_OS"] = self.current_os
            self._write_full(data)
        return data

    def _os_change_setup(self, data: dict, saved_os: str) -> dict:
        print(f"\nLast time you launched on {saved_os or 'an unrecorded OS'} — this is {self.current_os}!")
        nter = input("Set up a new environment for this OS? [Y/n]:> ").strip().lower()
        if nter not in ("y", ""):
            print("Keeping the existing .env as-is (dependency paths may change for this OS).\n")
            return data

        backup_name = self.ENV_FILE.parent / f".env.{saved_os or 'unknown'}"
        shutil.copy2(self.ENV_FILE, backup_name)
        print(f"Old .env preserved as {backup_name.name}.")

        keep = input("Keep the old series name? [Y/n]:> ").strip().lower()
        new_series = data.get("SERIES", "") if keep in ("Y", "y", "") else self._prompt_series_name()

        new_data = {
            "SERIES": new_series,
            "TMDB_API_KEY": data.get("TMDB_API_KEY", ""),   # project identity, carried over
            "SERIES_ID": data.get("SERIES_ID", ""),          # project identity, carried over
            "SEASON": data.get("SEASON", ""),                # project identity, carried over
            "DOWNLOAD_DIR": data.get("DOWNLOAD_DIR", ""),    # user preference, NOT machine-tied — carried over
            "YT_DLP_PATH": "", "DENO_PATH": "", "MKVMERGE_PATH": "", "MKVPROPEDIT_PATH": "",  # machine-tied — reset
            "LAST_OS": self.current_os,
        }
        self._write_full(new_data)
        print(f".env created for {self.current_os}.\n")
        return new_data

    # ---------- internal: file I/O ----------

    def _write_full(self, data: dict) -> None:
        """Reset .env to exactly this set of keys, written via dotenv's set_key
        (so formatting/quoting always matches what dotenv_values expects back)."""
        if self.ENV_FILE.exists():
            self.ENV_FILE.unlink()
        self.ENV_FILE.touch()
        for key, value in data.items():
            set_key(str(self.ENV_FILE), key, str(value))


    def _to_config(self, data: dict) -> SeriesConfig:
        return SeriesConfig(
            series=data.get("SERIES", ""),
            season=int(data.get("SEASON", "") or 0),
            series_id=data.get("SERIES_ID", ""),
            tmdb_api_key=data.get("TMDB_API_KEY", ""),
            download_dir=data.get("DOWNLOAD_DIR") or None,
            yt_dlp_path=data.get("YT_DLP_PATH") or None,
            deno_path=data.get("DENO_PATH") or None,
            mkvmerge_path=data.get("MKVMERGE_PATH") or None,
            mkvpropedit_path=data.get("MKVPROPEDIT_PATH") or None,
            last_os=data.get("LAST_OS", "")
        )