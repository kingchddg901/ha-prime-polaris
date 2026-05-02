"""
/* ============================================================
 * cook_predictor.py — Live Cook ETA + Stall Detection
 * ============================================================
 *
 * Pure-Python prediction module for active cooks. Two layers:
 *
 *   1. Newton's-law-of-cooling fit per probe (live, current cook
 *      only — no history needed). Uses rolling least-squares to
 *      estimate the cooling coefficient k from observed probe
 *      slope vs (chamber − probe) drive. Forward-extrapolates
 *      to estimate seconds-remaining-until-target.
 *
 *   2. Stall detection — collagen rendering on big cuts (brisket,
 *      pork shoulder) plateaus probe temp for hours. Detected as
 *      sustained low rolling stdev on the probe trajectory in
 *      the typical stall window (140–175°F).
 *
 * Designed to be reset on disturbance events (lid open) so the
 * fit isn't poisoned by a step-drop in chamber temp.
 *
 * Tier-2 personalization (per-protein, per-weight history priors)
 * lives elsewhere — see project memory for the design.
 * ============================================================
 */
"""

from __future__ import annotations

import csv
import logging
import math
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Deque

_LOGGER = logging.getLogger(__name__)

# Tier 2 gating thresholds — below these counts we don't apply
# a prior (predictions stay pure Tier 1 — current-cook fit only).
PRIOR_MIN_PER_PROTEIN = 5    # need ≥N cooks of the same protein
PRIOR_MIN_TOTAL       = 10   # else need ≥N cooks across any protein

# Heat-transfer through similar-shape meat scales as mass^(-1/3).
# Used to scale a prior k (recorded at one weight) to the current
# cook's weight: k_target = k_prior × (w_prior / w_target)^(1/3).
WEIGHT_SCALING_EXPONENT = 1 / 3

# Tunables
NEWTON_FIT_MIN_SAMPLES = 5      # need at least N samples before fit is meaningful
NEWTON_FIT_MAX_SAMPLES = 60     # rolling window — older samples drop off
STALL_WINDOW_SAMPLES   = 10     # samples to compute rolling stdev over
STALL_STDEV_THRESHOLD  = 0.5    # °F — below this on STALL_WINDOW samples = stall
STALL_TEMP_LOW         = 140.0  # °F — stall plateau typically starts here
STALL_TEMP_HIGH        = 175.0  # °F — and ends here


@dataclass
class ProbeSample:
    ts: datetime
    probe: float
    chamber: float


class ProbePredictor:
    """Tracks one probe's history and produces ETA / stall estimates."""

    def __init__(self) -> None:
        self._history: Deque[ProbeSample] = deque(maxlen=NEWTON_FIT_MAX_SAMPLES)

    def reset(self) -> None:
        """Clear history — call after a disturbance (lid open) so the
        fit isn't biased by the chamber-temp step drop."""
        self._history.clear()

    def observe(self, ts: datetime, probe: float, chamber: float) -> None:
        self._history.append(ProbeSample(ts, probe, chamber))

    @property
    def sample_count(self) -> int:
        return len(self._history)

    # --- Newton's law fit ------------------------------------

    def fit_k(self, prior: float | None = None) -> float | None:
        """Estimate Newton's-law coefficient k from rolling history.

        If `prior` is given, blends with the live fit on a sliding
        scale: 100% prior at 0 samples, ~80% live by 20 samples.
        Smooth ramp prevents jarring transitions as data accumulates.

        Model: dT/dt = k × (chamber − probe)
        Live regression (intercept fixed at 0) across consecutive pairs:
            k_live = Σ (drive_i × rate_i) / Σ (drive_i²)
        """
        live_k = self._fit_k_live()

        if prior is None:
            return live_k
        if live_k is None:
            return prior  # not enough live data — pure prior

        # Blend factor: 1.0 at 0 samples, 0.2 at 20+ samples
        n = len(self._history)
        alpha = max(0.2, 1.0 - n / 20.0)
        return alpha * prior + (1.0 - alpha) * live_k

    def _fit_k_live(self) -> float | None:
        """Pure rolling-regression fit, no prior."""
        if len(self._history) < NEWTON_FIT_MIN_SAMPLES:
            return None

        samples = list(self._history)
        num = 0.0
        den = 0.0
        for a, b in zip(samples[:-1], samples[1:]):
            dt = (b.ts - a.ts).total_seconds()
            if dt <= 0:
                continue
            rate = (b.probe - a.probe) / dt              # °F per second
            drive = (a.chamber + b.chamber) / 2 - (a.probe + b.probe) / 2
            if drive <= 0:
                # probe at or above chamber — physical regime is different
                continue
            num += drive * rate
            den += drive * drive

        if den == 0:
            return None
        k = num / den
        # Reject obviously bad fits (negative k means probe falling
        # faster than chamber — could be a transient, lid open, etc)
        if k <= 0 or k > 0.05:  # 0.05/s is way too fast; sanity bound
            return None
        return k

    def eta_seconds(
        self, target: float, prior: float | None = None
    ) -> float | None:
        """Seconds until probe reaches target, given the current fit.

        Solves T(t) = C − (C − T0) × exp(−kt)  for t at T(t) = target,
        assuming chamber holds at its current value going forward:

            t = ln((T0 − C) / (target − C)) / k

        Returns None if model can't be fit, target is unreachable
        (target ≥ chamber), or probe is already at/above target.
        """
        if not self._history:
            return None
        latest = self._history[-1]
        T0 = latest.probe
        C = latest.chamber

        if T0 >= target:
            return 0.0
        if C <= target:
            return None  # chamber too cold to ever reach target
        k = self.fit_k(prior=prior)
        if k is None:
            return None

        ratio = (T0 - C) / (target - C)
        if ratio <= 0:
            return None
        return math.log(ratio) / k

    # --- Stall detection -------------------------------------

    def stall(self) -> tuple[bool, float | None]:
        """(in_stall, recent_stdev). True only when probe temp plateaus
        in the typical collagen-stall range with low rolling stdev.
        """
        if len(self._history) < STALL_WINDOW_SAMPLES:
            return False, None
        recent = [s.probe for s in list(self._history)[-STALL_WINDOW_SAMPLES:]]
        try:
            sigma = statistics.stdev(recent)
        except statistics.StatisticsError:
            return False, None
        latest = recent[-1]
        in_window = STALL_TEMP_LOW <= latest <= STALL_TEMP_HIGH
        return (sigma < STALL_STDEV_THRESHOLD and in_window), sigma


class CookPredictor:
    """Container for both probe predictors plus session-level state."""

    def __init__(self, csv_path: Path | None = None) -> None:
        self.probes: dict[int, ProbePredictor] = {
            1: ProbePredictor(),
            2: ProbePredictor(),
        }
        self._priors = HistoryPriors(csv_path) if csv_path else None

    def reset(self) -> None:
        for p in self.probes.values():
            p.reset()

    def observe(
        self, ts: datetime, chamber: float,
        probe_1: float | None, probe_2: float | None,
    ) -> None:
        if probe_1 is not None and probe_1 > 0:
            self.probes[1].observe(ts, probe_1, chamber)
        if probe_2 is not None and probe_2 > 0:
            self.probes[2].observe(ts, probe_2, chamber)

    def reload_priors(self) -> None:
        """Re-read sessions.csv. Cheap to call — caller can invoke at
        session start so the latest CSV state informs predictions."""
        if self._priors is not None:
            self._priors.load()

    def get_prior(
        self, protein: str, weight_lb: float | None
    ) -> tuple[float | None, str | None]:
        """Return (k_prior, source_label) for current cook context."""
        if self._priors is None:
            return None, None
        return self._priors.get_prior(protein, weight_lb)


# === Tier 2: history priors ==================================


@dataclass
class HistoricalCook:
    protein: str
    weight_lb: float | None
    k: float        # derived from chamber_avg / probe initial / final / duration


class HistoryPriors:
    """Loads sessions.csv, derives a Newton's-law k per past cook,
    and exposes weight-scaled priors per protein.

    The closed-form k from CSV columns alone:
        T(t) = C − (C − T0) × exp(−kt)
        At t = duration:   T(t) ≈ probe_final
        k = ln((T0 − C) / (Tf − C)) / duration_seconds

    Skips rows where the data isn't suitable (probe never rose,
    final ≥ chamber, missing fields, etc).
    """

    def __init__(self, csv_path: Path) -> None:
        self._csv_path = csv_path
        self._by_protein: dict[str, list[HistoricalCook]] = defaultdict(list)
        self._all: list[HistoricalCook] = []
        self._loaded = False

    def load(self) -> None:
        self._by_protein.clear()
        self._all.clear()
        self._loaded = True

        if not self._csv_path.exists():
            return

        try:
            with self._csv_path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cook = self._row_to_cook(row)
                    if cook is None:
                        continue
                    self._all.append(cook)
                    if cook.protein:
                        self._by_protein[cook.protein].append(cook)
        except OSError as err:
            _LOGGER.warning("Could not read sessions.csv for priors: %s", err)

    @staticmethod
    def _row_to_cook(row: dict) -> HistoricalCook | None:
        try:
            protein = (row.get("protein") or "").strip().lower()
            weight = (
                float(row["weight_lb"]) if row.get("weight_lb") else None
            )
            chamber_avg = float(row.get("chamber_avg") or 0)
            duration_min = float(row.get("duration_min") or 0)
        except (TypeError, ValueError):
            return None

        # Probe 1 first; fall back to probe 2 if 1 unusable
        for prefix in ("probe1", "probe2"):
            try:
                T0 = float(row.get(f"{prefix}_initial") or 0)
                Tf = float(row.get(f"{prefix}_final") or 0)
            except (TypeError, ValueError):
                continue
            if T0 <= 0 or Tf <= 0 or duration_min <= 0 or chamber_avg <= 0:
                continue
            if Tf <= T0:           # probe didn't rise — not a real cook of this probe
                continue
            if Tf >= chamber_avg:  # asymptote violated; degenerate fit
                continue

            ratio = (T0 - chamber_avg) / (Tf - chamber_avg)
            if ratio <= 0:
                continue
            try:
                k = math.log(ratio) / (duration_min * 60.0)
            except ValueError:
                continue
            if k <= 0 or k > 0.05:
                continue

            return HistoricalCook(protein=protein, weight_lb=weight, k=k)

        return None

    def get_prior(
        self, protein: str, weight_lb: float | None
    ) -> tuple[float | None, str | None]:
        """Returns (k_prior, source_label) for the current cook context.

        Gating order:
          1. Per-protein cluster with ≥PRIOR_MIN_PER_PROTEIN cooks
          2. Cross-protein (any) with ≥PRIOR_MIN_TOTAL cooks
          3. None (no prior; Tier 1 only)
        """
        if not self._loaded:
            self.load()

        protein = (protein or "").strip().lower()

        # Tier 2a: per-protein
        cluster = self._by_protein.get(protein, [])
        if len(cluster) >= PRIOR_MIN_PER_PROTEIN:
            k = self._weighted_mean_k(cluster, weight_lb)
            if k is not None:
                return k, f"{protein}({len(cluster)})"

        # Tier 2b: cross-protein fallback
        if len(self._all) >= PRIOR_MIN_TOTAL:
            k = self._weighted_mean_k(self._all, weight_lb)
            if k is not None:
                return k, f"cross_protein({len(self._all)})"

        return None, None

    @staticmethod
    def _weighted_mean_k(
        cooks: list[HistoricalCook], target_weight: float | None
    ) -> float | None:
        """Mean k across cooks, scaled to target_weight using the
        physics-based mass^(-1/3) law. Cooks without weight data
        contribute unscaled (best-effort)."""
        if not cooks:
            return None
        scaled = []
        for c in cooks:
            if target_weight and c.weight_lb and c.weight_lb > 0:
                scale = (c.weight_lb / target_weight) ** WEIGHT_SCALING_EXPONENT
                scaled.append(c.k * scale)
            else:
                scaled.append(c.k)
        return statistics.fmean(scaled) if scaled else None
