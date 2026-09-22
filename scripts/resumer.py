r"""Lit la dernière extraction de la veille (data/brut/offres_M1718_<date>.json) et écrit
data/resume.json, le fichier que la page index.html affiche.

Usage :
    .venv\Scripts\python.exe scripts\resumer.py

C'est ici que la donnée brute est retravaillée : salaire (libellé texte -> minimum et maximum
annuels), outils cités dans la description (liste de mots à adapter à votre métier), comptages.
"""
import csv
import json
import re
import statistics
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CODE_ROME = "M1718"

# Les outils et compétences que l'on cherche dans les annonces : c'est VOTRE grille, adaptez-la.
# Chaque entrée : libellé affiché -> variantes cherchées (mot entier, insensible à la casse).
OUTILS = {
    "SEO": ["seo", "référencement naturel"],
    "SEA / Google Ads": ["sea", "google ads", "adwords"],
    "Meta Ads": ["meta ads", "facebook ads", "instagram ads"],
    "Google Analytics": ["google analytics", "ga4", "analytics"],
    "HubSpot": ["hubspot"],
    "CRM": ["crm", "salesforce"],
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


def cherche(texte, variantes):
    t = texte.lower()
    return any(re.search(r"(?<![\w-])" + re.escape(v) + r"(?![\w-])", t) for v in variantes)


def salaire_min_max(lib):
    """'Annuel de 32000.0 Euros à 38000.0 Euros' -> (32000, 38000) ; mensuel x12, horaire x1607."""
    if not lib:
        return None, None
    nombres = [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", lib)]
    l = lib.lower()
    mult = 12 if "mensuel" in l else (1607 if "horaire" in l else 1)
    vals = [n * mult for n in nombres if n * mult > 5000]   # écarte '13 mois', '35 h'…
    return (min(vals), max(vals)) if vals else (None, None)


def main():
    fichiers = sorted((RACINE / "data" / "brut").glob(f"offres_{CODE_ROME}_*.json"))
    if not fichiers:
        raise SystemExit("Aucune extraction : lancez d'abord scripts/extraire.py")
    d = json.loads(fichiers[-1].read_text(encoding="utf-8"))
    offres = d["offres"]
    n = len(offres)

    # Salaires
    mins, maxs = [], []
    for o in offres:
        smin, smax = salaire_min_max((o.get("salaire") or {}).get("libelle"))
        if smin:
            mins.append(smin); maxs.append(smax)

    # Outils cités dans intitulé + description
    outils = Counter()
    for o in offres:
        texte = (o.get("intitule") or "") + " " + (o.get("description") or "")
        for nom, variantes in OUTILS.items():
            if cherche(texte, variantes):
                outils[nom] += 1

    # Compétences telles que France Travail les code
    competences = Counter(c.get("libelle") for o in offres for c in o.get("competences") or [] if c.get("libelle"))

    def dep(o):
        lieu = o.get("lieuTravail") or {}
        cp = lieu.get("codePostal") or ""
        if cp[:2].isdigit():
            return cp[:2]
        m = re.match(r"\s*(\d{2})\s*-", lieu.get("libelle") or "")
        return m.group(1) if m else "?"

    departements = Counter(dep(o) for o in offres)
    contrats = Counter(o.get("typeContrat") or "?" for o in offres)
    entreprises = Counter((o.get("entreprise") or {}).get("nom") or "(non communiquée)" for o in offres)
    experience = Counter(o.get("experienceLibelle") or "?" for o in offres)
    teletravail = sum(1 for o in offres if "télétravail" in (o.get("description") or "").lower())

    # Série : une ligne par extraction de la même requête
    serie = []
    with (RACINE / "data" / "serie.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["rome"] == CODE_ROME and not r["departement"]:
                serie.append({"date": r["date"], "total": int(r["total"])})

    resume = {
        "metier": "Chargé / Chargée de marketing digital",
        "rome": CODE_ROME,
        "requete": d["requete"],
        "date": d["date"],
        "source": "France Travail — API Offres d'emploi v2",
        "total_api": d["total"],
        "recuperees": n,
        "puy_de_dome": departements.get("63", 0),
        "auvergne_rhone_alpes": sum(departements.get(x, 0) for x in
                                    ["01", "03", "07", "15", "26", "38", "42", "43", "63", "69", "73", "74"]),
        "teletravail_mentionne": teletravail,
        "salaire": {
            "offres_affichant": len(mins),
            "part_affichant": round(100 * len(mins) / n) if n else 0,
            "min_median": round(statistics.median(mins)) if mins else None,
            "max_median": round(statistics.median(maxs)) if maxs else None,
            "min_bas": round(min(mins)) if mins else None,
            "max_haut": round(max(maxs)) if maxs else None,
        },
        "contrats": contrats.most_common(),
        "experience": experience.most_common(5),
        "departements": departements.most_common(12),
        "outils": [{"nom": k, "offres": v, "part": round(100 * v / n)} for k, v in outils.most_common()],
        "competences": competences.most_common(12),
        "entreprises": entreprises.most_common(10),
        "serie": serie,
        "offres": [{
            "intitule": o.get("intitule"),
            "entreprise": (o.get("entreprise") or {}).get("nom"),
            "lieu": (o.get("lieuTravail") or {}).get("libelle"),
            "contrat": o.get("typeContrat"),
            "salaire": (o.get("salaire") or {}).get("libelle"),
            "date": (o.get("dateCreation") or "")[:10],
            "url": (o.get("origineOffre") or {}).get("urlOrigine"),
        } for o in sorted(offres, key=lambda o: o.get("dateCreation") or "", reverse=True)],
    }
    sortie = RACINE / "data" / "resume.json"
    sortie.write_text(json.dumps(resume, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Écrit : {sortie.relative_to(RACINE)} — {n} offres du {d['date']}")
    print(f"Salaire annuel affiché par {len(mins)} offres ({resume['salaire']['part_affichant']} %) : "
          f"médiane des minima {resume['salaire']['min_median']} €, des maxima {resume['salaire']['max_median']} €")
    print("Outils :", ", ".join(f"{o['nom']} {o['part']} %" for o in resume["outils"][:8]))
    print("Départements :", departements.most_common(6))
    print("Entreprises :", entreprises.most_common(5))


if __name__ == "__main__":
    main()
