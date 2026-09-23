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
| `$0a996` | (`L_0a996`) | **Machine à états principale** (état dans `B_2831e`) : 0 = démarrage (intro Atari, logos, titre), 1 = logos + titre (retour de la démo), 2 = front-end… |
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
