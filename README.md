# AI Manager

A Mac system manager that runs locally in its own window (macOS only).

- **Memory**: live memory, swap, disk and CPU, with a 30-minute chart and top processes
- **Apps**: list, search and uninstall apps (moved to the Trash, so they can be restored)
- **Storage**: browse, filter and sort files, find and remove duplicates, empty the Trash
- **Homebrew**: list, update-check and uninstall packages
- **Devices**: network, drives (with eject), Bluetooth and USB

## Install

Needs macOS 11+ and Python 3 (Apple's Command Line Tools include it).

```bash
git clone https://github.com/<you>/ai-manager.git
cd ai-manager
bash install.sh --login   # --login is optional: open AI Manager at login
```

Then open **AI Manager** from Spotlight. If macOS blocks the first launch, right-click the app and choose Open.
The first time you delete files or control apps, macOS asks for permission.

## How it works

`manager_server.py` is a small server bound to `127.0.0.1` only. Only the app's own page may call its API
(custom header, Origin check and Host check). Folder actions are limited to your home folder, and core folders
(Desktop, Documents, Downloads, Library and so on) can't be deleted. Deleting moves items to the Trash.

Change the port with `AI_MANAGER_PORT` (default 8767). Server log: `~/Library/Application Support/AI Manager/server.log`.

## Uninstall

```bash
bash uninstall.sh
```
