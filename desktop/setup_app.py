from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tkinter as tk
import threading
import queue
import logging
import webbrowser
import zipfile
from setup_downloads import install_adb, ensure_winget
from setup_checks import locate_adb, inspect_android
from pathlib import Path
from tkinter import messagebox


APP_NAME = "Reward Assist"
INSTALL_ROOT = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / APP_NAME
APP_EXE = INSTALL_ROOT / "Reward Assist.exe"
EXTENSION_ROOT = INSTALL_ROOT / "browser-helper"


def bundled(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / name


def find_chrome() -> Path | None:
    choices = [
        Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    return next((path for path in choices if path.is_file()), None)


def find_adb() -> Path | None:
    return locate_adb()


def install_requirement(package_id: str, label: str, status: tk.StringVar, root: tk.Tk) -> None:
    if package_id == "Google.PlatformTools":
        install_adb(status.set)
        return
    winget = ensure_winget(status.set)
    status.set(f"Downloading and installing {label}…")
    result = subprocess.run(
        [winget, "install", "--id", package_id, "--exact", "--silent",
         "--accept-package-agreements", "--accept-source-agreements"],
        capture_output=True, text=True, timeout=600,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode not in (0, -1978335189):
        detail = (result.stderr or result.stdout or "Unknown installation error").strip()
        raise RuntimeError(f"Windows could not install {label}. {detail[-500:]}")


def make_shortcut(shortcut: Path, target: Path) -> None:
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    safe_shortcut = str(shortcut).replace("'", "''")
    safe_target = str(target).replace("'", "''")
    script = (
        "$w=New-Object -ComObject WScript.Shell;"
        f"$s=$w.CreateShortcut('{safe_shortcut}');"
        f"$s.TargetPath='{safe_target}';"
        f"$s.WorkingDirectory='{str(target.parent).replace("'", "''")}';"
        "$s.Description='Reward Assist';$s.Save()"
    )
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], check=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)


def desktop_folder() -> Path:
    """Resolve the real Windows Desktop, including OneDrive redirection."""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
         "[Environment]::GetFolderPath('Desktop')"],
        capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    resolved = Path(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else None
    candidates = [resolved]
    if os.environ.get("OneDrive"):
        candidates.append(Path(os.environ["OneDrive"]) / "Desktop")
    candidates.append(Path.home() / "Desktop")
    return next((path for path in candidates if path and path.exists()), Path.home() / "Desktop")


class SetupWindow:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.report_callback_exception = self.report_error
        self.root.title("Reward Assist Setup — v0.5.31")
        width = min(720, self.root.winfo_screenwidth() - 40)
        height = min(720, self.root.winfo_screenheight() - 80)
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, (self.root.winfo_screenheight() - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(min(620, width), min(600, height))
        self.root.resizable(True, True)
        self.root.configure(bg="#07152f")
        self.desktop = tk.BooleanVar(value=True)
        self.launch = tk.BooleanVar(value=True)
        self.install_missing = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Ready to install")
        self._build()

    def _build(self) -> None:
        header = tk.Frame(self.root, bg="#07152f", padx=30, pady=20)
        header.pack(fill="x")
        tk.Label(header, text="R", bg="#39c6ed", fg="#07152f", font=("Segoe UI", 22, "bold"),
                 width=2, height=1).pack(side="left")
        title = tk.Frame(header, bg="#07152f")
        title.pack(side="left", padx=15)
        tk.Label(title, text="Reward Assist", bg="#07152f", fg="white",
                 font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(title, text="Windows setup", bg="#07152f", fg="#a9bdd5",
                 font=("Segoe UI", 11)).pack(anchor="w")

        card = tk.Frame(self.root, bg="white", padx=30, pady=22)
        card.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        tk.Label(card, text="Let’s get you ready", bg="white", fg="#10213d",
                 font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(card, text="Click Install below. We’ll download missing tools and include the Chrome helper.\nThen we’ll guide you through Chrome and your Android connection.",
                 bg="white", fg="#5f6d83", justify="left", font=("Segoe UI", 10)).pack(anchor="w", pady=(7, 18))

        chrome = "Found" if find_chrome() else "Missing — setup can install it"
        adb = "Found" if find_adb() else "Missing — setup can install it"
        helper = "Included — installed with Reward Assist"
        desktop_app = "Included — desktop shortcut will be created"
        for label, value in (("Reward Assist desktop app", desktop_app), ("Browser automation helper", helper),
                             ("Google Chrome", chrome), ("Android ADB", adb)):
            row = tk.Frame(card, bg="#f1f6fa", padx=14, pady=10)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=label, bg="#f1f6fa", fg="#10213d", font=("Segoe UI", 10, "bold")).pack(side="left")
            tk.Label(row, text=value, bg="#f1f6fa", fg="#26738b", font=("Segoe UI", 9)).pack(side="right")

        tk.Checkbutton(card, text="Download and install missing Chrome / Android tools automatically", variable=self.install_missing,
                       bg="white", activebackground="white", fg="#10213d",
                       font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(17, 2))
        tk.Button(card, text="Android tools license and download terms", relief="flat", command=lambda: webbrowser.open("https://developer.android.com/tools/releases/platform-tools")).pack(anchor="w")
        tk.Label(card, text="Installing missing tools accepts their installation agreements. Internet required.", bg="white", fg="#5f6d83", wraplength=540).pack(anchor="w")
        tk.Checkbutton(card, text="Create a desktop shortcut", variable=self.desktop, bg="white",
                       activebackground="white", fg="#10213d", font=("Segoe UI", 10)).pack(anchor="w", pady=2)
        tk.Checkbutton(card, text="Open Reward Assist after the setup guide", variable=self.launch, bg="white",
                       activebackground="white", fg="#10213d", font=("Segoe UI", 10)).pack(anchor="w")
        tk.Label(card, textvariable=self.status, bg="white", fg="#587087", font=("Segoe UI", 9)).pack(anchor="w", pady=(14, 4))
        self.install_button = tk.Button(card, text="Install Reward Assist", command=self.install, bg="#07152f",
                                        fg="white", activebackground="#132c53", activeforeground="white",
                                        relief="flat", cursor="hand2", font=("Segoe UI", 11, "bold"), pady=11)
        self.install_button.pack(fill="x")

    def report_error(self, kind, value, tb):
        logging.error("Setup callback failed", exc_info=(kind, value, tb))
        messagebox.showerror("Reward Assist Setup", str(value) + "\n\nDiagnostics: " + str(LOG_PATH))

    def install(self) -> None:
        if not self.install_missing.get():
            self.finish_install()
            return
        self.install_button.configure(state="disabled")
        events = queue.Queue()
        class Status:
            def set(self, message):
                events.put(("status", message))
        def worker():
            try:
                if not find_adb():
                    install_requirement("Google.PlatformTools", "Android ADB", Status(), None)
                if not find_chrome():
                    install_requirement("Google.Chrome", "Google Chrome", Status(), None)
                events.put(("done", ""))
            except Exception as exc:
                logging.exception("Prerequisite installation failed")
                events.put(("error", str(exc)))
        def poll():
            try:
                while True:
                    kind, message = events.get_nowait()
                    if kind == "status":
                        self.status.set(message)
                    elif kind == "done":
                        self.finish_install()
                        return
                    else:
                        self.install_button.configure(state="normal")
                        self.status.set("Installation paused. Fix the issue and retry.")
                        messagebox.showerror("Setup needs attention", message + "\n\nDiagnostics: " + str(LOG_PATH))
                        return
            except queue.Empty:
                self.root.after(100, poll)
        threading.Thread(target=worker, daemon=True).start()
        self.root.after(100, poll)

    def finish_install(self) -> None:
        self.install_button.configure(state="disabled")
        self.status.set("Installing Reward Assist…")
        self.root.update_idletasks()
        try:
            if not self.install_missing.get() and (not find_chrome() or not find_adb()):
                proceed = messagebox.askyesno(
                    "Missing requirements",
                    "One or more optional requirements are missing. Continue installing Reward Assist anyway?",
                )
                if not proceed:
                    self.install_button.configure(state="normal")
                    self.status.set("Ready to install")
                    return
            if self.install_missing.get() and (not find_chrome() or not find_adb()):
                raise RuntimeError("Chrome or ADB could not be found after installation. Restart Windows, then run setup again.")
            self.status.set("Installing Reward Assist…")
            self.root.update_idletasks()
            source = bundled("Rewards Assistant.exe")
            if not source.is_file():
                raise FileNotFoundError("The packaged Reward Assist application is missing.")
            INSTALL_ROOT.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, APP_EXE)
            extension_source = bundled("chrome_extension")
            if not extension_source.is_dir() or not (extension_source / "manifest.json").is_file():
                raise FileNotFoundError("The packaged browser automation helper is missing.")
            shutil.copytree(extension_source, EXTENSION_ROOT, dirs_exist_ok=True)
            for original in extension_source.rglob("*"):
                if original.is_file() and original.read_bytes() != (EXTENSION_ROOT / original.relative_to(extension_source)).read_bytes():
                    raise RuntimeError("Extension files could not be verified after installation.")
            with zipfile.ZipFile(INSTALL_ROOT / "Reward-Assist-Chrome-Extension.zip", "w", zipfile.ZIP_DEFLATED) as archive:
                for file in EXTENSION_ROOT.rglob("*"):
                    if file.is_file():
                        archive.write(file, "browser-helper/" + file.relative_to(EXTENSION_ROOT).as_posix())
            make_shortcut(INSTALL_ROOT / "Chrome Extension Folder.lnk", EXTENSION_ROOT)
            start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Reward Assist.lnk"
            make_shortcut(start_menu, APP_EXE)
            if self.desktop.get():
                desktop_link = desktop_folder() / "Reward Assist.lnk"
                make_shortcut(desktop_link, APP_EXE)
                if not desktop_link.is_file():
                    raise RuntimeError(f"Windows did not create the desktop shortcut at {desktop_link}.")
            (INSTALL_ROOT / "SETUP-GUIDE.txt").write_text(
                "Reward Assist setup\n\nChrome extension\nOpen chrome://extensions in Chrome. Enable Developer mode, click Load unpacked, and select:\n"
                + str(EXTENSION_ROOT)
                + "\nConfirm Rewards Assistant Helper is enabled. If it is already listed, click its Reload button.\n\nAndroid\nInstall the official restaurant apps you plan to use from Google Play. Enable Developer options by tapping Build number seven times in Settings > About phone (the location varies by device). Enable USB debugging in Developer options. Connect a data-capable USB cable, unlock the device and allow the USB debugging prompt.\n\nKeep the device unlocked while using Reward Assist. If Windows cannot see it, install the USB driver provided by the device manufacturer.\n",
                encoding="utf-8")
            self.show_setup_guide()
        except Exception as exc:
            logging.exception("Application installation failed")
            self.install_button.configure(state="normal")
            self.status.set("Installation could not finish")
            messagebox.showerror("Reward Assist Setup", str(exc))

    def show_setup_guide(self) -> None:
        for child in self.root.winfo_children():
            child.destroy()
        self.root.title("Reward Assist — Finish setup")
        self.guide_step = 0
        self.guide_frame = tk.Frame(self.root, bg="white", padx=24, pady=20)
        self.guide_frame.pack(fill="both", expand=True)
        self.draw_guide()

    def guide_text(self, text, bold=False):
        tk.Label(self.guide_frame, text=text, bg="white", fg="#10213d", justify="left",
                 wraplength=550, font=("Segoe UI", 11, "bold" if bold else "normal")).pack(anchor="w", pady=8)

    def open_extensions(self):
        chrome = find_chrome()
        if not chrome:
            messagebox.showerror("Chrome missing", "Install Google Chrome, then open chrome://extensions.")
            return
        subprocess.Popen([str(chrome), "chrome://extensions/"])

    def open_extension_folder(self):
        if not (EXTENSION_ROOT / "manifest.json").is_file():
            raise RuntimeError("The installed extension folder is missing. Rerun setup; check security history if files disappeared.")
        os.startfile(EXTENSION_ROOT)

    def copy_extension_path(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(str(EXTENSION_ROOT))
        self.root.update_idletasks()
        if self.root.clipboard_get() != str(EXTENSION_ROOT):
            raise RuntimeError("Clipboard copy failed. Select and copy the folder path shown below instead.")
        self.guide_status.set("Folder path copied. Paste it into Chrome’s Load unpacked folder picker.")

    def check_android(self):
        self.check_button.configure(state="disabled")
        self.guide_status.set("Checking USB connection and restaurant apps…")
        def worker():
            try:
                adb = find_adb()
                message = inspect_android(adb) if adb else "ADB is missing. Run setup again with automatic installation enabled."
            except Exception as exc:
                message = str(exc)
            def done():
                if self.guide_step == 1:
                    self.guide_status.set(message)
                    self.check_button.configure(state="normal")
            self.root.after(0, done)
        threading.Thread(target=worker, daemon=True).start()

    def guide_next(self):
        self.guide_step += 1
        self.draw_guide()

    def draw_guide(self):
        for child in self.guide_frame.winfo_children():
            child.destroy()
        self.guide_status = tk.StringVar()
        self.guide_text(f"Finish setup — step {self.guide_step + 1} of 3", True)
        if self.guide_step == 0:
            self.guide_text("1. Enable the included Chrome extension", True)
            self.guide_text("Needed for website signup. The extension files are installed, but Chrome requires you to enable them once.")
            self.guide_text("Open Extensions → turn on Developer mode → Load unpacked → select the folder below. If Rewards Assistant Helper is already listed, click Reload and make sure it is enabled.")
            path_field = tk.Entry(self.guide_frame, readonlybackground="#f1f6fa", width=72)
            path_value = tk.StringVar(value=str(EXTENSION_ROOT))
            path_field.configure(textvariable=path_value, state="readonly")
            path_field.path_value = path_value
            path_field.pack(fill="x", pady=8)
            tk.Button(self.guide_frame, text="Open installed extension folder", command=self.open_extension_folder).pack(anchor="w", pady=4)
            tk.Button(self.guide_frame, text="Open Chrome Extensions", command=self.open_extensions).pack(anchor="w", pady=4)
            tk.Button(self.guide_frame, text="Copy extension folder path", command=self.copy_extension_path).pack(anchor="w", pady=4)
            self.guide_text("Chrome: " + ("installed" if find_chrome() else "missing") + "   •   ADB: " + ("installed" if find_adb() else "missing"))
        elif self.guide_step == 1:
            self.guide_text("2. Connect your Android device", True)
            self.guide_text("In Android Settings → About phone, tap Build number seven times (its location varies). Then open Developer options and enable USB debugging.")
            self.guide_text("Connect a data-capable USB cable. Unlock the device and tap Allow on its USB debugging prompt. Keep it unlocked while the assistant runs.")
            self.guide_text("Install the official Taco Bell, Dutch Bros, or Paris Baguette app from Google Play—only the programs you plan to use.")
            self.check_button = tk.Button(self.guide_frame, text="Check device and installed apps", command=self.check_android)
            self.check_button.pack(anchor="w", pady=8)
        else:
            self.guide_text("3. Ready to open Reward Assist", True)
            self.guide_text("Before starting signup, make sure the Chrome helper is enabled and your Android device is connected and authorized. Checks do not automatically verify that the extension is enabled.")
            self.guide_text("You can finish configuration later. Instructions are saved beside the installed app as SETUP-GUIDE.txt. Android permissions and restaurant app installation must be completed on your device.")
            tk.Button(self.guide_frame, text="Open saved setup instructions", command=lambda: os.startfile(INSTALL_ROOT / "SETUP-GUIDE.txt")).pack(anchor="w", pady=8)
            tk.Button(self.guide_frame, text="Open Reward Assist" if self.launch.get() else "Finish setup", command=self.finish_setup, bg="#07152f", fg="white", padx=20, pady=12).pack(anchor="w", pady=12)
        tk.Label(self.guide_frame, textvariable=self.guide_status, wraplength=550, justify="left", bg="white", fg="#26738b").pack(anchor="w", pady=8)
        if self.guide_step < 2:
            tk.Button(self.guide_frame, text="Next", command=self.guide_next, padx=24, pady=10).pack(side="bottom", anchor="e")

    def finish_setup(self):
        if self.launch.get():
            subprocess.Popen([str(APP_EXE)], cwd=str(INSTALL_ROOT))
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


LOG_PATH = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "RewardAssist-Setup" / "setup.log"

if __name__ == "__main__":
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        logging.info("Setup started; installation target: %s", INSTALL_ROOT)
        SetupWindow().run()
    except Exception:
        logging.exception("Setup startup failed")
        messagebox.showerror("Reward Assist Setup", "Setup could not start. See diagnostics at " + str(LOG_PATH))
