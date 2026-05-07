# Prime Polaris Pellet Grill

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Home Assistant integration for pellet grills running the Prime Polaris / GrillirG cloud platform — including the **Pit Boss WiFi** lineup (`pb1000d3` and friends running the A10 controller).

Reverse engineered from the official GrillirG Control Android APK. Same cloud, same alarms, same control surface — just inside HA.

## Features

- **Live grill state** — chamber temp, probe temps, smoke level, running status
- **Full control** — setpoint, smoke mode + level, probes, winter mode, alarm switch
- **Bundled Lovelace card** — auto-registers on setup. No HACS plugin or manual resource step.
- **Live cook predictor** — Newton's-law fit per probe, ETA in min/h, stall detection. Optional per-protein priors that improve as you record cooks.
- **Cook-session CSV** — per-cook record (chamber stats, probe targets/finals, ambient, wind, disturbance count, your notes). Append-only, pandas-friendly.
- **Push alerts (FCM)** — connects to the OEM Firebase project so HA receives the same push notifications the official app does. Recommended dual-account setup keeps your phone's pushes intact.
- **Dashboard-driven account flows** — re-auth and reset live on the card's Setup tab. No Settings round-trip.

## Prerequisites

- Home Assistant 2024.11 or later
- A grill that's already paired with the official GrillirG / Prime Polaris / Pit Boss WiFi mobile app
- A registered account with the brand's mobile app

## Installation via HACS (custom repository)

1. **HACS → 3-dot menu → Custom repositories**
2. Repo URL: `https://github.com/kingchddg901/ha-prime-polaris` — Type: **Integration** — Add
3. Click **Install** on the new entry. Restart HA.
4. **Settings → Devices & Services → Add Integration → Pellet Grill**
5. Sign in with your account email (you'll receive a 6-digit OTP).

The bundled Lovelace card is auto-registered on first setup. Drop into any view:

```yaml
type: custom:ha-prime-polaris-card
```

## Recommended dual-account setup

The OEM cloud is **single-token-per-account**: registering an FCM push token under your account replaces whatever's there (e.g. your phone's). To get *both* phone alerts AND HA alerts, use a second account that the device is shared to.

1. **In the official app**: create a second account with a fresh email (Gmail `+alias` works fine). Complete OTP.
2. **In the official app, primary account**: invite the secondary email via Share Grill. Accept on the secondary side.
3. **In HA**: add the Pellet Grill integration *once*, using the **secondary** account's email + OTP. The grill appears via share.
4. **In HA**: open the entry's options (Settings → Integrations → Pellet Grill → Configure) → enable FCM push alerts.

Both your phone (primary account's token) and HA (secondary account's token) receive the same push notifications simultaneously. This was empirically confirmed on 2026-05-02.

## Single-account setup (simpler, less ideal)

If you don't want a second account, you can enable FCM under your primary. Your phone will stop receiving Prime Polaris pushes until you reopen the official app (which re-registers its token, displacing HA's again).

## Entities

After setup, the grill device exposes:

- `climate.<name>` — main climate entity
- `sensor.<name>_chamber_temperature` — chamber temp (long-term stats)
- `sensor.<name>_probe_1_temperature` / `_probe_2_temperature` — meat probes
- `sensor.<name>_probe_1_eta` / `_probe_2_eta` — live time-to-target with stall detection in attributes
- `sensor.<name>_running_status` — Cooking / Off / Starting / Error / Shutting Down
- `sensor.<name>_active_mode` — `temperature` / `smoke` / `off`
- `sensor.<name>_active_smoke_level` — smoke level 0–10 when smoke is on
- `sensor.<name>_last_alarm` — most recent alarm category, body in attributes
- `number.<name>_temperature` — type-in setpoint (1°F precision)
- `number.<name>_smoke_level` — slider 0–10
- `number.<name>_probe_1_target` / `_probe_2_target` — probe alert temps
- `number.<name>_push_alert_dedupe` — FCM dedup window (sec)
- `switch.<name>_smoke_mode` / `_winter_mode` / `_temperature_alarm` — toggles
- `switch.<name>_cook_session` — manual session recording (writes to sessions.csv)
- `switch.<name>_push_alerts` — FCM enable/disable (live, no Settings round-trip)
- `text.<name>_cook_notes` / `_cook_protein` / `_cook_weight_lb` — per-cook inputs
- `text.<name>_cook_ambient_override` / `_cook_wind_override` — default sensor pointers

## Cook predictor

Live ETA = Newton's-law-of-cooling fit over the probe's recent history:

```
dT_probe/dt = k × (T_chamber − T_probe)
```

`k` is fitted from 5+ samples on the current cook. Once you've recorded ~10 cooks total (or 5 of a single protein) the predictor adds a Bayesian-style warm-start prior based on past `k` values, scaled by mass^(-1/3) for the current cook's weight. Per-protein priors kick in at 5+ cooks of the same `protein` text input.

Stall detection: rolling stdev on the probe trajectory in the typical 140–175°F window.

The integration writes one row per cook to `<config>/prime_polaris/sessions.csv`. Open in Excel or `pandas.read_csv` for dial-in analysis.

## API origin

The cloud platform is `api.prime-polaris.com`, run by the OEM behind multiple grill brands. Discovery work was done by decompiling the official Android APK — credentials, endpoint shapes, push-event format all came from there. See the bundled [HACS card source](https://github.com/kingchddg901/ha-prime-polaris-card) for the matching frontend repo.

## Documentation

- [Setup walkthrough](docs/setup.md) — single-account and dual-account paths, step by step
- [Cook predictor](docs/predictor.md) — Newton's-law math, stall detection, per-protein priors
- [Cook sessions](docs/cook_sessions.md) — CSV schema and pandas analysis recipes
- [Troubleshooting](docs/troubleshooting.md) — common issues and fixes
- [API reference](docs/api.md) — every cloud endpoint we know about, field-by-field
- [Development & architecture](docs/development.md) — module map, brand-generic vs brand-specific code, fork-for-sibling-brand guide

## Forking for a sibling white-label

The Prime Polaris cloud is the OEM platform behind multiple grill brands (Pit Boss WiFi confirmed, others likely on similar OEM hardware). If you have a grill running a different cloud but using the same controller architecture, the cook predictor, session logger, dual-account FCM pattern, and Lovelace card transplant cleanly — you mainly need to remap the cloud endpoints and field names. See [development.md → Forking for a sibling white-label](docs/development.md#forking-for-a-sibling-white-label).

⚠️ Support status: hobby project, best-effort maintenance
I built this for my own use and share it in case it helps others. I can't commit to long-term maintenance, fast issue response, or feature requests. If you rely on this, be prepared to fork it or find a community maintainer if I step away.
PRs welcome. Issues may go unanswered.

## Issues

Bug reports and feature requests: [github.com/kingchddg901/ha-prime-polaris/issues](https://github.com/kingchddg901/ha-prime-polaris/issues)

## Distribution scope

This is a **HACS Custom Repository** — install via the Custom Repositories flow in HACS. It's deliberately *not* on the HACS default integration list and there's no plan to submit it. If someone wants to take this further (default HACS listing, brand assets PR to home-assistant/brands, ongoing default-list maintenance), the integration is MIT-licensed — fork it and run with it.

## License

MIT
