"""downloader.py — runs the actual yt-dlp subprocess for one episode at a time.

Built once by cli.py with the machine-dependent config (tool paths, download
dir, browser, codec) and then reused for every episode: QueueManager holds a
single Downloader instance and calls .download(filename, url) once per
episode pulled off the queue — download() takes the two pieces of data that
actually change per episode; everything else was fixed at construction.
"""

# Needed things to download a video
    # browser/it's cookies
    # codec

# Machine dependent (fixed for the whole run — set once in __init__)
    # yt-dlp bin
    # deno bin
    # download directory

# Episode specific (changes every call — passed as download() arguments)
    # filename
    # yt url

# TODO: Cookies method is still missing — browser is hardcoded for now;
# eventually should come from EnvConfig (validated against yt-dlp's
# supported browser list) and later support cookie files as an alternative.
# TODO: Currently CODEC is editable from code. I choose avc1 as its most compatible

import os
import subprocess

from epidex.cli import ToolPaths  # Just to know what is it.
from epidex.paths import OUTPUT_LOG


class Downloader:
    """Holds the config needed to run yt-dlp; reused across every episode."""

    def __init__(self, toolpaths: ToolPaths, download_dir: str, browser: str = "firefox", codec: str = "avc1"):
        """Set once by cli.py — none of this changes between episodes."""
        self.toolpaths = toolpaths
        self.download_dir = download_dir
        self.browser = browser
        self.codec = codec

    def download(self, filename: str, url: str) -> bool:
        """Kick off yt-dlp for one episode, block until done, return success/fail.

        filename/url are per-episode — passed in fresh on every call by
        QueueManager's worker loop, rather than stored on self.
        """
        extra_flags = {"start_new_session": True} if os.name != "nt" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        try:
            with open(OUTPUT_LOG, "a", encoding="utf-8") as logfile:
                subprocess.run([
                    str(self.toolpaths.yt_dlp), "--js-runtimes", f"deno:{self.toolpaths.deno}",
                    # "--ignore-errors",
                    "-f", f"bv[vcodec^={self.codec}]+ba/bv+ba",     # avc1 chosen as most compatible; falls back to any codec

                    "-o", filename,                                  # Output filename

                    "--cookies-from-browser", self.browser,          # Preferably firefox or its forks, or any browser
                                                                      # with accessible cookies. Later: cookie-file support.

                    "--merge-output-format", "mkv",                  # Hardcoded — everything downstream (mkv_tools) expects mkv

                    "-P", self.download_dir,

                    url,
                ], check=True, stdout=logfile, stderr=logfile, **extra_flags)

            return True

        except subprocess.CalledProcessError:
            with open(OUTPUT_LOG, "a", encoding="utf-8") as logfile:
                logfile.write("\n\n\n[ERROR]: yt-dlp failed to download the file!!\n\n\n")

            return False