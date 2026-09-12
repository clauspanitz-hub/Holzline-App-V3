"""Hex-Werte aus deutschen Farbnamen (Erstzuweisung, überschreibbar im Katalog)."""

from __future__ import annotations

import re
import unicodedata

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

def normalize_hex(value: str | None) -> str | None:
    """Leer → None; sonst #RRGGBB in Großbuchstaben. Ungültig → ValueError."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if not text.startswith("#"):
        text = f"#{text}"
    if len(text) == 4 and all(ch in "0123456789abcdefABCDEF" for ch in text[1:]):
        text = f"#{text[1] * 2}{text[2] * 2}{text[3] * 2}"
    if not _HEX_RE.match(text):
        raise ValueError("Hex muss #RRGGBB sein")
    return text.upper()


_EXACT: dict[str, str] = {
    "rosa": "#E8A0B8",
    "altrosa": "#C4838A",
    "pink": "#E85A9B",
    "rot": "#C23B3B",
    "blau": "#3B6FC2",
    "bootsblau": "#1E3A6E",
    "gelb": "#E0C040",
    "salbei": "#7A9A72",
    "weiss": "#F4F1EA",
    "weiß": "#F4F1EA",
    "beige": "#D9C7A3",
    "creme": "#F0E6C8",
    "taupe": "#8B7E70",
    "flieder": "#9B7BB8",
    "gruen": "#4F8F4A",
    "grün": "#4F8F4A",
    "grau": "#8A9096",
    "graublau": "#6A7B8A",
    "ahorn": "#E8D4A8",
    "buche": "#D4A574",
    "eiche": "#C4A35A",
    "nussbaum": "#5C3317",
    "orange": "#E07A3A",
    "lila": "#7B4FA0",
    "violett": "#6B3FA0",
    "tuerkis": "#3AA8A4",
    "türkis": "#3AA8A4",
    "mint": "#8FCBB1",
    "schwarz": "#2A2A2A",
    "natur": "#D2B48C",
    "gold": "#C4A35A",
    "silber": "#C0C4C8",
}


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKC", name or "").strip().lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = re.sub(r"[\s_\-]+", "", s)
    return s


def _mix(hex_color: str, toward: str, ratio: float) -> str:
    def parts(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    a, b = parts(hex_color), parts(toward)
    rgb = tuple(int(a[i] * (1 - ratio) + b[i] * ratio) for i in range(3))
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def hex_for_color_name(name: str) -> str | None:
    key = _norm(name)
    if not key:
        return None
    if key in _EXACT:
        return _EXACT[key]
    shade = None
    base = key
    if base.endswith("dunkel"):
        shade = "dunkel"
        base = base[: -len("dunkel")]
    elif base.endswith("hell"):
        shade = "hell"
        base = base[: -len("hell")]
    if base.startswith("dunkel") and shade is None:
        shade = "dunkel"
        base = base[len("dunkel") :]
    elif base.startswith("hell") and shade is None:
        shade = "hell"
        base = base[len("hell") :]
    if base.startswith("alt") and base[3:] in _EXACT:
        return _mix(_EXACT[base[3:]], "#5C4033", 0.28)
    found = _EXACT.get(base)
    if not found:
        for token, hex_value in _EXACT.items():
            if token in key and token not in ("alt",):
                found = hex_value
                break
    if not found:
        return None
    if shade == "dunkel":
        return _mix(found, "#1A1A1A", 0.38)
    if shade == "hell":
        return _mix(found, "#FFFFFF", 0.42)
    return found
