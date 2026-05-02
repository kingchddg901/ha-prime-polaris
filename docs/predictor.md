# Cook Predictor

The integration ships a live Newton's-law-of-cooling fit per probe + a stall-detection state machine + per-protein historical priors. No ML, no GPU, ~250 lines of Python in [`cook_predictor.py`](../custom_components/prime_polaris/cook_predictor.py).

## What you see in HA

Two new sensors per probe:

- `sensor.<name>_probe_1_eta` — minutes until probe reaches its set target. State is a float in minutes (or `unknown` when fit can't be computed). Attributes: `in_stall`, `stall_stdev`, `k`, `samples`, `prior_source`.
- `sensor.<name>_probe_2_eta` — same.

The card uses these for the live ETA chips and stall callouts.

## The math

Probe heating in a chamber is governed by Newton's law of cooling:

```
dT_probe/dt = k × (T_chamber − T_probe)
```

`k` is a per-cook, per-meat-shape constant. Bigger meat = smaller `k` = slower rise.

Forward-extrapolating to a target temperature with chamber held constant:

```
t = ln((T_probe_now − T_chamber) / (T_target − T_chamber)) / k
```

That's the closed-form ETA. As the cook progresses and the rolling fit refines `k`, ETA accuracy converges quickly — typically within ±10% by the time the probe has risen 30°F from its initial reading.

## Tier 1: live fit (always on)

Every coordinator poll feeds the predictor a `(timestamp, probe, chamber)` sample. Once 5+ samples are buffered, a rolling least-squares regression fits `k` from consecutive sample pairs:

```
k = Σ(drive_i × rate_i) / Σ(drive_i²)
```

where `drive_i = mean_chamber - mean_probe` and `rate_i = (probe_{i+1} - probe_i) / dt`.

The fit window is the last 60 samples (~30 min at 30s polling). Fit values outside `(0, 0.05]` per second are rejected as physically implausible — these usually come from chamber-temp glitches or lid opens.

## Tier 2: per-protein priors

After 5+ completed cooks of the same protein OR 10+ total cooks, the predictor blends a historical prior into the live fit:

```
k = α × k_prior + (1 − α) × k_live
α = max(0.2, 1 − n_samples/20)
```

Smooth ramp: 100% prior at 0 samples (when live fit can't be computed), 80% live by 20 samples (~10 min into a cook).

The prior `k_prior` is computed from past cooks in `sessions.csv`:

```
k_past = ln((T0 − chamber_avg) / (Tf − chamber_avg)) / duration_seconds
```

per-cook closed-form, where `T0`, `Tf`, `chamber_avg`, `duration` come from the row.

Priors are weight-scaled to the current cook using mass^(-1/3) (heat transfer through similar-shape meat scales with surface area / volume). A historical 9 lb brisket's `k = 0.0008` becomes `k ≈ 0.00067` when the current cook is 16 lb.

Gating: per-protein cluster needs ≥5 cooks for protein-specific prior; falls back to cross-protein cluster needing ≥10 total. Below either threshold → no prior, Tier 1 only.

`prior_source` attribute on the ETA sensor tells you which path is active: `null`, `cross_protein(N)`, or `<protein>(N)`.

## Tier 3: stall detection

Collagen rendering on big cuts (brisket, pork shoulder) plateaus probe temp for hours. The state machine flags this as a sustained low rolling stdev on the probe trajectory in the typical stall window (140–175°F):

```
in_stall = (rolling_stdev(last 10 samples) < 0.5°F) AND (latest_probe ∈ [140, 175])
```

`in_stall: true` shows up as an attribute on the ETA sensor. The card surfaces it as an orange "🛑 in stall" chip on the probe tile.

ETA still computes during stall but reads very long because Newton's-law `k` collapses (probe isn't moving). The card hides the ETA value when `in_stall: true` and shows the stall callout instead.

## Disturbance reset

Lid-opens cause chamber temp to drop sharply, which would poison a live fit. The session tracker detects disturbances and the predictor's rolling buffer auto-flushes within ~30 min via the natural sliding window. Future enhancement: explicit reset on disturbance event.

## Interpreting the values

- **First ~5 polls (2.5 min)**: ETA is `unknown`. Be patient.
- **Pre-stall**: ETA shrinks naturally as probe rises, fit improves. Trust it within ±15% by 10 min in.
- **In stall**: ETA balloons. Card shows stall indicator instead. Real time-to-target depends on stall duration which varies cook-to-cook.
- **Post-stall**: Probe rises sharply again. ETA snaps back to a meaningful, often-shorter number.

## Tunables

In [`cook_predictor.py`](../custom_components/prime_polaris/cook_predictor.py):

```python
NEWTON_FIT_MIN_SAMPLES = 5      # need at least N samples before fit is meaningful
NEWTON_FIT_MAX_SAMPLES = 60     # rolling window — older samples drop off
STALL_WINDOW_SAMPLES   = 10     # samples to compute rolling stdev over
STALL_STDEV_THRESHOLD  = 0.5    # °F — below this on STALL_WINDOW samples = stall
STALL_TEMP_LOW         = 140.0  # °F — stall plateau typically starts here
STALL_TEMP_HIGH        = 175.0  # °F — and ends here

PRIOR_MIN_PER_PROTEIN = 5    # need ≥N cooks of the same protein
PRIOR_MIN_TOTAL       = 10   # else need ≥N cooks across any protein
```

Adjust per your environment. Smaller `STALL_TEMP_HIGH` makes stall detection less aggressive on roasts that breeze through the stall.

## What the predictor doesn't model

- **Wind** — the integration logs wind speed to CSV per cook for future analysis but doesn't feed it into the predictor. Convective heat loss off the cook chamber affects how hard the controller works to maintain setpoint, which indirectly affects probe rise — but it's a second-order effect.
- **Multiple stalls** — some long cooks have a brief secondary plateau. Tier 3 catches the main collagen stall; secondary plateaus are detected as just unusually slow rise.
- **Spritz / wrap events** — wrapping in foil/butcher paper accelerates the cook past the stall. The predictor doesn't know about this; it'll re-converge quickly once probe slope picks back up.
- **Smoke mode** — chamber temp wobbles ±15°F by design (P-cycle, not PID) which makes `(chamber - probe)` noisy. The fit still works but is less precise. Stall detection is unaffected (it's probe-only).
