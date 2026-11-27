# Contribuer à ExamGen

*[English below](#contributing-english)*

Merci de votre intérêt ! Toutes les contributions sont les bienvenues : nouvelles questions, corrections dans la
banque, signalements de bogues, idées, traductions et code. Vous pouvez écrire en français ou en anglais.

En participant, vous acceptez de respecter le [code de conduite](CODE_OF_CONDUCT.md).

## Signaler un bogue ou proposer une idée

Ouvrez un [ticket](https://github.com/JoMeloche/exam_cegep_physique/issues/new/choose) avec le formulaire qui
convient. Pour un bogue, indiquez votre installation (Docker, Windows, macOS, Linux) et le message d'erreur.

## Proposer des questions

La banque de départ grandit grâce aux professeurs qui l'utilisent.

**Sans Git** : créez la question dans l'application (écran **Importer**, puis **Tester**), et joignez les fichiers
`nom.tex`, `nom.yaml` (et `nom.sol.tex`, la figure s'il y a lieu) au formulaire
[Proposer une question](https://github.com/JoMeloche/exam_cegep_physique/issues/new?template=question_submission.yml).
Les fichiers se trouvent dans `mes_examens/questions/<cours>/<thème>/` (Docker) ou `~/exam_app/questions/...`
(application de bureau).

**Avec Git** : ajoutez les fichiers dans `questions/<cours>/<thème>/` et les figures dans `figures/`, puis ouvrez une
pull request. Le format est décrit dans [docs/question_format.md](docs/question_format.md). Avant d'envoyer :

```bash
pip install -e "app/backend[dev]"
EXAM_APP_HOME=. python -m examgen validate --only 203-SN3-RE/Doppler   # vérifie et compile vos questions
```

Ne proposez que des questions que vous avez écrites ou que vous avez le droit de partager sous licence MIT
(pas de questions copiées d'un manuel).

## Contribuer au code

### Installer l'environnement

Il faut Python 3.11+, Node 20+ et LaTeX (`pdflatex` avec les paquets exam, babel-french, siunitx, pgf, enumitem, lm).

```bash
git clone https://github.com/JoMeloche/exam_cegep_physique.git
cd exam_cegep_physique/app
python -m venv .venv && source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -e "backend[dev]"
cd frontend && npm ci && cd ..

python -m examgen serve                  # API + interface compilée : http://127.0.0.1:8765
(cd frontend && npm run dev)             # interface avec rechargement : http://localhost:5173
```

Détails et commandes : [app/README.md](app/README.md).

### Structure

| Dossier | Rôle |
|---|---|
| `app/backend/examgen/` | Moteur : `library.py` (banque), `values.py` (tirage), `solve.py` (SymPy), `generate.py` (examens), `latex.py` (compilation), `api.py` (FastAPI) |
| `app/frontend/src/` | Interface React + Tailwind (`pages/`, `components/`) |
| `app/packaging/` | Applications de bureau |

### Tests

```bash
# Bibliothèque de test : une copie de la banque du dépôt
mkdir -p /tmp/apilib && cp -r questions figures exams config.yaml /tmp/apilib/
sed -i "s/^school: ''/school: 'Cégep de test'/" /tmp/apilib/config.yaml
cd app/backend && EXAMGEN_TEST_LIB=/tmp/apilib python -m pytest tests
cd ../frontend && npm run build          # vérifie aussi les types TypeScript
```

L'intégration continue (GitHub Actions) exécute ces vérifications sur chaque pull request.

### Pull requests

1. Créez une branche à partir de `main`.
2. Gardez la PR centrée sur un seul changement ; joignez des captures d'écran si l'interface change.
3. Ajoutez une ligne dans la section « Non publié » de [CHANGELOG.md](CHANGELOG.md).
4. L'interface est en français : gardez les textes visibles en français.

---

<a id="contributing-english"></a>

# Contributing (English)

Thanks for your interest! Questions for the bank, fixes, bug reports, ideas, translations and code are all welcome,
in French or English. By participating you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

- **Bugs and ideas**: open an [issue](https://github.com/JoMeloche/exam_cegep_physique/issues/new/choose).
- **Questions for the bank**: create the question in the app (**Importer**, then **Tester**) and attach its
  `.tex`/`.yaml` files to the [question form](https://github.com/JoMeloche/exam_cegep_physique/issues/new?template=question_submission.yml),
  or add them under `questions/<course>/<topic>/` in a pull request. Format:
  [docs/question_format.md](docs/question_format.md). Check them with
  `EXAM_APP_HOME=. python -m examgen validate --only <course>/<topic>`. Only submit questions you wrote or may share
  under the MIT license.
- **Code**: Python 3.11+, Node 20+ and LaTeX. Setup, run and test commands are in the French section above and in
  [app/README.md](app/README.md). CI runs the backend tests, validates the whole question bank and builds the UI on
  every pull request. Keep PRs focused, add screenshots for UI changes, add a line under "Unreleased" in
  [CHANGELOG.md](CHANGELOG.md), and keep user-facing text in French.
