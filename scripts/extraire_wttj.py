r"""Collecte de recherche Welcome to the Jungle, sans forcer le site.

Le site refuse (403) la lecture automatique de ses pages d'offre : ce script n'en lit donc aucune.
Il utilise ce que le site publie ouvertement, et ce que vous consultez vous-même.

Usage :
    .venv\Scripts\python.exe scripts\extraire_wttj.py
        1. lit les sitemaps publics (désignés par robots.txt) ;
        2. garde les offres /fr/ des métiers suivis (mots de l'URL, MOTS) ;
        3. écrit data_prive/wttj/sitemaps/<date>.csv : url, rome, entreprise, intitulé, ville, lastmod ;
        4. écrit data_prive/wttj/a_ouvrir.html : les offres nouvelles depuis le dernier passage, en
           liens cliquables, pour les ouvrir dans votre navigateur ;
        5. affiche les statistiques du jour : offres par métier, entreprises, villes ;
        6. écrit data/wttj_resume.json : ces seuls comptages agrégés (aucune URL, aucun contenu
           d'annonce), que la page d'accueil du site affiche.

    .venv\Scripts\python.exe scripts\extraire_wttj.py --pages "C:\chemin\pages_enregistrees"
        lit les pages d'offre que vous avez enregistrées depuis votre navigateur (Enregistrer sous…,
        page HTML) et en extrait le bloc schema.org JobPosting -> data_prive/wttj/offres.csv
        (et offres.jsonl, complet). Aucune requête vers le site.

Tout reste dans data_prive/ (ignoré par git) : le brut ne va jamais dans le dépôt public. Cadre :
exception de fouille de textes et de données pour la recherche (art. L122-5-3 CPI) ; ne publier que
des résultats agrégés ; les descriptions peuvent nommer un recruteur (RGPD) : pseudonymiser.
"""
import argparse
import collections
import csv
import gzip
import html
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import requests

RACINE = Path(__file__).resolve().parent.parent
DOSSIER = RACINE / "data_prive" / "wttj"
INDEX = "https://www.welcometothejungle.com/sitemaps/index.xml.gz"
UA = "metier-recherche/1.0 (collecte academique de sitemaps publics, IAE Clermont Auvergne)"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# Code ROME -> motifs cherchés dans l'intitulé de l'URL. Le premier qui correspond l'emporte :
# les plus précis d'abord.
MOTS = {
    "M1716": [r"directeu\w*-marketing-digital", r"head-of-digital"],
    "M1711": [r"directeu\w*-marketing", r"head-of-marketing", r"\bcmo\b"],
    "M1718": [r"marketing-digital", r"digital-marketing", r"\bgrowth\b"],
    "M1705": [r"responsable-marketing", r"marketing-manager"],
    "M1703": [r"chef-de-produit", r"product-marketing"],
    "M1620": [r"assistant\w*-marketing"],
    "M1430": [r"etudes?-(de-)?marche", r"market-research"],
    "E1113": [r"e-?commerce"],
    "E1101": [r"community-manager"],
    "E1124": [r"social-media"],
    "E1405": [r"\bseo\b", r"referenceu"],
    "M1886": [r"chef-de-projet-web", r"chef-de-projet-digital"],
    "M1719": [r"\binfluence\b"],
    "E1112": [r"charge\w*-de-communication", r"\bcommunication\b"],
    "E1103": [r"relations?-presse", r"relations?-publiques", r"attache\w*-de-presse"],
    "E1107": [r"evenementiel", r"\bevents?\b", r"event-manager"],
    "D1415": [r"\bcrm\b"],
}


# ---------- 1. Les sitemaps ----------

def lire(session, url):
    r = session.get(url, timeout=30)
    if r.status_code in (403, 429):
        sys.exit(f"Arrêt : {r.status_code} sur {url} — le site refuse, on ne force pas.")
    r.raise_for_status()
    return r.content


def locs(session, url):
    """(loc, lastmod) d'un sitemap .xml ou .xml.gz."""
    data = lire(session, url)
    try:
        data = gzip.decompress(data)
    except OSError:
        pass
    for e in ET.fromstring(data):
        loc, mod = e.find("s:loc", NS), e.find("s:lastmod", NS)
        if loc is not None:
            yield loc.text.strip(), (mod.text.strip() if mod is not None else "")


def decouper(url):
    """/fr/companies/<entreprise>/jobs/<intitulé>_<ville>[_<id>] -> (entreprise, intitulé, ville)."""
    m = re.search(r"/companies/([^/]+)/jobs/([^/?#]+)", url)
    if not m:
        return None
    parts = m.group(2).split("_")
    return m.group(1), parts[0], parts[1] if len(parts) > 1 else ""


def rome_de(intitule):
    for code, motifs in MOTS.items():
        if any(re.search(m, intitule) for m in motifs):
            return code
    return None


def sitemaps():
    s = requests.Session()
    s.headers["User-Agent"] = UA
    lignes = []
    for sitemap, _ in locs(s, INDEX):
        if "job-listings" not in sitemap:
            continue
        for url, mod in locs(s, sitemap):
            d = decouper(url) if "/fr/companies/" in url else None
            if d and (code := rome_de(d[1])):
                lignes.append({"url": url, "rome": code, "entreprise": d[0],
                               "intitule": d[1].replace("-", " "), "ville": d[2].replace("-", " "),
                               "lastmod": mod})
        time.sleep(2)                                  # deux secondes entre deux sitemaps
    return lignes


def ecrire_csv(chemin, lignes, champs):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=champs, extrasaction="ignore")
        w.writeheader()
        w.writerows(lignes)


def passage_sitemaps():
    aujourdhui = f"{date.today():%Y-%m-%d}"
    lignes = sitemaps()
    champs = ["url", "rome", "entreprise", "intitule", "ville", "lastmod"]
    ecrire_csv(DOSSIER / "sitemaps" / f"{aujourdhui}.csv", lignes, champs)

    # Nouvelles depuis le dernier passage : URL absentes du CSV précédent.
    precedents = sorted(p for p in (DOSSIER / "sitemaps").glob("*.csv") if p.stem < aujourdhui)
    connues = set()
    if precedents:
        with precedents[-1].open(encoding="utf-8") as f:
            connues = {r["url"] for r in csv.DictReader(f)}
    nouvelles = sorted((l for l in lignes if l["url"] not in connues),
                       key=lambda l: (l["rome"], l["lastmod"]), reverse=False)
    ecrire_liens(nouvelles, aujourdhui, depuis=precedents[-1].stem if precedents else None)

    print(f"{aujourdhui} : {len(lignes)} offres WTTJ pour les métiers suivis, "
          f"{len(nouvelles)} nouvelles depuis {precedents[-1].stem if precedents else 'toujours'}.")
    stats(lignes)
    resume_public(lignes, aujourdhui)


def resume_public(lignes, jour):
    """Les seuls chiffres publiés sur le site : comptages agrégés, sans URL ni contenu d'annonce."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from extraire import METIERS

    def compte(cle, n=None):
        return [[k, v] for k, v in collections.Counter(l[cle] for l in lignes if l[cle]).most_common(n)]

    par_rome = compte("rome")
    resume = {
        "date": jour,
        "source": "Welcome to the Jungle — sitemaps publics (robots.txt), offres en français",
        "methode": "métier déduit des mots de l'intitulé dans l'URL ; aucune page d'offre lue",
        "total": len(lignes),
        "par_metier": [[f"{METIERS[c][0]} ({c})", v] for c, v in par_rome],
        "entreprises": [[e.replace("-", " "), v] for e, v in compte("entreprise", 15)],
        "villes": compte("ville", 15),
    }
    (RACINE / "data" / "wttj_resume.json").write_text(
        json.dumps(resume, ensure_ascii=False, indent=1), encoding="utf-8")


def ecrire_liens(lignes, jour, depuis):
    par_rome = collections.defaultdict(list)
    for l in lignes:
        par_rome[l["rome"]].append(l)
    blocs = []
    for code in sorted(par_rome):
        items = "".join(
            f'<li><a href="{html.escape(l["url"])}" target="_blank">{html.escape(l["intitule"])}</a>'
            f' — {html.escape(l["entreprise"])}, {html.escape(l["ville"])} '
            f'<small>{l["lastmod"][:10]}</small></li>' for l in par_rome[code])
        blocs.append(f"<h2>{code} <small>({len(par_rome[code])})</small></h2><ul>{items}</ul>")
    titre = f"Offres WTTJ à ouvrir — {jour}" + (f" (nouvelles depuis le {depuis})" if depuis else "")
    page = (f"<!doctype html><meta charset='utf-8'><title>{titre}</title>"
            "<style>body{font:15px system-ui;max-width:900px;margin:24px auto;padding:0 16px}"
            "li{margin:3px 0}a:visited{color:#888}</style>"
            f"<h1>{titre}</h1><p>Ouvrez les offres qui vous intéressent, puis « Enregistrer sous… » "
            "(page HTML) dans un dossier, et lancez <code>extraire_wttj.py --pages ce_dossier</code>.</p>"
            + "".join(blocs))
    (DOSSIER / "a_ouvrir.html").write_text(page, encoding="utf-8")


def stats(lignes):
    def top(cle, n=8):
        return ", ".join(f"{k} ({v})" for k, v in collections.Counter(l[cle] for l in lignes).most_common(n))
    print("\nPar métier :", top("rome", 30))
    print("Entreprises :", top("entreprise"))
    print("Villes :", top("ville"))


# ---------- 2. Les pages que vous avez enregistrées ----------

def jobposting(texte):
    for bloc in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', texte, re.S):
        try:
            d = json.loads(bloc)
        except ValueError:
            continue
        for x in d if isinstance(d, list) else [d]:
            if isinstance(x, dict) and x.get("@type") == "JobPosting":
                return x
    return None


def lieu(o):
    loc = o.get("jobLocation")
    loc = loc[0] if isinstance(loc, list) and loc else loc
    adr = (loc or {}).get("address") or {}
    return adr.get("addressLocality", ""), adr.get("postalCode", "")


def passage_pages(dossier):
    fichiers = sorted(Path(dossier).rglob("*.htm*"))
    lignes, completes = [], []
    for f in fichiers:
        o = jobposting(f.read_text(encoding="utf-8", errors="replace"))
        if not o:
            print(f"  pas de JobPosting : {f.name}")
            continue
        ville, cp = lieu(o)
        desc = re.sub(r"<[^>]+>", " ", html.unescape(o.get("description", "")))
        sal = o.get("baseSalary") or {}
        val = sal.get("value") or {} if isinstance(sal, dict) else {}
        lignes.append({
            "fichier": f.name, "titre": o.get("title", ""),
            "rome": rome_de(re.sub(r"\W+", "-", o.get("title", "").lower())) or "",
            "entreprise": (o.get("hiringOrganization") or {}).get("name", ""),
            "ville": ville, "code_postal": cp, "date_publication": o.get("datePosted", ""),
            "contrat": ",".join(o["employmentType"]) if isinstance(o.get("employmentType"), list)
                       else o.get("employmentType", ""),
            "experience": json.dumps(o.get("experienceRequirements", ""), ensure_ascii=False)[:200],
            "salaire_min": val.get("minValue", ""), "salaire_max": val.get("maxValue", ""),
            "description_mots": len(desc.split()),
        })
        completes.append({"fichier": f.name, "offre": o})
    champs = list(lignes[0]) if lignes else ["fichier"]
    ecrire_csv(DOSSIER / "offres.csv", lignes, champs)
    with (DOSSIER / "offres.jsonl").open("w", encoding="utf-8") as f:
        for c in completes:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"{len(lignes)} offres extraites sur {len(fichiers)} fichiers -> "
          f"{(DOSSIER / 'offres.csv').relative_to(RACINE)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", help="dossier de pages d'offre enregistrées depuis votre navigateur")
    args = ap.parse_args()
    DOSSIER.mkdir(parents=True, exist_ok=True)
    if args.pages:
        passage_pages(args.pages)
    else:
        passage_sitemaps()


if __name__ == "__main__":
    main()
