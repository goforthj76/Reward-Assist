#!/usr/bin/env bash
# Reward Assist — Automated Linux Box Downloader & Installer
# Works on Ubuntu, Debian, Raspberry Pi OS, Arch Linux, Fedora, and headless Linux servers.
# Usage:
#   curl -sSL https://raw.githubusercontent.com/goforthj76/Reward-Assist/main/install-linux.sh | bash
#   or: bash install-linux.sh

set -e

REPO_URL="https://github.com/goforthj76/Reward-Assist.git"
INSTALL_DIR="${REWARD_ASSIST_DIR:-$HOME/.local/share/reward-assist}"
BIN_DIR="$HOME/.local/bin"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
GOOGLE_PLATFORM_TOOLS_LINUX="https://dl.google.com/android/repository/platform-tools-latest-linux.zip"

# Terminal formatting
BOLD="\033[1m"
GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
RED="\033[0;31m"
RESET="\033[0m"

echo -e "${CYAN}${BOLD}"
echo "  ____                         _      _            _     _   "
echo " |  _ \ _____      ____ _ _ __| |    / \   ___ ___(_)___| |_ "
echo " | |_) / _ \ \ /\ / / _\` | '__| |   / _ \ / __/ __| / __| __|"
echo " |  _ <  __/\ V  V / (_| | |  |_|  / ___ \\__ \__ \ \__ \ |_ "
echo " |_| \_\___| \_/\_/ \__,_|_|  (_) /_/   \_\___/___/_|___/\__|"
echo -e "${RESET}"
echo -e "${BOLD}Reward Assist — Linux Box Setup Station Installer${RESET}"
echo -e "Setting up 24/7 background companion & Android bridge on Linux..."
echo ""

# 1. Platform & OS Checks
OS_NAME="$(uname -s)"
if [ "$OS_NAME" != "Linux" ]; then
    echo -e "${RED}[!] Error: This installer is designed for Linux systems.${RESET}"
    echo "For Windows, download Reward-Assist-Setup.exe from the website."
    exit 1
fi

ARCH="$(uname -m)"
echo -e "${BLUE}[*] Detected architecture:${RESET} $ARCH on $(uname -s)"

# 2. Check for Python 3
if command -v python3 >/dev/null 2>&1; then
    PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    echo -e "${GREEN}[✓] Python 3 found:${RESET} version $PY_VER"
else
    echo -e "${YELLOW}[!] Python 3 is not installed.${RESET}"
    echo "Attempting to install Python 3 via package manager..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update && sudo apt-get install -y python3 python3-pip curl unzip git
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y python3 python3-pip curl unzip git
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -Sy --noconfirm python python-pip curl unzip git
    else
        echo -e "${RED}[!] Could not automatically install Python 3. Please install python3 manually and re-run.${RESET}"
        exit 1
    fi
fi

# 3. Prepare Directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$SYSTEMD_USER_DIR"

# 4. Fetch or Copy Application Files
SCRIPT_DIR=""
if [ -n "${BASH_SOURCE[0]}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/desktop/local_app.py" ]; then
    echo -e "${BLUE}[*] Installing from local directory:${RESET} $SCRIPT_DIR"
    cp -r "$SCRIPT_DIR/desktop/"* "$INSTALL_DIR/"
    [ -f "$SCRIPT_DIR/icon-192.png" ] && cp "$SCRIPT_DIR/icon-192.png" "$INSTALL_DIR/"
else
    echo -e "${BLUE}[*] Downloading latest Reward Assist from GitHub...${RESET}"
    TEMP_CLONE="$(mktemp -d /tmp/reward-assist-clone.XXXXXX)"
    if command -v git >/dev/null 2>&1; then
        git clone --depth 1 "$REPO_URL" "$TEMP_CLONE"
    else
        echo -e "${BLUE}[*] Fetching archive via curl...${RESET}"
        curl -sSL "https://github.com/goforthj76/Reward-Assist/archive/refs/heads/main.tar.gz" | tar -xz -C "$TEMP_CLONE" --strip-components=1
    fi
    cp -r "$TEMP_CLONE/desktop/"* "$INSTALL_DIR/"
    [ -f "$TEMP_CLONE/icon-192.png" ] && cp "$TEMP_CLONE/icon-192.png" "$INSTALL_DIR/"
    rm -rf "$TEMP_CLONE"
fi

# 5. Check / Install Android Debug Bridge (ADB)
echo -e "${BLUE}[*] Checking Android Debug Bridge (ADB)...${RESET}"
ADB_PATH="$(command -v adb || true)"
if [ -n "$ADB_PATH" ]; then
    echo -e "${GREEN}[✓] ADB is available:${RESET} $ADB_PATH"
else
    # Check if previously downloaded
    if [ -x "$INSTALL_DIR/platform-tools/adb" ]; then
        echo -e "${GREEN}[✓] Local ADB standalone found:${RESET} $INSTALL_DIR/platform-tools/adb"
    else
        echo -e "${YELLOW}[*] ADB not found on system. Installing standalone Google Platform Tools for Linux...${RESET}"
        TEMP_ZIP="$(mktemp /tmp/platform-tools.XXXXXX.zip)"
        if curl -sSL "$GOOGLE_PLATFORM_TOOLS_LINUX" -o "$TEMP_ZIP"; then
            unzip -q -o "$TEMP_ZIP" -d "$INSTALL_DIR"
            chmod +x "$INSTALL_DIR/platform-tools/adb"
            rm -f "$TEMP_ZIP"
            echo -e "${GREEN}[✓] Google Android Platform Tools installed to:${RESET} $INSTALL_DIR/platform-tools/adb"
        else
            echo -e "${YELLOW}[!] Warning: Could not download Google Platform Tools. Install 'adb' via package manager: sudo apt install adb${RESET}"
        fi
    fi
fi

# 6. Check for Chrome / Chromium
echo -e "${BLUE}[*] Checking browser support...${RESET}"
CHROME_BIN=""
for b in google-chrome google-chrome-stable chromium-browser chromium; do
    if command -v "$b" >/dev/null 2>&1; then
        CHROME_BIN="$(command -v "$b")"
        break
    fi
done

if [ -n "$CHROME_BIN" ]; then
    echo -e "${GREEN}[✓] Browser found:${RESET} $CHROME_BIN"
else
    echo -e "${YELLOW}[i] Note: Chrome/Chromium not found in PATH.${RESET}"
    echo "    Android tasks (Chick-fil-A, Taco Bell, Dutch Bros) will run directly via ADB."
    echo "    To support web signups (Cheesecake, sweetFrog), install Chrome: sudo apt install chromium-browser"
fi

# 7. Create Executable Launcher
cat << 'EOF' > "$BIN_DIR/reward-assist"
#!/usr/bin/env bash
# Reward Assist Launcher for Linux

INSTALL_DIR="${REWARD_ASSIST_DIR:-$HOME/.local/share/reward-assist}"
export PATH="$INSTALL_DIR/platform-tools:$HOME/.local/bin:$PATH"

case "$1" in
    --headless|-h)
        echo "Starting Reward Assist in 24/7 headless server mode..."
        export HEADLESS=1
        exec python3 "$INSTALL_DIR/local_app.py"
        ;;
    --daemon|-d)
        echo "Starting Reward Assist in background..."
        export HEADLESS=1
        nohup python3 "$INSTALL_DIR/local_app.py" > "$INSTALL_DIR/reward-assist.log" 2>&1 &
        echo "Reward Assist started with PID $! (logs: $INSTALL_DIR/reward-assist.log)"
        ;;
    --status)
        echo "Checking Reward Assist status..."
        if curl -s http://127.0.0.1:8768/api/status >/dev/null 2>&1; then
            echo -e "\033[0;32m[✓] Reward Assist server is active on http://127.0.0.1:8768\033[0m"
            curl -s http://127.0.0.1:8768/api/status | python3 -m json.tool 2>/dev/null || true
        else
            echo -e "\033[0;31m[!] Reward Assist is not currently running.\033[0m"
        fi
        echo ""
        echo "Checking connected Android devices:"
        if command -v adb >/dev/null 2>&1; then
            adb devices -l
        elif [ -x "$INSTALL_DIR/platform-tools/adb" ]; then
            "$INSTALL_DIR/platform-tools/adb" devices -l
        else
            echo "ADB not installed."
        fi
        ;;
    --stop)
        echo "Stopping Reward Assist..."
        pkill -f "local_app.py" || true
        echo "Stopped."
        ;;
    --service)
        echo "Configuring 24/7 systemd user service..."
        systemctl --user enable --now reward-assist.service
        systemctl --user status reward-assist.service --no-pager
        ;;
    *)
        exec python3 "$INSTALL_DIR/local_app.py" "$@"
        ;;
esac
EOF
chmod +x "$BIN_DIR/reward-assist"
echo -e "${GREEN}[✓] Launcher installed to:${RESET} $BIN_DIR/reward-assist"

# 8. Create systemd User Service (24/7 Server Mode)
cat << EOF > "$SYSTEMD_USER_DIR/reward-assist.service"
[Unit]
Description=Reward Assist 24/7 Setup Station & Companion
After=network.target

[Service]
Type=simple
Environment="HEADLESS=1"
Environment="PATH=$INSTALL_DIR/platform-tools:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/env python3 $INSTALL_DIR/local_app.py
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
echo -e "${GREEN}[✓] systemd service created:${RESET} $SYSTEMD_USER_DIR/reward-assist.service"

# 9. Ensure ~/.local/bin is in user PATH
SHELL_RC=""
if [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
elif [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
fi

if [ -n "$SHELL_RC" ]; then
    if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$SHELL_RC" 2>/dev/null; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
    fi
fi

# 10. Summary and Next Steps
echo ""
echo -e "${GREEN}${BOLD}======================================================${RESET}"
echo -e "${GREEN}${BOLD}  Reward Assist Linux Box Setup Complete! 🎉          ${RESET}"
echo -e "${GREEN}${BOLD}======================================================${RESET}"
echo ""
echo -e "${BOLD}How to run Reward Assist:${RESET}"
echo ""
echo -e "  ${CYAN}1. Start interactively:${RESET}"
echo "     reward-assist"
echo ""
echo -e "  ${CYAN}2. Run 24/7 in background (systemd service):${RESET}"
echo "     systemctl --user enable --now reward-assist"
echo "     (Keeps Reward Assist running continuously, even after reboots)"
echo ""
echo -e "  ${CYAN}3. Run in background (nohup daemon):${RESET}"
echo "     reward-assist --daemon"
echo ""
echo -e "  ${CYAN}4. Check status & connected Android phones:${RESET}"
echo "     reward-assist --status"
echo ""
echo -e "  ${CYAN}5. Stop server:${RESET}"
echo "     reward-assist --stop"
echo ""
echo -e "${BOLD}Connecting your Android phone/tablet:${RESET}"
echo "  1. Connect your Android device via USB."
echo "  2. Ensure USB debugging is ON in Developer options."
echo "  3. If prompted on device, check 'Always allow from this computer'."
echo "  4. If permissions are needed for non-root USB: sudo usermod -aG plugdev \$USER"
echo ""
