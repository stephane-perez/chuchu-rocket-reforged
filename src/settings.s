; ===========================================================================
; Chu Chu Rocket - GAME SETTINGS
; ===========================================================================
; Change a value, then rebuild (python build.py, or python build.py --reforged).
; With the values below the game is exactly the original one.
;
; Units
;   frame  : one game frame. The game is not locked to a fixed rate: a frame
;            takes 2 to 4 VBL (25 to 12 frames per second in PAL), so frame
;            counts are not an exact duration.
;   speed  : distance per frame in 1/65536 of a tile ($10000 = one tile).
;
; Values that are loaded with "moveq" must stay within 1..127; the build
; stops with an error message if a value is out of its range.
;
; Options chosen in the menus are saved in CHUCHU.SAV and reloaded at start:
; the DEFAULT_* values below are only used when there is no CHUCHU.SAV
; (delete it to see new defaults).
; ===========================================================================

; ---------------------------------------------------------------------------
; Creature speeds (per frame). Index 0 = "Slow Down" spinner event,
; 1 = normal, 2 = "Speed Up" spinner event (and puzzle fast forward for mice).
; Keep them below $8000 (half a tile per frame).
; ---------------------------------------------------------------------------
MOUSE_SPEED_SLOW	equ	$1200
MOUSE_SPEED_NORMAL	equ	$2400
MOUSE_SPEED_FAST	equ	$3600
CAT_SPEED_SLOW		equ	$0c00
CAT_SPEED_NORMAL	equ	$1800
CAT_SPEED_FAST		equ	$2400

; ---------------------------------------------------------------------------
; Mouse spawning: frames between two mice from a spawner = DELAY + Random(RANDOM)
; (Random(n) gives 0..n).
; SLOW is used during "Slow Down", FAST during "Mouse Mania", "Speed Up" and
; "Mouse Monopoly", NORMAL otherwise. CHALLENGE is used in challenge mode.
; ---------------------------------------------------------------------------
SPAWN_DELAY_SLOW	equ	100
SPAWN_RANDOM_SLOW	equ	80
SPAWN_DELAY_NORMAL	equ	50
SPAWN_RANDOM_NORMAL	equ	40
SPAWN_DELAY_FAST	equ	25
SPAWN_RANDOM_FAST	equ	20
CHALLENGE_SPAWN_DELAY	equ	15
CHALLENGE_SPAWN_RANDOM	equ	10

; Bonus mice: a gold (or purple) mouse comes after EVERY + Random(RANDOM)
; ordinary mice. The menu setting chooses the column: 0 = rare, 1 = normal,
; 2 = frequent. Use values of 1 or more.
GOLD_EVERY_RARE		equ	32
GOLD_EVERY_NORMAL	equ	16
GOLD_EVERY_FREQUENT	equ	8
GOLD_RANDOM_RARE	equ	32
GOLD_RANDOM_NORMAL	equ	16
GOLD_RANDOM_FREQUENT	equ	8
PURPLE_EVERY_RARE	equ	32
PURPLE_EVERY_NORMAL	equ	16
PURPLE_EVERY_FREQUENT	equ	8
PURPLE_RANDOM_RARE	equ	30
PURPLE_RANDOM_NORMAL	equ	20
PURPLE_RANDOM_FREQUENT	equ	8

; Cats present at the same time during "Cat Mania" (normally a new cat only
; appears when there is none left). 1..16.
CATMANIA_MAX_CATS	equ	4

; ---------------------------------------------------------------------------
; Arrows
; ---------------------------------------------------------------------------
ARROWS_PER_PLAYER	equ	3	; arrows on the board per player, 1..3
ARROW_LIFETIME		equ	1000	; frames before an arrow disappears
ARROW_BLINK_FRAMES	equ	75	; the arrow blinks during its last frames
ARROW_HEALTH		equ	2	; cat hits before the arrow breaks, 1..2
					; (the arrow is drawn damaged when 1 hit
					; is left, so 1 = damaged from the start)

; ---------------------------------------------------------------------------
; Score (Rocket_Enter)
; ---------------------------------------------------------------------------
SCORE_MOUSE		equ	1	; 1..127
SCORE_GOLD_MOUSE	equ	50	; 1..127
SCORE_PURPLE_MOUSE	equ	1	; 1..127, then the roulette starts
CAT_PENALTY_DIVISOR	equ	3	; a cat in a rocket takes score/3 away

; ---------------------------------------------------------------------------
; Roulette (spinner) events, duration in frames
; ---------------------------------------------------------------------------
SPINNER_EVENT_FRAMES	equ	500	; Cat Mania, Mouse Mania, Slow Down, Speed Up
SPINNER_MONOPOLY_FRAMES	equ	150	; Mouse Monopoly

; ---------------------------------------------------------------------------
; Round duration (seconds)
; ---------------------------------------------------------------------------
DEMO_ROUND_SECONDS	equ	180	; rounds of the demo (4 computer players)
CHALLENGE_SECONDS_EARLY	equ	40	; challenge mode, levels before ...
CHALLENGE_LATE_LEVEL	equ	24	; ... this level (numbered from 0)
CHALLENGE_SECONDS_LATE	equ	60	; challenge mode, from that level on

; The choices of the OPTIONS menu (TIME and WINS) and their texts.
; Keep the texts short (at most 9 characters for TIME, 1 for WINS).
TIME_CHOICE_1		equ	60
TIME_CHOICE_2		equ	180
TIME_CHOICE_3		equ	300
TIME_CHOICE_1_TEXT	macro
	dc.b	"1 MINUTE",0
	endm
TIME_CHOICE_2_TEXT	macro
	dc.b	"3 MINUTES",0
	endm
TIME_CHOICE_3_TEXT	macro
	dc.b	"5 MINUTES",0
	endm
WINS_CHOICE_1		equ	1
WINS_CHOICE_2		equ	3
WINS_CHOICE_3		equ	5
WINS_CHOICE_1_TEXT	macro
	dc.b	"1",0
	endm
WINS_CHOICE_2_TEXT	macro
	dc.b	"3",0
	endm
WINS_CHOICE_3_TEXT	macro
	dc.b	"5",0
	endm

; ---------------------------------------------------------------------------
; Computer players: pause after placing an arrow = DELAY + Random(RANDOM)
; frames. The column is the search that found the arrow: 0 = the arrow sends
; mice straight into its rocket, 1 or 2 = one or two more arrows are needed.
; Smaller values make the computer faster (harder).
; ---------------------------------------------------------------------------
AI_DELAY_0		equ	50
AI_DELAY_1		equ	25
AI_DELAY_2		equ	10
AI_RANDOM_0		equ	30
AI_RANDOM_1		equ	20
AI_RANDOM_2		equ	10

; ---------------------------------------------------------------------------
; Default options (used only without CHUCHU.SAV, see above)
; Controls: 0 keyboard, 1 mouse, 2 joystick 0, 3 joystick 1, 14 computer
; (see ControllerNames in chuchu.s for the other values).
; ---------------------------------------------------------------------------
DEFAULT_CONTROL_P1	equ	1
DEFAULT_CONTROL_P2	equ	14
DEFAULT_CONTROL_P3	equ	14
DEFAULT_CONTROL_P4	equ	14
DEFAULT_WINS		equ	5	; one of the WINS choices
DEFAULT_ROUND_SECONDS	equ	180	; one of the TIME choices
DEFAULT_GOLD_FREQ	equ	1	; 0 rare, 1 normal, 2 frequent
DEFAULT_PURPLE_FREQ	equ	1	; 0 rare, 1 normal, 2 frequent
DEFAULT_SFX		equ	1	; 1 on, 0 off
DEFAULT_MUSIC		equ	1	; 1 on, 0 off

; ===========================================================================
; Range checks (do not edit)
; ===========================================================================
	macro	CHECK_RANGE	; value, min, max, name
	if	(\1<\2)|(\1>\3)
	fail	"settings.s: \4 out of range"
	endif
	endm
	CHECK_RANGE	MOUSE_SPEED_SLOW,1,$7fff,MOUSE_SPEED_SLOW
	CHECK_RANGE	MOUSE_SPEED_NORMAL,1,$7fff,MOUSE_SPEED_NORMAL
	CHECK_RANGE	MOUSE_SPEED_FAST,1,$7fff,MOUSE_SPEED_FAST
	CHECK_RANGE	CAT_SPEED_SLOW,1,$7fff,CAT_SPEED_SLOW
	CHECK_RANGE	CAT_SPEED_NORMAL,1,$7fff,CAT_SPEED_NORMAL
	CHECK_RANGE	CAT_SPEED_FAST,1,$7fff,CAT_SPEED_FAST
	CHECK_RANGE	CATMANIA_MAX_CATS,1,16,CATMANIA_MAX_CATS
	CHECK_RANGE	ARROWS_PER_PLAYER,1,3,ARROWS_PER_PLAYER
	CHECK_RANGE	ARROW_LIFETIME,1,32767,ARROW_LIFETIME
	CHECK_RANGE	ARROW_BLINK_FRAMES,0,32767,ARROW_BLINK_FRAMES
	CHECK_RANGE	ARROW_HEALTH,1,2,ARROW_HEALTH
	CHECK_RANGE	SCORE_MOUSE,1,127,SCORE_MOUSE
	CHECK_RANGE	SCORE_GOLD_MOUSE,1,127,SCORE_GOLD_MOUSE
	CHECK_RANGE	SCORE_PURPLE_MOUSE,1,127,SCORE_PURPLE_MOUSE
	CHECK_RANGE	CAT_PENALTY_DIVISOR,1,32767,CAT_PENALTY_DIVISOR
	CHECK_RANGE	SPINNER_EVENT_FRAMES,1,32767,SPINNER_EVENT_FRAMES
	CHECK_RANGE	SPINNER_MONOPOLY_FRAMES,1,32767,SPINNER_MONOPOLY_FRAMES
	CHECK_RANGE	CHALLENGE_SECONDS_EARLY,1,127,CHALLENGE_SECONDS_EARLY
	CHECK_RANGE	CHALLENGE_SECONDS_LATE,1,127,CHALLENGE_SECONDS_LATE
	CHECK_RANGE	CHALLENGE_LATE_LEVEL,0,25,CHALLENGE_LATE_LEVEL
	CHECK_RANGE	GOLD_EVERY_RARE,1,32767,GOLD_EVERY_RARE
	CHECK_RANGE	GOLD_EVERY_NORMAL,1,32767,GOLD_EVERY_NORMAL
	CHECK_RANGE	GOLD_EVERY_FREQUENT,1,32767,GOLD_EVERY_FREQUENT
	CHECK_RANGE	PURPLE_EVERY_RARE,1,32767,PURPLE_EVERY_RARE
	CHECK_RANGE	PURPLE_EVERY_NORMAL,1,32767,PURPLE_EVERY_NORMAL
	CHECK_RANGE	PURPLE_EVERY_FREQUENT,1,32767,PURPLE_EVERY_FREQUENT
	CHECK_RANGE	DEFAULT_GOLD_FREQ,0,2,DEFAULT_GOLD_FREQ
	CHECK_RANGE	DEFAULT_PURPLE_FREQ,0,2,DEFAULT_PURPLE_FREQ
