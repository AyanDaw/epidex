"""mkv_tools.py — wrappers for the mkvmerge/mkvpropedit calls needed after a
download finishes.

Kept separate from Episode (data-only) and Downloader (yt-dlp only) so each
module owns exactly one external tool. Built once by cli.py with ToolPaths
and the audio-language settings fixed at construction; QueueManager holds
one MkvTools instance and calls fetch_runtime()/scrub_and_tag() per episode,
passing just the file path — same constructor/method split as Downloader.
"""

import json
import math
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from epidex.dependencies import ToolPaths  # TypeHint only


class MkvTools:
    """Holds tool paths + language settings; reused across every episode."""

    def __init__(self, tool_paths: ToolPaths, lang_code: str = "ben", lang_name: str = "[ বাংলা (Bengali) ]"):
        """Set once by cli.py — none of this changes between episodes.

        lang_code/lang_name are hardcoded defaults for now (this project's
        Bengali dub); same tier as Downloader's browser — a future EnvConfig
        field, not done yet.
        """
        self.toolpaths = tool_paths
        self.lang_code = lang_code
        self.lang_name = lang_name

    def fetch_runtime(self, file_path: str) -> str | None:
        """Get duration from the downloaded file itself via mkvmerge -J,
        in whole minutes rounded up (e.g. 6:30 -> 7, 5:01 -> 6, 9:00 -> 9).

        Returns None on any failure so QueueManager can tell fetch didn't
        happen — the caller is responsible for assigning the result onto
        ep.runtime; this function never touches Episode directly.
        """
        try:
            result = subprocess.run(
                [str(self.toolpaths.mkvmerge), "-J", file_path],
                capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)
            duration_ns = info["container"]["properties"]["duration"]
            duration_secs = duration_ns / 1_000_000_000
            return str(math.ceil(duration_secs / 60))
        except subprocess.CalledProcessError:
            print("Mkvmerge failed to read the runtime of the file")
            return None
        except json.JSONDecodeError:
            print("Invalid Json type, couldnot convert it to Runtime duration")
            return None
        except KeyError:
            print("Duration Key is missing from returned json, please fill it manually")
            return None

    def scrub_and_tag(self, file_path: str) -> bool:
        """Strip global tags, keep only video/audio, rename the audio
        stream + set its language tag using self.lang_code/self.lang_name.

        Returns True/False like Downloader.download() so QueueManager can
        tell whether tagging succeeded.
        """
        try:
            subprocess.run([
                        str(self.toolpaths.mkvpropedit),
                        file_path, "--tags", "all:",
                        "--edit", "info", "--set", "title=", "--edit", "track:a1",
                        "--set", f"language={self.lang_code}",
                        "--set", f"name={self.lang_name}",
                    ], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            print("Mkvpropedit failed to edit the file")
            return False