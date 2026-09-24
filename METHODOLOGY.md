# Methodology and findings

The rule is the one of *Shufflepuck Café Reforged*: **no claim without the bytes that back it**. Everything below is checked by a tool of the `tools/` folder and re-run by `tools/verify.py`.

## 1. The executable: Pack-Ice 2.40

`CHUCHU.TOS` (65,314 bytes) is a PRG with 65,282 bytes of text, no data and no relocation. It is the self-extracting wrapper of Pack-Ice: the string `Pack-Ice` sits at text+2, and the packed stream starts with `ICE!` at file offset `$1BA`. The tables of the stub (`direkt_tab`, `length_tab`, `more_offset` at text+`$162`) are exactly those of the Pack-Ice 2.40 routine.

`tools/unice.py` is a transcription of that 68000 routine. It reads the stream backwards, bit by bit, handles the "picture" mode (not used here), and checks that the stream is **consumed exactly**: 0 bytes are left.

The result is a **complete GEMDOS PRG** of 117,289 bytes:

| | |
|---|---|
| Text | $19602 (103,938 bytes) |
| Data | $237A (9,082) |
| BSS | $169F0 (92,656) |
| Flags | 6 (fastload + TT-RAM) |
| Relocations | 4,129 (3,858 in the code, 271 in the data), all inside the image |

The start-up code at `$42` is the **Pure C** `PCSTART`: stack set from the basepage, `Mshrink`, then command-line parsing. The game is written in C with **GodLib**, the Reservoir Gods library, a later version of which is published on GitHub (`ReservoirGods/GODLIB`).

## 2. The data: GodLib LINKFILE (2001 version)

`CHUCHU.LNK` uses an older GodLib format than the one of the current sources:

```
+$00 U32 $12345678 (ID)   +$04 U32 version (0)   +$08 U32 FAT size ($1663)
+$16 U32 pointer to the root folder (relative to the FAT) = $1A
folder : U16 fileCount, U16 folderCount, pName, pFiles, pFolders          (16 bytes)
file   : U32 size, U32 unpackedSize, U32 offset, U16 packed, U16 loaded, pName  (20 bytes)
```

The archive holds 178 files in the root folder, with no gap between them. 165 are packed with Pack-Ice: each one is checked, with an exact unpacked size and a fully consumed stream.

| Ext. | Count | Content (checked) |
|---|---|---|
| `.BSB` | 123 | GodLib `BSBK` sprite blocks: pointers, then for each sprite a 16-byte header, the 1-plane mask, then 4 interleaved planes. 1,013 sprites. |
| `.PI1` | 6 | Degas screens (4 in the Elite format, 32,066 bytes). |
| `.GFX` | 12 | `GFX ` v1: U16 width, U16 height, U8 planes, U8 mask. For each group of 16 pixels, **the mask word comes first**, then the 4 planes. A mask bit set to 1 means transparent. Hypothesis checked visually on `ATARI.GFX`. |
| `.PAL` | 2 | 16 STE palette words. |
| `.CHU` | 10 | Levels, signature `CHUL` (format documented in `GAME_LOGIC.md`). |
| `.TRI` / `.TVS` | 13 / 1 | `TSST` tunes and `TSSS` instruments (SID-sound). |
| `SNDREP` | 1 | The "SSD-Player by Animal Mine", **68000 code loaded at run time**. |
| `.HLP`, `.TXT` | 8 | Help texts and credits. |
| `FONTMID.IMG` | 1 | 8×8 font, 1 bit per pixel, first character = space. |
| `SPLINE.TAB` | 1 | 32 KB table for the Atari intro. |

The loader (`Packer_GetType`, at `$1142`) only depacks what starts with `ICE!` or `ATM5` (Atomik). A file stored unpacked is therefore accepted as it is. This is what makes it possible to put a modified asset back without a packer.

## 3. Disassembly (`tools/trace.py`)

The disassembly is **recursive**. Only what can run is followed:
- the entry point;
- the targets of branches and calls;
- relocated absolute `jsr`/`jmp`;
- `switch` tables;
- relocated pointers used as code addresses: `#imm`, `lea`, `pea`, or tables in the data. Each one is first decoded on trial and rejected if it runs into non-68000 code or overlaps an instruction.

Pure C `switch` tables come in three forms, all resolved:
- `cmp.w #N` / `bhi` / `add.w` / `move.w T(pc,dn.w)` / `jmp T(pc,dn.w)`: 20 tables of 16-bit offsets relative to T;
- the sparse form `moveq #N-1` / `lea T(pc)` / `cmp.w (a0)+` / `dbeq`: 1 table of values followed by a table of offsets;
- a table of `bra.w` from a module written in assembly: 1.

In the end, **96.4 % of the text is recognised as code**: 31,417 instructions, including 15 dead functions. Pure C links whole object modules, so the GodLib functions that are never called, such as the Timer A/B/D routines, are still in the binary. They were found through their prologue. The rest is data: tables, bitmaps, strings of the Pure C library and `(C)Xmath by d'ART`.

Capstone 5 pitfalls met and fixed:
- the size of memory shifts (`asl.w d16(An)`) is wrong: 2 bytes instead of 4;
- in 68000 mode, it accepts 68020 addressing modes (`([bd,An])`);
- it classifies `(0,An,Xn)` as "base displacement", which prevents filtering by mode: the fields have to be read;
- it rejects `movec`, used 4 times for the Falcon/TT caches: it has to be decoded again in 68030 mode.

**Self-modifying code.** The MFP Timer C handler (`L_03ed2`) contains `jsr $12345678` and `jmp $01234568`. These are dummy values that `Mfp_HookIntoTimerC` and `Mfp_InstallStandardTimerC` overwrite at run time. The source therefore refers to them as `(L_03f3a+2).l` and `(L_03f4a+2).l`.

## 4. Source generation (`tools/emit.py`)

**Everything that is an address becomes a label:**
- branch targets;
- PC-relative operands;
- relocated values in the code (`#label`, `(label).l`) and in the data (`dc.l label`);
- `switch` table entries (`dc.w L_x-J_base`);
- targets in the middle of an instruction (`label+n`).

Data stays as `dc.b`, and C strings are written as text.

vasm details to respect:
- `-no-opt` and explicit sizes everywhere (`bra.s`/`bra.w`), otherwise vasm optimises and the identity is lost;
- short addresses above `$8000` are written `$ffff8240.w`;
- bit operations take `.l` on a data register and `.b` in memory;
- `mc68030`/`mc68000` around the `movec`;
- `-nosym`, and `-tos-flags=6` to get the original header back.

Automatic annotations of the first generated source:
- 30 named GEMDOS, BIOS and XBIOS calls;
- hardware registers and system vectors;
- 12 functions recognised by comparing instruction sequences with the GodLib assembly sources (`tools/godlib_match.py`): Video_SaveRegsST/STE/Falcon, IKBD_PopKbdByte, Mfp_*, Audio_SoundChipOff, GemDos_Call_*… The small number comes from the gap between the 2002 GodLib and the published one;
- a few names given after reading (`tools/names.txt`).

Since then, every function has been named and commented (§11).

## 5. Checks

| Test | Result |
|---|---|
| Code round trip: source → vasm → PRG | **Identical** to the unpacked original (117,289 bytes, header and relocations included). |
| Data round trip: PNG/files → `CHUCHU.LNK` | **Identical** (242,134 bytes). |
| Asset round trip: binary → PNG → binary | 178/178 files identical. |
| Shift test: 16 bytes of padding before 876 of the 897 function starts, i.e. +14,016 bytes of code | Assembles and runs in Hatari. The 21 remaining boundaries are crossed by an 8-bit displacement that padding would overflow. |
| Run (Hatari 2.4.1, STE, EmuTOS 1.4) of the original, the rebuilt version and the shifted version | Intro, title, menu, then **demo mode with 4 AI players** and back to the menu, for all three. Frame-by-frame comparison (MD5) between rebuilt and shifted: 1,803/1,839 frames identical; the differences are isolated frames caused by the AVI sampling, never a lasting divergence. |
| `SKIP_INTRO` modification + banner on the title | Starts directly on the modified title screen, then menu, demo and menu. |

## 6. Code map (landmarks)

The complete map is `CODE_MAP.md`, generated from the source. A few landmarks:

| Address | Name | Role |
|---|---|---|
| `$00000` | `ProgramEntry` | `jmp PureC_Start` |
| `$00042` | `PureC_Start` | Pure C start-up |
| `$0a976` | `App_FrontEndStateMachine` | **Main state machine** (state in `gAppState`): 0 = boot (Atari intro, logos, title), 1 = logos + title (back from the demo), 2 = front end… |
| `$0a394` | `Intro_LogosAndTitle` | RGLOGO.PI1, then SONICTM.PI1, then TITLE.PI1, with fades |
| `$0d4fc` / `$0d724` / `$0d5cc` | `AtariIntro_Load` / `_Run` / `_Free` | Atari intro (ATARI.GFX, FUJI.GFX, BALL.BSB…) |
| `$0aec2` | `LinkFile_Load` | Loads a file of CHUCHU.LNK |
| `$0392a` | `Ice_Depack` | GodLib Pack-Ice depacker |
| `$03d9e`–`$03f68` | `Mfp_*` | MFP timer set-up and the self-modifying Timer C handler |

## 7. Limits and next steps

- **3.6 % of the text is still `dc.b`.** Mostly tables, but also a few code fragments that are never reached (Pure C library, Xmath floating point). PC-relative references inside them are not labels. To modify these areas, they first have to be recognised as code, through `names.txt` or a seed in `trace.py`.
- **Formats still to document**: `TSST`/`TSSS` music. The `CHUL` level format is described in `GAME_LOGIC.md` (the ideal starting point for a level editor).
- **Pack-Ice packer**: not needed. If space runs short on a floppy, the executable can be packed again with Pack-Ice on an ST, or a compatible packer can be written.
- **Other configurations**: Hatari in STF mode with TOS 1.x, and the Falcon, have not been tested yet.

## 8. Performance

### Measure first

- **CPU profile.** The Hatari profiler (`profile on`) is driven by two breakpoints on the VBL counter around the 4-AI demo (VBL 4100 to 5700 on STE, i.e. 32 s). Cycles are then aggregated by function and by block, using a symbol file built from the source labels (`perf/profile.sh`).
- **Real frame rate.** The VBL handler (`Video_UpdateRegsSTE` on STE, `Video_UpdateRegsST` on ST) sets the video address when the game clears a flag (`tas`). The instruction after this `tas` therefore marks every displayed frame. A breakpoint in `:trace` mode logs the matching VBL; a second one, on the arrow rendering (`Arrows_Draw`), separates the game from the menus (`perf/fps.sh`).
- **The game is not locked** to a fixed rate. Each frame takes 2, 3 or 4 VBL depending on the load, so every cycle saved shows.
- **The demo's randomness depends on the frame rate**: a faster version does not play the same levels. Averages over about 6 games (≈12,600 game VBL) are compared, never single frames.

### Profile of the original (STE, in game)

| CPU share | Where | What |
|---|---|---|
| **22.7 %** | `L_01daa` (`AudioMixer_MixChunk`) | **DMA mixer**: 2 voices, 8 bits → 50 kHz stereo, 8 KB ring buffer, called every VBL. |
| 12.6 % | `Vbl_Wait` | Waiting for the VBL (idle time). |
| 6.1 % + 2.8 % | `Board_RestoreDirtyCells`, `Board_RestoreDirtyBorder` | Restoring the 16×16 background under the sprites (32 `move.l d16(An),d16(An)` per tile). |
| 5.9 % | `Mice_Draw` | Mouse and cat sprites with the blitter. |
| 4.6 % | `L_15748` | Masked arrows, 4 planes. |
| ~4 % | `Time_ToTicks`/`Time_FromTicks` + `_lmul`/`_uldiv` | Clock: duration ↔ 1/200 s ticks conversions every frame. |
| 6 % + 1 % | RAM outside the program | SID music player (`SNDREP`) and its interrupts. |

Conditional breakpoints on the voice activity flags showed that **the 1,990 mixer calls during the demo all happen with both voices silent**. The game was mixing silence at 50 kHz.

On an STF there is no DMA sound, so no mixer. Sprites are drawn by the CPU (`L_0293e`, 15 %), and waiting for the VBL takes 19 %.

### Optimisations kept (`-D OPTIM`)

- **`OPT_MIXER`.** A silent voice points to a silence buffer allocated with `calloc` (`Memory_ScreenCalloc`, then `Memory_Clear`), and the volume table is 0 for a zero sample. Two silent voices therefore give exactly 0. In that case the mixer writes zeros with `move.l`, then **nothing at all** once the 8 KB buffer is entirely zero (counter `Opt_SilentBytes`, reset to 0 as soon as a voice plays). The audio buffer is identical to the original.
- **`OPT_TIME`.** `h×720000 = (h×11250)<<6` with a single `mulu.w`. For the unsigned division, `x/720000 = (x>>6)/11250` exactly, with no overflow since the quotient stays below 5966, and the remainder is `(remainder<<6)|(x&63)`. Then `divu.w #12000` and `divu.w #200`. This removes the 16-round bit-by-bit loop of `_uldiv`, triggered by a divisor ≥ 65,536.

### Proof of equivalence (`tools/difftest.py`)

Both builds are assembled with their symbols, relocated and loaded into Unicorn (68000 model). Each routine is called with the same inputs, then the result registers, the preserved registers (d3-d7/a2-a7) and the written memory are compared.

| Routine | Test | Result |
|---|---|---|
| `Time_ToTicks` | 70,000 durations, including every h×m combination | Identical |
| `Time_FromTicks` | 80,000 values: limits, realistic durations, **negative** values, random 32-bit values | Identical |
| `AudioMixer_MixChunk` | 400 successive calls on the ring buffer (split at the wrap as in `L_01cca`, 75 with active voices, random samples and volumes) | Buffer identical after every call |

The test bench was validated by **mutation**: changing `#200` to `#201` gives 69,707 differences, and a silence threshold of 4 KB instead of 8 KB gives 268 failing calls. The original routine was also checked against a Python `divmod`.

### Results

| Machine | Version | Game frames/s | Frames in 2 VBL (25 fps) |
|---|---|---|---|
| STE | Original | 16.5 | 19 % |
| STE | `OPT_MIXER` | 21.0 | 70 % |
| STE | `OPTIM` | **21.9 (+33 %)** | **77 %** |
| STF | Original | 18.0 | 35 % |
| STF | `OPTIM` | **18.9 (+5 %)** | 43 % |

A visual check on STE and STF (title, menu, game, back to the menu) shows no defect. The black and white embossed tiles seen on some levels are the holes (`HOLE.BSB`).

### `OPT_BLIT`: restoring the background with the blitter

`Board_RestoreDirtyCells` restores the inner tiles of the board, and `Board_RestoreDirtyBorder` the border tiles. A tile is 16 lines × 8 bytes, with a line pitch of 160 and a row pitch of `$A00`. The CPU copies each tile with 32 `move.l d16(An),d16(An)`, about 1,000 cycles.

- **Condition.** The blitter path is only taken when `gSystemBLT` is 1. This flag is `(Blitmode(-1)>>1)&1`, computed at start-up by `System_CalcBLT`, and the game already uses it to choose its blitter sprite routines. On an STF, the original CPU code therefore runs unchanged.
- **Copy.** HOP = source, OP = 3, masks `$FFFF`, skew 0, X increment 2, Y increment `162 − 8n`, Y count 16. Consecutive dirty tiles of a row are grouped into a single operation of n tiles. The blitter starts in shared mode, with the `bset #7 / nop / bne` restart loop the game already uses, which lets the music interrupts through. The blitter registers that are changed are saved and restored.
- **Walking the bits.** The mask is read by `lsr` shifts: zeros are skipped, each run of ones is measured, and the loop exits as soon as the mask is empty. A first version, which tested each column with `btst`, cost about 3,000 more cycles per call.

**Proof of equivalence.**
- `tools/difftest.py` includes a small model of the STE blitter. It is triggered when the code reads the control register `$FF8A3C` while the BUSY bit is set.
- Each routine is run in its original CPU version and in its blitter version, on 400 cases: random masks (densities 0, 10, 30, 60 and 100 %, and arbitrary 16-bit values) and random source and destination boards. That is 6,602 + 3,852 blitter copies.
- The whole destination board, the masks and all the registers are **identical**.
- Mutation: one column too many (`$0fff` → `$1fff`) gives 307 failing cases out of 400.
- In Hatari, the `BLIT_CHECK` variant has the CPU re-read every copy during 2 demo games: 16,067 copies, 0 differences.

**Measurements (STE, Hatari).**

| Version | Restore, cycles per call | CPU share | Game frames/s | Frames at 25 fps |
|---|---|---|---|---|
| Original CPU code | 24,575 | 9.7 % | 21.9 | 77 % |
| Blitter, `btst` walk | 20,330 | 8.1 % | 22.4 | 82 % |
| **Blitter, `lsr` walk** (kept) | **18,634** | **7.5 %** | **22.4** | **81 %** |

The copy stays bus-bound: the blitter reads and writes every word, sharing the bus with the CPU, and copies about 40 % faster than the CPU. The overall gain is −24 % on the restore, i.e. +2 % frames/s.

On a **Mega STe at 16 MHz with cache**, the CPU copies faster while the blitter stays at 8 MHz, so the gain may shrink there. `dist/reforged_sans_blit/` (`-D NO_BLIT`) allows the comparison.

### Remaining ideas (estimated gains, not done)

- **Background restore on STF** (`Board_RestoreDirtyCells`/`Board_RestoreDirtyBorder`, no blitter): use `move.l (a1)+,(a2)+` with one `lea` per line (−12 % on these routines, ~1 % overall).
- **CPU sprites on STF** (`L_0293e`, 15 %): for shifts of 10 to 15 bits, `swap` + `rol` instead of `ror.l` (−6 % on the loop, ~1 % overall).
- **Masked arrows** (`L_15748`, 4.6 %): unroll the loop and use 32-bit masks (−8 to 13 % on the loop).
- **Mixer with a single active voice**, common in real games: a one-voice loop saves ~25 % of the mixing cost during sound effects. Not measurable in the demo, which is silent.
- **Loading**: the library `memset`/`memcpy` (`Memory_Clear`, `Memory_Copy`) works byte by byte (~40 cycles per byte). The `calloc` of the 64 KB volume table costs ~80 ms. Replacing them with `move.l` loops would speed up transitions, with no effect during play.

## 9. Bug fixes

### `FIX_MOUSE`: mouse disabled when going back to GEM

Symptom reported on a Mega STe: after quitting, the mouse no longer moves under GEM.

**Cause (bug of the original game).** When a game starts, `Controls_ApplyIkbdMode` (`$0664e`) looks at the controller of the 4 players. If none is "Mouse", it calls `Ikbd_JoystickMode` (`$00bbc`), which sends `$12` (mouse off) and `$14` (joystick event mode) to the IKBD. Otherwise it calls `Ikbd_MouseMode` (`$00bce`), which sends `$08`. The exit routine `Game_Exit` (`$0ae7e`) gives the ACIA vector back to the system through `Ikbd_DeInit` but **never sends `$08`**. After a game played with a joystick, the keyboard or the 4-CPU demo, the mouse therefore stays off.

**Proof.** Hatari is driven from the keyboard through its command FIFO (`hatari-event keydown/keyup`), with the `--trace ikbd_cmds` trace. The path is: title, Play, 4p Battle, level 1, player 1 on "Joystick 0", game, F10, Undo ×2, Quit.

| Version | Last IKBD commands when going back to GEM |
|---|---|
| `orig/CHUCHU.TOS` (packed original) | `TurnMouseOff`, `ReturnJoystickAuto`: mouse off |
| Rebuilt, no option | same as the original |
| `REFORGED` | `TurnMouseOff`, `ReturnJoystickAuto`, **`RelMouseMode`** |

The bug therefore does not depend on the optimisations, but on the controller used in the last game.

**Fix.** In `Game_Exit`, before `Ikbd_DeInit`, a call to `Ikbd_MouseMode` sends `$08` (relative mouse) again, the standard desktop mode. `$14` (joystick event mode) is also the TOS default, and the mouse threshold and Y axis are not changed by `$12`. This single command is therefore enough to restore the desktop state.

## 10. Validation on real hardware (Mega STe)

| Version | Result |
|---|---|
| `reconstruit/` (rebuilt) | Works at 8 and 16 MHz. |
| `optim/` (first optimised version) | Works at 8 and 16 MHz; sprites are displayed faster. |
| `reforged/` (`OPTIM` + `OPT_BLIT` + `FIX_MOUSE` + banner) | Animations feel noticeably faster (felt, not measured). **The mouse is back on when quitting the game.** |

The gains measured in Hatari (§8) and the mouse fix (§9) are therefore confirmed on the original hardware.

## 11. Naming, settings and complete map

### Naming without breaking anything

Every label was renamed with `tools/rename.py`, from `analysis/*.map` files (one `OLD NEW` line per rename, `@NAME text` lines for the `;;` comment block placed above). After each pass, the tool rebuilds the game and checks that it stays **identical to the byte**; it also assembles the `REFORGED`, `REFORGED+BLIT_CHECK` and `OPTIM+SKIP_INTRO` variants. A rename therefore cannot change the behaviour.

- **Game logic** (`names_game_logic*.map`): round, creatures, arrows, rockets, roulette, AI, levels, timers, input.
- **Complete map** (`names_map_1` to `names_map_9`): GodLib system layer (names taken from the GodLib sources when the routine matches), game modules, render modules, graphics library and Pure C runtime. All **907 functions** now have a name and a `;;` block (what it does, what it receives, what it returns).
- Names are in English, in the form `Module_Action`, `gVariable`, `Table`. The TOS symbol table cuts names to 22 characters: the first 22 characters of every name are unique (`names_map_7_fixes.map`), otherwise profiling and `difftest.py` would mix up two functions.
- Every module follows the same life cycle, called by dispatchers: `*_Init` (`Game_InitModules`), `*_RoundBegin` (`Round_InitModules`), `*_SetupForLevel` / `*_ResetForLevel` (`Round_SetupLevel`), `*_LevelReset` (`Round_CleanupLevel`), `*_RoundEnd`, `*_DeInit`. Many of these entry points are empty (`*Stub`): they come from the original C code.

Naming corrected a few hypotheses. The table first called `AiReactionFrames` does not hold delays: it says **which rocket** each computer player sends the cats to in "cat soccer" and during "Cat Mania" (`AiCatTargets`: 0→2, 1→3, 2→0, 3→1). The real AI thinking delays are just before it (`AiThinkDelays`). Another finding: the "speed" option of the menu is saved but **never read** by the game.

`tools/codemap.py` generates `CODE_MAP.md` from the source: every function, grouped by layer and module in the order of the original program (Pure C keeps each `.C` file in one piece), with its original address and the first sentence of its `;;` block, then the named variables and tables. `rename.py` regenerates it after each pass.

### Settings (`src/settings.s`)

The game constants found while naming were moved out of the code into `src/settings.s`, included at the top of `chuchu.s`. The code uses them by name (`moveq #SCORE_GOLD_MOUSE,d1`, `dc.w SPAWN_DELAY_NORMAL,...`), so with the shipped values the assembly gives exactly the same bytes.

- **Range checks.** A `CHECK_RANGE` macro stops the assembly with a clear message when a value goes beyond what the code accepts (for example 1 to 127 for a value loaded with `moveq`, 1 to 3 arrows per player, matching the 3 slots of the player record).
- **Menu texts.** The texts of the TIME and WINS choices are macros, so they can be changed along with the values.
- **Alignment.** Changing the length of a text shifts all the data after it, and a `.w` or `.l` value at an odd address crashes a 68000. 274 `even` directives were therefore placed before every item at an even address that follows bytes: they emit nothing in the original layout, and restore the alignment when a text changes length.
- **Default options.** The `DefaultOptions` table was rewritten as `{dc.w number, dc.l value}` so that the defaults are readable and adjustable. They are only used when there is no `CHUCHU.SAV`.

**Test in Hatari.** A version with changed settings (25 s demo rounds, faster mice, 2 arrows per player, 3 points per mouse, faster AI, a 5-character "2 MIN" text instead of "1 MINUTE") assembles and runs: clock at 0:18 then 0:01, scores in multiples of 3 (59 = 50 + 3 × 3 with a gold mouse), no crash. At the end of the round, the demo stays on the "Winner!" screen; a version where only the demo duration changes does the same, so it is the original code that behaves this way at the end of a round, not the settings.
