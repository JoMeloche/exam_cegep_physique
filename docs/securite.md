# Comptes et sécurité (application web)

L'application web (Docker) demande maintenant une connexion. L'application de bureau (Windows, macOS,
Linux) n'en demande pas : elle n'écoute que sur l'ordinateur lui-même.

## Fonctionnement

1. N'importe qui peut **demander un compte** : nom, courriel, mot de passe et **raison de la demande**.
2. La demande reste **en attente** ; la personne ne peut rien voir ni faire.
3. Un administrateur ouvre **Utilisateurs** (menu de gauche, avec le nombre de demandes en attente),
   lit la raison, puis **approuve** ou **refuse** (avec un motif facultatif que la personne verra).
4. Une fois approuvée, la personne reçoit **sa propre banque de questions**, copiée de la banque de départ.
   Elle configure son établissement, ses professeurs et ses cours au premier accès.

L'administrateur peut aussi désactiver ou réactiver un compte, nommer d'autres administrateurs,
donner un **mot de passe temporaire** (mot de passe oublié) et supprimer un compte refusé.
Chacun change son mot de passe dans **Paramètres → Mon compte**.

## Premier administrateur

Au choix :

- **Dans le navigateur** : au premier démarrage, le serveur affiche un code de configuration.
  ```
  docker compose logs examgen
  ```
  Ouvrez l'application, entrez ce code, votre nom, votre courriel et votre mot de passe.
- **Par le fichier `.env`** : `EXAMGEN_ADMIN_EMAIL` et `EXAMGEN_ADMIN_PASSWORD` (10 caractères minimum).
  Retirez le mot de passe du fichier une fois le compte créé.
- **En ligne de commande** :
  ```
  docker compose exec -u examgen examgen examgen create-admin --email vous@cegep.qc.ca
  ```
  (sert aussi à redevenir administrateur si vous avez perdu l'accès).

Le premier administrateur garde la banque qui était déjà dans `mes_examens` : aucune donnée n'est déplacée.
Les banques des autres enseignants sont dans `mes_examens/users/<numéro>/`.

## Partage de questions

Chaque enseignant peut partager, depuis **Bibliothèque** :
- une question (bouton **Partager** sur la carte) ou **toute sa banque** (bouton en haut) ;
- avec **tous les utilisateurs** approuvés ou avec **certaines personnes** choisies dans une liste.

Les questions reçues apparaissent sous **Partagées avec moi**, en lecture seule, avec le nom de l'auteur.
On peut les **copier dans sa banque** pour les modifier. Dans **Générer**, l'interrupteur
**Questions partagées** permet de piger aussi dans ces questions (désactivé par défaut).
Arrêter un partage retire l'accès immédiatement. Les copies identiques à la banque de départ ne sont pas
répétées quand une banque entière est partagée.

Pour une seule banque commune à tous (département), mettez `EXAMGEN_LIBRARY_MODE=shared` dans `.env`.

## Ce qui protège l'application

| Sujet | Mesure |
|---|---|
| Mots de passe | Argon2id (argon2-cffi), 10 caractères minimum ; jamais stockés en clair |
| Sessions | Jeton aléatoire de 256 bits dans un témoin `HttpOnly`, `SameSite=Lax`, `Secure` en HTTPS ; seul son empreinte SHA-256 est stockée ; expiration après 24 h d'inactivité et 7 jours au maximum ; fermées à la désactivation du compte ou au changement de mot de passe |
| CSRF | Jeton lié à la session, exigé dans l'en-tête `X-CSRF-Token` de chaque écriture ; requêtes d'une autre origine refusées |
| Force brute | 8 essais ratés par compte et 30 par adresse IP par 15 min ; 5 demandes de compte par IP par heure ; réponse 429 |
| Découverte de comptes | Même réponse pour une adresse déjà inscrite ; temps de réponse identique pour un courriel inconnu |
| Accès | Toute l'API exige une session approuvée ; l'écran Utilisateurs exige le rôle administrateur ; chaque enseignant n'accède qu'à sa banque et aux questions qu'on lui a partagées |
| LaTeX | Le serveur choisit le moteur (le chemin LaTeX des Paramètres est ignoré), pas d'exécution de commandes arbitraires (`shell_escape=p`) et aucune lecture ni écriture hors du dossier de compilation (`openin_any=p`, `openout_any=p`) |
| En-têtes | Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, HSTS en HTTPS ; `Cache-Control: no-store` sur l'API |
| Conteneur | Processus sans privilèges (utilisateur `examgen`), `no-new-privileges`, port ouvert sur `127.0.0.1` seulement par défaut |
| Téléversements | Figures limitées à 20 Mo et aux formats png, jpg, pdf, eps |

Les comptes sont dans `mes_examens/.examgen/auth.sqlite3` (permissions 600). Sauvegardez `mes_examens`
au complet.

## Mettre l'application en ligne (HTTPS)

Ne publiez jamais l'application sur Internet en HTTP : les mots de passe circuleraient en clair.

**Avec le Caddy fourni** (certificat Let's Encrypt automatique) :
1. Faites pointer un nom de domaine (ex. `examens.moncegep.ca`) vers le serveur ; ouvrez les ports 80 et 443.
2. Dans `.env` : `EXAMGEN_DOMAIN=examens.moncegep.ca`
3. Lancez :
   ```
   docker compose -f docker-compose.yml -f docker-compose.https.yml up -d
   ```
   L'application n'est alors joignable que par Caddy, en HTTPS.

**Derrière un autre proxy** (nginx, Traefik, celui du cégep) : laissez `EXAMGEN_BIND=127.0.0.1`
(ou un réseau Docker interne), transmettez `Host`, `X-Forwarded-For` et `X-Forwarded-Proto`, et mettez dans
`.env` :
```
EXAMGEN_SECURE_COOKIES=1
FORWARDED_ALLOW_IPS=<adresse IP du proxy>
```
Sans cela, toutes les requêtes semblent venir du proxy et les limites d'essais s'appliquent à tout le monde.

**Sur un réseau local seulement** : `EXAMGEN_BIND=0.0.0.0` rend l'application accessible aux autres
ordinateurs à `http://<adresse-du-serveur>:8765`. C'est acceptable sur un réseau de confiance ; sinon
utilisez HTTPS.

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `EXAMGEN_AUTH` | `1` | `0` désactive les comptes (usage local seulement) |
| `EXAMGEN_ADMIN_EMAIL`, `EXAMGEN_ADMIN_PASSWORD` | vide | Premier administrateur |
| `EXAMGEN_LIBRARY_MODE` | `per-user` | `shared` = une banque commune |
| `EXAMGEN_SECURE_COOKIES` | `auto` | `1` derrière un proxy HTTPS |
| `EXAMGEN_TRUSTED_ORIGINS` | vide | Origines supplémentaires permises (si le proxy réécrit `Host`) |
| `EXAMGEN_SESSION_IDLE_HOURS`, `EXAMGEN_SESSION_MAX_HOURS` | `24`, `168` | Durée des sessions |
| `EXAMGEN_SEED` | `/app/seed` | Banque de départ copiée pour chaque nouvel enseignant |
| `EXAMGEN_AUTH_DB` | `$EXAM_APP_HOME/.examgen/auth.sqlite3` | Base des comptes |

## Limites connues

- Pas de courriel : l'administrateur voit les demandes dans l'application (badge dans le menu) et transmet
  lui-même les mots de passe temporaires.
- Les limites d'essais sont en mémoire : elles repartent à zéro au redémarrage du conteneur.
- Une seule instance du serveur (un seul processus) est prévue.
- Tout utilisateur approuvé voit le nom et le courriel des autres utilisateurs approuvés (liste de partage).
