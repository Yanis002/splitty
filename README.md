# Splitty

Simple web browser for LiveSplit One with an embedded video player for speedrunners.

### LiveSplit

This is just a browser showing https://one.livesplit.org, browser data should be stored wherever you execute the script from.

### Video Player

Very simple video player with multiple features
- listens for global hotkeys (corresponding to livesplit's hotkeys)
- starts and resets the video playback
- starting offset (in milliseconds)
- settings autoload at program start

It can be accessed either from the browser (by pressing Ctrl+P) or as a standalone program by launching `src/player.py` directly.

## Installation

Install the requirements with `pip install -r requirements.txt` then run `python src/main.py` (or `python src/player.py` if you only want the video player).

Autobuilds for both will come in the future.

## License

Licensed under GPL3.
