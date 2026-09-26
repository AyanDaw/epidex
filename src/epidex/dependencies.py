"""
Resolves and, when needed, installs the external binaries epidex depends on:
yt-dlp, ffmpeg, deno, mkvmerge, mkvpropedit.

This module is a pure function boundary. check_dependencies() takes a
SeriesConfig in and returns (ToolPaths, updates) out, with no file I/O on
.env and no prints. Nothing here calls sys.exit(); every failure is reported
through the return values, and it is cli.py's job to decide what the user
sees and what happens next.

Downloading is a separate, explicit phase. check_dependencies() only checks
and reports; cli.py calls _downloader() afterward, only for tools it
decided are missing, only after the user has agreed to it.

Per-tool install strategy (locked, not arbitrary): yt-dlp, ffmpeg, and deno
are fetched as direct static-binary downloads, because each has a specific
reason a distro package manager would be worse: yt-dlp's packaged versions
lag behind the fixes YouTube-breakage requires; the ffmpeg used here is
yt-dlp's own patched fork, which no package manager carries; deno is not in
default apt/dnf repos at all. mkvmerge/mkvpropedit go through the system
package manager instead, because they have real shared-library dependencies
(Qt, boost) and no portable static build exists for them; the package
manager is the only correct source there, not a fallback.

macOS is not a supported platform yet. Where a per-tool branch would need
one, it is left out or commented, not silently handled.
"""

import platform
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import requests

from epidex import paths
from epidex.env_manager import EnvConfig  # only for the type, not the class


@dataclass
class ToolPaths:
    """Resolved binary paths for every tool this app needs at runtime.

    A field is None when that tool could not be found or confirmed working
    anywhere (.env, the managed tools folder, or PATH). cli.py is expected
    to check for None fields before proceeding with anything that needs
    that tool.
    """

    yt_dlp: Path | None
    ffmpeg: Path | None
    deno: Path | None
    mkvmerge: Path | None
    mkvpropedit: Path | None


def check_dependencies(config: EnvConfig) -> tuple[ToolPaths, dict[str, str]]:
    """TLDR: resolve all five tools, report results, change nothing.

    Returns (ToolPaths, updates). ToolPaths is always fully built, one
    field per tool, for immediate runtime use. updates is
    {ENV_KEY: resolved_path}, containing only the tools whose resolved
    location differs from what was already in .env; cli.py is expected to
    hand this to env_manager for persistence. Values in updates are always
    str, since that is what env_manager and python-dotenv expect.

    This function never prints, never downloads, and never exits. It is
    safe to call repeatedly, including in a retry loop after a download
    attempt.
    """
    updates: dict[str, str] = {}
    tools_dir = paths.TOOLS_DIR

    yt_dlp = _resolve(config.yt_dlp_path, "yt-dlp", tools_dir, updates, "YT_DLP_PATH")
    ffmpeg = _resolve(config.ffmpeg_path, "ffmpeg", tools_dir, updates, "FFMPEG_PATH")
    deno = _resolve(config.deno_path, "deno", tools_dir, updates, "DENO_PATH")
    mkvmerge = _resolve(config.mkvmerge_path, "mkvmerge", tools_dir, updates, "MKVMERGE_PATH")
    mkvpropedit = _resolve(config.mkvpropedit_path, "mkvpropedit", tools_dir, updates, "MKVPROPEDIT_PATH")

    return ToolPaths(yt_dlp, ffmpeg, deno, mkvmerge, mkvpropedit), updates


def _works(path: Path) -> bool:
    """TLDR: confirm a candidate binary actually runs, not just exists.

    Runs `<path> --version` and treats a zero exit code as working. A path
    that exists but is corrupted, wrong-architecture, or half-downloaded
    will fail this and get rejected by _resolve rather than accepted and
    only discovered broken later, mid-download or mid-merge.
    """
    try:
        result = subprocess.run(
            [str(path), "--version"], capture_output=True, check=False, timeout=10
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _resolve(
    configured: str | None,
    name: str,
    managed_dir: Path,
    updates: dict[str, str],
    env_key_name: str,
) -> Path | None:

    """TLDR: find one tool by checking .env, then the managed tools folder,
    then PATH, accepting only a candidate that actually runs.

    Order of preference: an explicit path already saved in .env, then the
    app's own managed tools folder (paths.TOOLS_DIR), then whatever the OS
    finds on PATH. Every candidate is confirmed with _works() before being
    accepted, so a stale or broken .env entry correctly falls through to
    the next tier instead of being trusted.

    If the winning candidate's path differs from what was configured,
    its str form is recorded in updates under env_key_name, so the caller
    can persist the correction. Returns None if nothing usable was found
    at any tier.

    This function is silent by design: no printing, no downloading. It
    only reports what it found.
    """
    candidates: list[Path] = []
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
    """TLDR: attempt to install one missing tool by its canonical name.

    Returns only success or failure. It deliberately does not return a
    Path: the caller is expected to call check_dependencies() again
    afterward and let _resolve() find the actual location, whether that is
    inside target_dir (yt-dlp, ffmpeg, deno) or wherever a package manager
    chose to put it (mkvmerge, mkvpropedit). This keeps every entry in the
    dispatch table below the same shape, regardless of how differently
    each underlying installer behaves.
    """
    downloaders: dict[str, Callable[[Path], bool]] = {
    # dict_name: typehint > type[key type, value type]
    
    # This dictionary uses strings as keys (like "ffmpeg"). The values 
    # must be functions (Callables) that take a Path object as an input 
    # and return a bool (True/False) as an output.
    
        "yt_dlp" : lambda d: _download_yt_dlp(d) is not None, # is not None converts the output into its strict form.
        "ffmpeg" : lambda d: _download_ffmpeg(d) is not None, # Like its likely to return the bool, is not None makes
        "deno": lambda d: _download_deno(d) is not None,      # it strictly bool.
        "mkvmerge": lambda d: _download_mkvtoolnix(),
        "mkvpropedit": lambda d: _download_mkvtoolnix(),
    }
    downloader = downloaders.get(name)
    return downloader(target_dir) if downloader else False


def _make_executable(path: Path) -> None:
    """TLDR: chmod +x a downloaded binary. No-op on Windows, required on
    Linux (and, if ever supported, macOS), since a freshly downloaded file
    has no execute bit set yet.
    """
    if platform.system() != "Windows":
        path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _download_yt_dlp(target_dir: Path) -> Path | None:
    """TLDR: download the current yt-dlp release binary for this OS.

    yt-dlp ships a single static, self-contained binary per OS, and
    publishes it at a permanent "latest" URL, so no version lookup or
    archive extraction is needed here, unlike ffmpeg and deno below.
    """
    is_windows = platform.system() == "Windows"
    asset_name = "yt-dlp.exe" if is_windows else "yt-dlp"
    url = f"https://github.com/yt-dlp/yt-dlp/releases/latest/download/{asset_name}"

    target_dir.mkdir(parents=True, exist_ok=True)
    destination_dir = target_dir / asset_name

    try:
        response = requests.get(url=url, timeout=30, stream=True) 
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


# Static, patched ffmpeg builds maintained by the yt-dlp project itself,
# not a generic ffmpeg distribution. These carry fixes specific to sites
# yt-dlp downloads from and are the build yt-dlp's own docs recommend.
# There are currently no macOS builds published upstream, so Darwin has no
# entry here; _download_ffmpeg reports that clearly instead of guessing.

_FFMPEG_ASSETS = {
    "Windows": "https://github.com/yt-dlp/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip",
    "Linux": "https://github.com/yt-dlp/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-linux64-gpl.tar.xz",
}


def _download_ffmpeg(target_dir: Path) -> Path | None:
    """TLDR: download and extract yt-dlp's patched ffmpeg build for this OS.

    Unlike yt-dlp, ffmpeg ships as an archive (zip on Windows, tar.xz on
    Linux) with the binary nested a few folders deep, alongside ffprobe and
    other files we do not need. Only the single ffmpeg binary is pulled
    out and placed directly in target_dir; the now-empty parent folder
    left behind by extraction is removed afterward so repeated runs do not
    accumulate clutter.
    """
    system = platform.system()
    url = _FFMPEG_ASSETS.get(system)
    if url is None:
        print(f"ERROR: no known static ffmpeg build for {system}. Install manually.")
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
                # yt-dlp/FFmpeg-Builds zips nest the binary in a versioned bin/ subfolder.
                member = next(n for n in zf.namelist() if n.endswith(binary_name))
                zf.extract(member, target_dir)
                (target_dir / member).rename(target_dir / binary_name)
                shutil.rmtree(target_dir / member.split("/")[0], ignore_errors=True)
        else:
            with tarfile.open(tmp_path) as tf:
                member = next(n for n in tf.getnames() if n.endswith(f"/{binary_name}"))
                tf.extract(member, target_dir)
                (target_dir / member).rename(target_dir / binary_name)
                shutil.rmtree(target_dir / member.split("/")[0], ignore_errors=True)
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
    """TLDR: download and extract the current deno release for this OS
    and CPU architecture.

    Deno also ships as a per-platform zip with a single binary inside, so
    the asset name has to account for both OS and CPU architecture, unlike
    yt-dlp which only varies by OS.
    """
    system = platform.system()
    machine = platform.machine().lower()
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
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: failed to download deno: {e}")
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
    """TLDR: run an install command that may need elevated privileges,
    letting the OS handle the prompt itself.

    stdin/stdout are never captured, so if cmd starts with sudo, the
    terminal sudo is actually attached to prompts for the password the
    normal way; this function never sees or touches it. Regardless of
    success or failure, the sudo credential cache is dropped afterward
    (sudo -k), so back-to-back installs of different tools each prompt
    fresh instead of silently reusing one earlier approval.
    """
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
    """TLDR: install mkvmerge and mkvpropedit through the system's own
    package manager, since no portable static build exists for either.

    Unlike yt-dlp, ffmpeg, and deno, mkvtoolnix has real shared-library
    dependencies (Qt, boost), so a dropped-in binary would not reliably
    run across different systems. The package manager is the correct
    source here, not a fallback, and mkvmerge/mkvpropedit always install
    together as one package, so this single function satisfies both
    dependency entries.

    Windows tries winget first, since it can be invoked the same way as
    any other subprocess and lets Windows show its own UAC prompt. Linux
    tries apt, dnf, pacman, and zypper in turn, using whichever is found
    first. Neither path takes a target_dir; the OS decides where the
    installed files live.
    """
    system = platform.system()

    if system == "Windows":
        if shutil.which("winget"):
            print("Installing MKVToolNix via winget. Approve the prompt if one appears.")
            if _run_privileged(["winget", "install", "-e", "--id", "MoritzBunkus.MKVToolNix"]):
                return True
            print("winget install failed or was declined.")
        print("Install manually: https://mkvtoolnix.download/downloads.html#windows")
        return False

    if system == "Linux":
        for mgr, cmd in _LINUX_PACKAGE_MANAGERS:
            if shutil.which(mgr):
                print(f"Installing MKVToolNix via {mgr}.\nEnter your password if prompted.")
                if _run_privileged(cmd):
                    return True
                print(f"{mgr} install failed or was declined.")
                return False
        print("No supported package manager found (apt, dnf, pacman, zypper). Install manually.")
        return False

    # ================================================================================================== #
    # Currently we dont support MacOS                                                                    #
    #                                                                                                    #
    # if system == "Darwin":                                                                             #
    #     if shutil.which("brew"):                                                                      #
    #         print("Installing MKVToolNix via Homebrew.")                                               #
    #         if subprocess.run(["brew", "install", "mkvtoolnix"], check=True).returncode == 0:          #
    #             return True                                                                            #
    #         print("brew install failed.")                                                              #
    #     else:                                                                                          #
    #         print("Homebrew Not Found!")                                                               #
    #     print("Install manually: brew install mkvtoolnix")                                             #
    #     return False                                                                                   #
    # ================================================================================================== #

    print(f"Don't know how to install MKVToolNix on {system}. Install manually.")
    return False


# TODO: version-check / update function for yt-dlp, ffmpeg, deno.
# Separate from check_dependencies() on purpose: comparing installed vs
# latest release requires a network call per tool, which check_dependencies
# is not meant to do on every ordinary run.