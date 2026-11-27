# Revue des questions 203-SN1-RE (113 questions)

Vérifications faites : validateur de l'app (5 tirages, compilation) ; 150 tirages par question (contraintes,
valeurs non finies) ; comparaison automatique, sur 40 tirages, entre le corrigé (`parts`) et chaque réponse
finale du `.sol.tex` ; relecture de la physique, des plages de valeurs, du français, des unités et des QCM.

Résultat : 113/113 valides. Les corrigés et les solutions concordent partout ; aucune erreur de physique trouvée
dans les formules.

## Corrections

| Question | Problème | Correction |
|---|---|---|
| Cinematique_1D/cin_poursuite_police | Voiture de police jusqu'à 280 km/h | vc : 70 à 110 km/h (police 140 à 220 km/h) |
| Cinematique_1D/cin_metro_trois_phases | Métro jusqu'à 115 km/h | contrainte a1·t1 < 22 m/s |
| Frottement_plan_incline/frot_caisse_poussee | Caisse lancée à 60 m/s, glisse 520 m | contrainte : vitesse au lâcher entre 1 et 4 m/s (glissement ≤ 3.7 m) |
| Frottement_plan_incline/frot_traineau_neige | Accélération jusqu'à 8.4 m/s² | contrainte a < 3 m/s² |
| Lois_Newton/newt_fusee_decollage | Jusqu'à 6 g, altitude 72 km | contrainte F < 3·M·g (altitude max ≈ 10 km) |
| Lois_Newton/newt_traineau_corde | Enfant qui tire un traîneau à 33 m/s | contrainte v finale < 8 m/s |
| Quantite_mouvement/qm_pendule_balistique | Balle jusqu'à 1500 m/s | contrainte 150 à 900 m/s |
| Quantite_mouvement/qm_wagons_accroches | Wagons de 2 t | 15 à 40 t |
| Quantite_mouvement/qm_collision_intersection | Unité `deg` dans le corrigé | `\degree` |
| Quantite_mouvement/c_qm_camion_voiture | Doublon de c_newt_collision_camion (3e loi) | réécrite : comparaison des Δp (impulsion) |
| Rotation/rot_patineuse | Jusqu'à 9.5 tr/s | contrainte ω finale < 40 rad/s |
| Rotation/rot_volant_inertie | Vitesse en périphérie 500 m/s, arrêt en 71 min | contraintes ωR < 200 m/s, arrêt < 10 min |
| Travail_energie/te_boucle_montagnes_russes | Normale jusqu'à 15 g | contrainte h < 4R |
| Travail_energie/te_ressort_lanceur | Bille de jouet à 24 m | contrainte h max < 5 m |
| Travail_energie/te_caisse_tiree_angle | Caisse à 13.5 m/s | contrainte v finale < 6 m/s |
| Projectile/c_proj_temps_vol_angle | « Les deux restent le même temps » | « Ils restent dans les airs pendant la même durée » |
| 6 solutions avec conversion km/h (cin_freinage_auto, cin_poursuite_police, frot_derapage_route, circ_bosse_creux, circ_virage_plat, proj_colis_avion) | `\qty{\vsi{v}}` affichait 13.8888888889 m/s | `\qty[round-mode=figures,round-precision=4,drop-zero-decimal]{...}` → 13.89 m/s, 25 m/s |

À noter pour l'app : `drop-zero-decimal` exige siunitx ≥ 3.0.
