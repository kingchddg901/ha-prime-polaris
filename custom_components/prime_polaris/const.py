"""
/* ============================================================
 * const.py — Prime Polaris Integration Constants
 * ============================================================
 *
 * Central registry for all constant values used across the
 * integration. Keeping these here avoids magic strings and
 * makes it easy to update API endpoints if PrimePolar changes
 * their backend.
 *
 * API discovered via APK decompilation of GrillirG Control
 * v1.1.3 (com.primepolaris.grillirgcontrol). The backend at
 * api.prime-polaris.com is a white-label platform that powers
 * multiple generic pellet grill controller brands.
 *
 * Architecture:
 *   - REST polling every POLL_INTERVAL seconds (default 30)
 *   - JWT auth with ~180 day expiry
 *   - Email OTP login flow (no password stored)
 * ============================================================
 */
"""

DOMAIN = "prime_polaris"
MANUFACTURER = "PrimePolarIS"
NAME = "Pellet Grill"

# === API =====================================================

API_BASE = "https://api.prime-polaris.com/api"

# Auth endpoints
ENDPOINT_SEND_OTP = "/email/m2s/send/verify/code"
ENDPOINT_LOGIN = "/auth/m2s/email/login"
ENDPOINT_LOGOUT = "/auth/logout"

# Device management endpoints
ENDPOINT_DEVICE_LIST = "/dms/queryDeviceListByUserId"
ENDPOINT_DEVICE_REALTIME = "/dms/queryDeviceRealTimeData"
ENDPOINT_DEVICE_STATUS = "/dms/queryDeviceStatus"
ENDPOINT_DEVICE_SPEC = "/dms/queryDeviceSpec"
ENDPOINT_DEVICE_HEARTBEAT = "/dms/queryDeviceHeartbeat"

# Command endpoints
ENDPOINT_SEND_COMMAND = "/dms/deviceFunctionSettings"
ENDPOINT_SEND_RECOVERY = "/dms/sendRecoveryCommand"

# Program/recipe endpoints
ENDPOINT_PROGRAM_LIST = "/dms/queryDeviceProgramList"
ENDPOINT_UPDATE_PROGRAM = "/dms/updateDeviceDetailsProgram"

# Timer endpoints
ENDPOINT_SET_COUNTDOWN = "/dms/setAppCountdown"
ENDPOINT_CANCEL_COUNTDOWN = "/dms/cancelAppCountdown"
ENDPOINT_PAUSE_COUNTDOWN = "/dms/pauseAppCountdown"
ENDPOINT_SET_COUNTUP = "/dms/setAppCountup"
ENDPOINT_CANCEL_COUNTUP = "/dms/cancelAppCountup"
ENDPOINT_PAUSE_COUNTUP = "/dms/pauseAppCountup"

# === Auth ====================================================

# Used in OTP request payload — identifies login vs registration
EMAIL_TYPE_LOGIN = "Login"

# Publishable API key embedded in the app
PUBLISHABLE_API_KEY = "grillirg"

# JWT is valid for ~180 days; we treat it as expired if within
# this many seconds of expiry to avoid mid-session failures
TOKEN_EXPIRY_BUFFER_SECONDS = 3600  # 1 hour

# === Polling =================================================

POLL_INTERVAL = 30  # seconds

# How many consecutive failed polls before entities are flipped to
# unavailable. The cloud sometimes returns 5xx or times out for a
# minute or two without anything actually being broken — being too
# strict here makes the dashboard flicker constantly.
POLL_FAILURE_TOLERANCE = 3

# === Config entry keys =======================================

CONF_EMAIL = "email"
CONF_TOKEN = "token"
CONF_TOKEN_EXPIRY = "token_expiry"
CONF_USER_ID = "user_id"
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_NAME = "device_name"
CONF_FIRMWARE_VERSION = "firmware_version"

# === Device state field names ================================
# These match the keys returned by queryDeviceRealTimeData.
# Documented here so entity files can reference constants
# rather than raw strings.

FIELD_DEVICE_SWITCH = "deviceSwitch"
FIELD_RUNNING_STATUS = "runningStatus"
FIELD_TEMP_SCALE = "tempScale"
FIELD_SMOKE_MODE = "smokeMode"
FIELD_SMOKE_LEVEL = "smokeLevel"
FIELD_WINTER_MODE = "winter"
FIELD_FURNACE_TEMP_SETTING = "furnaceTempSetting"
FIELD_FURNACE_TEMP_MEASURED = "furnaceTempMeasured"
FIELD_TEMP_UNIT = "tempUnit"
FIELD_ALARM_SWITCH = "alarmSwitch"
FIELD_ALARM_EVENT = "alarmEvent"
FIELD_PROBE1_SETTING = "probeP1Setting"
FIELD_PROBE1_STATUS = "probeP1Status"
FIELD_PROBE1_MEASURED = "probeP1Measured"
FIELD_PROBE2_SETTING = "probeP2Setting"
FIELD_PROBE2_STATUS = "probeP2Status"
FIELD_PROBE2_MEASURED = "probeP2Measured"
FIELD_FORWARD_TIMING_STATUS = "forwardTimingStatus"
FIELD_FORWARD_TIMER_VALUE = "forwardTimerValue"
FIELD_COUNTDOWN_STATUS = "countdownStatus"
FIELD_COUNTDOWN_SET_VALUE = "countdownSetTimerValue"
FIELD_COUNTDOWN_VALUE = "countdownTimerValue"

# === Running status values ====================================
# Observed: 3 = off/idle. Others inferred from APK event names.

RUNNING_STATUS_OFF = 3
RUNNING_STATUS_STARTING = 1
RUNNING_STATUS_COOKING = 2
RUNNING_STATUS_SHUTDOWN = 4
RUNNING_STATUS_ERROR = 5

RUNNING_STATUS_LABELS = {
    RUNNING_STATUS_STARTING: "Starting",
    RUNNING_STATUS_COOKING: "Cooking",
    RUNNING_STATUS_OFF: "Off",
    RUNNING_STATUS_SHUTDOWN: "Shutting Down",
    RUNNING_STATUS_ERROR: "Error",
}

# === HA event names ==========================================
# Fired on the HA event bus so automations can subscribe.
# Payload shape for EVENT_ALARM is documented best-effort —
# alarmEvent element schema has not yet been observed in the
# wild (only ignition timeouts trip it, rare in practice).

EVENT_ALARM = f"{DOMAIN}_alarm"

# === FCM (Firebase Cloud Messaging) ===========================
#
# Firebase publishable client credentials for the OEM project
# (GrillirG / Prime Polaris). These ARE intentionally embedded
# here and are NOT a leaked secret:
#
#   - They are extracted verbatim from the official Android APK
#     on Google Play, where they're already public to anyone who
#     downloads the app or inspects the package.
#   - Firebase publishable keys identify a project to Google's
#     SDK; they don't authorize anything by themselves. Per
#     Firebase docs (https://firebase.google.com/docs/projects/
#     api-keys), these can safely live in client-side source.
#   - Per-user authentication is the JWT obtained via the email-
#     OTP flow (api.py / config_flow.py); FCM token registration
#     is gated by that JWT server-side.
#
# GitHub's secret-scanner flags the AIza... prefix because it's
# the same shape as a Google Cloud Platform server-side API key,
# but Firebase publishable keys share the prefix without sharing
# the privilege. The alert can be closed as "Won't fix —
# Firebase publishable client key, not a secret."
#
# Recovered from APK resources.arsc on 2026-05-02.

FCM_PROJECT_ID = "grillirg-control"
FCM_APP_ID = "1:225981028998:android:0bdbfcb8e235501edbcf07"
FCM_API_KEY = "AIzaSyBRnBQnGn7URrtximmfUGkLbbHC5ge70JA"
FCM_SENDER_ID = "225981028998"
FCM_BUNDLE_ID = "com.primepolaris.grillirgcontrol"

# Endpoint that associates an FCM token with the user's account
ENDPOINT_REGISTER_FCM_TOKEN = "/auth/registerFcmToken"

# Options-flow keys
OPT_FCM_ENABLED = "fcm_enabled"
OPT_FCM_DEDUP_SECONDS = "fcm_dedup_seconds"
DEFAULT_FCM_DEDUP_SECONDS = 60  # suppress repeats within this window

# HA event fired for each de-duplicated FCM push received
EVENT_FCM_ALARM = f"{DOMAIN}_fcm_alarm"

# === Command names ============================================
# Socket.IO / REST command identifiers discovered in APK.

CMD_TEMPERATURE_SET = "TemperatureSet"
CMD_MEAT_TEMP_SET = "MeatTemSet"
CMD_SMOKE_SET = "SmokeSet"
CMD_TIME_SET = "TimeSet"
CMD_WINTER_MODE = "WinterMode"
CMD_FAN_8 = "FAN_8"
CMD_FAN_8_DISABLE = "FAN_8_Disable"
CMD_FAN_OK = "FANOk"
CMD_FAN_DISABLE = "FANDisable"
CMD_LOW_POWER = "LowPower"

# === Temperature =============================================

# Minimum set point required before remote power-on is allowed.
# This is a safety guard to prevent igniting with no target temp.
MIN_REMOTE_POWER_ON_TEMP = 150  # °F

TEMP_MIN = 180   # °F — controller minimum cooking temp (smoke mode handles below)
TEMP_MAX = 500   # °F
TEMP_STEP = 1    # °F — A10 controller does true 1°F steady-state control

# tempUnit field values
TEMP_UNIT_FAHRENHEIT = 0
TEMP_UNIT_CELSIUS = 1

# === Smoke level =============================================

SMOKE_LEVEL_MIN = 0
SMOKE_LEVEL_MAX = 9   # controller clamps at 9 — empirically verified
SMOKE_LEVEL_STEP = 1

# === Resp codes ==============================================

RESP_CODE_SUCCESS = 10000
