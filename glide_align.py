"""Alinhamento de callouts do SRT à narração real (palavras com tempo do whisper.cpp).

Os SRT de callouts são gerados a partir do roteiro e não do áudio: no projeto analisado
o texto chegava a aparecer ~100 s antes da fala no fim do vídeo (o SRT assumia uma
locução ~5% mais rápida). Aqui cada grupo de callouts é ancorado à fala que o repete.

1. Candidatos fortes: janelas da transcrição com >=2 palavras-chave do callout (ou um
   número raro), com peso IDF.
2. Cadeia monótona (programação dinâmica): as âncoras têm de estar pela mesma ordem no SRT
   e na fala, com declive local plausível. Isto rejeita coincidências soltas.
3. Grupos sem âncora são interpolados entre as âncoras vizinhas.
Callouts encadeados (mesma frase partida em linhas) movem-se juntos.
"""
from __future__ import annotations

import bisect
import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

STOPWORDS = set(
    # en
    "the a an of to and or in on for is are was were be been this that it its with as at by from but not "
    "into than then there their they he she we you i his her our your will would can could has have had "
    # pt
    "o os um uma uns umas de do da dos das e ou em no na nos nas por para com que se ao aos à às é são foi "
    "ser mais mas como seu sua seus suas isso este esta esse essa ele ela eles elas não já também "
    # es
    "el la los las un una unos unas del al y o en por para con que se es son fue ser más pero como su sus "
    "este esta ese esa él ella ellos ellas no ya también lo le les".split()
)
NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
    "nine": "9", "ten": "10", "um": "1", "dois": "2", "tres": "3", "quatro": "4", "cinco": "5", "seis": "6",
    "sete": "7", "oito": "8", "nove": "9", "dez": "10", "uno": "1", "dos": "2", "cuatro": "4", "siete": "7",
    "ocho": "8", "nueve": "9", "diez": "10",
}
ABBREVIATIONS = {"kw": "kilowatt", "pm": "permanent", "km": "kilometro", "kg": "kilo"}
SPLIT_RE = re.compile(r"[\s\-:—–•→,~≈+%$()/|;!?¿¡\"“”'’]+")


def norm_token(token: str) -> str:
    token = unicodedata.normalize("NFKD", str(token).lower())
    token = "".join(ch for ch in token if not unicodedata.combining(ch))
    token = re.sub(r"[^a-z0-9]", "", token)
    token = NUMBER_WORDS.get(token, token)
    return ABBREVIATIONS.get(token, token)


def stem(token: str) -> str:
    return token if token.isdigit() else token[:5]


def keywords(text: str) -> list[str]:
    out = []
    for raw in SPLIT_RE.split(str(text or "")):
        tok = norm_token(raw)
        if tok and tok not in STOPWORDS:
            out.append(stem(tok))
    return out


def load_whisper_json(path: Path | str) -> list[tuple[float, str]]:
    """Palavras (início em s, radical normalizado) do JSON do whisper-cli com -ml 1 -oj."""
    data = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    words: list[tuple[float, str]] = []
    for seg in data.get("transcription") or []:
        start = float((seg.get("offsets") or {}).get("from") or 0) / 1000.0
        for raw in re.split(r"[\s\-]+", str(seg.get("text") or "")):
            tok = norm_token(raw)
            if tok:
                words.append((start, stem(tok)))
    return words


def _groups(cues: list[tuple[float, float, str]], gap: float = 0.6, max_lines: int = 4, max_span: float = 12.0) -> list[list[int]]:
    """Linhas contíguas da mesma frase (callout partido em linhas) formam um grupo.
    Limitado a 4 linhas / 12 s para que legendas contínuas não virem um único bloco."""
    groups: list[list[int]] = []
    for idx, cue in enumerate(cues):
        if groups:
            group = groups[-1]
            prev = cues[group[-1]]
            if cue[0] - prev[1] <= gap and len(group) < max_lines and cue[1] - cues[group[0]][0] <= max_span:
                group.append(idx)
                continue
        groups.append([idx])
    return groups


def _candidates(text: str, words: list[tuple[float, str]], df: dict[str, int]) -> list[tuple[float, float]]:
    keys = keywords(text)
    if not keys:
        return []
    kset = set(keys)
    weight = {k: 1.0 / math.log(2 + df.get(k, 0)) for k in kset}
    total = sum(weight.values())
    span = len(keys) + 4
    out = []
    for i, (t, w) in enumerate(words):
        if w not in kset:
            continue
        found = {x for _, x in words[i:i + span]} & kset
        rare_number = any(k.isdigit() and len(k) >= 2 and df.get(k, 0) <= 3 for k in found)
        if len(found) >= 2 or rare_number:
            out.append((t, sum(weight[k] for k in found) / total))
    return out


def align_callouts(
    cues: Iterable[tuple[float, float, str]],
    words: list[tuple[float, str]],
    min_score: float = 0.5,
) -> tuple[list[tuple[float, float]], dict[str, Any]]:
    """Devolve (novos (início, fim) por cue, resumo). Sem âncoras suficientes, não mexe."""
    cues = [(float(a), float(b), str(c)) for a, b, c in cues]
    stats: dict[str, Any] = {"cues": len(cues), "anchored": 0, "interpolated": 0, "applied": False}
    if len(cues) < 2 or len(words) < 20:
        return [(a, b) for a, b, _ in cues], stats
    df: dict[str, int] = {}
    for _, w in words:
        df[w] = df.get(w, 0) + 1
    groups = _groups(cues)
    nodes: list[tuple[float, float, float, int]] = []  # (t_srt, t_fala, score, grupo)
    for gi, group in enumerate(groups):
        for ci in group:
            for t, score in _candidates(cues[ci][2], words, df):
                if score >= min_score:
                    nodes.append((cues[ci][0], t, score, gi))
    if not nodes:
        return [(a, b) for a, b, _ in cues], stats
    nodes.sort()
    best = [n[2] for n in nodes]
    prev = [-1] * len(nodes)
    for j, (sj, tj, scj, gj) in enumerate(nodes):
        for i in range(j):
            si, ti, _sci, gi = nodes[i]
            if gi >= gj or ti >= tj or sj <= si:
                continue
            ds, dt = sj - si, tj - ti
            if not (0.75 <= dt / ds <= 1.35) and abs(dt - ds) > 6.0:
                continue
            if best[i] + scj > best[j]:
                best[j] = best[i] + scj
                prev[j] = i
    j = max(range(len(nodes)), key=lambda k: best[k])
    chain = []
    while j >= 0:
        chain.append(nodes[j])
        j = prev[j]
    chain.reverse()
    # Exige uma cadeia com substância: pelo menos 3 âncoras ou 15% dos grupos.
    if len(chain) < max(3, int(0.15 * len(groups))):
        stats["reason"] = "âncoras insuficientes"
        return [(a, b) for a, b, _ in cues], stats
    anchor_by_group = {n[3]: n for n in chain}
    xs = [n[0] for n in chain]
    ys = [n[1] for n in chain]

    def mapped(t: float) -> float:
        k = bisect.bisect_left(xs, t)
        if k == 0:
            return t + (ys[0] - xs[0])
        if k >= len(xs):
            return t + (ys[-1] - xs[-1])
        x0, x1, y0, y1 = xs[k - 1], xs[k], ys[k - 1], ys[k]
        return y0 + (t - x0) * (y1 - y0) / (x1 - x0)

    anchored_groups = sorted(anchor_by_group)
    new = [(a, b) for a, b, _ in cues]
    deltas = []
    for gi, group in enumerate(groups):
        if gi in anchor_by_group:
            anchor = anchor_by_group[gi]
            delta = anchor[1] - anchor[0]
            stats["anchored"] += len(group)
        else:
            pred = mapped(cues[group[0]][0])
            delta = pred - cues[group[0]][0]
            # Refinamento local: procura a frase perto da previsão, sempre entre as âncoras
            # vizinhas (a ordem da cadeia nunca é quebrada).
            k = bisect.bisect_left(anchored_groups, gi)
            lo = anchor_by_group[anchored_groups[k - 1]][1] + 0.3 if k > 0 else 0.0
            hi = anchor_by_group[anchored_groups[k]][1] - 0.3 if k < len(anchored_groups) else float("inf")
            best_local = None
            for ci in group:
                offset_in_group = cues[ci][0] - cues[group[0]][0]
                for t, score in _candidates(cues[ci][2], words, df):
                    start_guess = t - offset_in_group
                    if score < min_score or not (lo <= t <= hi) or abs(start_guess - pred) > 20.0:
                        continue
                    key = (score, -abs(start_guess - pred))
                    if best_local is None or key > best_local[0]:
                        best_local = (key, start_guess)
            if best_local is not None:
                delta = best_local[1] - cues[group[0]][0]
                stats["refined"] = int(stats.get("refined") or 0) + len(group)
            stats["interpolated"] += len(group)
        deltas.append(delta)
        for ci in group:
            a, b, text = cues[ci]
            start = a + delta
            # Ajuste fino por linha: a própria frase dita a <=1,5 s da posição do grupo.
            local = [(score, -abs(t - start), t) for t, score in _candidates(text, words, df)
                     if score >= min_score and abs(t - start) <= 1.5]
            if local:
                start = max(local)[2]
                stats["line_snapped"] = int(stats.get("line_snapped") or 0) + 1
            new[ci] = (max(0.0, start), max(0.0, start + (b - a)))
    # Ordem e sem sobreposição: cada cue termina antes do seguinte começar.
    for i in range(len(new) - 1):
        a, b = new[i]
        nxt = new[i + 1][0]
        if nxt < a + 0.4:
            nxt = a + 0.4
            new[i + 1] = (nxt, max(nxt + 0.4, new[i + 1][1]))
        if b > nxt - 0.04:
            new[i] = (a, max(a + 0.4, nxt - 0.04))
    stats.update({
        "applied": True,
        "anchors": len(chain),
        "groups": len(groups),
        "median_shift_s": round(sorted(deltas)[len(deltas) // 2], 2),
        "max_shift_s": round(max(abs(d) for d in deltas), 2),
    })
    return new, stats
