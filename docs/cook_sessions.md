# Cook Sessions

Each cook you record gets one row in `<config>/prime_polaris/sessions.csv` — a flat 23-column file you can open in Excel or `pandas.read_csv` directly.

## Recording a cook

1. Set protein / weight / notes on the **Live** tab (Live → This cook section)
2. Flip `switch.<name>_cook_session` ON when the meat hits the grill
3. Cook normally
4. Either:
   - Flip the switch OFF when food's pulled (preferred — gives clean duration), OR
   - Power off the grill — auto-stop fires and finalises the row

## Schema

| Column | Type | Notes |
|---|---|---|
| `cook_id` | str | 12-char uuid suffix |
| `started_at` | iso datetime | session start, UTC |
| `ended_at` | iso datetime | session end |
| `duration_min` | float | minutes between start and end |
| `protein` | str | from text input, lowercased |
| `weight_lb` | float | from text input |
| `ambient_start` | float | resolved at cook start, °F |
| `ambient_avg` | float | mean across cook |
| `wind_speed_avg` | float | mean across cook |
| `mode` | str | `temperature` or `smoke` (snapshot at start) |
| `smoke_level` | int | 0–10 if mode=smoke, else null |
| `setpoint` | int | °F at cook start |
| `chamber_avg` | float | mean across cook |
| `chamber_stdev` | float | stdev, °F |
| `chamber_peak` | float | max chamber temp |
| `chamber_min` | float | min chamber temp |
| `probe1_target` | int | °F |
| `probe1_initial` | float | probe 1 reading at cook start |
| `probe1_final` | float | probe 1 reading at cook end |
| `probe2_target` | int | °F |
| `probe2_initial` | float | probe 2 at start |
| `probe2_final` | float | probe 2 at end |
| `disturbance_count` | int | inferred lid-open events during cook |
| `ended_normally` | int | 1 if user-stopped or grill-off; 0 if interrupted |
| `notes` | str | free-form from text input |

### Sample row

```csv
cook_id,started_at,ended_at,duration_min,protein,weight_lb,ambient_start,...
a3f9c2e8b1d4,2026-05-02T16:02:00+00:00,2026-05-03T00:14:30+00:00,492.5,brisket,16.0,68.0,...
```

## Disturbance count

`disturbance_count` is the number of inferred lid-open events during the cook. The state machine watches the chamber-temp signal during temperature-mode cooks and looks for a sustained drop (≥3°F per 30s) that recovers within ~2 minutes after a total drop of ≥15°F. Smoke mode disables detection (the natural sawtooth would false-positive constantly).

For each disturbance, an HA event `prime_polaris_disturbance` fires with `cook_id`, `detected_at`, `peak_drop`, `chamber_at_start`, `chamber_lowest`, `recovery_seconds`. Subscribe to that event for per-event automations (e.g. push notification when the lid's been open for too long).

The CSV only carries the count summary — for forensic per-event detail, use the HA recorder's per-sample chamber temp history or build a side CSV via your own automation.

## Analysis recipes

### Mean chamber by protein

```python
import pandas as pd
df = pd.read_csv("/config/prime_polaris/sessions.csv")
df.groupby("protein")["chamber_avg"].agg(["mean", "std", "count"])
```

### Smoke level → chamber profile

```python
smoke = df[df["mode"] == "smoke"]
smoke.groupby("smoke_level").agg(
    avg=("chamber_avg", "mean"),
    swing=("chamber_stdev", "mean"),
    cooks=("cook_id", "count"),
)
```

### Cook duration vs weight (linear fit per protein)

```python
import numpy as np
brisket = df[df["protein"] == "brisket"].dropna(subset=["weight_lb", "duration_min"])
m, b = np.polyfit(brisket["weight_lb"], brisket["duration_min"], 1)
print(f"~{m:.0f} min/lb + {b:.0f} min baseline")
```

### Disturbance impact on chamber stability

```python
df.groupby("disturbance_count")[["chamber_stdev", "chamber_avg"]].mean()
```

Should show stdev climbing as disturbance count rises.

### Ambient effect on cook duration

```python
brisket = df[df["protein"] == "brisket"].dropna(subset=["ambient_avg", "duration_min", "weight_lb"])
brisket["min_per_lb"] = brisket["duration_min"] / brisket["weight_lb"]
brisket.plot.scatter(x="ambient_avg", y="min_per_lb")
```

Cooler ambient → longer min/lb. The relationship is real but noisy.

## Backups

The CSV is plain text in `<config>/prime_polaris/`. Include it in your HA backups (the standard backup includes `<config>` by default). For long-term archival, copy it offsite periodically — at ~5 KB per cook, a year of cooks is well under 1 MB.

## Resetting

To start fresh:

```bash
mv <config>/prime_polaris/sessions.csv <config>/prime_polaris/sessions.archived.csv
```

Next cook creates a new file with the header. Tier 2 priors will rebuild from the new history as cooks accumulate.

## Editing past rows

The CSV is append-only from the integration's perspective — there's no service to retroactively edit a row. If you mis-typed a protein or weight, edit the file directly with any text editor. Tier 2 priors will re-load on the next cook session start.

## Per-cook overrides

Most cooks will use whatever defaults are configured in Setup. For one-off cooks where you want to override:

1. Live tab → flip session OFF if it's currently on
2. Type the override into Cook Ambient Override / Cook Wind Override
3. Flip session ON — values are snapshotted at this moment

Per-cook overrides are cleared when the session ends. Defaults (set in Setup) persist across cooks.
