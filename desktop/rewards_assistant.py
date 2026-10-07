#!/usr/bin/env python3
"""Rewards Assistant: accessible launcher and encrypted profile manager for Android reward apps."""

from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

# The bundled Windows Python runtime does not always advertise its Tcl/Tk
# library locations even though the files are installed beside python.exe.
_runtime_root = Path(sys.executable).resolve().parent
_tcl_root = _runtime_root / "tcl"
if (_tcl_root / "tcl8.6" / "init.tcl").exists():
    os.environ.setdefault("TCL_LIBRARY", str(_tcl_root / "tcl8.6"))
if (_tcl_root / "tk8.6" / "tk.tcl").exists():
    os.environ.setdefault("TK_LIBRARY", str(_tcl_root / "tk8.6"))

import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser


APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "RewardsAssistant"
PROFILE_FILE = APP_DIR / "profiles.dat"
APPS = {
    "Dutch Bros": {
        "package": "com.dutchbros.loyalty",
        "color": "#4db9e8",
        "automation": True,
        "account_url": "https://www.dutchbros.com/",
        "rewards_url": "https://www.dutchbros.com/dutch-rewards/",
        "mode": "Android device",
    },
    "Taco Bell": {
        "package": "com.tacobell.ordering",
        "color": "#9b4dca",
        "automation": False,
        "account_url": "https://www.tacobell.com/rewards",
        "rewards_url": "https://www.tacobell.com/rewards",
        "mode": "Online",
    },
    "Wendy's": {
        "package": "com.wendys.nutritiontool",
        "color": "#e44b45",
        "automation": False,
        "account_url": "https://order.wendys.com/us/en/sign-in?lang=en_US&tab=offers",
        "rewards_url": "https://order.wendys.com/us/en/loyalty?lang=en_US",
        "mode": "Online",
    },
}
FIELDS = ("first_name", "last_name", "phone", "email", "zip_code", "birthday")


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes) -> tuple[DATA_BLOB, object]:
    buffer = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def protect(data: bytes) -> bytes:
    source, keepalive = _blob(data)
    output = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(source), "Rewards Assistant", None, None, None, 0, ctypes.byref(output)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def unprotect(data: bytes) -> bytes:
    source, keepalive = _blob(data)
    output = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 0, ctypes.byref(output)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def find_adb() -> str | None:
    candidates = [
        os.environ.get("ADB", ""),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Android/Sdk/platform-tools/adb.exe"),
        shutil.which("adb") or "",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def run_adb(adb: str, *args: str, capture: bool = False) -> str:
    result = subprocess.run(
        [adb, *args], check=True, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
    )
    return result.stdout if capture else ""


def load_profiles() -> list[dict[str, str]]:
    if not PROFILE_FILE.exists():
        return []
    try:
        payload = base64.b64decode(PROFILE_FILE.read_bytes())
        value = json.loads(unprotect(payload).decode("utf-8"))
        return value if isinstance(value, list) else []
    except Exception:
        messagebox.showwarning("Profile storage", "The encrypted profile file could not be opened.")
        return []


def save_profiles(profiles: list[dict[str, str]]) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(profiles, indent=2).encode("utf-8")
    PROFILE_FILE.write_bytes(base64.b64encode(protect(raw)))


def validate(data: dict[str, str]) -> str | None:
    if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{0,39}", data["first_name"]):
        return "Enter a valid first name."
    if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{0,39}", data["last_name"]):
        return "Enter a valid last name."
    if not re.fullmatch(r"\d{10}", re.sub(r"\D", "", data["phone"])):
        return "Phone must contain 10 digits."
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", data["email"]):
        return "Enter a valid email address."
    if not re.fullmatch(r"\d{5}", data["zip_code"]):
        return "ZIP code must contain 5 digits."
    try:
        birthday = dt.date.fromisoformat(data["birthday"])
    except ValueError:
        return "Birthday must use YYYY-MM-DD."
    if birthday >= dt.date.today():
        return "Birthday must be in the past."
    return None


class RewardsAssistant(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Rewards Assistant")
        self.geometry("980x760")
        self.minsize(820, 680)
        self.configure(bg="#f5f7fb")
        self.selected_app = tk.StringVar(value="Dutch Bros")
        self.status = tk.StringVar(value="Connect an Android device with USB debugging enabled.")
        self.fields = {name: tk.StringVar() for name in FIELDS}
        self.profiles = load_profiles()
        self._style()
        self._build()
        self.after(300, self.check_device)

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TEntry", font=("Segoe UI", 13), padding=9)
        style.configure("TButton", font=("Segoe UI Semibold", 12), padding=11)
        style.configure("Brand.TButton", font=("Segoe UI Semibold", 14), padding=15)

    def _build(self) -> None:
        header = tk.Frame(self, bg="#14213d", padx=30, pady=22)
        header.pack(fill="x")
        tk.Label(header, text="Rewards Assistant", bg="#14213d", fg="white",
                 font=("Segoe UI Semibold", 26)).pack(anchor="w")
        tk.Label(header, text="Simple account setup for your restaurant rewards apps",
                 bg="#14213d", fg="#cbd6ee", font=("Segoe UI", 12)).pack(anchor="w", pady=(4, 0))

        body = tk.Frame(self, bg="#f5f7fb", padx=30, pady=22)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="1. Choose a rewards program", bg="#f5f7fb", fg="#14213d",
                 font=("Segoe UI Semibold", 16)).pack(anchor="w")
        brands = tk.Frame(body, bg="#f5f7fb")
        brands.pack(fill="x", pady=(10, 20))
        symbols = {"Dutch Bros": "DB", "Taco Bell": "TB", "Wendy's": "W"}
        for name, config in APPS.items():
            card = tk.Frame(brands, bg="white", highlightbackground="#dbe2ee", highlightthickness=1)
            card.pack(side="left", fill="x", expand=True, padx=(0, 10))
            tk.Label(card, text=symbols[name], bg=config["color"], fg="white",
                     font=("Segoe UI Black", 18), width=3, height=2).pack(side="left")
            tk.Radiobutton(
                card, text=f"{name}\n{config['mode']}", variable=self.selected_app, value=name,
                indicatoron=False, bg="white", activebackground=config["color"],
                selectcolor=config["color"], fg="#14213d", font=("Segoe UI Semibold", 13),
                padx=12, pady=10, relief="flat", bd=0, justify="left",
            ).pack(side="left", fill="both", expand=True)

        form_card = tk.Frame(body, bg="white", padx=22, pady=18, highlightbackground="#dbe2ee", highlightthickness=1)
        form_card.pack(fill="x")
        tk.Label(form_card, text="2. Account holder details", bg="white", fg="#14213d",
                 font=("Segoe UI Semibold", 16)).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 12))
        labels = {
            "first_name": "First name", "last_name": "Last name", "phone": "Phone",
            "email": "Email", "zip_code": "ZIP code", "birthday": "Birthday (YYYY-MM-DD)",
        }
        for i, name in enumerate(FIELDS):
            row, col = 1 + i // 2, (i % 2) * 2
            tk.Label(form_card, text=labels[name], bg="white", fg="#34425c",
                     font=("Segoe UI", 11)).grid(row=row, column=col, sticky="w", padx=(0, 8), pady=8)
            ttk.Entry(form_card, textvariable=self.fields[name], width=26).grid(
                row=row, column=col + 1, sticky="ew", padx=(0, 22), pady=8
            )
        form_card.columnconfigure(1, weight=1)
        form_card.columnconfigure(3, weight=1)

        actions = tk.Frame(body, bg="#f5f7fb")
        actions.pack(fill="x", pady=18)
        ttk.Button(actions, text="Save encrypted profile", command=self.save_profile).pack(side="left")
        ttk.Button(actions, text="Check USB device", command=self.check_device).pack(side="left", padx=10)
        ttk.Button(actions, text="Open selected service", command=self.open_service).pack(side="left")
        ttk.Button(actions, text="Start guided setup", command=self.start_setup).pack(side="right")

        tk.Label(body, textvariable=self.status, bg="#eef3fb", fg="#203557",
                 font=("Segoe UI", 11), padx=15, pady=12, anchor="w", wraplength=780,
                 justify="left").pack(fill="x")
        tk.Label(body, text="Verification codes are entered by the account holder and are never saved.",
                 bg="#f5f7fb", fg="#63708a", font=("Segoe UI", 10)).pack(anchor="w", pady=(12, 0))

        manage = tk.Frame(body, bg="white", padx=18, pady=14, highlightbackground="#dbe2ee", highlightthickness=1)
        manage.pack(fill="both", expand=True, pady=(16, 0))
        tk.Label(manage, text="Rewards manager", bg="white", fg="#14213d",
                 font=("Segoe UI Semibold", 15)).pack(anchor="w")
        tk.Label(manage, text="Open rewards, offers, QR access, or Gmail without storing passwords.",
                 bg="white", fg="#63708a", font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 10))
        shortcuts = tk.Frame(manage, bg="white")
        shortcuts.pack(fill="x")
        ttk.Button(shortcuts, text="Open rewards / QR", command=self.open_rewards).pack(side="left")
        ttk.Button(shortcuts, text="Open Gmail for code", command=lambda: webbrowser.open("https://mail.google.com/")) .pack(side="left", padx=10)
        ttk.Button(shortcuts, text="Open saved profiles folder", command=self.open_profiles_folder).pack(side="left")

    def values(self) -> dict[str, str]:
        data = {name: value.get().strip() for name, value in self.fields.items()}
        data["phone"] = re.sub(r"\D", "", data["phone"])
        return data

    def save_profile(self) -> None:
        data = self.values()
        error = validate(data)
        if error:
            messagebox.showerror("Check details", error)
            return
        record = {**data, "app": self.selected_app.get(), "saved_at": dt.datetime.now().isoformat(timespec="seconds")}
        self.profiles.append(record)
        save_profiles(self.profiles)
        self.status.set(f"Encrypted profile saved on this Windows account ({len(self.profiles)} total).")

    def adb_ready(self) -> str | None:
        adb = find_adb()
        if not adb:
            self.status.set("ADB was not found. Install Android Platform Tools or set the ADB environment variable.")
            return None
        try:
            devices = [line for line in run_adb(adb, "devices", capture=True).splitlines()[1:] if line.endswith("\tdevice")]
        except subprocess.CalledProcessError:
            self.status.set("ADB could not start. Reconnect the USB cable and try again.")
            return None
        if len(devices) != 1:
            self.status.set(f"Expected one authorized Android device; found {len(devices)}.")
            return None
        return adb

    def check_device(self) -> None:
        adb = self.adb_ready()
        if adb:
            self.status.set("Android device connected and authorized.")

    def open_service(self) -> None:
        app = self.selected_app.get()
        if app != "Dutch Bros":
            webbrowser.open(APPS[app]["account_url"])
            self.status.set(f"Opened the official {app} account page in your browser.")
            return
        adb = self.adb_ready()
        if not adb:
            return
        app = self.selected_app.get()
        package = APPS[app]["package"]
        installed = package in run_adb(adb, "shell", "pm", "list", "packages", package, capture=True)
        try:
            if installed:
                run_adb(adb, "shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")
                self.status.set(f"Opened {app} on the connected device.")
            else:
                uri = f"market://details?id={package}"
                run_adb(adb, "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", uri, "-p", "com.android.vending")
                self.status.set(f"Opened the official {app} Google Play listing. Complete installation on the device.")
        except subprocess.CalledProcessError:
            self.status.set(f"Could not open {app}. Check the device screen and USB connection.")

    def open_rewards(self) -> None:
        app = self.selected_app.get()
        if app == "Dutch Bros":
            adb = self.adb_ready()
            if not adb:
                return
            self.open_service()
            self.status.set("Dutch Bros opened on Android. Tap Scan to display the rewards QR code.")
            return
        webbrowser.open(APPS[app]["rewards_url"])
        self.status.set(f"Opened the official {app} rewards page.")

    def open_profiles_folder(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(APP_DIR)

    def start_setup(self) -> None:
        data = self.values()
        error = validate(data)
        if error:
            messagebox.showerror("Check details", error)
            return
        app = self.selected_app.get()
        if app != "Dutch Bros":
            webbrowser.open(APPS[app]["account_url"])
            messagebox.showinfo(
                f"{app} guided setup",
                f"The official {app} signup page is open in your browser. Use the account holder's details, "
                "then enter the verification code they receive. The code is not saved by Rewards Assistant.",
            )
            return
        APP_DIR.mkdir(parents=True, exist_ok=True)
        details_path = APP_DIR / "current_details.txt"
        details_path.write_text("\n".join(f"{key}: {data[key]}" for key in FIELDS) + "\nEND\n", encoding="utf-8")
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        if getattr(sys, "frozen", False):
            helper = Path(sys.executable).resolve().with_name("Dutch Bros Setup.exe")
            if not helper.exists():
                messagebox.showerror("Dutch Bros setup", f"Helper not found:\n{helper}")
                return
            command = [str(helper), "--details-file", str(details_path)]
        else:
            script = Path(__file__).resolve().parent.parent / "dutch_bros_signup_assistant.py"
            if not script.exists():
                messagebox.showerror("Dutch Bros setup", f"Automation script not found:\n{script}")
                return
            command = [sys.executable, str(script), "--details-file", str(details_path)]
        subprocess.Popen(command, creationflags=flags)
        self.status.set("Dutch Bros guided setup started in a separate window.")


if __name__ == "__main__":
    RewardsAssistant().mainloop()
