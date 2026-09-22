r"""Récupère les offres France Travail d'un métier et les enregistre dans data/.

Usage :
    .venv\Scripts\python.exe scripts\extraire.py                     # requête de la veille (CODE_ROME)
    .venv\Scripts\python.exe scripts\extraire.py --verifier          # teste seulement la connexion
    .venv\Scripts\python.exe scripts\extraire.py --rome "" --mots "marketing digital"   # par mots plutôt que par code
    .venv\Scripts\python.exe scripts\extraire.py --departement 63

Produit, pour chaque extraction datée :
    data/brut/offres_<date>.json   les offres telles que l'API les renvoie (JSON complet)
    data/offres_<date>.csv         une ligne par offre, colonnes lisibles
    data/serie.csv                 une ligne par extraction : date, requête, total (la tendance)

Les identifiants sont lus dans le fichier .env (voir .env.example) ou dans l'environnement
(secrets GitHub Actions). API : https://francetravail.io/data/api/offres-emploi —
150 offres par appel, 1 150 par requête, total réel dans l'en-tête Content-Range.
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

RACINE = Path(__file__).resolve().parent.parent
load_dotenv(RACINE / ".env")

MOTS_CLES = ""
CODE_ROME = "M1718"       # Chargé / Chargée de marketing digital — requête de la veille

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"


def obtenir_token():
    cid, secret = os.getenv("FT_CLIENT_ID"), os.getenv("FT_CLIENT_SECRET")
    if not cid or not secret or cid.startswith("PAR_votre"):
        sys.exit("Identifiants absents : copiez .env.example en .env et remplissez-le.")
    r = requests.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": cid,
        "client_secret": secret,
        "scope": "api_offresdemploiv2 o2dsoffre",
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def chercher(token, params, pas=150, maximum=1150):
    """Pagine la recherche ; renvoie (liste d'offres, total annoncé par l'API dans Content-Range)."""
    offres, total, debut = [], None, 0
    while debut < maximum:
        fin = min(debut + pas - 1, maximum - 1)
        r = requests.get(SEARCH_URL, params=dict(params, range=f"{debut}-{fin}"),
                         headers={"Authorization": f"Bearer {token}"}, timeout=30)
        if r.status_code == 204:                     # aucune offre
            break
        if r.status_code not in (200, 206):
            raise RuntimeError(f"{r.status_code} : {r.text[:200]}")
        m = re.search(r"/(\d+)", r.headers.get("Content-Range", ""))   # ex. "offres 0-149/1234"
        if m:
            total = int(m.group(1))
        lot = r.json().get("resultats", [])
        offres.extend(lot)
        if len(lot) < pas or (total is not None and len(offres) >= total):
            break
        debut += pas
        time.sleep(0.3)                              # on reste poli avec l'API
    return offres, total


def departement(lieu):
    """Code département : depuis le code postal, sinon depuis le libellé du type '75 - Paris'."""
    cp = lieu.get("codePostal") or ""
    if cp[:2].isdigit():
        return cp[:2]
    m = re.match(r"\s*(\d{2})\s*-", lieu.get("libelle") or "")
    return m.group(1) if m else ""


def en_tableau(offres):
    lignes = []
    for o in offres:
        lignes.append({
            "id": o.get("id"),
            "intitule": o.get("intitule"),
            "entreprise": (o.get("entreprise") or {}).get("nom"),
            "lieu": (o.get("lieuTravail") or {}).get("libelle"),
            "departement": departement(o.get("lieuTravail") or {}),
            "contrat": o.get("typeContrat"),
            "experience": o.get("experienceLibelle"),
            "salaire": (o.get("salaire") or {}).get("libelle"),
            "date_publication": (o.get("dateCreation") or "")[:10],
            "rome": o.get("romeCode"),
            "competences": " | ".join(c.get("libelle", "") for c in o.get("competences") or []),
            "url": (o.get("origineOffre") or {}).get("urlOrigine"),
        })
    return pd.DataFrame(lignes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verifier", action="store_true", help="teste seulement la connexion")
    ap.add_argument("--mots", default=MOTS_CLES, help='mots-clés ; "" pour ne pas filtrer')
    ap.add_argument("--rome", default=CODE_ROME, help='code ROME, ex. "M1718" ; vide = pas de filtre')
    ap.add_argument("--departement", default="", help='ex. "63" ; vide = France entière')
    args = ap.parse_args()

    token = obtenir_token()
    print("Connexion à l'API France Travail : OK")
    if args.verifier:
        return

    params = {}
    if args.mots:
        params["motsCles"] = args.mots
    if args.rome:
        params["codeROME"] = args.rome
    if args.departement:
        params["departement"] = args.departement
    if not params:
        sys.exit("Il faut au moins des mots-clés ou un code ROME.")

    offres, total = chercher(token, params)
    df = en_tableau(offres)
    aujourdhui = f"{date.today():%Y-%m-%d}"
    slug_mots = re.sub(r"[^a-z0-9]+", "-", args.mots.lower()).strip("-")
    etiquette = "_".join(filter(None, [args.rome, slug_mots, args.departement]))
    suffixe = f"_{etiquette}" if etiquette else ""

    (RACINE / "data" / "brut").mkdir(parents=True, exist_ok=True)
    brut = RACINE / "data" / "brut" / f"offres{suffixe}_{aujourdhui}.json"
    brut.write_text(json.dumps({"requete": params, "date": aujourdhui, "total": total,
                                "offres": offres}, ensure_ascii=False, indent=1), encoding="utf-8")
    sortie = RACINE / "data" / f"offres{suffixe}_{aujourdhui}.csv"
    df.to_csv(sortie, index=False, encoding="utf-8-sig")

    serie = RACINE / "data" / "serie.csv"
    nouveau = not serie.exists()
    with serie.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nouveau:
            w.writerow(["date", "mots_cles", "rome", "departement", "total", "recuperees"])
        w.writerow([aujourdhui, args.mots, args.rome, args.departement, total, len(df)])

    print(f"Requête : {params} — extraction du {aujourdhui}")
    print(f"Offres annoncées par l'API : {total} ; récupérées : {len(df)}")
    print(f"Écrit : {sortie.relative_to(RACINE)} et {brut.relative_to(RACINE)}")
    print(df[["intitule", "entreprise", "lieu", "contrat", "salaire"]].head().to_string())


if __name__ == "__main__":
    main()
