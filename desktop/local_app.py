#!/usr/bin/env python3
"""Local Rewards Assistant web UI and Windows/ADB bridge."""

from __future__ import annotations

from android_verification import verify_android_code
from setup_checks import locate_adb

import base64
import ctypes
from ctypes import wintypes
import datetime as dt
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
from background_process import run_hidden, minimized_browser_options
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
import xml.etree.ElementTree as ET
from gift_cards import apply_gift_card, validate_gift_card
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "demo"


def choose_data_root() -> Path:
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", Path.home())) / "RewardsAssistant",
        ROOT / "user_data",
    ]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / f".write-test-{uuid.uuid4().hex}"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return candidate
        except OSError:
            continue
    raise OSError("Rewards Assistant could not find a writable private data folder.")


DATA_ROOT = choose_data_root()
PROFILE_FILE = DATA_ROOT / "profiles.dat"
PROFILE_WARNING = ""
WEB_PROFILE_ROOT = DATA_ROOT / "web-profiles"
WEB_SESSION_ROOT = DATA_ROOT / "web-sessions"
DUTCH_SESSION_ROOT = Path(tempfile.gettempdir()) / "RewardsAssistant-Dutch"
QR_ROOT = DATA_ROOT / "qr-vault"
HOST, PORT = "127.0.0.1", 8768
BUILD_VERSION = "0.5.32"
VERIFICATION_ORIGIN = "https://db-proj.onrender.com"
VERIFICATION_API = f"{VERIFICATION_ORIGIN}/api/verification"
RELAY_POLL_SECONDS = 5.0
RELAYS: dict[str, dict[str, object]] = {}
RELAYS_LOCK = threading.Lock()
BUNDT_SESSION = {}
BUNDT_LOCK = threading.Lock()
TACO_CHECKOUT_LOCK = threading.Lock()
ALL_FIELDS = ("first_name", "last_name", "phone", "email", "zip_code", "birthday")
DUTCH_REQUIRED = ALL_FIELDS
WEB_REQUIRED = ("first_name", "last_name", "email", "zip_code", "birthday")


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes) -> tuple[DATA_BLOB, object]:
    buffer = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def protect(data: bytes) -> bytes:
    source, keepalive = _blob(data)
    output = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(source), "Rewards Assistant profiles", None, None, None, 0, ctypes.byref(output)
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


def load_profiles() -> list[dict[str, str]]:
    global PROFILE_WARNING
    if not PROFILE_FILE.exists():
        PROFILE_WARNING = ""
        return []
    try:
        profiles = json.loads(unprotect(base64.b64decode(PROFILE_FILE.read_bytes())).decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        PROFILE_WARNING = "The previous encrypted profile file cannot be opened by this Windows session. It has been preserved and will not block setup."
        return []
    PROFILE_WARNING = ""
    changed = False
    for profile in profiles:
        if not profile.get("id"):
            profile["id"] = uuid.uuid4().hex
            changed = True
    if changed:
        save_profiles(profiles)
    return profiles


def save_profiles(profiles: list[dict[str, str]]) -> None:
    global PROFILE_WARNING
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    if PROFILE_WARNING and PROFILE_FILE.exists():
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = PROFILE_FILE.with_name(f"profiles-unreadable-{stamp}.dat.bak")
        shutil.copy2(PROFILE_FILE, backup)
    PROFILE_FILE.write_bytes(base64.b64encode(protect(json.dumps(profiles).encode("utf-8"))))
    PROFILE_WARNING = ""


def parse_details(text: str, required: tuple[str, ...] = DUTCH_REQUIRED) -> dict[str, str]:
    values: dict[str, str] = {}
    saw_end = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.rstrip(" ;").upper() == "END":
            saw_end = True
            break
        if ":" not in line:
            raise ValueError(f"Expected key: value, but found {line!r}")
        key, value = line.split(":", 1)
        values[key.strip().casefold()] = value.strip()
    # Gift cards belong only to the checkout request, never persisted signup tasks.
    values.pop("gift_card_number", None)
    values.pop("gift_card_pin", None)
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise ValueError("Missing: " + ", ".join(missing))
    if not saw_end:
        raise ValueError("Put END on its own final line.")
    if values.get("phone") and not re.fullmatch(r"\d{10}", re.sub(r"\D", "", values["phone"])):
        raise ValueError("Phone must contain exactly 10 digits.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", values["email"]):
        raise ValueError("Email address is invalid.")
    if not re.fullmatch(r"\d{5}", values["zip_code"]):
        raise ValueError("ZIP code must contain exactly 5 digits.")
    dt.date.fromisoformat(values["birthday"])
    if values.get("phone"):
        values["phone"] = re.sub(r"\D", "", values["phone"])
    return values


def parse_detail_blocks(text: str, required: tuple[str, ...]) -> list[dict[str, str]]:
    """Parse one or more key/value profiles, each terminated by END."""
    blocks: list[dict[str, str]] = []
    current: list[str] = []
    for raw in text.splitlines():
        current.append(raw)
        if raw.strip().rstrip(" ;").upper() == "END":
            blocks.append(parse_details("\n".join(current), required))
            current = []
    if any(line.strip() for line in current):
        raise ValueError("Every account block must finish with END on its own line.")
    if not blocks:
        raise ValueError("Paste at least one account block ending with END.")
    emails = [item["email"].casefold() for item in blocks]
    if len(emails) != len(set(emails)):
        raise ValueError("Each account in the batch must use a different email address.")
    return blocks


def find_adb() -> str | None:
    path = locate_adb()
    return str(path) if path else None


def find_chrome() -> Path | None:
    candidates = (
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    )
    return next((path for path in candidates if path.exists()), None)


def find_browser_helper() -> Path | None:
    candidates = (
        Path(sys.executable).resolve().parent / "browser-helper",
        ROOT / "chrome_extension",
        Path(getattr(sys, "_MEIPASS", ROOT)) / "chrome_extension",
    )
    return next((path for path in candidates if (path / "manifest.json").is_file()), None)


def find_edge() -> Path | None:
    candidates = (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe",
    )
    return next((path for path in candidates if path.exists()), None)


def open_local_ui() -> None:
    url = f"http://{HOST}:{PORT}/"
    edge = find_edge()
    if edge:
        subprocess.Popen([
            str(edge), f"--app={url}", "--start-maximized",
            "--disable-features=msEdgeSidebarV2",
        ])
    else:
        webbrowser.open(url)


def list_adb_devices() -> list[dict[str, str]]:
    adb = find_adb()
    if not adb:
        return []
    try:
        run_hidden([adb, "start-server"], check=True, capture_output=True, text=True, timeout=15)
        result = run_hidden([adb, "devices", "-l"], check=True, capture_output=True, text=True, timeout=15)
        rows = [line.split() for line in result.stdout.splitlines()[1:] if line.strip()]
    except (subprocess.SubprocessError, OSError):
        return []
    devices = []
    for row in rows:
        if len(row) < 2:
            continue
        devices.append({
            "serial": row[0], "state": row[1],
            "model": next((item.removeprefix("model:").replace("_", " ") for item in row[2:]
                           if item.startswith("model:")), "Android"),
        })
    return devices


def adb_target(adb: str, serial: str, *args: str) -> list[str]:
    return [adb, *(["-s", serial] if serial else []), *args]


def _taco_ui(adb: str, serial: str) -> ET.Element:
    run_hidden(adb_target(adb, serial, "shell", "uiautomator", "dump", "/sdcard/reward-assist.xml"),
                   check=True, capture_output=True, text=True, timeout=20)
    try:
        result = run_hidden(adb_target(adb, serial, "shell", "cat", "/sdcard/reward-assist.xml"),
                                check=True, capture_output=True, text=True, timeout=15)
    finally:
        run_hidden(adb_target(adb, serial, "shell", "rm", "-f", "/sdcard/reward-assist.xml"),
                       capture_output=True, timeout=15)
    return ET.fromstring(result.stdout)


def _bounds_center(bounds: str) -> tuple[int, int]:
    numbers = [int(value) for value in re.findall(r"\d+", bounds)]
    if len(numbers) != 4:
        raise ValueError("Android returned an invalid control position.")
    return ((numbers[0] + numbers[2]) // 2, (numbers[1] + numbers[3]) // 2)


def _taco_tap(adb: str, serial: str, *, text: str = "", resource_id: str = "", topmost: bool = False) -> bool:
    root = _taco_ui(adb, serial)
    parents = {child: parent for parent in root.iter() for child in parent}
    nodes = list(root.iter("node"))
    if topmost:
        nodes = [node for node in nodes if node.attrib.get("bounds") and node.attrib.get("enabled") != "false"]
        nodes.sort(key=lambda node: (_bounds_center(node.attrib["bounds"])[1], _bounds_center(node.attrib["bounds"])[0]))
    for node in nodes:
        if text and text.casefold() not in {node.attrib.get("text", "").casefold(), node.attrib.get("content-desc", "").casefold()}:
            continue
        if resource_id and node.attrib.get("resource-id", "") != resource_id:
            continue
        target = node
        while target.attrib.get("clickable") != "true" and target in parents:
            target = parents[target]
        if target.attrib.get("clickable") != "true":
            target = node
        x, y = _bounds_center(target.attrib.get("bounds", node.attrib.get("bounds", "")))
        run_hidden(adb_target(adb, serial, "shell", "input", "tap", str(x), str(y)),
                       check=True, capture_output=True, text=True, timeout=10)
        time.sleep(1.2)
        return True
    return False


def _taco_texts(adb: str, serial: str) -> list[str]:
    return [node.attrib.get("text", "") for node in _taco_ui(adb, serial).iter("node") if node.attrib.get("text")]


def start_taco_signin(serial: str, email: str) -> dict[str, object]:
    if not serial or not re.fullmatch(r"[A-Za-z0-9._+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", email):
        raise ValueError("Select an Android device and enter a supported email address.")
    status = device_status(serial)
    if not status.get("ok"):
        return status
    adb = find_adb()
    run_hidden(adb_target(adb, serial, "shell", "monkey", "-p", "com.tacobell.ordering",
                              "-c", "android.intent.category.LAUNCHER", "1"),
                   check=True, capture_output=True, timeout=20)
    time.sleep(2)
    root = _taco_ui(adb, serial)
    # Wait across splash, onboarding, and home transitions instead of one snapshot.
    for attempt in range(12):
        texts = [n.get("text", "") for n in root.iter("node")]
        if "Email Address" in texts and "NEXT" in texts:
            break
        if {"Share your location", "Never Miss a Craving"} & set(texts):
            _taco_tap(adb, serial, text="Skip This Step For Now")
        elif "Sign In" in texts:
            _taco_tap(adb, serial, text="Sign In")
        time.sleep(1)
        root = _taco_ui(adb, serial)
    texts = [n.attrib.get("text", "") for n in root.iter("node")]
    fields = [n for n in root.iter("node") if n.attrib.get("class") == "android.widget.EditText"
              and n.attrib.get("package") == "com.tacobell.ordering"]
    if "Email Address" not in texts or "NEXT" not in texts or len(fields) != 1 or fields[0].attrib.get("resource-id") != "input_field":
        raise ValueError("Open Taco Bell's email Sign In screen on Android, then click Retry Android sign-in. Sign out of any previous account first.")
    x, y = _bounds_center(fields[0].attrib["bounds"])
    def entry(*args):
        try:
            run_hidden(adb_target(adb, serial, "shell", "input", *args), check=True, capture_output=True, timeout=15)
        except (subprocess.SubprocessError, OSError):
            raise ValueError("Android sign-in entry was interrupted. Check the device before retrying.") from None
    entry("tap", str(x), str(y))
    entry("keyevent", "KEYCODE_MOVE_END")
    entry("keyevent", *(["KEYCODE_DEL"] * 254))
    entry("text", email)
    root = _taco_ui(adb, serial)
    if not any(n.attrib.get("class") == "android.widget.EditText" and n.attrib.get("text") == email for n in root.iter("node")):
        raise ValueError("Email entry could not be verified. Complete Android sign-in manually.")
    entry("keyevent", "KEYCODE_BACK")
    if not _taco_tap(adb, serial, text="NEXT"):
        raise ValueError("Email entered. Tap NEXT in Taco Bell to continue sign-in.")
    return {"ok": True, "stage": "verification_required", "message": "Email submitted to Taco Bell on Android. Complete its verification or sign-in prompts on the device, then confirm the account before preparing checkout."}


def payment_ready(root: ET.Element, method: str) -> bool:
    nodes = [n for n in root.iter("node") if n.get("package") == "com.tacobell.ordering"]
    texts = {n.get("text", "").strip().casefold() for n in nodes}
    if "place order" not in texts or "select payment method" in texts:
        return False
    labels = ("venmo",) if method == "venmo" else ("taco bell gift card", "gift card")
    return any(n.get("text", "").strip().casefold() in labels for n in nodes)


def choose_taco_payment(serial: str, method: str) -> dict[str, object]:
    if method not in {"venmo", "gift_card"}:
        raise ValueError("Choose Venmo or Gift Card.")
    adb = find_adb()
    root = _taco_ui(adb, serial)
    if not payment_ready(root, method) and method == "venmo":
        _taco_tap(adb, serial, text="Add a Payment Method")
        _taco_tap(adb, serial, text="Venmo")
        root = _taco_ui(adb, serial)
    ready = payment_ready(root, method)
    return {"ok": True, "payment_ready": ready, "message":
            "Selected payment is visible at final checkout." if ready else
            ("Complete Venmo linking in Taco Bell/Venmo, return to checkout, then click Check payment and continue. Linking may be needed again after storage is cleared."
             if method == "venmo" else "Confirm the gift card is selected at final checkout, then click Check payment and continue.")}


def submit_taco_order(serial: str) -> dict[str, object]:
    """Submit once; keep a durable guard if confirmation is uncertain."""
    adb = find_adb()
    root = _taco_ui(adb, serial)
    buttons = [n for n in root.iter("node") if n.get("package") == "com.tacobell.ordering"
               and n.get("text", "").upper() == "PLACE ORDER" and n.get("enabled") != "false"]
    if not buttons:
        raise ValueError("Final PLACE ORDER button is not visible. No order was submitted.")
    guard = DATA_ROOT / ("order-submission-" + re.sub(r"[^A-Za-z0-9_-]", "_", serial) + ".lock")
    try:
        with guard.open("x", encoding="utf-8") as handle:
            handle.write(dt.datetime.now().isoformat())
    except FileExistsError:
        raise ValueError("An order submission was already attempted for this person. Check Taco Bell before continuing; automatic retry is disabled.") from None
    if not _taco_tap(adb, serial, text="PLACE ORDER"):
        raise ValueError("Submission could not be confirmed. Check Taco Bell; automatic retry is disabled.")
    return {"ok": True, "stage": "submission_attempted", "message": "PLACE ORDER was pressed once. Check Taco Bell’s order confirmation before clicking Next person. Automatic resubmission is disabled."}


def prepare_taco_order(serial: str, plan: dict[str, object]) -> dict[str, object]:
    """Prepare one authorized Taco Bell reward order and stop before PLACE ORDER."""
    if plan.get("checkout_confirmed") is not True:
        raise ValueError("Confirm the selected account and checkout preparation first.")
    card = validate_gift_card(plan.get("gift_card"))
    status = device_status(serial)
    if not status.get("ok"):
        return status
    adb = find_adb()
    if not adb:
        raise ValueError("ADB is not installed.")
    package = "com.tacobell.ordering"
    packages = run_hidden(adb_target(adb, serial, "shell", "pm", "list", "packages", package),
                              capture_output=True, text=True, timeout=20).stdout
    if package not in packages:
        raise ValueError("Install the official Taco Bell app on the selected Android device first.")
    reward = str(plan.get("reward", "")).strip()
    if reward == "Beef Soft Taco":
        reward = "Soft Taco"
    allowed_rewards = {"Soft Taco", "Cantina Chicken Crispy Taco", "Beefy 5-Layer Burrito"}
    if reward not in allowed_rewards:
        raise ValueError("Choose Soft Taco, Cantina Chicken Crispy Taco, or Beefy 5-Layer Burrito.")
    location = str(plan.get("location", "")).strip()
    if not location:
        raise ValueError("Enter a Taco Bell address, store, or ZIP.")
    pickup_method = str(plan.get("pickup_method", "Drive-Thru")).strip()
    if pickup_method not in {"Drive-Thru", "In Store"}:
        raise ValueError("Pickup method must be Drive-Thru or In Store.")
    requested_time = str(plan.get("pickup_time", "ASAP")).strip() or "ASAP"
    if requested_time.casefold() != "asap" and not re.fullmatch(r"(?:1[0-2]|[1-9]):[0-5]\d\s*(?:AM|PM)", requested_time, re.I):
        raise ValueError("Pickup time must be ASAP or a time such as 3:15 PM.")

    run_hidden(adb_target(adb, serial, "shell", "monkey", "-p", package,
                              "-c", "android.intent.category.LAUNCHER", "1"),
                   check=True, capture_output=True, text=True, timeout=20)
    time.sleep(2)
    texts = _taco_texts(adb, serial)
    if "PLACE ORDER" in texts or (card and ("Taco Bell Gift Card Number *" in texts or "Select Payment Method" in texts)):
        message = apply_gift_card(adb, serial, card, _taco_ui, _taco_tap, _bounds_center)
        return {"ok": True, "stage": "final_review", "message": (message or "Order is already ready for final review.") + " PLACE ORDER was not pressed."}
    if "Choose Reward" not in texts and "Free Welcome Reward" not in texts:
        _taco_tap(adb, serial, text="Rewards")
    if "Choose Reward" not in texts and not _taco_tap(adb, serial, text="Redeem"):
        raise ValueError("The Free Welcome Reward is not available or is already applied.")
    if "Choose Your Pickup Location" in _taco_texts(adb, serial):
        _taco_tap(adb, serial, text="SELECT STORE")
        root = _taco_ui(adb, serial)
        field = next((node for node in root.iter("node") if node.attrib.get("class") == "android.widget.EditText"), None)
        if field is None:
            raise ValueError("Taco Bell did not expose its store search field.")
        x, y = _bounds_center(field.attrib["bounds"])
        run_hidden(adb_target(adb, serial, "shell", "input", "tap", str(x), str(y)), check=True, timeout=10)
        run_hidden(adb_target(adb, serial, "shell", "input", "keyevent", "123"), check=True, timeout=10)
        for _ in range(30):
            run_hidden(adb_target(adb, serial, "shell", "input", "keyevent", "67"), timeout=10)
        for char in location:
            token = "%s" if char == " " else char
            run_hidden(adb_target(adb, serial, "shell", "input", "text", token), timeout=10)
        run_hidden(adb_target(adb, serial, "shell", "input", "keyevent", "66"), check=True, timeout=10)
        time.sleep(3)
        if not _taco_tap(adb, serial, text="PICKUP HERE", topmost=True):
            raise ValueError("No pickup store was available for that location.")
        _taco_tap(adb, serial, text="Redeem")
    if not _taco_tap(adb, serial, text=reward):
        raise ValueError(f"Could not locate {reward} on the reward screen. Check the available choices in Taco Bell, then retry.")
    if not _taco_tap(adb, serial, text="ADD TO BAG"):
        raise ValueError("Taco Bell did not enable Add to Bag for the selected reward.")
    if not _taco_tap(adb, serial, text="MY BAG"):
        raise ValueError("The reward was applied, but the bag could not be opened.")
    if not _taco_tap(adb, serial, text="GO TO CHECKOUT"):
        raise ValueError("The reward bag could not proceed to checkout.")
    _taco_tap(adb, serial, text="CONTINUE")
    time.sleep(1)
    _taco_tap(adb, serial, text=pickup_method)
    if requested_time.casefold() == "asap":
        _taco_tap(adb, serial, text="ASAP")
    else:
        requested_time = re.sub(r"\s+", " ", requested_time.upper())
        if not _taco_tap(adb, serial, text="Later"):
            raise ValueError("Taco Bell did not offer scheduled pickup for this store.")
        selected = False
        for _ in range(12):
            if _taco_tap(adb, serial, text=requested_time):
                selected = True
                break
            run_hidden(adb_target(adb, serial, "shell", "input", "swipe", "300", "860", "300", "720", "250"),
                           check=True, capture_output=True, text=True, timeout=10)
            time.sleep(0.4)
        if not selected:
            run_hidden(adb_target(adb, serial, "shell", "input", "keyevent", "4"), timeout=10)
            raise ValueError(f"{requested_time} is not an available pickup time for this store.")
        if not _taco_tap(adb, serial, text="CONFIRM"):
            raise ValueError("The scheduled pickup time could not be confirmed.")
        time.sleep(1)
    texts = _taco_texts(adb, serial)
    if "PLACE ORDER" not in texts:
        raise ValueError("Checkout did not reach the final review screen.")
    card_message = apply_gift_card(adb, serial, card, _taco_ui, _taco_tap, _bounds_center)
    return {"ok": True, "stage": "final_review", "message":
            f"{reward} is prepared for {pickup_method} at {location}, pickup {requested_time}. " + (card_message or "Total and store are visible for review. Add any required payment method in Taco Bell.") + " PLACE ORDER was not pressed."}


def device_status(serial: str = "") -> dict[str, object]:
    adb = find_adb()
    if not adb:
        return {"ok": False, "message": "ADB is not installed. Install Android Platform Tools first."}
    devices = list_adb_devices()
    authorized = [item for item in devices if item["state"] == "device"]
    unauthorized = [item for item in devices if item["state"] == "unauthorized"]
    offline = [item for item in devices if item["state"] == "offline"]
    if serial:
        match = next((item for item in devices if item["serial"] == serial), None)
        if not match:
            return {"ok": False, "message": f"Selected Android device {serial} is no longer connected."}
        if match["state"] != "device":
            return {"ok": False, "message": f"{match['model']} is {match['state']}; unlock it and authorize USB debugging."}
        return {"ok": True, "serial": serial, "model": match["model"],
                "devices": devices, "message": f"{match['model']} is selected and USB debugging is authorized."}
    if len(authorized) == 1:
        return {"ok": True, "serial": authorized[0]["serial"], "model": authorized[0]["model"],
                "devices": devices, "message": f"{authorized[0]['model']} is connected and USB debugging is authorized."}
    if len(authorized) > 1:
        return {"ok": False, "needs_selection": True, "devices": devices,
                "message": f"Choose one of the {len(authorized)} connected Android devices."}
    if unauthorized:
        return {"ok": False, "message": "USB debugging is on, but this computer is not authorized. On Android, open Developer options, choose Revoke USB debugging authorizations, toggle USB debugging off/on, reconnect the cable, then tap Allow (optionally Always allow)."}
    if offline:
        return {"ok": False, "message": "Android is connected but ADB reports it offline. Reconnect USB, unlock it, and approve USB debugging."}
    return {"ok": False, "message": "No Android device is visible to ADB. Use a data-capable USB cable and enable USB debugging."}


def reset_dutch_app(serial: str = "") -> dict[str, object]:
    status = device_status(serial)
    if not status["ok"]:
        return status
    adb = find_adb()
    if not adb:
        return {"ok": False, "message": "ADB is not installed."}
    try:
        result = run_hidden(
            adb_target(adb, serial, "shell", "pm", "clear", "com.dutchbros.loyalty"),
            check=True, capture_output=True, text=True, timeout=25,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return {"ok": False, "message": f"Dutch Bros could not be reset: {exc}"}
    if "success" not in result.stdout.casefold():
        return {"ok": False, "message": "Android did not confirm that Dutch Bros data was cleared."}
    DUTCH_SESSION_ROOT.mkdir(parents=True, exist_ok=True)
    (DUTCH_SESSION_ROOT / "sms-code.txt").unlink(missing_ok=True)
    (DUTCH_SESSION_ROOT / "sms-code.tmp").unlink(missing_ok=True)
    (DUTCH_SESSION_ROOT / "status.json").write_text(json.dumps({
        "stage": "idle",
        "message": "Dutch Bros was reset. Paste the next person’s details and start guided setup.",
        "updatedAt": dt.datetime.now().isoformat(),
    }), encoding="utf-8")
    return {
        "ok": True,
        "message": "Dutch Bros local app data was cleared. Saved Rewards Assistant profiles were kept.",
    }


def clear_android_app_data(package_name: str, app_name: str, serial: str = "") -> None:
    """Clear an installed rewards app's local data without deleting its cloud account."""
    status = device_status(serial)
    if not status["ok"]:
        raise ValueError(str(status["message"]))
    adb = find_adb()
    if not adb:
        raise ValueError("ADB is not installed.")
    result = run_hidden(
        adb_target(adb, serial, "shell", "pm", "clear", package_name),
        capture_output=True, text=True, timeout=25,
    )
    if result.returncode != 0 or "success" not in result.stdout.casefold():
        raise ValueError(f"Android could not clear {app_name} local app data.")


def taco_device_status(serial: str = "") -> dict[str, object]:
    """Report whether the connected Android can support the official Taco Bell app flow."""
    status = device_status(serial)
    if not status["ok"]:
        return status
    adb = find_adb()
    if not adb:
        return {"ok": False, "message": "ADB is not installed."}

    def prop(name: str) -> str:
        return run_hidden(
            adb_target(adb, serial, "shell", "getprop", name), capture_output=True, text=True, timeout=15
        ).stdout.strip()

    android = prop("ro.build.version.release")
    sdk_text = prop("ro.build.version.sdk")
    abis = prop("ro.product.cpu.abilist")
    model = prop("ro.product.model") or "Android device"
    packages = run_hidden(
        adb_target(adb, serial, "shell", "pm", "list", "packages", "com.tacobell.ordering"),
        capture_output=True, text=True, timeout=20,
    ).stdout
    installed = "com.tacobell.ordering" in packages
    has_64_bit = any(token in abis for token in ("arm64-v8a", "x86_64"))
    sdk = int(sdk_text) if sdk_text.isdigit() else 0
    compatible = installed or (sdk >= 30 and has_64_bit)
    if installed:
        message = f"Taco Bell is installed on {model}."
    elif compatible:
        message = (
            f"{model} runs Android {android or 'unknown'} with {abis or 'unknown ABI'}. "
            "It passes Reward Assist's basic 64-bit preflight; Google Play makes the final compatibility decision."
        )
    else:
        message = (
            f"{model} runs Android {android or 'unknown'} (API {sdk_text or 'unknown'}) with "
            f"{abis or 'unknown ABI'}. This device is 32-bit-only, and Google Play reports the current "
            "Taco Bell app as incompatible. Use a Play-compatible 64-bit Android device for app sign-in and ordering."
        )
    return {"ok": compatible, "installed": installed, "model": model, "android": android,
            "sdk": sdk, "abis": abis, "message": message}


def save_completed_dutch_profile(details: dict[str, str], qr_temp: Path | None) -> bool:
    profiles = load_profiles()
    profile = next((item for item in profiles if item.get("app") == "Dutch Bros" and
                    item.get("email", "").casefold() == details["email"].casefold()), None)
    if profile is None:
        profile = {
            "id": uuid.uuid4().hex,
            "label": details["first_name"],
            "app": "Dutch Bros",
            "email": details["email"],
            "phone": details["phone"],
            "first_name": details["first_name"],
            "last_name": details["last_name"],
            "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
            "rewards_log": {"medium_drink": False, "birthday_large_drink": False},
        }
        profiles.append(profile)
    else:
        profile["phone"] = details["phone"]
        profile.setdefault("rewards_log", {"medium_drink": False, "birthday_large_drink": False})
    qr_saved = False
    if qr_temp and qr_temp.exists():
        QR_ROOT.mkdir(parents=True, exist_ok=True)
        qr_path = QR_ROOT / f"{profile['id']}.png.dat"
        qr_path.write_bytes(base64.b64encode(protect(qr_temp.read_bytes())))
        qr_temp.unlink(missing_ok=True)
        profile["qr_saved"] = True
        qr_saved = True
    save_profiles(profiles)
    return qr_saved


def monitor_dutch_process(process: subprocess.Popen[object], details: dict[str, str], status_path: Path,
                          qr_temp: Path | None) -> None:
    return_code = process.wait()
    if return_code != 0:
        try:
            previous = json.loads(status_path.read_text(encoding="utf-8"))
            reason = previous.get("message", "")
        except (OSError, ValueError):
            reason = ""
        status_path.write_text(json.dumps({
            "stage": "attention",
            "message": f"Dutch Bros helper stopped with exit code {return_code}. "
                       + (f"Last helper message: {reason}" if reason else "No diagnostic was received. Check the connected phone and retry."),
            "updatedAt": dt.datetime.now().isoformat(),
        }), encoding="utf-8")
        if qr_temp:
            qr_temp.unlink(missing_ok=True)
        return
    try:
        qr_saved = save_completed_dutch_profile(details, qr_temp)
    except Exception as exc:
        status_path.write_text(json.dumps({
            "stage": "attention",
            "message": f"Account completed, but local saving failed: {exc}",
            "updatedAt": dt.datetime.now().isoformat(),
        }), encoding="utf-8")
        return
    status_path.write_text(json.dumps({
        "stage": "complete",
        "message": "Dutch Bros setup completed. Login information was encrypted and saved locally."
                   + (" The Dutch Pass QR was also saved locally." if qr_saved else ""),
        "updatedAt": dt.datetime.now().isoformat(),
    }), encoding="utf-8")


def relay_request(method: str, path: str, payload: dict[str, str] | None = None,
                  access_token: str = "", timeout: float = 35.0) -> tuple[int, dict[str, object]]:
    headers = {"Accept": "application/json"}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    request = Request(f"{VERIFICATION_API}{path}", data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read()
        try:
            error = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            error = {}
        message = str(error.get("error") or f"Verification service returned HTTP {exc.code}.")
        raise ValueError(message) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ValueError(f"Verification service is unavailable: {exc}") from exc


def start_relay(app: str, email: str) -> str:
    cancel_relay(app)
    _, result = relay_request("POST", "/start", {"provider": app, "email": email})
    required = ("request_id", "access_token", "submission_path")
    if any(not result.get(key) for key in required):
        raise ValueError("Verification service returned an incomplete request.")
    relay = {
        "request_id": str(result["request_id"]),
        "access_token": str(result["access_token"]),
        "submission_url": VERIFICATION_ORIGIN + str(result["submission_path"]),
        "last_poll": 0.0,
    }
    with RELAYS_LOCK:
        RELAYS[app] = relay
    return str(relay["submission_url"])


def cancel_relay(app: str) -> None:
    with RELAYS_LOCK:
        relay = RELAYS.pop(app, None)
    if not relay:
        return
    try:
        relay_request(
            "DELETE", f"/{relay['request_id']}", access_token=str(relay["access_token"]), timeout=10.0
        )
    except ValueError:
        pass


def poll_relay(app: str, session_root: Path) -> None:
    with RELAYS_LOCK:
        relay = RELAYS.get(app)
        if not relay or time.monotonic() - float(relay["last_poll"]) < RELAY_POLL_SECONDS:
            return
        relay["last_poll"] = time.monotonic()
        request_id = str(relay["request_id"])
        access_token = str(relay["access_token"])
    try:
        _, result = relay_request("GET", f"/status/{request_id}", access_token=access_token, timeout=20.0)
        if result.get("status") != "code_received":
            return
        code = str(result.get("code", "")).strip()
        if not re.fullmatch(r"\d{4,8}", code):
            raise ValueError("The relayed code is not a 4–8 digit restaurant verification code.")
        task_path = session_root / "task.json"
        if not task_path.exists():
            return
        task = json.loads(task_path.read_text(encoding="utf-8"))
        task["verification_code"] = code
        task_path.write_text(json.dumps(task), encoding="utf-8")
        (session_root / "status.json").write_text(json.dumps({
            "stage": "code_received",
            "message": "Verification code received securely and sent to Chrome.",
            "updatedAt": dt.datetime.now().isoformat(),
        }), encoding="utf-8")
        try:
            relay_request("DELETE", f"/{request_id}", access_token=access_token, timeout=20.0)
        finally:
            with RELAYS_LOCK:
                RELAYS.pop(app, None)
    except ValueError as exc:
        (session_root / "status.json").write_text(json.dumps({
            "stage": "waiting_code",
            "message": f"Automatic code check is waiting: {exc}",
            "updatedAt": dt.datetime.now().isoformat(),
        }), encoding="utf-8")


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        query = parse_qs(parsed_url.query)
        if self.path == "/api/status":
            profiles = load_profiles()
            self.send_json(200, {
                "local": True, "version": BUILD_VERSION, "profiles": profiles, "warning": PROFILE_WARNING,
            })
            return
        if parsed_url.path == "/api/adb":
            serial = str(query.get("serial", [""])[0])
            result = device_status(serial)
            result["devices"] = list_adb_devices()
            self.send_json(200, result)
            return
        if parsed_url.path == "/api/taco/device":
            result = taco_device_status(str(query.get("serial", [""])[0]))
            self.send_json(200 if result["ok"] else 409, result)
            return
        if parsed_url.path == "/api/dutch/status":
            status_path = DUTCH_SESSION_ROOT / "status.json"
            if status_path.exists():
                self.send_json(200, json.loads(status_path.read_text(encoding="utf-8")))
            else:
                self.send_json(200, {"stage": "idle", "message": "No Dutch Bros setup is running."})
            return
        if parsed_url.path == "/api/profile/qr":
            profile_id = parse_qs(parsed_url.query).get("id", [""])[0]
            if not re.fullmatch(r"[0-9a-f]{32}", profile_id):
                self.send_json(400, {"ok": False, "message": "Invalid profile ID."})
                return
            qr_path = QR_ROOT / f"{profile_id}.png.dat"
            if not qr_path.exists():
                self.send_json(404, {"ok": False, "message": "No saved QR is available for this profile."})
                return
            try:
                image = unprotect(base64.b64decode(qr_path.read_bytes()))
            except (OSError, ValueError):
                self.send_json(409, {"ok": False, "message": "The encrypted QR cannot be opened in this Windows session."})
                return
            profile = next((item for item in load_profiles() if item.get("id") == profile_id), {})
            self.send_bytes(200, image, str(profile.get("qr_mime", "image/png")))
            return
        if parsed_url.path == "/api/web/status":
            app = parse_qs(parsed_url.query).get("app", [""])[0]
            if app == "Nothing Bundt Cakes":
                with BUNDT_LOCK:
                    status = dict(BUNDT_SESSION.get("status", {"stage": "idle", "message": "Start Nothing Bundt Cakes setup first."}))
                self.send_json(200, status)
                return
            slug = re.sub(r"[^A-Za-z]+", "-", app).strip("-").lower()
            status_path = WEB_SESSION_ROOT / slug / "status.json"
            if app in {"Taco Bell", "Wendy's"}:
                poll_relay(app, status_path.parent)
            if not status_path.exists():
                self.send_json(200, {"stage": "idle", "message": "No assisted setup is running."})
            else:
                self.send_json(200, json.loads(status_path.read_text(encoding="utf-8")))
            return
        if parsed_url.path == "/api/extension/task":
            app = parse_qs(parsed_url.query).get("app", [""])[0]
            slug = re.sub(r"[^A-Za-z]+", "-", app).strip("-").lower()
            if app == "Nothing Bundt Cakes":
                with BUNDT_LOCK:
                    task = dict(BUNDT_SESSION.get("task", {"active": False})) if time.monotonic() < BUNDT_SESSION.get("expires", 0) else {"active": False}
                    if not task.get("active"):
                        BUNDT_SESSION.pop("task", None)
                self.send_json(200, task)
                return
            task_path = WEB_SESSION_ROOT / slug / "task.json"
            if not task_path.exists():
                self.send_json(200, {"active": False})
            else:
                self.send_json(200, json.loads(task_path.read_text(encoding="utf-8")))
            return
        super().do_GET()

    def do_DELETE(self) -> None:
        try:
            if self.path != "/api/profile":
                self.send_json(404, {"ok": False, "message": "Unknown endpoint."})
                return
            profile_id = str(self.read_json().get("id", "")).strip()
            if not profile_id:
                raise ValueError("Profile ID is required.")
            profiles = load_profiles()
            remaining = [profile for profile in profiles if profile.get("id") != profile_id]
            if len(remaining) == len(profiles):
                self.send_json(404, {"ok": False, "message": "Profile was not found."})
                return
            (QR_ROOT / f"{profile_id}.png.dat").unlink(missing_ok=True)
            save_profiles(remaining)
            self.send_json(200, {"ok": True, "profiles": remaining, "message": "Profile deleted."})
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "message": str(exc)})
        except Exception as exc:
            self.send_json(500, {"ok": False, "message": f"Local operation failed: {exc}"})

    def do_POST(self) -> None:
        try:
            payload = self.read_json()
            if self.path == "/api/profile/custom":
                label = str(payload.get("label", "")).strip()
                app = str(payload.get("app", "Custom account")).strip()
                email = str(payload.get("email", "")).strip()
                username = str(payload.get("username", "")).strip()
                if not label:
                    raise ValueError("Profile name is required.")
                if not app:
                    raise ValueError("Service or restaurant name is required.")
                if not email and not username:
                    raise ValueError("Enter an email or username.")
                profile_id = uuid.uuid4().hex
                profile = {
                    "id": profile_id,
                    "label": label,
                    "app": app,
                    "email": email,
                    "username": username,
                    "password": str(payload.get("password", "")),
                    "phone": str(payload.get("phone", "")).strip(),
                    "first_name": str(payload.get("first_name", "")).strip(),
                    "last_name": str(payload.get("last_name", "")).strip(),
                    "notes": str(payload.get("notes", "")).strip(),
                    "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "custom": True,
                }
                qr_data = str(payload.get("qr_data", ""))
                if qr_data:
                    match = re.fullmatch(r"data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=\r\n]+)", qr_data)
                    if not match:
                        raise ValueError("QR image must be PNG, JPEG, or WebP.")
                    image = base64.b64decode(match.group(2), validate=True)
                    if len(image) > 5 * 1024 * 1024:
                        raise ValueError("QR image must be 5 MB or smaller.")
                    QR_ROOT.mkdir(parents=True, exist_ok=True)
                    (QR_ROOT / f"{profile_id}.png.dat").write_bytes(base64.b64encode(protect(image)))
                    profile["qr_saved"] = True
                    profile["qr_mime"] = match.group(1)
                profiles = load_profiles()
                profiles.append(profile)
                save_profiles(profiles)
                self.send_json(200, {"ok": True, "profiles": profiles, "message": "Custom profile saved securely on this computer."})
                return
            if self.path == "/api/profile":
                app = str(payload.get("app", "Dutch Bros"))
                details = parse_details(
                    str(payload.get("details", "")),
                    DUTCH_REQUIRED if app == "Dutch Bros" else WEB_REQUIRED,
                )
                profile = {
                    "id": uuid.uuid4().hex,
                    "label": str(payload.get("label", "Profile")).strip() or "Profile",
                    "app": app,
                    "email": details["email"],
                    "phone": details.get("phone", ""),
                    "first_name": details["first_name"],
                    "last_name": details["last_name"],
                    "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
                }
                if app == "Dutch Bros":
                    profile["rewards_log"] = {"medium_drink": False, "birthday_large_drink": False}
                profiles = load_profiles()
                profiles.append(profile)
                save_profiles(profiles)
                self.send_json(200, {"ok": True, "profiles": profiles})
                return
            if self.path in {"/api/dutch/start", "/api/dutch/resume"}:
                resume_current = self.path.endswith("/resume")
                serial = str(payload.get("device_serial", "")).strip()
                status = device_status(serial)
                if not status["ok"]:
                    self.send_json(409, status)
                    return
                details = parse_details(str(payload.get("details", "")))
                if payload.get("reset_existing") is True and not resume_current:
                    clear_android_app_data("com.dutchbros.loyalty", "Dutch Bros", serial)
                if payload.get("terms_accepted") is not True:
                    raise ValueError("The account holder must review and accept the terms before setup.")
                save_qr = bool(payload.get("save_qr", False))
                frozen_helper = ROOT / "Dutch Bros Setup.exe"
                script = ROOT.parent / "dutch_bros_signup_assistant.py"
                if getattr(sys, "frozen", False):
                    if not frozen_helper.exists():
                        raise ValueError("The packaged Dutch Bros helper is missing. Reinstall Rewards Assistant.")
                    helper_command = [str(frozen_helper)]
                else:
                    if not script.exists():
                        raise ValueError(f"Dutch Bros automation helper is missing: {script}")
                    helper_command = [sys.executable, str(script)]
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", prefix="rewards-dutch-", suffix=".txt", delete=False
                ) as details_handle:
                    details_handle.write(
                        "\n".join(f"{key}: {details[key]}" for key in ALL_FIELDS) + "\nEND\n"
                    )
                    details_path = Path(details_handle.name)
                DUTCH_SESSION_ROOT.mkdir(parents=True, exist_ok=True)
                status_path = DUTCH_SESSION_ROOT / "status.json"
                sms_code_path = DUTCH_SESSION_ROOT / "sms-code.txt"
                sms_code_path.unlink(missing_ok=True)
                status_path.write_text(json.dumps({
                    "stage": "starting",
                    "message": "Starting Dutch Bros on the authorized Android device...",
                    "updatedAt": dt.datetime.now().isoformat(),
                }), encoding="utf-8")
                qr_temp = DUTCH_SESSION_ROOT / f"qr-{uuid.uuid4().hex}.png" if save_qr else None
                command = helper_command + [
                    "--details-file", str(details_path),
                    "--status-file", str(status_path), "--sms-code-file", str(sms_code_path),
                    "--managed-run", "--consent-confirmed",
                ]
                if qr_temp:
                    command.extend(["--qr-file", str(qr_temp)])
                if resume_current:
                    command.append("--resume-current")
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                try:
                    helper_env = os.environ.copy()
                    if serial:
                        helper_env["REWARD_ASSIST_ADB_SERIAL"] = serial
                    process = subprocess.Popen(command, creationflags=flags, env=helper_env)
                except Exception:
                    details_path.unlink(missing_ok=True)
                    raise
                threading.Thread(
                    target=monitor_dutch_process,
                    args=(process, details, status_path, qr_temp),
                    daemon=True,
                ).start()
                self.send_json(200, {
                    "ok": True,
                    "message": (
                        "Dutch Bros resume started from the current device screen."
                        if resume_current else
                        "Dutch Bros guided setup started. Progress will appear here."
                    ),
                })
                return
            if self.path == "/api/dutch/code":
                code = str(payload.get("code", "")).strip()
                if not re.fullmatch(r"\d{4,8}", code):
                    raise ValueError("Verification code must contain 4 to 8 digits.")
                DUTCH_SESSION_ROOT.mkdir(parents=True, exist_ok=True)
                code_path = DUTCH_SESSION_ROOT / "sms-code.txt"
                temporary_path = DUTCH_SESSION_ROOT / "sms-code.tmp"
                temporary_path.write_text(code, encoding="utf-8")
                temporary_path.replace(code_path)
                self.send_json(200, {"ok": True, "message": "SMS code sent to the Dutch Bros helper."})
                return
            if self.path == "/api/dutch/reset":
                result = reset_dutch_app(str(payload.get("device_serial", "")).strip())
                self.send_json(200 if result["ok"] else 409, result)
                return
            if self.path == "/api/dutch/recover":
                details = parse_details(str(payload.get("details", "")))
                qr_candidates = sorted(
                    DUTCH_SESSION_ROOT.glob("qr-*.png"), key=lambda path: path.stat().st_mtime, reverse=True
                )
                qr_temp = qr_candidates[0] if qr_candidates else None
                qr_saved = save_completed_dutch_profile(details, qr_temp)
                status_path = DUTCH_SESSION_ROOT / "status.json"
                status_path.write_text(json.dumps({
                    "stage": "complete",
                    "message": "Completed Dutch Bros account recovered and saved locally."
                               + (" The Dutch Pass QR was saved too." if qr_saved else ""),
                    "updatedAt": dt.datetime.now().isoformat(),
                }), encoding="utf-8")
                self.send_json(200, {
                    "ok": True,
                    "message": "Completed account saved without repeating signup.",
                    "qr_saved": qr_saved,
                })
                return
            if self.path == "/api/profile/reward":
                profile_id = str(payload.get("id", ""))
                reward = str(payload.get("reward", ""))
                if reward not in {"medium_drink", "birthday_large_drink"}:
                    raise ValueError("Unknown drink tracker item.")
                profiles = load_profiles()
                profile = next((item for item in profiles if item.get("id") == profile_id), None)
                if profile is None:
                    raise ValueError("Profile was not found.")
                log = profile.setdefault("rewards_log", {})
                log[reward] = bool(payload.get("used", False))
                save_profiles(profiles)
                self.send_json(200, {"ok": True, "message": "Drink usage log updated."})
                return
            if self.path == "/api/web/start":
                app = str(payload.get("app", ""))
                if app == "Nothing Bundt Cakes":
                    queue = parse_detail_blocks(str(payload.get("details", "")), WEB_REQUIRED + ("phone", "password", "country", "state", "bakery"))
                    if len(queue) != 1:
                        raise ValueError("Test one Nothing Bundt Cakes account at a time.")
                    details = {key: queue[0][key] for key in WEB_REQUIRED + ("phone", "password", "country", "state", "bakery")}
                    if details["country"] not in {"United States", "Canada"}:
                        raise ValueError("Use country: United States or country: Canada.")
                    browser = find_chrome()
                    if browser is None:
                        raise ValueError("Install Google Chrome and enable Rewards Assistant Helper first.")
                    with BUNDT_LOCK:
                        BUNDT_SESSION.clear()
                        BUNDT_SESSION.update(task={"active": True, "details": details, "session_id": uuid.uuid4().hex}, expires=time.monotonic()+900,
                            status={"stage": "waiting_extension", "message": "Opening Nothing Bundt Cakes. Enable or reload Rewards Assistant Helper if the form does not fill."})
                    try:
                        subprocess.Popen([str(browser), "--new-window", "https://www.nothingbundtcakes.com/customer/account/create/"], **minimized_browser_options())
                    except OSError:
                        with BUNDT_LOCK:
                            BUNDT_SESSION.clear()
                        raise ValueError("Chrome could not open. Try again.") from None
                    self.send_json(200, {"ok": True, "message": "Opening Nothing Bundt Cakes. The helper will fill the form and click Create Account once."})
                    return
                if app not in {"Taco Bell", "Wendy's"}:
                    raise ValueError("Choose Taco Bell or Wendy's.")
                queue = parse_detail_blocks(str(payload.get("details", "")), WEB_REQUIRED)
                if app != "Taco Bell" and len(queue) > 1:
                    raise ValueError("Batch setup is currently available only for Taco Bell.")
                if len(queue) > 8:
                    raise ValueError("A Taco Bell batch can contain at most 8 distinct account-holder profiles.")
                details = queue[0]
                browser = find_chrome()
                if browser is None:
                    raise ValueError("Google Chrome is not installed on this computer.")
                slug = re.sub(r"[^A-Za-z]+", "-", app).strip("-").lower()
                session_root = WEB_SESSION_ROOT / slug
                session_root.mkdir(parents=True, exist_ok=True)
                for stale_name in ("status.json", "code.txt", "approve.txt", "task.json"):
                    stale_path = session_root / stale_name
                    if stale_path.exists():
                        stale_path.unlink()
                task = {
                    "active": True,
                    "app": app,
                    "details": details,
                    "queue": queue,
                    "queue_index": 0,
                    "verification_code": "",
                    "approved": False,
                    "created_at": dt.datetime.now().isoformat(timespec="seconds"),
                }
                (session_root / "task.json").write_text(json.dumps(task), encoding="utf-8")
                try:
                    submission_url = start_relay(app, details["email"])
                except ValueError:
                    # Remote code sharing is optional; manual code entry still works.
                    submission_url = ""
                (session_root / "status.json").write_text(json.dumps({
                    "stage": "waiting_extension",
                    "message": f"Opening Taco Bell account 1 of {len(queue)} in normal Chrome."
                    if len(queue) > 1 else
                    "Opening normal Chrome. The Rewards Assistant extension will fill the official page. "
                    + ("" if submission_url else "Protected verification page unavailable; enter the email code below when requested."),
                    "batch_current": 1,
                    "batch_total": len(queue),
                    "submission_url": submission_url,
                    "updatedAt": dt.datetime.now().isoformat(),
                }), encoding="utf-8")
                url = (
                    "https://www.tacobell.com/register/yum"
                    if app == "Taco Bell"
                    else "https://order.wendys.com/us/en/sign-in?lang=en_US&tab=offers"
                )
                helper = find_browser_helper()
                browser_command = [str(browser), "--new-window"]
                if helper:
                    browser_command.append(f"--load-extension={helper}")
                browser_command.append(url)
                try:
                    subprocess.Popen(browser_command, **minimized_browser_options())
                except OSError as exc:
                    task["active"] = False
                    (session_root / "task.json").write_text(json.dumps(task), encoding="utf-8")
                    raise ValueError("Chrome could not open. Check its installation, then retry this person.") from exc
                self.send_json(200, {
                    "ok": True,
                    "url": url,
                    "submission_url": submission_url,
                    "message": f"{app} opened in normal Chrome. Keep Rewards Assistant running while the extension works.",
                })
                return
            if self.path == "/api/paris/start":
                details = parse_detail_blocks(str(payload.get("details", "")), WEB_REQUIRED)[0]
                if not details.get("phone"):
                    raise ValueError("Paris Baguette signup requires a smartphone number in the details block.")
                serial = str(payload.get("device_serial", "")).strip()
                status = device_status(serial)
                if not status["ok"]:
                    self.send_json(409, status)
                    return
                adb = find_adb()
                if not adb:
                    raise ValueError("ADB is not installed.")
                package_name = "com.parisbaguette.app"
                packages = run_hidden(
                    adb_target(adb, serial, "shell", "pm", "list", "packages", package_name),
                    capture_output=True, text=True, timeout=20,
                ).stdout
                if package_name not in packages:
                    subprocess.Popen(adb_target(adb, serial, "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", f"market://details?id={package_name}"), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    self.send_json(409, {"ok": False, "message": "Paris Baguette is not installed. Its official Google Play listing is open on the connected Android device; install it, then retry."})
                    return
                if payload.get("reset_existing") is True:
                    clear_android_app_data(package_name, "Paris Baguette", serial)
                run_hidden(
                    adb_target(adb, serial, "shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"),
                    capture_output=True, text=True, timeout=20,
                )
                self.send_json(200, {"ok": True, "message": "Paris Baguette opened on the authorized Android device for the live signup test."})
                return
            if self.path == "/api/web/cancel":
                app = str(payload.get("app", ""))
                if app != "Taco Bell":
                    raise ValueError("Choose Taco Bell to end this group.")
                # Match the lowercase slug used by the signup/status endpoints.
                session_root = WEB_SESSION_ROOT / "taco-bell"
                session_root.mkdir(parents=True, exist_ok=True)
                (session_root / "task.json").write_text(json.dumps({"active": False}), encoding="utf-8")
                cancel_relay(app)
                (session_root / "status.json").write_text(json.dumps({
                    "stage": "idle", "message": "Group ended. Any open checkout remains in Taco Bell."
                }), encoding="utf-8")
                self.send_json(200, {"ok": True})
                return
            if self.path == "/api/taco/payment":
                serial = str(payload.get("device_serial", "")).strip()
                if not serial or not device_status(serial).get("ok"):
                    raise ValueError("Connect the selected Android device.")
                if not TACO_CHECKOUT_LOCK.acquire(blocking=False):
                    raise ValueError("Wait for the current Android step.")
                try:
                    result = choose_taco_payment(serial, str(payload.get("payment_method", "")))
                finally:
                    TACO_CHECKOUT_LOCK.release()
                self.send_json(200, result)
                return
            if self.path == "/api/taco/submit":
                serial = str(payload.get("device_serial", "")).strip()
                if payload.get("submit_confirmed") is not True or not serial:
                    raise ValueError("Enable automatic order submission for this person first.")
                if not device_status(serial).get("ok"):
                    raise ValueError("The selected Android device is not connected.")
                if not TACO_CHECKOUT_LOCK.acquire(blocking=False):
                    raise ValueError("Wait for the current Android step to finish.")
                try:
                    method = str(payload.get("payment_method", ""))
                    if method not in {"venmo", "gift_card"} or not payment_ready(_taco_ui(find_adb(), serial), method):
                        raise ValueError("The selected payment method is not confirmed at checkout. No order was submitted.")
                    result = submit_taco_order(serial)
                finally:
                    TACO_CHECKOUT_LOCK.release()
                self.send_json(200, result)
                return
            if self.path == "/api/taco/reset":
                serial = str(payload.get("device_serial", "")).strip()
                if not serial or payload.get("previous_person_finished") is not True:
                    raise ValueError("Confirm the previous person is finished and select an Android device.")
                if not TACO_CHECKOUT_LOCK.acquire(blocking=False):
                    raise ValueError("Wait for the current Android step to finish.")
                try:
                    clear_android_app_data("com.tacobell.ordering", "Taco Bell", serial)
                    (DATA_ROOT / ("order-submission-" + re.sub(r"[^A-Za-z0-9_-]", "_", serial) + ".lock")).unlink(missing_ok=True)
                finally:
                    TACO_CHECKOUT_LOCK.release()
                self.send_json(200, {"ok": True, "message": "Taco Bell Android data cleared for the next person."})
                return
            if self.path == "/api/taco/verify":
                serial = str(payload.get("device_serial", "")).strip()
                code = str(payload.get("code", "")).strip()
                status = device_status(serial)
                if not serial or not status.get("ok"):
                    raise ValueError("Connect and select the Android device first.")
                if not TACO_CHECKOUT_LOCK.acquire(blocking=False):
                    raise ValueError("Wait for the current Android step to finish.")
                try:
                    result = verify_android_code(find_adb(), serial, code, _taco_ui, _taco_tap, _bounds_center, adb_target)
                finally:
                    TACO_CHECKOUT_LOCK.release()
                self.send_json(200, result)
                return
            if self.path == "/api/taco/signin":
                if not TACO_CHECKOUT_LOCK.acquire(blocking=False):
                    raise ValueError("Another Android action is running. Wait for it to finish.")
                try:
                    result = start_taco_signin(str(payload.get("device_serial", "")).strip(), str(payload.get("email", "")).strip())
                finally:
                    TACO_CHECKOUT_LOCK.release()
                self.send_json(200 if result.get("ok") else 409, result)
                return
            if self.path == "/api/taco/prepare":
                serial = str(payload.get("device_serial", "")).strip()
                plan = payload.get("plan")
                if not isinstance(plan, dict):
                    raise ValueError("A Taco Bell order plan is required.")
                if not TACO_CHECKOUT_LOCK.acquire(blocking=False):
                    raise ValueError("A checkout is already being prepared. Wait for it to finish.")
                try:
                    result = prepare_taco_order(serial, plan)
                finally:
                    TACO_CHECKOUT_LOCK.release()
                self.send_json(200 if result.get("ok") else 409, result)
                return
            if self.path == "/api/extension/status":
                app = str(payload.get("app", ""))
                if app == "Nothing Bundt Cakes":
                    with BUNDT_LOCK:
                        task = BUNDT_SESSION.get("task", {})
                        if payload.get("session_id") == task.get("session_id") and task.get("active"):
                            stage = str(payload.get("stage", "attention"))
                            if stage == "claim_submit":
                                if task.get("submitted"):
                                    self.send_json(200, {"ok": True, "claimed": False})
                                    return
                                task["submitted"] = True
                                task["profile"] = {k: v for k, v in task.get("details", {}).items() if k != "password"}
                                task.pop("details", None)
                                BUNDT_SESSION["status"] = {"stage": "submitted", "message": "Create Account is being clicked once. Waiting for the registration confirmation; automatic retry is disabled."}
                                self.send_json(200, {"ok": True, "claimed": True})
                                return
                            messages = {
                                "complete": "Nothing Bundt Cakes confirmed registration. Profile saved locally.",
                                "filling_details": "Filling Nothing Bundt Cakes details and waiting for bakery choices.",
                                "attention": "Signup could not be confirmed. Check validation or verification in Chrome. Create Account will not be clicked again automatically."
                            }
                            if stage == "complete" and not task.get("submitted"):
                                self.send_json(200, {"ok": True, "ignored": True})
                                return
                            BUNDT_SESSION["status"] = {"stage": stage if stage in messages else "attention", "message": messages.get(stage, messages["attention"])}
                            if stage == "complete":
                                profile = dict(task.get("profile", {}))
                                profile.update(id=uuid.uuid4().hex, app=app, label=profile.get("first_name", "Profile"), saved_at=dt.datetime.now().isoformat(timespec="seconds"))
                                profiles = load_profiles()
                                if not any(p.get("app") == app and p.get("email", "").casefold() == profile.get("email", "").casefold() for p in profiles):
                                    profiles.append(profile)
                                    save_profiles(profiles)
                            if stage in {"complete", "attention"}:
                                BUNDT_SESSION.pop("task", None)
                    self.send_json(200, {"ok": True})
                    return
                if app not in {"Taco Bell", "Wendy's"}:
                    raise ValueError("Invalid extension status source.")
                slug = re.sub(r"[^A-Za-z]+", "-", app).strip("-").lower()
                session_root = WEB_SESSION_ROOT / slug
                session_root.mkdir(parents=True, exist_ok=True)
                status = {
                    "stage": str(payload.get("stage", "attention")),
                    "message": str(payload.get("message", "The extension is waiting.")),
                    "updatedAt": dt.datetime.now().isoformat(),
                }
                existing_status_path = session_root / "status.json"
                task_path = session_root / "task.json"
                current_task = json.loads(task_path.read_text(encoding="utf-8")) if task_path.exists() else {}
                if not current_task.get("active"):
                    self.send_json(200, {"ok": True, "ignored": True})
                    return
                if status["stage"] == "complete":
                    completed_details = payload.get("details")
                    expected_email = str(current_task.get("details", {}).get("email", "")).casefold()
                    if not isinstance(completed_details, dict) or str(completed_details.get("email", "")).casefold() != expected_email:
                        self.send_json(200, {"ok": True, "ignored": True})
                        return
                if existing_status_path.exists():
                    existing = json.loads(existing_status_path.read_text(encoding="utf-8"))
                    for key in ("batch_current", "batch_total", "submission_url"):
                        if key in existing:
                            status[key] = existing[key]
                (session_root / "status.json").write_text(json.dumps(status), encoding="utf-8")
                task_path = session_root / "task.json"
                if status["stage"] == "filling_details" and task_path.exists():
                    task = json.loads(task_path.read_text(encoding="utf-8"))
                    task["verification_code"] = ""
                    task_path.write_text(json.dumps(task), encoding="utf-8")
                if status["stage"] == "complete" and isinstance(payload.get("details"), dict):
                    details = payload["details"]
                    profile = {
                        "id": uuid.uuid4().hex,
                        "label": str(details.get("first_name", "Profile")).strip() or "Profile",
                        "app": app,
                        "email": str(details.get("email", "")).strip(),
                        "first_name": str(details.get("first_name", "")).strip(),
                        "last_name": str(details.get("last_name", "")).strip(),
                        "birthday": str(details.get("birthday", "")).strip(),
                        "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
                    }
                    profiles = load_profiles()
                    if profile["email"] and not any(
                        item.get("app") == app and item.get("email", "").casefold() == profile["email"].casefold()
                        for item in profiles
                    ):
                        profiles.append(profile)
                        save_profiles(profiles)
                    cancel_relay(app)
                    task = json.loads(task_path.read_text(encoding="utf-8")) if task_path.exists() else {}
                    queue = task.get("queue") if isinstance(task.get("queue"), list) else []
                    index = int(task.get("queue_index", 0))
                    if index + 1 < len(queue):
                        index += 1
                        next_details = queue[index]
                        task.update({
                            "active": True, "details": next_details, "queue_index": index,
                            "verification_code": "", "approved": False,
                        })
                        task_path.write_text(json.dumps(task), encoding="utf-8")
                        submission_url = start_relay(app, next_details["email"])
                        next_url = "https://www.tacobell.com/register/yum"
                        next_status = {
                            "stage": "waiting_extension",
                            "message": f"Account {index} saved. Starting Taco Bell account {index + 1} of {len(queue)}.",
                            "batch_current": index + 1, "batch_total": len(queue),
                            "submission_url": submission_url,
                            "updatedAt": dt.datetime.now().isoformat(),
                        }
                        (session_root / "status.json").write_text(json.dumps(next_status), encoding="utf-8")
                        self.send_json(200, {"ok": True, "next_url": next_url, "batch_current": index + 1, "batch_total": len(queue)})
                        return
                    task_path.write_text(json.dumps({"active": False}), encoding="utf-8")
                    status.update({"message": f"All {len(queue) or 1} account setup(s) completed and saved locally.", "batch_current": len(queue) or 1, "batch_total": len(queue) or 1})
                    (session_root / "status.json").write_text(json.dumps(status), encoding="utf-8")
                self.send_json(200, {"ok": True})
                return
            if self.path in {"/api/web/code", "/api/web/approve"}:
                app = str(payload.get("app", ""))
                slug = re.sub(r"[^A-Za-z]+", "-", app).strip("-").lower()
                session_root = WEB_SESSION_ROOT / slug
                if not session_root.exists():
                    raise ValueError("Start guided setup first.")
                if self.path.endswith("/code"):
                    code = str(payload.get("code", "")).strip()
                    if not re.fullmatch(r"\d{4,8}", code):
                        raise ValueError("Verification code must contain 4 to 8 digits.")
                    task_path = session_root / "task.json"
                    if not task_path.exists():
                        raise ValueError("Start guided setup first.")
                    task = json.loads(task_path.read_text(encoding="utf-8"))
                    task["verification_code"] = code
                    task_path.write_text(json.dumps(task), encoding="utf-8")
                    cancel_relay(app)
                    self.send_json(200, {"ok": True, "message": "Code sent to the Chrome extension."})
                else:
                    task_path = session_root / "task.json"
                    if not task_path.exists():
                        raise ValueError("Start guided setup first.")
                    task = json.loads(task_path.read_text(encoding="utf-8"))
                    task["approved"] = True
                    task_path.write_text(json.dumps(task), encoding="utf-8")
                    self.send_json(200, {"ok": True, "message": "Final creation approved."})
                return
            self.send_json(404, {"ok": False, "message": "Unknown endpoint."})
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "message": str(exc)})
        except Exception as exc:
            self.send_json(500, {"ok": False, "message": f"Local operation failed: {exc}"})

    def log_message(self, format: str, *args: object) -> None:
        return


class ExclusiveThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def main() -> None:
    global PORT
    server = None
    for candidate_port in range(PORT, PORT + 10):
        PORT = candidate_port
        try:
            server = ExclusiveThreadingHTTPServer((HOST, PORT), Handler)
            break
        except OSError as exc:
            if getattr(exc, "winerror", None) != 10048:
                raise
            continue
    if server is None:
        raise OSError("Reward Assist could not find an available local port. Close old Reward Assist windows and retry.")
    threading.Timer(0.5, open_local_ui).start()
    print(f"Rewards Assistant is running at http://{HOST}:{PORT}/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
