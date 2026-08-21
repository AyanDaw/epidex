"""
This file is a book keeper of all paths, If any module
need any kind of path, will import from here. So keep
in mind to keep creating paths here.
Update the lilterals if new Used by app files increases
"""

import re
from pathlib import Path
from typing import Literal

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