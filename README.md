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
python build.py --reforged       # VERSION DE RÉFÉRENCE : optimisée + corrigée + bandeau titre
python build.py -D OPTIM         # optimisations seules (voir ci-dessous)
python build.py -D SKIP_INTRO    # variante : sans l'intro Atari ni les logos
python tools/verify.py           # toutes les vérifications (voir METHODOLOGIE.md)
```

Options d'assemblage, combinables (`-D OPTIM -D SKIP_INTRO`). Sans option, on obtient le binaire original exact :

| Option | Effet |
|---|---|
| `OPTIM` | Active toutes les optimisations `OPT_*`. |
| `OPT_MIXER` | Le mixeur audio DMA (STE) ne mélange plus du silence. |
| `OPT_TIME` | Conversions de durées du chronomètre sans `_lmul`/`_uldiv`. |
| `OPT_BLIT` | Restauration du décor sous les sprites au blitter, s'il est présent (STE, Mega STe, TT, Falcon). Les cases consécutives sont copiées en une seule opération. |
| `NO_BLIT` | Retire `OPT_BLIT` de `OPTIM`, pour comparer sur machine réelle. |
| `FIX_MOUSE` | Corrige un bug du jeu d'origine : la souris restait coupée sous GEM après une partie sans joueur à la souris. |
| `REFORGED` | `OPTIM` + `FIX_MOUSE`. |
| `SKIP_INTRO` | Saute l'intro Atari et les logos. |

`--reforged` ajoute aussi la surcouche d'assets `mods/reforged/` : bandeau « AI REFORGED 2026 » sur l'écran titre, généré par `python mods/title/make.py`. Le dossier `assets/` reste celui de l'original, donc `--check` redonne toujours l'original exact.

Testé sur **Mega STe** (8 et 16 MHz) : les versions reconstruite et optimisée fonctionnent. La version `reforged` donne des animations nettement plus fluides, et la souris est bien réactivée en quittant le jeu.

Gains mesurés dans Hatari sur la démo à 4 IA, environ 12 600 VBL de jeu par mesure :

| Machine | Original | `OPTIM` |
|---|---|---|
| STE | 16,5 images/s, 19 % des images à 25 im/s | **22,4 images/s (+36 %)**, 81 % à 25 im/s |
| STF | 18,0 images/s | **18,9 images/s (+5 %)**, pas de blitter : code CPU d'origine |

Les routines optimisées sont prouvées équivalentes aux originales par `tools/difftest.py`, qui les exécute côte à côte dans un émulateur 68000 (voir METHODOLOGIE.md, §8).

Copier `out/CHUCHU.TOS` et `out/CHUCHU.LNK` dans le même dossier, sur disquette, disque dur ou dans le dossier GEMDOS d'Hatari. L'exécutable produit n'est pas compressé : il fait 117 Ko au lieu de 65 Ko, ce qui ne change rien à son fonctionnement.

## Modifier

**Les règles du jeu.** `src/settings.s` regroupe les valeurs qu'on peut changer sans toucher au code : vitesse des souris et des chats, délais d'apparition, fréquence des souris dorées et violettes, nombre de chats pendant « Cat Mania », nombre de flèches par joueur, durée de vie des flèches, points marqués, durée des événements de la roulette, durée des manches, rapidité des joueurs ordinateur, options par défaut et choix du menu OPTIONS (valeurs et textes). Chaque valeur est expliquée dans le fichier ; l'assemblage s'arrête avec un message si une valeur sort de sa plage. Avec les valeurs livrées, on obtient toujours le jeu original à l'octet près.

Deux remarques : les options du menu sont enregistrées dans `CHUCHU.SAV`, qui l'emporte sur les valeurs `DEFAULT_*` (supprimez-le pour les voir) ; et avec une durée de manche de démo plus courte que la démo elle-même, la démo reste bloquée sur l'écran « Winner! » de fin de manche (c'est le code d'origine qui se comporte ainsi, pas le réglage).

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

Les exécutables construits sont dans `dist/` : `reforged/`, `reforged_sans_blit/` (`--reforged -D NO_BLIT`) et `reconstruit/`.

## Arborescence

```
src/chuchu.s        le source (maître : c'est lui qu'on édite)
src/settings.s      les réglages du jeu (vitesses, scores, durées...)
assets/             les données, graphismes en PNG indexés
orig/               vos fichiers originaux (CHUCHU.TOS, CHUCHU.LNK)
build.py            construction
tools/              décompresseur Pack-Ice, LINKFILE, convertisseurs, désassembleur, vérifications
analysis/           résultat du désassemblage (trace.json), noms reconnus,
                    renommages et commentaires appliqués au source (*.map)
mods/               modifications de démonstration
run/                lanceur Hatari (+ EmuTOS 1.4, GPL)
perf/               profilage et mesure de cadence dans Hatari
docs/               captures
METHODOLOGIE.md     comment tout cela a été obtenu et vérifié
GAME_LOGIC.md       comment le jeu fonctionne, et où le trouver (en anglais)
CODE_MAP.md         carte complète : chaque fonction et variable (en anglais)
```

Le source est entièrement nommé et commenté en anglais : les 907 fonctions ont un
nom et un bloc d'explication `;;`. Pour s'y retrouver sans lire l'assembleur :
`GAME_LOGIC.md`, puis `CODE_MAP.md`, puis `python tools/xref.py NOM` (qui appelle
quoi, quelles variables). `python tools/rename.py FICHIER.map` renomme des
étiquettes et ajoute les commentaires d'en-tête, vérifie que l'exécutable reste
identique, puis régénère `CODE_MAP.md` (`python tools/codemap.py`).

`tools/setup.py` régénère `src/chuchu.s` et `assets/` depuis `orig/`, sous la forme brute du premier désassemblage. **Il écrase tout le travail fait sur le source** (noms, commentaires, réglages, optimisations) : il ne sert plus qu'à repartir de zéro. Le projet est versionné avec git : faites `git diff` pour voir ce que vous avez changé.
