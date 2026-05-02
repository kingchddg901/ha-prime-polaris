# Troubleshooting

## Setup / connection

### "OTP request failed" during initial setup

The cloud rejected the email-OTP send. Common causes:

- **Wrong domain** — accounts created via the Pit Boss app vs the GrillirG app share the cloud but accounts created via grill-side WiFi setup use a slightly different login flow on some firmware. If this fails, try signing in to the official Android app first to confirm credentials, then retry.
- **Network issue** — the integration logs `Cannot reach Prime Polaris cloud`. Check `https://api.prime-polaris.com` is reachable from HA.
- **Email blocklisted** — some throwaway providers (Mailinator, etc.) get blocked by the cloud. Use a real address.

### "No grills found on this account"

The account has no devices bound. Either:
- The grill isn't paired with this account in the official app — pair it there first.
- For dual-account setups, the device wasn't shared yet — check the primary account did the share, and the secondary accepted it.

### Card shows but state is `unavailable`

The integration loaded but the first poll failed. Watch HA logs for a more specific error:

```
2026-05-02 12:00:00 ERROR (MainThread) [custom_components.prime_polaris.coordinator] ...
```

Common causes:
- **Token expired** — should auto-trigger reauth flow. Check Settings → Devices & Services for a "Reconfigure" prompt, or use the card's Setup tab → Re-authenticate.
- **Cloud outage** — try `curl https://api.prime-polaris.com/api/dms/queryDeviceListByUserId` from your HA host. If that's down, you can't do anything about it.

## Card

### Card shows "Custom element doesn't exist: ha-prime-polaris-card"

The card JS didn't load. Hard-refresh the browser (Ctrl+Shift+R). If still broken:

1. **Settings → Dashboards → Resources** — does the entry `/prime_polaris_card/ha-prime-polaris-card.js` exist?
2. If not, the auto-registration didn't fire. Restart HA. Check the integration's log for `Registered Lovelace card resource` on startup.
3. If still missing, manually add: **Resources → Add Resource → URL** = `/prime_polaris_card/ha-prime-polaris-card.js?v=0.4.2`, **Type** = JavaScript Module.

### Probe ETA stuck at "fitting…"

Less than 5 polls have completed since the probe was plugged in (or probe temp ≤ 0). Wait ~3 minutes. If still stuck:

- Probe might be reading `0` because of a hardware issue (probe seated wrong, cable damaged) — check directly via `sensor.<name>_probe_N_temperature`.
- Chamber temp is below probe temp — the predictor only fits when `(chamber - probe) > 0`. This is rare but happens during shutdown.

### "Ambient unresolved" red chip

The text in `Cook Ambient Override` (Setup tab) doesn't resolve to a number. Either:

- Typo in the entity_id — fix it
- Entity doesn't exist or is `unknown` / `unavailable` — check `hass.states[your_entity_id]`
- For `weather.*` entities, the `temperature` attribute must be present

A literal number (`32`) always resolves; use that as a fallback while debugging.

### Chamber gauge doesn't update

The arc redraws on every coordinator poll (~30s). If frozen for longer:

- Check `sensor.<name>_chamber_temperature` is updating in HA Developer Tools → States
- Hard-refresh the browser

## FCM push alerts

### Pushes don't arrive at HA

1. Verify FCM is enabled: `switch.<name>_push_alerts` should be ON
2. Check integration log for `FCM token registered with prime-polaris` on the most recent restart
3. Trigger a real alarm (drop chamber setpoint below current chamber temp) and watch the log for `FCM push received: ...`

If still nothing, the FCM listener probably failed to start. The `firebase-messaging` Python library can be finicky on some HA installs. Disable FCM and use polling-only.

### Pushes arrive at HA but no longer at the phone

You're hitting the single-token-per-account limit. Either:

- Reopen the official app on your phone (re-registers the phone's token, displaces HA's). Repeat as needed.
- Switch to the **dual-account setup** ([setup.md → Path B](setup.md#path-b-dual-account-recommended)). Permanent fix.

### Pushes arrive at both but `sensor.<name>_last_alarm` doesn't update

Check the alarm dedupe window. Pushes for the same alarm category fire every ~25–30s while the condition persists; the dedupe suppresses repeats. Default 60s window means only the first ~2 pushes of a sustained alarm produce an HA event. Adjust via Setup tab → Push alert dedupe (or the option flow).

## Cook session

### Session row never appears in `sessions.csv`

The row writes when the session ends. Either:

- You haven't toggled the session OFF yet
- The grill hasn't gone Off (no auto-stop trigger)
- The directory `<config>/prime_polaris/` doesn't exist or HA can't write to it (check permissions)

Watch the integration log for `Cook session ended (cook_id=...)` to confirm the write fired.

### `chamber_avg` looks way wrong

Two main causes:

- You started recording while the grill was still warming up — `chamber_avg` includes the climb. Either tag in notes, or only start recording once the grill is at temp.
- The cook went into smoke mode mid-cook — `mode` snapshots at start, so a temperature-mode session that switches to smoke will show `chamber_avg` averaged over both phases.

## Logs

The integration logs under `custom_components.prime_polaris`. To enable debug:

```yaml
# configuration.yaml
logger:
  logs:
    custom_components.prime_polaris: debug
```

Then **Settings → System → Logs** filter by that prefix.
