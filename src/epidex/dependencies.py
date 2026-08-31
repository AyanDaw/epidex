# dependencies.py — no EnvManager import at all

from typing import Literal
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

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

    return (ToolPaths(yt_dlp=yt_dlp, deno=deno, mkvmerge=mkvmerge, mkvpropedit=mkvpropedit), updates)


def _resolve(configured: str | None, name: str, env_key_name: str, updates: dict[str, str]) -> Path:
    """Its work is only resolving Paths."""
    if configured and Path(configured).exists():
        return Path(configured) # already correct path in .env
    elif configured and not Path(configured).exists():
        print(f"WARNING: {env_key} in .env points to '{configured}', but that path "
              f"doesn't exist — falling back to PATH lookup.")

        
    return ...

def _downloader(name: Literal["yt-dlp", "deno", "mkvmerge", "mkvpropedit"]) -> bool:
    """Called by cli not resolve. Its work only to downloading not resolving.
    Can be used as downloading one dependencies or update all through CLI"""
    return bool(successful)


# def _resolve(configured: str | None, name: str, env_key: str,
#              updates: dict[str, str], downloader) -> Path:
#     if configured and Path(configured).exists():
#         return configured   # already correct in .env — nothing to report back
#     if configured:
#         print(f"WARNING: {env_key} in .env points to '{configured}', but that path "
#               f"doesn't exist — falling back to PATH lookup.")

#     found = shutil.which(name)
#     if found:
#         updates[env_key] = found
#         return found

#     if downloader is not None:
#         print(f"'{name}' not found — attempting to download it automatically...")
#         downloaded = downloader()
#         if downloaded:
#             updates[env_key] = downloaded
#             return downloaded

#     if downloader is None:
#         sys.exit(f"ERROR: '{name}' not found on PATH, and {env_key} isn't set in .env.\n"
#                   f"mkvtoolnix must be installed manually, then either add it to PATH "
#                   f"or set {env_key} in .env.")
#     sys.exit(f"ERROR: couldn't find or download '{name}'. Install it manually, "
#               f"then add it to PATH or set {env_key} in .env.")


# def _download_yt_dlp() -> str | None: ...
# def _download_deno() -> str | None: ...
































# resolve_tool, check_dependencies, auto-install/auto-download logic

def resolve_tool(name: str, env_key: str) -> str:
    """Fixes the dependency checks. .env override first, PATH lookup second, exits with an actionable message otherwise."""
    configured = (config.get(env_key) or "").strip()
    if configured:
        if Path(configured).exists():
            return configured
        print(f"WARNING: {env_key} in .env points to '{configured}', but that path doesn't exist — falling back to PATH.")

    found = shutil.which(name)
    if found:
        return found

    if configured:
        sys.exit(f"ERROR: couldn't find '{name}' — the path in .env ('{configured}') doesn't exist, "
                  f"and it's not on PATH either. Fix {env_key} in .env or add {name} to PATH.")
    sys.exit(f"ERROR: '{name}' not found on PATH, and {env_key} isn't set in .env. "
              f"Install it, then either add it to PATH or set {env_key} in .env to its full path.")


def check_dependencies():
    global YT_DLP_BIN, DENO_BIN, MKVMERGE_BIN, MKVPROPEDIT_BIN
    YT_DLP_BIN = resolve_tool("yt-dlp", "YT_DLP_PATH")
    DENO_BIN = resolve_tool("deno", "DENO_PATH")
    MKVMERGE_BIN = resolve_tool("mkvmerge", "MKVMERGE_PATH")
    MKVPROPEDIT_BIN = resolve_tool("mkvpropedit", "MKVPROPEDIT_PATH")
    for label, path in [("yt-dlp", YT_DLP_BIN), ("deno", DENO_BIN),
                        ("mkvmerge", MKVMERGE_BIN), ("mkvpropedit", MKVPROPEDIT_BIN)]:
        try:
            subprocess.run([path, "--version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            sys.exit(f"ERROR: found a path for {label} ('{path}') but running it failed.")


def sync_resolved_paths_to_env():
    """After check_dependencies() resolves each tool - possibly via PATH, not .env -
    write the resolved paths back so next run skips the PATH lookup entirely."""
    data = dotenv_values(ENV_FILE)
    data["YT_DLP_PATH"] = YT_DLP_BIN or ""
    data["DENO_PATH"] = DENO_BIN or ""
    data["MKVMERGE_PATH"] = MKVMERGE_BIN or ""
    data["MKVPROPEDIT_PATH"] = MKVPROPEDIT_BIN or ""
    _write_env(data)