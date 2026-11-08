# Better Swann UI build plan: evidence

Technical design for `BUILD-PLAN.md`. Written 2026-11-07. No code exists yet.
What the recorder can actually do is in `PLAN-evidence.md`. Do not repeat those findings here; reference them.

---

## 1. Stack

| Part | Choice | Why |
| --- | --- | --- |
| Back end | Python 3.12 + FastAPI | Every probe written so far is Python. `python-dvr` (the DVRIP reference) is Python. Async suits long-lived recorder sessions and an SMTP sink in one process. |
| Video relay | go2rtc | RTSP in, WebRTC or MSE out. Handles HEVC, which Safari plays natively and Chrome on Apple silicon plays with hardware decode. Falls back to transcode via ffmpeg. Single static binary, YAML config. |
| Front end | Plain HTML, CSS and vanilla JS, served by FastAPI | Two cameras. A framework earns nothing here. No build step, no node_modules. |
| Store | SQLite via `aiosqlite` | Events, clip index, config backups, alert images. Single file, no server. |
| Mail sink | `aiosmtpd` | Receives the recorder's alert emails in-process. |
| Media tool | ffmpeg / ffprobe (already installed at `/opt/homebrew/bin`) | Snapshots, clip export, probing, fallback recording. |
| Process manager | `honcho` or a plain `Makefile` | Two processes: FastAPI and go2rtc. |

If the owner prefers PHP/Laravel, the whole design still holds. Swap FastAPI for Laravel and `aiosmtpd` for a separate small Python sink, because PHP has no good async SMTP server. The DVRIP client would need porting, which is the real cost of switching.

### Rejected

- **ONVIF libraries.** The recorder is an ONVIF client, not a server. See `PLAN-evidence.md`.
- **MediaMTX instead of go2rtc.** MediaMTX is a better server, go2rtc is a better browser bridge. We need the bridge.
- **HLS only.** Latency of 6 to 20 seconds is wrong for live security view. WebRTC gives sub-second.
- **Writing our own RTSP-to-browser bridge.** go2rtc already solves HEVC in the browser, which is the hard part.

---

## 2. Folder layout

```
./
  .env                      host, ports, user, password (already exists, git-ignored)
  .gitignore                .env, go2rtc.yaml, snapshots/, data/, media/, *.db
  Makefile                  dev, run, stop
  pyproject.toml
  go2rtc.yaml               generated from .env, never hand-edited
  swann/
    __init__.py
    config.py               loads .env, holds EVERY constant. No literals elsewhere.
    cgi.py                  CGI client, port 85
    dvrip.py                DVRIP client, port 9000
    session.py              one shared recorder session + keepalive loop
    rtsp.py                 URL building, ffmpeg snapshot, clip export
    recordings.py           clip search and download, whichever route step 1 proves
    alerts.py               SMTP sink, email parsing, snapshot extraction
    db.py                   SQLite schema and queries
    models.py               dataclasses: Device, Channel, Storage, Clip, Alert
  app/
    main.py                 FastAPI app and routes
    deps.py                 shared session dependency
  web/
    index.html              live view
    playback.html
    alerts.html
    health.html
    settings.html
    css/, js/
  data/                     swann.db, config backups
  media/                    exported clips, alert images
  snapshots/                already exists, holds the recon stills
  scripts/
    spike_recordings.py     step 1
    spike_substream.py      step 2
```

the owner's rule: never hardcode values if constants or config exist. Every port, path, timeout, channel default and URL template lives in `swann/config.py`. Nothing else holds a literal.

---

## 3. The recorder client

### 3.1 Session management (`swann/session.py`)

This is the piece most likely to be got wrong, so it is specified fully.

- **One session for the whole app.** Not one per request. The recorder's CGI login is per-user and a second login may evict the first. See `PLAN-evidence.md` under "Sessions and users".
- Login: `GetSalt`, then `Login` with `Sign = MD5_8(Salt + MD5_8(password))`. The `md5_8` function is in `PLAN-evidence.md`.
- `AliveInterval` is 21 seconds and is the server's timeout, not the send rate. A background task sends `KeepAlive` every **10 seconds**, matching the recorder's own web viewer.
- Every call after login carries `"Salt": <salt>` in the body plus the session cookie.
- On `Ret 105` (session lost), the task re-logs in once and retries the failed call once. Two failures in a row surface as an error to the UI.
- The session object is a FastAPI dependency and is created on startup, closed on shutdown with `Logout`.
- A single `asyncio.Lock` serialises calls. The recorder's own viewer aborts any in-flight request before sending a new one (`gCgi.run` guard in `plugin.js`), which says it handles one at a time.

### 3.2 CGI client (`swann/cgi.py`)

`POST http://<host>:85/cgi-bin/<verb>.cgi`, JSON body, JSON reply.

Verbs, from `js/plugin.js` `CgiClass`:

| Verb | Use here |
| --- | --- |
| `login` | `GetSalt`, `Login`, `KeepAlive`, `Logout` |
| `getinfo` | `SystemInfo`, `StorageInfo`, `WorkState`, `WifiStatus` |
| `getability` | `SystemFunction`, `Intelligent` |
| `getchannelability` | `ChannelSystemFunction` |
| `getconfig` | all config reads, per-channel with the `.[N]` suffix |
| `setconfig` | all config writes, phase 5 only |
| `opdev` | `OPMachine` (reboot), `OPTimeQuery`, `OPLocalSearch` |
| `opcontrol` | PTZ and similar, not used yet |
| `getlog` | device log for the health page |
| `usermanager` | create the tool's own user, step 10 |

Return codes to handle: `100` ok, `101` unknown name, `105` session lost, `136` not supported, `607` config name not found. Treat anything else as an error and log the raw reply.

`DataUseAES` is `false` on this recorder, so bodies are plain JSON. The client must still read that flag at login and refuse to send `setconfig` if it ever turns true, rather than sending plaintext that gets rejected or misread.

### 3.3 DVRIP client (`swann/dvrip.py`)

Port 9000. Binary header then JSON. Header and login are proven; see `PLAN-evidence.md`.

Needed for step 1 only, unless the CGI route wins. Keep it behind the same interface as the CGI route so `recordings.py` does not care which one answers.

---

## 4. Step 1: list old recordings

Three routes, cheapest first. Stop at the first that returns real file records.

**Route A: CGI `opdev` with `OPLocalSearch`.**
Seen in `main.js` line 1026 with a 10 second timeout, alongside `OPTimeQuery`. Also `getconfig NetLocalSearch.[N]` at line 1061. The recorder reports `SupportNetLocalSearch` as true. This route reuses the session we already hold and the verb is visible in the viewer's own code, so it is both the cheapest and the best evidenced. Call `OPTimeQuery` first and use the exact time string the recorder hands back.

**Route B: DVRIP `OPFileQuery` done properly.**
Three attempts already returned `Ret 117` with no files, which is the owner's stop-and-change-approach line. So this route does not get retried blind. Precondition: read `python-dvr` (OpenIPC, `DVRIPCam.list_local_files`) and diff its request against ours before sending anything. Specific things to check:
- Whether `Channel` is 0-based or 1-based. We sent `0`.
- Whether the time strings want `"2026-11-07 00:00:00"` or another shape.
- Whether `OPTimeQuery` must run first to sync the device clock view.
- Whether `Ret 117` means "no files matched" rather than "bad request", in which case the time range or channel is wrong rather than the layout. Our `recv` already loops to the declared body length, so truncation is unlikely.

**Route C: `/API10/getRecordList`.**
Blocked on the custom `Authorization` value. Needs a capture of the Swann app's own traffic. Method: iPhone on USB, `rvictl -s <UDID>`, then `tcpdump -i rvi0 -s0 -w swann.pcap host 192.168.1.100` while the app plays an old clip on home Wi-Fi. Only works if the app reaches the recorder on the LAN rather than through the ThroughTek relay. This is a last resort because it needs the owner's phone and time.

**Fallback if all three fail.**
Record from RTSP on the Mac with ffmpeg segments. Measure the real bitrate first with `ffprobe` over 60 seconds. At 4K HEVC, expect 4 to 8 Mbit/s per camera, which is 40 to 80 GB per camera per day. That is almost certainly too much, so the fallback would record the sub stream, which makes step 3 a hard dependency rather than an optimisation.

Download, once listing works: DVRIP uses `OPPlayBack` with `Action: Download`. The CGI route's download verb is unknown and is part of what route B must prove.

---

## 5. Step 3: the smaller video stream

`/chNN/0` and `/chNN/1` both return 3840x2160. Three possible reasons, in likelihood order:

1. The sub stream exists but is configured at 4K. Fix by reading and then setting the encoder config.
2. The path suffix is ignored and both map to the main stream. Then the real sub-stream path is different.
3. The recorder has no sub stream for these channels. `ChannelSystemFunction` does not say, but `SystemFunction.EncodeFunction.DoubleStream` is **true**, which argues against this.

Because `DoubleStream` is true, reason 1 or 2 is almost certain. Find the encoder config name first. Candidates already returning `607`: `Simplify.Encode`, `AVEnc.ExtraFormat`, `Encode`. Still untried: `AVEnc.Encode`, `Simplify.Encode.[0]`, `EncodeCapability`, `Camera.Param`, `Camera.ParamEx`. Also pull the viewer's lazily-loaded config pages (`html/config_c7.html` references them) and grep for the names it actually sends.

If the sub stream turns out to be 4K and we change it, that is a **write** to the recorder and needs the owner's yes, because it also changes what the Swann app sees.

If no sub stream can be had, go2rtc transcodes to 720p with ffmpeg. That costs CPU on the Mac, roughly one core per camera, and is acceptable for two cameras.

---

## 6. Steps 4 and 5: client plus health page

Build the health page (step 5) first because it exercises the whole chain with zero risk: login, keepalive, three different read verbs, dataclass mapping, the DB, the API layer and the front end. If health works, everything after it is new surface, not new plumbing.

Health page shows, all from reads already proven:

| Panel | Source |
| --- | --- |
| Recorder model, firmware, build date, uptime | `getinfo SystemInfo` |
| Disk model, size, free space, oldest and newest footage | `getinfo StorageInfo` |
| Cameras online, alarm state per channel | `getinfo WorkState` |
| Channel count and names | login `ChannelNum`, then `getconfig` channel titles |
| Features switched on | `getability SystemFunction` |
| Recent device log | `getlog` |

`ChannelNum` comes from the login reply. Never hardcode 2 or 8.

---

## 7. Steps 8 and 9: live view

`go2rtc.yaml` is generated from `.env` at startup so the password never sits in a tracked file:

```yaml
streams:
  ch01:
    - rtsp://USER:PASS@HOST:554/ch01/0
  ch01_sub:
    - rtsp://USER:PASS@HOST:554/ch01/1
```

The front end embeds go2rtc's WebRTC player per camera. Grid uses the sub stream; full screen switches that one camera to the main stream.

Features: grid, click to full screen, snapshot to `media/`, mute toggle. Audio is `pcm_alaw`, which go2rtc transcodes to Opus for WebRTC.

Two-way talk is possible later. Both cameras report `SupportIPCTalk`. It is not in this build plan because it needs the audio path back into the recorder, which is unproven.

---

## 8. Steps 11 and 12: alerts

The recorder can send email on motion and person detection, and attach snapshots. `NetWork.NetEmail` exists, is off and has no server set. `SupportMailTest` and `SupportAbnormitySendMail` are both true.

Design:
1. `aiosmtpd` listens on the Mac, port 2525, on the LAN address only.
2. `setconfig NetWork.NetEmail` points the recorder at it: no TLS, no auth, port 2525. **This is a write and needs the owner's yes.**
3. Each arriving mail is parsed for channel, event type and time, snapshots are saved to `media/alerts/`, and a row goes into SQLite.
4. The alerts page lists them newest first with the image, filterable by camera and type.

Test the path with `opdev` mail test before relying on it, since `SupportMailTest` is true.

Why not polling `getinfo WorkState`: it works, but it only shows current state, so a short event between polls is missed, and it carries no snapshot.

`NetWork.NetFTP` is a second route that can push actual clips rather than stills. Keep it in reserve for after step 1 is settled, because if recordings can be listed and pulled directly, FTP adds nothing.

---

## 9. Steps 6, 7 and 13: own login, backup, settings

Order matters and is not negotiable:

1. Create the tool's own recorder user with `usermanager`. Read the user list first. Never touch the admin account. Give it the rights it needs and no more.
2. Back up every readable config name to a timestamped JSON file in `data/backups/`. The list of names that return `100` is in `PLAN-evidence.md`.
3. Only then build any screen that writes.
4. Every write screen reads the current value, shows it, writes on save, reads it back and shows what the recorder actually stored. The recorder is the source of truth, not the form.
5. `SupportRestoreConfigV2` is true, so a whole-device export probably exists. Find it before the first write.

Which screens get built depends on the owner's answer to question 11 in `swannapp/help.md`. Do not build all of them.

---

## 10. Database

```sql
CREATE TABLE alerts (
  id INTEGER PRIMARY KEY,
  received_at TEXT NOT NULL,     -- ISO 8601, Mac clock
  device_time TEXT,              -- as the recorder reported it
  channel INTEGER NOT NULL,
  event_type TEXT NOT NULL,      -- motion, human, line_cross, ...
  image_path TEXT,
  raw_subject TEXT,
  read INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE clips (
  id INTEGER PRIMARY KEY,
  channel INTEGER NOT NULL,
  begin_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  size_bytes INTEGER,
  device_ref TEXT,               -- clipID or filename, route dependent
  local_path TEXT                -- set once downloaded
);

CREATE TABLE config_backups (
  id INTEGER PRIMARY KEY,
  taken_at TEXT NOT NULL,
  name TEXT NOT NULL,
  payload TEXT NOT NULL
);
```

Times from the recorder are stored exactly as the recorder gives them, in a separate column from the Mac's own clock. The recorder's timezone handling is unverified and mixing the two would corrupt the clip index.

---

## 11. API routes

```
GET  /api/health                 device, storage, channels, features
GET  /api/channels               id, name, online, abilities
GET  /api/clips?ch=&from=&to=    clip search
POST /api/clips/{ref}/download   pull a clip to media/
GET  /api/alerts?ch=&type=       alert list
GET  /api/snapshot/{ch}          live still via ffmpeg
GET  /api/config/{name}          read one config
PUT  /api/config/{name}          write one config, phase 5 only
POST /api/backup                 dump all config to data/backups/
```

Live video does not pass through FastAPI. The browser talks to go2rtc directly.

---

## 12. How the owner tests each step

Per the owner's rule, testing is never a task in a list. These are the commands and checks to run when each step lands.

**Step 1 (recordings):** run `python3 -I scripts/spike_recordings.py`. It prints how many clips exist for yesterday on camera 1, with start and end times. A non-empty list is the pass.

**Step 3 (sub stream):** run `python3 -I scripts/spike_substream.py`. It prints the width and height of every stream path it can find. Anything under 4K on a second path is the pass.

**Step 5 (health):** `make dev`, then open `http://localhost:8000/health.html`. Disk free space and oldest footage date should match what the recorder's own menu shows on the TV.

**Step 9 (live view):** open `http://localhost:8000/`. Both cameras play within 3 seconds. Click one for full screen. Wave at camera 2 and check the delay is under 2 seconds.

**Step 10 (playback):** pick yesterday 20:00 on camera 2 and press play. Compare against the same time in the Swann app.

**Step 12 (alerts):** walk past camera 2. An alert with a picture appears on the alerts page within 60 seconds.

**Step 13 (settings):** change one harmless value, such as a camera name. Reload. Check the recorder's own TV menu shows the new name.

---

## 13. Open risks

| Risk | Impact | What we do |
| --- | --- | --- |
| Recordings cannot be listed by any route | Playback becomes Mac-side recording, and step 3 becomes mandatory | Three routes in step 1, measured fallback |
| No sub stream exists | CPU cost for transcode, worse on battery | Accept for two cameras; revisit if more are added |
| A second login evicts the Swann app's session | the owner's phone stops working while the tool runs | Step 6 gives the tool its own user, before any heavy use |
| A `setconfig` write breaks recording | Lost footage | Full backup before the first write, read-back after every write |
| Recorder clock drifts from the Mac | Clip index points at the wrong times | Store both clocks separately, never convert |
| Chrome cannot decode HEVC on this Mac | No live view in Chrome | go2rtc transcodes to H.264; Safari works natively either way |

---

## Correction, 2026-11-08: sections 4 and 5 are superseded

Section 4 ("Step 1: list old recordings") is wrong in three ways, and the spike that ran against the
recorder proved it. Full working in `PLAN-evidence.md` under "Step 1 spike".

1. **Route A was never a recordings route.** `OPLocalSearch` and `NetLocalSearch` search the LAN for IP
   cameras to add. The recorder's own `html/cfg/IPCan_set.js` calls both from a function named
   `SearchDevice`, with `{"SearchProtocol": "ONVIF"}`. Section 4 called Route A "the best evidenced"
   on the strength of a timeout line in `main.js` and never found the caller.
2. **Route B is closed, not untried.** `Ret 117` is "message format error", not "no files" (`python-dvr`
   `CODES`). Both reference clients' field sets were sent exactly, plus a full field matrix and a
   container matrix. Every object gives 117, including an empty one. An unknown message code gives 102,
   so 1440 is supported; a body with no `OPFileQuery` object gives 119, so the request is being parsed.
3. **The fallback was the wrong fallback.** `OPPlayBack` with `PlayMode: "ByTime"` needs no file list.
   Its claim is accepted with Ret 100 on both channels, but `DownloadStart` and `Start` both deliver
   zero bytes. So that route is closed too.

Section 5 ("Step 3: the smaller video stream") is answered in part. `getability EncodeCapability` shows
`ExtraStream2` and `JPEGStream` both enabled in hardware. But every encoder config name is refused with
Ret 607, including `AVEnc.Encode` from the recorder's own `main_stream_set.js`. So the sub stream's size
cannot be read or set over the network, only from the on-screen menu on the TV, and the RTSP path that
serves it is still unknown.

### What this changes in the build order

Nothing except playback. Live video, snapshots, health, disk state, alerts, users and settings are all
proven working over RTSP and CGI. So the build no longer waits on a spike. `BUILD-PLAN.md` now starts at
the recorder client and puts old video last, behind a choice between:

- **Route A: capture the Swann app's `Authorization` value.** iPhone on USB, `rvictl -s <UDID>`, then
  `tcpdump -i rvi0 -s0 -w swann.pcap host 192.168.1.100` while the app plays an old clip on home Wi-Fi.
  The teardown already has the URL shapes, including
  `getRecordList?startTime=<t>&recordMax=9999&streamType=0`. Only the header value is missing. Needs
  the owner's phone, and only works if the app reaches the recorder over the LAN rather than the
  ThroughTek relay.
- **Route B: record on the Mac from RTSP.** Certain to work, but it only holds video from the day it
  starts, and it needs a sub stream to be affordable. Measure the real bitrate with `ffprobe` over 60
  seconds before committing. At 4K HEVC expect 40 to 80 GB per camera per day.
