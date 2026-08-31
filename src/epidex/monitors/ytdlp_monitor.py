# old monitor.py

import time
from pathlib import Path


from epidex.paths import STOP_FLAG
from epidex.paths import YTDLP_LOG


def main():
    print("Watching yt-dlp / mkvmerge / mkvpropedit output...\n")
    YTDLP_LOG.touch(exist_ok=True)   # create it empty if this is the very first run
    with open(YTDLP_LOG, 'r', encoding="utf-8") as log:
        log.seek(0,2)
        while True:
            if STOP_FLAG.exists():
                print("\nQueue finished - closing.")
                time.sleep(2)
                break
            line = log.readline()
            if line:
                line = line.replace("\n", '')
                print(line, end="")
                if line.startswith("[download] Destination:"):
                    print('\n', end='')
                elif line.startswith("[download]"):
                    if line.startswith("[download] 100%"):
                        print('\n', end='')
                    else:
                        print('\r', end='')
                else:
                    print('\n', end='')
            else:
                time.sleep(0.5)

if __name__ == "__main__":
    main()