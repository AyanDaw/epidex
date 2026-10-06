"""InputPanel — the interactive producer side of the download queue.

Asks the user, one episode at a time, for the episode URL and description,
looks the title up in the season's cached TMDB metadata ({epnumber: title}),
builds an Episode, and hands it to QueueManager.enqueue(). It never downloads,
tags, or touches the filesystem itself.

QueueManager and LogWriter are injected by cli.py (imported here only for type
hints); Episode is the one sibling import, because it is a pure data type.

run() always returns normally instead of calling exit(), so cli.py can drain
the queue and shut the monitors down cleanly afterwards.
"""

import os
import random
import subprocess
import time
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from epidex.episode import Episode  # only sibling import: Episode is a pure data type

if TYPE_CHECKING:   # type hints only; cli.py injects the real instances
    from epidex.logging_utils import LogWriter
    from epidex.queue_manager import QueueManager

FUNNY_MSG = ["Wait i ate too much, *burrrrp* let me digest some food :)", 
             "Hey You are working too hard, Its a water break reminder",
             "Its good to take break sometimes ;)",
             "Have you taken a washroom break? remember dont long hold your pee :|"]

_YT_HOSTS = ("youtube.com", "youtu.be")


class InputPanel:
    """Prompts for episode details and feeds finished Episodes into the queue.

    Attributes mirror the constructor arguments, plus last_episode: the highest
    episode number in season_metadata. It marks the end of the season and is
    passed to Episode as maxeps for filename zero-padding.
    """
    def __init__(self, user: str, manager: QueueManager, log_writer: LogWriter, series: str, season: int,
                 season_metadata: dict, min_free_slots: int = 2):
        """user is a display name used in interrupt messages (placeholder for
        future multi-user features). manager and log_writer are injected by
        cli.py. season_metadata is the {episode_number: title} dict built by
        tmdb.py. min_free_slots is how many queue slots must be open before
        input resumes after the queue has filled up."""
        
        self.user = user # Place holder for now for future upgrades
        self.manager = manager
        self.log_writer = log_writer
        self.series = series
        self.season = season
        self.season_metadata = season_metadata
        self.min_free_slots = min_free_slots
        self.last_episode = max(season_metadata, default=0)


    def wait_for_space(self, next_episode: int):
        """TLDR: queue full -> print one rest message, then quietly wait until min_free_slots are open.

        Does nothing unless the queue is completely full. Once it is, blocks
        (polling every second) until min_free_slots are free, so the user gets
        a batch of room instead of one slot at a time. next_episode is only
        used in the message. Ctrl+C here propagates up to run().
        """

        if self.manager.empty_slots() != 0:
            return
        print(random.choice(FUNNY_MSG))
        print(f"You'll enter episode {next_episode} once the break ends. Keep your details ready in the clip-board.")
        while self.manager.empty_slots() < self.min_free_slots:
            time.sleep(1)


    def run(self, start_epnumber: int):
        """Main input loop: build one Episode per iteration and enqueue it, until told to stop.

        start_epnumber is the episode number to start asking from.

        Each iteration: stop if past the season's last episode; wait for queue
        space; look the title up in season_metadata (if it is missing, offer to
        skip that episode); ask for the URL and description; build the Episode
        and enqueue it; clear the screen.

        Returns (never exits the process) when: the user types 'quit'; the
        episode number passes the season's last episode; the user declines to
        skip an episode with no title; or Ctrl+C hits anywhere outside the URL
        and description prompts. Ctrl+C at those two prompts only cancels the
        current entry, and the same episode is asked again. cli.py takes over
        after return to drain the queue.

        Log markers written: "[SKIPPED]: <ep>" for every skipped episode, and
        "[FINALE]: Season complete" when the season's last episode is reached,
        either by the end-of-season check (only if this run handled at least
        one episode) or by skipping the last episode.
        """

        epnumber = start_epnumber
        print("(Type 'quit' at the URL prompt to stop adding episodes. Ctrl+C at a prompt cancels that entry; "
              "Ctrl+C during a break or the skip question stops adding. Either way, the queue finishes before exit.)\n")
        try:
            while True:
                if epnumber > self.last_episode:
                    print(f"Episode {epnumber} is past the end of the season ({self.last_episode}). Done adding.")
                    if epnumber > start_epnumber:
                        self.log_writer.append_to_log("[FINALE]: Season complete\n")
                    break
                self.wait_for_space(epnumber) # Epnumber is the next episode cause we are stopping it before entering of epnumber
                title = self.season_metadata.get(epnumber)
                if title is None:
                    print("Metadata returned 'None' as Title. Either SKIP the episode"
                    "\nand manually DOWNLOAD the episode later..."
                    "\nOR"
                    "\nRESTART the program after EXITING...")
                    try:
                        if _ask_yes_no("Want to skip? if not then we stop adding."):
                            print(f"Episode {epnumber} skipped...")
                            self.log_writer.append_to_log(f"[SKIPPED]: {epnumber}\n")
                            if epnumber+1 <= self.last_episode:
                                print (f"\nMoving to the next Episode whose episode number is {epnumber+1}.") 
                            else:
                                print("\nThere are no more Episodes in this season. Done adding.")
                                self.log_writer.append_to_log("[FINALE]: Season complete\n")
                                break
                            epnumber += 1
                            input("Press 'Enter' to continue")
                            _clear_screen()
                            continue
                        else:
                            break       # cli.py drains the queue and shuts down

                    except KeyboardInterrupt:
                        print(f"Interrupted by {self.user}")
                        break
                print(f"\nThis Episode is going to be downloaded:v\n\n\t{epnumber} : {title}\n")
                    
                try:
                    url = input("Episode URL, or 'quit' to stop:> " ).strip()
                except KeyboardInterrupt:
                    print(f"\nCancelled — Episode {epnumber} will be asked again.")
                    continue

                if url.lower() == "quit":
                    break

                if not _looks_like_url(url):
                    print("That doesn't look like a valid http(s) link.")
                    continue
                url = _clean_url(url)
                try:

                    description = input("Paste the description here:> ").strip()
                except KeyboardInterrupt:
                    print(f"\nCancelled — Episode {epnumber} will be asked again.")
                    continue
                
                ep = Episode(
                    series=self.series, 
                    season=self.season,
                    epnumber=epnumber, 
                    maxeps=str(self.last_episode),
                    title = title,
                    url=url)

                ep.description = description
                ep.build_filename()
                self.manager.enqueue(ep=ep)
                _clear_screen()
                epnumber += 1

        except KeyboardInterrupt:
            print(f"Interrupted by {self.user}")




# ================================================================
# URL Utility Tools
# ================================================================

def _clean_url(url: str) -> str:
    """TLDR: drop YouTube's `si` share-tracking param only; leave other sites/params alone.

    Only hosts in _YT_HOSTS (and their subdomains) are touched; every other URL
    is returned unchanged. Other query params are kept, in order.
    e.g. 'https://youtu.be/abc?si=XYZ&t=30' -> 'https://youtu.be/abc?t=30'
    """

    parts = urlsplit(url)
    host = parts.hostname or ""
    if not any(host == hosts or host.endswith("." + hosts) for hosts in _YT_HOSTS):
        return url
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "si"]
    return urlunsplit(parts._replace(query=urlencode(query)))


def _looks_like_url(url: str) -> bool:
    """True if url has an http(s) scheme and a host. Syntax check only —
    whether yt-dlp supports the site is left for yt-dlp to report."""

    parts = urlsplit(url)
    return parts.scheme in ("http", "https") and bool(parts.netloc)




# ================================================================
# Helper Tools
# ================================================================

def _ask_yes_no(prompt: str) -> bool:
    """Ask a [Y/n] question. Enter, 'y', 'yes' mean yes; 'n', 'no' mean no; anything else re-asks.

    Ctrl+C is not caught here; it propagates to the caller.
    """

    while True:
        answer = input(f"{prompt} [Y/n]:> ").strip().lower()
        if answer in ("", "y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer by pressing ('Enter', y, yes) or (n, no). Irrespective of Case.")


def _clear_screen():
    """TLDR: clear this console the same way Qmonitor.py does.

    Runs 'cls' on Windows and 'clear' everywhere else.
    """

    subprocess.run("cls" if os.name == "nt" else "clear", check=False, shell=True)