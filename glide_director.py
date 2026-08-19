from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable


DIRECTOR_VERSION = "5"

CATEGORY_TERMS: dict[str, tuple[str, ...]] = {
    "people": (
        "person", "people", "woman", "man", "face", "interview", "presenter",
        "pessoa", "mulher", "homem", "gente", "entrevista", "apresentador",
        "persona", "mujer", "hombre", "personne", "femme", "homme",
    ),
    "factory": (
        "factory", "industrial", "steel", "mill", "plant", "warehouse",
        "fabrica", "fábrica", "industria", "indústria", "acero", "usine", "werk",
    ),
    "machine": (
        "machine", "engine", "motor", "gear", "robot", "equipment",
        "maquina", "máquina", "engrenagem", "mecanismo", "maschine",
    ),
    "food": (
        "food", "recipe", "cook", "kitchen", "chocolate", "coffee",
        "comida", "receita", "cozinha", "chocolate", "cafe", "café",
        "receta", "cocina", "nourriture", "cuisine",
    ),
    "document": (
        "document", "paper", "archive", "letter", "newspaper", "patent",
        "documento", "papel", "arquivo", "carta", "jornal", "patente",
        "archivo", "documentaire", "zeitung",
    ),
    "city": (
        "city", "street", "building", "urban", "town", "road",
        "cidade", "rua", "predio", "prédio", "urbano", "estrada",
        "ciudad", "calle", "ville", "stadt",
    ),
    "nature": (
        "nature", "forest", "mountain", "river", "ocean", "tree", "animal",
        "natureza", "floresta", "montanha", "rio", "oceano", "arvore", "árvore",
        "naturaleza", "forêt", "wald",
    ),
    "vehicle": (
        "car", "truck", "train", "plane", "ship", "vehicle", "road",
        "carro", "caminhao", "caminhão", "trem", "aviao", "avião", "navio",
        "coche", "voiture", "auto", "zug",
    ),
    "money": (
        "money", "cash", "bank", "economy", "price", "market", "wealth",
        "dinheiro", "banco", "economia", "preco", "preço", "mercado",
        "dinero", "argent", "geld",
    ),
    "technology": (
        "technology", "digital", "computer", "screen", "data", "software", "cyber",
        "tecnologia", "computador", "dados", "sistema", "digital",
        "tecnología", "technologie",
    ),
}

ROLE_TERMS: dict[str, tuple[str, ...]] = {
    "conflict": (
        "problema", "crise", "falhou", "perigo", "ameaça", "ameaca", "conflito",
        "problem", "crisis", "failed", "danger", "threat", "conflict",
        "problema", "crisis", "danger", "menace",
    ),
    "reveal": (
        "segredo", "revelou", "verdade", "descobriu", "surpreendente", "ninguém esperava",
        "secret", "revealed", "truth", "discovered", "surprising", "nobody expected",
        "secreto", "verdad", "révélé", "vérité",
    ),
    "conclusion": (
        "portanto", "finalmente", "conclusão", "conclusao", "em resumo", "por fim",
        "therefore", "finally", "conclusion", "in summary",
        "finalmente", "conclusión", "en résumé", "schließlich",
    ),
    "cta": (
        "inscreva", "subscribe", "suscríbete", "suscribete", "abonnez", "подпис",
        "iscriv", "subskryb", "like", "curta", "compartilhe", "share",
    ),
}


KEYWORD_STOPWORDS = {
    "a", "ao", "aos", "as", "ate", "com", "como", "da", "das", "de", "do", "dos",
    "e", "em", "era", "essa", "esse", "esta", "este", "foi", "mais", "mas", "na",
    "nas", "no", "nos", "num", "para", "pela", "pelo", "por", "que", "se", "sem",
    "ser", "sua", "uma", "the", "and", "for", "from", "into", "that", "this",
    "with", "was", "were", "you", "your", "about", "when", "where", "what", "los",
    "las", "del", "una", "uno", "con", "dans", "avec", "des", "les", "pour", "sur",
    "der", "die", "das", "und", "mit", "ein", "della", "gli", "che", "nie", "jest",
    "dla", "oraz", "это", "как",
}


def fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", fold_text(value).strip())


def keyword_terms(value: str, *, limit: int = 18) -> list[str]:
    text = normalized_text(value)
    tokens = [
        token for token in re.findall(r"[\w]+", text, flags=re.UNICODE)
        if len(token) >= 3 and token not in KEYWORD_STOPWORDS and not token.isdigit()
    ]
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    for left, right in zip(tokens, tokens[1:]):
        if left != right:
            phrase = f"{left} {right}"
            counts[phrase] = counts.get(phrase, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (item[1], len(item[0])), reverse=True)
    return [term for term, _ in ranked[:limit]]


def categories_for_text(value: str) -> list[str]:
    text = normalized_text(value)
    scores: list[tuple[int, str]] = []
    for category, terms in CATEGORY_TERMS.items():
        score = sum(1 for term in terms if term in text)
        if score:
            scores.append((score, category))
    return [category for _, category in sorted(scores, reverse=True)]


def categories_for_path(path: Path | str) -> list[dict[str, Any]]:
    categories = categories_for_text(Path(path).stem.replace("_", " "))
    if not categories:
        return [{"name": "general", "confidence": 0.25, "source": "fallback"}]
    return [
        {"name": category, "confidence": max(0.42, 0.82 - index * 0.12), "source": "filename"}
        for index, category in enumerate(categories[:4])
    ]


def media_signature(path: Path) -> str:
    try:
        stat = path.stat()
        raw = f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
    except Exception:
        raw = str(path)
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def clip_number_hint(path: Path | str) -> int | None:
    name = Path(path).stem
    match = re.search(r"(^|[_\-\s])(\d{1,5})(?=[_\-\s]|$)", name)
    if not match:
        match = re.search(r"(\d{1,5})", name)
    if not match:
        return None
    try:
        return int(match.group(2 if match.lastindex and match.lastindex >= 2 else 1))
    except Exception:
        return None


def fingerprint_from_bytes(gray: bytes, width: int, height: int) -> str:
    if not gray or width < 9 or height < 2:
        return ""
    bits: list[str] = []
    sample_rows = 8
    sample_cols = 9
    for row in range(sample_rows):
        y = min(height - 1, int((row + 0.5) * height / sample_rows))
        values: list[int] = []
        for col in range(sample_cols):
            x = min(width - 1, int((col + 0.5) * width / sample_cols))
            values.append(gray[y * width + x])
        bits.extend("1" if values[index] > values[index + 1] else "0" for index in range(8))
    return f"{int(''.join(bits), 2):016x}"


def fingerprint_distance(left: str, right: str) -> int:
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except Exception:
        return 64


def _cue_dict(cue: Any, index: int) -> dict[str, Any]:
    if isinstance(cue, dict):
        start = float(cue.get("start") or 0.0)
        end = float(cue.get("end") or start)
        text = str(cue.get("text") or "")
    else:
        start = float(getattr(cue, "start", 0.0))
        end = float(getattr(cue, "end", start))
        text = str(getattr(cue, "text", ""))
    words = max(1, len(re.findall(r"\w+", text, flags=re.UNICODE)))
    duration = max(0.08, end - start)
    return {
        "index": index,
        "start": start,
        "end": end,
        "text": text,
        "words": words,
        "words_per_second": words / duration,
        "duration": duration,
    }


def narrative_role(text: str, position: float) -> str:
    normalized = normalized_text(text)
    for role in ("cta", "conclusion", "reveal", "conflict"):
        if any(term in normalized for term in ROLE_TERMS[role]):
            return role
    if position <= 0.12:
        return "introduction"
    if position >= 0.88:
        return "conclusion"
    return "explanation"


def build_narrative_blocks(cues: Iterable[Any], total_duration: float) -> list[dict[str, Any]]:
    cue_items = [_cue_dict(cue, index) for index, cue in enumerate(cues)]
    if not cue_items:
        return []
    blocks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for cue in cue_items:
        position = cue["start"] / max(0.1, total_duration)
        role = narrative_role(cue["text"], position)
        gap = cue["start"] - float(current["end"] if current else cue["start"])
        boundary = (
            current is None
            or role != current["role"]
            or gap >= 1.4
            or len(current["cues"]) >= 12
        )
        if boundary:
            current = {
                "index": len(blocks),
                "role": role,
                "start": cue["start"],
                "end": cue["end"],
                "cues": [],
                "text": "",
                "categories": [],
            }
            blocks.append(current)
        current["end"] = cue["end"]
        current["cues"].append(cue["index"])
        current["text"] = (current["text"] + " " + cue["text"]).strip()
    rhythm_ranges = {
        "introduction": (2.0, 3.5),
        "explanation": (3.0, 5.0),
        "conflict": (1.8, 3.2),
        "reveal": (1.5, 2.8),
        "conclusion": (3.5, 6.0),
        "cta": (3.5, 5.5),
    }
    for block in blocks:
        cues_in_block = [cue_items[index] for index in block["cues"]]
        average_speed = sum(item["words_per_second"] for item in cues_in_block) / max(1, len(cues_in_block))
        punctuation_strength = sum(
            item["text"].count(mark) for item in cues_in_block for mark in ("!", "?", ":", "...")
        )
        energy = min(1.0, max(0.0, (average_speed - 1.2) / 2.8 + punctuation_strength * 0.035))
        low, high = rhythm_ranges.get(block["role"], rhythm_ranges["explanation"])
        target = high - (high - low) * energy
        block["energy"] = round(energy, 3)
        block["shot_duration"] = round(target, 2)
        block["categories"] = categories_for_text(block["text"])
        block["keywords"] = keyword_terms(block["text"], limit=14)
        block["cue_count"] = len(block["cues"])
        block.pop("text", None)
    return blocks


def build_energy_map(cues: Iterable[Any], total_duration: float) -> dict[str, Any]:
    cue_items = [_cue_dict(cue, index) for index, cue in enumerate(cues)]
    points: list[dict[str, Any]] = []
    previous_end = 0.0
    for cue in cue_items:
        gap = max(0.0, cue["start"] - previous_end)
        punctuation = min(1.0, sum(cue["text"].count(mark) for mark in ("!", "?", ":")) * 0.22)
        speed = min(1.0, max(0.0, (cue["words_per_second"] - 1.2) / 3.0))
        strong = 1.0 if narrative_role(cue["text"], cue["start"] / max(0.1, total_duration)) in {"conflict", "reveal"} else 0.0
        energy = min(1.0, speed * 0.62 + punctuation * 0.18 + strong * 0.20)
        points.append({
            "time": round(cue["start"], 3),
            "end": round(cue["end"], 3),
            "energy": round(energy, 3),
            "pause_before": round(gap, 3),
            "words_per_second": round(cue["words_per_second"], 3),
        })
        previous_end = cue["end"]
    average = sum(item["energy"] for item in points) / max(1, len(points))
    return {"version": DIRECTOR_VERSION, "average": round(average, 3), "points": points}


def direct_timeline(
    video_items: list[dict[str, Any]],
    blocks: list[dict[str, Any]],
    *,
    recent_fingerprints: set[str] | None = None,
    preferences: list[dict[str, Any]] | None = None,
    decision_mode: str = "balanced",
) -> dict[str, Any]:
    recent = recent_fingerprints or set()
    preferences = preferences or []
    decision_mode = str(decision_mode or "balanced").strip().lower()
    if decision_mode not in {"conservative", "balanced", "aggressive"}:
        decision_mode = "balanced"
    unused = list(video_items)
    ordered: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []
    used_fingerprints: list[str] = []
    preference_bias = {
        str(item.get("preference_key") or ""): float(item.get("weight") or 0.0)
        for item in preferences
    }
    category_bias: dict[str, float] = {}
    avoid_terms: dict[str, float] = {}
    prefer_terms: dict[str, float] = {}
    for preference in preferences:
        key = str(preference.get("preference_key") or "")
        value = preference.get("value") if isinstance(preference.get("value"), dict) else {}
        weight = float(preference.get("weight") or 0.0)
        raw_categories = value.get("categories") or value.get("category") or value.get("visual_category") or []
        categories = raw_categories if isinstance(raw_categories, list) else [raw_categories]
        for category in categories:
            name = str(category or "").strip()
            if not name:
                continue
            sign = -1.0 if key.startswith(("reject", "remove", "avoid")) else 1.0
            category_bias[name] = category_bias.get(name, 0.0) + sign * min(1.2, weight)
        rel = str(value.get("rel") or value.get("path") or value.get("file") or "").strip()
        if rel:
            terms = keyword_terms(Path(rel).stem.replace("_", " "), limit=8)
            target = avoid_terms if key.startswith(("remove", "reject", "avoid")) else prefer_terms
            for term in terms:
                target[term] = target.get(term, 0.0) + min(1.0, max(0.15, abs(weight)))
    total_items = max(1, len(video_items))
    clip_numbers = [
        int(item["clip_number"])
        for item in video_items
        if isinstance(item.get("clip_number"), int)
    ]
    min_number = min(clip_numbers) if clip_numbers else None
    max_number = max(clip_numbers) if clip_numbers else None

    def item_keywords(item: dict[str, Any]) -> set[str]:
        values = {str(value) for value in (item.get("keywords") or []) if str(value).strip()}
        if values:
            return values
        return set(keyword_terms(Path(str(item.get("path") or "")).stem.replace("_", " "), limit=12))

    def score_parts(item: dict[str, Any], block: dict[str, Any]) -> dict[str, Any]:
        item_categories = {str(value) for value in item.get("categories") or []}
        block_categories = set(block.get("categories") or [])
        role = str(block.get("role") or "")
        semantic_weight = 1.0 if decision_mode == "balanced" else (0.78 if decision_mode == "conservative" else 1.28)
        order_weight = 1.0 if decision_mode == "balanced" else (1.45 if decision_mode == "conservative" else 0.72)
        semantic = len(item_categories & block_categories) * 2.4 * semantic_weight
        block_keywords = {str(value) for value in (block.get("keywords") or []) if str(value).strip()}
        matched_keywords = sorted(item_keywords(item) & block_keywords)[:8]
        keyword_score = min(2.25 if decision_mode == "aggressive" else 1.8, len(matched_keywords) * 0.45 * semantic_weight)
        if not block_categories and "general" in item_categories:
            semantic += 0.35
        block_position = min(1.0, max(0.0, float(block.get("start") or 0.0) / max(0.1, float(block.get("total_duration") or 0.0) or 1.0)))
        original_index = int(item.get("original_index") or 0)
        order_position = original_index / max(1, total_items - 1)
        if min_number is not None and max_number is not None and max_number > min_number and isinstance(item.get("clip_number"), int):
            order_position = (int(item["clip_number"]) - min_number) / max(1, max_number - min_number)
        order_distance = abs(order_position - block_position)
        order_prior = max(0.0, 1.0 - order_distance * 2.15) * 1.15 * order_weight
        local_stability = max(0.0, 1.0 - abs(order_position - original_index / max(1, total_items - 1)) * 1.8) * 0.28
        if semantic <= 0.1 and order_distance > (0.62 if decision_mode == "aggressive" else 0.48):
            order_prior -= 0.70
        media_type = str(item.get("media_type") or "video")
        image_bias = 0.0
        if media_type == "image":
            if semantic > 0.0 or keyword_score > 0.0:
                image_bias += 0.55
            else:
                image_bias -= 0.22
            if role in {"reveal", "conflict"} and (semantic > 0.0 or keyword_score > 0.0):
                image_bias += 0.22
            if role == "explanation" and not (semantic > 0.0 or keyword_score > 0.0):
                image_bias -= 0.18
        role_category_boost = 0.0
        if role == "introduction":
            role_category_boost += 0.35 if not item.get("suspect") else -0.35
        elif role == "conflict":
            if item_categories & {"machine", "factory", "vehicle", "technology", "document"}:
                role_category_boost += 0.42
        elif role == "reveal":
            if item_categories & {"document", "money", "technology", "factory"}:
                role_category_boost += 0.52
        elif role == "conclusion":
            if item_categories & {"city", "nature", "factory", "vehicle", "document"}:
                role_category_boost += 0.24
        elif role == "cta":
            role_category_boost += 0.28 if media_type == "video" and not item.get("suspect") else -0.18
        fingerprint = str(item.get("fingerprint") or "")
        repeat_penalty = 0.0
        if fingerprint and fingerprint in recent:
            repeat_penalty += 1.2
        if fingerprint and any(fingerprint_distance(fingerprint, used) <= 7 for used in used_fingerprints[-3:]):
            repeat_penalty += 2.6
        suspect_penalty = 1.5 if item.get("suspect") else 0.0
        removal_bias = preference_bias.get("remove_clip", 0.0) * (0.5 if item.get("suspect") else 0.0)
        learned_bias = sum(category_bias.get(category, 0.0) for category in item_categories)
        item_terms = item_keywords(item)
        learned_bias += sum(prefer_terms.get(term, 0.0) for term in item_terms) * 0.18
        learned_bias -= sum(avoid_terms.get(term, 0.0) for term in item_terms) * 0.22
        role_boost = 0.0
        if role in {"introduction", "conclusion"}:
            role_boost += order_prior * 0.35
        total = semantic + keyword_score + order_prior + local_stability + role_boost + role_category_boost + learned_bias + image_bias - repeat_penalty - suspect_penalty - removal_bias
        return {
            "score": total,
            "semantic": semantic,
            "keyword_score": keyword_score,
            "order_prior": order_prior,
            "local_stability": local_stability,
            "role_category_boost": role_category_boost,
            "repeat_penalty": repeat_penalty,
            "suspect_penalty": suspect_penalty,
            "learned_bias": learned_bias,
            "image_bias": image_bias,
            "matched_categories": sorted(item_categories & block_categories),
            "matched_keywords": matched_keywords,
            "order_distance": order_distance,
        }

    def score_item(item: dict[str, Any], block: dict[str, Any]) -> float:
        return float(score_parts(item, block)["score"])

    def explain_choice(item: dict[str, Any], block: dict[str, Any], parts: dict[str, Any]) -> str:
        reasons: list[str] = []
        if parts.get("matched_keywords"):
            reasons.append("palavras: " + ", ".join(parts["matched_keywords"][:4]))
        if parts.get("matched_categories"):
            reasons.append("categoria: " + ", ".join(parts["matched_categories"][:3]))
        if float(parts.get("order_prior") or 0.0) >= 0.55:
            reasons.append("ordem/numero combina com este trecho")
        if item.get("suspect"):
            reasons.append("usado com penalidade visual")
        if item.get("media_type") == "image":
            reasons.append("imagem encaixada no bloco")
        if float(parts.get("role_category_boost") or 0.0) >= 0.25:
            reasons.append("funcao visual combina com a cena")
        if abs(float(parts.get("learned_bias") or 0.0)) >= 0.2:
            reasons.append("preferencia local do canal")
        return "; ".join(reasons) or "melhor pontuacao local para o bloco"

    for block in blocks or [{"index": 0, "role": "explanation", "categories": [], "shot_duration": 4.0}]:
        if not unused:
            break
        details = {id(item): score_parts(item, block) for item in unused}
        scores = {item_id: float(parts["score"]) for item_id, parts in details.items()}
        candidates = list(unused)
        if decision_mode == "conservative" and len(candidates) > 4:
            local_candidates = [
                item for item in candidates
                if float(details[id(item)].get("order_distance") or 0.0) <= 0.26
                or float(details[id(item)].get("semantic") or 0.0) >= 2.0
                or float(details[id(item)].get("keyword_score") or 0.0) >= 0.9
            ]
            if local_candidates:
                candidates = local_candidates
        ranked = sorted(candidates, key=lambda item: scores[id(item)], reverse=True)
        take = max(1, min(len(ranked), int(max(1.0, (float(block.get("end") or 0) - float(block.get("start") or 0)) / max(1.2, float(block.get("shot_duration") or 4.0))))))
        selected = ranked[:take]
        selected_ids = {id(item) for item in selected}
        for item in selected:
            ordered.append(item)
            if item.get("fingerprint"):
                used_fingerprints.append(str(item["fingerprint"]))
            assignments.append({
                "block": block.get("index"),
                "role": block.get("role"),
                "path": item.get("path"),
                "categories": item.get("categories") or [],
                "score": round(scores[id(item)], 3),
                "confidence": round(max(0.35, min(0.96, 0.52 + max(0.0, scores[id(item)]) / 8.0)), 3),
                "reason": explain_choice(item, block, details[id(item)]),
                "matched_keywords": details[id(item)].get("matched_keywords") or [],
                "matched_categories": details[id(item)].get("matched_categories") or [],
                "clip_number": item.get("clip_number"),
                "original_index": item.get("original_index"),
                "media_type": item.get("media_type") or "video",
                "visual_category": item.get("visual_category") or "",
                "suspect": bool(item.get("suspect")),
            })
        unused = [item for item in unused if id(item) not in selected_ids]
    ordered.extend(unused)
    return {
        "version": DIRECTOR_VERSION,
        "order": [str(item.get("path") or "") for item in ordered],
        "assignments": assignments,
        "blocks": blocks,
        "decision_mode": decision_mode,
        "reordered": [item.get("path") for item in ordered] != [item.get("path") for item in video_items],
        "anti_repeat": {
            "recent_matches": sum(1 for item in video_items if item.get("fingerprint") in recent),
            "unique_fingerprints": len({item.get("fingerprint") for item in ordered if item.get("fingerprint")}),
        },
    }


def confidence_summary(
    *,
    media_total: int,
    media_valid: int,
    subtitle_count: int,
    audio_ok: bool,
    coverage_ratio: float,
    technical_risk: float,
) -> dict[str, Any]:
    media = 100.0 * media_valid / max(1, media_total)
    synchronization = 98.0 if subtitle_count > 0 and audio_ok else (65.0 if audio_ok else 30.0)
    coverage = max(0.0, min(100.0, coverage_ratio * 100.0))
    audio = 92.0 if audio_ok else 35.0
    reliability = max(0.0, min(100.0, 100.0 - technical_risk * 100.0))
    overall = media * 0.25 + synchronization * 0.20 + coverage * 0.25 + audio * 0.20 + reliability * 0.10
    risks: list[str] = []
    actions: list[dict[str, str]] = []
    if media < 75:
        risks.append("Muitos clipes invalidos ou suspeitos.")
        actions.append({
            "area": "media",
            "label": "Executar Auto-Fix",
            "detail": "Remover clipes invalidos e revisar os suspeitos antes do render.",
        })
    if coverage < 70:
        risks.append("Cobertura visual limitada para a duracao da narracao.")
        actions.append({
            "area": "visual_coverage",
            "label": "Adicionar cobertura visual",
            "detail": "Importe mais clipes ou permita fallback visual no final da timeline.",
        })
    if audio < 70:
        risks.append("Narracao ausente ou com leitura instavel.")
        actions.append({
            "area": "audio",
            "label": "Revisar narracao",
            "detail": "Confirme a faixa principal e mantenha voz nivelada e recuperacao ativas.",
        })
    if reliability < 75:
        risks.append("Risco tecnico elevado para este conjunto de midias.")
        actions.append({
            "area": "technical_reliability",
            "label": "Manter recuperacao automatica",
            "detail": "O Glide podera trocar encoder ou ignorar apenas o clipe defeituoso.",
        })
    return {
        "overall": round(overall),
        "media": round(media),
        "synchronization": round(synchronization),
        "visual_coverage": round(coverage),
        "audio": round(audio),
        "technical_reliability": round(reliability),
        "risk": "baixo" if overall >= 80 else ("medio" if overall >= 60 else "alto"),
        "informational_only": True,
        "risks": risks,
        "actions": actions,
    }
