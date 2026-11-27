# Sécurité / Security

## Versions prises en charge / Supported versions

Seule la dernière version publiée et la branche `main` reçoivent des correctifs de sécurité.
Only the latest release and the `main` branch receive security fixes.

## Signaler une vulnérabilité / Reporting a vulnerability

**Ne publiez pas de ticket public.** Utilisez le signalement privé de GitHub :
[Security → Report a vulnerability](https://github.com/JoMeloche/exam_cegep_physique/security/advisories/new).

**Please don't open a public issue.** Use GitHub's private reporting:
[Security → Report a vulnerability](https://github.com/JoMeloche/exam_cegep_physique/security/advisories/new).

Indiquez / Include:

- la version et l'installation (Docker, Windows, macOS, Linux) / version and install type;
- les étapes pour reproduire et l'impact / steps to reproduce and impact;
- une piste de correctif si vous en avez une / a suggested fix if you have one.

Nous accusons réception sous 7 jours et vous tenons informé jusqu'à la correction.
We acknowledge reports within 7 days and keep you updated until it is fixed.

## Bon à savoir / Good to know

- L'application compile du LaTeX : n'importez que des questions de sources fiables, comme pour tout fichier `.tex`.
  The app compiles LaTeX: only import questions from sources you trust, as with any `.tex` file.
- L'application web n'a pas d'authentification intégrée pour l'instant : ne l'exposez pas directement sur Internet.
  Placez-la derrière un réseau privé, un VPN ou un proxy avec authentification.
  The web app has no built-in authentication yet: don't expose it directly to the Internet. Keep it on a private
  network, behind a VPN or an authenticating reverse proxy.
