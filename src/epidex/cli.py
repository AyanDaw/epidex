import os
import platform
import shlex
import shutil
import subprocess
import sys
from dataclasses import fields
from pathlib import Path
from types import ModuleType

from epidex import dependencies
from epidex.dependencies import ToolPaths
from epidex.downloader import Downloader
from epidex.env_manager import EnvConfig, EnvManager
from epidex.input_panel import InputPanel
from epidex.logging_utils import LogWriter
from epidex.mkv_tools import MkvTools
from epidex.monitors import output_monitor, queue_monitor
from epidex.paths import (
    STOP_FLAG,
    TOOLS_DIR,
    get_app_data,
    get_download_dir,
)
from epidex.queue_manager import QueueManager
from epidex.tmdb import load_metadata_tmdb

# from epidex.viewer

LANG_CODE = "ben" # TODO Should be configured from env
LANG_NAME = "[ বাংলা (Bengali) ]" # TODO Should be configured from env
USER = "User" # TODO Should be from env

OS = platform.system()
_MONITORS: list[ModuleType] = [output_monitor, queue_monitor]


_LINUX_TERMINALS = {
    "kitty": [],
    "alacritty": ["-e"],
    "wezterm": ["start", "--"], 
    "foot": [],
    "gnome-terminal": ["--"],
    "konsole": ["-e"],
    "xterm": ["-e"]
}
# These are search and result.



def main():
    # Creates the folders
    _create_dirs(path=TOOLS_DIR)

    # Starting up the app...
    _monitor_procs: list[tuple[str, subprocess.Popen]] = []
    STOP_FLAG.unlink(missing_ok=True)
    env_manager = EnvManager()
    envconfig, tool_paths = _configs_solver(env_manager=env_manager)
    series = envconfig.series
    series_id = envconfig.series_id
    season = envconfig.season

    # Creating default directories
    download_dir: Path = get_download_dir(series=series, season=season, env_download_dir=envconfig.download_dir)
    get_app_data_list: dict[str, Path]= {}
    for file in ['linkbook.txt', 'log_file.txt', 'metadata.json']:
        get_app_data_list[file] = get_app_data(file, series=series, season=season)

    DEFAULT_DIRS = [get_app_data_list['linkbook.txt'].parent,
                    get_app_data_list['log_file.txt'].parent, 
                    get_app_data_list['metadata.json'].parent,
                    download_dir,
                    STOP_FLAG.parent,
    ]
    for items_paths in DEFAULT_DIRS: # Default will be a directory where all default paths are stored else any one needs any paths it will be called there
        _create_dirs(path=items_paths)

    # Resuming the start job
    api_key = envconfig.tmdb_api_key
    log_writer = LogWriter(log_file=get_app_data_list['log_file.txt'], linkbook=get_app_data_list['linkbook.txt'])
    mkv_tools = MkvTools(tool_paths=tool_paths, lang_code=LANG_CODE, lang_name=LANG_NAME)
    downloader = Downloader(toolpaths=tool_paths, download_dir=str(download_dir), browser= 'firefox', codec= 'avc1')
    queue_manager = QueueManager(downloader=downloader, mkv_tools=mkv_tools,log_fn=log_writer.append_to_log, linkbook_fn=log_writer.append_to_linkbook,maxsize=10)
    season_metadata = load_metadata_tmdb(series=series, series_id=series_id, season=season, api_key=api_key)
    input_panel = InputPanel(user=USER, manager=queue_manager, log_writer=log_writer, series=series, season=season, season_metadata=season_metadata)

    try:

        # Using the app...
        start_epnumber = _ask_start_epnumber()
        queue_manager.start()
        for mons in _MONITORS:
            proc = _spawn_console(mons)
            if proc is None:
                print(f"[ERROR]: It seems like we run into some unfortunate errors while opening {mons.__name__}!")
                continue
            _monitor_procs.append((mons.__name__, proc))
        input_panel.run(start_epnumber=start_epnumber)

        # Finishing the unfinished jobs
        print("WAIT! Dont close the program rightnow!\n\nFinishing up remaining downloads in the queue...")
        queue_manager.q.join() # Finishes the unfinished jobs and currently running tasks.
        queue_manager.stop() # How this works too?

    finally:
        # Shutting down the app
        STOP_FLAG.touch() # Whats this line do?
        for name, proc in _monitor_procs:
            try:
                proc.wait(timeout=10) # How?
            except subprocess.TimeoutExpired:
                print(f"{name} didn't exit on its own in time, closing it forcefully.")
                proc.terminate() # Literrally kills?
        STOP_FLAG.unlink(missing_ok=True) # Deletes, right?
        print("Now you can close safely...")




# ================================================================
# Helper Functions
# ================================================================

def _ask_start_epnumber() -> int:
    while True:
        _clear_screen()
        start = input("Enter the starting episode number:> ")
        if not start.isdigit():
            print("Enter Digits Only!!")
            input()
            continue
        if not _ask_yes_no(f"Are you sure Episode {start} is the starting episode number?"):
            continue
        return int(start)


def _ask_yes_no(question: str) -> bool:
    answer = input(f"{question} [Y/n]:> ").strip().lower()
    return answer in ["y", "yes", ""]


def _clear_screen():
    subprocess.run("cls" if OS == 'Windows' else "clear", shell=True, check=False)


def _create_dirs(path: Path) -> bool:
    path.mkdir(parents=True, exist_ok=True)
    return path.exists()

# ================================================================
# SUB Main Functions
# ================================================================


def _spawn_console(pyfile: ModuleType) -> subprocess.Popen | None:
    command = [sys.executable, "-m", pyfile.__name__]
    system = platform.system()

    if system == 'Windows': # Windows Branch
        wt = shutil.which('wt')
        if wt:
            return subprocess.Popen([wt, "-w", "0", "new-tab", *command])
        return subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_CONSOLE)
    
    if system != 'Linux':
        print(f"[WARNING]: unsupported OS, skipping {pyfile.__name__}'s monitor")
        return None

    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print(f"[WARNING]: display not found, skipping {pyfile.__name__}'s monitor")
        return None

    # Linux Branch
    # TERMINAL is the user's preferred emulator, not a type, respected by convention on i3/sway/hyprland setups
    candidates: dict[str, list[str]] = {}
    try:
        args = shlex.split(os.environ.get("TERMINAL", ""))
    except ValueError:
        print("TERMINAL couldn't be parsed, using defaults")
        args = []

    if args:
        name, *flags = args
        candidates[name] = flags or _LINUX_TERMINALS.get(Path(name).name, ["-e"])
    
    for name, flags in _LINUX_TERMINALS.items():
        candidates.setdefault(name, flags)

    for name, flags in candidates.items():
        path = shutil.which(name)
        if path:
            return subprocess.Popen([path, *flags, *command]) # In a list literal, *x means "spill the elements of x here, one by one"
    
    print(f"[WARNING]: no terminal emulator found — skipping {pyfile.__name__}'s monitor")
        
    return None
    
    # =========================================================== #
    # if not (platformOS == 'Linux' or platformOS == 'Windows'):  #
    #     print("Unsupported OS")                                 #
    # =========================================================== #


def _configs_solver(env_manager: EnvManager) -> tuple[EnvConfig, ToolPaths]:
    """TLDR: load config, then loop until every tool resolves; persist found paths, return both."""
    envconfig: EnvConfig = env_manager.load()
    
    while True:
        _clear_screen()
        tool_paths, updates = dependencies.check_dependencies(config= envconfig)
        missing = [f.name for f in fields(tool_paths) if getattr(tool_paths, f.name) is None]
        if not missing:
            break

        print("\n[WARNING]: these dependencies were not found:")
        for name in missing:
            print(f"\t- {name}")
        print("\nYou can install them yourself (they must work from a terminal), "
              "or let epidex download them for you. (If you dont have trust issues) :)\n")
        
        if _ask_yes_no("Let epidex download them?"):
            for name in missing:
                # mkvmerge and mkvpropedit share one installer, so an earlier
                # install may already have fixed this one. Re-check before running it.
                current, _ = dependencies.check_dependencies(config=envconfig)
                if getattr(current, name) is not None:
                    continue
                if not dependencies._downloader(name= name, target_dir= TOOLS_DIR):
                    print(f"[ERROR]: couldn't install {name}. Please install it manually.")
        else:
            answer = input("Install them youself, then press Enter to recheck "
                           "(or type 'q' to quit):> ").strip().lower()
            if answer == "q":
                sys.exit("Exiting...")
        # the loop restarts here and re-checks everything
    for key, path in updates.items():
        env_manager.set_tool_path(key=key, path=path)
    return envconfig, tool_paths




if __name__ == "__main__":
    main()