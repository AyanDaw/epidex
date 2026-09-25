# dependencies.py — no EnvManager import at all

import platform
import shutil
import stat
import subprocess
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import requests

from epidex import paths
from epidex.env_manager import SeriesConfig

# We are not calling the Whole class, Just for type fitting.



@dataclass
class ToolPaths:
    yt_dlp: Path | None
    ffmpeg: Path | None
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
    tools_dir = paths.TOOLS_DIR

    yt_dlp = _resolve(config.yt_dlp_path, "yt-dlp", tools_dir, updates, "YT_DLP_PATH")
    ffmpeg = _resolve(config.ffmpeg_path, "ffmpeg", tools_dir, updates, "FFMPEG_PATH")
    deno = _resolve(config.deno_path, "deno", tools_dir, updates, "DENO_PATH")
    mkvmerge = _resolve(config.mkvmerge_path, "mkvmerge", tools_dir, updates, "MKVMERGE_PATH")
    mkvpropedit = _resolve(config.mkvpropedit_path, "mkvpropedit", tools_dir, updates, "MKVPROPEDIT_PATH")

    # cli will be running here in loop, so after getting this returned cli will check if any dependency is still none 
    return ToolPaths(yt_dlp, ffmpeg, deno, mkvmerge, mkvpropedit), updates


def _works(path: Path) -> bool:
    """Confirms a resolved binary actually runs, via --version."""
    try:
        result = subprocess.run([str(path), "--version"], capture_output=True, check=False, timeout=10)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _resolve(configured: str | None, name: str, managed_dir:Path, updates: dict[str, str], env_key_name: str) -> Path | None:
    """Its work is resolving Paths. It will check if there is already configured path. if not find it.
     If not there in the machine then it will ask to download permission. User can download  by their self 
     or let the app manage it.
     Three-tier lookup: .env -> managed tools dir -> PATH. Each candidate
    is confirmed with --version before being accepted. Silent — no
    printing, no downloading; caller decides what to say and do."""
    
    candidates: list[Path] = [] # Joto available options ache ete store hobe one by one porechecking hobe, first correct ta return jabe.
    if configured:
        candidates.append(Path(configured))
    binary_name = f"{name}.exe" if platform.system() == "Windows" else name
    candidates.append(managed_dir / binary_name)
    found_on_path = shutil.which(name)
    if found_on_path:
        candidates.append(Path(found_on_path))

    for candidate in candidates:
        if candidate.exists() and _works(candidate):
            resolved = str(candidate)
            if resolved != configured:
                updates[env_key_name] = resolved
            return candidate
    return None


def _downloader(name: str, target_dir: Path) -> bool:
    """Its work only to downloading not resolving.
    Can be used as downloading one dependencies or update all through CLI
    Attempt to install one missing tool. Returns success/failure only —
    caller re-resolves via check_dependencies() to find the actual path."""

    downloaders: dict[str, Callable[[Path], bool]] = {
    # dict_name: typehint > type[key type, value type]
    
    # This dictionary uses strings as keys (like "ffmpeg"). The values 
    # must be functions (Callables) that take a Path object as an input 
    # and return a bool (True/False) as an output.
    
        "yt_dlp" : lambda d: _download_yt_dlp(d) is not None, # is not None converts the output into its strict form.
        "ffmpeg" : lambda d: _download_ffmpeg(d) is not None, # Like its likely to return the bool, is not None makes
        "deno": lambda d: _download_deno(d) is not None,      # it strictly bool.
        "mkvmerge": lambda d: _download_mkvtoolnix(),
        "mkvpropedit" : lambda d: _download_mkvtoolnix(),
    }
    downloader = downloaders.get(name)
    return downloader(target_dir) if downloader else False


def _make_executable(path: Path) -> None:
    """chmod +x — no-op requirement on Windows, required on Linux/Mac."""
    if platform.system() != "Windows":
        path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


# For every downloader check if available else skip. Give a message for already availibility
def _download_yt_dlp(target_dir: Path) -> Path | None:
    """yt-dlp ships a single static binary with a permanent 'latest' URL per OS"""
    is_windows = platform.system() == 'Windows'
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


_FFMPEG_ASSETS = {
    "Windows": "https://github.com/yt-dlp/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip",
    "Linux": "https://github.com/yt-dlp/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-linux64-gpl.tar.xz"
}

def _download_ffmpeg(target_dir: Path) -> Path | None:
    """Static ffmpeg builds have no shared-library dependencies (unlike
    mkvtoolnix), so — like yt-dlp/deno — a direct download is the correct
    portable path here, not a package-manager fallback. There are currently
    no MacOS builds."""
    system = platform.system()
    url = _FFMPEG_ASSETS.get(system)
    if url is None:
        print(f"ERROR: no known static ffmpeg build for {system} — install manually.")
        return None

    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(url, timeout=60, stream=True)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: failed to download ffmpeg: {e}")
        return None

    suffix = ".zip" if system == "Windows" else ".tar.xz"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        for chunk in response.iter_content(chunk_size=8192):
            tmp.write(chunk)
        tmp_path = Path(tmp.name)

    binary_name = "ffmpeg.exe" if system == "Windows" else "ffmpeg"
    try:
        if system == "Windows":
            with zipfile.ZipFile(tmp_path) as zf:
                # gyan.dev zips nest the binary in a versioned bin/ subfolder
                member = next(n for n in zf.namelist() if n.endswith(binary_name))
                zf.extract(member, target_dir)
                (target_dir / member).rename(target_dir / binary_name)
        else:
            import tarfile
            with tarfile.open(tmp_path) as tf:
                member = next(n for n in tf.getnames() if n.endswith(f"/{binary_name}"))
                tf.extract(member, target_dir)
                (target_dir / member).rename(target_dir / binary_name)
    except (StopIteration, OSError) as e:
        print(f"ERROR: couldn't extract ffmpeg from archive: {e}")
        return None
    finally:
        tmp_path.unlink(missing_ok=True)

    dest = target_dir / binary_name
    _make_executable(dest)
    return dest


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


def _run_privileged(cmd: list[str]) -> bool:
    """Run an install command that may need sudo, letting the OS prompt for
    the password directly (never captured by us). Always drops the sudo
    credential cache afterward, success or failure, so the NEXT privileged
    call — even for a different tool a second later — prompts fresh instead
    of silently reusing this one."""
    try:
        result = subprocess.run(cmd, check=False) # no capture_output - inherits our TTY
        success = result.returncode == 0
    except FileNotFoundError:
        success = False
    finally:
        if cmd and cmd[0] == "sudo":
            subprocess.run(["sudo", "-k"], capture_output=True, check=False) # drop cached credential
    return success


_LINUX_PACKAGE_MANAGERS = [
    ("apt", ["sudo", "apt", "install", "-y", "mkvtoolnix"]),
    ("dnf", ["sudo", "dnf", "install", "-y", "mkvtoolnix"]),
    ("pacman", ["sudo", "pacman", "-S", "--noconfirm", "mkvtoolnix-cli"]),
    ("zypper", ["sudo", "zypper", "install", "-y", "mkvtoolnix"]),
]


def _download_mkvtoolnix() -> bool:
    """No portable cross-distro binary exists for mkvtoolnix — shared library
    dependencies (Qt, boost) mean the system package manager IS the correct
    distribution path here, not a fallback. mkvmerge + mkvpropedit always
    install together as one package."""
    import shutil as _shutil
    system = platform.system()

    if system == "Windows":
        if _shutil.which("winget"):
            print("Installing MKVToolNix via winget — approve the prompt if one appears.")
            if _run_privileged(["winget", "install", "-e", "--id", "MoritzBunkus.MKVToolNix"]):
                return True
            print("FALIURE: winget install failed or was declined.")
        print("Install manually: https://mkvtoolnix.download/downloads.html#windows")
        return False

    if system == "Linux":
        for mgr, cmd in _LINUX_PACKAGE_MANAGERS:
            if _shutil.which(mgr):
                print(f"Installing MKVToolNix via {mgr} — enter your password if prompted.")
                if _run_privileged(cmd):
                    return True
                print(f"{mgr} install failed or was declined.")
                return False
        print("No supported package manager found (apt/dnf/pacman/zypper). Install manually.")
        return False

    # ================================================================================================== #
    # Currently we dont support MacOS                                                                    #
    #                                                                                                    #
    # if system == "Darwin":                                                                             #
    #     if _shutil.which("brew"):                                                                      #
    #         print("Installing MKVToolNix via Homebrew.")                                               #
    #         if subprocess.run(["brew", "install", "mkvtoolnix"], check=True).returncode == 0:          #
    #             return True                                                                            #
    #         print("brew install failed.")                                                              #
    #     else:                                                                                          #
    #         print("Homebrew Not Found!")                                                               #
    #     print("Install manually: brew install mkvtoolnix")                                             #
    #     return False                                                                                   #
    # ================================================================================================== #

    print(f"Don't know how to install MKVToolNix on {system} — install manually.")
    return False



#TODO Add a Updater
#INFO No support for macOS