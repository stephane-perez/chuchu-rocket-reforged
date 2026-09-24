#!/bin/sh
# fps.sh <game_dir> <tag> [asm_option] [start=3000] [end=23000] [machine=ste]
# Logs the VBL of every displayed frame (VBL handler: Video_UpdateRegsSTE on STE,
# Video_UpdateRegsST on ST) and the calls to Arrows_Draw (only called in game),
# then prints frame-rate statistics for the game part. ~6 demo games by default.
here=$(cd "$(dirname "$0")" && pwd); root=$(dirname "$here")
d=$(cd "$1" && pwd); tag=$2; def=$3; a=${4:-3000}; b=${5:-23000}; m=${6:-ste}
w="$here/work"; mkdir -p "$w"
python3 "$here/mksym.py" "$root/src/chuchu.s" "$w/$tag.sym" $def >/dev/null
h=Video_UpdateRegsSTE; [ "$m" = "ste" ] || h=Video_UpdateRegsST
[ "$m" = "falcon" -o "$m" = "tt" ] && echo "machine not supported" && exit 1
T=$((0x10bf0))   # TEXT start under EmuTOS 1.4 / 4 MB, read from the profiles
f=$(awk -v h=$h '$3==h{print $1}' "$w/$tag.sym"); g=$(awk '$3=="Arrows_Draw"{print $1}' "$w/$tag.sym")
echo 'e VBL' > "$w/evf"; echo 'e VBL+1000000' > "$w/evg"
printf 'b pc = $%x && VBL > %s && VBL < %s :trace :quiet :file %s\nb pc = $%x && VBL > %s && VBL < %s :trace :quiet :file %s\n' \
  $((T+0x$f+12)) $a $b "$w/evf" $((T+0x$g)) $a $b "$w/evg" > "$w/$tag.fps.ini"
"$here/hatari.sh" "$d" "$w/$tag.fps.ini" $((b+10)) $m 2>&1 | grep "(dec)" | sed -E 's/.*#([0-9]+) \(dec\).*/\1/' > "$w/$tag.fps.txt"
python3 "$here/fpsstat.py" "$w/$tag.fps.txt"
