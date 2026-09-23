#!/bin/sh
# Lance le jeu dans Hatari sans ecran et enregistre un AVI.
# usage: run/run.sh <dossier contenant CHUCHU.TOS + CHUCHU.LNK> [nb_vbl=3000]
# (le mode demo demarre seul apres ~40 s d'inactivite dans le menu)
here=$(cd "$(dirname "$0")" && pwd)
d=$(cd "$1" && pwd); n=${2:-3000}; name=$(basename "$d")
mkdir -p "$here/hatari_home"
HOME="$here/hatari_home" SDL_VIDEODRIVER=${SDL_VIDEODRIVER:-dummy} SDL_AUDIODRIVER=dummy hatari \
  --machine ste --tos "$here/etos256us.img" --memsize 4 --fast-boot on \
  --harddrive "$d" --gemdos-drive C --auto 'C:\CHUCHU.TOS' \
  --sound off --confirm-quit off --fast-forward on --statusbar off --drive-led off \
  --avirecord --avi-vcodec png --avi-file "$here/$name.avi" --run-vbls $n --log-level error
echo "video : $here/$name.avi"
