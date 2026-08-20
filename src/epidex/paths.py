from epidex.cli import SERIES
from epidex.cli import SEASON
from pathlib import Path


# MAIN_DIRS
EPIDEX_PATH = Path(__file__).resolve()
SRC = EPIDEX_PATH.parent
EPIDEX_APP_PATH = SRC.parent
ENV_FILE = EPIDEX_APP_PATH / ".env"
DATA_PATH = EPIDEX_APP_PATH / "data"


# USER
UserName = "User"                                   # TODO Place Holder
USER_DATA = DATA_PATH / UserName
SERIES_PATH = USER_DATA / SERIES
SERIES_SEASON_PATH = SERIES_PATH / SEASON


# APP_DATA_DIRS
LINKBOOK = SERIES_SEASON_PATH / "linkbook.txt"      # TODO Place Holder
LOG_FILE = SERIES_SEASON_PATH / "log_file.txt"      # TODO Place Holder


