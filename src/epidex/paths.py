"""
This file is a book keeper of all paths, If any module
need any kind of path, will import from here. So keep
in mind to keep creating paths here.
Update the lilterals if new Used by app files increases
"""
"""
TODO — forward-looking path changes (multi-user support, not yet built):

1. DB_FILE = DATA_PATH / "epidex.db"
   Add as a static constant once the multi-user database lands. Lives as a
   sibling to per-user folders inside data/ — NOT nested inside any single
   user's folder, since it's an index/registry spanning ALL users, not data
   belonging to one of them.

2. UserName = "User" placeholder → real usernames
   Currently hardcoded as a single placeholder folder. Once multi-user lands,
   this stops being a constant — USER_DATA and get_series_season_path() need
   a `user` parameter too (same pattern already used for series/season),
   sourced from DB_FILE rather than assumed to be "User" for everyone.

3. get_app_data()'s Literal list → add "series_config.json"
   This is the derived snapshot of series-identity fields (TMDB_API_KEY,
   SERIES, SEASON, SERIES_ID) written into each season's folder at time of
   use. It's a historical cache/record only — never authoritative, never
   edited directly by EnvManager — so it needs to be a valid target for
   get_app_data() once EnvManager starts writing it.

4. get_download_dir()'s env_download_dir wiring
   Function signature is already correctly designed (takes env_download_dir
   as a plain parameter) — just not yet connected end-to-end. Once
   EnvManager exists and loads .env's DOWNLOAD_DIR key, cli.py needs to pass
   that loaded value in here rather than leaving the parameter unfed.
"""



import platform
import re
from pathlib import Path
from typing import Literal

import platformdirs

# ==============================
# Static Values
# ==============================


# MAIN_DIRS
EPIDEX_PATH = Path(__file__).resolve().parent           # epidex(root)/src/epidex/
EPIDEX_APP_PATH = EPIDEX_PATH.parents[1]                # epidex(root)/
SRC = EPIDEX_APP_PATH / "src"                           # epidex(root)/src/
MONITORS = EPIDEX_PATH / "monitors"                     # epidex(root)/src/epidex/monitors/
ENV_FILE = EPIDEX_APP_PATH / ".env"                     # epidex(root)/.env 
DATA_PATH = EPIDEX_APP_PATH / "data"                    # epidex(root)/data/


# MONITORS
MONITORS_DATA = DATA_PATH / "monitors"                  # epidex(root)/data/monitors/
QUEUE_STATUS_FILE = MONITORS_DATA / "queue_status.json" # epidex(root)/data/monitors/queue_status.json
YTDLP_LOG = MONITORS_DATA / "ytdlp.log"                 # epidex(root)/data/monitors/ytdlp.log
STOP_FLAG = MONITORS_DATA / "STOP_MONITORS"             # epidex(root)/data/monitors/STOP_MONITORS


# ______________________________________________________________________________________________
# ______________________________________________________________________________________________


# ==============================
# Dynamic Values
# ==============================


def _slugify(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", name).strip()


# USER
UserName = "User"                                       # TODO Place Holder,Will be done if User separation added later

USER_DATA = DATA_PATH / UserName                        # epidex(root)/data/<UserName>/


# SERIES/SEASON path
def get_series_season_path(series: str, season) -> Path:
    """Return the app-data folder for a specific series+season,"""
    # ~/data/<UserName>/<SeriesFullNameSlug>/S<SeasonNumber>/
    
    return USER_DATA / _slugify(series) / f"S{int(season):02d}"


# USER_DOWNLOAD_DIRS
def get_download_dir(series: str, season, env_download_dir: str | None) -> Path:
    """Return where downloaded episodes should be saved.
    Uses env_download_dir (from .env's DOWNLOAD_DIR) if set, otherwise default."""
    # ~/Custom/Path/ if set else ~/Home/Downloads/<seriesName> S<season>/
    
    if env_download_dir:
        return Path(env_download_dir)
    return Path.home() / "Downloads" / f"{_slugify(series)} S{int(season):02d}"


# APP_DATA_DIRS
def get_app_data(query: Literal["linkbook.txt", "log_file.txt", "metadata.json"], series: str, season) -> Path:
    """Return the full path to a specific app-data file (linkbook, log, or metadata cache. Limited Options) for a series+season."""
    
    # ~/<PATH>/linkbook.txt
    # ~/<PATH>/log_file.txt
    # ~/<PATH>/metadata.json
    
    return get_series_season_path(series=series, season=season) / query

# TOOLS
# bundled ffmpeg. Linux uses ~/.local/bin because it's conventionally
# already on PATH; Windows has no such always-on-PATH user folder, so it
# gets a fixed known location instead.
if platform.system() == "Windows":
    TOOLS_DIR = Path(platformdirs.user_data_dir("epidex")) / "tools"
else:
    TOOLS_DIR = Path.home() / ".local" / "bin"