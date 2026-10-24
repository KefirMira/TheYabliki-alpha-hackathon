"""Conservative URL identity: keep path case, query order and significant bytes."""
from urllib.parse import unquote_plus, urlsplit, urlunsplit

TRACKING = {"gclid", "dclid", "fbclid", "msclkid", "yclid", "_openstat", "mc_cid", "mc_eid"}


def canonical_url(value: str) -> str:
    parts = urlsplit(value)
    host = parts.hostname.encode("idna").decode("ascii").lower()
    if ":" in host:
        host = f"[{host}]"
    if parts.port is not None:
        host += f":{parts.port}"
    query = "&".join(part for part in parts.query.split("&") if (
        not unquote_plus(part.split("=", 1)[0]).lower().startswith("utm_")
        and unquote_plus(part.split("=", 1)[0]).lower() not in TRACKING
    ))
    return urlunsplit((parts.scheme.lower(), host, parts.path, query, ""))
