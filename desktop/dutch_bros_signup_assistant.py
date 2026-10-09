#!/usr/bin/env python3
"""Consent-gated Dutch Bros signup assistant driven by Android Debug Bridge.

The program reads account details from the local terminal, holds them only in
memory, pauses for the user-supplied SMS code, and stops on unexpected screens.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path


PACKAGE = "com.dutchbros.loyalty"
PLAY_STORE_PACKAGE = "com.android.vending"
PLAY_STORE_URI = f"market://details?id={PACKAGE}"
SCREEN_TIMEOUT_MS = "1800000"  # 30 minutes
REQUIRED = ("first_name", "last_name", "phone", "email", "zip_code", "birthday")
PRACTICE = {
    "first_name": "Practice",
    "last_name": "User",
    "phone": "2025550100",  # NANPA-reserved fictional-use number.
    "email": "practice@example.com",
    "zip_code": "00000",
    "birthday": "2000-01-01",
}
ARCHIVE_ROOT = Path(__file__).resolve().parent / "account_archive"


class StatusMirror:
    def __init__(self, stream: object, status_file: Path):
        self.stream = stream
        self.status_file = status_file
        self.pending = ""

    def write(self, text: str) -> int:
        written = self.stream.write(text) if self.stream is not None else len(text)
        if self.stream is not None:
            self.stream.flush()
        self.pending += text
        while "\n" in self.pending:
            line, self.pending = self.pending.split("\n", 1)
            message = line.strip()
            if message:
                self.status_file.write_text(json.dumps({
                    "stage": "running", "message": message,
                    "updatedAt": dt.datetime.now().isoformat(),
                }), encoding="utf-8")
        return written

    def flush(self) -> None:
        if self.stream is not None:
            self.stream.flush()


def find_adb() -> str:
    candidates = [
        os.environ.get("ADB", ""),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Android/Sdk/platform-tools/adb.exe"),
        "adb",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            subprocess.run(
                [candidate, "version"], check=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return candidate
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
    raise SystemExit("ADB was not found. Set the ADB environment variable to adb.exe.")


ADB = find_adb()
ADB_SERIAL = os.environ.get("REWARD_ASSIST_ADB_SERIAL", "").strip()


def adb(*args: str, capture: bool = False) -> str:
    command = [ADB]
    if ADB_SERIAL and args and args[0] not in {"devices", "version", "start-server", "kill-server"}:
        command.extend(["-s", ADB_SERIAL])
    result = subprocess.run(
        [*command, *args], check=True, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
    )
    return result.stdout if capture else ""


def save_device_screenshot(path: Path) -> None:
    """Save a PNG from the attached device without routing binary data through text mode."""
    with path.open("wb") as output:
        subprocess.run(
            [ADB, *(["-s", ADB_SERIAL] if ADB_SERIAL else []), "exec-out", "screencap", "-p"],
            check=True,
            stdout=output,
            stderr=subprocess.PIPE,
        )


def ensure_one_device() -> None:
    devices = [
        line for line in adb("devices", capture=True).splitlines()[1:]
        if line.strip().endswith("\tdevice")
    ]
    if ADB_SERIAL:
        if not any(line.split()[0] == ADB_SERIAL for line in devices):
            raise SystemExit(f"Selected Android device {ADB_SERIAL} is not authorized or connected.")
        return
    if len(devices) != 1:
        raise SystemExit(f"Expected exactly one authorized device; found {len(devices)}.")


def ui_root() -> ET.Element:
    adb("shell", "uiautomator", "dump", "/sdcard/window.xml", capture=True)
    return ET.fromstring(adb("shell", "cat", "/sdcard/window.xml", capture=True))


def nodes(root: ET.Element, class_name: str | None = None) -> list[ET.Element]:
    found = list(root.iter("node"))
    if class_name:
        found = [n for n in found if n.attrib.get("class") == class_name]
    return found


def description(node: ET.Element) -> str:
    return node.attrib.get("content-desc", "").strip()


def find_desc(root: ET.Element, text: str, exact: bool = True) -> ET.Element | None:
    wanted = text.casefold()
    for node in nodes(root):
        actual = description(node).casefold()
        if (actual == wanted) if exact else (wanted in actual):
            return node
    return None


def find_label(root: ET.Element, text: str, exact: bool = True) -> ET.Element | None:
    wanted = text.casefold()
    for node in nodes(root):
        actual = (node.attrib.get("text") or description(node)).strip().casefold()
        if (actual == wanted) if exact else (wanted in actual):
            return node
    return None


def center(bounds: str) -> tuple[int, int]:
    values = [int(n) for n in re.findall(r"\d+", bounds)]
    if len(values) != 4:
        raise ValueError(f"Unexpected bounds: {bounds}")
    x1, y1, x2, y2 = values
    return (x1 + x2) // 2, (y1 + y2) // 2


def click(node: ET.Element, pause: float = 0.5) -> None:
    x, y = center(node.attrib["bounds"])
    adb("shell", "input", "tap", str(x), str(y))
    time.sleep(pause)


def tap(x: int, y: int, pause: float = 0.5) -> None:
    adb("shell", "input", "tap", str(x), str(y))
    time.sleep(pause)


def wait_for_desc(text: str, timeout: float = 15, exact: bool = True) -> tuple[ET.Element, ET.Element]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root = ui_root()
        match = find_desc(root, text, exact=exact)
        if match is not None:
            return root, match
        time.sleep(0.7)
    raise SystemExit(f'Timed out waiting for screen element "{text}". Nothing else was submitted.')


def replace_focused_text(value: str) -> None:
    if any(ord(char) < 32 for char in value):
        raise SystemExit("A field contains an unsupported control character.")
    adb("shell", "input", "keyevent", "KEYCODE_MOVE_END")
    # Android's input command accepts multiple keycodes. Sending them together
    # avoids launching 80 separate ADB processes for every field.
    adb("shell", "input", "keyevent", *("KEYCODE_DEL",) * 80)
    # Escape characters interpreted by the Android shell/input command.
    encoded = value.replace("%", "\\%").replace(" ", "%s")
    adb("shell", "input", "text", encoded)


def fill(node: ET.Element, value: str) -> None:
    click(node, pause=0.2)
    replace_focused_text(value)
    time.sleep(0.25)


def fill_current_field(index: int, value: str, expected: int, screen_name: str) -> None:
    """Re-read bounds before each tap because the soft keyboard shifts the form."""
    deadline = time.monotonic() + 15
    last_count = 0
    while time.monotonic() < deadline:
        try:
            root = ui_root()
        except (ET.ParseError, subprocess.CalledProcessError):
            time.sleep(0.5)
            continue
        fields = nodes(root, "android.widget.EditText")
        # After app launch IME state can briefly describe the previous screen.
        # Dismiss only when this form has an active editor, then reread bounds.
        if any(field.attrib.get("focused") == "true" for field in fields):
            if hide_keyboard_if_shown():
                root = ui_root()
                fields = nodes(root, "android.widget.EditText")
        last_count = len(fields)
        if len(fields) >= expected:
            click(fields[index], pause=0.7)
            # The keyboard can resize/scroll the form after the tap. Never
            # delete text until a fresh hierarchy confirms the intended focus.
            focused_fields = nodes(ui_root(), "android.widget.EditText")
            if len(focused_fields) != len(fields) or not focused_fields[index].attrib.get("focused") == "true":
                raise SystemExit(
                    f"Could not focus field {index + 1} on {screen_name}. "
                    "The keyboard or layout moved; no text was cleared. Hide the keyboard and retry."
                )
            replace_focused_text(value)
            time.sleep(0.25)
            verified = nodes(ui_root(), "android.widget.EditText")
            actual = verified[index].attrib.get("text", "") if len(verified) == len(fields) else ""
            retained = re.sub(r"\D", "", actual) == value if value.isdigit() else actual == value
            if len(verified) != len(fields) or not retained:
                raise SystemExit(f"Field {index + 1} on {screen_name} did not retain the entered value. Nothing else was submitted.")
            return
        time.sleep(0.5)
    raise SystemExit(
        f"Expected at least {expected} fields on {screen_name}; "
        f"the screen stayed at {last_count} fields for 15 seconds."
    )


def hide_keyboard() -> None:
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(0.7)


def hide_keyboard_if_shown() -> bool:
    """Read IME state before Back so a hidden keyboard cannot cause navigation.

    Samsung/Flutter can expose clipped field bounds while the IME is open;
    those bounds can miss the actual editable target even after refreshing.
    """
    state = adb("shell", "dumpsys", "input_method", capture=True)
    if re.search(r"\bmInputShown\s*=\s*true\b", state):
        hide_keyboard()
        return True
    return False


def package_installed() -> bool:
    last_error: subprocess.CalledProcessError | None = None
    for attempt in range(3):
        result = subprocess.run(
            [ADB, "shell", "pm", "path", PACKAGE],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode == 0:
            return bool(result.stdout.strip())
        # This Android build returns 1 with no message when the package simply
        # is not installed. That is a normal preflight result, not an ADB error.
        if result.returncode == 1 and not result.stdout.strip() and not result.stderr.strip():
            return False
        last_error = subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )
        time.sleep(0.7 * (attempt + 1))
    assert last_error is not None
    raise last_error


def configure_device() -> None:
    print("Setting screen timeout to 30 minutes...", flush=True)
    last_error: subprocess.CalledProcessError | None = None
    for attempt in range(3):
        try:
            adb("shell", "settings", "put", "system", "screen_off_timeout", SCREEN_TIMEOUT_MS)
            return
        except subprocess.CalledProcessError as exc:
            last_error = exc
            print(f"ADB was briefly unavailable; retrying ({attempt + 1}/3)...", flush=True)
            time.sleep(0.7 * (attempt + 1))
    assert last_error is not None
    raise last_error


def dismiss_optional_play_pass() -> None:
    """Decline only the optional paid Play Pass trial; never accept account terms."""
    try:
        root = ui_root()
    except (ET.ParseError, subprocess.CalledProcessError):
        return
    play_pass = find_label(root, "Google Play Pass", exact=False)
    not_now = find_label(root, "Not now")
    if play_pass is not None and not_now is not None and not_now.attrib.get("enabled") == "true":
        print("Declining the optional Google Play Pass trial...", flush=True)
        click(not_now, pause=1)


def ensure_app_installed() -> None:
    if package_installed():
        dismiss_optional_play_pass()
        print("Dutch Bros is already installed.", flush=True)
        return
    print("Dutch Bros is missing; opening its official Google Play listing...", flush=True)
    adb(
        "shell", "am", "start", "-a", "android.intent.action.VIEW",
        "-d", PLAY_STORE_URI, "-p", PLAY_STORE_PACKAGE,
    )
    deadline = time.monotonic() + 180
    install_pressed = False
    review_announced = False
    while time.monotonic() < deadline:
        if package_installed():
            dismiss_optional_play_pass()
            print("Dutch Bros installation verified.", flush=True)
            return
        root = ui_root()
        review = find_label(root, "Review your account", exact=False)
        if review is not None:
            if not review_announced:
                print("Google Play requires account review on the tablet.", flush=True)
                review_announced = True
            input("Complete the Google Play review manually, then press Enter here: ")
            # Account review may leave the user in Settings or another Play
            # setup page. Always return to the exact app listing afterward.
            adb(
                "shell", "am", "start", "-a", "android.intent.action.VIEW",
                "-d", PLAY_STORE_URI, "-p", PLAY_STORE_PACKAGE,
            )
            time.sleep(1)
            deadline = time.monotonic() + 180
            continue
        install = find_label(root, "Install")
        if install is not None and install.attrib.get("enabled") == "true":
            print("Starting the Google Play installation...", flush=True)
            click(install, pause=1)
            install_pressed = True
            continue
        open_button = find_label(root, "Open")
        if open_button is not None and package_installed():
            print("Dutch Bros installation verified.", flush=True)
            return
        time.sleep(1.5 if install_pressed else 0.8)
    raise SystemExit("Google Play did not finish installing Dutch Bros within 3 minutes.")


def collect_details(details_file: Path | None = None) -> dict[str, str]:
    print("Paste the details below. Put END on its own final line:\n")
    details: dict[str, str] = {}
    if details_file:
        try:
            source = details_file.read_text(encoding="utf-8").splitlines()
        finally:
            details_file.unlink(missing_ok=True)
    else:
        source = None
    lines = iter(source) if source is not None else None
    while True:
        if lines is not None:
            try:
                line = next(lines)
            except StopIteration:
                raise SystemExit("Details file ended before END.")
        else:
            try:
                line = input()
            except EOFError:
                raise SystemExit("Input ended before END.")
        if source is not None:
            print(line if line.strip().upper() == "END" else line.split(":", 1)[0] + ": [loaded]")
        if line.strip().upper() == "END":
            break
        if not line.strip():
            continue
        if ":" not in line:
            raise SystemExit(f"Invalid line (expected key: value): {line!r}")
        key, value = line.split(":", 1)
        details[key.strip().casefold()] = value.strip()
    missing = [key for key in REQUIRED if not details.get(key)]
    unknown = [key for key in details if key not in REQUIRED and key != "promo_code"]
    if missing:
        raise SystemExit("Missing fields: " + ", ".join(missing))
    if unknown:
        raise SystemExit("Unknown fields: " + ", ".join(unknown))
    validate_details(details)
    return details


def validate_details(details: dict[str, str]) -> None:
    if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{0,29}", details["first_name"]):
        raise SystemExit("first_name is invalid or longer than 30 characters.")
    if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{0,29}", details["last_name"]):
        raise SystemExit("last_name is invalid or longer than 30 characters.")
    if not re.fullmatch(r"\d{10}", details["phone"]):
        raise SystemExit("phone must contain exactly 10 digits.")
    if not re.fullmatch(r"\d{5}", details["zip_code"]):
        raise SystemExit("zip_code must contain exactly 5 digits.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", details["email"]):
        raise SystemExit("email does not look valid.")
    try:
        birthday = dt.date.fromisoformat(details["birthday"])
    except ValueError:
        raise SystemExit("birthday must be a real date in YYYY-MM-DD format.")
    today = dt.date.today()
    try:
        age_cutoff = today.replace(year=today.year - 13)
    except ValueError:
        age_cutoff = today.replace(year=today.year - 13, day=28)
    if birthday > age_cutoff:
        raise SystemExit("The app requires the account holder to be at least 13 years old.")


def require_consent() -> None:
    print("\nThe account holder must have reviewed and accepted the terms in the app.")
    if input('Type I AGREE to continue: ').strip() != "I AGREE":
        raise SystemExit("Consent was not confirmed.")


def open_signup(timeout_seconds: float = 45) -> ET.Element:
    adb("shell", "am", "force-stop", PACKAGE)
    adb("shell", "monkey", "-p", PACKAGE, "-c", "android.intent.category.LAUNCHER", "1")
    print("Waiting for Dutch Bros to finish loading...", flush=True)
    deadline = time.monotonic() + timeout_seconds
    signup_clicks = 0
    last_signup_click = 0.0
    last_package = "unknown"
    while time.monotonic() < deadline:
        try:
            root = ui_root()
        except (ET.ParseError, subprocess.CalledProcessError):
            time.sleep(0.8)
            continue
        root_node = root.find("node")
        if root_node is not None:
            last_package = root_node.attrib.get("package", last_package)
        fields = nodes(root, "android.widget.EditText")
        if len(fields) == 3:
            print("Blank signup form is ready.", flush=True)
            return root
        sign_up = find_desc(root, "SIGN UP")
        now = time.monotonic()
        if (
            sign_up is not None
            and sign_up.attrib.get("enabled") == "true"
            and now - last_signup_click >= 2.0
        ):
            if signup_clicks == 0:
                print("Opening the blank signup form...", flush=True)
            else:
                print("SIGN UP was still visible; retrying the tap...", flush=True)
            click(sign_up, pause=1)
            signup_clicks += 1
            last_signup_click = time.monotonic()
            continue
        time.sleep(0.8)
    raise SystemExit(
        "Dutch Bros did not reach the blank 3-field Sign Up form "
        f"(waited {int(timeout_seconds)} seconds; last foreground package: {last_package}). "
        "Check the phone screen and retry."
    )


def initial_signup(
    details: dict[str, str], practice: bool, launch_timeout: float = 45
) -> None:
    print("Opening the Dutch Bros signup screen...", flush=True)
    root = open_signup(timeout_seconds=launch_timeout)
    fields = nodes(root, "android.widget.EditText")
    if len(fields) != 3:
        raise SystemExit(f"Expected 3 initial fields; found {len(fields)}.")
    print("Entering first name...", flush=True)
    fill_current_field(0, details["first_name"], 3, "Sign Up")
    print("Entering last name...", flush=True)
    fill_current_field(1, details["last_name"], 3, "Sign Up")
    print("Entering phone number...", flush=True)
    fill_current_field(2, details["phone"], 3, "Sign Up")
    hide_keyboard()
    if practice:
        print("\nPractice fields filled. SEND ME A CODE was not pressed.")
        return
    root, send_code = wait_for_desc("SEND ME A CODE")
    if send_code.attrib.get("enabled") != "true":
        raise SystemExit("SEND ME A CODE is disabled; check the phone screen.")
    print("Requesting the SMS verification code...", flush=True)
    click(send_code, pause=2)


def enter_sms_code(code_file: Path | None = None) -> None:
    if code_file:
        print("Waiting for the SMS verification code in Rewards Assistant...", flush=True)
        deadline = time.monotonic() + 15 * 60
        code = ""
        while time.monotonic() < deadline:
            if code_file.exists():
                try:
                    code = code_file.read_text(encoding="utf-8").strip()
                finally:
                    code_file.unlink(missing_ok=True)
                break
            time.sleep(0.5)
        if not code:
            raise SystemExit("Timed out waiting for the SMS verification code in Rewards Assistant.")
    else:
        code = input("Enter the SMS verification code: ").strip()
    if not re.fullmatch(r"\d{4,8}", code):
        raise SystemExit("The verification code must contain 4 to 8 digits.")
    print("Entering and verifying the SMS code...", flush=True)
    root = ui_root()
    fields = nodes(root, "android.widget.EditText")
    if not fields:
        raise SystemExit("Could not find the verification-code input.")
    fill(fields[0], code)
    hide_keyboard()
    root = ui_root()
    for label in ("COMPLETE SIGN UP", "VERIFY", "CONTINUE", "SUBMIT", "NEXT"):
        button = find_desc(root, label)
        if button is not None and button.attrib.get("enabled") == "true":
            click(button, pause=2)
            break
    else:
        # Some segmented OTP controls auto-submit after the final digit.
        time.sleep(2)
    wait_for_desc("Create Your Account", timeout=20)


def android_date(iso_date: str) -> str:
    value = dt.date.fromisoformat(iso_date)
    return f"{value.month}/{value.day}/{value.year}"


def fill_account_details(details: dict[str, str]) -> None:
    print("Opening the account-details form...", flush=True)
    root, _ = wait_for_desc("Create Your Account")
    fields = nodes(root, "android.widget.EditText")
    if len(fields) < 4:
        raise SystemExit(f"Expected 4 account-detail fields; found {len(fields)}.")

    # Birthday opens a calendar. Switch to direct input and replace its default.
    print("Entering birthday...", flush=True)
    click(fields[0], pause=0.6)
    root, switch = wait_for_desc("Switch to input")
    click(switch, pause=0.4)
    root = ui_root()
    date_fields = nodes(root, "android.widget.EditText")
    if len(date_fields) != 1:
        raise SystemExit("Could not identify the birthday text input.")
    fill(date_fields[0], android_date(details["birthday"]))
    hide_keyboard()
    root, ok = wait_for_desc("OK")
    click(ok, pause=0.8)

    root, _ = wait_for_desc("Create Your Account")
    fields = nodes(root, "android.widget.EditText")
    print("Entering ZIP code...", flush=True)
    fill_current_field(1, details["zip_code"], 4, "Create Your Account")
    print("Entering and confirming email...", flush=True)
    fill_current_field(2, details["email"], 4, "Create Your Account")
    fill_current_field(3, details["email"], 4, "Create Your Account")
    if details.get("promo_code") and len(fields) > 4:
        fill_current_field(4, details["promo_code"], 5, "Create Your Account")
    hide_keyboard()

    root, agree = wait_for_desc("I AGREE, LETS GO!")
    if agree.attrib.get("enabled") != "true":
        raise SystemExit("Final agreement button is disabled; review the fields on the phone.")
    print("Submitting the completed account form...", flush=True)
    click(agree, pause=3)


def finish_onboarding_and_open_scan() -> None:
    print("Finishing onboarding and opening Scan...", flush=True)
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            root = ui_root()
        except (ET.ParseError, subprocess.CalledProcessError):
            time.sleep(0.8)
            continue
        if find_desc(root, "Dutch Pass QR Code", exact=False) is not None:
            print("\nSuccess: Dutch Pass QR screen is open.", flush=True)
            return
        scan = find_desc(root, "Scan", exact=False)
        if scan is not None:
            # Try Scan directly first. If the welcome modal makes navigation
            # non-clickable, dismiss only that blocking modal and reacquire Scan.
            if scan.attrib.get("clickable") != "true":
                dismiss = find_desc(root, "DISMISS")
                if dismiss is not None and dismiss.attrib.get("clickable") == "true":
                    print("Welcome message is blocking Scan; dismissing it...", flush=True)
                    click(dismiss, pause=1)
                    ready_deadline = time.monotonic() + 8
                    while time.monotonic() < ready_deadline:
                        root = ui_root()
                        scan = find_desc(root, "Scan", exact=False)
                        if scan is not None and scan.attrib.get("clickable") == "true":
                            break
                        time.sleep(0.5)
                    if scan is None or scan.attrib.get("clickable") != "true":
                        continue
            if scan.attrib.get("clickable") != "true":
                time.sleep(0.5)
                continue
            click(scan, pause=2)
            root = ui_root()
            if find_desc(root, "Dutch Pass QR Code", exact=False) is not None or any(
                "scan" in description(n).casefold() and n.attrib.get("selected") == "true"
                for n in nodes(root)
            ):
                print("\nSuccess: account created and Scan opened.")
                return

        skip = find_desc(root, "Skip", exact=False)
        if skip is not None:
            print("Skipping onboarding...", flush=True)
            click(skip, pause=1)
            continue

        advanced = False
        for forward_label in ("Next", "Continue", "Done", "Get Started", "Let's Go"):
            forward = find_desc(root, forward_label, exact=False)
            if forward is not None and forward.attrib.get("enabled") == "true":
                print(f"Advancing onboarding with {forward_label}...", flush=True)
                click(forward, pause=1)
                advanced = True
                break
        if advanced:
            continue

        # Onboarding's forward arrow may be unlabeled. Use only a small clickable
        # button in the right half of the screen, never a form or agreement button.
        candidates = [
            n for n in nodes(root, "android.widget.Button")
            if n.attrib.get("clickable") == "true"
            and center(n.attrib.get("bounds", "[0,0][0,0]"))[0] > 300
            and not description(n)
        ]
        if len(candidates) == 1:
            click(candidates[0], pause=1)
            continue
        time.sleep(0.8)
    raise SystemExit(
        "Could not safely finish onboarding or verify Scan within 90 seconds. "
        "Leave the current screen open and run with --finish-onboarding."
    )


def skip_onboarding_to_home() -> None:
    """Skip post-signup onboarding and stop on Home without opening Scan."""
    print("Skipping post-signup onboarding...", flush=True)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            root = ui_root()
        except (ET.ParseError, subprocess.CalledProcessError):
            time.sleep(0.7)
            continue

        # Bottom navigation means the main page has loaded. Stop immediately;
        # do not dismiss the welcome message and do not open Scan.
        if find_desc(root, "Scan", exact=False) is not None:
            print("Main page is ready.", flush=True)
            return

        skip = find_desc(root, "Skip", exact=False)
        if skip is not None and skip.attrib.get("enabled") == "true":
            click(skip, pause=0.8)
            continue

        moved = False
        for label in ("Next", "Continue", "Done", "Get Started", "Let's Go"):
            forward = find_desc(root, label, exact=False)
            if forward is not None and forward.attrib.get("enabled") == "true":
                click(forward, pause=0.8)
                moved = True
                break
        if moved:
            continue

        arrows = [
            node for node in nodes(root, "android.widget.Button")
            if node.attrib.get("clickable") == "true"
            and not description(node)
            and center(node.attrib.get("bounds", "[0,0][0,0]"))[0] > 300
        ]
        if len(arrows) == 1:
            click(arrows[0], pause=0.8)
            continue
        time.sleep(0.7)
    raise SystemExit("Account was submitted, but onboarding did not reach Home within 60 seconds.")


def archive_completed_account(details: dict[str, str], capture_scan: bool) -> Path:
    """Archive submitted details and a completion screenshot; never store an SMS code."""
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_name = re.sub(
        r"[^A-Za-z0-9_-]+", "_", f"{details['first_name']}_{details['last_name']}"
    ).strip("_") or "account"
    destination = ARCHIVE_ROOT / f"{stamp}-dutch-bros-{safe_name}"
    destination.mkdir(parents=True, exist_ok=False)

    record = {
        "app": "Dutch Bros",
        "created_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "details": {key: details[key] for key in REQUIRED},
        "sms_code_saved": False,
        "screenshot": "scan.png" if capture_scan else "completion.png",
    }

    screenshot_name = "completion.png"
    if capture_scan:
        root = ui_root()
        scan = find_desc(root, "Scan", exact=False)
        if scan is None:
            raise SystemExit(
                "The account is complete, but Scan was not found; no archive was written."
            )
        click(scan, pause=1.5)
        screenshot_name = "scan.png"

    save_device_screenshot(destination / screenshot_name)
    (destination / "account.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Saved account archive to: {destination}", flush=True)
    return destination


def offer_account_archive(details: dict[str, str]) -> None:
    print(
        "\nOptional archive: this saves the submitted personal details as plain-text JSON "
        "on this PC plus a device screenshot."
    )
    choice = input("Type SAVE, SCAN (includes the scannable rewards screen), or press Enter to skip: ").strip().upper()
    if choice not in {"SAVE", "SCAN"}:
        return
    if choice == "SCAN":
        print("The Scan screenshot can function like a loyalty credential; keep the archive private.")
    archive_completed_account(details, capture_scan=choice == "SCAN")


def ask_to_create_another() -> bool:
    print("\nThe account is complete.")
    answer = input("Type ANOTHER to create another account, or press Enter to exit: ").strip()
    if answer != "ANOTHER":
        return False
    print("Clearing only Dutch Bros local app data to start a fresh signup...", flush=True)
    adb("shell", "pm", "clear", PACKAGE)
    time.sleep(1.5)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--practice", action="store_true", help="fill fictional first-screen data only")
    parser.add_argument(
        "--resume-details",
        action="store_true",
        help="resume from the verified Create Your Account details screen",
    )
    parser.add_argument(
        "--details-file",
        type=Path,
        help="load the consented account details from a local key:value file",
    )
    parser.add_argument("--status-file", type=Path, help="mirror progress to a local JSON status file")
    parser.add_argument("--qr-file", type=Path, help="save the completed Dutch Pass screen here")
    parser.add_argument("--capture-current-qr", action="store_true", help="open Scan and capture an existing account")
    parser.add_argument(
        "--resume-current", action="store_true",
        help="inspect the current Dutch Bros screen and continue from the safest recognized step",
    )
    parser.add_argument("--sms-code-file", type=Path, help="wait for the dashboard to provide the SMS code")
    parser.add_argument("--managed-run", action="store_true", help="finish after one dashboard-managed account")
    parser.add_argument(
        "--consent-confirmed", action="store_true",
        help="the account holder already confirmed acceptance in the local dashboard",
    )
    args = parser.parse_args()
    if args.status_file:
        args.status_file.parent.mkdir(parents=True, exist_ok=True)
        sys.stdout = StatusMirror(sys.stdout, args.status_file)
        sys.stderr = StatusMirror(sys.stderr, args.status_file)
    selected_modes = sum((args.practice, args.resume_details))
    if selected_modes > 1:
        parser.error("choose only one recovery/practice option")
    ensure_one_device()
    configure_device()
    ensure_app_installed()
    if args.capture_current_qr:
        if not args.qr_file:
            parser.error("--capture-current-qr requires --qr-file")
        finish_onboarding_and_open_scan()
        save_device_screenshot(args.qr_file)
        print("Current Dutch Pass QR captured.", flush=True)
        return
    if not args.practice and not args.consent_confirmed:
        require_consent()
    details = PRACTICE.copy() if args.practice else collect_details(args.details_file)
    if args.resume_current:
        root = ui_root()
        if find_desc(root, "Scan", exact=False) is not None or find_desc(
            root, "Dutch Pass QR Code", exact=False
        ) is not None:
            print("Completed account screen detected; opening Scan and finishing capture.", flush=True)
            finish_onboarding_and_open_scan()
            if args.qr_file:
                save_device_screenshot(args.qr_file)
                print("Dutch Pass QR captured for encrypted local storage.", flush=True)
            print("\nAccount form submitted.", flush=True)
            return
        if find_desc(root, "Create Your Account") is not None:
            print("Account-details screen detected; resuming there.", flush=True)
            fill_account_details(details)
            finish_onboarding_and_open_scan() if args.qr_file else skip_onboarding_to_home()
            if args.qr_file:
                save_device_screenshot(args.qr_file)
                print("Dutch Pass QR captured for encrypted local storage.", flush=True)
            print("\nAccount form submitted.", flush=True)
            return
    if args.resume_details:
        root = ui_root()
        if find_desc(root, "Create Your Account") is None:
            raise SystemExit("The phone is not on the Create Your Account details screen.")
        fill_account_details(details)
        finish_onboarding_and_open_scan() if args.qr_file else skip_onboarding_to_home()
        if args.qr_file:
            save_device_screenshot(args.qr_file)
            print("Dutch Pass QR captured for encrypted local storage.", flush=True)
        print("\nAccount form submitted.", flush=True)
        if not args.managed_run:
            offer_account_archive(details)
        return
    launch_timeout = 45.0
    while True:
        root = ui_root()
        existing_fields = nodes(root, "android.widget.EditText")
        existing_text = " ".join(
            ((node.attrib.get("text") or "") + " " + description(node)).casefold()
            for node in nodes(root)
        )
        resume_sms = len(existing_fields) == 1 and any(
            phrase in existing_text for phrase in ("verification", "sms", "enter code", "complete sign up")
        )
        if resume_sms:
            print("Existing SMS verification screen detected; resuming there.", flush=True)
        else:
            initial_signup(details, practice=args.practice, launch_timeout=launch_timeout)
        if args.practice:
            return
        enter_sms_code(args.sms_code_file)
        fill_account_details(details)
        finish_onboarding_and_open_scan() if args.qr_file else skip_onboarding_to_home()
        if args.qr_file:
            save_device_screenshot(args.qr_file)
            print("Dutch Pass QR captured for encrypted local storage.", flush=True)
        print("\nAccount form submitted.", flush=True)
        if args.managed_run:
            return
        offer_account_archive(details)
        if not ask_to_create_another():
            return
        # Consent and details are deliberately collected again for each person.
        require_consent()
        details = collect_details()
        # A freshly cleared app can take longer to rebuild first-launch state.
        launch_timeout = 120.0


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"ADB command failed with exit code {exc.returncode}.", file=sys.stderr)
        raise SystemExit(exc.returncode)
    except SystemExit as exc:
        if isinstance(exc.code, str):
            print(exc.code, file=sys.stderr, flush=True)
        raise
    except Exception as exc:
        # Exception text/command arguments can contain personal field values.
        print(f"Dutch Bros helper failed ({type(exc).__name__}). Nothing else was submitted.", file=sys.stderr, flush=True)
        raise SystemExit(1)
