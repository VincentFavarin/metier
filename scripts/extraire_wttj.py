r"""Collecte de recherche : les offres Welcome to the Jungle des métiers suivis, lues comme un visiteur.

Usage :
    .venv\Scripts\python.exe scripts\extraire_wttj.py               # 300 pages au plus
    .venv\Scripts\python.exe scripts\extraire_wttj.py --max 20      # pour essayer
    .venv\Scripts\python.exe scripts\extraire_wttj.py --liste       # compte les URL, ne lit aucune offre

Comment :
    1. les sitemaps publics que robots.txt désigne (sitemaps/index.xml.gz -> job-listings.N.xml.gz) ;
    2. on garde les URL /fr/ dont les mots correspondent à un métier de MOTS ;
    3. on ne lit que les offres nouvelles ou dont le <lastmod> a changé depuis la dernière collecte ;
    4. dans chaque page, le bloc JSON-LD schema.org « JobPosting » que le site publie pour les moteurs.

Règles : une page toutes les PAUSE secondes, user-agent qui dit ce qu'il est, rien qui soit interdit
par robots.txt (pas d'URL à paramètres), et arrêt immédiat au premier 403, 429 ou captcha :
on ne contourne aucune protection.

Ce que ça écrit, HORS du dépôt public (data_prive/ est dans .gitignore) :
    data_prive/wttj/<AAAA-MM>.jsonl   une ligne par offre lue : url, rome, lastmod, vu_le, offre (JobPosting)
    data_prive/wttj/etat.json         url -> lastmod déjà lu, pour ne rien relire
Cadre : exception de fouille de textes et de données pour la recherche (art. L122-5-3 CPI). Le brut
reste privé ; seuls des résultats agrégés peuvent être publiés. Les descriptions peuvent contenir le
nom d'un recruteur (RGPD) : à pseudonymiser avant toute analyse partagée.
"""
import argparse
import gzip
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
UA = "metier-recherche/1.0 (collecte academique, IAE Clermont Auvergne)"
PAUSE = 6
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# Code ROME -> motifs cherchés dans les mots de l'URL (le « slug » de l'intitulé). Le premier qui
# correspond l'emporte : les plus précis d'abord.
MOTS = {
    "M1716": [r"directeu\w*-marketing-digital", r"head-of-digital"],
    "M1711": [r"directeu\w*-marketing", r"head-of-marketing", r"\bcmo\b"],
    "M1718": [r"marketing-digital", r"digital-marketing", r"growth"],
    "M1705": [r"responsable-marketing", r"marketing-manager"],
    "M1703": [r"chef-de-produit", r"product-marketing"],
    "M1620": [r"assistant\w*-marketing"],
    "M1430": [r"etudes?-(de-)?marche", r"market-research"],
    "E1113": [r"e-?commerce"],
    "E1101": [r"community-manager"],
    "E1124": [r"social-media"],
    "E1405": [r"\bseo\b", r"referenceu"],
    "M1886": [r"chef-de-projet-web", r"chef-de-projet-digital"],
    "M1719": [r"influence"],
    "E1112": [r"charge\w*-de-communication", r"communication"],
    "E1103": [r"relations?-presse", r"relations?-publiques", r"attache\w*-de-presse"],
    "E1107": [r"evenementiel", r"\bevents?\b", r"event-manager"],
    "D1415": [r"\bcrm\b"],
}


def lire(session, url):
    r = session.get(url, timeout=30)
    if r.status_code in (403, 429) or "captcha" in r.text[:5000].lower():
        sys.exit(f"Arrêt : {r.status_code} sur {url} — le site refuse, on ne force pas.")
    r.raise_for_status()
    return r


def locs(session, url):
    """(loc, lastmod) d'un sitemap .xml.gz."""
    data = lire(session, url).content
    try:
        data = gzip.decompress(data)
    except OSError:
        pass
    racine = ET.fromstring(data)
    for e in racine:
        loc = e.find("s:loc", NS)
        mod = e.find("s:lastmod", NS)
        if loc is not None:
            yield loc.text.strip(), (mod.text.strip() if mod is not None else "")


def rome_de(url):
    slug = url.rsplit("/jobs/", 1)[-1].replace("_", " ")
    for code, motifs in MOTS.items():
        if any(re.search(m, slug) for m in motifs):
            return code
    return None


def jobposting(html):
    for bloc in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            d = json.loads(bloc)
        except ValueError:
            continue
        for x in d if isinstance(d, list) else [d]:
            if isinstance(x, dict) and x.get("@type") == "JobPosting":
                return x
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=300, help="pages d'offre lues au plus par passage")
    ap.add_argument("--liste", action="store_true", help="compte les URL retenues, ne lit aucune offre")
    args = ap.parse_args()

    s = requests.Session()
    s.headers["User-Agent"] = UA
    DOSSIER.mkdir(parents=True, exist_ok=True)
    fichier_etat = DOSSIER / "etat.json"
    etat = json.loads(fichier_etat.read_text(encoding="utf-8")) if fichier_etat.exists() else {}

    a_lire = []
    for sitemap, _ in locs(s, INDEX):
        if "job-listings" not in sitemap:
            continue
        for url, mod in locs(s, sitemap):
            if "/fr/companies/" in url and "?" not in url:
                code = rome_de(url)
                if code and etat.get(url) != mod:
                    a_lire.append((mod, url, code))
        time.sleep(2)
    a_lire.sort(reverse=True)                     # les plus récentes d'abord
    print(f"{len(a_lire)} offres nouvelles ou modifiées pour les métiers suivis.")
    if args.liste:
        return

    aujourdhui = f"{date.today():%Y-%m-%d}"
    lues = 0
    with (DOSSIER / f"{aujourdhui[:7]}.jsonl").open("a", encoding="utf-8") as sortie:
        for mod, url, code in a_lire[: args.max]:
            offre = jobposting(lire(s, url).text)
            etat[url] = mod
            if offre:
                sortie.write(json.dumps({"url": url, "rome": code, "lastmod": mod, "vu_le": aujourdhui,
                                         "offre": offre}, ensure_ascii=False) + "\n")
                lues += 1
            fichier_etat.write_text(json.dumps(etat, ensure_ascii=False), encoding="utf-8")
            time.sleep(PAUSE)
    print(f"{aujourdhui} : {lues} offres enregistrées dans {DOSSIER.relative_to(RACINE)}.")


if __name__ == "__main__":
    main()
