import json
import queue
import random
import threading
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from epidex.paths import QUEUE_STATUS_FILE  # add to paths.py if it isn't there yet

if TYPE_CHECKING:
    from epidex.downloader import Downloader
    from epidex.episode import Episode
    from epidex.mkv_tools import MkvTools  # Just to know what is it


class QueueManager:
    """TLDR: owns the download queue + its two background threads (worker, status-writer).

    QueueManager is the pipeline orchestrator handed to cli.py. Producer
    (InputPanel) and consumer (this class's worker thread) run concurrently
    via self.q, but the worker processes exactly one Episode at a time —
    downloads are never parallel. Each episode goes through
    Downloader.download() -> on success MkvTools.fetch_runtime() +
    MkvTools.scrub_and_tag() -> log_fn/linkbook_fn -> status snapshot.
    """

    def __init__(
        self,
        downloader: "Downloader",
        mkv_tools: "MkvTools",
        log_fn: Callable[[str], None],      # logging_utils.append_to_log, wired by cli.py
        linkbook_fn: Callable[[str], None], # logging_utils.append_to_linkbook
        maxsize: int,
    ):
        """TLDR: wire in the collaborators cli.py already constructed; init empty queue/thread state."""
        self.q: queue.Queue[Episode | None] = queue.Queue(maxsize=maxsize)   # maxsize = 0 means unbounded queue
        self.downloader = downloader
        self.mkv_tools = mkv_tools
        self.log_fn = log_fn
        self.linkbook_fn = linkbook_fn

        self.current = None                     # the Episode currently being processed, if any
        self.stop_requested = False             # signal to let the worker thread exit cleanly
        self.worker_thread = None
        self.status_writer_thread = None


    def start(self):
        """Spin up the background thread that continuously processes the queue."""
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        self.status_writer_thread = threading.Thread(target=self._status_writer, daemon=True)
        self.status_writer_thread.start()

    def _worker(self):
        """Runs in the background thread. Loop: get one Episode, process it, repeat."""
        while not self.stop_requested:
            ep = self.q.get()
            if ep is None:          # sentinel, see stop() below
                self.q.task_done()
                break
            self.current = ep

            try:
                # Narrows ep.filename: str | None -> str for the type checker, and is the
                # actual runtime enforcement of the "build_filename() before enqueue()"
                # invariant from InputPanel — a violation logs loudly here instead of
                # surfacing as an unrelated TypeError further down.
                assert ep.filename is not None, f"episode {ep.epnumber} enqueued with no filename"
                ep.download_status = self.downloader.download(filename=ep.filename, url=ep.url)

                if ep.download_status:
                    full_path = str(Path(self.downloader.download_dir) / ep.filename)
                    ep.runtime = self.mkv_tools.fetch_runtime(file_path=full_path)
                    if not self.mkv_tools.scrub_and_tag(file_path=full_path): self.log_fn(f"{ep.filename} + FAILED TO SCRUB & TAG")


                self.log_fn(ep.log_entry())
                self.linkbook_fn(
                    ep.url if ep.download_status
                    else f"{ep.url} + NOT SUCCESSFUL!!"
                )

                time.sleep(random.randint(3,8))
            except Exception as e:  # noqa: BLE001
                self.log_fn(f"{ep.epnumber} WORKER ERROR: {e!r}\n{traceback.format_exc()}")
            finally:
                self.current = None     # Clears the work bench
                self.q.task_done()      # Next element

    def enqueue(self, ep: "Episode") -> None:
        """TLDR: hand one Episode to the worker. Blocks if the queue is full (queue.Queue's job, not ours)."""
        self.q.put(ep)


    def empty_slots(self) -> int:
        """TLDR: free capacity left before enqueue() would block."""
        return self.q.maxsize - self.q.qsize()  # (careful: maxsize=0 means "unbounded" in queue.Queue)


    def stop(self):
        """TLDR: tell the worker to finish its current item, then exit — doesn't stop status_writer."""
        self.stop_requested = True
        self.q.put(None)


    def snapshot(self) -> dict:
        """TLDR: current + pending queue state as a plain dict, for JSON-dumping to QUEUE_STATUS_FILE.

        Reads self.q.queue under self.q.mutex — that deque is mutated by
        InputPanel's enqueue() from a different thread, so an unlocked read
        can raise "deque mutated during iteration".
        """
        now_processing = self.current.epnumber if self.current else None
        now_title = self.current.title if self.current else None
        with self.q.mutex:
            left_in_q = list(self.q.queue)
        upcoming = [{"epnumber": ep.epnumber, "title": ep.title} for ep in left_in_q]
        return {
            "now_processing_epnumber": now_processing,
            "now_processing_title": now_title,
            "queue_length": str(len(upcoming))+f"/{self.q.maxsize}",
            "upcoming": upcoming,
        }


    def _status_writer(self):
        """TLDR: every 1s, dump snapshot() to QUEUE_STATUS_FILE for Qmonitor.py to poll and render."""
        while not self.stop_requested:
            snap = self.snapshot()
            with open(QUEUE_STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(snap, f, indent=2)
            time.sleep(1)