#!/bin/sh
# hatari.sh <dossier_jeu> <fichier_commandes_debogueur> <nb_vbl> [machine=ste]
# Hatari sans ecran, rapide, avec commandes du debogueur (--parse).
here=$(cd "$(dirname "$0")" && pwd); root=$(dirname "$here")
mkdir -p "$here/.hatari"
HOME="$here/.hatari" SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy hatari \
  --machine ${4:-ste} --tos "$root/run/etos256us.img" --memsize 4 --fast-boot on \
  --harddrive "$1" --gemdos-drive C --auto 'C:\CHUCHU.TOS' \
  --sound off --confirm-quit off --fast-forward on --statusbar off --drive-led off \
  --parse "$2" --run-vbls $3 --log-level error < /dev/null
