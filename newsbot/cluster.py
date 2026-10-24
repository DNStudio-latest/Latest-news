"""Group items describing the same development (TF-IDF cosine, no ML deps)."""
from __future__ import annotations

import math
import re
from collections import Counter

from .models import Cluster, Item

STOPWORDS = set(
    """a an the and or but if of to in on at for from by with about into over after before under
    is are was were be been being has have had do does did will would can could should may might
    this that these those it its as than then there here what which who whom whose how why when
    new says said say report reports reported live update updates latest news breaking video watch
    he she they them his her their we our you your i me my not no yes up out off more most all
    just now today year years day days week amid vs via""".split()
)
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'\-]+")


def tokens(text: str) -> list[str]:
    out = []
    for tok in _TOKEN_RE.findall(text.lower()):
        tok = tok.strip("'-")
        if tok.endswith("'s"):
            tok = tok[:-2]
        if len(tok) > 4 and tok.endswith("s") and not tok.endswith("ss"):
            tok = tok[:-1]
        if len(tok) > 1 and tok not in STOPWORDS:
            out.append(tok)
    return out


def item_terms(item: Item) -> Counter:
    # Titles carry most of the signal; the summary adds a little context.
    terms = Counter({t: 3 for t in tokens(item.title)})
    terms.update(tokens(" ".join(item.summary.split()[:40])))
    return terms


def _vector(terms: Counter, idf: dict[str, float]) -> dict[str, float]:
    vec = {t: c * idf.get(t, 1.0) for t, c in terms.items()}
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {t: v / norm for t, v in vec.items()}


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(t, 0.0) for t, v in a.items())


def build_idf(docs: list[Counter]) -> dict[str, float]:
    df: Counter = Counter()
    for d in docs:
        df.update(d.keys())
    n = len(docs) or 1
    return {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}


def cluster_items(items: list[Item], threshold: float) -> list[Cluster]:
    """Greedy single pass: attach each item to the most similar cluster centroid."""
    terms = [item_terms(i) for i in items]
    idf = build_idf(terms)
    vectors = [_vector(t, idf) for t in terms]

    # News first so clusters are seeded by real headlines rather than posts.
    order = sorted(range(len(items)), key=lambda k: (not items[k].is_news, -items[k].score))
    clusters: list[Cluster] = []
    centroids: list[Counter] = []
    for k in order:
        best, best_sim = None, threshold
        for c, centroid in enumerate(centroids):
            sim = cosine(vectors[k], _vector(centroid, idf))
            if sim >= best_sim:
                best, best_sim = c, sim
        if best is None:
            clusters.append(Cluster([items[k]]))
            centroids.append(Counter(terms[k]))
        else:
            clusters[best].items.append(items[k])
            centroids[best].update(terms[k])
    clusters.sort(key=lambda c: c.weight, reverse=True)
    return clusters


def signature(text: str) -> list[str]:
    """Compact term list stored with each article for cross-run de-duplication."""
    return [t for t, _ in Counter(tokens(text)).most_common(25)]


def signature_similarity(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / math.sqrt(len(sa) * len(sb))
