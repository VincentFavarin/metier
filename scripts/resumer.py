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


def salaire_min_max(lib):
    """'Annuel de 32000.0 Euros à 38000.0 Euros' -> (32000, 38000) ; mensuel x12, horaire x1607."""
    if not lib:
        return None, None
    nombres = [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", lib)]
    l = lib.lower()
    mult = 12 if "mensuel" in l else (1607 if "horaire" in l else 1)
    vals = [n * mult for n in nombres if n * mult > 5000]   # écarte '13 mois', '35 h'…
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
    avec = [o for o in offres if o["smin"]]
    print(f"Salaire affiché par {len(avec)} offres sur {len(offres)} ({100 * len(avec) // len(offres)} %)")


if __name__ == "__main__":
    main()
