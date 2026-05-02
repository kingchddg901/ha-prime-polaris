# Setup Walkthrough

Two paths: **single-account** (faster, your phone loses OEM pushes) and **dual-account** (recommended, both your phone and HA get pushes simultaneously). Pick one.

---

## Path A: Single-account (5 minutes)

Use this if you don't mind reopening the official app to get phone pushes back, or if you don't use phone pushes at all.

### 1. Install the integration

**Via HACS (recommended)**
1. HACS → 3-dot menu → **Custom repositories**
2. Add `https://github.com/kingchddg901/ha-prime-polaris` as type **Integration**
3. Click **Install** on the new entry
4. Restart HA

**Manual**
1. Copy `custom_components/prime_polaris/` from this repo into your HA's `<config>/custom_components/` directory
2. Restart HA

### 2. Configure

1. **Settings → Devices & Services → Add Integration → Pellet Grill**
2. Enter your account email — the same one you sign in with on the GrillirG / Pit Boss WiFi mobile app
3. Check that email for a 6-digit code, enter it
4. If the account has multiple grills, pick which one to add

After this you should see a **Pellet Grill** device with ~15 entities.

### 3. (Optional) Enable push alerts

1. **Settings → Devices & Services → Pellet Grill → Configure**
2. Toggle **Enable FCM push alerts** ON
3. Acknowledge the warning — your phone will stop receiving Prime Polaris pushes until you reopen the official app
4. Submit

To get phone pushes back: open the official app on your phone. It re-registers the phone's token, displacing HA's. To swap back: reopen HA's option flow and toggle FCM (or open the card → Setup tab → Re-authenticate, which forces a token re-register).

### 4. Add the card

The card is bundled with the integration and auto-registers as a Lovelace resource. Drop it into any view:

```yaml
type: custom:ha-prime-polaris-card
```

That's it. `entity_prefix` defaults to `grill` and auto-discovers entities.

---

## Path B: Dual-account (recommended)

Phone keeps OEM pushes forever. HA gets independent pushes via a secondary account. About 10 minutes total.

The OEM cloud is **single-token-per-account** — any FCM token registered under an account replaces whatever's there. So we use a separate account for HA. Both accounts share the device, both register their own tokens, both receive the same pushes.

### 1. Create the secondary account (in the official app)

1. **Sign out** of the official app on your phone
2. **Sign up** with a fresh email — Gmail `+alias` works (`yourname+grill@gmail.com`), Apple Hide-My-Email, anything you can receive OTP at
3. Complete OTP
4. Sign back in with your **primary** account on the phone — your phone is back to normal

### 2. Share the grill (primary → secondary)

1. In the official app on your phone, signed in as primary, find the **Share** option for the grill
2. Invite the secondary account's email
3. Switch accounts (or use a different device) to accept on the secondary side

After this, querying the secondary account's device list should show the grill with `sharedFlag: 1`.

### 3. Install the integration in HA

Same as Path A step 1 above.

### 4. Configure with the secondary account

1. **Settings → Devices & Services → Add Integration → Pellet Grill**
2. Enter the **secondary** account's email
3. Check that email for the 6-digit OTP, enter it
4. Pick the shared grill if prompted

### 5. Enable FCM push alerts

1. **Settings → Devices & Services → Pellet Grill → Configure**
2. Toggle **Enable FCM push alerts** ON
3. The warning's still shown but it doesn't apply to your phone — your phone is on the primary account, untouched
4. Submit

Now: phone (primary token) gets OEM pushes. HA (secondary token) gets identical pushes simultaneously.

### 6. Drop the card in

```yaml
type: custom:ha-prime-polaris-card
```

---

## After setup

- **Live tab** is your daily-use view: chamber arc, probe ETAs, chart, recipe tiles, controls
- **Setup tab** is where you configure default ambient/wind sensors and re-authenticate when the token expires (~180 days)

### First-time tasks worth doing

1. Setup tab → **Default sensors** → click your weather/AWN sensor chip to set ambient
2. Live tab → tap a recipe (Brisket Low & Slow, Chicken, etc.) to see how presets work
3. Live tab → flip `Cook Session` switch to test the recording → `<config>/prime_polaris/sessions.csv` should appear after the first cook ends

## Troubleshooting

See [troubleshooting.md](troubleshooting.md).
