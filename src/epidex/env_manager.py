# Env related every thing not fixed yet

def _write_env(data: dict):
    """Write a flat dict out as a .env file, one KEY = "value" per line."""
    lines = [f'{k} = "{v}"' for k, v in data.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_series_globals():
    global TMDB_API, SERIES, SEASON, SERIES_ID
    TMDB_API = config["TMDB_API_KEY"]
    SERIES = config["SERIES"]
    SEASON = int(config["SEASON"])
    SERIES_ID = config["SERIES_ID"]


def _prompt_series_name() -> str:
    return input("Series name:> ").strip()


def _prompt_full_series_info() -> dict:
    """Only ever called on a genuinely first-ever .env — SEASON/SERIES_ID/API key
    are project identity and never re-asked again after this."""
    print("\nSeries setup (first run):\n")
    data = {"SERIES": _prompt_series_name(),
             "TMDB_API_KEY": input("TMDB API Key:> ").strip(),
             "SERIES_ID": input("TMDB Series ID:> ").strip()}
    while True:
        season = input("Season number:> ").strip()
        if season.isdigit():
            data["SEASON"] = season
            break
        print("Enter digits only.")
    return data


def _prompt_tool_paths(existing: dict | None = None) -> dict:
    """All optional — blank keeps the current value (if any) and falls back to PATH."""
    existing = existing or {}
    print("\nDependency paths (optional — leave blank to keep current / auto-detect from PATH):\n")
    paths = {}
    for key, name in [("YT_DLP_PATH", "yt-dlp"), ("DENO_PATH", "deno"),
                       ("MKVMERGE_PATH", "mkvmerge"), ("MKVPROPEDIT_PATH", "mkvpropedit")]:
        current = existing.get(key, "")
        hint = f" [{current}]" if current else ""
        entered = input(f"{name} full path{hint}:> ").strip()
        paths[key] = entered or current
    return paths


def env_editor():
    """Ensure a usable .env exists for the CURRENT OS - handles first run, an
    unchanged OS, and a changed OS - then loads the result into config/globals."""
    global config
    current_os = platform.system()   # 'Linux', 'Windows', 'Darwin'

    if not ENV_FILE.exists():
        print("No .env found — let's set one up.\n")
        data = _prompt_full_series_info()
        data.update(_prompt_tool_paths())
        data["LAST_OS"] = current_os
        _write_env(data)
        print(f"\n.env created for {current_os}.\n")
        config = dotenv_values(ENV_FILE)
        _load_series_globals()
        return

    data = dotenv_values(ENV_FILE)
    saved_os = (data.get("LAST_OS") or "").strip()

    if saved_os == current_os:
        nter = input("Existing .env found for this OS. Change series name or dependency paths? [y/N]:> ").strip().lower()
        if nter == "y":
            hint = f" [{data.get('SERIES', '')}]" if data.get("SERIES") else ""
            new_name = input(f"Series name{hint}, leave blank to keep:> ").strip()
            if new_name:
                data["SERIES"] = new_name
            data.update(_prompt_tool_paths(existing=data))
            data["LAST_OS"] = current_os
            _write_env(data)
        config = dotenv_values(ENV_FILE)
        _load_series_globals()
        return

    # OS differs from last launch
    print(f"\nLast time you launched on {saved_os or 'an unrecorded OS'} — this is {current_os}!")
    nter = input("Set up a new environment for this OS? [Y/n]:> ").strip().lower()
    if nter not in ("y", ""):
        print("Keeping the existing .env as-is (dependency paths may be wrong for this OS).\n")
        config = data
        _load_series_globals()
        return

    backup_name = f".env.{saved_os or 'unknown'}"
    shutil.copy2(ENV_FILE, backup_name)
    print(f"Old .env preserved as {backup_name}.")

    keep = input("Keep the old series name? [Y/n]:> ").strip().lower()
    new_series = data.get("SERIES", "") if keep in ("y", "") else _prompt_series_name()

    new_data = {
        "SERIES": new_series,
        "TMDB_API_KEY": data.get("TMDB_API_KEY", ""),   # project identity, carried over
        "SERIES_ID": data.get("SERIES_ID", ""),          # project identity, carried over
        "SEASON": data.get("SEASON", ""),                # project identity, carried over
        "YT_DLP_PATH": "", "DENO_PATH": "", "MKVMERGE_PATH": "", "MKVPROPEDIT_PATH": "",
        "LAST_OS": current_os,
    }
    _write_env(new_data)
    print(f".env created for {current_os}.\n")
    config = dotenv_values(ENV_FILE)
    _load_series_globals()