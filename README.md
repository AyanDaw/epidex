<!-- for the internal subprocess-pip auto-installer to read from, and for anyone building from source manually -->


"Project isnt completed yet"

on some OS/browser combos, the browser has to be closed for yt-dlp to read its cookie DB (locked file), and Linux sometimes needs extra keyring packages to decrypt it. That's a runtime failure mode for Downloader.download() to surface clearly, not something check_dependencies() can catch upfront.

Currently only Firefox (or its forks) is supported for cookie extraction; edit downloader.py directly if you use another browser.
(browser must be closed while downloading, Linux keyring dependency for decrypting cookies) — practical warnings for whoever hits a cryptic yt-dlp cookie error.