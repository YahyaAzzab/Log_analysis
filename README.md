# Pipeline log analyser

Ce dépôt contient deux dossiers. La version à évaluer est `log_analysis`.

## log_analysis

C'est la version du cours. Elle est écrite en Python, sans site web. Les graphiques sont faits avec matplotlib, vu en cours. Le programme lit les journaux SSH, compte les tentatives, et enregistre les erreurs de chaque module dans un fichier de log.

Les trois graphiques demandés sont :

- le nombre de tentatives échouées par pays
- le nombre de tentatives réussies par utilisateur
- les tentatives échouées avec un invalid user

Pour la lancer :

```bash
cd log_analysis
pip install -r requirements.txt
python main.py
```

Les images sont écrites dans `log_analysis/reports/`. Le détail est dans `log_analysis/README.md`.

## log_analysis_version_avancee

C'est le travail que j'avais commencé avant de voir le message du professeur. Je suis nouveau dans l'établissement, je n'avais pas les consignes en même temps que les autres. Cette version va plus loin : une API, un site, PostgreSQL et une géolocalisation. Quand le projet web a été évoqué, ce n'était pas ce qui était demandé.

Je la laisse ici pour montrer le travail déjà fait. Je ne l'ai pas réécrite. Elle a seulement été déplacée dans ce dossier. Ce n'est pas la version à noter. La version qui suit les consignes est `log_analysis`.

La consigne dit : tout push dans git après le mardi 10, projet non validé. Je pousse donc ce dépôt le mardi 10. J'avais mal compris le sujet au début, mais je respecte cette date.
