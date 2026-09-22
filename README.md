# Le marché de mon métier — chargé(e) de marketing digital

Dossier de travail pour la séance « Écouter le marché de votre métier »
(M2 MOD, IAE Clermont Auvergne). Dépôt de démonstration : il montre ce que
l'on attend d'un dossier `avenir`, étape par étape, et la chaîne complète
API → données → Action planifiée → page GitHub Pages.

## Le métier, tel que le marché le nomme

- **Intitulé principal** : chargé / chargée de marketing digital
- **Variantes rencontrées dans les offres** : chef de projet marketing digital,
  chef de produit digital, traffic manager, CRM manager, chargé d'acquisition
- **Code ROME** : **M1718** — Chargé / Chargée de marketing digital
  (le README disait M1705 « Marketing » ; c'est la première extraction qui a
  donné le bon code : 14 offres sur 22 étaient en M1718)

## Les questions que je pose à ce marché

1. Combien d'offres, et où : Clermont / Puy-de-Dôme, Auvergne-Rhône-Alpes,
   France, télétravail ?
2. Quels contrats et quels salaires affichés ?
3. Quels outils et compétences reviennent le plus — et lesquels la formation
   ne me donnera pas ?
4. Quelles entreprises publient le plus cet intitulé ?

## Ce que la première journée a appris (22/09/2026)

Trois requêtes, même jour, même API :

| Requête | Offres | Lecture |
|---|---|---|
| `motsCles = "chef de projet marketing digital"` | 22 | trop étroit, et du bruit (PMO, communication) |
| `codeROME = M1718` | 113 | le référentiel : homogène, c'est la requête de la veille |
| `motsCles = "marketing digital"` | 424 | large, mais 191 annonces identiques d'un même réseau (M1716) : à dédoublonner avant de compter |

Sur M1718 : 0 offre dans le 63, 11 en Auvergne-Rhône-Alpes, Paris et
Hauts-de-Seine en tête ; 27 % des offres affichent un salaire, médiane
31 000 → 35 700 € annuels ; réseaux sociaux, anglais, SEO/SEA, GA4 et
« IA » reviennent le plus.

## La chaîne

```
API France Travail  →  scripts/extraire.py  →  data/brut/*.json (brut) + data/*.csv + data/serie.csv
                                            →  scripts/resumer.py  →  data/resume.json  →  index.html (GitHub Pages)
                       .github/workflows/veille.yml : GitHub relance tout ça chaque matin à 7 h
```

- `scripts/extraire.py` — appelle l'API (token OAuth, pagination 150 / 1 150,
  total lu dans `Content-Range`), enregistre le JSON brut et un CSV datés,
  ajoute une ligne à `data/serie.csv` (la tendance).
- `scripts/resumer.py` — retravaille le brut : salaires (libellé texte →
  min/max annuels), outils cités dans les descriptions (grille à adapter),
  comptages par département, contrat, entreprise ; écrit `data/resume.json`.
- `index.html` — lit `data/resume.json` et trace les graphiques (Chart.js).

## Faire tourner chez soi

```
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env        (puis remplir avec ses identifiants francetravail.io)
.venv\Scripts\python.exe scripts\extraire.py --verifier
.venv\Scripts\python.exe scripts\extraire.py
.venv\Scripts\python.exe scripts\resumer.py
.venv\Scripts\python.exe -m http.server 8125      (puis http://localhost:8125)
```

## Faire tourner sans soi (GitHub)

1. Dépôt **public** (GitHub Pages gratuit ne fonctionne que sur un dépôt public).
2. Settings → Secrets and variables → Actions : `FT_CLIENT_ID` et `FT_CLIENT_SECRET`.
3. Settings → Pages → Source « Deploy from a branch », branche `main`, dossier `/ (root)`.
4. Actions → veille → Run workflow : le premier commit du bot arrive dans `data/`.

## Règles

- Les identifiants sont dans `.env` (local) ou dans les secrets du dépôt
  (GitHub) : jamais dans un fichier versionné.
- Un canal, une requête, une date : chaque chiffre du site les affiche.
- Pas de scraping de LinkedIn, APEC ou Indeed (interdit par leurs CGU).
