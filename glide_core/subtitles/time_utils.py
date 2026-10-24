from __future__ import annotations

import re


def srt_time_to_seconds(value: str) -> float:
    """Converte timestamp SRT 'HH:MM:SS,mmm' em segundos decimais."""
    match = re.match(r"\s*(\d+):(\d{2}):(\d{2})[,.](\d{1,3})\s*", value)
    if not match:
        raise ValueError(f"Tempo SRT invalido: {value!r}")
    hours, minutes, seconds, millis = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis.ljust(3, "0")) / 1000


def seconds_to_ass_time(value: float) -> str:
    """Converte segundos decimais em formato de tempo ASS 'H:MM:SS.cc'."""
    value = max(0.0, value)
    centis = int(round(value * 100))
    hours = centis // 360000
    centis %= 360000
    minutes = centis // 6000
    centis %= 6000
    seconds = centis // 100
    centis %= 100
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centis:02d}"


def ass_escape(text: str) -> str:
    """Escapa caracteres para formato de legenda ASS seguro."""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("{", "(").replace("}", ")")
    parts = [re.sub(r"\s+", " ", part).strip() for part in str(text).split("\n")]
    return "\\N".join(part.replace("\\", "\\\\") for part in parts if part)


def ass_color(value: str | None, default: str, alpha: str = "00") -> str:
    """Converte hex RGB (#RRGGBB) para formato ASS &HAABBGGRR."""
    raw = (value or default).strip()
    if raw.startswith("#"):
        raw = raw[1:]
    if len(raw) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", raw):
        raw = default.lstrip("#")
    r, g, b = raw[0:2], raw[2:4], raw[4:6]
    return f"&H{alpha.upper()}{b.upper()}{g.upper()}{r.upper()}"
