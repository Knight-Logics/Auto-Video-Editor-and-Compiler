import base64
import hashlib
import hmac
import json
import os
import platform
import time
import urllib.error
import urllib.request
import uuid
import webbrowser


FREE_TRIAL_USES = 20
LICENSE_PLANS = {
    "credits_5": {"label": "$5 - 5 compile credits", "credits": 5, "amount_cents": 500, "mode": "payment"},
    "credits_12": {"label": "$10 - 12 compile credits", "credits": 12, "amount_cents": 1000, "mode": "payment"},
    "monthly_unlimited": {"label": "$10/mo - unlimited compiles", "credits": None, "amount_cents": 1000, "mode": "subscription"},
}
DEFAULT_LICENSE_SERVER = "https://knightlogics.com/api/autovid-license"
LICENSE_SERVER_URL = os.environ.get("AUTOVID_LICENSE_SERVER", DEFAULT_LICENSE_SERVER).strip()
APPDATA_ROOT = os.environ.get("PROGRAMDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
RUNTIME_DIR = os.path.join(APPDATA_ROOT, "KnightLogics", "AutoVidCompiler")
STATE_PATH = os.path.join(RUNTIME_DIR, "license.json")
REQUEST_TIMEOUT_SEC = 12
OFFLINE_SUBSCRIPTION_GRACE_SECONDS = 7 * 24 * 60 * 60


def _windows_machine_guid():
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value or "")
    except Exception:
        return ""


def machine_id():
    windows_guid = _windows_machine_guid()
    if windows_guid:
        raw_parts = [
            "windows",
            windows_guid,
            str(uuid.getnode()),
            os.environ.get("PROCESSOR_IDENTIFIER", ""),
        ]
    else:
        raw_parts = [
            platform.node(),
            platform.system(),
            platform.machine(),
            os.environ.get("COMPUTERNAME", ""),
            os.environ.get("PROCESSOR_IDENTIFIER", ""),
            str(uuid.getnode()),
        ]
    raw = "|".join(part for part in raw_parts if part)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sign_payload(payload):
    key = hashlib.sha256(("KnightLogics.AutoVidCompiler.v1|" + machine_id()).encode("utf-8")).digest()
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(key, normalized, hashlib.sha256).hexdigest()


def _write_state(state):
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    state = dict(state)
    state.setdefault("version", 1)
    state.setdefault("machine_id", machine_id())
    state.setdefault("free_used", 0)
    state.setdefault("free_limit", FREE_TRIAL_USES)
    state.setdefault("credits", 0)
    state.setdefault("email", "")
    state.setdefault("license_key", "")
    state.setdefault("unlimited_active", False)
    state.setdefault("subscription_status", "")
    state.setdefault("subscription_current_period_end", 0)
    state.setdefault("updated_at", int(time.time()))
    state["updated_at"] = int(time.time())
    payload = {k: v for k, v in state.items() if k != "signature"}
    state["signature"] = _sign_payload(payload)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return state


def _new_state():
    return _write_state(
        {
            "version": 1,
            "machine_id": machine_id(),
            "free_used": 0,
            "free_limit": FREE_TRIAL_USES,
            "credits": 0,
            "email": "",
            "license_key": "",
            "unlimited_active": False,
            "subscription_status": "",
            "subscription_current_period_end": 0,
            "created_at": int(time.time()),
        }
    )


def _load_state():
    if not os.path.exists(STATE_PATH):
        return _new_state()
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        return _new_state()
    if not isinstance(state, dict):
        return _new_state()
    signature = str(state.get("signature", ""))
    payload = {k: v for k, v in state.items() if k != "signature"}
    if not hmac.compare_digest(signature, _sign_payload(payload)):
        tampered_path = STATE_PATH + ".tampered"
        try:
            if os.path.exists(tampered_path):
                os.remove(tampered_path)
            os.replace(STATE_PATH, tampered_path)
        except Exception:
            pass
        state = _new_state()
        state["free_used"] = FREE_TRIAL_USES
        return _write_state(state)
    state.setdefault("free_used", 0)
    state.setdefault("free_limit", FREE_TRIAL_USES)
    state.setdefault("credits", 0)
    state.setdefault("email", "")
    state.setdefault("license_key", "")
    state.setdefault("unlimited_active", False)
    state.setdefault("subscription_status", "")
    state.setdefault("subscription_current_period_end", 0)
    state.setdefault("machine_id", machine_id())
    return state


def _request(action, payload=None):
    if not LICENSE_SERVER_URL:
        return {"ok": False, "error": "License server is not configured."}
    body = {
        "action": action,
        "machine_id": machine_id(),
    }
    state = _load_state()
    if state.get("license_key"):
        body["license_key"] = str(state.get("license_key") or "")
    if state.get("email"):
        body["email"] = str(state.get("email") or "")
    if payload:
        body.update(payload)
    req = urllib.request.Request(
        LICENSE_SERVER_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {"ok": True}
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {}
        data.setdefault("ok", False)
        data.setdefault("error", f"License server HTTP {exc.code}.")
        return data
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _merge_remote_status(remote):
    state = _load_state()
    if remote.get("ok") or any(key in remote for key in ("free_used", "free_limit", "credits", "unlimited_active")):
        state["free_used"] = int(remote.get("free_used", state.get("free_used", 0)) or 0)
        state["free_limit"] = int(remote.get("free_limit", FREE_TRIAL_USES) or FREE_TRIAL_USES)
        state["credits"] = int(remote.get("credits", state.get("credits", 0)) or 0)
        state["email"] = str(remote.get("email", state.get("email", "")) or "")
        state["license_key"] = str(remote.get("license_key", state.get("license_key", "")) or "")
        state["unlimited_active"] = bool(remote.get("unlimited_active", state.get("unlimited_active", False)))
        state["subscription_status"] = str(remote.get("subscription_status", state.get("subscription_status", "")) or "")
        state["subscription_current_period_end"] = int(remote.get("subscription_current_period_end", state.get("subscription_current_period_end", 0)) or 0)
        state["last_remote_sync"] = int(time.time())
        _write_state(state)
    return state


def get_status(prefer_remote=True):
    if prefer_remote:
        remote = _request("status")
        if remote.get("ok"):
            state = _merge_remote_status(remote)
            state["source"] = "server"
            return state
    state = _load_state()
    state["source"] = "local"
    return state


def consume_use():
    remote = _request("consume")
    if remote.get("ok"):
        state = _merge_remote_status(remote)
        state["source"] = "server"
        state["entitlement"] = remote.get("entitlement", "")
        return True, state, ""
    if remote.get("payment_required"):
        state = _merge_remote_status(remote)
        state["source"] = "server"
        return False, state, remote.get("error", "No free uses or paid credits are available.")

    state = _load_state()
    now = int(time.time())
    if not state.get("last_remote_sync"):
        state["source"] = "local"
        return False, state, "License server is required before the first compile use can be granted."

    unlimited_active = bool(state.get("unlimited_active", False))
    last_sync = int(state.get("last_remote_sync", 0) or 0)
    period_end = int(state.get("subscription_current_period_end", 0) or 0)
    subscription_not_expired = period_end <= 0 or period_end > now
    sync_is_recent = now - last_sync <= OFFLINE_SUBSCRIPTION_GRACE_SECONDS
    if unlimited_active and subscription_not_expired and sync_is_recent:
        state["source"] = "local"
        state["entitlement"] = "monthly_unlimited"
        return True, state, "License server was unreachable; using cached monthly unlimited entitlement."

    state["source"] = "local"
    return False, state, "License server is currently unavailable. Connect to the internet and refresh your license before compiling."


def create_checkout_session(email="", plan_id="credits_5"):
    if plan_id not in LICENSE_PLANS:
        plan_id = "credits_5"
    return _request("create_checkout", {"email": str(email or "").strip(), "plan_id": plan_id})


def confirm_session(session_id):
    result = _request("confirm_session", {"session_id": str(session_id or "").strip()})
    if result.get("ok"):
        _merge_remote_status(result)
    return result


def activate_license(email="", license_key=""):
    result = _request(
        "activate_license",
        {
            "email": str(email or "").strip(),
            "license_key": str(license_key or "").strip(),
        },
    )
    if result.get("ok"):
        _merge_remote_status(result)
    return result


def recovery_summary(status=None):
    status = status or get_status(prefer_remote=False)
    email = str(status.get("email", "") or "").strip()
    license_key = str(status.get("license_key", "") or "").strip()
    if email and license_key:
        return f"Recovery email: {email} | Key: {license_key}"
    if license_key:
        return f"Recovery key: {license_key}"
    return "No recovery key saved yet. Paid plans create one after checkout confirmation."


def open_checkout_url(url):
    if not url:
        return False
    try:
        webbrowser.open(url)
        return True
    except Exception:
        return False


def status_line(status=None):
    status = status or get_status(prefer_remote=False)
    free_used = int(status.get("free_used", 0) or 0)
    free_limit = int(status.get("free_limit", FREE_TRIAL_USES) or FREE_TRIAL_USES)
    credits = int(status.get("credits", 0) or 0)
    remaining_free = max(0, free_limit - free_used)
    source = status.get("source", "local")
    if bool(status.get("unlimited_active", False)):
        return f"Trial uses left: {remaining_free}/{free_limit} | Unlimited monthly active | License source: {source}"
    return f"Trial uses left: {remaining_free}/{free_limit} | Paid credits: {credits} | License source: {source}"
