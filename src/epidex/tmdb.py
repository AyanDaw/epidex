"""TMDB season metadata: fetch from the API, cache on disk, parse episode titles."""
 
import json
import sys
from datetime import datetime
from pathlib import Path
 
import requests
 
from epidex.paths import get_app_data

TYPE = "tv"
CLEAR_LINE = "\033[1A\033[2K"  # ANSI: move the cursor up one line and erase it


def load_metadata_tmdb(
    series: str,
    series_id: str,
    season: int,
    api_key: str
) -> dict[int, str]:
    """
    Return {episode_number: title} for the whole season.

    Offers the cached copy if one exists; otherwise (or if declined) fetches from
    TMDB and refreshes the cache. If the fetch fails, offers the old cache as a
    fallback. Exits the program if no metadata can be obtained.
    """

    tmdb_link = f"https://api.themoviedb.org/3/{TYPE}/{series_id}/season/{season}"

    cache_file = get_app_data("metadata.json", series=series, season=season)
    # Read the cache first, so it can be offered now and used as a fallback later.
    old_cache = _read_cache(cache_file) if cache_file.exists() else None
    data = None


    if old_cache is not None:
        fetched = datetime.fromtimestamp(cache_file.stat().st_mtime)  # noqa: DTZ006
        if _ask_yes_no(
            f"\nCached metadata found (last fetched {fetched:%Y-%m-%d %H:%M:%S}).\n"
            "Use it? If no, fresh metadata will be fetched."
        ):
            data = old_cache
 
    if data is None:
        data = _fetch_season(tmdb_link=tmdb_link, api_key=api_key)
        if data is not None:
            _write_cache(data=data, cache_file=cache_file)
        elif old_cache is not None and _ask_yes_no("Fetch failed. Use the old cache instead?"):
            data = old_cache
        else:
            sys.exit("No metadata available, exiting...")
 
    # From here on we have data; otherwise the program has already exited.
    episodes = data.get("episodes")
    if not episodes:
        sys.exit("TMDB returned no episodes for this season.")
 
    return {episode["episode_number"]: episode["name"] for episode in episodes}
 



# ================================================================
# Fetching Tools
# ================================================================

def _fetch_season(tmdb_link: str, api_key: str) -> dict | None:
    """Returns the parsed JSON, or None if the fetch failed fatally or the user gave up."""
    while True:
        try:
            print("[WAIT]: Trying to fetch data from TMDB...\n")
            response = requests.get(tmdb_link, params={"api_key": api_key}, timeout=20)
            response.raise_for_status()
            return response.json()
 
        except requests.exceptions.Timeout:
            print("[TIMEOUT]: Request Timeout!!")
 
        except requests.exceptions.ConnectionError:
            print("[FAILURE]: Could not connect to TMDB")
 
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            if code in (401, 404):
                # Retrying can't fix a bad key or a wrong series/season.
                reason = "Bad API key" if code == 401 else "Series or season not found"
                print(f"[ERROR]: {reason}")
                return None
            print(f"[ERROR]: Error code {code}")
 
        except requests.exceptions.RequestException as e:
            print(f"[ERROR]: {type(e).__name__}")
 
        # Reached only after a retryable failure.
        if not _ask_retry():
            return None
        # 4 lines to erase: "[WAIT]" line + its blank line, the error line, the retry prompt.
        print(CLEAR_LINE * 4, end="\r")




# ================================================================
# Cache Tools
# ================================================================

def _write_cache(data: dict, cache_file: Path) -> bool:
    """
    Atomically save data to cache_file.
 
    Returns True on success. On failure, warns and returns False; never prompts
    and never exits, since the data is already in memory.
    """
    # Write to a temp file first so the existing cache stays untouched on failure.
    tmp = cache_file.with_name(cache_file.name + ".tmp")
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as tmpfile:
            json.dump(data, tmpfile, indent=4)
        tmp.replace(cache_file)
 
    except (OSError, TypeError, ValueError) as e:  # PermissionError is a subclass of OSError
        print(
            f"[WARNING]: Couldn't save the metadata cache ({type(e).__name__}: {e}); "
            "continuing without it."
        )
        tmp.unlink(missing_ok=True)
        return False
    else:
        print("Metadata successfully saved!")
        return True
 
 
def _read_cache(cache_file: Path) -> dict | None:
    """Return the cached data, or None if it's unreadable, corrupt or has no episodes."""
    try:
        with cache_file.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("[WARNING]: The cache file contains invalid JSON (corrupted or edited by hand).")
        return None
    except PermissionError:
        print("[WARNING]: No permission to read the cache file.")
        return None
    except OSError:
        print("[WARNING]: Couldn't read the cache file (disk issue, invalid path, etc.).")
        return None
 
    if not isinstance(data, dict) or not data.get("episodes"):
        print("[WARNING]: The cache file has no episode data.")
        return None
 
    print("The file has been read successfully!")
    return data




# ================================================================
# Helper Functions
# ================================================================

def _ask_yes_no(prompt: str) -> bool:
    """Ask a [Y/n] question. Enter, 'y' and 'yes' mean yes; anything else means no."""
    answer = input(f"{prompt} [Y/n]:> ").strip().lower()
    return answer in ("", "y", "yes")
 
 
def _ask_retry(comment: str | None = None) -> bool:
    """Ask whether to retry, with an optional note appended to the question."""
    return _ask_yes_no("Want to retry?" + (f" {comment}" if comment else ""))
 