"""Load an email file into (subject, body).

.eml : parsed with the standard library. Body = text/plain part if present,
       otherwise text/html (the API strips HTML).
.txt : if the first line starts with "Subject:", it is the subject; the rest is the body.
"""
from __future__ import annotations

import email
import email.policy
from email.message import EmailMessage
from pathlib import Path


def _part_text(part: EmailMessage) -> str:
    try:
        return part.get_content()
    except (LookupError, UnicodeDecodeError):      # unknown or wrong charset
        payload = part.get_payload(decode=True) or b""
        return payload.decode("utf-8", errors="replace")


def load_eml(data: bytes) -> tuple[str, str]:
    msg = email.message_from_bytes(data, policy=email.policy.default)
    subject = str(msg.get("subject", "") or "")
    part = msg.get_body(preferencelist=("plain", "html"))
    body = _part_text(part) if part is not None else ""
    return subject.strip(), body.strip()


def load_txt(text: str) -> tuple[str, str]:
    first, _, rest = text.partition("\n")
    if first.lower().startswith("subject:"):
        return first[len("subject:"):].strip(), rest.strip()
    return "", text.strip()


def load_email(path: str | Path) -> tuple[str, str]:
    path = Path(path)
    data = path.read_bytes()
    if path.suffix.lower() == ".eml":
        return load_eml(data)
    return load_txt(data.decode("utf-8-sig", errors="replace").replace("\r\n", "\n"))
