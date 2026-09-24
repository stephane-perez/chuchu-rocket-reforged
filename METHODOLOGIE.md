# Méthodologie et constats

La règle est celle de *Shufflepuck Café Reforged* : **aucune affirmation sans les octets qui la portent**. Tout ce qui suit est vérifié par un outil du dossier `tools/`, et relancé par `tools/verify.py`.

## 1. L'exécutable : Pack-Ice 2.40

`CHUCHU.TOS` (65 314 octets) est un PRG de 65 282 octets de texte, sans données et sans relocation. C'est l'enveloppe auto-décompressante de Pack-Ice : on y voit la chaîne `Pack-Ice` à text+2, et le flux commence par `ICE!` à l'offset fichier `$1BA`. Les tables du stub (`direkt_tab`, `length_tab`, `more_offset` à text+`$162`) sont exactement celles de la routine Pack-Ice 2.40.

`tools/unice.py` est la transcription de cette routine 68000. Il lit le flux à l'envers, bit par bit, gère le mode « picture » (non utilisé ici), et vérifie que le flux est **consommé exactement** : il reste 0 octet.

Le résultat est un **PRG GEMDOS complet** de 117 289 octets :

| | |
|---|---|
| Texte | $19602 (103 938 octets) |
| Données | $237A (9 082) |
| BSS | $169F0 (92 656) |
| Flags | 6 (fastload + TT-RAM) |
| Relocations | 4 129 (3 858 dans le code, 271 dans les données), toutes dans l'image |

Le code de démarrage à `$42` est le `PCSTART` de **Pure C** : calcul de la pile depuis la basepage, `Mshrink`, puis découpage de la ligne de commande. Le jeu est écrit en C avec **GodLib**, la bibliothèque de Reservoir Gods, dont une version plus récente est publiée sur GitHub (`ReservoirGods/GODLIB`).

## 2. Les données : GodLib LINKFILE (version 2001)

`CHUCHU.LNK` suit un format de GodLib plus ancien que celui des sources actuelles :

```
+$00 U32 $12345678 (ID)   +$04 U32 version (0)   +$08 U32 taille de la FAT ($1663)
+$16 U32 pointeur vers le dossier racine (relatif à la FAT) = $1A
dossier : U16 nbFichiers, U16 nbDossiers, pNom, pFichiers, pDossiers      (16 octets)
fichier : U32 taille, U32 tailleDécompressée, U32 offset, U16 compressé, U16 chargé, pNom  (20 o)
```

L'archive contient 178 fichiers dans le dossier racine, sans trou entre eux. 165 sont compressés en Pack-Ice : chacun est vérifié, avec une taille décompressée exacte et un flux consommé en entier.

| Ext. | Nb | Contenu (vérifié) |
|---|---|---|
| `.BSB` | 123 | Blocs de sprites GodLib `BSBK` : pointeurs, puis pour chaque sprite un en-tête de 16 octets, le masque sur 1 plan, puis 4 plans entrelacés. 1 013 sprites. |
| `.PI1` | 6 | Écrans Degas (4 au format Elite, 32 066 octets). |
| `.GFX` | 12 | `GFX ` v1 : U16 largeur, U16 hauteur, U8 plans, U8 masque. Par groupe de 16 pixels, **le mot de masque vient en premier**, puis les 4 plans. Le bit de masque à 1 signifie transparent. Hypothèse validée visuellement sur `ATARI.GFX`. |
| `.PAL` | 2 | 16 mots de palette STE. |
| `.CHU` | 10 | Niveaux, signature `CHUL` (format non documenté). |
| `.TRI` / `.TVS` | 13 / 1 | Musiques `TSST` et instruments `TSSS` (SID-sound). |
| `SNDREP` | 1 | Le player « SSD-Player by Animal Mine », du **code 68000 chargé à l'exécution**. |
| `.HLP`, `.TXT` | 8 | Textes d'aide et crédits. |
| `FONTMID.IMG` | 1 | Police 8×8 à 1 bit par pixel, premier caractère = espace. |
| `SPLINE.TAB` | 1 | Table de 32 Ko pour l'intro Atari. |

Le chargeur (`Packer_GetType`, à `$1142`) ne décompresse que ce qui commence par `ICE!` ou `ATM5` (Atomik). Un fichier stocké en clair est donc accepté tel quel. C'est ce qui permet de réinjecter un asset modifié sans avoir de compresseur.

## 3. Désassemblage (`tools/trace.py`)

Le désassemblage est **récursif**. On ne suit que ce qui peut s'exécuter :
- le point d'entrée ;
- les cibles des branchements et des appels ;
- les `jsr`/`jmp` absolus relocalisés ;
- les tables de `switch` ;
- les pointeurs relocalisés utilisés comme adresses de code : `#imm`, `lea`, `pea`, ou tables en données. Chacun est d'abord décodé à l'essai et rejeté s'il tombe dans du non-68000 ou chevauche une instruction.

Les tables de `switch` de Pure C prennent trois formes, toutes résolues :
- `cmp.w #N` / `bhi` / `add.w` / `move.w T(pc,dn.w)` / `jmp T(pc,dn.w)` : 20 tables d'offsets sur 16 bits relatifs à T ;
- la forme éparse `moveq #N-1` / `lea T(pc)` / `cmp.w (a0)+` / `dbeq` : 1 table de valeurs suivie d'une table d'offsets ;
- une table de `bra.w` issue d'un module en assembleur : 1.

Au final, **96,4 % du texte est reconnu comme code** : 31 417 instructions, dont 15 fonctions mortes. Pure C lie les modules objets en entier, donc les fonctions GodLib jamais appelées, comme les routines Timer A/B/D, restent présentes dans le binaire. Elles ont été retrouvées par leur prologue. Le reste est constitué de données : tables, bitmaps, chaînes de la lib Pure C et `(C)Xmath by d'ART`.

Pièges de capstone 5 rencontrés et corrigés :
- la taille des décalages mémoire (`asl.w d16(An)`) est fausse : 2 octets au lieu de 4 ;
- en mode 68000, il accepte les modes d'adressage du 68020 (`([bd,An])`) ;
- il classe `(0,An,Xn)` en mode « base displacement », ce qui empêche de filtrer par mode : il faut regarder les champs ;
- il refuse `movec`, utilisé 4 fois pour les caches Falcon/TT : il faut repasser en mode 68030.

**Code auto-modifiant.** Le handler MFP Timer C (`L_03ed2`) contient `jsr $12345678` et `jmp $01234568`. Ce sont des valeurs bidon, que `Mfp_HookIntoTimerC` et `Mfp_InstallStandardTimerC` écrasent à l'exécution. Le source les référence donc en `(L_03f3a+2).l` et `(L_03f4a+2).l`.

## 4. Génération du source (`tools/emit.py`)

**Tout ce qui est une adresse devient un label :**
- cibles de branchement ;
- opérandes relatifs au PC ;
- valeurs relocalisées dans le code (`#label`, `(label).l`) et dans les données (`dc.l label`) ;
- entrées des tables de `switch` (`dc.w L_x-J_base`) ;
- cibles situées au milieu d'une instruction (`label+n`).

Les données restent en `dc.b`, et les chaînes C sont rendues en texte.

Particularités de vasm à respecter :
- `-no-opt` et des tailles explicites partout (`bra.s`/`bra.w`), sinon vasm optimise et l'identité est perdue ;
- les adresses courtes au-delà de `$8000` s'écrivent `$ffff8240.w` ;
- les opérations de bit prennent `.l` sur un registre de données et `.b` en mémoire ;
- `mc68030`/`mc68000` autour des `movec` ;
- `-nosym`, et `-tos-flags=6` pour retrouver l'en-tête d'origine.

Annotations automatiques :
- 30 appels GEMDOS, BIOS et XBIOS nommés ;
- registres matériels et vecteurs système ;
- 12 fonctions reconnues en comparant les séquences d'instructions aux sources assembleur de GodLib (`tools/godlib_match.py`) : Video_SaveRegsST/STE/Falcon, IKBD_PopKbdByte, Mfp_*, Audio_SoundChipOff, GemDos_Call_*… Le faible nombre vient de l'écart de version entre la GodLib de 2002 et celle publiée ;
- quelques noms donnés après lecture (`tools/names.txt`). Ceux suffixés « nom supposé » dans le source restent des hypothèses.

## 5. Vérifications

| Test | Résultat |
|---|---|
| Aller-retour du code : source → vasm → PRG | **Identique** à l'original décompressé (117 289 octets, en-tête et relocations compris). |
| Aller-retour des données : PNG/fichiers → `CHUCHU.LNK` | **Identique** (242 134 octets). |
| Aller-retour des assets : binaire → PNG → binaire | 178/178 fichiers identiques. |
| Test de décalage : 16 octets de padding avant 876 des 897 débuts de fonction, soit +14 016 octets de code | S'assemble et tourne dans Hatari. Les 21 frontières restantes sont franchies par un déplacement sur 8 bits, qu'un padding ferait déborder. |
| Exécution (Hatari 2.4.1, STE, EmuTOS 1.4) de l'original, de la version reconstruite et de la version décalée | Intro, titre, menu, puis **mode démo à 4 IA** et retour au menu, pour les trois. Comparaison image par image (MD5) entre reconstruite et décalée : 1 803/1 839 images identiques, et les écarts sont des images isolées dues à l'échantillonnage de l'AVI, jamais une divergence durable. |
| Modification `SKIP_INTRO` + bandeau sur le titre | Démarre directement sur l'écran titre modifié, puis enchaîne menu, démo et menu. |

## 6. Carte du code (premiers repères)

| Adresse | Nom | Rôle |
|---|---|---|
| `$00000` | `entry` | `jmp PureC_Start` |
| `$00042` | `PureC_Start` | Démarrage Pure C |
| `$0a996` | (`L_0a996`) | **Machine à états principale** (état dans `gAppState`) : 0 = démarrage (intro Atari, logos, titre), 1 = logos + titre (retour de la démo), 2 = front-end… |
| `$0a394` | `Intro_LogosAndTitle` | RGLOGO.PI1, puis SONICTM.PI1, puis TITLE.PI1, avec des fondus |
| `$0d4fc` / `$0d724` / `$0d5cc` | `AtariIntro_Load` / `_Run` / `_Free` | Intro Atari (ATARI.GFX, FUJI.GFX, BALL.BSB…) |
| `$0aec2` | `LinkFile_Load` (supposé) | Chargement d'un fichier de CHUCHU.LNK |
| `$0392a` | `Ice_Depack` | Décompresseur Pack-Ice de GodLib |
| `$03d9e`–`$03f68` | `Mfp_*` | Installation des timers MFP et du handler Timer C auto-modifiant |

## 7. Limites et suite

- **3,6 % du texte reste en `dc.b`.** C'est surtout des tables, mais aussi quelques fragments de code jamais atteints (bibliothèque Pure C, flottants de Xmath). S'ils contiennent des références relatives au PC, elles ne sont pas des labels. Pour modifier ces zones, il faut d'abord les faire reconnaître comme code, via `names.txt` ou une graine dans `trace.py`.
- **Environ 870 fonctions portent encore un nom `F_xxxxx`.** Le nommage progressif se fait désormais dans `src/chuchu.s` par rechercher-remplacer, puisque c'est lui le fichier maître.
- **Formats à documenter** : niveaux `CHUL` (point d'entrée idéal pour créer des niveaux), musiques `TSST`/`TSSS`.
- **Compresseur Pack-Ice** : il n'est pas nécessaire. S'il manque de la place sur disquette, on peut recompresser l'exécutable avec Pack-Ice sur ST, ou écrire un compresseur compatible.
- **Autres configurations** : Hatari en mode STF avec TOS 1.x, et Falcon, n'ont pas encore été testés.

## 8. Performances

### Mesurer d'abord

- **Profil CPU.** Le profileur de Hatari (`profile on`) est piloté par deux points d'arrêt sur le compteur de VBL, qui encadrent la démo à 4 IA (VBL 4100 à 5700 sur STE, soit 32 s). Les cycles sont ensuite agrégés par fonction et par bloc, grâce à un fichier de symboles tiré des labels du source (`perf/profile.sh`).
- **Cadence réelle.** Le gestionnaire VBL (`Video_UpdateRegsSTE` sur STE, `Video_UpdateRegsST` sur ST) programme l'adresse vidéo quand le jeu remet à zéro un drapeau (`tas`). L'instruction qui suit ce `tas` marque donc chaque image affichée. Un point d'arrêt en mode `:trace` relève le VBL correspondant ; un second, sur le rendu des flèches (`Arrows_Draw`), distingue la partie des menus (`perf/fps.sh`).
- **Le jeu n'est pas verrouillé** sur une cadence fixe. Chaque image prend 2, 3 ou 4 VBL selon la charge, donc tout cycle gagné se voit.
- **Le hasard de la démo dépend du rythme des images** : une version plus rapide ne joue pas les mêmes niveaux. On compare donc des moyennes sur environ 6 parties (≈12 600 VBL de jeu), jamais des images une à une.

### Profil de l'original (STE, partie)

| Part du CPU | Où | Quoi |
|---|---|---|
| **22,7 %** | `L_01daa` (`AudioMixer_MixChunk`) | **Mixeur DMA** : 2 voies, 8 bits → stéréo 50 kHz, tampon circulaire de 8 Ko, appelé à chaque VBL. |
| 12,6 % | `Vbl_Wait` | Attente de VBL (temps libre). |
| 6,1 % + 2,8 % | `Board_RestoreDirtyCells`, `Board_RestoreDirtyBorder` | Restauration du décor 16×16 sous les sprites (32 `move.l d16(An),d16(An)` par case). |
| 5,9 % | `Mice_Draw` | Sprites des souris et chats au blitter. |
| 4,6 % | `L_15748` | Flèches masquées, 4 plans. |
| ~4 % | `Time_ToTicks`/`Time_FromTicks` + `_lmul`/`_uldiv` | Chronomètre : conversions durée ↔ ticks de 1/200 s à chaque image. |
| 6 % + 1 % | RAM hors programme | Lecteur de musique SID (`SNDREP`) et ses interruptions. |

Des points d'arrêt conditionnels sur les drapeaux d'activité des voies ont montré que **les 1 990 appels du mixeur pendant la démo se font avec les deux voies muettes**. Le jeu mélangeait du silence à 50 kHz.

Sur STF, il n'y a pas de son DMA, donc pas de mixeur. Les sprites sont dessinés par le CPU (`L_0293e`, 15 %), et l'attente de VBL représente 19 %.

### Optimisations retenues (`-D OPTIM`)

- **`OPT_MIXER`.** Une voie muette pointe sur un tampon de silence alloué par `calloc` (`Memory_ScreenCalloc`, puis `Memory_Clear`), et la table de volume vaut 0 pour un échantillon nul. Deux voies muettes donnent donc exactement 0. Dans ce cas, le mixeur écrit des zéros avec `move.l`, puis **plus rien** une fois les 8 Ko du tampon entièrement à zéro (compteur `Opt_SilentBytes`, remis à 0 dès qu'une voie joue). Le tampon audio est identique à l'original.
- **`OPT_TIME`.** `h×720000 = (h×11250)<<6` avec un seul `mulu.w`. Pour la division non signée, `x/720000 = (x>>6)/11250` exactement, sans débordement puisque le quotient reste < 5966, et le reste vaut `(reste<<6)|(x&63)`. Puis `divu.w #12000` et `divu.w #200`. Cela supprime la boucle bit à bit de 16 tours de `_uldiv`, déclenchée par un diviseur ≥ 65 536.

### Preuve d'équivalence (`tools/difftest.py`)

Les deux builds sont assemblés avec leurs symboles, relogés et chargés dans Unicorn (modèle 68000). Chaque routine est appelée avec les mêmes entrées, puis on compare les registres de résultat, les registres préservés (d3-d7/a2-a7) et la mémoire écrite.

| Routine | Test | Résultat |
|---|---|---|
| `Time_ToTicks` | 70 000 durées, dont toutes les combinaisons h×m | Identique |
| `Time_FromTicks` | 80 000 valeurs : limites, durées réalistes, **négatives**, 32 bits aléatoires | Identique |
| `AudioMixer_MixChunk` | 400 appels successifs sur le tampon circulaire (coupure au bouclage comme dans `L_01cca`, 75 avec voix actives, échantillons et volumes aléatoires) | Tampon identique après chaque appel |

Le banc a été validé par **mutation** : `#200` changé en `#201` donne 69 707 différences, et un seuil de silence de 4 Ko au lieu de 8 Ko donne 268 appels en échec. La routine d'origine a en plus été confrontée à un calcul Python de `divmod`.

### Résultats

| Machine | Version | Images/s en jeu | Images en 2 VBL (25 im/s) |
|---|---|---|---|
| STE | Original | 16,5 | 19 % |
| STE | `OPT_MIXER` | 21,0 | 70 % |
| STE | `OPTIM` | **21,9 (+33 %)** | **77 %** |
| STF | Original | 18,0 | 35 % |
| STF | `OPTIM` | **18,9 (+5 %)** | 43 % |

Un contrôle visuel sur STE et STF (titre, menu, partie, retour au menu) ne montre aucun défaut. Les cases en relief noir et blanc visibles sur certains niveaux sont les trous (`HOLE.BSB`).

### `OPT_BLIT` : restauration du décor au blitter

`Board_RestoreDirtyCells` restaure les cases intérieures du plateau, et `Board_RestoreDirtyBorder` les cases de bord. Une case fait 16 lignes × 8 octets, avec un pas de ligne de 160 et un pas de rangée de `$A00`. Le CPU copie chaque case avec 32 `move.l d16(An),d16(An)`, soit environ 1 000 cycles.

- **Condition.** Le chemin blitter n'est pris que si `gSystemBLT` vaut 1. Ce drapeau vaut `(Blitmode(-1)>>1)&1`, calculé au démarrage par `System_CalcBLT`, et c'est lui qui sert déjà au jeu pour choisir ses routines de sprites au blitter. Sur STF, c'est donc le code CPU d'origine qui s'exécute, inchangé.
- **Copie.** HOP = source, OP = 3, masques `$FFFF`, skew 0, incrément X de 2, incrément Y de `162 − 8n`, Y count de 16. Les cases sales consécutives d'une rangée sont regroupées en une seule opération de n cases. Le blitter démarre en mode partagé, avec la boucle de relance `bset #7 / nop / bne` que le jeu utilise déjà, ce qui laisse passer les interruptions de la musique. Les registres du blitter modifiés sont sauvegardés puis restaurés.
- **Parcours des bits.** Le masque est lu par décalages `lsr` : on saute les zéros, on mesure chaque suite de 1, et on sort dès que le masque est vide. Une première version, qui testait chaque colonne avec `btst`, coûtait environ 3 000 cycles de plus par appel.

**Preuve d'équivalence.**
- `tools/difftest.py` embarque un petit modèle du blitter STE. Il est déclenché quand le code lit le registre de contrôle `$FF8A3C` alors que le bit BUSY est à 1.
- Chaque routine est exécutée en version CPU d'origine et en version blitter, sur 400 cas : masques aléatoires (densités 0, 10, 30, 60 et 100 %, et valeurs 16 bits quelconques) et plateaux source et destination aléatoires. Soit 6 602 + 3 852 copies blitter.
- Le plateau de destination entier, les masques et tous les registres sont **identiques**.
- Mutation : une colonne de trop (`$0fff` → `$1fff`) donne 307 cas en échec sur 400.
- Dans Hatari, la variante `BLIT_CHECK` fait relire chaque copie par le CPU pendant 2 parties de démo : 16 067 copies, 0 différence.

**Mesures (STE, Hatari).**

| Version | Restauration, cycles par appel | Part du CPU | Images/s en jeu | Images à 25 im/s |
|---|---|---|---|---|
| CPU d'origine | 24 575 | 9,7 % | 21,9 | 77 % |
| Blitter, parcours par `btst` | 20 330 | 8,1 % | 22,4 | 82 % |
| **Blitter, parcours par `lsr`** (retenu) | **18 634** | **7,5 %** | **22,4** | **81 %** |

La copie reste limitée par le bus : le blitter lit et écrit chaque mot, en partageant le bus avec le CPU, et copie environ 40 % plus vite que le CPU. Le gain total est de −24 % sur la restauration, soit +2 % d'images/s.

Sur **Mega STe à 16 MHz avec cache**, le CPU copie plus vite alors que le blitter reste à 8 MHz, et le gain peut s'y réduire. `dist/reforged_sans_blit/` (`-D NO_BLIT`) permet la comparaison.

### Pistes restantes (gains estimés, non réalisés)

- **Restauration du décor sur STF** (`Board_RestoreDirtyCells`/`Board_RestoreDirtyBorder`, pas de blitter) : passer en `move.l (a1)+,(a2)+` avec un `lea` par ligne (−12 % sur ces routines, ~1 % au total).
- **Sprites CPU sur STF** (`L_0293e`, 15 %) : pour les décalages de 10 à 15 bits, `swap` + `rol` au lieu de `ror.l` (−6 % sur la boucle, ~1 % au total).
- **Flèches masquées** (`L_15748`, 4,6 %) : dérouler la boucle et utiliser des masques sur 32 bits (−8 à 13 % sur la boucle).
- **Mixeur avec une seule voie active**, fréquent en jeu réel : une boucle à une voie économise ~25 % du coût de mixage pendant les bruitages. Non mesurable dans la démo, qui est silencieuse.
- **Chargements** : le `memset`/`memcpy` de la bibliothèque (`Memory_Clear`, `Memory_Copy`) travaille octet par octet (~40 cycles par octet). Le `calloc` de la table de volume de 64 Ko coûte ~80 ms. Les remplacer par des boucles `move.l` accélérerait les transitions, sans effet pendant la partie.

## 9. Corrections de bugs

### `FIX_MOUSE` : souris coupée en revenant sous GEM

Symptôme signalé sur Mega STe : après avoir quitté, la souris ne bouge plus sous GEM.

**Cause (bug du jeu d'origine).** Au lancement d'une partie, `Controls_ApplyIkbdMode` (`$0664e`) regarde le contrôleur des 4 joueurs. Si aucun n'est « Mouse », il appelle `Ikbd_JoystickMode` (`$00bbc`), qui envoie `$12` (souris coupée) et `$14` (joystick en mode événements) à l'IKBD. Sinon, il appelle `Ikbd_MouseMode` (`$00bce`), qui envoie `$08`. La routine de sortie `Game_Exit` (`$0ae7e`), elle, rend le vecteur ACIA au système via `Ikbd_DeInit` mais **n'envoie jamais `$08`**. Après une partie au joystick, au clavier ou avec la démo à 4 CPU, la souris reste donc coupée.

**Preuve.** Hatari est piloté au clavier par sa FIFO de commandes (`hatari-event keydown/keyup`), avec le traçage `--trace ikbd_cmds`. Le parcours est : titre, Play, 4p Battle, niveau 1, joueur 1 sur « Joystick 0 », partie, F10, Undo ×2, Quit.

| Version | Dernières commandes IKBD en revenant sous GEM |
|---|---|
| `orig/CHUCHU.TOS` (original compressé) | `TurnMouseOff`, `ReturnJoystickAuto` : souris coupée |
| Reconstruite sans option | identique à l'original |
| `REFORGED` | `TurnMouseOff`, `ReturnJoystickAuto`, **`RelMouseMode`** |

Le bug ne dépend donc pas des optimisations, mais du contrôleur utilisé pendant la dernière partie.

**Correction.** Dans `Game_Exit`, avant `Ikbd_DeInit`, un appel à `Ikbd_MouseMode` renvoie `$08` (souris relative), le mode standard du bureau. `$14` (joystick en mode événements) est aussi le mode par défaut du TOS, et le seuil et l'axe Y de la souris ne sont pas modifiés par `$12`. Cette seule commande suffit donc à rétablir l'état du bureau.

## 10. Validation sur machine réelle (Mega STe)

| Version | Résultat |
|---|---|
| `reconstruit/` | Fonctionne à 8 et 16 MHz. |
| `optim/` (première version optimisée) | Fonctionne à 8 et 16 MHz ; les sprites s'affichent plus vite. |
| `reforged/` (`OPTIM` + `OPT_BLIT` + `FIX_MOUSE` + bandeau) | Les animations paraissent nettement plus rapides (ressenti, non mesuré). **La souris est bien réactivée en quittant le jeu.** |

Les gains mesurés dans Hatari (§8) et le correctif de souris (§9) sont donc confirmés sur le matériel d'origine.

## 11. Nommage, réglages et carte complète

### Nommer sans rien casser

Toutes les étiquettes ont été renommées par `tools/rename.py`, à partir de fichiers `analysis/*.map` (une ligne `ANCIEN NOUVEAU` par renommage, des lignes `@NOM texte` pour le bloc de commentaires `;;` placé au-dessus). Après chaque passe, l'outil reconstruit le jeu et vérifie qu'il reste **identique à l'octet près** ; il assemble aussi les variantes `REFORGED`, `REFORGED+BLIT_CHECK` et `OPTIM+SKIP_INTRO`. Un renommage ne peut donc pas changer le comportement.

- **Logique du jeu** (`names_game_logic*.map`) : manche, créatures, flèches, fusées, roulette, IA, niveaux, chronomètres, saisie.
- **Carte complète** (`names_map_1` à `names_map_9`) : couche système GodLib (noms repris des sources GodLib quand la routine y correspond), modules de jeu, modules de rendu, bibliothèque graphique et runtime Pure C. Les **907 fonctions** ont maintenant un nom et un bloc `;;` (ce qu'elle fait, ce qu'elle reçoit, ce qu'elle rend).
- Les noms sont en anglais, au format `Module_Action`, `gVariable`, `Table`. La table des symboles TOS coupe les noms à 22 caractères : les 22 premiers caractères de chaque nom sont uniques (`names_map_7_fixes.map`), sinon le profilage et `difftest.py` confondraient deux fonctions.
- Chaque module suit le même cycle de vie, appelé par des répartiteurs : `*_Init` (`Game_InitModules`), `*_RoundBegin` (`Round_InitModules`), `*_SetupForLevel` / `*_ResetForLevel` (`Round_SetupLevel`), `*_LevelReset` (`Round_CleanupLevel`), `*_RoundEnd`, `*_DeInit`. Beaucoup de ces points d'entrée sont vides (`*Stub`) : ils viennent du code C d'origine.

Le nommage a corrigé quelques hypothèses. La table appelée d'abord `AiReactionFrames` ne contient pas des délais : elle dit **vers quelle fusée** chaque joueur ordinateur envoie les chats en « cat soccer » et pendant « Cat Mania » (`AiCatTargets` : 0→2, 1→3, 2→0, 3→1). Les vrais délais de réflexion de l'IA sont juste avant (`AiThinkDelays`). Autre découverte : l'option « speed » du menu est enregistrée mais **jamais lue** par le jeu.

`tools/codemap.py` génère `CODE_MAP.md` à partir du source : chaque fonction, classée par couche et par module dans l'ordre du programme d'origine (Pure C garde chaque fichier `.C` d'un seul tenant), avec son adresse d'origine et la première phrase de son bloc `;;`, puis les variables et tables nommées. `rename.py` le régénère après chaque passe.

### Les réglages (`src/settings.s`)

Les constantes de jeu repérées pendant le nommage sont sorties du code dans `src/settings.s`, inclus en tête de `chuchu.s`. Le code les utilise par leur nom (`moveq #SCORE_GOLD_MOUSE,d1`, `dc.w SPAWN_DELAY_NORMAL,...`), si bien qu'avec les valeurs livrées l'assemblage redonne exactement les mêmes octets.

- **Contrôle des plages.** Une macro `CHECK_RANGE` arrête l'assemblage avec un message clair si une valeur sort de ce que le code accepte (par exemple 1 à 127 pour une valeur chargée par `moveq`, 1 à 3 flèches par joueur, qui correspondent aux 3 emplacements de la fiche joueur).
- **Textes du menu.** Les textes des choix TIME et WINS sont des macros, pour qu'on puisse les changer avec les valeurs.
- **Alignement.** Changer la longueur d'un texte décale toutes les données qui suivent, et une donnée `.w` ou `.l` à une adresse impaire fait planter un 68000. 274 directives `even` ont donc été placées devant chaque donnée qui se trouve à une adresse paire juste après des octets : elles n'émettent rien dans la disposition d'origine, et rétablissent l'alignement si un texte change de longueur.
- **Options par défaut.** La table `DefaultOptions` a été réécrite en `{dc.w numéro, dc.l valeur}` pour que les valeurs par défaut soient lisibles et réglables. Elles ne servent que sans `CHUCHU.SAV`.

**Essai dans Hatari.** Une version avec des réglages changés (manches de démo de 25 s, souris plus rapides, 2 flèches par joueur, 3 points par souris, IA plus rapide, texte « 2 MIN » de 5 caractères au lieu de « 1 MINUTE ») s'assemble et tourne : chrono à 0:18 puis 0:01, scores en multiples de 3 (59 = 50 + 3 × 3 avec une souris dorée), pas de plantage. En fin de manche, la démo reste sur l'écran « Winner! » : une version où seule la durée de démo change fait la même chose : c'est donc le code d'origine qui se comporte ainsi en fin de manche, pas les réglages.
