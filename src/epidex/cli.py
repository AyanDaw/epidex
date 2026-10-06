"""TLDR: epidex's entry point and the only module that knows about all the others.

Builds every object once (config, tool paths, logger, downloader, queue, input
panel), hands them to each other explicitly, and owns startup and shutdown.
Run with `python -m epidex` from the src/ folder; `--version` prints the version.
"""

import argparse
import os
import platform
import shlex
import shutil
import subprocess
import sys
from dataclasses import fields
from pathlib import Path
from types import ModuleType

from rich.console import Console

from epidex import __version__, dependencies
from epidex.dependencies import ToolPaths
from epidex.downloader import Downloader
from epidex.env_manager import EnvConfig, EnvManager
from epidex.input_panel import InputPanel
from epidex.logging_utils import LogWriter
from epidex.mkv_tools import MkvTools
from epidex.monitors import output_monitor, queue_monitor
from epidex.paths import (
    SRC,
    STOP_FLAG,
    TOOLS_DIR,
    get_app_data,
    get_download_dir,
)
from epidex.queue_manager import QueueManager
from epidex.tmdb import load_metadata_tmdb

# from epidex.viewer

LANG_CODE = "ben"  # TODO Should be configured from env
LANG_NAME = "[ বাংলা (Bengali) ]"  # TODO Should be configured from env
USER = "User"  # TODO Should be from env

OS = platform.system()
_console = Console()

_MONITORS: list[ModuleType] = [output_monitor, queue_monitor]

# terminal binary name -> flags that must come before the command to run
_LINUX_TERMINALS = {
    "kitty": [],
    "alacritty": ["-e"],
    "wezterm": ["start", "--"],
    "foot": [],
    "gnome-terminal": ["--"],
    "konsole": ["-e"],
    "xterm": ["-e"],
}


def main():
    """TLDR: wire everything together once, run the input loop, then shut down cleanly.

    Order matters, each step feeds the next:
      1. --version is answered first, so it can never trigger a prompt.
      2. EnvManager loads .env, then _configs_solver resolves every external tool.
      3. Folders are created, then LogWriter, MkvTools, Downloader, QueueManager
         and InputPanel are built.
      4. The worker thread and both monitors start; the input loop blocks until
         the user quits.
      5. The queue drains. `finally` always raises STOP_FLAG, waits for the
         monitors to close and removes the flag, even if something crashed.

    Known limit: Ctrl+C jumps straight to `finally`; a download already running
    is not killed, because yt-dlp runs in its own process session.
    """

    # Version checker
    parser = argparse.ArgumentParser(prog="epidex")
    parser.add_argument("--version", action="version", version=f"epidex v{__version__}")
    parser.parse_args()

    # Starting up the app...
    monitor_procs: list[tuple[str, subprocess.Popen]] = []
    STOP_FLAG.unlink(missing_ok=True)
    env_manager = EnvManager()
    envconfig, tool_paths = _configs_solver(env_manager=env_manager)
    series = envconfig.series
    series_id = envconfig.series_id
    season = envconfig.season

    # Creating the folders that runtime writes need (files create themselves)
    download_dir: Path = get_download_dir(series=series, season=season, env_download_dir=envconfig.download_dir)
    log_file = get_app_data("log_file.txt", series=series, season=season)
    linkbook = get_app_data("linkbook.txt", series=series, season=season)
    for folder in (log_file.parent, download_dir, STOP_FLAG.parent):
        _create_dirs(folder)

    # Building the pipeline
    api_key = envconfig.tmdb_api_key
    log_writer = LogWriter(log_file=log_file, linkbook=linkbook)
    mkv_tools = MkvTools(tool_paths=tool_paths, lang_code=LANG_CODE, lang_name=LANG_NAME)
    downloader = Downloader(toolpaths=tool_paths, download_dir=str(download_dir), browser="firefox", codec="avc1")
    queue_manager = QueueManager(
        downloader=downloader,
        mkv_tools=mkv_tools,
        log_fn=log_writer.append_to_log,
        linkbook_fn=log_writer.append_to_linkbook,
        maxsize=10,
    )
    season_metadata = load_metadata_tmdb(series=series, series_id=series_id, season=season, api_key=api_key)
    input_panel = InputPanel(
        user=USER,
        manager=queue_manager,
        log_writer=log_writer,
        series=series,
        season=season,
        season_metadata=season_metadata,
    )

    try:
        # Using the app...
        start_epnumber = _ask_start_epnumber()
        queue_manager.start()
        for mons in _MONITORS:
            proc = _spawn_console(mons)
            if proc is None:  # _spawn_console already printed the reason
                continue
            monitor_procs.append((mons.__name__, proc))
        input_panel.run(start_epnumber=start_epnumber)

        # Finishing the unfinished jobs
        print("WAIT! Dont close the program rightnow!\n\nFinishing up remaining downloads in the queue...")
        queue_manager.q.join()  # blocks until every queued episode (and the running one) is done
        queue_manager.stop()  # wakes the worker thread so it exits instead of blocking forever

    finally:
        # Shutting down the app
        STOP_FLAG.touch()  # the monitors poll for this file and close themselves
        for name, proc in monitor_procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print(f"{name} didn't exit on its own in time, closing it forcefully.")
                proc.terminate()  # safety net only; the monitors normally exit on their own
        STOP_FLAG.unlink(missing_ok=True)
        print("Now you can close safely...")




# ================================================================
# Helper Functions
# ================================================================


def _ask_start_epnumber() -> int:
    """TLDR: ask for the first episode number until it is digits and the user confirms it."""

    while True:
        _clear_screen()
        start = input("Enter the starting episode number:> ")
        if not start.isdigit():
            print("Enter Digits Only!!")
            input("Press Enter to try again:> ")
            continue
        if not _ask_yes_no(f"Are you sure Episode {start} is the starting episode number?"):
            continue
        return int(start)


def _ask_yes_no(question: str) -> bool:
    """TLDR: [Y/n] prompt; Enter, 'y' or 'yes' mean True, anything else means False."""

    answer = input(f"{question} [Y/n]:> ").strip().lower()
    return answer in ["y", "yes", ""]


def _clear_screen() -> None:
    """TLDR: clear this console ('cls' on Windows, 'clear' elsewhere) and wait for it to finish."""

    subprocess.run("cls" if OS == "Windows" else "clear", shell=True, check=False)


def _create_dirs(path: Path) -> None:
    """TLDR: create a folder and any missing parents; harmless if it already exists."""

    path.mkdir(parents=True, exist_ok=True)


def _check_tools(envconfig: EnvConfig) -> tuple[ToolPaths, dict[str, str]]:
    """TLDR: run check_dependencies() behind a spinner whose text names what is actually running.

    The check starts up to five external programs one after another (yt-dlp alone
    can take seconds to launch), so without feedback the terminal looks frozen.
    A spinner is used instead of a percentage because the total time is unknown.
    """

    with _console.status("Checking yt-dlp, ffmpeg, deno, mkvmerge, mkvpropedit..."):
        return dependencies.check_dependencies(config=envconfig)




# ================================================================
# SUB Main Functions
# ================================================================


def _spawn_console(pyfile: ModuleType) -> subprocess.Popen | None:
    """TLDR: open `python -m <pyfile>` in a new terminal window or tab and return its process.

    Windows uses a Windows Terminal tab if `wt` exists, otherwise a new console.
    Linux needs a display, then tries $TERMINAL first and the known emulators in
    _LINUX_TERMINALS after it. Returns None (after printing why) when no window
    could be opened, so the caller can skip that monitor. cwd is SRC so
    `-m epidex...` is importable.
    """

    command = [sys.executable, "-m", pyfile.__name__]
    system = platform.system()

    if system == "Windows":  # Windows Branch
        wt = shutil.which("wt")
        if wt:
            return subprocess.Popen([wt, "-w", "0", "new-tab", "-d", str(SRC), *command])
        return subprocess.Popen(command, cwd=SRC, creationflags=subprocess.CREATE_NEW_CONSOLE)

    if system != "Linux":
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
            return subprocess.Popen([path, *flags, *command], cwd=SRC)  # *x spills the list's items in place

    print(f"[WARNING]: no terminal emulator found — skipping {pyfile.__name__}'s monitor")
    return None


def _configs_solver(env_manager: EnvManager) -> tuple[EnvConfig, ToolPaths]:
    """TLDR: load .env, then loop until every external tool resolves; save the paths found.

    Each pass re-runs the check. If tools are missing the user either lets epidex
    download them (one install can fix several, e.g. mkvmerge and mkvpropedit, so
    each is re-checked first) or installs them manually and presses Enter. Typing
    'q' quits. Returns the loaded config and the final ToolPaths.
    """

    envconfig: EnvConfig = env_manager.load()
    _clear_screen()
    while True:
        tool_paths, updates = _check_tools(envconfig=envconfig)
        missing = [f.name for f in fields(tool_paths) if getattr(tool_paths, f.name) is None]
        if not missing:
            print("[INFO]: Dependencies are all set!")
            break

        print("\n[WARNING]: these dependencies were not found:")
        for name in missing:
            print(f"\t- {name}")
        print(
            "\nYou can install them yourself (they must work from a terminal), "
            "or let epidex download them for you. (If you dont have trust issues) :)\n"
        )

        if _ask_yes_no("Let epidex download them?"):
            for name in missing:
                # mkvmerge and mkvpropedit share one installer, so an earlier
                # install may already have fixed this one. Re-check before running it.
                current, _ = _check_tools(envconfig=envconfig)
                if getattr(current, name) is not None:
                    continue
                if not dependencies._downloader(name=name, target_dir=TOOLS_DIR):
                    print(f"[ERROR]: couldn't install {name}. Please install it manually.")
        else:
            answer = input("Install them yourself, then press Enter to recheck (or type 'q' to quit):> ").strip().lower()
            if answer == "q":
                print("Exiting...")
                sys.exit(0)
        # the loop restarts here and re-checks everything

    for key, path in updates.items():
        env_manager.set_tool_path(key=key, path=path)
    return envconfig, tool_paths


if __name__ == "__main__":
    main()