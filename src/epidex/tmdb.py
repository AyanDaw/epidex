# load_metadata_tmdb and TMDB API interaction

def load_metadata_tmdb(series_id: str, season:int) -> dict:
    """
    Return {episode_number: title} for the whole season.
    Check cache first; on miss , call TMDB once, cache result, return it.
    """

    TMDB_LINK = f"https://api.themoviedb.org/3/{TYPE}/{series_id}/season/{season}?api_key={TMDB_API}"

    data = {}

    # Check the file existence
    cache_file = Path("metadata.json")
    if cache_file.exists():
        last_cache_date = datetime.fromtimestamp(cache_file.stat().st_mtime)
        fetch_succeeded = False
        while True:
            print(f"\n\nThere exists a previous cached matadata.\nLast fetched time:\t{last_cache_date.strftime("%Y-%m-%d %H:%M:%S")}")
            nter = input("\n\nDo you want to use that?\nif no then fresh metadata will be fetched. [Y/n]:> ")

            if nter in ["y", "Y", ""]:
                try:
                    with open(cache_file, "r") as file:
                        data = json.load(file)
                        if data: 
                            print("The file has been read successfully!")  # In the file we will contain only json part not the whole response. its already in json
                            break
                except json.JSONDecodeError:
                    print("The file exists but contains invalid JSON (corrupted or manually edited incorrectly)")
                    continue
                except PermissionError:
                    print("You dont have permission to read it.")
                    continue
                except OSError:
                    print("Other Filesystem-related errors (disk issues, invalid path, etc.).")
                    continue
            else:
                while True:
                    try:
                        response = requests.get(TMDB_LINK, timeout=20)
                        response.raise_for_status()
                    
                    except requests.exceptions.Timeout:
                        print("Request time out!")
                        nter = input("Want to retry?[Y/n]:> ")
                        if nter in ["y", "Y", ""]:
                            continue
                        else:
                            break
                    except requests.exceptions.ConnectionError:
                        print("Could not connect to TMDB")
                        nter = input("Want to retry? [Y/n]:> ")
                        if nter in ["y", "Y", ""]:
                            continue
                        else:
                            break
                    except requests.exceptions.HTTPError:
                        code = response.status_code
                        if code == 401:
                            print("Bad API Key\nRestart the program after correcting the API Key\nExiting...")
                            exit()
                        elif code == 404:
                            print("Series Not found!\nRestart the program after correcting the API Key\nExiting...")
                            exit()
                        else:
                            print(f"Unexpected Error: {code}")
                        nter = input("Want to retry? [Y/n]:> ")
                        if nter in ["y", "Y", ""]:
                            continue
                        else:
                            break

                    data = response.json()
                    if data:
                        try:
                            cache_file_backup = Path("metadatacopy.json")
                            shutil.copy2(cache_file, cache_file_backup) # (src,dest)
                            with open(cache_file, "w") as file:
                                json.dump(data, file, indent=4) # writing the json format in the json file
                                print("\n\nMetadata Successfully fetched and written in the file!")
                            fetch_succeeded = True
                            cache_file_backup.unlink()
                            break
                        except TypeError:
                            print("Your dictionary contains an object that JSON can't serialize (e.g. Path, set, custom class).")
                            cache_file.unlink()
                            cache_file_backup.rename("metadata.json")
                            break
                        except PermissionError:
                            print("Cannot write to the file or directory.")
                            cache_file.unlink()
                            cache_file_backup.rename("metadata.json")
                            break
                        except OSError:
                            print("Other Filesystem-related errors (disk issues, invalid path, etc.).")
                            cache_file.unlink()
                            cache_file_backup.rename("metadata.json")
                            break
                    else: # This case is unsuccessfull metadata fetch, three options either retry or reuse old data or exit.
                        print("\n\nBecause of some unexpected problems we couldn't fetch your fresh metadata.")
                        nter = input("Want to retry?[Y/n]:> ")
                        if nter in ["y", "Y", ""]:
                            continue
                        else:
                            nter = input("Want to exit? if not we will send you to use old data asking page. [Y/n]:> ")
                            if nter in ["y", "Y",""]:
                                exit()
                            else:
                                break # exits from inner loop
            if fetch_succeeded:
                break # leave outer loop too — data is good, go use it
            else:                
                continue # go back to outer loop's top — re-ask about cached data
            # Now WE have the metadata if file EXISTS
    else:
        while True:
            try:
                print("Wait Fetching tmdb\n")
                response = requests.get(TMDB_LINK, timeout=20)
                response.raise_for_status()

            except requests.exceptions.Timeout:
                print("Request time out!")
                nter = input("Want to retry? if not then we would exit. [Y/n]:> ")
                if nter in ["y", "Y", ""]:
                    continue
                else:
                    exit()

            except requests.exceptions.ConnectionError:
                print("Could not connect to TMDB")
                nter = input("Want to retry? if not then we would exit. [Y/n]:> ")
                if nter in ["y", "Y", ""]:
                    continue
                else:
                    exit()
            
            except requests.exceptions.HTTPError:
                code = response.status_code
                if code == 401:
                    reason = "Bad API Key"
                elif code == 404:
                    reason = "Series Not found!"
                else:
                    reason = code
                print(f"Unexpected Error: {reason}")
                nter = input("Want to retry? if not then we would exit. [Y/n]:> ")
                if nter in ["y", "Y", ""]:
                    continue
                else:
                    exit()

            data = response.json()
            if data:
                try:
                    with open(cache_file, "w") as file:
                        json.dump(data, file, indent=4) # writing the json format in file
                        print("\n\nMetadata Successfully fetched and written in the file!")
                        break
                except TypeError:
                    print("Your dictionary contains an object that JSON can't serialize (e.g. Path, set, custom class).")
                    nter = input("Want to retry? if not then we would exit. [Y/n]:> ")
                    if nter in ["y", "Y", ""]:
                        continue
                    else:
                        exit()
                except PermissionError:
                    print("Cannot write to the file or directory.")
                    nter = input("Want to retry? if not then we would exit. [Y/n]:> ")
                    if nter in ["y", "Y", ""]:
                        continue
                    else:
                        exit()
                except OSError:
                    print("Other Filesystem-related errors (disk issues, invalid path, etc.).")
                    nter = input("Want to retry? if not then we would exit. [Y/n]:> ")
                    if nter in ["y", "Y", ""]:
                        continue
                    else:
                        exit()
            else:
                print("\n\nBecause of some unexpected problems we couldn't fetch your fresh metadata.")
                nter = input("Want to retry? if not then we would exit. [Y/n]:> ")
                if nter in ["y", "Y", ""]:
                    continue
                else:
                    exit()

    # After All of this we will either have the data in hand or we will exit the program
    metadata = {}
    for ep in data["episodes"]:
        metadata[ep["episode_number"]] = ep["name"]   # {Episode Number: Title}
    # We have the meta data dictionary now
    return metadata