# Field guide: evidence

Research done 2026-11-08 against the live recorder at `192.168.0.115` and against the saved copy of
the recorder's own web UI in the session scratchpad (`rsui/`, `webui/`).

This file is the working out behind `FIELD-GUIDE-PLAN.md`. It is long on purpose.

---

## 1. How big the job is

Counted by walking every screen's `fields` tree through `GET /api/settings/<key>`:

```
distinct leaf names: 309
  of those, numbers: 165
  by kind: text 55, int 165, bool 65, hex 26, empty 5, choice 3
```

The same leaf name turns up on many screens with different meanings:

| Leaf | Screens | Meaning changes? |
|---|---|---|
| `Enable` | 23 | Yes. Movement on, FTP on, person detection on. |
| `Port` | 10 | Yes. FTP 21, SMTP 25 or 587, RTSP 554, NTP 123. |
| `Level` | 6 | Yes. Movement sensitivity 1-6 vs `PEARule.Level` 0-2. |
| `AlarmOutLatch`, `EventLatch`, `RecordLatch` | 8 each | No. Same meaning on every alert screen. |

**So a guide keyed on the leaf name alone is wrong.** Lookup order must be
`"<Config>/<path>"`, then `"<Config>/<leaf>"`, then `"<leaf>"`.

---

## 2. Where a real limit can come from

Three sources were checked. Only two gave anything.

### 2.1 The recorder's own ability reply. Works, for the encoder only.

`NetUse.DigitalAbility`, read per camera. Live values on 2026-11-08, identical on both cameras:

```
videoFormat 0            -> PAL, so frames a second runs 1 to 25
nCapture 1
IFrameRange              -> main_min 1, main_max 64, sub_min 1, sub_max 64
ability.Compression      -> 0x00000180
ability.MaxBitrate       -> 49152
ability.MaxEncodePower   -> 0
ability.MaxEncodePowerPerChannel -> ["0x00000000"]
ability.ImageSizePerChannel      -> ["0x00564000"]
ability.ExImageSizePerChannelEx[0][22] -> "0x0000084B"
```

Decoded against `res_type` and `Compression` from the maker's `rsui/plugin.js`:

- `Compression 0x180` = bits 7 and 8 = **H.264 and H.265**, and nothing else. Two options, not ten.
- `ImageSizePerChannel 0x00564000` = bits 14, 17, 18, 20, 22 = **1080P, 3M, 5M, 4M, 8M**.
  That is the main stream list. Camera 1 main reads 8M, which is in it.
- `ExImageSizePerChannelEx[0][22] = 0x84B` = bits 0, 1, 3, 6, 11 = **D1, HD1, CIF, QVGA, 720P**.
  That is the second stream list *when the main stream is 8M* (index 22). Camera 1 second stream reads
  720P and camera 2 reads QVGA. Both are in it.
- `MaxEncodePower` is 0, and `main_stream_set.js` only caps frames a second when it is above 0, so the
  whole DSP power calculation is skipped on this recorder.

**The second stream list depends on the main stream.** Proven at `rsui/cfg/sub_stream_set.js:281`:

```js
dwMask = encodeAbility.ExImageSizePerChannelEx[nChannelNum][ResolutionIndex(dstMainFmt.Video.Resolution)];
```

So it is a 2D table: one row per camera, one column per main stream size.

### 2.2 The maker's own tables. Work, and the live values agree with them.

`rsui/plugin.js` lines 41 to 200. Copied into `config.py` as constants:

- `res_type[32]` with `res_pw` / `res_ph` (PAL) and `res_nw` / `res_nh` (NTSC). Index 22 is 8M at
  3264 by 2448. Index 11 is 720P at 1280 by 720.
- `STREAM_CODE_VALUE[res] = [lowest, highest, usual]` kbit/s, and `H265_STREAM_CODE_VALUE` the same
  for H.265. On this firmware the two tables are identical, line for line.
- `getGainValue(bitrate)` gives the step: 8 below 32, then 16, 32, 64, 128, 256, 1024, and 2048 above
  6144. That is how the maker builds the bit rate dropdown, so the list is short, not 8000 entries.
- `Compression[10]`, the codec names.

Checked against the live values:

| Camera | Stream | Size | Table says | Live reads | Agrees |
|---|---|---|---|---|---|
| 1 | main | 8M (22) | 1536 to 8192, usual 6144 | 6144 | yes |
| 1 | second | 720P (11) | 1024 to 4096, usual 2048 | 1024 | yes |
| 2 | main | 8M (22) | 1536 to 8192, usual 6144 | 6144 | yes |
| 2 | second | QVGA (6) | 8 to 1024, usual 1024 | 128 | yes |

Picture quality is 1 to 6. Proven at `main_stream_set.js`: the control is set with
`val(vfFormat.Quality - 1)` and read back with `+ 1`, over a six item list.

### 2.3 The maker's per screen HTML. Gone, and not worth chasing.

Every other screen's dropdown lists lived in HTML fragments the old web UI loaded per page. They are
not in the saved copy, and the recorder now answers 401 to `/rsui/...`, so they cannot be fetched
again. `grep -c "<option" rsui/config_c7.html` is 0.

The maker's JavaScript reads them but never states them:

```
rsui/cfg/syspm_general.js:62   $("#DSTAutoLogout").val(GeneralInfo[...].AutoLogout);
rsui/cfg/syspm_general.js:87   GeneralInfo[...].AutoLogout = $("#DSTAutoLogout").val() * 1;
```

No range, no validation, nothing. Same story on the other screens.

Only five `getability` names are used anywhere in the maker's UI: `DDNSService`, `EncodeCapability`,
`MotionArea`, `MultiLanguage`, `VGAresolution`. `EncodeCapability` is the analogue camera version of
`NetUse.DigitalAbility` and does not apply here, because this recorder has no analogue sockets.

---

## 3. What this forces: two tiers

**Tier 1, proven.** The limit comes from the recorder or from a maker table that the live values
agree with. The control enforces it: a dropdown, or a number box with `min`, `max` and `step`.

**Tier 2, everything else.** The help sentence may say "usually 1 to 10", but the box stays a free
number box and nothing is clamped.

This split is not caution for its own sake. This recorder answers `Ret 100` to writes it then
ignores (see `CLAUDE.md`, the `ChannelTitle` case). A value silently clamped to a wrong guess is
worse than a value the recorder refuses, because the refusal is visible and the clamp is not.

---

## 4. Which screens get full help

Billy said "where appropriate". The split:

**Full help, every field.** Video quality, recording and schedule, still pictures, general, date and
time, network, ports and streaming, email, disk, movement, people and vehicles, sound, area
intrusion, line crossing, objects left or taken, recorder's own screen.

**One screen level note, no per field popups.** "What the cameras allow" and "What this recorder
supports". Between them they hold about 40 `AnalogCap*` and `DigitalCap*` flags that are read only
and say the same thing in forty ways: whether the recorder can do that picture size. Forty popups
saying "whether this recorder can do 3M" is noise, so the screen gets one note instead.

**Left plain.** Wi-Fi, FTP upload, cloud storage, dynamic DNS, allowed and blocked addresses, setup
wizard, camera movement, automatic firmware update, Swann's own settings. These are either off, not
used on this recorder, or already named plainly by the recorder itself.

---

## 5. The info icon

A `<details>` with the icon as its `<summary>` and the panel positioned under it.

Why not a tooltip or a dialog:

- A hover tooltip does not exist on a phone, and this app is used on a phone.
- A real dialog needs JavaScript and can block the page. The project already avoids browser dialogs.
- `<details>` is keyboard reachable and screen reader reachable with no extra work, and the settings
  menu already uses the same pattern, so there is one idea to learn, not two.

---

## 6. The one live write planned

Everything above is read only. The only write is to prove a dropdown still saves:

```
NetUse.DigitalEncode, camera 1, MainFormat/Video/GOP:  15 -> 16, read back, -> 15, read back
```

Keyframe gap is harmless: it changes how often a full frame is written, not whether video is saved.

**Not tested by writing:** frames a second, picture size and bit rate. Pushing a camera to 25 frames
a second or changing its picture size changes what is recorded while it is recorded. The limits for
those come from the recorder's own ability reply, which is already proof enough.

---

## 7. What is being changed

| File | Change |
|---|---|
| `swann/config.py` | `FIELD_RANGES`, bigger `FIELD_NOTES` and `FIELD_CHOICES`, the maker's resolution and bit rate tables, and `field_guide()` to look one up |
| `swann/fields.py` | `describe()` takes the config name and attaches help, unit, lowest, highest, step and choices |
| `swann/settings.py` | passes the config name into `describe()` |
| `web/js/settings.js` | the info icon, and picking the control from the guide |
| `web/js/visual.js` | a video quality editor driven by the camera's own limits |
| `web/css/app.css` | the icon, its panel, and the range line |

---

## 8. What was actually built, 2026-11-08

### 8.1 Claims that did not survive checking

Section 2 above said the maker's per screen HTML was gone. Before shipping, every limit marked
"from Swann's page" was grepped for in the saved copy. Nine did not hold up and were demoted to
help text with no limit on the control:

| Claim | What the grep found |
|---|---|
| `Detect.MotionDetect.Level` 1 to 6 | `alarm_mv.js:103` reads a `<select>` whose options are in HTML we do not have. No range anywhere. |
| `Quality` max 6 | `main_stream_set.js:330,558` prove `Quality = list position + 1`, so 1 is the floor. The ceiling is in the missing HTML. |
| `TransferPlan`, `MonMode`, `DateSeparator`, `VideoOutPut` | No hit at all in `rsui/`. |
| `VideoFormat` PAL/NTSC | Only `videoFormat` the number. The two names were a guess. |
| `BandWidthTips` 0/1 | No hit. |
| `OverWrite` / `StopRecord` | The only `OverWrite` list in `rsui/` is `SwannClo_Sto.js:4`, which is the cloud one and holds `["OFF","Auto","1Day",...]`. Different setting. |
| `TypeHuman`, `TypeVehicle` | No hit. |
| Logo `FgTrans`/`BgTrans` 0 to 255 | No hit. |

Two claims were corrected rather than dropped:

- **`fVideo.GUISet.WindowAlpha` is 128 to 255.** `chn_display.js:10` sets the slider to
  `minValue: 0, maxValue: 127`, and `:64` and `:75` convert with `255 - WindowAlpha`. Live value 255.
- **`General.AutoMaintain.AutoRebootHour` is minutes, not hours.** `auto_wh.js:34` clamps it to
  `30` up to `1469` and `:37` does `nMinutes = AutoRebootHour - 30`. But the live value is `0`, which
  is outside that, and the recorder still restarts at midnight. So Swann's page enforces it and the
  recorder does not. No limit was set.

Still proven, and enforced: `AutoRebootDay` (`auto_wh.js:3,10,15`), `DateFormat` (`syspm_dst.js:11`),
`TimeFormat` (`:63`), `DSTRule` (`:239`), `BitRateControl`, `RecordMode`, and the encoder tables in
section 2.

### 8.2 The keyframe gap rule, found by writing

`IFrameRange` says `main_min 1, main_max 64`. That is true and not the whole story. Written live on
camera 1's main stream, frames a second 15, each read back straight after:

```
GOP 15 -> 16   Ret 100, read back 15.  IGNORED
GOP 15 -> 30   Ret 100, read back 30.  LANDED
GOP 30 -> 20   Ret 100, read back 30.  IGNORED
GOP 30 -> 45   Ret 100, read back 45.  LANDED
GOP 45 -> 64   Ret 100, read back 45.  IGNORED
GOP 45 -> 15   Ret 100, read back 15.  LANDED (restored)
```

**The keyframe gap must be a multiple of the frames a second.** With 15 that is 15, 30, 45, 60. The
page now builds that list itself and moves the gap to the nearest allowed one when the frames a
second changes. `ENCODE_GOP_STEPS_BY_FPS` in `config.py`.

This is also the only place `Ret 100 does not prove a change landed` was caught by the read back
during this work, which is why that rule exists.

### 8.3 The other live writes, all restored

```
Camera 2, second stream, Quality 4 -> 5   saved and read back 5
Camera 2, second stream, Quality 5 -> 4   saved and read back 4 (restored)
```

Final state checked on both cameras: picture size 8M, bit rate 6144, frames a second 15, keyframe
gap 15, second stream quality 4. Identical to before this work.

### 8.4 Coverage

623 of 880 distinct (config, leaf) pairs on the screens Billy uses now carry a help sentence. The
257 without one are: list entries labelled by a bare number, the 40 `AnalogCap*` and `DigitalCap*`
flags (which got one screen note each instead), and the screens deliberately left plain.

### 8.5 Checks run

- **Reading level** over all 391 help sentences: Flesch reading ease 85.2, grade 3.2, average
  sentence 7.4 words. The ceiling is ease 60 and grade 7 to 8.
- **AI tells**: no em dashes, no curly quotes, no emoji, no banned vocabulary.
- **Phone width**, measured in a same origin iframe at 390px with every info panel open, on 15
  screens including the two biggest (movement, 150 panels; people and vehicles, 150 panels):
  `scrollWidth == clientWidth == 375` on every one. No sideways scroll.
- **The dependency chain**, in the browser: main picture size 8M to 1080P rebuilt the bit rate list
  from 1536-8192 to 1024-4096 and moved 6144 to 4096. Frames a second 15 to 10 rebuilt the keyframe
  gap list to 10/20/30/40/50/60 and moved 15 to 10. Both rows kept their "waiting to save" mark.
