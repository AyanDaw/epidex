# argument parsing, top-level orchestration (old main() from nonfondownloader.py)

# Python Module Import

# import json
# import math
# import os
# import platform
# import random
# import re
# import requests
# import shutil
# import subprocess
# import sys
# import time
# from datetime import datetime
# from dotenv import dotenv_values
# from pathlib import Path
# from rich.console import Console


# Custom Modules Import

from epidex import paths
from epidex.dependencies import ToolPaths, check_dependencies
from epidex.downloader import Downloader
from epidex.env_manager import EnvManager
from epidex.episode import Episode
from epidex.logging_utils import LogWriter
from epidex.mkv_tools import MkvTools

# from epidex.input_panel import InputPanel
# from epidex.tmdb import load_metadata_tmdb
from epidex.paths import get_app_data
from epidex.queue_manager import QueueManager

logger = LogWriter(
    log_file=get_app_data("log_file.txt", series=series, season=season),
    linkbook=get_app_data("linkbook.txt", series=series, season=season),
)
Q = QueueManager(downloader=..., mkv_tools=..., log_fn=logger.append_to_log, linkbook_fn=logger.append_to_linkbook, maxsize=10)










































































# Constants

config = EnvManager().load()   # returns dict: SERIES, SEASON, DOWNLOAD_DIR, ...
series_dir = paths.get_series_season_path(config["SERIES"], config["SEASON"])
download_dir = paths.get_download_dir(config["SERIES"], config["SEASON"], config.get("DOWNLOAD_DIR"))


config = None
SERIES = None
SEASON = None
SERIES_ID = None

STOP_FLAG = Path("STOP_MONITORS")   # tells monitor.py / Qmonitor.py to exit cleanly on their own

YT_DLP_BIN = None
DENO_BIN = None
MKVMERGE_BIN = None
MKVPROPEDIT_BIN = None


YTDLP_LOG = Path("ytdlp_output.log")


def spawn_console(pyfile: str):
    cmd = [sys.executable, pyfile]
    if os.name == "nt":
        wt = shutil.which("wt")
        if wt:
            return subprocess.Popen([wt, "-w", "0", "new-tab", sys.executable, pyfile])
    return subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)

    term = os.environ.get("TERMINAL")  # respected by convention on i3/sway/hyprland setups
    candidates = ([(term, ["-e"])] if term else []) + [
        ("kitty", []), ("alacritty", ["-e"]), ("wezterm", ["start", "--"]),
        ("foot", []), ("gnome-terminal", ["--"]), ("konsole", ["-e"]), ("xterm", ["-e"]),
    ]
    for name, prefix in candidates:
        path = shutil.which(name)
        if path:
            return subprocess.Popen([path, *prefix, *cmd])

    print(f"WARNING: no terminal emulator found — running {pyfile} in the background, "
          f"its output will mix into this console.")
    return subprocess.Popen(cmd)


def main():
    STOP_FLAG.unlink(missing_ok=True)
    env_editor()
    check_dependencies()
    sync_resolved_paths_to_env()
    series = SERIES
    series_id = SERIES_ID
    season = SEASON
    season_metadata = load_metadata_tmdb(series_id=series_id, season=season)    # One TMDB call, cached
    while True:
        start = input("Enter the starting episode number:> ")
        if not start.isdigit():
            print("Enter Digits Only!!")
            input()
            continue
        epnumber = int(start)
        break
    Q = QueueManager(maxsize=10)
    Input = InputPanel(series=series, season=season, season_metadata=season_metadata, manager=Q)
    Q.start()
    monitor = spawn_console("monitor.py")
    Qmonitor = spawn_console("Qmonitor.py")
    InputPanel.run(Input, start_epnumber=epnumber)

    print("WAIT! Dont close the program rightnow!\n\nFinishing up remaining downloads in the queue...")
    Q.q.join()
    Q.stop()
    with open(QUEUE_STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump({"now_processing_epnumber": None, "now_processing_title": "All done!",
                   "queue_length": "0/0", "upcoming": []}, f, indent=2)

    STOP_FLAG.touch()
    for proc, name in [(monitor, "monitor.py"), (Qmonitor, "Qmonitor.py")]:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            print(f"{name} didn't exit on its own in time, closing it forcefully.")
            proc.terminate()
    STOP_FLAG.unlink(missing_ok=True)
    print("Now you can close")



if __name__ == "__main__":
    main()