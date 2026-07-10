"""Algorithme de compatibilité MentorSTAN.
Calcule un score de compatibilité (sur 100) entre un profil parrain et un profil filleul.
"""
from data import NIVEAUX

# Poids des critères (total = 100)
POIDS = {
    "niveau": 12,
    "interets_academiques": 25,
    "interets_extra": 12,
    "personnalite": 20,
    "disponibilites": 15,
    "objectifs": 8,
    "ville": 3,
    "langues": 5,
}


def _split(csv):
    if not csv:
        return set()
    return set(x.strip() for x in csv.split(",") if x.strip())


def _jaccard(set_a, set_b):
    if not set_a and not set_b:
        return 0.0
    union = set_a | set_b
    if not union:
        return 0.0
    inter = set_a & set_b
    return len(inter) / len(union)


def _score_niveau(niveau_p, niveau_f):
    if not niveau_p or not niveau_f:
        return 0.0
    if niveau_p not in NIVEAUX or niveau_f not in NIVEAUX:
        return 0.0
    i_p, i_f = NIVEAUX.index(niveau_p), NIVEAUX.index(niveau_f)
    ecart = abs(i_p - i_f)
    # Le parrain doit idéalement être d'un niveau supérieur ou égal
    if i_p < i_f:
        return 0.2  # parrain moins avancé que le filleul : peu pertinent
    if ecart == 0:
        return 0.7
    if ecart == 1:
        return 1.0
    if ecart == 2:
        return 0.6
    return 0.3


def _score_personnalite(perso_p, perso_f):
    """perso_* : chaîne '3,4,5,...' (10 valeurs de 1 à 5)."""
    try:
        vp = [int(x) for x in perso_p.split(",") if x != ""]
        vf = [int(x) for x in perso_f.split(",") if x != ""]
    except (ValueError, AttributeError):
        return 0.0
    if not vp or not vf or len(vp) != len(vf):
        return 0.0
    # distance moyenne normalisée (0 = identique, 1 = totalement opposé)
    diffs = [abs(a - b) for a, b in zip(vp, vf)]
    moyenne_diff = sum(diffs) / len(diffs)
    score = 1 - (moyenne_diff / 4)  # écart max = 4 (1 vs 5)
    return max(0.0, score)


def _score_disponibilites(jours_p, creneaux_p, jours_f, creneaux_f):
    jp, jf = _split(jours_p), _split(jours_f)
    cp, cf = _split(creneaux_p), _split(creneaux_f)
    score_jours = _jaccard(jp, jf)
    score_creneaux = _jaccard(cp, cf)
    return (score_jours + score_creneaux) / 2


def compute_score(parrain, filleul):
    """parrain, filleul : dict avec les clés user (niveau, ville_origine, langues)
    et profile (interets_academiques, interets_extra, personnalite, jours_dispo,
    creneaux_dispo, objectifs)."""

    detail = {}

    detail["niveau"] = _score_niveau(parrain["user"]["niveau"], filleul["user"]["niveau"])

    ia_p = _split(parrain["profile"]["interets_academiques"])
    ia_f = _split(filleul["profile"]["interets_academiques"])
    detail["interets_academiques"] = _jaccard(ia_p, ia_f)

    ie_p = _split(parrain["profile"]["interets_extra"])
    ie_f = _split(filleul["profile"]["interets_extra"])
    detail["interets_extra"] = _jaccard(ie_p, ie_f)

    detail["personnalite"] = _score_personnalite(
        parrain["profile"]["personnalite"], filleul["profile"]["personnalite"]
    )

    detail["disponibilites"] = _score_disponibilites(
        parrain["profile"]["jours_dispo"], parrain["profile"]["creneaux_dispo"],
        filleul["profile"]["jours_dispo"], filleul["profile"]["creneaux_dispo"],
    )

    obj_p = _split(parrain["profile"]["objectifs"])
    obj_f = _split(filleul["profile"]["objectifs"])
    detail["objectifs"] = _jaccard(obj_p, obj_f)

    ville_p = (parrain["user"]["ville_origine"] or "").strip().lower()
    ville_f = (filleul["user"]["ville_origine"] or "").strip().lower()
    detail["ville"] = 1.0 if ville_p and ville_p == ville_f else 0.0

    lg_p = _split(parrain["user"]["langues"])
    lg_f = _split(filleul["user"]["langues"])
    detail["langues"] = _jaccard(lg_p, lg_f)

    score_final = sum(detail[k] * POIDS[k] for k in POIDS)

    return round(score_final, 1), {k: round(v * 100, 1) for k, v in detail.items()}


def meilleur_parrain(filleul, parrains):
    """Retourne (parrain, score, detail) pour le meilleur parrain disponible."""
    meilleur = None
    for p in parrains:
        score, detail = compute_score(p, filleul)
        if meilleur is None or score > meilleur[1]:
            meilleur = (p, score, detail)
    return meilleur
