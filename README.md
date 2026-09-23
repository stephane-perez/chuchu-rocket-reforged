# Chu Chu Rocket (Atari ST) : désassemblé, modifiable, réassemblable

Démontage complet de **Chu Chu Rocket**, build 1.18 LITE (Reservoir Gods, 2002), à partir de `CHUCHU.TOS` et `CHUCHU.LNK`. Le jeu est reconstruit **pour l'Atari ST**. Il ne s'agit pas d'un portage : le code reste du 68000, sous la forme d'un source assembleur complet.

- `src/chuchu.s` (39 000 lignes, syntaxe Motorola/Devpac, assembleur vasm) redonne **l'exécutable identique à l'octet près**.
- `assets/` contient les 178 fichiers de données, dont les graphismes en PNG indexés éditables. Réimportés sans modification, ils redonnent **`CHUCHU.LNK` identique à l'octet près**.
- La source supporte l'édition : le test de décalage (16 octets de padding insérés avant 876 fonctions, soit +14 Ko) tourne dans Hatari exactement comme l'original.

Projet privé, personnel et pédagogique. Le jeu appartient à ses auteurs (Reservoir Gods, concept Sonic Team).

## Construire

Prérequis : Python 3 avec Pillow, et [vasm](http://sun.hasenbraten.de/vasm/) compilé pour la syntaxe Motorola (`make CPU=m68k SYNTAX=mot`), soit `vasmm68k_mot` dans le PATH.

```
python build.py --check          # out/CHUCHU.TOS + out/CHUCHU.LNK, comparés aux originaux
python build.py -D SKIP_INTRO    # variante : sans l'intro Atari ni les logos
python tools/verify.py           # toutes les vérifications (voir METHODOLOGIE.md)
```

Copier `out/CHUCHU.TOS` et `out/CHUCHU.LNK` dans le même dossier, sur disquette, disque dur ou dans le dossier GEMDOS d'Hatari. L'exécutable produit n'est pas compressé : il fait 117 Ko au lieu de 65 Ko, ce qui ne change rien à son fonctionnement.

## Modifier

**Le code.** Modifiez `src/chuchu.s` directement. Tout ce qui est une adresse est un label, donc on peut ajouter ou retirer des instructions n'importe où. Deux règles à respecter :
- un branchement court (`bra.s`, `bne.s`…) a une portée de ±128 octets : passez-le en `.w` s'il ne l'atteint plus (vasm vous le signale) ;
- vasm tourne en `-no-opt` pour rester fidèle à l'octet près : il n'optimise rien à votre place.

La modification de démonstration `SKIP_INTRO` montre la marche à suivre, avec des blocs `ifd`/`ifnd` dans `L_0a9b4` et `Intro_LogosAndTitle`.

**Les graphismes.** Éditez les PNG de `assets/` dans un éditeur qui respecte les **PNG indexés** : GrafX2, Aseprite, Pro Motion, ou GIMP en mode indexé. Relancez ensuite `build.py`. Les fichiers modifiés sont stockés non compressés dans `CHUCHU.LNK`, ce que le chargeur accepte : il ne décompresse que ce qui commence par `ICE!` ou `ATM5`.

| Format | PNG | Convention |
|---|---|---|
| `.PI1` (Degas) | 320×200, 16 couleurs | La palette du PNG est la palette ST. Elle est reconvertie en valeurs STE sur 4 bits. |
| `.BSB` (sprites GodLib) | Planche de sprites côte à côte + `.json` | Indices 0 à 15 opaques, 16 transparent, 17 à 31 transparents avec couleur résiduelle (rare). |
| `.GFX` (image masquée) | Image + `.json` | Même convention que `.BSB`. |

La palette d'affichage des sprites est `BOARD.PAL`, ou `ATARIPAL.PAL` pour l'intro. Seuls les indices comptent.

Exemple : `python mods/title/make.py` ajoute un bandeau sur l'écran titre, écrit avec la police du jeu (`FONTMID.IMG`). Combiné à `-D SKIP_INTRO`, on obtient la version montrée dans `docs/mod_demo.png`.

## Tester dans Hatari

`run/run.sh <dossier> <nb_vbl>` lance le jeu sans écran (STE, 4 Mo, EmuTOS) et enregistre un AVI. Laissé inactif, le jeu passe en **mode démo**, avec 4 joueurs contrôlés par l'IA : c'est un excellent test de non-régression.

## Arborescence

```
src/chuchu.s        le source (maître : c'est lui qu'on édite)
assets/             les données, graphismes en PNG indexés
orig/               vos fichiers originaux (CHUCHU.TOS, CHUCHU.LNK)
build.py            construction
tools/              décompresseur Pack-Ice, LINKFILE, convertisseurs, désassembleur, vérifications
analysis/           résultat du désassemblage (trace.json), noms reconnus
mods/               modifications de démonstration
run/                lanceur Hatari (+ EmuTOS 1.4, GPL)
docs/               captures
METHODOLOGIE.md     comment tout cela a été obtenu et vérifié
```

`tools/setup.py` régénère `src/` et `assets/` depuis `orig/`. **Attention, il écrase vos modifications.** Le projet est versionné avec git : faites `git diff` pour voir ce que vous avez changé.
