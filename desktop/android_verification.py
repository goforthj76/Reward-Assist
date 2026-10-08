"""Enter a user-supplied code only on the recognized Taco Bell verification screen."""
import re
import subprocess
import time


def verify_android_code(adb, serial, code, read_ui, tap, center, target):
    if not re.fullmatch(r"[0-9]{4,8}", code):
        raise ValueError("Enter the 4–8 digit Android verification code from your email.")
    package = "com.tacobell.ordering"
    root = read_ui(adb, serial)
    nodes = [n for n in root.iter("node") if n.get("package") == package]
    texts = {n.get("text", "") for n in nodes}
    fields = [n for n in nodes if n.get("class") == "android.widget.EditText"]
    if not {"Verify Your Email", "Code", "VERIFY"}.issubset(texts) or len(fields) != 1 or fields[0].get("resource-id") != "input_field":
        raise ValueError("Android is not on Taco Bell’s email-code screen. No code was entered.")
    def entry(*args):
        try:
            subprocess.run(target(adb, serial, "shell", "input", *args), check=True,
                           capture_output=True, timeout=15)
        except (subprocess.SubprocessError, OSError):
            raise ValueError("Code entry was interrupted. Check the Android connection and retry.") from None
    x, y = center(fields[0].get("bounds", ""))
    entry("tap", str(x), str(y))
    entry("keyevent", "KEYCODE_MOVE_END")
    entry("keyevent", *(["KEYCODE_DEL"] * 32))
    entry("text", code)
    root = read_ui(adb, serial)
    if not any(n.get("package") == package and n.get("resource-id") == "input_field"
               and n.get("text") == code for n in root.iter("node")):
        raise ValueError("Could not confirm code entry. VERIFY was not pressed.")
    entry("keyevent", "KEYCODE_BACK")
    if not tap(adb, serial, text="VERIFY"):
        raise ValueError("Could not find VERIFY. Retry when the verification screen is visible.")
    for _ in range(6):
        time.sleep(2)
        root = read_ui(adb, serial)
        texts = {n.get("text", "") for n in root.iter("node") if n.get("package") == package}
        if any(re.search(r"invalid|expired|incorrect|try again", text, re.I) for text in texts):
            raise ValueError("Taco Bell did not accept the code. Paste the latest email code and retry.")
        if "Verify Your Email" not in texts and "Free Welcome Reward" in texts:
            return {"ok": True, "stage": "signed_in", "message": "Android verification finished. Preparing this person’s order…"}
    return {"ok": True, "stage": "verification_unconfirmed", "message": "Code submitted, but sign-in could not be confirmed. If Android is signed in, use the continue button; otherwise retry with the latest code."}
