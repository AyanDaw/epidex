"""Episode class (download, fetch_runtime, scrub_and_tag, build_filename)"""

import json
import math
import os
import re
import subprocess
from pathlib import Path


class Episode:
    def __init__(self, series: str, season: int, epnumber: int, maxeps: str):
        """All variables"""

        self.series = series        # str, Done
        self.season = season        # int, Done
        self.epnumber = epnumber    # int, Done
        self.maxeps = maxeps        # str, Done
        self.title = None           # str, Done
        self.youtube_url = None     # str, Done
        self.runtime = None         # str, Done
        self.description = None     # str, Done
        self.filename = None        # str, Done
        self.download_status= False # bool, Done



    def build_filename(self) -> str:
        """e.g. 'Series A S01E<padding>5 <Title>'"""

        padding = len(self.maxeps)
        self.filename = f"{self.series} S{self.season:02d}E{self.epnumber:0{padding}d} {self.title}"
        self.filename = re.sub(r'[<>:"/\\|?*]', "", self.filename).strip() # Sanitizing for Windows
        self.filename += ".mkv" # Extension



    def download(self) -> bool:
        """Kick off yt-dlp download, block/poll untill done, set download_complete."""
        extra_flags = {"start_new_session": True} if os.name != "nt" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        try:
            with open(YTDLP_LOG, "a", encoding="utf-8") as logfile:
                subprocess.run([
                        YT_DLP_BIN, "--js-runtimes", f"deno:{DENO_BIN}",
                        "--ignore-errors", "-f", "bv[vcodec^=avc1]+ba/bv[vcodec^=avc1]+ba",
                        "-o", str(self.filename), "--cookies-from-browser", "firefox",
                        "--merge-output-format", "mkv", "-P", str(Path.cwd()),
                        self.youtube_url], check=True, stdout=logfile, stderr=logfile, **extra_flags)
            return True
        except subprocess.CalledProcessError:
            with open(YTDLP_LOG, "a", encoding="utf-8") as logfile:
                logfile.write("\n\n\nyt-dlp failed to download the file\n\n\n")
            return False



    def fetch_metadata(self, tmdb_cache):
        self.title = tmdb_cache.get(self.epnumber)   # Episode Title



    def fetch_runtime(self):
        """Get duration from the downloaded file itself via mkvmerge -J, set self.runtime in minutes."""

        try:
            result = subprocess.run(
                [MKVMERGE_BIN, "-J", str(self.filename)],
                capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)
            duration_ns = info["container"]["properties"]["duration"]
            duration_secs = duration_ns / 1_000_000_000
            self.runtime = str(math.ceil(duration_secs/60))   # e.g. 6:30 becomes 7, 5:01 becomes 6, 9:00 become 9. like this
        except subprocess.CalledProcessError:
            print("Mkvmerge failed to read the runtime of the file")
        except json.JSONDecodeError:
            print("Invalid Json type, couldnot convert it to Runtime duration")
        except KeyError:
            print("Duration Key is missing from returned json, please fill it manually")



    def log_entry(self) -> str:
        """Return the '<Ep no.> <runtime> <description>' line to append to your log file."""
        return f"{self.epnumber} {self.runtime} {self.description}\n"



    def scrub_and_tag(self):
        """Strip global tags, keep only videos/audio, rename audio stream + set 'bn' lang tag."""
        try:
            subprocess.run([
                        MKVPROPEDIT_BIN,
                        str(self.filename), "--tags", "all:",
                        "--edit", "info", "--set", "title=", "--edit", "track:a1",
                        "--set", "language=ben",
                        "--set", "name=[ বাংলা (Bengali) ]",
                    ], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            print("Mkvpropedit failed to edit the file")