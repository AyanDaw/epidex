"""queue_monitor — live view of the queue snapshot written by QueueManager.

Runs in its own console tab, spawned by cli.py. Re-reads QUEUE_STATUS_FILE
every REFRESH_SECONDS and exits once STOP_FLAG exists.
"""

import json
import os
import subprocess
import time

from epidex.paths import QUEUE_STATUS_FILE, STOP_FLAG

REFRESH_SECONDS = 5   # keep well under cli.py's wait for this process to exit


def _clear_screen():
    """Clear this console: 'cls' on Windows, 'clear' everywhere else."""
    subprocess.run("cls" if os.name == "nt" else "clear", check=False, shell=True)


def _read_snapshot() -> dict | None:
    """Return the parsed snapshot, or None if it can't be used right now
    (missing, empty, mid-write, or locked). The caller just tries again."""
    try:
        with open(QUEUE_STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f) or None   # an empty dict counts as "nothing yet"
    except (json.JSONDecodeError, PermissionError, FileNotFoundError):
        # mid-write / file busy / QueueManager hasn't written its first snapshot yet
        return None
    except OSError:
        print("Other filesystem-related error (disk issue, invalid path, etc.).")
        return None


def main():
    """Redraw the queue status until STOP_FLAG appears."""
    while True:
        if STOP_FLAG.exists():
            _clear_screen()
            print("Queue finished — closing.")
            time.sleep(2)            # give you a moment to read it before the window closes
            break

        data = _read_snapshot()
        if data is None:
            time.sleep(1)
            continue

        epnum = data["now_processing_epnumber"]
        title = data["now_processing_title"]
        if epnum is None:            # idle, or the final "All done!" snapshot
            header = f"Now Processing: {title or 'Idle'}"
        else:
            header = f"Now Processing Episode: {epnum} : {title}"
        upcoming = "\n".join(ep["title"] for ep in data["upcoming"])

        _clear_screen()
        print(
            f"{header}\n"
            f"Queue Storage: {data['queue_length']}\n"
            f"Queue :\n"
            f"{upcoming}"
        )
        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    main()