# Mesures de performance

Outils utilisés pour trouver et valider les optimisations (voir `METHODOLOGIE.md`, §8). Ils demandent Hatari 2.4 et vasm.

- `profile.sh` : profil CPU (profileur intégré de Hatari) d'une fenêtre de la démo, agrégé par fonction à l'aide des labels du source.
- `fps.sh` : cadence réelle pendant le jeu. Il relève le VBL de chaque image affichée et calcule la distribution de la durée des images.
- `../tools/difftest.py` : preuve d'équivalence des routines optimisées, par exécution différentielle dans un émulateur 68000.

Exemple :

```
python build.py -D OPTIM && cp -r out /tmp/optim
perf/fps.sh /tmp/optim optim OPTIM            # STE
perf/fps.sh /tmp/optim optim_st OPTIM 3000 23000 st
```

Le hasard de la démo dépend du rythme des images : deux builds différents ne jouent pas les mêmes niveaux. On compare donc des moyennes sur plusieurs parties, jamais des images une à une.
