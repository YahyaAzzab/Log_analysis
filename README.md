# STRIX

STRIX (Authentication Threat Intelligence) lit des journaux d'authentification SSH, en extrait les tentatives utiles, repère les adresses agressives, et les présente dans un tableau de bord.

Les fichiers d'entrée sont des `auth.log` tournés, y compris compressés (`.gz`). Le pipeline les transforme en événements, les enregistre dans PostgreSQL, puis une API FastAPI sert le site.

## Pipeline

```text
data/auth.log*
        |
        v
ingestion/read.py          lecture dans l'ordre chronologique
        |
        v
processing/extract_transform.py
                           date, IP, utilisateur, type, port
        |
        v
processing/detection.py    bot et adresse malveillante
        |
        v
processing/gelocation.py   géolocalisation des IP malveillantes (IPinfo)
        |
        v
storage/                   PostgreSQL : auth_events + ip_intel
        |
        v
serving/api.py + serving/web/
                           API et tableau de bord
```

Le nom `gelocation.py` est volontaire : le fichier n'est pas renommé.

### Lecture

`ingestion/read.py` parcourt tous les journaux du dossier `data/`. Le suffixe le plus grand est le plus ancien (`auth.log.4.gz` avant `auth.log.1`). Les fichiers `.gz` sont lus en texte. Une erreur sur un fichier n'arrête pas les autres.

### Événements reconnus

`processing/extract_transform.py` ne garde que les lignes SSH reconnues :

| Type | Ligne syslog |
| --- | --- |
| `failed_password` | `Failed password for ...` |
| `invalid_user` | `Invalid user ...` |
| `accepted` | `Accepted password` ou `Accepted publickey` |
| `auth_failure` | `authentication failure` (PAM) |

Le syslog n'a pas d'année (`May 24 00:26:51`). L'année est ajoutée depuis `LOG_YEAR`.

### Détection

Pour chaque IP, les échecs sont triés et passés dans une fenêtre glissante.

- **Bot** : au moins 5 échecs en 30 secondes (`BOT_MIN_ATTEMPTS`, `BOT_WINDOW_SECONDS`).
- **Malveillante** : bot, ou au moins 20 échecs au total (`MALICIOUS_MIN_FAILURES`).

Les connexions réussies ne comptent pas dans ces seuils.

### Géolocalisation

Seules les IP malveillantes sont envoyées à IPinfo, pour limiter le quota. Les adresses privées ou locales ne sont pas interrogées. Le même IP n'est pas demandé deux fois dans le même chargement. Le jeton n'est jamais écrit dans les logs.

### Stockage

`storage/schema.sql` crée deux tables.

- `auth_events` : chaque tentative (date, IP, utilisateur, type, port, fichier source).
- `ip_intel` : pays, ville, coordonnées et organisation des IP malveillantes, plus le score bot.

La contrainte `(ts, ip, username, port, event_type)` ignore un doublon à la seconde près. Relancer `load` n'ajoute pas une deuxième fois les mêmes lignes.

## Interface

`python main.py serve` ouvre le site sur [http://127.0.0.1:8000](http://127.0.0.1:8000).

| Page | Rôle |
| --- | --- |
| `/` | Vue d'ensemble : volumes, courbe, IP les plus actives, dernières lignes |
| `/timeline.html` | Échecs dans le temps et heatmap heure × jour |
| `/map.html` | Carte des IP géolocalisées |
| `/ips.html` | Annuaire : répétitions, échecs, succès, pays |
| `/events.html` | Journal complet : date, heure, IP, utilisateur, résultat |
| `/ip.html?ip=` | Fiche d'une adresse : score, lieu, utilisateurs essayés |

Les filtres (dates, pays, IP, utilisateur, bots seulement) sont communs aux pages. Un thème clair et un thème sombre sont disponibles. L'intro se rejoue à chaque rechargement de l'accueil.

Les graphiques sont dessinés dans le navigateur avec ECharts. Python ne produit pas d'image.

## Prérequis

- Python 3.9
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL, avec une base vide nommée `strix`

```bash
createdb strix
```

## Installation

```bash
cd log_analysis
uv sync
cp .env.example .env
```

Renseigner `.env` :

```text
IPINFO_TOKEN=votre_jeton
DATABASE_URL=postgresql://utilisateur@localhost:5432/strix
LOG_YEAR=2024
```

| Variable | Rôle |
| --- | --- |
| `IPINFO_TOKEN` | Jeton IPinfo, utilisé pendant `load` |
| `DATABASE_URL` | Connexion PostgreSQL |
| `LOG_YEAR` | Année ajoutée aux dates syslog |

`.env` n'est pas versionné. Les journaux `data/*.log*` non plus.

Déposer les fichiers dans `data/`, par exemple `auth.log.1`, `auth.log.2`, `auth.log.3.gz`, `auth.log.4.gz`.

## Commandes

Activer l'environnement, puis :

```bash
source .venv/bin/activate
python main.py load
python main.py serve
```

Sans activation :

```bash
.venv/bin/python main.py load
.venv/bin/python main.py serve
```

`load` lit `./data` par défaut. Un autre dossier se passe avec `--data-dir`.

`serve` écoute `127.0.0.1:8000`. Ne pas interrompre `load` pendant la géolocalisation : l'insertion en base a lieu après.

## API

Toutes les routes acceptent des filtres en query string : `date_from`, `date_to`, `country`, `ip`, `username`, `bots_only`, `min_attempts`.

| Route | Contenu |
| --- | --- |
| `GET /api/health` | État du service |
| `GET /api/kpis?scope=all` | Volumes, IP distinctes, bots, pays |
| `GET /api/timeline` | Série horaire ou journalière |
| `GET /api/top-ips` | IP avec le plus d'échecs |
| `GET /api/top-users` | Utilisateurs les plus visés |
| `GET /api/countries` | Répartition par pays |
| `GET /api/map` | Points géolocalisés |
| `GET /api/bots` | IP marquées bot |
| `GET /api/events?scope=all` | Journal paginé |
| `GET /api/ips?scope=all` | Annuaire des adresses |
| `GET /api/ip/{ip}` | Fiche d'une adresse |

`scope=all` inclut les connexions réussies. `scope=failures` ne garde que les échecs. Les vues d'attaque (courbe, carte, bots) restent sur les échecs.

## Tests

```bash
uv run --with pytest pytest -q tests
```

Les tests couvrent le parsing de chaque type de ligne SSH et les seuils de détection (rafale, limite de fenêtre, volume sans rafale).

## Limites

- Les lignes qui ne sont pas une tentative SSH reconnue sont ignorées.
- Deux événements identiques dans la même seconde n'en font qu'un en base.
- La carte ne contient que les IP malveillantes : ce sont les seules envoyées à IPinfo.
- L'année n'est pas dans le journal. Elle vient de `LOG_YEAR`.
