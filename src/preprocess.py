"""Text cleaning shared by the training pipeline AND the API.

Anything the model is trained on must go through exactly the same steps at
prediction time, so this is the only place cleaning rules live.

Rules (each one is justified in the notebook's data section):
  1. HTML -> visible text (script/style dropped), HTML entities decoded.
  2. Header lines left inside bodies (Date:, From:, Message-ID:, X-...:) removed.
     They describe the mail system / source corpus, not phishing intent.
  3. Email addresses -> "[email]". They identify senders, recipients and the
     corpus (e.g. the Nazario mailbox owner), not intent.
  4. Years 1990-2029 -> "[year]". The corpora come from different eras
     (legitimate mail 1998-2008, Nazario phishing 2015-2020), so raw years let a
     model learn "recent = phishing".
  5. Runs of 4+ identical punctuation characters (e.g. "_____") -> 3.
  6. Whitespace collapsed (newlines kept as single line breaks).
Also: MIME encoded-words (=?utf-8?B?...?=) are decoded to readable text, lists of
addresses collapse to one "[email]", and the Nazario mailbox owner's identifiers
(monkey.org, "jose") are DELETED. That corpus is 100% phishing, so the owner's
name is a perfect label shortcut, equivalent to the receiver column we drop. It is
deleted rather than replaced by a placeholder, because a placeholder that only
ever occurs in one corpus is still a shortcut.
URLs are deliberately KEPT: links are a genuine phishing signal.
"""
from __future__ import annotations

import html
import re
import warnings
from email.header import decode_header, make_header

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

_HTML_TAG = re.compile(r"<\s*/?\s*(html|head|body|div|p|br|table|tr|td|span|font|a|img|b|i|u|center|meta|style|script)\b", re.I)
_HEADER_NAMES = (r"date|from|to|cc|bcc|subject|sender|reply[ \t-]*to|return[ \t-]*path|received"
                 r"|delivered[ \t-]*to|message[ \t-]*id|in[ \t-]*reply[ \t-]*to|references|mime[ \t-]*version"
                 r"|content[ \t-]*[a-z-]+|x[ \t]*-[ \t]*[a-z0-9-]+")
# A header line: a known header name at the start of a line (hyphens may appear as
# " - " in the pre-tokenised corpora), then ":", and at most 200 characters in total.
# The length cap matters: some corpora (SpamAssassin) lost their newlines, so a
# header can be glued to the whole body on one line. Deleting that line would
# delete the email.
_HEADER_LINE = re.compile(rf"^[ \t]*(?:{_HEADER_NAMES})[ \t]*:[^\n]{{0,200}}$", re.I | re.M)
# Also matches the pre-tokenised form "liz . bellamy @ enron . com"
_EMAIL = re.compile(r"[\w+-]+(?:\s?\.\s?[\w+-]+)*\s?@\s?[\w-]+(?:\s?\.\s?[\w-]+)+")
_EMAIL_RUN = re.compile(r"\[email\](?:[\s,;<>]+\[email\])+")
_YEAR = re.compile(r"\b(?:199\d|20[0-2]\d)\b")
_RECIPIENT = re.compile(r"\bmonkey\s?\.\s?org\b|\bjose\b", re.I)
_MIME_WORD = re.compile(r"=\?[\w-]+\?[QqBb]\?[^?\s]*\?=")
# Pre-tokenised leftovers of encoded-words, e.g. "= ? utf - 8 ? q ? ... ? ="
_MIME_TOKENISED_OPEN = re.compile(r"=\s\?\s[\w-]+(?:\s-\s\d+)?\s\?\s[qb]\s\?", re.I)
_MIME_TOKENISED_CLOSE = re.compile(r"\s\?\s=(?=\s|$)")
# "_____" and tokenised "- - - - -". "_" is listed explicitly because regex counts it as \w.
_PUNCT_RUN = re.compile(r"([^\w\s]|_)(?: ?\1){3,}")
_SPACES = re.compile(r"[ \t\f\v ]+")
_BLANK_LINES = re.compile(r"\s*\n\s*")


def html_to_text(text: str) -> str:
    if _HTML_TAG.search(text):
        soup = BeautifulSoup(text, "lxml")
        for tag in soup(["script", "style", "head"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
    return html.unescape(text)


def _decode_mime_word(m: re.Match) -> str:
    try:
        return str(make_header(decode_header(m.group())))
    except Exception:          # malformed encoding: leave it as is
        return m.group()


def decode_mime(text: str) -> str:
    text = _MIME_WORD.sub(_decode_mime_word, text)
    if _MIME_TOKENISED_OPEN.search(text):
        text = _MIME_TOKENISED_CLOSE.sub(" ", _MIME_TOKENISED_OPEN.sub(" ", text))
    return text


def clean_field(text: str | None) -> str:
    if not isinstance(text, str) or not text:
        return ""
    text = decode_mime(text)
    text = html_to_text(text)
    text = _HEADER_LINE.sub(" ", text)
    text = _EMAIL.sub("[email]", text)
    text = _EMAIL_RUN.sub("[email]", text)
    text = _RECIPIENT.sub("", text)
    text = _YEAR.sub("[year]", text)
    text = _PUNCT_RUN.sub(lambda m: m.group(1) * 3, text)
    text = _SPACES.sub(" ", text)
    text = _BLANK_LINES.sub("\n", text)
    return text.strip()


def build_text(subject: str, body: str) -> str:
    """Model input. Subject and body are already cleaned."""
    return f"{subject}\n\n{body}" if subject else body


def clean_email(subject: str | None, body: str | None) -> tuple[str, str, str]:
    """Returns (clean_subject, clean_body, model_text)."""
    s, b = clean_field(subject), clean_field(body)
    return s, b, build_text(s, b)
