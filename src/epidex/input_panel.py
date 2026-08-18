# InputPanel class


class InputPanel:
    """Keeps asking for episode number/URL/description and pushing Episodes into the
    QueueManager's queue, pausing with a message when there isn't enough room."""

    def __init__(self, manager: QueueManager, series: str, season: int, season_metadata: dict, min_free_slots: int = 2):
        self.manager = manager
        self.series = series
        self.season = season
        self.season_metadata = season_metadata
        self.min_free_slots = min_free_slots
        self.resting = False

    def wait_for_space(self, next_episode: int):
        """If fewer than min_free_slots are open, print a rest message and poll until there's room."""
        if self.manager.empty_slots() == 0:
            self.resting = True
        if self.resting:
            while self.manager.empty_slots() < self.min_free_slots:
                
                print(FUNNY_MSG[random.randint(0,len(FUNNY_MSG)-1)])
                print(f"You'll Enter {next_episode} Once the break ends")
                time.sleep(5)
                print("Checking if got any empty slots ")
            self.resting = False   # only clears once we've actually reached min_free_slots

    def run(self, start_epnumber: int):
        """Main input loop: build one Episode per iteration, enqueue it, repeat."""
        epnumber = start_epnumber
        print("(Type 'quit' at the URL prompt to stop adding episodes. Ctrl+C cancels just the current entry.)\n")
        try:
            while True:
                self.wait_for_space(epnumber) # Epnumber is the next episode cause we are stopping it before entering of epnumber
                ep = Episode(series=self.series, season=self.season, epnumber=epnumber)   #TODO: Max ep from tmdb fetch
                
                ep.fetch_metadata(tmdb_cache=self.season_metadata)
                if ep.title is None:
                    print("Metadata returned 'None' as Title. Either skip the episode and manually download the episode later or restart the program after exiting")
                    nter = input("Want to skip? if not then we would exit. [Y/n]:> ")
                    if nter in ["y", "Y", ""]:
                        print(f"Episode number {epnumber} is being skipped, moving to Episode number {epnumber+1}")
                        append_to_log(log= f"{epnumber} SKIPPED\n")
                        epnumber += 1
                        continue
                    else:
                        exit()
                print(f"\nThis Episode is going to be downloaded:v\n{epnumber} : {ep.title}\n")
        
                ep.build_filename()
                try:
                    yt_url = input("YouTube URL (Click Share and copy from there), or 'quit' to stop:> ").strip()
                except KeyboardInterrupt:
                    print("\nCancelled — Episode {} will be asked again.".format(epnumber))
                    continue

                if yt_url.lower() == "quit":
                    break

                if "youtu" not in yt_url.lower():
                    print("That doesn't look like a YouTube link.")
                    confirm = input("Use it anyway? [y/N]:> ").strip().lower()
                    if confirm != "y":
                        continue

                yt_url = re.sub(r"[?&]si=(.*)", "", yt_url)
                ep.youtube_url = yt_url

                try:
                    ep.description = input("Paste the description:> ").strip()
                except KeyboardInterrupt:
                    print("\nCancelled — Episode {} will be asked again.".format(epnumber))
                    continue
                self.manager.enqueue(ep=ep)
                epnumber += 1
        except KeyboardInterrupt:
            print("Interrupted by User")