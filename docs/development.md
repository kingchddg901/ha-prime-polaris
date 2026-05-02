# Development & Architecture

This integration was reverse engineered for Pit Boss WiFi grills running the GrillirG / Prime Polaris cloud, but the underlying patterns apply to **any white-label cloud-pellet-grill platform**. If you have hardware running a similar OEM controller (Z Grills, Char-Griller WiFi, Recteq Ridge, etc.), most of this code maps over with cloud endpoint substitutions and minor field-name tweaks.

This doc covers the architecture, what's brand-specific vs. generic, and how to fork for a sibling brand or extend the existing integration.

## Architecture

```
                       ┌──────────────────────────────────────────┐
                       │  HA Lovelace card (custom_element JS)    │
                       │   src in github/ha-prime-polaris-card/   │
                       │   bundled as www/ha-prime-polaris-card.js │
                       └─────────────────┬────────────────────────┘
                                         │ entity reads + service calls
                       ┌─────────────────▼─────────────────────────┐
                       │  HA core entity layer                      │
                       │   sensor / number / switch / text /        │
                       │   climate platforms                        │
                       └─────────────────┬──────────────────────────┘
                                         │
   ┌────────────────────┐                │
   │  FCM listener      │ events         │  coordinator data
   │  (firebase-msging) │ ──────────────▶│
   └────────────────────┘                │
                                         │
                       ┌─────────────────▼──────────────┐
                       │   PrimePolarisCoordinator      │
                       │   (DataUpdateCoordinator)      │
                       │  - 30s REST poll               │
                       │  - alarm event diff            │
                       │  - cook session tracker hook   │
                       │  - cook predictor hook         │
                       └─────────────────┬──────────────┘
                                         │
                       ┌─────────────────▼──────────────┐
                       │   PrimePolarisApiClient        │
                       │   (REST over aiohttp)          │
                       └─────────────────┬──────────────┘
                                         │
                                  api.prime-polaris.com
```

## Module map

```
custom_components/prime_polaris/
├── __init__.py            entry setup/unload, services + frontend wiring
├── api.py                 REST client — auth, device queries, commands, exceptions
├── climate.py             climate entity — single one per device, exposes setpoint + presets + diagnostic attrs
├── config_flow.py         email + OTP flow + reauth + options flow (FCM toggle, dedup window)
├── const.py               domain, endpoint paths, field names, status enums, FCM creds
├── coordinator.py         DataUpdateCoordinator subclass — owns the poll loop and orchestrates predictors / sessions
├── cook_predictor.py      Newton's-law fit + stall detection + per-protein priors loaded from CSV
├── fcm_listener.py        firebase-messaging wrapper, MCS connect, push dedup, HA event fire
├── frontend.py            registers the bundled card as a static path + Lovelace resource
├── manifest.json          HACS / HA integration metadata, requirements
├── number.py              number entities — setpoint, smoke level, probe targets, FCM dedup knob
├── sensor.py              sensor entities — chamber temp, probes, ETA, mode, last alarm, etc
├── services.py            request_otp, verify_otp, clear_cook_inputs (called by the card)
├── services.yaml          service descriptions for HA UI
├── session_logger.py      cook session tracker — accumulates samples, writes CSV per cook
├── strings.json           dev source for translations
├── switch.py              switch entities — smoke, winter, alarm, cook session, push alerts, FCM enable
├── text.py                text entities — notes, protein, weight, ambient/wind override
├── translations/          generated UI strings (en.json)
└── www/                   bundled Lovelace card
```

## Brand-specific vs. generic

### Brand-specific (where to change for a different white-label)

| File | Brand specifics | What to change |
|---|---|---|
| `const.py` | `API_BASE`, all `ENDPOINT_*`, `FCM_*` credentials | Sniff the new brand's APK to recover these |
| `api.py` | Request/response field names (e.g. `verifyCode`, `furnace_temp_setting`), error code conventions | Update field names; the request shape is likely similar |
| `frontend.py` | `CARD_URL_PATH` reference | Just rename to match your new domain |
| `manifest.json` | `domain`, `name`, `documentation`, `issue_tracker` | Standard rebrand |
| `translations/en.json` | UI strings (Pellet Grill name, error messages) | Standard rebrand |

### Brand-generic (transplants without changes)

- **Coordinator pattern** — DataUpdateCoordinator with 30s polling, failure tolerance, alarm event diff, predictor hook. Reuse as-is.
- **`cook_predictor.py`** — Newton's-law math is universal. Probe heating physics is the same regardless of brand.
- **`session_logger.py`** — CSV schema is general. `_check_disturbance` state machine works for any grill.
- **Reauth + Repairs patterns** — modern HA conventions, brand-independent.
- **Dual-account FCM architecture** — applies to any single-token-per-account cloud, which is most of them.
- **Card** — entity-prefix configurable, so the card itself works against any rebrand.

### Card entity-prefix

The card uses `entity_prefix` (default `grill`) to derive every entity_id it reads:

```yaml
type: custom:ha-prime-polaris-card
entity_prefix: my_smoker
```

If you fork the integration and rename the device class, just update `entity_prefix` in card config and the card targets your new entities.

## Adding to this integration

### A new sensor

1. Add a constant for the API field name to `const.py`:
   ```python
   FIELD_NEW_VALUE = "newApiField"
   ```
2. Add a `PrimePolarisensorDescription` entry to `SENSOR_DESCRIPTIONS` in `sensor.py`.
3. Done. Entity registers on next reload.

### A new switch / number / text

Same pattern — add a description entry to the appropriate platform file's descriptions tuple. Each platform's `setup_entry` iterates the tuple.

### A new HA service

1. Define schema and handler in `services.py`
2. Register in `async_register_services()`
3. Document in `services.yaml`
4. Done

### A new entity_category for diagnostic-only entities

Use `_attr_entity_category = EntityCategory.DIAGNOSTIC` (already used for the FCM dedup number). Tucks the entity under the device's "Diagnostic" tab.

## Forking for a sibling white-label brand

If you're targeting a different brand on a similar OEM cloud:

### Step 1: Decompile the official Android APK

Use `apktool` or just `unzip` + a string extractor (Python `binascii.b2a_uu` over the `index.android.bundle` works for Hermes-compiled RN apps). Extract:

- `resources.arsc` strings — Firebase project credentials live here as named resources (`google_app_id`, `gcm_defaultSenderId`, etc.)
- The compiled bundle string table — endpoint paths, field names, attribution strings

This integration's repo includes example reconnaissance scripts in [the card project](https://github.com/kingchddg901/ha-prime-polaris-card) that aren't strictly needed but show the pattern.

### Step 2: Map the cloud endpoints

Most cloud integrations follow a common shape:

- `/auth/login` or similar — token issuance
- `/devices` or `/queryDeviceList` — list devices on the account
- `/realtime` or `/queryRealTimeData` — current state poll
- `/control` or `/sendCommand` — write commands

Find the equivalent on your target cloud, hit each with `curl` to confirm the request/response shape.

### Step 3: Identify the field names

Each brand renames fields slightly. Common cases:

| Function | Prime Polaris | Common alternatives |
|---|---|---|
| Set chamber temp | `furnace_temp_setting` | `target_temp`, `setpoint`, `cookTempSetting` |
| Probe temp | `probeP1Measured` | `probe1`, `meatTemp1`, `mt1` |
| Smoke mode | `smokeMode` + `smokeLevel` | `smokeP`, `pSetting` |
| Running status | `runningStatus` | `state`, `mode`, `cookerState` |

Update `const.py`'s `FIELD_*` and `ENDPOINT_*` constants to match.

### Step 4: Test against your hardware

Spin up an entry, smoke-test the climate / probe / smoke / power-off paths. The cook predictor and session logger should "just work" if the field names are mapped correctly.

### Step 5: Brand the integration

Rename `domain` in `manifest.json`, update `name` and `translations/en.json`, update `frontend.py`'s `CARD_URL_PATH` if you want a brand-specific URL. The Lovelace card can be reused as-is via the `entity_prefix` config option.

## Build & deploy

### Integration

The integration is plain Python. No build step. Just sync source files into your HA's `<config>/custom_components/<domain>/` and restart HA.

For dev iteration: keep the source in this repo and copy on save. Or symlink.

### Card

The card is in a separate repo: [github.com/kingchddg901/ha-prime-polaris-card](https://github.com/kingchddg901/ha-prime-polaris-card). It's an esbuild-bundled vanilla-JS / shadow-DOM custom element.

```bash
cd ../ha-prime-polaris-card
npm install
npm run build      # produces dist/ha-prime-polaris-card.js
PRIME_POLARIS_INTEGRATION=//path/to/this/repo/custom_components/prime_polaris npm run deploy
```

`npm run deploy` builds and copies the bundle into the integration's `www/` directory. Bump `CARD_VERSION` in both `cook_predictor.py`-side `frontend.py` and the card's `src/constants.js` to match (the version becomes the cache-bust query param on the Lovelace resource URL).

## Release process

1. Bump `version` in `manifest.json`
2. Update `CHANGELOG.md` with the new section
3. If shipping a new card bundle: build + deploy + bump `CARD_VERSION` in `frontend.py`
4. Commit, tag, push:
   ```bash
   git add -A && git commit -m "v0.X.Y: <summary>"
   git tag vX.Y.Z && git push origin main vX.Y.Z
   ```
5. Create a GitHub release on the tag (the validation workflow runs HACS + hassfest checks)
6. HACS users get the update on their next HACS refresh

## Testing

There's no automated test suite yet. Manual testing is what we have:

- **Smoke test**: setpoint change, smoke toggle, alarm switch, probe target — confirm via Developer Tools → States that the values flow through cleanly
- **Cook session**: start session, change setpoint, end session, verify CSV row makes sense
- **FCM**: enable, induce alarm (drop setpoint below current chamber), confirm push arrives at HA event listener
- **Reauth**: in card's Setup tab, click Re-authenticate, walk through the flow

Any contributions should mention which paths were exercised. PRs welcome.

## Contributing

1. Fork → branch → PR
2. Match the existing style (no Black or formatter enforced; the Python is pep8-flavored)
3. New features: add a CHANGELOG entry and update relevant docs
4. New endpoints discovered: add to `docs/api.md`
5. New device-class quirks observed: note in [api.md → Open / unverified](api.md#open--unverified)
