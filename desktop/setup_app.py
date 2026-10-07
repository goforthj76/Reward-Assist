from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tkinter as tk
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
    choices = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Android/Sdk/platform-tools/adb.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Packages/Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe/platform-tools/adb.exe",
    ]
    command = shutil.which("adb")
    if command:
        choices.insert(0, Path(command))
    return next((path for path in choices if path.is_file()), None)


def install_requirement(package_id: str, label: str, status: tk.StringVar, root: tk.Tk) -> None:
    winget = shutil.which("winget")
    if not winget:
        raise RuntimeError(
            f"{label} is missing and Windows Package Manager is unavailable. "
            "Install App Installer from Microsoft Store, then run Reward Assist Setup again."
        )
    status.set(f"Downloading and installing {label}…")
    root.update_idletasks()
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
        self.root.title("Reward Assist Setup")
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
        tk.Label(card, text="Install everything in one step", bg="white", fg="#10213d",
                 font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(card, text="Reward Assist includes its own runtime. Setup also checks the tools used\nfor Android connections before creating your shortcuts.",
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

        tk.Checkbutton(card, text="Install missing Chrome or Android ADB automatically", variable=self.install_missing,
                       bg="white", activebackground="white", fg="#10213d",
                       font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(17, 2))
        tk.Checkbutton(card, text="Create a desktop shortcut", variable=self.desktop, bg="white",
                       activebackground="white", fg="#10213d", font=("Segoe UI", 10)).pack(anchor="w", pady=2)
        tk.Checkbutton(card, text="Open Reward Assist when setup finishes", variable=self.launch, bg="white",
                       activebackground="white", fg="#10213d", font=("Segoe UI", 10)).pack(anchor="w")
        tk.Label(card, textvariable=self.status, bg="white", fg="#587087", font=("Segoe UI", 9)).pack(anchor="w", pady=(14, 4))
        self.install_button = tk.Button(card, text="Install Reward Assist", command=self.install, bg="#07152f",
                                        fg="white", activebackground="#132c53", activeforeground="white",
                                        relief="flat", cursor="hand2", font=("Segoe UI", 11, "bold"), pady=11)
        self.install_button.pack(fill="x")

    def install(self) -> None:
        self.install_button.configure(state="disabled")
        self.status.set("Installing Reward Assist…")
        self.root.update_idletasks()
        try:
            if self.install_missing.get():
                if not find_chrome():
                    install_requirement("Google.Chrome", "Google Chrome", self.status, self.root)
                if not find_adb():
                    install_requirement("Google.PlatformTools", "Android ADB", self.status, self.root)
            elif not find_chrome() or not find_adb():
                proceed = messagebox.askyesno(
                    "Missing requirements",
                    "One or more optional requirements are missing. Continue installing Reward Assist anyway?",
                )
                if not proceed:
                    self.install_button.configure(state="normal")
                    self.status.set("Ready to install")
                    return
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
            if EXTENSION_ROOT.exists():
                shutil.rmtree(EXTENSION_ROOT)
            shutil.copytree(extension_source, EXTENSION_ROOT)
            start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Reward Assist.lnk"
            make_shortcut(start_menu, APP_EXE)
            if self.desktop.get():
                desktop_link = desktop_folder() / "Reward Assist.lnk"
                make_shortcut(desktop_link, APP_EXE)
                if not desktop_link.is_file():
                    raise RuntimeError(f"Windows did not create the desktop shortcut at {desktop_link}.")
            self.status.set("Installation complete")
            messagebox.showinfo(
                "Reward Assist",
                "Reward Assist is installed and ready.\n\n"
                "A desktop shortcut was created. The browser helper and Android tools were checked too."
            )
            if self.launch.get():
                subprocess.Popen([str(APP_EXE)], cwd=str(INSTALL_ROOT))
            self.root.destroy()
        except Exception as exc:
            self.install_button.configure(state="normal")
            self.status.set("Installation could not finish")
            messagebox.showerror("Reward Assist Setup", str(exc))

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    SetupWindow().run()
