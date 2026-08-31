# old Qmonitor.py

import json
import os
import subprocess
import time
from pathlib import Path

from epidex.paths import QUEUE_STATUS_FILE
from epidex.paths import STOP_FLAG


def main():
    while True:
        if STOP_FLAG.exists():
            subprocess.run("cls" if os.name == "nt" else "clear", shell=True)
            print("Queue finished — closing.")
            time.sleep(2)   # give you a moment to read it before the window closes
            break
        data = {}
        try:
            with open(QUEUE_STATUS_FILE, "r") as f:
                data = json.load(f)
                if not data:
                    time.sleep(1)
                    continue # Placeholder
        except json.JSONDecodeError:
            # JSON error
            time.sleep(1)
            continue
        except PermissionError:
            # file is busy
            time.sleep(1)
            continue
        except OSError:
            print("Other Filesystem-related errors (disk issues, invalid path, etc.).")
            time.sleep(1)
            continue

        subprocess.run("cls" if os.name == "nt" else "clear", shell=True)
        title = data["now_processing_title"]
        epnum = data["now_processing_epnumber"]
        queue_len = data["queue_length"]
        upcoming = "\n".join(ep["title"] for ep in data["upcoming"])
        print(
            f"Now Processing Episode: {epnum} : {title}\n"
            f"Queue Storage: {queue_len}\n"
            f"Queue :\n"
            f"{upcoming}"
        )
        time.sleep(5)

if __name__ == "__main__":
    main()