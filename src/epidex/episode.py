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

    def __init__(self, series: str, season: int, epnumber: int, maxeps: str, title: str, url: str):
        """maxeps is the season's total episode count as a string (e.g. "140")
        — its length gives the zero-padding width used in build_filename(),
        with a minimum of 2 ("140" -> E005, "9" -> E05)."""

        self.series: str = series                   # sent by Input Panel
        self.season: int = season                   # sent by Input Panel
        self.epnumber: int = epnumber               # sent by Input Panel
        self.maxeps: str = maxeps                   # sent by Input Panel
        self.title: str = title                     # sent by Input Panel
        self.url: str = url                         # sent by Input Panel
        self.runtime: str | None = None             # filled in by QueueManager, after mkv_tools.fetch_runtime()
        self.description: str | None = None         # set by Input Panel
        self.filename: str | None = None            # set by build_filename()
        self.download_status: bool = False          # filled in by QueueManager, after Downloader.download()


    def build_filename(self) -> str:
        """e.g. 'Series A S01E005 <Title>.mkv'.

        Builds the filename from the title InputPanel set.
        """
        padding: int = max(len(self.maxeps), 2)
        self.filename = f"{self.series} S{self.season:02d}E{self.epnumber:0{padding}d} {self.title}"
        self.filename = re.sub(r'[<>:"/\\|?*]', "", self.filename).strip()  # Sanitize for Windows
        self.filename += ".mkv"
        return self.filename


    def log_entry(self) -> str:
        """Return the '<Ep no.> <runtime> <description>' line for log.txt.

        No success/failure branching here by design — if download failed,
        runtime is still None and gets logged as-is (e.g. "5 None ...").
        A viewer/retry system may replace this later; not needed for now.
        """
        return f"{self.epnumber} {self.runtime} {self.description}\n"