"""Session-only Taco Bell gift card entry. Never submits an order."""
import re
import subprocess
import time


def validate_gift_card(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Gift card details must include a number and PIN.")
    number = re.sub(r"[ -]", "", str(value.get("number", "")).strip())
    pin = str(value.get("pin", "")).strip()
    if not number and not pin:
        return None
    if not re.fullmatch(r"[0-9]{1,32}", number) or not re.fullmatch(r"(?:[0-9]{3}|[0-9]{8})", pin):
        raise ValueError("Enter a numeric gift card number and a 3- or 8-digit PIN.")
    return {"number": number, "pin": pin}


def gift_fields(root):
    """Match the observed labeled Compose controls, not arbitrary text fields."""
    labels = [n.attrib.get("text", "") for n in root.iter("node")]
    fields = [n for n in root.iter("node") if n.attrib.get("class") == "android.widget.EditText"]
    if ("Taco Bell Gift Card Number *" not in labels or "PIN (3 or 8 digit code) *" not in labels
            or len(fields) != 2 or any(n.attrib.get("resource-id") != "input_field" for n in fields)):
        raise ValueError("The gift card form has changed. Enter the card in the official Taco Bell app.")
    return fields


def apply_gift_card(adb, serial, card, read_ui, tap, center):
    card = validate_gift_card(card)
    if card is None:
        return ""

    def command(*args):
        # Do not expose command arguments (which may contain the card) in errors.
        try:
            subprocess.run([adb, "-s", serial, "shell", "input", *args],
                           check=True, capture_output=True, timeout=15)
        except (subprocess.SubprocessError, OSError):
            raise ValueError("Gift card entry was interrupted. Check the Taco Bell screen before retrying.") from None

    def screen():
        root = read_ui(adb, serial)
        if not any(n.attrib.get("package") == "com.tacobell.ordering" for n in root.iter("node")):
            raise ValueError("Open Taco Bell checkout on the selected Android device.")
        return root

    root = screen()
    texts = [n.attrib.get("text", "") for n in root.iter("node")]
    if "Taco Bell Gift Card Number *" not in texts:
        if "Add a Taco Bell Gift Card" not in texts:
            for attempt in range(5):
                if tap(adb, serial, text="Add a Payment Method"):
                    break
                root = screen()
                if not any(n.attrib.get("resource-id") == "checkout_screen_main" for n in root.iter("node")):
                    raise ValueError("Open checkout to add this gift card.")
                scroll = next((n for n in root.iter("node") if n.attrib.get("scrollable") == "true"), None)
                if scroll is None:
                    break
                x1, y1, x2, y2 = map(int, re.findall(r"\d+", scroll.attrib["bounds"]))
                command("swipe", str((x1+x2)//2), str(y2-60), str((x1+x2)//2), str((y1+y2)//2), "300")
            else:
                raise ValueError("Could not find Add a Payment Method. Open it in Taco Bell and retry.")
        if not tap(adb, serial, text="Add a Taco Bell Gift Card"):
            raise ValueError("Open Add a Taco Bell Gift Card in Taco Bell and retry.")
    for index, value in enumerate((card["number"], card["pin"])):
        field = gift_fields(screen())[index]
        x, y = center(field.attrib["bounds"])
        command("tap", str(x), str(y))
        command("keyevent", "KEYCODE_MOVE_END")
        command("keyevent", *(["KEYCODE_DEL"] * 64))
        command("text", value)
        command("keyevent", "KEYCODE_BACK")
    fields = gift_fields(screen())
    if re.sub(r"\s", "", fields[0].attrib.get("text", "")) != card["number"] or fields[1].attrib.get("text", "") != card["pin"]:
        raise ValueError("Gift card entry could not be verified. Check the fields in Taco Bell before continuing.")
    # Only the observed add-card action is allowed here; PLACE ORDER is never used.
    if not tap(adb, serial, text="ADD GIFT CARD"):
        raise ValueError("Card details were entered. Review and add the card in Taco Bell.")
    time.sleep(1)
    texts = [n.attrib.get("text", "") for n in screen().iter("node")]
    if "Taco Bell Gift Card Number *" in texts:
        raise ValueError("Taco Bell has not confirmed the gift card. Check its message and card details on the device.")
    return "Gift card submitted to Taco Bell. Verify the selected payment method and remaining total on the device before placing the order."
