"""ytdlp_monitor — live view of the yt-dlp output log.

Runs in its own console tab, spawned by cli.py. Tails YTDLP_LOG (written by
Downloader and MkvTools) and exits once STOP_FLAG exists and the log has been
fully read.
"""

import time

from epidex.paths import STOP_FLAG, YTDLP_LOG

# yt-dlp progress lines that must end with a real newline instead of "\r"
_NEWLINE_AFTER = ("[download] Destination:", "[download] 100%")


def _print_line(line: str):
    """Print one log line so yt-dlp's progress output looks right: progress
    updates overwrite themselves ("\\r"), everything else gets its own line."""
    line = line.replace("\n", "")
    print(line, end="")
    if line.startswith("[download]") and not line.startswith(_NEWLINE_AFTER):
        print(end="\r")
    else:
        print()


def main():
    """Tail YTDLP_LOG from its current end, printing new lines as they arrive."""
    print("Watching yt-dlp / mkvmerge / mkvpropedit output...\n")
    YTDLP_LOG.touch(exist_ok=True)   # create it empty if this is the very first run
    # errors="replace": yt-dlp's file encoding isn't guaranteed to be UTF-8 on
    # every OS, and one undecodable byte must not kill the monitor mid-download.
    with open(YTDLP_LOG, "r", encoding="utf-8", errors="replace") as log:
        log.seek(0, 2)               # start at the end: only show new output
        while True:
            line = log.readline()
            if line:
                _print_line(line)
            elif STOP_FLAG.exists():
                break                # flag set AND nothing left to read: safe to close
            else:
                time.sleep(0.5)
    print("\nQueue finished - closing.")
    time.sleep(2)                    # give you a moment to read it before the window closes


if __name__ == "__main__":
    main()