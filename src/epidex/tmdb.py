import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import requests

from epidex.paths import get_app_data

TYPE = "tv"




def load_metadata_tmdb(series: str, series_id: str, season: int, api_key: str) -> dict:
    """
    Return {episode_number: title} for the whole season.
    Check cache first; on miss , call TMDB once, cache result, return it.
    """

    TMDB_LINK = f"https://api.themoviedb.org/3/{TYPE}/{series_id}/season/{season}"

    data = {}

    # Check the file existence
    cache_file = get_app_data("metadata.json", series=series, season=season)
    
    data = None
    if cache_file.exists() and _ask_yes_no("\n\n"+"There exists a previous cached matadata.\n"+f"Last fetched time:\t{last_cache_date.strftime("%Y-%m-%d %H:%M:%S")}"+"\n\nDo you want to use that?"+"\nIf no then fresh metadata will be fetched."):
        # Python 3.12+ needed.
        last_cache_date = datetime.fromtimestamp(cache_file.stat().st_mtime)  # noqa: DTZ006
        fetch_succeeded = False
        while True:
            print(f"\n\nThere exists a previous cached matadata.\nLast fetched time:\t{last_cache_date.strftime("%Y-%m-%d %H:%M:%S")}")  # Python 3.12+ we will add that in directory
            if _ask_yes_no("\n\nDo you want to use that?\nif no then fresh metadata will be fetched."):
                data = _read_cache(cache_file=cache_file)
            else:
                while True:
                    data = _fetch_season(tmdb_link=TMDB_LINK, api_key=TMDB_API)
                    if data:
                        try:
                            cache_file_backup = cache_file.with_name(cache_file.name + ".bak")
                            shutil.copy2(cache_file, cache_file_backup) # (src,dest)

                            with open(cache_file, "w") as file:
                                json.dump(data, file, indent=4) # writing the json format in the json file
                                print("\n\nMetadata Successfully fetched and written in the file!")
                            fetch_succeeded = True
                            cache_file_backup.unlink()
                            break
                        except TypeError:
                            print("Your dictionary contains an object that JSON can't serialize (e.g. Path, set, custom class).")
                            cache_file_backup.replace(cache_file)
                            break
                        except PermissionError:
                            print("Cannot write to the file or directory.")
                            cache_file_backup.replace(cache_file)
                            break
                        except OSError:
                            print("Other Filesystem-related errors (disk issues, invalid path, etc.).")
                            cache_file_backup.replace(cache_file)
                            break
                    else: # This case is unsuccessfull metadata fetch, three options either retry or reuse old data or exit.
                        print("\n\nBecause of some unexpected problems we couldn't fetch your fresh metadata.")
                        if _ask_retry():
                            continue
                        else:
                            if _ask_yes_no("Want to exit? if not we will send you to use old data asking page."):
                                sys.exit()
                            else:
                                break # exits from inner loop
            if fetch_succeeded:
                break # leave outer loop too — data is good, go use it
            else:                
                continue # go back to outer loop's top — re-ask about cached data
            # Now WE have the metadata if file EXISTS
    else:
        while True:
            data = _fetch_season(tmdb_link=TMDB_LINK, api_key=TMDB_API)
            if data:
                try:
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(cache_file, "w") as file:
                        json.dump(data, file, indent=4) # writing the json format in file
                        print("\n\nMetadata Successfully fetched and written in the file!")
                        break
                except TypeError:
                    print("Your dictionary contains an object that JSON can't serialize (e.g. Path, set, custom class).")
                    
                    if _ask_retry("If not then we would exit."):
                        continue
                    else:
                        sys.exit()
                except PermissionError:
                    print("Cannot write to the file or directory.")
                    if _ask_retry("If not then we would exit."):
                        continue
                    else:
                        sys.exit()

                except OSError:
                    print("Other Filesystem-related errors (disk issues, invalid path, etc.).")
                    if _ask_retry("If not then we would exit."):
                        continue
                    else:
                        sys.exit()


            else:
                print("\n\nBecause of some unexpected problems we couldn't fetch your fresh metadata.")
                if _ask_retry("If not, then we would exit..."):
                    continue
                else:
                    sys.exit()

    # After All of this we will either have the data in hand or we will exit the program
    metadata = {}
    episodes = data.get("episodes")
    if not episodes:
        sys.exit("TMDB returned no episodes for this season.")
    for ep in episodes:
        metadata[ep["episode_number"]] = ep["name"]   # {Episode Number: Title}
    # We have the meta data dictionary now
    return metadata




# ================================================================
# Helper Functions
# ================================================================

def _ask_yes_no(prompt: str, default: str = "Y", alt: str = "n") -> bool:
    answer = input(f"{prompt} [{default}|{alt}]:> ")
    return answer in [default, default.lower(), default.upper(), ""]


def _ask_retry(comment: str | None = None) -> bool:
    return _ask_yes_no("Want to retry?" + f" {comment}" if comment else "")




# ================================================================
# Fetching Tools
# ================================================================

CLEAR_LINE = "\033[1A\033[2K"
def _fetch_season(tmdb_link: str, api_key: str) -> dict | None:
    """Returns the parsed JSON, or None if the fetch failed or the user gave up."""
    while True:
        try:
            print("[WAIT✋]: Trying to fetch data from TMDB...\n")
            response = requests.get(tmdb_link, params={"api_key": api_key}, timeout=20)
            response.raise_for_status()
            return response.json() # runs only if no exception was raised

        except requests.exceptions.Timeout:
            print("[TIMEOUT]: Request Timeout!!")
        
        except requests.exceptions.ConnectionError:
            print("[FAILURE]: Could not connect to TMDB")

        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            if code in (401, 404):
                print("[ERROR]: Bad API key" if code == 401 else "[ERROR]: Series not found")
                return None          # retrying can't fix this
            print(f"[ERROR]: Error code {code}")
        except requests.exceptions.RequestException as e:
            print(f"[ERROR]: {type(e).__name__}")   

        # reached only after a retryable failure
        if not _ask_retry():
            return None
        print(CLEAR_LINE * 4, end="\r")


def _write_cache(data: dict):
    ...


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

    if not data:
        print("The cache file is empty.")
        return None

    print("The file has been read successfully!")
    return data