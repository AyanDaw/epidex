# dependencies.py — no EnvManager import at all

import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests

from epidex.env_manager import SeriesConfig

# We are not calling the Whole class, Just for type fitting.



@dataclass
class ToolPaths:
    yt_dlp: Path | None
    deno: Path | None
    mkvmerge: Path | None
    mkvpropedit: Path | None
    # None as some dependencies can not be available too.


def check_dependencies(config: SeriesConfig) -> tuple[ToolPaths, dict[str, str]]:
    """Resolve all four tools. Returns (ToolPaths, updates) where `updates`
    is {ENV_KEY: resolved_path} for only the tools that weren't already
    correctly set in .env — i.e. what the caller should persist.
    downloading done by _downloader() called from cli.py not _resolve()"""
    updates: dict[str, str] = {} # {ENV_KEY: resolved_path}
    # Updates gonna update .env file, So and values are always str:str. We need to force convert them to str.

    yt_dlp = _resolve(configured=config.yt_dlp_path, name="yt-dlp", env_key_name="YT_DLP_PATH", updates=updates)
    deno = _resolve(configured=config.deno_path, name="deno", env_key_name="DENO_PATH", updates=updates)
    mkvmerge = _resolve(configured=config.mkvmerge_path, name="mkvmerge", env_key_name="MKVMERGE_PATH", updates=updates)
    mkvpropedit = _resolve(configured=config.mkvpropedit_path, name="mkvpropedit", env_key_name="MKVPROPEDIT_PATH", updates=updates)

    # cli will be running here in loop, so after getting this returned cli will check if any dependency is still none 
    return (ToolPaths(yt_dlp=yt_dlp, deno=deno, mkvmerge=mkvmerge, mkvpropedit=mkvpropedit), updates)


def _resolve(configured: str | None, name: str, env_key_name: str, updates: dict[str, str]) -> Path | None:
    """Its work is resolving Paths. It will check if there is already configured path. if not find it.
     If not there in the machine then it will ask to download permission. User can download  by their self or let the app manage it."""
    if configured and Path(configured).exists():
        return Path(configured) # already correct path in .env
    elif configured and not Path(configured).exists():
        print(f"WARNING: {env_key_name} in .env points to '{configured}', but that path "
              f"doesn't exist — falling back to PATH lookup.")

    found = shutil.which(name)
    if found:
        updates [env_key_name] = found
        return Path(found)
    else:
        # Not found case.
        print(f"WARNING: {env_key_name} also not found in your machine!")
        return None


        #TODO This Part should belongs to CLI 
        # 
        # ...


def _downloader(name: str) -> Path | None:
    """Its work only to downloading not resolving.
    Can be used as downloading one dependencies or update all through CLI"""

    #TODO Help i dont know how to download from and then install. Also not sure where should i keep them? like inside epidex or outside? also update that file which tells linux whats its dependencies
    downloaders: dict[str, function] = {
        "yt_dlp" : _download_yt_dlp,
        "deno": _download_deno,
        "mkvmerge": _download_mkvtools_mkvmerge,
        "mkvpropedit" : _download_mkvtools_mkvpropedit
    }
    downloader = downloaders[name]
    return downloader()


def _run_privileged(cmd: list[str]) -> bool:
    ...

def _make_executable(path: Path) -> None:
    """chmod +x — no-op requirement on Windows, required on Linux/Mac."""
    if platform.system() != "Windows":
        path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


# For every downloader check if available else skip. Give a message for already availibility
def _download_yt_dlp(target_dir: Path) -> Path | None:
    """yt-dlp ships a single static binary with a permanent 'latest' URL per OS"""
    is_windows = platform.system() != 'Windows'
    asset_name = "yt-dlp.exe" if is_windows else "yt-dlp"
    url = f"https://github.com/yt-dlp/yt-dlp/releases/latest/download/{asset_name}"

    target_dir.mkdir(parents= True, exist_ok= True)
    destination_dir = target_dir/asset_name

    try:
        response = requests.get(url= url, timeout=30, stream= True) 
        # Instead of downloading all the data at once it allows to download in packages
        response.raise_for_status() # It Raises a error when server takes too long to response
    except requests.exceptions.RequestException as e:
        print(f"ERROR: failed to download yt-dlp: {e}")
        return None

    with open(destination_dir, "wb") as f:
    # This 'wb' stands for 'Write Binary'. As we are downloading the binary file.
        for chunk in response.iter_content(chunk_size= 8192):  # noqa: FURB122 (A Ruff detection disable code)
            f.write(chunk)
            # f.writelines(chunk) is useless as we are nt writing lines here

    _make_executable(destination_dir)
    return destination_dir


_DENO_ASSETS = {
    ("Windows", "amd64"): "deno-x86_64-pc-windows-msvc.zip",
    ("Linux", "x86_64"): "deno-x86_64-unknown-linux-gnu.zip",
    ("Darwin", "x86_64"): "deno-x86_64-apple-darwin.zip",
    ("Darwin", "arm64"): "deno-aarch64-apple-darwin.zip",
}


def _download_deno(target_dir: Path) -> Path | None:
    """deno ships as a per-platform zip containing one binary."""
    system = platform.system() # Detecting system
    machine = platform.machine().lower() # Detecting machine, amd64_86 etc. 
    if machine in ("amd64", "x86_64"):
        # because amd64 and x86_64 are the same thing, and Windows and other calls it iter System
        machine = "amd64" if system == "Windows" else "x86_64"

    asset_name = _DENO_ASSETS.get((system, machine))
    if asset_name is None:
        print(f"Error: No known deno build for {system}/{machine} - install it manually.")
        return None

    url = f"https://github.com/denoland/deno/releases/latest/download/{asset_name}"
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(url, timeout= 30, stream=True)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to download deno: {e}")
        return None

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        for chunk in response.iter_content(chunk_size=8192):
            tmp.write(chunk) # download the file as tempfile with adding the extension as '.zip'
        tmp_path = Path(tmp.name)

    try:
        with zipfile.ZipFile(tmp_path) as zf:
            zf.extractall(target_dir) # Extracts the zip file to target_dir
    finally:
        tmp_path.unlink(missing_ok=True) # Deletes the temporary zip file, if its ok then ok too

    binary_name = "deno.exe" if system == "Windows" else "deno"
    destination_dir = target_dir / binary_name
    if not destination_dir.exists():
        print("ERROR: expected deno binary missing after extracting zip.")
        return None

    _make_executable(destination_dir)
    return destination_dir


def _download_mkvtoolnix() -> None:
    """No portable cross-distro binary exists for mkvtoolnix — it has shared
    library dependencies that make a dropped-in executable unreliable outside
    the exact system it was built for. Detect the package manager instead and
    tell the user the one command to run. mkvmerge and mkvpropedit always
    install together as a single package, so one call covers both env keys."""
    system = platform.system()

    if system == "Windows":
        print("MKVToolNix has no automatable portable download.")
        print("Install with: winget install MoritzBunkus.MKVToolNix")
        print("or download the installer from https://mkvtoolnix.download/downloads.html#windows")
        return

    if system == "Linux":
        import shutil as _shutil
        managers = [
            ("apt", "sudo apt install mkvtoolnix"),
            ("dnf", "sudo dnf install mkvtoolnix"),
            ("pacman", "sudo pacman -S mkvtoolnix-cli"),
            ("zypper", "sudo zypper install mkvtoolnix"),
        ]
        for mgr, cmd in managers:
            if _shutil.which(mgr):
                print(f"MKVToolNix can't be auto-downloaded portably (it has system "
                      f"library dependencies). Detected {mgr} — run:\n  {cmd}")
                return
        print("MKVToolNix can't be auto-downloaded portably. Install it with your "
              "distro's package manager, e.g. 'apt install mkvtoolnix'.")
        return

    if system == "Darwin":
        print("MKVToolNix can't be auto-downloaded portably. Install with:\n  brew install mkvtoolnix")
        return

    print(f"Don't know how to suggest an install for MKVToolNix on {system} — install manually.")