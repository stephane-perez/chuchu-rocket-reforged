#!/bin/sh
# profile.sh <dossier_jeu> <tag> [option_asm] [debut=4100] [fin=5700] [machine=ste]
# Profil CPU Hatari d'une fenetre de VBL, puis agregation par fonction.
#   ex. : perf/profile.sh out base            (build sans option)
#         perf/profile.sh out opt OPTIM
here=$(cd "$(dirname "$0")" && pwd); root=$(dirname "$here")
d=$(cd "$1" && pwd); tag=$2; def=$3; a=${4:-4100}; b=${5:-5700}; m=${6:-ste}
w="$here/work"; mkdir -p "$w"
python3 "$here/mksym.py" "$root/src/chuchu.s" "$w/$tag.sym" $def >/dev/null
printf 'symbols autoload off\nsymbols %s TEXT\nprofile on\nscreenshot %s_start.png\n' "$w/$tag.sym" "$w/$tag" > "$w/$tag.start"
printf 'screenshot %s_stop.png\nprofile save %s_prof.txt\nquit\n' "$w/$tag" "$w/$tag" > "$w/$tag.stop"
printf 'b VBL = %s :once :trace :quiet :file %s\nb VBL = %s :once :quiet :file %s\n' $a "$w/$tag.start" $b "$w/$tag.stop" > "$w/$tag.ini"
"$here/hatari.sh" "$d" "$w/$tag.ini" $((b+100)) $m > "$w/$tag.log" 2>&1
python3 "$here/agg.py" "$w/${tag}_prof.txt" "$w/$tag.sym" 25
