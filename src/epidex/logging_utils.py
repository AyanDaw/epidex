from pathlib import Path


class LogWriter:
    """TLDR: writes log/linkbook entries to two fixed per-series files, resolved once at construction.

    Mirrors Downloader/MkvTools: cli.py resolves the series+season paths
    via paths.get_app_data() and constructs this once; QueueManager only
    ever sees the two bound methods (append_to_log, append_to_linkbook).
    """

    def __init__(self, log_file: Path, linkbook: Path):
        """TLDR: store the two resolved file paths this instance writes to."""
        self.log_file = log_file
        self.linkbook = linkbook

    def append_to_log(self, log: str) -> None:
        """TLDR: append one line to self.log_file. Never raises — catches its own I/O errors and prints instead."""
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"{log}\n")
        except FileNotFoundError:
            print("The parent directory doesn't exist.")
        except PermissionError:
            print("No permission to create or modify the file, or the file is protected.")
        except IsADirectoryError:
            print("You gave a directory path instead of a file path.")
        except NotADirectoryError:
            print("Part of the path that should be a directory is actually a file.")
        except UnicodeEncodeError:
            print("The text can't be encoded using the specified encoding (unlikely with UTF-8, but possible with other encodings).")
        except TypeError:
            print("You passed something other than a string to write(), such as an int or dict.")
        except ValueError:
            print("You tried to write to a file that has already been closed, or you used an invalid mode.")
        except OSError:
            print("General operating system errors (disk full, invalid filename, I/O error, hardware problems, etc.).")

    def append_to_linkbook(self, url: str) -> None:
        """TLDR: append one URL line to self.linkbook. Never raises — same error-handling shape as append_to_log."""
        try:
            with open(self.linkbook, "a", encoding="utf-8") as f:
                f.write(f"{url}\n")
        except FileNotFoundError:
            print("The parent directory doesn't exist.")
        except PermissionError:
            print("No permission to create or modify the file, or the file is protected.")
        except IsADirectoryError:
            print("You gave a directory path instead of a file path.")
        except NotADirectoryError:
            print("Part of the path that should be a directory is actually a file.")
        except UnicodeEncodeError:
            print("The text can't be encoded using the specified encoding (unlikely with UTF-8, but possible with other encodings).")
        except TypeError:
            print("You passed something other than a string to write(), such as an int or dict.")
        except ValueError:
            print("You tried to write to a file that has already been closed, or you used an invalid mode.")
        except OSError:
            print("General operating system errors (disk full, invalid filename, I/O error, hardware problems, etc.).")