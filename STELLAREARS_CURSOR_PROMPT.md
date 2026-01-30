# Cursor prompt for StellarEars repo: push status to e-ink client

Use this in the **StellarEars** repo so the e-ink display updates when state changes instead of being polled.

## Goal

Whenever StellarEars’ displayed state changes (mute, session_will_upload, battery, last_upload/last_http), **push** the current status to the epaper client so it can refresh the screen. No polling.

## What to implement

1. **Config**
   - Add an optional env var, e.g. `EPAPER_UPDATE_URL` (or `EPD_UPDATE_URL`). Example: `http://host.docker.internal:9090/update` when StellarEars runs in Docker and the epaper service runs on the host; or `http://<pi-ip>:9090/update` when epaper runs on a Pi on the LAN.
   - If `EPAPER_UPDATE_URL` is unset or empty, do nothing (epaper push is optional).

2. **When to push**
   - Whenever the **status** that would be returned by your existing `GET /status` (or equivalent) **changes** — i.e. whenever you would update that status object (muted, session_will_upload, battery_percent, last_upload, last_http, etc.). Call the push immediately after updating that state, once per logical change (no need to throttle; the epaper client only redraws when the derived display state actually changes).

3. **How to push**
   - HTTP **POST** to `EPAPER_UPDATE_URL`.
   - **Body**: the same JSON object you expose at `GET /status` (Content-Type: `application/json`).
   - Fire-and-forget: do not block the main flow on this. Use a background task, goroutine, or fire-and-forget request (e.g. don’t wait for response for success; optional: log errors).
   - Timeout: short (e.g. 2–5 seconds). If the request fails (host down, network error), log and continue; no retries required.

4. **No polling**
   - The epaper client no longer polls `GET /status`. It only updates when it receives this POST. So StellarEars must call the push on every relevant state change.

## Summary

- **StellarEars**: on every status change → POST current status JSON to `EPAPER_UPDATE_URL` (if set).
- **Epaper client**: listens on `POST /update`, receives that JSON, updates the e-ink display only when the derived state (mute/session, battery, connection) changes.

Use this prompt in the StellarEars repo to add the push-to-epaper behavior.
