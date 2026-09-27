"""Episode class — pure data holder for one episode's identity and pipeline state.

No tool paths, no subprocess, no filesystem access beyond string building.
QueueManager reads from and writes onto instances of this class as an
episode moves through the pipeline: download_status and runtime are set by
QueueManager's worker after calling Downloader/mkv_tools; everything else is
set up-front by InputPanel before the episode ever reaches the queue.
"""

import re


class Episode:
    """Holds one episode's identity, TMDB metadata, and pipeline state."""

    def __init__(self, series: str, season: int, epnumber: int, maxeps: str, yt_url: str):
        """maxeps is the season's total episode count, passed as a string
        (e.g. "140") — its length gives the zero-padding width used in
        build_filename() (e.g. "140" -> pad to 3 digits: E005)."""

        self.series = series
        self.season = season
        self.epnumber = epnumber
        self.maxeps = maxeps
        self.title = None              # set by fetch_metadata()
        self.youtube_url = yt_url
        self.runtime = None             # filled in by QueueManager, after mkv_tools.fetch_runtime()
        self.description = None
        self.filename = None            # set by build_filename()
        self.download_status = False    # filled in by QueueManager, after Downloader.download()

    def build_filename(self) -> str:
        """e.g. 'Series A S01E005 <Title>.mkv'.

        MUST be called after fetch_metadata() — title has to be set first,
        or this silently writes the literal string "None" into the filename
        instead of erroring.
        """
        padding = len(self.maxeps)
        self.filename = f"{self.series} S{self.season:02d}E{self.epnumber:0{padding}d} {self.title}"
        self.filename = re.sub(r'[<>:"/\\|?*]', "", self.filename).strip()  # Sanitize for Windows
        self.filename += ".mkv"
        return self.filename

    def fetch_metadata(self, tmdb_cache):
        """Look up this episode's title from the season's cached TMDB data.
        Call this before build_filename()."""
        self.title = tmdb_cache.get(self.epnumber)

    def log_entry(self) -> str:
        """Return the '<Ep no.> <runtime> <description>' line for log.txt.

        No success/failure branching here by design — if download failed,
        runtime is still None and gets logged as-is (e.g. "5 None ...").
        A viewer/retry system may replace this later; not needed for now.
        """
        return f"{self.epnumber} {self.runtime} {self.description}\n"