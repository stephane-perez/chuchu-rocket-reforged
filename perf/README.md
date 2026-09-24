# Performance measurements

Tools used to find and validate the optimisations (see `METHODOLOGY.md`, §8). They need Hatari 2.4 and vasm.

- `profile.sh`: CPU profile (Hatari's built-in profiler) of a window of the demo, aggregated by function using the source labels.
- `fps.sh`: real frame rate during the game. It logs the VBL of every displayed frame and computes the distribution of frame durations.
- `../tools/difftest.py`: proof of equivalence of the optimised routines, by differential execution in a 68000 emulator.

Example:

```
python build.py -D OPTIM && cp -r out /tmp/optim
perf/fps.sh /tmp/optim optim OPTIM            # STE
perf/fps.sh /tmp/optim optim_st OPTIM 3000 23000 st
```

The demo's randomness depends on the frame rate: two different builds do not play the same levels. Averages over several games are compared, never single frames.
