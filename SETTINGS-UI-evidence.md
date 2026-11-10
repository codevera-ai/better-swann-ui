# Settings UI: evidence

Started as an audit on 2026-11-08. Finished the same day, after all ten steps of
`SETTINGS-UI-PLAN.md` were built and tested against the live recorder at `192.168.0.115`.

Everything below is a real reply or a real round trip, not a guess. Where an earlier draft of this
file was wrong, the correction is marked **CORRECTION** and the old claim is kept so nobody repeats
it.

---

## 1. Why the generic renderer was not enough

`swann/fields.py` works out a control from the *shape* of a value: `bool` to a tick box, `int` to a
number box, a hex-looking string to a text box, a dict to a group, a list to a numbered list. There
is no type information in the recorder's reply, so the renderer cannot know that four ints in a row
mean a rectangle.

Observed on the privacy screen before the change:

```
Relative pos
  0   [ 1024 ]
  1   [ 1024 ]
  2   [ 2048 ]
  3   [ 2048 ]
```

That is the recorder's own 0 to 8192 coordinate space, which appears nowhere on the page.

Nine screens now draw instead. Every one of them keeps a "Show every setting" switch that falls
back to the old field list, so nothing the generic renderer could reach was lost.

---

## 2. Coordinates

### 2.1 The space

0 to 8192 across and 0 to 8192 down, whatever the real picture size is. `cfg.VISUAL_SPACE`.

### 2.2 Privacy covers, `AVEnc.VideoWidget[N].Covers`

```json
"Covers": [
  {"BackColor": "0x80000000", "EncodeBlend": false, "FrontColor": "0xF0FFFFFF",
   "PreviewBlend": false, "RelativePos": [1024, 1024, 2048, 2048]},
  ... x8
],
"CoversNum": 0
```

**CORRECTION.** The first draft of this file said `RelativePos` is `[x, y, w, h]`. It is not. On a
cover it is **`[left, top, right, bottom]`**.

Proof, 2026-11-08: a box was dragged on camera 1 to roughly 14% in from the left, 13% down,
44% to the right edge and 43% down the picture. Saved. Read back:

```
RelativePos [1122, 1042, 3580, 3500]
```

`1122/8192 = 13.7%`, `1042/8192 = 12.7%`, `3580/8192 = 43.7%`, `3500/8192 = 42.7%`. Those are the
two corners, not a corner plus a size. Restored afterwards to `[1024, 1024, 2048, 2048]` and
`CoversNum` back to 0.

Constants: `cfg.PRIVACY_POS_LEFT/TOP/RIGHT/BOTTOM` = 0/1/2/3.

**`EncodeBlend` is not enough on its own.** It burns the block into the recording only. The live
picture is controlled by `PreviewBlend`, which the recorder's own web UI never sets. Found on
2026-11-08 when a saved block did not appear on the live view. The tool now writes both together
(`cfg.PRIVACY_ON_KEY` and `cfg.PRIVACY_PREVIEW_KEY`) and reads "on" as either one being true.

8 cover slots exist per channel, fixed length, but `cfg.PRIVACY_COVER_LIMIT` is 4 because that is
what the recorder's own screen offers.

### 2.3 On screen text, `AVEnc.VideoWidget[N].ChannelTitleAttribute` / `.TimeTitleAttribute`

```json
"ChannelTitleAttribute": {"BackColor": "0x80000000", "EncodeBlend": true,
  "FrontColor": "0xF0FFFFFF", "PreviewBlend": true, "RelativePos": [570, 7552, 255, 24]}
```

Here `RelativePos` is `[x, y, <ignored>, <ignored>]`. It cannot be corners: `right` of 255 would be
to the left of `left` of 570. The last two numbers were 255 and 24 on every channel and never
changed through any write. Constants `cfg.OVERLAY_POS_X` and `cfg.OVERLAY_POS_Y`.

**The recorder stores these numbers and does not use them.** Proven 2026-11-08:

1. Camera 1's clock read `[5166, 512, 255, 24]`, which is 63% across and 6% down, so top right.
2. The live picture showed the clock bottom centre and the camera name top left. Neither matched.
3. The clock was dragged to about 16% across and 26% down. Saved. Read back `[1351, 2094, 255, 24]`.
4. A fresh snapshot was taken. The clock had not moved. Still bottom centre.
5. Restored to `[5166, 512, 255, 24]` on all 8 channels and read back.

These are network cameras. Each camera draws its own name and clock into the video before the
recorder ever sees it. `AVEnc.VideoWidget` is the recorder's own overlay, which this path does not
use. The screen now carries a warning saying so (`cfg.SETTINGS_SCREENS`, key `overlay`).

### 2.4 Movement grid

Two configs hold the same grid:

- `Detect.MotionDetect.Region`, per channel, a list of hex strings.
- `Custom.SwannSpecialInfo.InfoAlarm.RegionAll[channel].Region[0]`, the Swann layer.

**Grid size, proven by reading it.** Both hold **32 strings of 8 hex digits**, so the grid is
**32 rows by 32 columns**. The vendor's own JavaScript hardcodes 18, which belongs to a different
build. `web/js/visual.js` derives it from the reply every time:

```js
const digits = String(stored[0] || "").replace(/^0x/i, "").length || rules.digits;
const columns = digits * BITS_PER_DIGIT || rules.columns;
const rowCount = stored.length || rules.rows;
```

`cfg.MOTION_COLUMNS`, `cfg.MOTION_ROWS` and `cfg.MOTION_HEX_DIGITS` are fallbacks only, used when
the recorder answers with nothing.

Bit order: column `j` is bit `j`, least significant bit first. All on is `0xFFFFFFFF` per row.

**Both configs must be written, and the order matters.** Round trip on 2026-11-08: rows and columns
17 to 30 were brushed off, saved, and read back as `0x8001FFFF` on rows 17 to 30 in **both**
configs. "Watch it all" then restored both to all `0xFFFFFFFF`.

Writing the Swann config makes the recorder copy the grid into the plain one by itself. With the
Swann write first, the plain config is read back while that copy is still in flight, and the page
wrongly reports "The recorder said it saved this, but reading it back shows the old value". So
`visual.js` queues `Detect.MotionDetect` **first** and the Swann config **last**:

```js
function save() {
  const mine = live[rules.regionKey];
  if (Array.isArray(mine)) {
    queuePath(detect, join(channel, rules.regionKey), intoConfig(mine), mine);
  }
  queuePath(swann, path, intoConfig(stored), stored);
}
```

### 2.5 Area, line and objects

`Detect.Analyze_Swann_Pid` (area), `_Lcd` (line), `_Sod` (objects). One structure, three screens:

```json
"RuleConfig": {"PEARule": {
  "Level": 2,
  "PerimeterEnable": 0,
  "PerimeterRule": {"LimitPara": {
      "Boundary": {"Mode": [0,0,0,0], "PointNum": 0,
                   "Points": [{"x":0,"y":0}, ... x16], "Valid": [1,1,1,1]},
      "DirectionLimit": 0, "ForbiddenDirection": 0, "MinDist": 0, "MinTime": 0},
    "Mode": 0, "TypeHuman": 0, "TypeLimit": 0, "TypeVehicle": 0},
  "ShowRule": 0, "ShowTrack": 0,
  "TripWireEnable": 0,
  "TripWireRule": {"Limit": {"MinDist": 0, "MinTime": 0},
    "TripWire": [{"ForbiddenDir": 0, "IsDoubleDir": 0, "Valid": 1}, ... x8],
    "TypeHuman": 0, "TypeLimit": 0, "TypeVehicle": 0}}}
```

**CORRECTION.** The first draft read `Boundary.Points` as one polygon with up to 16 points. It is
not. `Mode` and `Valid` both have **4** entries, one per rule, and `getability Intelligent` answers
`AreaNum: 4`. So it is **4 rules of 4 points each**, filling the 16 slots in order. Rule *r* owns
points `r*4` to `r*4+3`. Constants `cfg.SHAPE_RULE_COUNT = 4` and `cfg.SHAPE_POINTS_PER_RULE = 4`.

`getability Intelligent` also answers `AreaMaxLineNum: 16`, which is the total point budget, not the
points in one area.

**Line coordinates do exist.** The read above shows a `TripWire` entry with no points, because no
line has ever been drawn on this recorder. Written on 2026-11-08 to
`Detect.Analyze_Swann_Lcd` channel 0:

```
RuleConfig/PEARule/TripWireRule/TripWire/0/Line/StartPt  {"x": 1600, "y": 4096}
RuleConfig/PEARule/TripWireRule/TripWire/0/Line/EndPt    {"x": 6600, "y": 4096}
```

The recorder stored it and read it back unchanged. Restored to zeros afterwards. Constants
`cfg.LINE_PATH`, `cfg.LINE_KEY`, `cfg.LINE_START_KEY`, `cfg.LINE_END_KEY`, `cfg.LINE_COUNT = 4`.

`TypeHuman` and `TypeVehicle` are the person and vehicle filters, and `ForbiddenDir` /
`IsDoubleDir` set the direction. These are shown beside the drawing, not buried
(`cfg.DIRECTION_CHOICES`).

**CORRECTION.** The first draft said `Detect.Analyze` is a smart alert schedule screen that returns
the wrong structure. It is not a schedule at all. It returns the same `PEARule` structure as the
three above. Nothing in it is a week. It was left as a plain form.

---

## 3. Weeks

### 3.1 Shape

`ScheduleSheet` is a list of rows; each row is 7 strings, one per day; each string is 48 characters,
one per half hour. `"1"` is on, `"0"` is off. Constants `cfg.WEEK_SLOTS_PER_DAY = 48`,
`cfg.WEEK_SLOT_MINUTES = 30`, `cfg.WEEK_ON`, `cfg.WEEK_OFF`.

| Config | Rows | Screen |
|---|---|---|
| `Record.ScheduleSheet` | 6 | Recording and schedule |
| `ExtRecord.ScheduleSheet` | 6 | Recording and schedule |
| `Custom.SwannSNAP.ScheduleSheet` | 3 | Still pictures |

### 3.2 Day 0 is Sunday, slot 0 is midnight

Proven 2026-11-08. 8 November 2026 is a Sunday. Row 0, day 0, slot 39 was set for channel 0 at
19:52 local. 19:52 falls in slot 39 (`39 * 30 min = 19:30`). Within seconds the health page showed
camera 1 `recording: true` and camera 2 `recording: false`. Clearing it stopped the recording.

`cfg.WEEK_DAYS = ("Sunday", "Monday", ... "Saturday")`.

### 3.3 What the rows mean

The same write proves **row 0 is "record all the time"**: with only row 0 painted, camera 1
recorded with nothing moving in front of it.

Row 2 is movement. The vendor's own code builds the flag as `0x01 << 2` for the movement trigger,
and on this recorder rows 2 and 4 are the rows that arrive all `1` from the factory, which matches a
recorder that is set to record on movement and on smart events.

Row 4 is people and vehicles. This one is **inference, not proof**. It was not fired at the live
recorder, because doing so needs someone to walk in front of a camera at a known time.

Rows 1, 3 and 5 are unknown. They are **not shown** and are carried through every write untouched,
so nothing can change them by accident. `cfg.RECORD_SHEET_ROWS` lists only rows 0, 2 and 4;
`cfg.STILLS_SHEET_ROWS` lists only rows 0 and 2.

### 3.4 Not a week after all

`NetWork.NetEmailExt` has an `Interval` and a `WorkSheet`, not a 48 character sheet, so the email
screen was left as a form. `Custom.SwannSpecialInfo.InfoRecord` holds `RecordMask` and
`EncodeDefinedBit[64][2]`, which was never needed once `Record` and `ExtRecord` were proven.

---

## 4. The recorder's own screen, `fVideo.Tour`

**CORRECTION.** The plan said "drag to reorder the tour". There is no order to drag.

`fVideo.Tour` holds three tour types, keyed `Monitor`, `Alarm` and `Montion` (the recorder's own
spelling). Each holds a `Mask` of 20 numbers. Each number is a bitmask of which cameras appear in
one split layout. So it is a camera picker per layout, not a running order.

The screen now draws three cards with tick boxes per camera, one card per tour type.
Constants `cfg.TOUR_MASK_KEY`, `cfg.TOUR_MASK_BITS = 32`, `cfg.TOUR_SPLITS`, `cfg.TOUR_TYPE_TITLES`.

---

## 5. Colours

`BackColor` and `FrontColor` appear on covers, the channel title and the time title, as packed ARGB
hex like `0x80000000`. The old field renderer showed a text box with the note "A packed number the
recorder writes in hex. Change it only if you know the layout."

Every screen's payload now carries `cfg.visual_settings()`, so the plain field list can spot those
two names anywhere and draw a colour swatch plus an opacity slider that writes the same string.
Constants `cfg.COLOUR_PREFIX`, `cfg.COLOUR_DIGITS`, `cfg.COLOUR_KEYS`, `cfg.COLOUR_ALPHA_MAX`.

---

## 6. What was built

One new file, `web/js/visual.js`, about 1,100 lines. It exports three things on `window`:
`visualEditor(data, queuePath)`, `visualColourRow` and `visualSplitColour`.

Shared parts inside it:

1. **`shot(channel, visual)`** - a still from `GET /api/live/{channel}/snapshot`, an SVG sheet with
   `viewBox="0 0 8192 8192" preserveAspectRatio="none"` for polygons and lines, an HTML layer for
   boxes and handles, `at()` to turn a pointer event into recorder coordinates, and `drag()`.
2. **A week grid**, 7 rows by 48 columns, painting on drag.
3. **A hex bit grid**, for the movement brush.

Seven editor types cover the nine screens, because area and objects share one:
`privacy`, `overlay`, `motion`, `shape`, `line`, `week`, `tour`. The screen says which one it wants
through a new `editor` key in `cfg.SETTINGS_SCREENS`, and `swann/settings.py` passes it to the page.

### 6.1 Drag that works on a phone

Pointer events throughout (`pointerdown`, `pointermove`, `pointerup`, `pointercancel`) with
`touch-action: none` in the CSS, so one code path serves mouse and finger.

Two faults found and fixed while testing:

- **A tap painted nothing, and a drag measured from the first wobble.** `drag()` only called
  `onMove` on `pointermove`. Fixed by calling it inside `pointerdown` as well.
- **Painting only hit the cell under the pointer.** Both the week grid and the movement brush now
  snapshot the state on press and fill the whole rectangle from the press cell to the current cell
  on every move.

### 6.2 Only real changes are queued

`queuePath` in `web/js/settings.js` compares the new value against the value before the drag and
drops the change if they match, so a drag that ends where it started sends nothing:

```js
function queuePath(config, path, value, before) {
  const key = changeKey(config.key, path);
  if (same(value, before)) { pending.delete(key); }
  else { pending.set(key, {name: config.name, channel: config.channel, path, value}); }
  drawSaveBar();
}
```

---

## 7. Phone width

Chrome on this Mac refuses to make a window narrower than about 563 CSS pixels, and headless Chrome
lays the page out wider than its `--window-size` before cropping the screenshot, so both of those
give a false reading. The real measurement was taken in a same origin iframe sized to 390 and 405
pixels, driven from a throwaway page served out of `web/`, which was deleted afterwards.

Result, all nine screens:

```
privacy   scroll=390 client=390 over=0
overlay   scroll=375 client=375 over=0
motion    scroll=375 client=375 over=0
area      scroll=375 client=375 over=0
line      scroll=375 client=375 over=0
objects   scroll=375 client=375 over=0
recording scroll=375 client=375 over=0
stills    scroll=375 client=375 over=0
monitor   scroll=375 client=375 over=0
```

`scroll` equals `client` on every one, and no element's right edge passes the viewport. No sideways
scroll.

### 7.1 The menu had to fold

The settings menu is 40 links in 7 groups. At 860 pixels and under it stacks above the screen, where
it measured **over 1,600 pixels tall**. Every drawing editor sat below it, so reaching one on a phone
meant scrolling past the whole menu first.

The menu now sits in a `<details>` fold:

- Wide: the CSS hides the handle and shows the groups, whatever the fold's own state says.
- 860 and under: the handle shows and the fold starts shut. Picking a screen shuts it again.

No screen width is written in the JavaScript. It decides whether to shut the fold by asking whether
the handle is on screen (`handle.offsetParent !== null`), so the CSS stays the only place the
breakpoint lives. The handle's word is `cfg.SETTINGS_MENU_LABEL`.

---

## 8. Screens left as plain forms

31 of the 40. Network, ports, Wi-Fi, email, DDNS, IP filter, FTP, cloud, disk, log, general, clock,
users, camera details, information, abilities, PTZ, maintain, auto upgrade, Swann extras, setup
wizard, danger, cameras, video quality, quality limits, people and vehicles, sound, faults, network
state, smart alerts shared settings, monitor.

These are lists of named settings with no spatial or time meaning. A form is the right control and
changing them would be change for its own sake.

---

## 9. Every live write made on 2026-11-08, and its restore

| Config | What was written | Restored to |
|---|---|---|
| `AVEnc.VideoWidget[0].Covers[0].RelativePos` | `[1122, 1042, 3580, 3500]` | `[1024, 1024, 2048, 2048]` |
| `AVEnc.VideoWidget[0].CoversNum` | `1` | `0` |
| `AVEnc.VideoWidget[0].TimeTitleAttribute.RelativePos` | `[1351, 2094, 255, 24]` | `[5166, 512, 255, 24]` |
| `Detect.MotionDetect.Region` (ch 0) | rows 17-30 `0x8001FFFF` | all rows `0xFFFFFFFF` |
| `Custom.SwannSpecialInfo.InfoAlarm.RegionAll[0].Region[0]` | rows 17-30 `0x8001FFFF` | all rows `0xFFFFFFFF` |
| `Detect.Analyze_Swann_Lcd` (ch 0) `TripWire[0].Line` | `StartPt {1600, 4096}`, `EndPt {6600, 4096}` | zeros |
| `Record.ScheduleSheet[0][0]` slot 39 (ch 0) | `1` | `0` |
| `General.General.AutoLogout` | `45` | `60` |
| `NetWork.NetEmailExt.Interval` | changed | original |
| `user2` enabled flag | on | off |

Every one of them was read back after the write and after the restore.

---

## 10. Nothing left open

The five open questions from the first draft are all closed:

1. **What do the 6 rows of `Record.ScheduleSheet` mean?** Row 0 all the time (proven), row 2
   movement, row 4 people and vehicles (inferred). Rows 1, 3, 5 hidden and carried through.
2. **Which movement config does the recorder honour?** Both. Write the plain one first.
3. **Where do line crossing coordinates live?** `TripWire[n].Line.StartPt` and `.EndPt`.
4. **What is the movement grid's real width?** 32 by 32 here, and read from the reply every time.
5. **Is `Custom.SwannSNAP` the same 48 character shape?** Yes, with 3 rows instead of 6.
