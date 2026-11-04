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

## 4. Petits sites et sites spécialisés (trouvés le 04/11/2026, non testés 🔎)

Tous ces sites sont apparus dans des recherches web. Je n'ai pas encore pu vérifier leur
`robots.txt` ni leurs CGU : sans vérification, la règle par défaut est la collecte manuelle.

### Flux RSS publiés exprès : le canal le plus prometteur

Un flux RSS est fait pour être lu par des programmes. C'est la voie la plus défendable après une
API.

| Source | Ce qu'elle publie |
|---|---|
| [Atlas des flux, rubrique emploi](https://atlasflux.saynete.net/atlas_des_flux_rss_fra_emploi.htm) | annuaire de flux RSS d'offres françaises (collectivités, administrations, organismes publics) : la meilleure porte d'entrée vers les petits sites |
| [Emploi des centres sociaux](https://emploi.centres-sociaux.fr/flux-rss/) | un flux par région et par département |
| [France Travail recrute](https://recrute.francetravail.org/Pages/Offre/ListeRss.aspx) (France Travail comme employeur) | flux par métier |
| Pages carrière sous Talentsoft : [Amundi](https://jobs.amundi.com/offre-de-emploi/tous-les-flux-rss.aspx), [IRD](https://emploi-recrutement.ird.fr/job/all-rss-feeds.aspx), [JCDecaux](https://jcdecaux-recrute.talent-soft.com/offre-de-emploi/tous-les-flux-rss.aspx), [Astronics](https://francejobs.astronics.com/offre-de-emploi/tous-les-flux-rss.aspx) | flux par région, métier et contrat (CDI, CDD, stage, apprentissage). Tous ont la même adresse `…/tous-les-flux-rss.aspx` : d'autres employeurs sous Talentsoft en publient sans doute aussi |

### Marketing, communication, digital

[Isarta](https://isarta.fr/) · [LesJeudis](https://lesjeudis.com/) · We Are COM · Emploi-e-commerce ·
cabinets : [Elaee](https://www.elaee.com/), [Michael Page](https://www.michaelpage.fr/jobs/communication/digital-marketing-communication),
[Page Personnel](https://www.pagepersonnel.fr/jobs/marketing-digital-communication)

### Stages et alternance

1jeune1solution · [Portail de l'alternance](https://alternance.emploi.gouv.fr) · L'Étudiant ·
[Stage.fr](https://www.stage.fr/) · Kapstages · Studyrama Emploi · Direct Étudiant · Walt Community ·
JobIRL · 1 élève 1 stage · Myfuturepass (stages dans la fonction publique) ·
liste de référence de l'[Onisep](https://www.onisep.fr/vers-l-emploi/stages-en-entreprises/stages-ou-trouver-des-offres)

### Régional : Auvergne-Rhône-Alpes, Clermont-Ferrand

[Nos Talents Nos Emplois](https://nostalentsnosemplois.auvergnerhonealpes.fr/), la plateforme de
la Région (plus de 130 000 offres d'après [Centre Inffo](https://www.centre-inffo.fr/site-regions-formation/actualites-regions/auvergne-rhone-alpes-le-site-web-nos-talents-nos-emplois-propose-des-offres-demploi-de-stages-et-dalternance)) ·
Jobsora (agrégateur)

### Économie sociale et solidaire, associations

[Emploi-ESS (UDES)](https://www.emploi-ess.fr/) · [Jobimpact](https://jobimpact.fr/offres-emploi) ·
Jobsense · Job For Change · Jobs That Makesense (déjà relayé par France Travail) ·
Solidarité Emploi · espace emploi des Scop · COORACE · offres des CRESS régionales

### Europe

| Pays | Sites |
|---|---|
| Union européenne | [EURES](https://europa.eu/eures/portal/) (portail public, 31 pays) · [EuroBrussels](https://www.eurobrussels.com/) (institutions de l'UE) · Europass |
| Espagne | InfoJobs |
| Suisse | jobs.ch · jobup.ch (Suisse romande) · Zentraljob |
| Allemagne | Bundesagentur für Arbeit (API, section 1) |
| Royaume-Uni | Reed (API, section 1) |

Pour la Belgique, l'Italie et le Luxembourg, la recherche n'a fait apparaître aucun site
national, à part EURES. Les services publics de l'emploi de ces pays (VDAB, Forem, Actiris en
Belgique, ADEM au Luxembourg, ANPAL en Italie) restent à vérifier un par un.

## Sources

- [Choisir le service public sur data.gouv.fr](https://www.data.gouv.fr/datasets/les-offres-diffusees-sur-choisir-le-service-public)
- [Jobsuche API (bund.dev)](https://jobsuche.api.bund.dev/) · [bundesAPI/jobsuche-api](https://github.com/bundesAPI/jobsuche-api)
- [Documentation EURES non officielle](https://github.com/rorar/EURES-API-Documentation)
- [Article France Travail sur l'API offres pour les collectivités](https://www.francetravail.org/accueil/actualites/api-offres-de-pole-emploi-dedie.html?type=article)
