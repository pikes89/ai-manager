#!/bin/bash
# Installs AI Manager on this Mac:  bash install.sh [--login]
#   --login   also open AI Manager automatically at login
set -e
[ "$(uname)" = "Darwin" ] || { echo "AI Manager only runs on macOS."; exit 1; }
cd "$(dirname "$0")"
SRC="$(pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is missing. A window will open to install Apple's Command Line Tools."
  echo "Finish that install, then run this installer again."
  xcode-select --install || true
  exit 1
fi

DEST="$HOME/Library/Application Support/AI Manager"
APP="$HOME/Applications/AI Manager.app"
mkdir -p "$DEST" "$HOME/Applications"
rm -rf "$DEST/web"
cp -R "$SRC/web" "$SRC/manager_server.py" "$SRC/mac_manager.py" "$DEST/"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$SRC/assets/AIManager.icns" "$APP/Contents/Resources/AIManager.icns"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>AI Manager</string>
<key>CFBundleDisplayName</key><string>AI Manager</string>
<key>CFBundleIdentifier</key><string>local.aimanager.app</string>
<key>CFBundleExecutable</key><string>AIManager</string>
<key>CFBundleIconFile</key><string>AIManager</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleVersion</key><string>1.0</string>
<key>CFBundleShortVersionString</key><string>1.0</string>
<key>LSMinimumSystemVersion</key><string>11.0</string>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
cat > "$APP/Contents/MacOS/AIManager" <<'LAUNCH'
#!/bin/bash
# Starts the local AI Manager server if needed, then opens its SYSTEM panel.
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
DIR="$HOME/Library/Application Support/AI Manager"
PORT="${AI_MANAGER_PORT:-8767}"
URL="http://127.0.0.1:${PORT}/"
cd "$DIR" || exit 1
if ! curl -s -o /dev/null "$URL"; then
  AI_MANAGER_PORT="$PORT" nohup python3 manager_server.py >"$DIR/server.log" 2>&1 &
  for _ in $(seq 1 40); do curl -s -o /dev/null "$URL" && break; sleep 0.25; done
fi
if [ -d "/Applications/Google Chrome.app" ]; then
  exec open -na "Google Chrome" --args --app="$URL" --window-size=1100,800
else
  exec open "$URL"
fi
LAUNCH
chmod +x "$APP/Contents/MacOS/AIManager"
codesign --force -s - "$APP" >/dev/null 2>&1 || true
echo "Installed: $APP"

if [ "$1" = "--login" ]; then
  osascript -e "tell application \"System Events\" to make login item at end with properties {path:\"$APP\", hidden:false, name:\"AI Manager\"}" >/dev/null \
    && echo "Added to Login Items."
fi
echo "Open it from Spotlight (AI Manager) or:  open \"$APP\""
echo "First launch: if macOS blocks it, right-click the app and choose Open."
