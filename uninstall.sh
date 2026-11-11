#!/bin/bash
# Removes AI Manager (the app, its server files and its login item). Your own files are untouched.
osascript -e 'tell application "System Events" to delete login item "AI Manager"' >/dev/null 2>&1 || true
pkill -f "AI Manager/manager_server.py" 2>/dev/null || true
rm -rf "$HOME/Applications/AI Manager.app" "$HOME/Library/Application Support/AI Manager"
echo "AI Manager removed."
