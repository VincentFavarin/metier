r"""Lit les offres actives du jour (data/actives/<date>.csv), retrouve leur dernière version dans
data/brut, et écrit data/resume.json : le fichier que la page index.html affiche.

Usage :
    .venv\Scripts\python.exe scripts\resumer.py

C'est ici que la donnée brute est retravaillée :
  - salaire : libellé texte -> minimum et maximum annuels bruts ;
  - outils cités dans l'intitulé + la description (grille OUTILS, à adapter à votre métier) ;
  - position sur la carte : latitude/longitude de l'API quand elle les donne, sinon le centre
    de la commune (geo.api.gouv.fr, mis en cache dans data/geo/), sinon la ville principale
    du département ; les offres « France » n'ont pas de point.
  - niveau de poste déduit de l'intitulé (assistant / chargé / responsable / directeur / autre),
    nature du contrat (apprentissage, professionnalisation, salarié, non salarié) et libellés
    lisibles des codes de contrat (clé « contrats » du résumé).
  - exigences : exp_exige, exp_ans (années, 0 = débutant accepté), qualification, formation
    (niveau le plus élevé demandé), secteur, temps (plein/partiel), postes.
La page recalcule ensuite tous les comptages côté navigateur, selon les métiers cochés.
"""
import csv
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "scripts"))
from extraire import METIERS  # noqa: E402  (la liste des métiers vit dans un seul fichier)

# Les outils et compétences que l'on cherche dans les annonces : c'est VOTRE grille, adaptez-la.
# Chaque entrée : libellé affiché -> variantes cherchées (mot entier, insensible à la casse).
OUTILS = {
    "SEO": ["seo", "référencement naturel"],
    "SEA / Google Ads": ["sea", "google ads", "adwords"],
    "Meta Ads": ["meta ads", "facebook ads", "instagram ads"],
    "Google Analytics": ["google analytics", "ga4", "analytics"],
    "HubSpot": ["hubspot"],
    "CRM / Salesforce": ["crm", "salesforce"],
    "Emailing": ["emailing", "e-mailing", "newsletter", "mailchimp", "brevo", "sendinblue"],
    "Réseaux sociaux": ["réseaux sociaux", "social media", "community management"],
    "LinkedIn": ["linkedin"],
    "WordPress": ["wordpress"],
    "Shopify / e-commerce": ["shopify", "prestashop", "e-commerce", "ecommerce"],
    "Canva": ["canva"],
    "Suite Adobe": ["photoshop", "illustrator", "indesign", "adobe"],
    "Excel": ["excel"],
    "Power BI / Looker": ["power bi", "looker", "data studio"],
    "SQL / Python": ["sql", "python"],
    "Marketing automation": ["automation", "automatisation", "zapier", "make", "n8n"],
    "IA générative": ["ia", "intelligence artificielle", "chatgpt", "ia générative", "genai", "llm"],
    "Anglais": ["anglais", "english"],
}
REGEX_OUTILS = {nom: re.compile(r"(?<![\w-])(" + "|".join(re.escape(v) for v in variantes) + r")(?![\w-])")
                for nom, variantes in OUTILS.items()}

GEO = "https://geo.api.gouv.fr"

# Niveau du poste, lu dans l'intitulé : l'ordre compte (un « directeur marketing » n'est pas
# un « chargé »). Première expression qui correspond, en minuscules.
NIVEAUX = [
    ("directeur", r"directeur|directrice|\bhead of\b|\bcdo\b|\bcmo\b|\bvp\b"),
    ("responsable", r"responsable|manager|\bchef|\bcheffe|\blead\b|\bhead\b"),
    ("assistant", r"assistant|alternan|apprenti|stagiaire|\bstage\b|junior"),
    ("charge", r"charg[ée]|consultant|analyste|analyst|spécialiste|specialist|traffic|community"
                r"|expert|technicien|conseiller|animateur|référenceur|rédacteur|designer"
                r"|développeur|business developer|ingénieur|gestionnaire|coordinateur|superviseur"),
]
REGEX_NIVEAUX = [(cle, re.compile(motif, re.IGNORECASE)) for cle, motif in NIVEAUX]
NIVEAUX_LIBELLES = [
    ["assistant", "Assistant·e / junior"],
    ["charge", "Chargé·e"],
    ["responsable", "Responsable"],
    ["directeur", "Directeur·rice"],
    ["autre", "Autre"],
]

# Codes de type de contrat de l'API -> libellé court lisible par un étudiant.
CONTRATS = {
    "CDI": "CDI",
    "CDD": "CDD",
    "MIS": "Intérim",
    "SAI": "Saisonnier",
    "FRA": "Franchise",
    "LIB": "Profession libérale",
    "CCE": "Profession commerciale",
    "DDI": "CDI de chantier",
    "DIN": "CDI intérimaire",
    "TTI": "Intérim",
    "CDS": "CDD senior",
    "REP": "Reprise d'entreprise",
}

NATURES = [
    ("apprentissage", "apprentissage"),
    ("professionnalisation", "professionnalisation"),
    ("non salarié", "non_salarie"),
    ("contrat travail", "salarie"),
]

# Niveau de formation demandé : du plus faible au plus élevé (l'ordre sert aussi à l'affichage).
FORMATIONS = ["< Bac", "Bac", "Bac+2", "Bac+3/4", "Bac+5"]


def niveau(intitule):
    """'Directeur marketing' -> 'directeur' ; 'Chargé de com' -> 'charge' ; sinon 'autre'."""
    t = intitule or ""
    for cle, rx in REGEX_NIVEAUX:
        if rx.search(t):
            return cle
    return "autre"


def contrat_libelle(code):
    """Code de contrat de l'API -> libellé court ; les codes inconnus restent identifiables."""
    return CONTRATS.get(code) or f"Autre ({code})"


def nature(o):
    """natureContrat -> 'apprentissage' | 'professionnalisation' | 'salarie' | 'non_salarie' | 'autre'."""
    lib = (o.get("natureContrat") or "").lower()
    if not lib:
        return "autre"
    for motif, cle in NATURES:
        if motif in lib:
            return cle
    return "autre"


def exp_ans(lib):
    """'Débutant accepté'/'0 An(s)' -> 0, '6 Mois' -> 0.5, '5 An(s)' -> 5, 'Expérience exigée' -> None."""
    l = (lib or "").lower()
    if not l:
        return None
    if "débutant" in l or "debutant" in l:
        return 0
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(an|mois)", l)
    if not m:
        return None
    n = float(m.group(1).replace(",", "."))
    n = n if m.group(2) == "an" else n / 12
    return int(n) if n == int(n) else round(n, 2)


def formation(o):
    """Niveau de formation le plus élevé demandé par l'offre, ou None si rien n'est indiqué."""
    meilleur = None
    for f in o.get("formations") or []:
        l = (f.get("niveauLibelle") or "").lower()
        if not l:
            continue
        if "bac+5" in l or "bac + 5" in l:
            n = "Bac+5"
        elif "bac+3" in l or "bac+4" in l or "bac + 3" in l or "bac + 4" in l:
            n = "Bac+3/4"
        elif "bac+2" in l or "bac + 2" in l:
            n = "Bac+2"
        elif "bac" in l:
            n = "Bac"
        else:
            n = "< Bac"
        if meilleur is None or FORMATIONS.index(n) > FORMATIONS.index(meilleur):
            meilleur = n
    return meilleur


def temps_travail(o):
    """'Temps plein' -> 'plein', 'Temps partiel' -> 'partiel', sinon None."""
    l = (o.get("dureeTravailLibelleConverti") or "").lower()
    return "plein" if "plein" in l else ("partiel" if "partiel" in l else None)


# En-tête normalisé des libellés de salaire de France Travail :
# « Annuel de 32000.0 Euros à 38000.0 Euros », « Mensuel de 486.0 Euros sur 12 mois »,
# « Horaire de 12.31 Euros - 13ème mois + primes »…
MOTIF_SALAIRE = re.compile(
    r"^(annuel|mensuel|horaire)\s+de\s+(\d+(?:[.,]\d+)?)\s*euros"
    r"(?:\s*à\s*(\d+(?:[.,]\d+)?)\s*euros)?",
    re.IGNORECASE,
)
MULTIPLICATEUR = {"annuel": 1, "mensuel": 12, "horaire": 1607}
# Fenêtre de vraisemblance, en brut annuel. En dessous : l'employeur a saisi des
# milliers d'euros dans la case « annuel » (« Annuel de 32.0 Euros à 38.0 Euros »).
# Au dessus : il a saisi un salaire annuel dans la case « mensuel ». Le plancher
# laisse passer les apprentis (27 % du SMIC = 5 832 € par an).
SALAIRE_MIN, SALAIRE_MAX = 4000, 250000


def salaire_min_max(lib):
    """'Annuel de 32000.0 Euros à 38000.0 Euros' -> (32000, 38000) ; mensuel x12, horaire x1607.

    On ne lit que cet en-tête : le commentaire libre qui suit un « - » répète ou
    brouille les chiffres (« De 30 à 35 k€ par an », « 13ème mois », « 35h hebdo »),
    et « sur 12 mois » n'est pas un montant. Lire tous les nombres du libellé
    obligeait à écarter les petites valeurs, ce qui effaçait les vrais salaires
    d'apprenti (486 €/mois = 27 % du SMIC).
    """
    if not lib:
        return None, None
    m = MOTIF_SALAIRE.match(lib.strip())
    if not m:
        return None, None
    mult = MULTIPLICATEUR[m.group(1).lower()]
    vals = [float(x.replace(",", ".")) * mult for x in (m.group(2), m.group(3)) if x]
    vals = [v for v in vals if SALAIRE_MIN <= v <= SALAIRE_MAX]
    return (round(min(vals)), round(max(vals))) if vals else (None, None)


def departement(lieu):
    cp = lieu.get("codePostal") or ""
    if cp[:2].isdigit() and cp != "99999":
        return "2A" if cp[:2] == "20" and cp < "20200" else ("2B" if cp[:2] == "20" else cp[:2])
    m = re.match(r"\s*(\d{2}|2A|2B)\s*-", lieu.get("libelle") or "")
    return m.group(1) if m else ""


class Geocodeur:
    """Centre des communes et villes principales des départements, via geo.api.gouv.fr, avec cache."""

    def __init__(self):
        self.dossier = RACINE / "data" / "geo"
        self.dossier.mkdir(parents=True, exist_ok=True)
        self.communes = self._lire("communes.json")
        self.departements = self._lire("departements.json")
        self.appels = 0

    def _lire(self, nom):
        f = self.dossier / nom
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}

    def _get(self, url):
        self.appels += 1
        time.sleep(0.05)
        try:
            r = requests.get(url, timeout=15)
            return r.json() if r.status_code == 200 else None
        except requests.RequestException:
            return None

    def commune(self, code):
        if code not in self.communes:
            d = self._get(f"{GEO}/communes/{code}?fields=centre")
            self.communes[code] = d["centre"]["coordinates"][::-1] if d and d.get("centre") else None
        return self.communes[code]

    def departement(self, code):
        if code not in self.departements:
            d = self._get(f"{GEO}/communes?codeDepartement={code}&fields=centre&boost=population&limit=1")
            self.departements[code] = d[0]["centre"]["coordinates"][::-1] if d else None
        return self.departements[code]

    def position(self, lieu):
        """(lat, lon, précision) ; précision = 'offre', 'commune', 'departement' ou None."""
        if lieu.get("latitude") and lieu.get("longitude"):
            return lieu["latitude"], lieu["longitude"], "offre"
        if lieu.get("commune"):
            p = self.commune(lieu["commune"])
            if p:
                return p[0], p[1], "commune"
        dep = departement(lieu)
        if dep:
            p = self.departement(dep)
            if p:
                return p[0], p[1], "departement"
        return None, None, None

    def sauver(self):
        (self.dossier / "communes.json").write_text(json.dumps(self.communes), encoding="utf-8")
        (self.dossier / "departements.json").write_text(json.dumps(self.departements), encoding="utf-8")


def main():
    jours = sorted((RACINE / "data" / "actives").glob("*.csv"))
    if not jours:
        raise SystemExit("Aucune extraction : lancez d'abord scripts/extraire.py")
    jour = jours[-1].stem
    with jours[-1].open(encoding="utf-8") as f:
        actives = [(r["rome"], r["id"]) for r in csv.DictReader(f)]
    ids_actifs = {i for _, i in actives}

    # Dernière version connue de chaque offre active (les fichiers sont lus dans l'ordre des mois).
    versions = {}
    for f in sorted((RACINE / "data" / "brut").glob("*/*.jsonl")):
        with f.open(encoding="utf-8") as fh:
            for ligne in fh:
                if ligne.strip():
                    v = json.loads(ligne)
                    if v["id"] in ids_actifs:
                        versions[v["id"]] = v
    nb_versions = sum(1 for f in (RACINE / "data" / "brut").glob("*/*.jsonl")
                      for l in f.open(encoding="utf-8") if l.strip())

    geo = Geocodeur()
    offres = []
    for rome, oid in actives:
        v = versions.get(oid)
        if not v:
            continue
        o = v["offre"]
        lieu = o.get("lieuTravail") or {}
        texte = (o.get("intitule") or "") + " " + (o.get("description") or "")
        t = texte.lower()
        smin, smax = salaire_min_max((o.get("salaire") or {}).get("libelle"))
        lat, lon, precision = geo.position(lieu)
        offres.append({
            "id": oid,
            "rome": rome,
            "intitule": o.get("intitule"),
            "entreprise": (o.get("entreprise") or {}).get("nom"),
            "lieu": lieu.get("libelle"),
            "dep": departement(lieu),
            "lat": lat, "lon": lon, "prec": precision,
            "contrat": o.get("typeContrat"),
            "experience": o.get("experienceLibelle"),
            "alternance": bool(o.get("alternance")),
            "salaire": (o.get("salaire") or {}).get("libelle"),
            "smin": smin, "smax": smax,
            "date": (o.get("dateCreation") or "")[:10],
            "vu_le": v["vu_le"],
            "url": (o.get("origineOffre") or {}).get("urlOrigine"),
            "outils": [nom for nom, rx in REGEX_OUTILS.items() if rx.search(t)],
            "teletravail": "télétravail" in t,
            "competences": [c.get("libelle") for c in o.get("competences") or [] if c.get("libelle")],
            "niveau": niveau(o.get("intitule")),
            "nature": nature(o),
            "exp_exige": o.get("experienceExige") or None,
            "exp_ans": exp_ans(o.get("experienceLibelle")),
            "qualification": o.get("qualificationLibelle") or None,
            "formation": formation(o),
            "secteur": o.get("secteurActiviteLibelle") or None,
            "temps": temps_travail(o),
            "postes": int(o.get("nombrePostes") or 1),
        })
    geo.sauver()

    # Série : par jour et par métier
    serie = defaultdict(dict)
    with (RACINE / "data" / "serie.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            serie[r["date"]][r["rome"]] = int(r["total"])

    resume = {
        "date": jour,
        "source": "France Travail — API Offres d'emploi v2",
        "requete": "une requête codeROME par métier, France entière",
        "metiers": [{"code": c, "libelle": l, "groupe": g, "coche": k,
                     "actives": sum(1 for o in offres if o["rome"] == c)}
                    for c, (l, g, k) in METIERS.items()],
        "outils": list(OUTILS),
        "contrats": {c: contrat_libelle(c)
                     for c in sorted({o["contrat"] for o in offres if o["contrat"]})},
        "niveaux": NIVEAUX_LIBELLES,
        "formations": FORMATIONS,
        "versions_conservees": nb_versions,
        "sans_position": sum(1 for o in offres if o["lat"] is None),
        "serie": [{"date": d, "par_metier": m} for d, m in sorted(serie.items())],
        "offres": offres,
    }
    sortie = RACINE / "data" / "resume.json"
    sortie.write_text(json.dumps(resume, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    prec = defaultdict(int)
    for o in offres:
        prec[o["prec"]] += 1
    print(f"Écrit : {sortie.relative_to(RACINE)} — {len(offres)} offres actives du {jour}, "
          f"{sortie.stat().st_size // 1024} Ko")
    print(f"Positions : {dict(prec)} ({geo.appels} appels geo.api.gouv.fr)")
    avec = [o for o in offres if o["smin"] is not None]
    part = 100 * len(avec) // len(offres) if offres else 0
    print(f"Salaire affiché par {len(avec)} offres sur {len(offres)} ({part} %)")


if __name__ == "__main__":
    main()
