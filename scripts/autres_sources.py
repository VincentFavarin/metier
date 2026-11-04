r"""Les offres des autres sources (Adzuna, Welcome to the Jungle), lues dans le fichier
consolidé data/sources/*.csv, mises au format des offres de data/resume.json.

Appelé par scripts/resumer.py : rien à lancer à la main. Le fichier le plus récent de
data/sources/ est lu ; ses lignes « France Travail » sont ignorées, car resumer.py prend
France Travail dans l'extraction du jour, plus fraîche.

Format du fichier (séparateur « ; », UTF-8) :
    source;id;rome;titre;entreprise;ville;departement;contrat;date;salaire;url

Ce qui est retravaillé ici :
  - département : nom (« Hauts-de-Seine ») -> code (« 92 ») ;
  - contrat : Adzuna « permanent » -> CDI, « contract » -> CDD ; l'intitulé l'emporte
    quand il dit « CDI », « CDD », « stage », « alternance » ;
  - salaire Adzuna : la période n'est pas donnée, elle est déduite du montant
    (>= 12 000 : annuel ; < 100 : horaire ; freelance entre 100 et 2 000 : tarif
    journalier, non comparable, écarté des médianes ; sinon : mensuel) ;
  - position : latitude/longitude de l'offre Adzuna (data/adzuna/), sinon la ville
    retrouvée parmi les offres déjà placées, sinon geo.api.gouv.fr (cache data/geo/villes.json),
    sinon le centre du département ;
  - doublons entre sources : même intitulé et même entreprise qu'une offre d'une autre
    source -> champ « doublon » (la source gardée), écarté par le filtre « Doublons probables ».
"""
import csv
import json
import re
import statistics
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import requests

RACINE = Path(__file__).resolve().parent.parent
DOSSIER = RACINE / "data" / "sources"
GEO = "https://geo.api.gouv.fr"

# Ordre de préférence quand une même offre est publiée sur plusieurs sources.
ORDRE_SOURCES = ["France Travail", "Adzuna", "Welcome to the Jungle"]

DEPARTEMENTS = {
    "01": "Ain", "02": "Aisne", "03": "Allier", "04": "Alpes-de-Haute-Provence", "05": "Hautes-Alpes",
    "06": "Alpes-Maritimes", "07": "Ardèche", "08": "Ardennes", "09": "Ariège", "10": "Aube", "11": "Aude",
    "12": "Aveyron", "13": "Bouches-du-Rhône", "14": "Calvados", "15": "Cantal", "16": "Charente",
    "17": "Charente-Maritime", "18": "Cher", "19": "Corrèze", "2A": "Corse-du-Sud", "2B": "Haute-Corse",
    "21": "Côte-d'Or", "22": "Côtes-d'Armor", "23": "Creuse", "24": "Dordogne", "25": "Doubs", "26": "Drôme",
    "27": "Eure", "28": "Eure-et-Loir", "29": "Finistère", "30": "Gard", "31": "Haute-Garonne", "32": "Gers",
    "33": "Gironde", "34": "Hérault", "35": "Ille-et-Vilaine", "36": "Indre", "37": "Indre-et-Loire",
    "38": "Isère", "39": "Jura", "40": "Landes", "41": "Loir-et-Cher", "42": "Loire", "43": "Haute-Loire",
    "44": "Loire-Atlantique", "45": "Loiret", "46": "Lot", "47": "Lot-et-Garonne", "48": "Lozère",
    "49": "Maine-et-Loire", "50": "Manche", "51": "Marne", "52": "Haute-Marne", "53": "Mayenne",
    "54": "Meurthe-et-Moselle", "55": "Meuse", "56": "Morbihan", "57": "Moselle", "58": "Nièvre", "59": "Nord",
    "60": "Oise", "61": "Orne", "62": "Pas-de-Calais", "63": "Puy-de-Dôme", "64": "Pyrénées-Atlantiques",
    "65": "Hautes-Pyrénées", "66": "Pyrénées-Orientales", "67": "Bas-Rhin", "68": "Haut-Rhin", "69": "Rhône",
    "70": "Haute-Saône", "71": "Saône-et-Loire", "72": "Sarthe", "73": "Savoie", "74": "Haute-Savoie",
    "75": "Paris", "76": "Seine-Maritime", "77": "Seine-et-Marne", "78": "Yvelines", "79": "Deux-Sèvres",
    "80": "Somme", "81": "Tarn", "82": "Tarn-et-Garonne", "83": "Var", "84": "Vaucluse", "85": "Vendée",
    "86": "Vienne", "87": "Haute-Vienne", "88": "Vosges", "89": "Yonne", "90": "Territoire de Belfort",
    "91": "Essonne", "92": "Hauts-de-Seine", "93": "Seine-Saint-Denis", "94": "Val-de-Marne", "95": "Val-d'Oise",
    "971": "Guadeloupe", "972": "Martinique", "973": "Guyane", "974": "La Réunion", "976": "Mayotte",
    "975": "Saint-Pierre-et-Miquelon", "977": "Saint-Barthélemy", "978": "Saint-Martin",
    "986": "Wallis-et-Futuna", "987": "Polynésie française", "988": "Nouvelle-Calédonie",
}


def norm(s):
    """'Saint-Étienne (42)' -> 'saint etienne 42' : minuscules, sans accents ni ponctuation."""
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


CODE_DEP = {norm(nom): code for code, nom in DEPARTEMENTS.items()}
CODE_DEP.update({"reunion": "974", "corse du sud": "2A", "haute corse": "2B"})


def code_departement(valeur):
    """'Hauts-de-Seine' -> '92', '92' -> '92', 'Ile-de-France' (une région) -> ''."""
    v = (valeur or "").strip()
    if re.fullmatch(r"\d{2,3}|2A|2B", v):
        return v
    return CODE_DEP.get(norm(v), "")


def norm_ville(s):
    """'92 - PUTEAUX' / 'Puteaux' / 'puteaux' -> 'puteaux' ; 'Paris 16e Arrondissement' -> 'paris'."""
    s = re.sub(r"^\s*(\d{2,3}|2A|2B)\s*-\s*", "", s or "")
    s = norm(s)
    s = re.sub(r"\b\d+\s*(e|er|eme)?\s*arrondissement\b", "", s)
    s = re.sub(r"\barrondissement\b", "", s)
    s = re.sub(r"\bst\b", "saint", s)
    s = re.sub(r"\bste\b", "sainte", s)
    s = re.sub(r"\s\d+$", "", s.strip())
    return re.sub(r"\s+", " ", s).strip()


def norm_titre(s):
    """Intitulé comparable d'une source à l'autre : sans accents, sans « H/F », sans ponctuation."""
    s = norm(s)
    s = re.sub(r"\b(h f|f h|h f x|f h x|x h f|hf|fh)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_entreprise(s):
    return re.sub(r"[^a-z0-9]", "", norm(s))


# ---------------------------------------------------------------- contrat et salaire

def contrat_et_alternance(source, contrat, titre):
    """-> (code de contrat au format France Travail, alternance ?)."""
    t = norm(titre)
    alternance = bool(re.search(r"\b(alternan\w*|apprenti\w*|apprentissage|professionnalisation)\b", t))
    if re.search(r"\b(stage|stagiaire|internship|intern)\b", t) and not alternance:
        return "STG", False
    if re.search(r"\bfreelance\b", t):
        return "LIB", False
    if re.search(r"\bcdi\b", t):
        return "CDI", alternance
    if re.search(r"\bcdd\b", t):
        return "CDD", alternance
    if re.search(r"\b(interim|interimaire)\b", t):
        return "MIS", alternance
    c = (contrat or "").lower()
    if c == "permanent":
        return "CDI", alternance
    if c == "contract":
        return "CDD", alternance
    return None, alternance


SALAIRE_MIN, SALAIRE_MAX = 4000, 250000   # même fenêtre que scripts/resumer.py


def salaire_adzuna(texte, titre):
    """'40000-45000' -> (libellé, smin, smax) en brut annuel ; la période est déduite du montant."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*", texte or "")
    if not m:
        return (texte or None), None, None
    a, b = float(m.group(1)), float(m.group(2))
    bas, haut = min(a, b), max(a, b)
    freelance = "freelance" in norm(titre)
    if bas >= 12000:
        periode, mult = "Annuel", 1
    elif freelance and 100 <= bas < 2000:
        lib = f"Journalier de {bas:.1f} Euros" + (f" à {haut:.1f} Euros" if haut > bas else "")
        return lib + " (tarif freelance, période déduite)", None, None
    elif bas < 100:
        periode, mult = "Horaire", 1607
    else:
        periode, mult = "Mensuel", 12
    lib = f"{periode} de {bas:.1f} Euros" + (f" à {haut:.1f} Euros" if haut > bas else "") + " - période déduite du montant (Adzuna)"
    vals = [v * mult for v in (bas, haut) if SALAIRE_MIN <= v * mult <= SALAIRE_MAX]
    return lib, (round(min(vals)) if vals else None), (round(max(vals)) if vals else None)


# ---------------------------------------------------------------- positions

class Villes:
    """Nom de ville -> (lat, lon, département), appris des offres déjà placées, puis geo.api.gouv.fr."""

    def __init__(self, offres_placees):
        self.fichier = RACINE / "data" / "geo" / "villes.json"
        self.cache = json.loads(self.fichier.read_text(encoding="utf-8")) if self.fichier.exists() else {}
        points = defaultdict(list)
        for nom, lat, lon, dep in offres_placees:
            k = norm_ville(nom)
            if k and lat is not None:
                points[k].append((lat, lon, dep))
        self.connues = {}
        for k, pts in points.items():
            dep = Counter(p[2] for p in pts if p[2]).most_common(1)
            self.connues[k] = (statistics.median(p[0] for p in pts), statistics.median(p[1] for p in pts),
                               dep[0][0] if dep else "")
        self.par_dep = defaultdict(list)
        for lat, lon, dep in (p for pts in points.values() for p in pts):
            if dep:
                self.par_dep[dep].append((lat, lon))
        self.appels = 0
        self.reseau = True

    def ville(self, nom):
        k = norm_ville(nom)
        if not k:
            return None
        if k in self.connues:
            return self.connues[k]
        if k in self.cache:
            return tuple(self.cache[k]) if self.cache[k] else None
        if not self.reseau:
            return None
        self.appels += 1
        time.sleep(0.05)
        try:
            r = requests.get(f"{GEO}/communes", timeout=15,
                             params={"nom": k, "fields": "centre,codeDepartement", "boost": "population", "limit": 1})
        except requests.RequestException:
            self.reseau = False          # pas de réseau : on n'insiste pas, et on ne met rien en cache
            return None
        if r.status_code != 200:
            return None
        d = r.json()
        self.cache[k] = [d[0]["centre"]["coordinates"][1], d[0]["centre"]["coordinates"][0], d[0]["codeDepartement"]] \
            if d and d[0].get("centre") else None
        return tuple(self.cache[k]) if self.cache[k] else None

    def departement(self, dep, geo):
        """Centre du département : cache de resumer.py, sinon la médiane des offres placées dans ce département."""
        p = geo.departements.get(dep)
        if p:
            return p
        pts = self.par_dep.get(dep)
        if pts:
            return statistics.median(x[0] for x in pts), statistics.median(x[1] for x in pts)
        return None

    def sauver(self):
        self.fichier.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- lecture

def fichier_le_plus_recent():
    fichiers = sorted(DOSSIER.glob("*.csv")) if DOSSIER.exists() else []
    return fichiers[-1] if fichiers else None


def lire_adzuna_brut():
    """id -> dernière version de l'offre Adzuna enregistrée par scripts/extraire_adzuna.py."""
    brut = {}
    for f in sorted((RACINE / "data" / "adzuna").glob("*/*.jsonl")):
        with f.open(encoding="utf-8") as fh:
            for ligne in fh:
                if ligne.strip():
                    v = json.loads(ligne)
                    brut[str(v["offre"].get("id"))] = v["offre"]
    return brut


def nom_source(s):
    return "Welcome to the Jungle" if s.lower().startswith("welcome") else s


def joli_slug(s):
    """'link-consulting' -> 'Link Consulting' (les entreprises WTTJ ne sont connues que par leur URL)."""
    return " ".join(w.capitalize() for w in re.split(r"[-_\s]+", s or "") if w) or None


def offres_autres_sources(offres_ft, geo, regex_outils, niveau):
    """-> (offres au format resume.json, nom du fichier lu, date du fichier)."""
    fichier = fichier_le_plus_recent()
    if not fichier:
        return [], None
    with fichier.open(encoding="utf-8-sig", newline="") as f:
        lignes = [r for r in csv.DictReader(f, delimiter=";") if nom_source(r["source"]) != "France Travail"]

    brut = lire_adzuna_brut()
    connues = [(o["lieu"], o["lat"], o["lon"], o["dep"]) for o in offres_ft if o["prec"] in ("offre", "commune")]
    for a in brut.values():
        area = (a.get("location") or {}).get("area") or []
        if len(area) >= 4 and a.get("latitude") is not None:
            connues.append((area[-1], a["latitude"], a["longitude"], code_departement(area[2])))
    villes = Villes(connues)

    offres = []
    for r in lignes:
        src = nom_source(r["source"])
        a = brut.get(r["id"]) if src == "Adzuna" else None
        titre = r["titre"].strip()
        if src == "Welcome to the Jungle":
            titre = titre[:1].upper() + titre[1:]
        entreprise = r["entreprise"].strip() or None
        if src == "Welcome to the Jungle":
            entreprise = joli_slug(entreprise)
        ville = r["ville"].strip()
        dep = code_departement(r["departement"])

        # Position : celle de l'offre, sinon la ville, sinon le département.
        lat = lon = prec = None
        if a and a.get("latitude") is not None:
            lat, lon, prec = a["latitude"], a["longitude"], "offre"
        if lat is None and ville and norm(ville) != norm(r["departement"]):
            v = villes.ville(ville)
            if v:
                lat, lon, prec = v[0], v[1], "commune"
                dep = dep or v[2]
        if lat is None and dep:
            p = villes.departement(dep, geo)
            if p:
                lat, lon, prec = p[0], p[1], "departement"

        contrat, alternance = contrat_et_alternance(src, r["contrat"], titre)
        if src == "Adzuna":
            salaire, smin, smax = salaire_adzuna(r["salaire"], titre)
        else:
            salaire, smin, smax = (r["salaire"] or None), None, None
        texte = (titre + " " + ((a or {}).get("description") or "")).lower()
        lieu = ville or r["departement"] or None
        if lieu and dep and src != "France Travail" and not lieu.startswith(dep + " "):
            lieu = f"{dep} - {lieu[:1].upper() + lieu[1:]}"
        offres.append({
            "id": r["id"] or (r["url"] or "").rstrip("/").rsplit("/", 1)[-1],
            "source": src,
            "rome": r["rome"],
            "intitule": titre,
            "entreprise": entreprise,
            "lieu": lieu,
            "dep": dep,
            "lat": round(lat, 4) if lat is not None else None,
            "lon": round(lon, 4) if lon is not None else None, "prec": prec,
            "contrat": contrat,
            "alternance": alternance,
            "salaire": salaire,
            "smin": smin, "smax": smax,
            "date": r["date"][:10],
            "url": r["url"] or None,
            "outils": [nom for nom, rx in regex_outils.items() if rx.search(texte)],
            "teletravail": "télétravail" in texte or "teletravail" in texte,
            "competences": [],
            "niveau": niveau(titre),
            "nature": "apprentissage" if alternance else ("non_salarie" if contrat == "LIB" else "autre"),
            "exp_exige": "D" if re.search(r"\b(debutant|junior)\b", norm(titre)) else None,
        })
    villes.sauver()

    # Doublons entre sources : même intitulé et même entreprise (nommée), publiés ailleurs.
    vus = {}
    toutes = sorted(list(offres_ft) + offres, key=lambda o: ORDRE_SOURCES.index(o.get("source", "France Travail")))
    for o in toutes:
        if not o.get("entreprise"):
            continue
        k = (norm_titre(o["intitule"]), norm_entreprise(o["entreprise"]))
        src = o.get("source", "France Travail")
        if k in vus and vus[k] != src:
            o["doublon"] = vus[k]
        else:
            vus.setdefault(k, src)

    # Les champs vides ne sont pas écrits : 13 000 offres de plus, c'est autant de « null » en moins
    # à télécharger. Les pages lisent un champ absent comme un champ vide.
    garder = {"id", "source", "rome", "intitule", "lat", "lon", "contrat", "niveau", "date"}
    offres = [{k: v for k, v in o.items() if k in garder or v not in (None, "", [], False)} for o in offres]

    print(f"Autres sources : {len(offres)} offres lues dans {fichier.relative_to(RACINE)} "
          f"({dict(Counter(o['source'] for o in offres))}), {villes.appels} appels geo.api.gouv.fr"
          + ("" if villes.reseau else " (réseau indisponible : positions manquantes complétées au prochain passage)"))
    print(f"Doublons entre sources : {sum(1 for o in toutes if o.get('doublon'))}")
    return offres, fichier
