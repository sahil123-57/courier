import hashlib
import hmac


def _sig(name, secret):
    return hmac.new(secret.encode(), name.encode(), hashlib.sha256).hexdigest()[:24]


def make_token(name, secret):
    return f"{name}.{_sig(name, secret)}"


def read_token(token, secret):
    name, _, sig = (token or "").rpartition(".")
    if not name or not hmac.compare_digest(sig, _sig(name, secret)):
        return None
    return name
