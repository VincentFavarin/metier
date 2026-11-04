# Sources d'offres d'emploi, de stage et d'alternance : France, Europe, monde

Recensement du 04/11/2026 pour la collecte de recherche. Il complète `sources-api.md`, qui ne
couvre que la France.

**Ce que veut dire « vérifié ».**
- ✅ : j'ai interrogé le point d'accès moi-même dans cette session, ou lu la documentation
  officielle de l'éditeur.
- 🔎 : l'information vient de documentations ou d'articles trouvés en ligne. Elle reste à tester
  avant de s'en servir.
- ❌ : pas de voie légale de collecte automatique (connexion obligatoire, CGU explicites, refus
  technique).

Rien n'est classé « collectable » sur la seule foi de ma mémoire.

**L'ordre de préférence**, du plus sûr au moins sûr : API officielle, puis open data, puis sitemap
autorisé par `robots.txt`, puis collecte manuelle dans son navigateur.

## 1. API officielles et open data : à collecter en priorité

| Source | Couverture | Accès | État |
|---|---|---|---|
| France Travail — Offres d'emploi v2 | France, avec ~60 sites partenaires relayés | [francetravail.io](https://francetravail.io/inscription), gratuit, OAuth2 | ✅ branchée sur le site |
| La bonne alternance | France, alternance | [api.apprentissage.beta.gouv.fr](https://api.apprentissage.beta.gouv.fr/fr/compte), gratuit, clé | ✅ (documentation lue) |
| **Choisir le service public (DGAFP)** : offres d'emploi de l'État, des **mairies et collectivités** et des hôpitaux | France, fonction publique | [Jeu de données data.gouv.fr](https://www.data.gouv.fr/datasets/les-offres-diffusees-sur-choisir-le-service-public), CSV hebdomadaire, Licence Ouverte 2.0 | 🔎 fiche trouvée, fichier non téléchargé |
| API Engagement | France, Service civique et bénévolat | [api-engagement.beta.gouv.fr](https://api-engagement.beta.gouv.fr/), sur demande | ✅ (site lu) |
| Adzuna | 19 pays : gb, us, at, au, be, br, ca, ch, de, es, fr, in, it, mx, nl, nz, pl, sg, za | [developer.adzuna.com](https://developer.adzuna.com/signup), gratuit avec quota | ✅ branchée ; liste des pays tirée de la spécification officielle |
| Bundesagentur für Arbeit (Jobbörse) | Allemagne | [jobsuche.api.bund.dev](https://jobsuche.api.bund.dev/) : clé publique `jobboerse-jobsuche`, celle qu'utilise l'application web de l'agence | 🔎 documentation trouvée ; une source dit qu'il n'existe pas d'API officielle, à clarifier |
| USAJOBS | États-Unis, emploi fédéral | `developer.usajobs.gov`, clé gratuite | 🔎 |
| Reed | Royaume-Uni | `reed.co.uk/developers`, clé gratuite | 🔎 URL de base et quotas contradictoires selon les sources |
| Careerjet / Optioncarriere | multi-pays | [compte éditeur](https://www.careerjet.com/partners/register/as-publisher) | ✅ (documentation lue) ; pensée pour publier sur un site, pas pour constituer une archive |
| Jooble | multi-pays, une clé par pays | formulaire `fr.jooble.org/api/about` | 🔎 quota gratuit très faible |
| Arbeitnow | Europe, surtout Allemagne | API sans clé | ✅ répond (06/10) |
| Remotive, Himalayas, Remote OK | télétravail, monde | API ou flux sans clé | ✅ répondent (06/10) |
| The Muse | surtout États-Unis | API publique, clé facultative | ✅ répond (06/10) |
| Logiciels de recrutement : SmartRecruiters, Lever, Greenhouse, Recruitee | une entreprise à la fois, monde | flux publics des pages carrière | ✅ documentation SmartRecruiters ; 🔎 pour les trois autres |

## 2. Sitemaps publics : seulement les comptages, pas les pages

| Source | Ce qui est possible | État |
|---|---|---|
| Welcome to the Jungle | sitemaps autorisés par `robots.txt` : 89 475 offres, intitulé, entreprise, ville et date tirés de l'URL | ✅ branché (`scripts/extraire_wttj.py`) ; les pages d'offre répondent 403 aux programmes |

D'autres sites publient sans doute des sitemaps. Je n'ai pas pu le vérifier : les requêtes
automatiques vers des sites tiers m'ont été refusées dans cette session. Il faudra regarder leur
`robots.txt` un par un.

## 3. Sans voie de collecte automatique légale : collecte manuelle seulement

| Source | Raison |
|---|---|
| LinkedIn | CGU interdisant la collecte automatique ; API réservée aux logiciels de recrutement partenaires |
| Facebook, Instagram (Meta) | CGU interdisant la collecte automatique ; pas d'API d'offres d'emploi |
| Indeed | programme éditeurs fermé depuis 2022 ; collecte interdite par les CGU |
| Glassdoor | API fermée |
| Welcome to the Jungle (pages d'offre) | CGU ; 403 aux programmes |
| UCAPRO, alumni IAE, JobTeaser | connexion obligatoire (vérifié le 04/11 pour UCAPRO et le site alumni de l'IAE) |
| Emploi-territorial (centres de gestion) | pas d'API trouvée ; une partie des offres est reprise dans Choisir le service public, ci-dessus |
| EURES (portail européen) | pas d'API officielle trouvée, seulement une spécification rétro-ingénierée non maintenue par l'UE ; à demander à l'Autorité européenne du travail (ELA) |
| Apec, HelloWork, Monster, Meteojob, Cadremploi, Jobijoba | pas d'API de consultation (voir `sources-api.md`) ; une partie est relayée par France Travail |

Les **mairies** passent par trois canaux : Choisir le service public (open data, section 1),
France Travail (déjà branché) et leurs propres sites ou pages Facebook. Ces derniers sont épars,
et c'est là que la collecte manuelle reste nécessaire.

## Sources

- [Choisir le service public sur data.gouv.fr](https://www.data.gouv.fr/datasets/les-offres-diffusees-sur-choisir-le-service-public)
- [Jobsuche API (bund.dev)](https://jobsuche.api.bund.dev/) · [bundesAPI/jobsuche-api](https://github.com/bundesAPI/jobsuche-api)
- [Documentation EURES non officielle](https://github.com/rorar/EURES-API-Documentation)
- [Article France Travail sur l'API offres pour les collectivités](https://www.francetravail.org/accueil/actualites/api-offres-de-pole-emploi-dedie.html?type=article)
