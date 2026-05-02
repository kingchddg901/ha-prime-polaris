# Changelog

All notable changes to this integration are documented here. Versioning is semver-ish — minor bumps for new features, patch bumps for bug fixes.

## [0.2.0] — 2026-05-02

### Added
- **Bundled Lovelace card** — auto-registered as a Lovelace resource on setup. No HACS plugin or manual resource step required.
- **Cook predictor**:
  - Live Newton's-law-of-cooling fit per probe → ETA in min/h on `sensor.<name>_probe_N_eta`
  - Stall detection (collagen plateau in 140–175°F window) surfaced as `in_stall` attribute
  - Per-protein weight-scaled history priors blended with live fit (active after ≥5 cooks of a protein OR ≥10 total cooks)
- **Cook-session tracker** — manual start via switch, auto-stop on grill power-off. Disturbance (lid-open) inference. Per-cook CSV at `<config>/prime_polaris/sessions.csv` with 23 columns.
- **FCM push receiver** — connects to the OEM Firebase project so HA receives the same push notifications the official app does. Opt-in via options. Dedup window configurable.
- **In-card account flows** — request_otp / verify_otp / clear_cook_inputs services drive a Setup tab UI for re-auth and reset. No Settings round-trip.
- **Auto-detected sensor suggestions** — Setup tab suggests `weather.*` and outdoor-hint / weather-attribution sensors as ambient/wind candidates.
- **Recipe presets** (in card) — eight defaults, custom recipes via card YAML.
- **Repairs issue** for token expiry warnings.
- **`extra_state_attributes`** on climate entity exposes email + token expiry for dashboard display.

### Changed
- **Poll failure tolerance** raised from 1 to 3 consecutive failures before entities flip to unavailable. Cloud blips no longer flicker the dashboard.
- **Reauth flow** modernized — uses `entry.async_start_reauth()` instead of persistent_notification.
- **Command paths** wrapped in `HomeAssistantError` for clean user-facing error messages.
- **Setpoint resolution** now true 1°F (was 25°F slider step). Min raised from 150°F to 180°F to match the controller's actual cooking minimum.
- **Ambient/wind override entities** are now persistent — set once in Setup, used as defaults for every cook.

### Removed
- Duplicate `sensor.<name>_probe_*_target` entities. The `number.*` versions cover the same field. Existing instances become orphaned in HA's entity registry — clean up via Settings → Devices & Services if desired.

## [0.1.0] — Initial release

- REST polling client for `api.prime-polaris.com`
- Climate / sensor / switch / number platforms
- Email + OTP config flow with reauth support
- Smoke / winter / alarm switch
- Probe target numbers
- Two-step cook control: setpoint via climate, smoke via switch + level slider
