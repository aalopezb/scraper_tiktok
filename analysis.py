import re
import statistics
from collections import Counter
 
SPAM_RE = re.compile(
    r"(https?://|www\.|\.com\b|follow\s*(me|back)|\bf4f\b|\bl4l\b|\bsub4sub\b|"
    r"s[ií]gueme|sigueme|s[ií]ganme|seguime|check\s*(my|out)|link\s*in\s*bio|"
    r"link\s*en\s*(mi\s*)?bio|dm\s*me|whatsapp|telegram|ganar\s*dinero|gratis|promo)",
    re.I,
)
 
POSITIVE = {
    "love", "amazing", "great", "best", "awesome", "good", "nice", "beautiful",
    "funny", "lol", "amo", "genial", "increible", "increíble", "excelente",
    "mejor", "bueno", "buenisimo", "buenísimo", "hermoso", "hermosa", "bonito",
    "gracioso", "jaja", "jajaja", "felicidades", "crack", "top", "wow",
    "perfecto", "encanta", "gracias",
}
NEGATIVE = {
    "hate", "bad", "worst", "ugly", "trash", "fake", "scam", "boring", "cringe",
    "odio", "malo", "peor", "feo", "basura", "falso", "estafa", "aburrido",
    "asco", "pesimo", "pésimo", "horrible",
}
 
 
def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))
 
 
def _wavg(parts):
    """Promedio ponderado ignorando las senales sin dato (None)."""
    valid = [(s, w) for s, w in parts if s is not None]
    total = sum(w for _, w in valid)
    if total == 0:
        return None
    return sum(s * w for s, w in valid) / total
 
 
def analyze_comments(comments: list[dict]) -> dict:
    texts = [(c.get("texto") or "").strip() for c in comments]
    texts = [t for t in texts if t]
    n = len(texts)
    if n == 0:
        return {"n": 0}
    norm = [re.sub(r"\s+", " ", t.lower()) for t in texts]
    pos = neg = 0
    for t in texts:
        words = set(re.findall(r"\w+", t.lower()))
        p, q = len(words & POSITIVE), len(words & NEGATIVE)
        if p > q:
            pos += 1
        elif q > p:
            neg += 1
    return {
        "n": n,
        "unicos_pct": round(len(set(norm)) / n * 100, 1),
        "spam_pct": round(sum(1 for t in texts if SPAM_RE.search(t)) / n * 100, 1),
        "solo_emoji_pct": round(
            sum(1 for t in texts if not any(ch.isalnum() for ch in t)) / n * 100, 1
        ),
        "largo_promedio": round(statistics.mean(len(t) for t in texts), 1),
        "sentimiento": round((pos - neg) / n, 2),  # -1 (negativo) .. 1 (positivo)
    }
 
 
def score_video(v: dict, followers: int) -> dict:
    plays = v.get("reproducciones") or 0
    likes = v.get("me_gustas") or 0
    com = v.get("comentarios") or 0
    sh = v.get("compartidos") or 0
    sv = v.get("guardados") or 0
    alerts: list[str] = []
 
    inter = likes + com + sh + sv
    er = inter / plays if plays else 0.0
    like_rate = likes / plays if plays else 0.0
    c2l = com / likes if likes else None
    reach = plays / followers if followers else None
    ca = analyze_comments(v.get("comentarios_muestra") or [])
 
    # ---------- VALOR ----------
    er_s = _clamp(er / 0.10 * 100)
    reach_s = _clamp(reach * 100) if reach is not None else None
    conv_s = _clamp(((com + sh) / plays) / 0.01 * 100) if plays else 0.0
    sent_s = (ca["sentimiento"] + 1) / 2 * 100 if ca["n"] else None
    valor = _wavg([(er_s, 0.40), (reach_s, 0.20), (conv_s, 0.25), (sent_s, 0.15)])
 
    # ---------- VERACIDAD ----------
    if like_rate <= 0.20:
        ratio_s = 100.0
    elif like_rate <= 0.45:
        ratio_s = 100 - (like_rate - 0.20) / 0.25 * 60
    else:
        ratio_s = 10.0
    if like_rate > 0.30:
        alerts.append("Proporción de me gustas/vistas inusualmente alta")
 
    if c2l is None or likes < 50:
        c2l_s = None  # pocos datos para opinar
    else:
        c2l_s = 20 + 80 * _clamp((c2l - 0.0005) / (0.008 - 0.0005), 0, 1)
        if c2l < 0.001:
            alerts.append("Muy pocos comentarios para la cantidad de me gustas")
 
    quality = None
    if ca["n"] >= 3:
        quality = (
            0.5 * ca["unicos_pct"]
            + 0.3 * (100 - ca["spam_pct"])
            + 0.2 * (100 - min(100, ca["solo_emoji_pct"] * 1.5))
        )
        if ca["spam_pct"] >= 30:
            alerts.append(f"{ca['spam_pct']:.0f}% de los comentarios muestreados parecen spam o promoción")
        if ca["unicos_pct"] < 70:
            alerts.append("Muchos comentarios repetidos en la muestra")
    elif ca["n"] == 0 and com > 0:
        alerts.append("No se pudo leer la muestra de comentarios")
 
    veracidad = _wavg([(ratio_s, 0.35), (c2l_s, 0.30), (quality, 0.35)])
    if veracidad is None:
        veracidad = 50.0
        alerts.append("Datos insuficientes para evaluar veracidad")
 
    return {
        "valor": round(valor if valor is not None else 0.0, 1),
        "veracidad": round(veracidad, 1),
        "alertas": alerts,
        "analisis_comentarios": ca,
        "metricas": {
            "tasa_interaccion": round(er * 100, 2),
            "me_gustas_por_vista": round(like_rate * 100, 2),
            "comentarios_por_me_gusta": round(c2l * 100, 3) if c2l is not None else None,
            "alcance_vs_seguidores": round(reach * 100, 1) if reach is not None else None,
        },
    }
 
 
def _label_valor(s: float) -> str:
    return "Alto" if s >= 70 else "Medio" if s >= 40 else "Bajo"
 
 
def _label_veracidad(s: float) -> str:
    return "Alta" if s >= 75 else "Media" if s >= 50 else "Baja"
 
 
def analyze(data: dict) -> dict:
    """Recibe la salida de tiktok_videos.get_recent_videos y agrega puntajes."""
    perfil = data.get("perfil") or {}
    followers = perfil.get("seguidores") or 0
    videos = [{**v, **score_video(v, followers)} for v in data.get("videos", [])]
 
    if videos:
        valor = round(statistics.mean(v["valor"] for v in videos), 1)
        veracidad = round(statistics.mean(v["veracidad"] for v in videos), 1)
    else:
        valor = veracidad = 0.0
 
    counter = Counter(a for v in videos for a in v["alertas"])
    alertas = [
        f"{a} (en {c} de {len(videos)} videos)" for a, c in counter.items() if c >= 2
    ]
 
    plays = [v["reproducciones"] for v in videos]
    if len(plays) >= 3 and statistics.mean(plays) > 0:
        cv = statistics.pstdev(plays) / statistics.mean(plays)
        if cv > 1.5:
            alertas.append("Rendimiento muy desigual entre videos (puede ser un video viral aislado)")
 
    return {
        "perfil": perfil,
        "cuenta": {
            "valor": valor,
            "veracidad": veracidad,
            "etiqueta_valor": _label_valor(valor),
            "etiqueta_veracidad": _label_veracidad(veracidad),
            "videos_analizados": len(videos),
            "alertas": alertas,
        },
        "videos": videos,
    }
 