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
        fetched = datetime.fromtimestamp(cache_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")  # noqa: DTZ006
        if _ask_yes_no(f"\nCached metadata found (last fetched {fetched}).\nUse it? If no, fresh metadata will be fetched."):
            data = old_cache # Old cache reuse case

    if data is None: 
        data = _fetch_season(tmdb_link=tmdb_link, api_key=api_key) # Fresh data case
        if data is not None:
            _write_cache(data=data, cache_file=cache_file) # Writing the fresh data
        elif old_cache is not None and _ask_yes_no("Fetch failed. Use the old cache instead?"):
        # If the fetch is not successful, then ask and works accordingly
            data = old_cache
        else:
            sys.exit("No metadata available, exiting...")

    # After All of this we will either have the data in hand or we will exit the program
    metadata: dict = {}
    episodes = data.get("episodes")
    
    if not episodes:
        sys.exit("TMDB returned no episodes for this season.")

    for episode in episodes:
        metadata[episode["episode_number"]] = episode["name"]   # {Episode Number: Title}
    # We have the metadata dictionary now
    return metadata




# ================================================================
# Fetching Tools
# ================================================================

def _fetch_season(tmdb_link: str, api_key: str) -> dict | None:
    """Returns the parsed JSON, or None if the fetch failed or the user gave up."""
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
                print("[ERROR]: Bad API key" if code == 401 else "[ERROR]: Series or season not found")
                return None          # retrying can't fix this
            print(f"[ERROR]: Error code {code}")
        except requests.exceptions.RequestException as e:
            print(f"[ERROR]: {type(e).__name__}")   

        # reached only after a retryable failure
        if not _ask_retry():
            return None
        print(CLEAR_LINE * 4, end="\r")




# ================================================================
# Cache Tools
# ================================================================

def _write_cache(data: dict, cache_file: Path) -> bool:
    """Atomically save data to cache_file. Returns True on success; on failure
    warns and returns False. Never prompts, never exits."""
    tmp = cache_file.with_name(cache_file.name + ".tmp") # "metadata.json.tmp", in this way actual old file stays untouched.
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, 'w', encoding="utf-8") as tmpfile:
            json.dump(data, tmpfile, indent=4)
        tmp.replace(cache_file)

    except (OSError, TypeError, ValueError) as e: # PermissionError is a subclass
        print(f"[WARNING]: Couldn't save the metadata cache ({type(e).__name__}: {e}); continuing without it.")
        tmp.unlink(missing_ok=True)
        return False
    else:
        print("Metadata successfully saved!")
        return True


def _read_cache(cache_file: Path) -> dict | None:
    """Returns the cached data, or None if it's missing, unreadable or corrupt."""
    try:
        with open(cache_file, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("The file exists but contains invalid JSON (corrupted or manually edited incorrectly)")
        return None

    except PermissionError:
        print("You dont have permission to read it.")
        return None

    except OSError:
        print("Other Filesystem-related errors (disk issues, invalid path, etc.).")
        return None

    if not isinstance(data, dict) or not data.get("episodes"):
        print("The cache file is empty.")
        return None

    print("The file has been read successfully!")
    return data




# ================================================================
# Helper Functions
# ================================================================

def _ask_yes_no(prompt: str) -> bool:
    answer = input(f"{prompt} [Y/n]:> ").strip().lower()
    return answer in ["", "y", "yes"]


def _ask_retry() -> bool:
    return _ask_yes_no("Want to retry?")