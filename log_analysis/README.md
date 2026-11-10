# Analyse des logs SSH

J'analyse des fichiers `auth.log` (y compris les fichiers compressés `.gz`) et je sors trois graphiques.

Le programme est en Python. Le seul package en plus de la bibliothèque standard est matplotlib, pour les graphiques. Il n'y a pas de site web.

## Lancer

Depuis ce dossier :

```bash
pip install -r requirements.txt
python main.py
```

`python main.py` ouvre une fenêtre avec les graphiques. Il faut la fermer pour que le programme se termine. Les images sont aussi dans `reports/`.

Le programme repère les bots (5 échecs en 30 secondes). Les IP malveillantes sont localisées avec ipinfo, puis tout est enregistré dans PostgreSQL (`cours_events` et `cours_ip_intel`). Il faut un fichier `.env` avec `IPINFO_TOKEN` et `DATABASE_URL`. S'il n'est pas dans ce dossier, celui de `log_analysis_version_avancee` est utilisé.

Les journaux sont cherchés dans `data/`. S'il est vide, le programme prend ceux de `../log_analysis_version_avancee/data/`. On peut aussi donner le dossier :

```bash
python main.py --data-dir /chemin/vers/les/logs
```

## Ce que fait le programme

1. `ingestion/reader.py` lit les fichiers du plus ancien au plus récent. Le numéro le plus grand est le plus vieux (`auth.log.4.gz` avant `auth.log.1`).
2. `processing/parser.py` garde seulement les lignes SSH utiles :
   - mot de passe refusé
   - utilisateur invalide (`Invalid user`)
   - échec PAM (`authentication failure`)
   - connexion acceptée
3. Le syslog n'écrit pas l'année (`May 24 00:26:51`). Je mets 2024.
4. `processing/countries.py` cherche le pays de chaque IP avec `urllib` (bibliothèque standard) et garde le résultat dans un cache, pour ne pas redemander la même adresse.
5. `storage/save_csv.py` enregistre toutes les tentatives dans `storage/evenements.csv`.
6. `dashboard/charts.py` crée les trois images dans `reports/`.

## Les trois graphiques

- `reports/echecs_par_pays.png` : tentatives échouées par pays
- `reports/reussites_par_utilisateur.png` : tentatives réussies par utilisateur
- `reports/echecs_invalid_user.png` : échecs où l'utilisateur est invalide, par nom

Une même tentative peut produire deux lignes dans le log (`Invalid user` puis `Failed password for invalid user`). Je compte les lignes, pas une tentative regroupée.

## Logs d'erreurs

Chaque module écrit ses erreurs dans son fichier :

- `logs/ingestion.log`
- `logs/processing.log`
- `logs/storage.log`
- `logs/dashboard.log`
- `logs/main.log`

Un fichier illisible, un gzip cassé, une date impossible, une coupure réseau ou un dossier manquant est écrit ici. Le reste du traitement continue.

## Limites

Les lignes qui ne sont pas une tentative SSH sont ignorées. Si le service de pays ne répond pas, le pays est marqué `inconnu` et les deux autres graphiques sont quand même créés. Les adresses privées ne sont pas envoyées sur Internet.
