# Cloud API Reference

The Prime Polaris / GrillirG cloud (`api.prime-polaris.com`) is the OEM platform behind multiple grill brands — Pit Boss WiFi (`pb1000d3` and others on the A10 controller), and likely Z Grills, Char-Griller, Recteq variants on similar Chinese OEM hardware. This document captures everything the integration knows about the cloud so future maintainers (and people building integrations for sibling white-labels) don't have to redo the discovery work.

All endpoints discovered via decompilation of the official Android APK + live testing on a Pit Boss `pb1000d3` running A10 firmware `002000002`.

## Base

```
Base URL : https://api.prime-polaris.com/api
Method   : POST (everything)
Headers  : Authorization: Bearer <jwt>
           Content-Type:  application/json
```

JWT is acquired via email + OTP (see Auth section). Tokens are valid ~180 days.

Standard response envelope:

```json
{
  "respCode":     10000,
  "respMessage":  "success",
  "timeString":   "5/2/2026, 9:11:49 AM",
  "path":         "/dms/...",
  "data":         { ... }
}
```

Non-success response codes start at `-10001`. Auth failures use `-10001` through `-10003` and `-10007`. Most validation errors use `-10004` with a human-readable `respMessage`.

## Auth

### Request OTP

```
POST /email/m2s/send/verify/code
Body: { "email": "user@example.com", "emailType": "Login" }
```

Server emails a 6-digit code. No body in success response.

### Login

```
POST /auth/m2s/email/login
Body: { "email": "user@example.com", "verifyCode": "123456", "emailType": "Login" }
Response data: { "token": "<jwt>", ... }
```

The JWT `exp` claim is the Unix expiry timestamp. Currently issued for 180 days.

### Logout

```
POST /auth/logout
```

Best-effort — invalidates the server-side session. Local token should still be discarded.

## Device

### Device list

```
POST /dms/queryDeviceListByUserId
Body: {}
Response data: { "list": [ { ... }, ... ], "count": N }
```

Each device entry includes:

| Field | Notes |
|---|---|
| `id` | Device ID — used as `deviceId` in all subsequent calls |
| `deviceName` | User-set name |
| `grillBrand` | e.g. `PITBOSS` — confirms the white-label brand |
| `grillModel` | e.g. `pb1000d3` |
| `modelName` | Controller model — `A10` for the wifi controllers we've seen |
| `firmwareVersion` | Used in command payloads |
| `deviceHardwareSpecificationsId` | Numeric ID for the controller hardware (5 for A10) |
| `deviceSoftwareSpecificationsId` | Variant of the controller (e.g. 60 for A99 grill body class) |
| `grillMeshArea` | Cooking surface area, in² |
| `manualLink` | URL to the official PDF manual |
| `runningStatus` | 0 / 1 / 2 / 3 / 4 / 5 — see status table below |
| `onlineStatus` | **0 = online**, non-zero = offline (counterintuitive — verified empirically) |
| `sharedFlag` | 0 = owner, 1 = shared to this account |
| `otaUpgradeStatus` | Probably 0=none, 1=available, 2=in-progress (untested) |

### Realtime data

```
POST /dms/queryDeviceRealTimeData
Body: { "deviceId": "<id>" }
Response data:
{
  "deviceSwitch":          0|1,        // power state
  "runningStatus":         0..5,
  "tempScale":             0,           // probably degree-format flag (untested)
  "smokeMode":             0|1,
  "smokeLevel":            0..10,
  "winter":                0|1,
  "refTemp":               0,           // current chamber temp at the moment winter mode was set?
  "furnaceTempSetting":    180..500,    // user-set target temp (°F)
  "furnaceTempMeasured":   0..600+,     // current chamber temp (°F)
  "tempUnit":              0,           // 0=Fahrenheit, 1=Celsius
  "forwardTimingStatus":   0|1,         // count-up timer running
  "forwardTimerValue":     int,
  "countdownStatus":       0|1,
  "countdownSetTimerValue": int,
  "countdownTimerValue":   int,
  "alarmSwitch":           0|1,         // user-toggleable temp alarm enable
  "alarmEvent":            [],          // ALARMS - schema unknown, see notes below
  "probeP1Setting":        0..500,      // probe 1 alert temp (°F)
  "probeP1Status":         0|1|2,       // 0=no target, 1=armed, 2=triggered
  "probeP1Measured":       0..500+,     // probe 1 reading (°F)
  "probeP2Setting":        ...,
  "probeP2Status":         ...,
  "probeP2Measured":       ...
}
```

### Status / heartbeat

Two simpler endpoints expose subsets of the realtime payload:

```
POST /dms/queryDeviceStatus      // runningStatus, onlineStatus, otaUpgradeStatus, sharedFlag
POST /dms/queryDeviceHeartbeat   // deviceId + onlineStatus
```

Useful for online-detection without the full data fetch.

### Hardware spec

```
POST /dms/queryDeviceSpec
Body: { "deviceId": "<id>", "deviceHardwareSpecificationsId": <id> }
```

Untested in detail — returns capability info.

## Commands

All commands go through one endpoint with a flat payload:

```
POST /dms/deviceFunctionSettings
Body: {
  "deviceId":        "<id>",
  "firmwareVersion": "<version>",
  ... command-specific fields ...
}
```

### Confirmed command fields

| Field | Type | Description |
|---|---|---|
| `furnace_temp_setting` | int | Setpoint °F (180–500). Ignored when `smokeMode=1`. |
| `device_switch` | 0 only | Power off. **Power on (`1`) is server-blocked** with `-10004` "command not supported". |
| `smoke_mode_and_smoke_level` | `[mode, level]` | Both must be sent together. mode 0/1, level 0–10. |
| `winter_and_ref_temp` | `[0\|1, refTemp]` | Winter mode toggle + current chamber temp. |
| `alarm_switch` | 0/1 | Master alarm enable. **Doesn't affect safety alarms** (ignition timeout, RTD fault) — those fire regardless. |
| `setProbeTemp` | `[ { "probeId": 1\|2, "temp_and_status": [temp, 1] } ]` | Probe alert target. **Min temp 100°F** (cloud rejects lower with `-10420`). |

### Mutual exclusion

**Smoke mode and temperature setpoint are mutually exclusive at the firepot.** The cloud accepts both being set without complaint, but the controller runs smoke mode when both are on (smoke wins at the auger). The realtime payload mirrors both values truthfully — a user who sets temp=225 then enables smoke will see both fields populated but the chamber will run the smoke P-cycle, not the PID setpoint.

The official app blocks setting both via UI gating. The integration intentionally doesn't (preserves API truth, surfaces the actual operating mode via `sensor.<name>_active_mode`).

## Sharing

```
POST /dms/shareDevice
Body: { "deviceId": "<id>", "subUserEmail": "<email>" }
```

Sends an invite. `-10402 user is not exist` if the target email isn't a registered Prime Polaris user — register them first via the OTP flow.

```
POST /dms/agreeSharedDevice    // recipient accepts
Body: { "deviceId": "<id>", "agreement_status": 0|1 }

POST /dms/userBindsDevice       // recipient binds the device to their account
Body: { "deviceId": "<id>", "deviceName": "<name>" }

POST /dms/queryUserSharedDevice // list devices currently shared with current user
Body: {}
```

The integration **never calls share endpoints** — the user does sharing manually via the official app before adding the secondary account to HA. The integration just queries `queryDeviceListByUserId` which returns shared devices alongside owned ones.

## Push notifications (FCM)

### Token registration

```
POST /api/auth/registerFcmToken
Body: { "fcmToken": "<fcm_token>", "deviceType": "android" }
```

Both fields required. `deviceType` accepts `"android"` or `"ios"`. Success: `respCode=10000`.

### FCM credentials (from APK resources)

```
project_id          : grillirg-control
google_app_id       : 1:225981028998:android:0bdbfcb8e235501edbcf07
google_api_key      : AIzaSyBRnBQnGn7URrtximmfUGkLbbHC5ge70JA
gcm_defaultSenderId : 225981028998
storage_bucket      : grillirg-control.firebasestorage.app
```

### Push payload schema

Captured 2026-05-02 from a temp-deviation alert:

```json
{
  "priority": "normal",
  "notification": {
    "title": "Furnace Temperature",
    "body":  "Furnace temperature is 225 ℉"
  },
  "data": {
    "screen": "DeviceMain",
    "params": "{\"deviceId\":\"<id>\",\"deviceHardwareSpecificationsId\":5,\"deviceSoftwareSpecificationsId\":60,\"deviceName\":\"<name>\"}"
  },
  "from": "225981028998",
  "fcmMessageId": "..."
}
```

`data.params` is a **JSON-encoded string**, not a nested object — parse twice. Other alarm categories (probe-target-reached, ignition timeout, etc.) likely use different `notification.title` values but the same envelope.

**Single token per account**: registering an FCM token under an account replaces any previously registered token. To avoid displacing the user's phone, use a separate account that the device is shared to (see [setup.md → Path B](setup.md)).

**Repeat rate**: pushes for the same alarm category fire every ~25–30s while the condition persists. The integration's listener dedupes by `notification.title` within a 60s window (configurable).

## Status enum

`runningStatus` values, observed empirically on `pb1000d3` / A10:

| Value | Label | Notes |
|---|---|---|
| `0` | (unused) | Suggested by APK strings, not seen in the wild |
| `1` | Starting | Brief — during ignition before flame is established |
| `2` | Cooking | Both "heating to setpoint" AND "holding at setpoint" — no separate steady-state value |
| `3` | Off | Direct transition from Cooking on power-off; no intermediate observed |
| `4` | Shutting Down | APK strings define this but **pb1000d3 doesn't emit it** during normal power-off. May be a different model or hold-to-off path. |
| `5` | Error | Confirmed by the user observing an ignition-timeout alarm in real life. Schema for what populates `alarmEvent` not yet captured (see notes below). |

## Open / unverified

### `alarmEvent` payload schema

The realtime payload's `alarmEvent` field is an array. We've never seen it non-empty — alarms appear to flow primarily through FCM push, and the realtime mirror clears `alarmEvent` between polls (transient by design). The integration has speculative wiring for it (sensor + HA event) but the entry shape is unknown until first capture in the wild.

### `runningStatus = 4`

APK strings suggest "Shutting Down" but never seen on `pb1000d3` — possibly emitted by a different controller variant during some shutdown path we haven't triggered.

### Other endpoints discovered but not used

- `/dms/queryDeviceProgramList` — returns the list of grill-size variants the controller supports (NOT cook recipes), e.g. for A10 controller: A45/A70/A99/C99 sizes
- `/dms/updateDeviceDetailsProgram` — sets the device's grill-size variant
- `/dms/sendRecoveryCommand` — recovery flow, untested
- `/dms/setAppCountdown`, `/dms/cancelAppCountdown`, `/dms/pauseAppCountdown` — server-side timer (we don't use it; HA users can use HA timers)
- `/dms/setAppCountup`, `/dms/cancelAppCountup`, `/dms/pauseAppCountup` — count-up version

### Socket.IO

The cloud also runs a Socket.IO endpoint at `/socket.io/` (Engine.IO v4). Authentication is via `40{"token":"<jwt>"}` connect packet. **Confirmed: it's a client→server command channel only** — the server doesn't push device state changes. Don't use it as a state source. The OEM app probably uses it for low-latency commands in addition to REST, but functionally REST suffices.
