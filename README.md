# Générateur d'examens pour le cégep

*[English below](#english)*

Une application qui monte vos examens automatiquement à partir d'une banque de questions LaTeX.
Vous choisissez le professeur, le cours, le numéro d'examen, la date et la durée ; l'application
choisit les questions, tire de nouvelles valeurs numériques pour chaque version, calcule les solutions
et produit un PDF d'examen et un PDF de solutionnaire par version, par exemple
`203-NYC-05_Examen_1_A26_v1.pdf` et `203-NYC-05_Examen_1_A26_v1_solution.pdf`.

- Fonctionne pour n'importe quel cégep : établissement, logo, professeurs, cours, consignes de la page
  couverture, nom des fichiers et lettres de session se configurent dans l'application.
- Banque de départ en physique (mécanique, électricité et magnétisme, ondes et physique moderne,
  mises à niveau) que vous pouvez modifier, compléter ou remplacer.
- Questions en LaTeX, variables avec intervalles, solutions automatiques étape par étape (SymPy)
  ou rédigées en LaTeX, choix de réponse mélangés à chaque version.
- Tout reste sur votre ordinateur ou votre serveur : aucun service externe.

## Installation en 3 étapes (Docker)

1. Installez **Docker Desktop** (Windows, macOS) ou Docker (Linux) : https://www.docker.com/products/docker-desktop/
2. Téléchargez ce projet : bouton vert **Code → Download ZIP**, puis décompressez-le
   (ou `git clone https://github.com/JoMeloche/exam_cegep_physique.git`).
3. Dans le dossier du projet, ouvrez un terminal et lancez :
   ```
   docker compose up -d
   ```
   Le premier lancement prend 5 à 10 minutes (installation de LaTeX). Ouvrez ensuite
   **http://localhost:8765** dans votre navigateur.

Au premier lancement, créez le compte administrateur avec le code affiché par `docker compose logs examgen`
(ou mettez `EXAMGEN_ADMIN_EMAIL` et `EXAMGEN_ADMIN_PASSWORD` dans `.env`). Un écran de bienvenue vous demande
ensuite votre établissement, vos professeurs et vos cours.

**Comptes** : n'importe qui peut demander un compte en expliquant pourquoi ; un administrateur approuve ou
refuse la demande dans **Utilisateurs**. Chaque enseignant a sa propre banque et peut partager des questions
avec tous ou avec des collègues choisis. Pour mettre l'application en ligne en HTTPS, voir
[docs/securite.md](docs/securite.md).

Vos questions, vos examens et vos PDF sont conservés dans le dossier **`mes_examens`** à côté de
`docker-compose.yml`. Sauvegardez ce dossier ; vous pouvez le partager avec vos collègues.

| Action | Commande |
|---|---|
| Arrêter | `docker compose down` |
| Redémarrer | `docker compose up -d` |
| Mettre à jour l'application | `git pull` puis `docker compose up -d --build` |
| Changer le port ou le dossier de données | copiez `.env.example` en `.env` et modifiez-le |

> Votre bibliothèque dans `mes_examens` n'est jamais écrasée par une mise à jour : la banque de départ
> n'est copiée que si le dossier `questions` est vide.

### Sans Docker
- **Windows, application de bureau** : un installateur (`ExamGen-Setup.exe`, LaTeX inclus) se construit
  avec `app/packaging/build_windows.ps1` (voir [app/README.md](app/README.md)).
- **Depuis le code source** : voir [app/README.md](app/README.md).

## Adapter l'application à votre cégep

Tout se fait dans **Paramètres** :
- **Établissement, logo, professeurs** : imprimés sur la page couverture.
- **Cours** : code (ex. `203-NYA-05`), discipline, nom, groupe. Un cours peut **utiliser la banque d'un autre
  dossier** : par exemple votre `203-NYC-05` peut piger dans les questions du dossier `203-SN3-RE`
  (ondes et physique moderne) sans rien renommer.
- **Noms des fichiers** : modèle avec `{course} {exam} {session} {version} {date} {year}`.
- **Sessions** : lettre par mois (A = automne, H = hiver, E = été par défaut).
- **Page couverture** : consignes et note en LaTeX.

La structure de chaque examen (thèmes, nombre de questions, points) se règle dans l'écran **Générer**
et s'enregistre pour la prochaine fois.

## Ajouter des questions
Écran **Importer** : l'énoncé en LaTeX, où chaque `\v{nom}` devient une variable ; une ligne par variable
(intervalle, type de nombre, unité) ; le temps estimé ; la difficulté ; puis la solution (automatique, réponses
seulement ou LaTeX). Le bouton **Tester** compile la question avec 5 jeux de valeurs avant l'enregistrement.
Le format des fichiers est décrit dans [docs/question_format.md](docs/question_format.md).

## Contenu du dépôt
| Dossier | Contenu |
|---|---|
| `app/` | L'application (moteur Python et API, interface React, Docker, empaquetage Windows) |
| `questions/<cours>/<thème>/` | La banque : `nom.tex` (énoncé), `nom.yaml` (variables, temps, difficulté, solution), `nom.sol.tex` |
| `figures/` | Images des questions |
| `exams/<cours>/examen_<N>.yaml` | Structure des examens |
| `config.yaml` | Configuration de départ (sans établissement ni professeur) |
| `docs/` | Format des questions |
| `legacy/` | L'examen SN3 d'origine, fait à la main, d'où la banque a été importée |

## Licence
[MIT](LICENSE) : libre d'utiliser, modifier et partager, en conservant l'avis de licence.

---

<a id="english"></a>
# Exam generator for Québec cégeps (English)

An app that builds exams automatically from a LaTeX question bank. Choose the professor, course, exam number,
date and duration; the app picks questions, draws fresh values for every version, computes the solutions and
outputs one exam PDF and one solution PDF per version (e.g. `203-NYC-05_Examen_1_A26_v1.pdf`).

- Works for any cégep: institution, logo, professors, courses, cover-page instructions, file naming and session
  letters are all set in the app.
- Starter physics bank (mechanics, electricity & magnetism, waves & modern physics, upgrading courses).
- LaTeX questions with ranged variables, automatic step-by-step solutions (SymPy) or LaTeX solutions,
  multiple-choice answers shuffled per version. Runs entirely on your computer.

## Install in 3 steps (Docker)
1. Install **Docker Desktop** (Windows, macOS) or Docker (Linux).
2. Download this project (**Code → Download ZIP** and unzip, or `git clone`).
3. In the project folder run `docker compose up -d`, wait 5–10 minutes the first time, then open
   **http://localhost:8765**. Create the administrator account with the code shown by
   `docker compose logs examgen` (or set `EXAMGEN_ADMIN_EMAIL`/`EXAMGEN_ADMIN_PASSWORD` in `.env`); a welcome
   screen then asks for your institution, professors and courses.

**Accounts**: anyone can request an account with a reason; an administrator approves or rejects it under
**Utilisateurs**. Each teacher gets their own bank and can share questions with everyone or chosen colleagues.
HTTPS deployment and the security model: [docs/securite.md](docs/securite.md) (French).

Your library and PDFs live in the **`mes_examens`** folder next to `docker-compose.yml`.
Stop: `docker compose down`. Update: `git pull` then `docker compose up -d --build`.
Port and data folder: copy `.env.example` to `.env`.

Without Docker: Windows desktop installer and source setup are described in [app/README.md](app/README.md).

## Adapting it
**Settings** covers institution, logo, professors, courses (a course can draw from another course's question
folder, e.g. your `203-NYC-05` using `203-SN3-RE`), file-name pattern, session letters and cover-page text.
The question format is in [docs/question_format.md](docs/question_format.md).

## License
[MIT](LICENSE).
