# How the game works (no assembly needed)

This guide explains how Chu Chu Rocket works and where to find each part in
`src/chuchu.s`. The source is named and commented in English.

Every function has a block of `;;` comments above it. The block says what the
function does, what it receives and what it returns. To find your way, search
for a name in the file (Ctrl+F) and read that block. `CODE_MAP.md` lists every
function by module, and `src/settings.s` holds the values you can change
without touching the code.

## Finding your way in the source

```
python tools/xref.py Round_UpdateLogic          # callers, callees, globals used
python tools/xref.py Round_UpdateLogic --tree 2 # call tree below it
python tools/xref.py Mouse_Spawn --up 3         # what leads to this function
python tools/xref.py --global gMiceCount        # who reads / writes a variable
python tools/xref.py --hot 30                   # most called functions during a game
python tools/xref.py Creature_Move --src        # print the code of the function
```

Naming conventions:

| Form | Meaning | Example |
|---|---|---|
| `Module_Action` | function | `Mouse_Spawn`, `Arrows_Age` |
| `gName` | global variable (BSS, cleared at start-up) | `gMiceCount` |
| `CapitalisedName` | table of constant data | `MouseSpeeds` |
| `UPPER_CASE` | setting from `src/settings.s` | `ARROW_LIFETIME` |
| `B_xxxxx` / `D_xxxxx` | variable / data not named yet (xxxxx = original address) | |
| `L_xxxxx` / `J_xxxxx` | local label (a jump target inside a function) | |

The renames are listed in `analysis/*.map` and applied by `tools/rename.py`,
which checks that the executable stays identical to the byte.

## Program flow

```
ProgramEntry
└─ Game_Main
   ├─ Game_Init                       (system: video, keyboard, sound, CHUCHU.LNK)
   ├─ App_FrontEndStateMachine        (runs everything else)
   │  ├─ Atari intro, Intro_LogosAndTitle (logos, title screen)
   │  ├─ Render_LoadAll, Game_InitModules (once: graphics, tables, levels, players)
   │  ├─ SaveFile_Load                (options and records from CHUCHU.SAV)
   │  ├─ FrontEnd_Run                 (menus)
   │  ├─ Demo_Run                     (demo; saves and restores the options)
   │  ├─ Round_Run                    (one round)
   │  │  ├─ Round_SetupLevel          (board, duration, spawners)
   │  │  └─ loop, once per frame:
   │  │     ├─ Round_UpdateLogic      (the game logic)
   │  │     ├─ Render_Frame / Hud_Update
   │  │     └─ Sound_Update
   │  └─ SaveFile_Save                (at exit)
   └─ Game_Exit                       (back to GEM, mouse included)
```

`Round_UpdateLogic` runs one frame of the game according to `gRoundState`:
4 = normal play, 2/3 = puzzle running / fast forward, 6 = roulette, 9 = demo.

During normal play, every frame: arrows get older (`Arrows_Age`), cats move
(`Cats_Update`), mice move (`Mice_Update`), spawners release creatures
(`Spawners_Update`), players act (`Players_Update`: keyboard, joystick or
computer), the clock runs (`Timers_Update`) and the computer players update
their path maps (`Ai_UpdatePathMaps`).

## The board

12 columns × 9 rows. The board wraps around: leaving on the left enters on the
right. Each tile is 2 bytes in the level file:

- byte 0, bits 0-3: walls (1 left, 2 right, 4 down, 8 up);
- byte 0, bits 4-6: type ($10 spawner, $20 rocket, $30 hole, $40 arrow);
- byte 1, bits 0-1: direction (0 left, 1 right, 2 down, 3 up).

`Level_GetCell(row, column)` returns the address of a tile.

## Level files (`.CHU`)

Ten files are loaded at start-up by `Levels_LoadAll` (table `LevelFileNames`):
sets 0-3 puzzles, 4 stage challenge, 5 normal battle, 6-9 downloadable levels.
A file is `"CHUL"` + number of levels (long) + 25 levels of 250 bytes. A level
is a 34-byte header followed by 9 × 12 tiles of 2 bytes.

| Header | Content |
|---|---|
| +$08 | title (zero-terminated text) |
| +$1d | objective: 0 puzzle, 1 battle, 2 get the mice, 3 feed the cat, 4 hundred mice, 5 cat soccer, 6 win 100 |
| +$1e..+$21 | arrows available in a puzzle (one byte per direction) |

The 25 battle levels have no title in the file: at load time the game gives
them the names of the team (`LevelCreditNames`: ReservoirGods, MrPink...).
`Level_BuildWallMask` builds a wall mask of every level, used to draw the
level preview.

## Creatures

Mice and cats share the same 26-byte record and the same movement function,
`Creature_Move`. The record holds the position in 16.16 fixed point (in
tiles), the direction, the kind (1 mouse, 2 gold mouse, 3 purple mouse, 4 cat)
and the state. When a creature reaches the centre of a tile, its new direction
is read from `gTurnTable[direction][walls]`. `TurnTable_Build` fills this table
at start-up: blocked ahead, the creature turns right; blocked on the right
too, it turns left; blocked on three sides, it turns back. An arrow replaces
the direction before this lookup.

Speeds per frame (`MouseSpeeds`, `CatSpeeds`, in 1/65536 of a tile): mice
$1200 / $2400 / $3600, cats $0c00 / $1800 / $2400 (slow / normal / fast).

## Spawning

`Spawners_Update` drives the spawners. Delay between two mice (`SpawnDelays`,
in frames): 50 + random(40) normally, 100 + random(80) during "Slow Down",
25 + random(20) during "Mouse Mania", "Speed Up" and "Mouse Monopoly",
15 + random(10) in challenge mode. A gold mouse comes every 8 to 64 mice and
a purple one every 8 to 62, depending on the frequency option
(`BonusMouseFreqs`). A new cat only appears when no cat is left on the board
(up to 4 during "Cat Mania").

## Arrows and players

Each player has 3 arrows (`Player_PlaceArrow`); placing a fourth removes the
oldest one. A new arrow has 2 hit points: a cat walking over it damages it,
then destroys it (`Arrow_HitByCat`). It vanishes after 1000 frames and blinks
during the last 75 (`Arrows_Age`, `Arrows_Draw`). In puzzles, the stock comes
from the level header, `Player_UndoArrow` removes the last arrow placed, and
`PuzzleArrows_Save/Restore` put the same arrows back when the puzzle restarts.

## Score (`Rocket_Enter`)

| Enters the rocket | Effect |
|---|---|
| mouse | +1 |
| gold mouse | +50 |
| purple mouse | +1 and roulette (`Spinner_Trigger`) |
| cat | the score loses a third |

The roulette (`Spinner_Spin`) draws one of 8 events: Cat Attack, Cat Mania,
Everybody Move, Mouse Mania, Mouse Monopoly, Place Arrows Again, Slow Down,
Speed Up. Timed events last 500 frames, Mouse Monopoly 150.

## Time

A 200 Hz clock (`gClock`: hours/minutes/seconds/200ths) runs in the Timer C
interrupt. Five timers (`gTimers`) use it; timer 1 is the round timer
(`RoundTimer_Start/Stop/Pause/Resume`). `RoundTimer_SetLimit` sets the round
duration: the menu option (180 s in the demo), or 40 s / 60 s in challenge
mode.

## Computer players

`Ai_Update`: after placing an arrow, a computer player waits
`AiThinkDelays` + a random number of frames. Then `Ai_FindBestArrow` tries the
possible tiles with the maps built by `Ai_UpdatePathMaps` (where the mice go,
which tiles lead to its rocket with 0, 1 or 2 more arrows) and places the best
arrow. In cat soccer and during Cat Mania it aims at an opponent's rocket
(`AiCatTargets`).

## Randomness

`Random`: `seed = seed × $10dcd + $29`. The seed is set to 0 at start-up
(`Random_Init`), so the demo replays the same game as long as the frame rate
is the same.

## Changing the rules

Most of the numbers above are in `src/settings.s`: creature speeds, spawn
delays, bonus mouse frequencies, arrows per player, arrow lifetime, scores,
roulette durations, round times, computer delays and default options. With
the values it ships with, the build is identical to the original game.
