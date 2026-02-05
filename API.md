# E-paper image server – API reference

Base URL: `http://<host>:8080` (default port 8080; set `EPD_LISTEN_PORT` to change).

---

## Endpoints

### `GET /`

Serves the web UI: a simple HTML page with a file upload form. Images uploaded via the form are displayed on the e-paper (same behavior as `POST /api/photos`).

**Response:** `200` — HTML.

---

### `POST /upload`

Web form upload target. Accepts `multipart/form-data` with a field named **`image`**.

- **Success:** Redirects to `/?message=...` with status `302`.
- **Error:** Redirects to `/?message=...` with status `400`.

Prefer **`POST /api/photos`** for scripts and integrations; it returns JSON.

---

### `POST /api/photos`

Upload an image to display on the e-paper panel. The image is saved, scaled to the display resolution (e.g. 1600×1200), and the display is updated in the background. Any image format supported by the server (JPEG, PNG, BMP, GIF, WebP, etc.) and any size or resolution are accepted.

**Request**

- **Method:** `POST`
- **Content-Type:** `multipart/form-data`
- **Body:** One file, with form field name **`image`** or **`file`**.

**Example (curl)**

```bash
curl -X POST -F "image=@/path/to/photo.jpg" http://<host>:8080/api/photos
```

**Success response**

- **Status:** `200 OK`
- **Content-Type:** `application/json`
- **Body:**

```json
{
  "ok": true,
  "message": "Image uploaded; display updating."
}
```

**Error response**

- **Status:** `400 Bad Request`
- **Content-Type:** `application/json`
- **Body:**

```json
{
  "ok": false,
  "error": "No file selected"
}
```

or

```json
{
  "ok": false,
  "error": "Invalid image: <details>"
}
```

**Notes**

- There is no upload size limit; the server will resize to the display resolution.
- The display update runs in the background; the response is returned as soon as the file is saved and the update is queued.

---

### `GET /health`

Liveness check. Use for monitoring or load balancers.

**Response:** `200 OK` — body: `ok` (plain text).

---

## Summary

| Method | Path           | Description                    |
|--------|----------------|--------------------------------|
| GET    | `/`            | Web UI (upload form)           |
| POST   | `/upload`      | Form upload (redirect response)|
| POST   | `/api/photos`  | Upload image (JSON response)   |
| GET    | `/health`      | Liveness check                 |
