# QueueManager class

class QueueManager:
    """Owns a queue.Queue of Episode objects; a background thread pulls one at a time
    and runs it through download -> runtime -> tag, so nothing touches yt-dlp/mkv tools
    concurrently."""

    def __init__(self, maxsize: int):
        self.q = queue.Queue(maxsize=maxsize) # maxsize = 0 means unbounded queue
        self.current = None          # the Episode currently being processed, if any
        self.stop_requested = False  # signal to let the worker thread exit cleanly
        self.worker_thread = None

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
            ep.download_status = ep.download()
            
            if ep.download_status:
                ep.fetch_runtime()
                ep.scrub_and_tag()
            
            append_to_log(log= ep.log_entry())
            if not ep.download_status:
                append_to_linkbook(url= f"{ep.youtube_url} + NOT SUCCESSFUL!!")
            else:
                append_to_linkbook(url=ep.youtube_url)
            time.sleep(random.randint(3,8))
            self.current = None
            self.q.task_done()    # Next element

    def enqueue(self, ep) -> None:
        """Add an Episode to the queue. Blocks automatically if full — that's queue.Queue's job."""
        self.q.put(ep)


    def empty_slots(self) -> int:
        """How many more Episodes can be added before enqueue would block."""
        return self.q.maxsize - self.q.qsize()  # (careful: maxsize=0 means "unbounded" in queue.Queue)


    # Deleted Status memory

    def stop(self):
        """Signal the worker thread to finish after its current item and exit."""
        self.stop_requested = True
        self.q.put(None)

    # Status memory deleted so window is deleted too


    def snapshot(self) -> dict:
        """Convert current queue state into plain JSON-serializable data."""
        now_processing = self.current.epnumber if self.current else None
        now_title = self.current.title if self.current else None
        left_in_q = list(self.q.queue)
        upcoming = [{"epnumber": ep.epnumber, "title": ep.title} for ep in left_in_q]
        return {
            "now_processing_epnumber": now_processing,
            "now_processing_title": now_title,
            "queue_length": str(len(upcoming))+f"/{self.q.maxsize}",
            "upcoming": upcoming,
        }


    def _status_writer(self):
        """Runs in its own thread - periodically dumps snapshot() to a file for monitor.py to read."""
        while not self.stop_requested:
            snap = self.snapshot()
            with open(QUEUE_STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(snap, f, indent=2)
            time.sleep(1)