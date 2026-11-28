# Journal des modifications / Changelog

Toutes les modifications notables sont consignées ici. Format inspiré de
[Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions selon [SemVer](https://semver.org/lang/fr/).
All notable changes are listed here, following Keep a Changelog and Semantic Versioning.

## [Non publié / Unreleased]

## [1.0.0] - 2026-11-28

Première version publique / First public release.

### Ajouté / Added
- Génération automatique d'examens à partir d'une banque de questions LaTeX : plusieurs versions avec de nouvelles
  valeurs ou des questions différentes, choix de réponse mélangés, PDF d'examen et de solutionnaire par version.
- Solutions étape par étape calculées avec SymPy, réponses seulement ou solutions rédigées en LaTeX.
- Interface web (React) : Générer, Bibliothèque, Importer avec bouton Tester, Examens produits, Paramètres,
  mode sombre.
- Configuration pour n'importe quel cégep : établissement, logo, professeurs, cours, page couverture, noms des
  fichiers, lettres de session ; un cours peut utiliser la banque d'un autre.
- Banque de départ de 734 questions de physique : 203-SN1-RE, 203-SN2-RE, 203-SN3-RE, MAN-SEC4 et MAN-SEC5.
- Installation en une commande avec `docker compose up -d`.
- Ligne de commande : `examgen generate`, `validate`, `import-folder`, `serve`.
- Page GitHub du projet : bannière, badges, captures d'écran, README bilingue, guide de contribution, code de conduite,
  politique de sécurité, formulaires de tickets et modèle de pull request.
- Intégration continue : tests du moteur avec LaTeX, validation de toute la banque de questions et compilation de
  l'interface sur chaque pull request ; construction et essai de l'image Docker (connexion, export d'un examen,
  téléchargement du ZIP).
- Examens produits : téléchargement en ZIP (tout, examens seulement ou solutionnaires seulement), suppression d'un
  examen, filtre par cours, date de l'examen, professeur et nombre de versions.
- Version mobile et tablette : barre du haut et menu coulissant.
- Structures proposées pour les examens 1 à 3 de 203-SN2-RE, MAN-SEC4 et MAN-SEC5 (4 questions à développement
  et 5 conceptuelles, 100 points, environ 80 minutes de travail sur 2 h). Modifiables dans l'écran Générer.

### Modifié / Changed
- Les PDF s'ouvrent dans le navigateur au lieu d'être téléchargés ; chaque examen est affiché à côté de son
  solutionnaire.
- Aperçu PDF de la bibliothèque dans une fenêtre de l'application (plus de fenêtre bloquée par le navigateur).
- Paramètres : avertissement s'il reste des modifications non enregistrées.
- Le nom du fichier d'une nouvelle question est déduit du titre s'il est laissé vide.
- Nombres affichés à la française (2,7) et confirmations dans l'application plutôt que celles du navigateur.

### Corrigé / Fixed
- Accessibilité : étiquettes reliées aux champs, boutons-icônes nommés, état des interrupteurs annoncé, titre de
  l'onglet selon l'écran.
- Les adresses `/api` inconnues répondent 404 au lieu de renvoyer l'interface.
- Les tests fonctionnent dans un clone neuf, sans préparation.

[Non publié / Unreleased]: https://github.com/JoMeloche/exam_cegep_physique/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/JoMeloche/exam_cegep_physique/releases/tag/v1.0.0
