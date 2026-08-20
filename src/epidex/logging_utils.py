# append_to_log, append_to_linkbook (small enough to merit its own module rather than living in cli.py)

def append_to_log(log: str):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
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

    
def append_to_linkbook(url: str):
    try:
        with open(LINKBOOK, "a", encoding="utf-8") as f:
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
 