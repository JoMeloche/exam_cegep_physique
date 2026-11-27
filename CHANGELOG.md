# Journal des modifications / Changelog

Toutes les modifications notables sont consignées ici. Format inspiré de
[Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions selon [SemVer](https://semver.org/lang/fr/).
All notable changes are listed here, following Keep a Changelog and Semantic Versioning.

## [Non publié / Unreleased]

### Ajouté / Added
- Page GitHub du projet : bannière, badges, captures d'écran, README bilingue, guide de contribution, code de conduite,
  politique de sécurité, formulaires de tickets et modèle de pull request.
- Intégration continue : tests du moteur avec LaTeX, validation de toute la banque de questions et compilation de
  l'interface sur chaque pull request.

## [0.1.0] - 2026-11-27

Première version / First version.

### Ajouté / Added
- Génération automatique d'examens à partir d'une banque de questions LaTeX : plusieurs versions avec de nouvelles
  valeurs ou des questions différentes, choix de réponse mélangés, PDF d'examen et de solutionnaire par version.
- Solutions étape par étape calculées avec SymPy, réponses seulement ou solutions rédigées en LaTeX.
- Interface web (React) : Générer, Bibliothèque, Importer avec bouton Tester, Examens produits, Paramètres,
  mode sombre.
- Configuration pour n'importe quel cégep : établissement, logo, professeurs, cours, page couverture, noms des
  fichiers, lettres de session ; un cours peut utiliser la banque d'un autre.
- Banque de départ de plus de 650 questions de physique (203-SN1-RE, 203-SN2-RE, 203-SN3-RE, mises à niveau).
- Installation en une commande avec `docker compose up -d`.
- Ligne de commande : `examgen generate`, `validate`, `import-folder`, `serve`.

[Non publié / Unreleased]: https://github.com/JoMeloche/exam_cegep_physique/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/JoMeloche/exam_cegep_physique/commits/main
