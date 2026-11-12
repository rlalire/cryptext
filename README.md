# Cryptext

Extension Blender (4.2 → 5.x) : des centaines de chiffres en 3D, dessinés avec la police **Cryptext25**, apparaissent depuis le noir, flottent, s'immobilisent, s'agitent puis se repoussent hors de l'image. Seul reste le nombre choisi, qui pivote pour révéler son mot (la police est dessinée pour que les chiffres retournés se lisent comme des lettres : `10106` → `gold`).

Composition carrée 1024×1024, fond noir, chiffres en or (argent ou blanc au choix).

## Installer

```bash
cd addon/cryptext && mkdir -p ../../dist && zip -qr ../../dist/cryptext-$(grep '^version' blender_manifest.toml | cut -d'"' -f2).zip . -x "__pycache__/*"
```

Puis dans Blender : Édition › Préférences › Extensions › Installer depuis le disque, et choisir le zip.

## Utiliser

Vue 3D › barre latérale (N) › onglet **Cryptext** › **Créer / reconstruire la scène**.

| Panneau | Réglages |
|---|---|
| Cryptext | nombre final, police (vide = Cryptext25 fournie) |
| Position des caractères | espacement global et décalage X / Y de chaque caractère du nombre (ex. coller le 1 et le 0 pour former un « d » une fois retourné) ; boutons « Avant le pivot » et « Voir le mot » |
| Zone ronde (hélice) | pour une hélice holographique : le nuage remplit le disque inscrit dans l'image, chaque chiffre s'éteint avant de toucher le bord, et le nombre est réduit si besoin pour tenir dans le cercle pendant tout le pivot ; rayon utile, fondu au bord. Un cercle guide (non rendu) s'affiche dans la vue caméra |
| Nuage | quantité de chiffres, graine, tailles, débord, profondeur avant/arrière, largeur du nombre, dégagement |
| Apparition | début, étalement, durée du fondu depuis le noir, profondeur d'arrivée |
| Flottement | amplitude, rotation, vitesse, échelle du bruit, instant d'immobilité, durée de l'immobilisation, inclinaison au repos |
| Agitation | début, montée, amplitude, rotation, vitesse |
| Répulsion | début, durée, étalement, distance, vrille de sortie |
| Nombre | taille dans la foule (il grandit pendant la répulsion), agitation, durée de croissance |
| Pivot | début, durée, mode |
| Matière et rendu | or / argent / blanc, rugosité, épaisseur, biseau, profondeur de champ, reflets, flou de mouvement |
| Durée | images/s, fin ; « Ajuster la durée » = fin du pivot + 4 s |

Les réglages de timing sont des entrées du modificateur Geometry Nodes : ils se modifient en direct et s'animent (clic droit › Insérer une image clé). Le bouton horloge à côté d'un début place la tête de lecture à cet instant.

Timing par défaut (25 i/s) : apparition 0–20 s, immobile à 30 s, agitation à 31 s, répulsion 33–38,5 s, pivot 41–44 s, fin 48 s.

### Modes de pivot

- **0 · Axe Y, sens horaire** (par défaut) : l'axe Y est l'axe de visée de la caméra. Le nombre tourne de 180° dans le plan de l'image et se lit retourné (`10106` → `gold`).
- **1 · Axe Y, sens antihoraire** : même chose dans l'autre sens.
- **2 · Bascule 3D (axes X + Z)** : double rotation en profondeur, qui arrive au même résultat.

## Fonctionnement

- `core.py` : glyphes 3D (un maillage biseauté par caractère, collection « Cryptext glyphes » hors scène), nuage de points (échantillonnage « meilleur candidat » dans le volume vu par la caméra, chiffres du nombre placés d'après la mise en page réelle de la police), réseau Geometry Nodes piloté par le temps de la scène, matière (attribut `fondu` → apparition depuis le noir), monde (reflets pour le métal, invisible à la caméra), lumières, caméra, rendu Eevee.
- `ui.py` : réglages, opérateurs et panneaux.
- `tools/render_test.py` : rendu de contrôle sans interface (`CRYPTEXT_CYCLES=1` pour une machine sans GPU).
