# Better Swann UI plan: evidence

Recon done on 2026-11-07 from the Mac at 192.168.1.50. All calls were read-only. No setting was changed.
Serial number and password are deliberately left out of this file.

## Status at a glance

| Thing | State | Route |
| --- | --- | --- |
| Log in to the recorder | Proven | CGI on port 85, salt and MD5_8 sign. Also DVRIP on 9000. |
| Live video | Proven | RTSP on 554, `/chNN/0`, HEVC 4K with audio |
| Still snapshots | Proven | ffmpeg one frame from RTSP, saved to `snapshots/` |
| Read settings | Proven | CGI `getconfig` and `getinfo`, many names confirmed |
| Disk and health | Proven | `getinfo StorageInfo` and `getinfo WorkState` |
| Device features | Proven | `getability SystemFunction` and `Intelligent` |
| Smaller video stream | Open | `/chNN/1` also returns 4K. Encoder config name not found yet. |
| List old recordings | Open | DVRIP `OPFileQuery` gives Ret 117 and no files. Two other routes untried. |
| Download old recordings | Open | Depends on the list working first |
| Playback over RTSP | Open | `/cam/playback` fails on four time formats |
| `/API10/` login | Blocked | Needs a custom `Authorization` value. Not solvable from the app binary alone. |
| ONVIF | Dead end | Recorder is an ONVIF client, not a server |
| Write settings | Untested | `setconfig` exists. Nothing has been written. |
| Email alerts | Untested | `NetWork.NetEmail` exists and is off. Turning it on needs the owner's yes. |

## The recorder

| Item | Value |
| --- | --- |
| Address | 192.168.1.100 |
| Board | NBD80N16RA-KL-V3 |
| Firmware | V1.0.49-8ADVANX, built 2026-05-18 |
| Vendor | Xiongmai (XMeye) firmware under Swann branding. Evidence: RTSP `Server: H264DVR 1.0`, NAT cloud `secu100.net`, dotted config names (`NetWork.Nat`, `AVEnc.VideoWidget`), Sofia MD5_8 password hash, DVRIP login on 9000. Earlier chat said Raysharp; that was wrong (the web UI CSS is called RSUI, which misled it). |
| Channels | `ChannelNum` 8 from login. 2 cameras in use: ch01 "RearSittingRoom", ch02 "Car". Use `ChannelNum`, never hardcode. |
| Video | Both cameras HEVC (H.265) 3840x2160 with pcm_alaw audio at 64 kbit/s |
| Disk | TOSHIBA MQ04ABF100V, 870.70 GB, full and overwriting. Holds about 1155 hours. Oldest footage 2026-09-01. |
| Cloud | `NetWork.Nat`: `NatEnable: true`, `Addr: secu100.net`, port 8000. This is the XMeye P2P link the Swann app uses away from home. |
| Email alerts | `NetWork.NetEmail` exists, `Enable: false`, no server set. |
| Cameras | Sit on the recorder's internal PoE network. Not reachable from the LAN. Plan never talks to cameras directly. |

## Open ports

Scanned 1 to 254 on 192.168.1.x for 80, 85, 554, 8000, 9000, 34567, 35000.

| Port | Use |
| --- | --- |
| 85 | Web viewer and JSON CGI API |
| 554 | RTSP live video (login needed; anonymous gives 401) |
| 9000 | DVRIP (Xiongmai binary protocol). 34567, the usual DVRIP port, is closed. |

## Web viewer blank page

- Cause: a Chrome extension blocks any URL containing "cookie". `js/jcookie.js` fails with "Failed to fetch" in Chrome (devtools shows 503); curl gets it with 200.
- Without it `$.cookie` is undefined, `main.js` throws at line 330 and nothing renders.
- Proven by injecting the jcookie code by hand: login form rendered with no errors.
- Fix for the user: allow 192.168.1.100 in the blocker, or use Safari.

## JSON CGI API (port 85)

- `POST http://192.168.1.100:85/cgi-bin/<cmd>.cgi` with a JSON body. Session is a cookie.
- Login: `login` `{"Name":"GetSalt"}` gives `Salt`. Then `login` `{"Name":"Login","User":u,"Salt":s,"Sign":MD5_8(s + MD5_8(pass))}`.
- Every later call includes `"Salt": s`. `AliveInterval` is 21 s, most likely the server's session timeout. Send `KeepAlive` more often than that; the viewer sends it every 10 s. `Logout` at the end.
- Login reply: `AliveInterval 21`, `ChannelNum 8`, `DataUseAES false`, `ExtraChannel 1`, `SessionID`. AES is off, so `setconfig` bodies are plain JSON.
- Ret codes seen: 100 ok, 101 unknown name, 607 config name not found, 105 session lost (from viewer code).
- Verbs from `js/plugin.js` `CgiClass`: `login`, `getinfo`, `getability`, `getchannelability`, `getconfig`, `setconfig`, `opdev`, `opcontrol`, `getlog`, `usermanager`, `upgrade`, `resetpwd`.
- Per-channel config uses the suffix `.[N]`, for example `Name.[0]` (from `main.js` line 1064).
- `opdev` handles `OPMachine` (reboot), `OPTimeQuery`, `OPLocalSearch`.

MD5_8 (Sofia hash), from `js/md5.js`:

```python
def md5_8(s):
    d = hashlib.md5(s.encode()).digest()
    out = ''
    for i in range(8):
        v = (d[2*i] + d[2*i+1]) % 62
        out += chr(v+48) if v <= 9 else chr(v+55) if v <= 35 else chr(v+61)
    return out
```

### Config names tested with getconfig / getinfo

| Name | Result |
| --- | --- |
| getinfo SystemInfo | 100 |
| getinfo StorageInfo | 100 |
| getinfo WorkState | 100 (`AlarmState`, `ChannelState`) |
| getinfo WifiStatus | 100 |
| getability SystemFunction | 100 |
| getability Intelligent | 100 |
| getchannelability ChannelSystemFunction | 100 |
| Record, ExtRecord | 100 |
| Detect.MotionDetect | 100 |
| NetWork.NetEmail, NetWork.NetFTP, NetWork.NetCommon, NetWork.RTSP, NetWork.Nat, NetWork.NetNTP | 100 |
| General.General, System.ExUserMap, Uart.PTZ, AVEnc.VideoWidget | 100 |
| Simplify.Encode, AVEnc.ExtraFormat, Encode, Detect.HumanDetection, Storage.StorageGlobal | 607 |

Video encoder settings name is still unknown. Find it from the viewer's config pages, which load lazily.

### Abilities switched on (SystemFunction)

Alarm: MotionDetect, HumanDectionNVRNew, VideoAnalyze, NewVideoAnalyze, LossDetect, IPCAlarm, NetAlarm, NetAbort, NetIpConflict, StorageFailure, StorageLowSpace, StorageNotExist.
Net: RTSP, DDNS, DHCP, DNS, EmailTLS, FTP, IPFilter, NTP, Nat, PPPoE, UPNP, Wifi, ARSP, AlarmCenter.
Other: SupportNVR, SupportOnvifClient, SupportExtPlayBack, SupportMaxPlayback, SupportPlayBackExactSeek, SupportPlaybackLocate, SupportNetLocalSearch, SupportSnapSchedule, SupportRestoreConfigV2, SupportMailTest, SupportFTPTest, SupportAbnormitySendMail, SupportDropBoxCloudStroage, AlterDigitalName, SupportSetDigIP, SupportTimeZone, SupportLogStorageCtrl, DownLoadPause.
Encode: DoubleStream, SmartEncodeDigital.
Channel: SupportIPCTalk is `[1, 1, 0, ...]`, so both cameras support two-way talk.
Intelligent: line crossing and area intrusion (PEA) up to 8 lines and 4 areas.

## RTSP

- `rtsp://user:pass@192.168.1.100:554/chNN/0` works for ch01 and ch02. Password must be URL encoded.
- `/chNN/1` also returns 3840x2160. Either the path is ignored or the sub stream is set to 4K. Unproven.
- `/user=<u>&password=&channel=N&stream=1.sdp?real_stream` also returns 3840x2160.
- `/ch01/0?starttime=...` returns live video, not playback. `/playback?...` fails.
- macOS has no `timeout`; use ffprobe/ffmpeg `-timeout 5000000` (microseconds).

## ONVIF

- `POST :85/onvif/device_service` gives 401 "not find Authorization word" with no `WWW-Authenticate` header. Basic auth gives "ValidateSessionToken interface failed". WS-Security UsernameToken also fails.
- Conclusion: the recorder is an ONVIF client (it talks ONVIF to its cameras), not a usable ONVIF server. No ONVIF events or profiles.

## DVRIP (port 9000)

- 20-byte header `<BBxxIIxxHI>`: 0xff, version 1, session, sequence, message id, body length. Body is JSON plus `\x0a\x00`.
- Login message 1000 with `{"EncryptType":"MD5","LoginType":"DVRIP-Web","PassWord":md5_8(pass),"UserName":u}` gives message 1001, Ret 100.
- File search message 1440 `OPFileQuery` returned Ret 117 with no files for every variant tried (Type h264, h265, *; DriverTypeMask 0xFFFF and 0x0001; channel 0; 2026-11-07). Stopped after three tries.
- Next things to try in step 2: check the exact request in the open source `python-dvr` library (OpenIPC) and `OPTimeQuery` first, then `opdev OPLocalSearch` over CGI, then `getconfig NetLocalSearch.[N]`.
- Fallback if all fail: record each camera from RTSP to the Mac with ffmpeg segment files. Disk cost at 4K HEVC is high; measure bitrate first.

## Leads from the Swann app teardown (2026-11-07)

Source: `swannapp/IPA-ANALYSIS.md` and `swannapp/IPA-ANALYSIS-evidence.md`. These are a static teardown of the decrypted Swann Security iOS app 5.13.2, not vendor documentation.

- The app has an XM device layer (`XMDevice.swift`, `XMSession.swift`, `XMCamera.swift`, `XMClipListResponse.swift`). Product type 90 is `XM`, "CCTV System". Clip records keep `xmChannel`, `xmIndex`, `xmClipID` and `xmHint`.
- `XMDevice` builds `http://127.0.0.1:` + `/API10/authenticateUser`. The 127.0.0.1 is the app's own tunnel, so on the LAN that maps to a recorder port.
- On this recorder, port 85 answers every unknown path with 401 "CheckHeaderData interface failed, not find Authorization word". With a Basic header, unknown paths say "ValidateSessionToken interface failed", but `/API10/authenticateUser` says "GetSessionToken interface failed". So `/API10/authenticateUser` is a real endpoint and issues a session token. `/cgi-bin/<unknown>.cgi` gives `{"Ret":136,"Tip":"Not support"}`.
- Login tries that failed on `/API10/authenticateUser` (all 401 GetSessionToken failed): GET Basic plain password, POST Basic plain password, GET Basic MD5_8 password, GET Basic MD5 hex password. Stopped after three approaches.
- Teardown sections 30 and 31 (added later) list the XM fields `username`, `password`, `recordlist`, `startTime`, `endTime`, `clipID` and the log `[XM] Download clip:`. They say plainly that the exact `authenticateUser` body is not in the binary.
- Correction from the IPA disassembly (2026-11-07): `XMSession` sends `POST http://127.0.0.1:<port>/API10/authenticateUser` with an `Authorization` header. The header name is stored inline in the code at `0x10018d0fc` to `0x10018d124`, so `strings` misses it. The value is built at `0x10018db54` from the device credentials, a timestamp and a hash, then base64 encoded. It is not `Basic <plain>` and not `Basic <md5>`, which is why those attempts failed. The exact algorithm needs a traffic capture or more disassembly.
- `POST /API10/authenticateUser` with JSON `{"username","password"}` and no header gives 401 "There is no Authorization word in the command". The same body plus a Basic header gives "GetSessionToken interface failed". So an `Authorization` header is required, and Basic with the plain password is not the accepted form.
- Swift stores short strings (15 bytes or less) inside the code, not in the string table, so values like `Basic ` or a header name will not show up with `strings`. Finding the format statically needs disassembly of `XMSession`.
- The HAL call names (`getRecordList?startTime=<t>&recordMax=9999&streamType=0`, `downloadRecord?ClipID=`, `downloadThumbnail?Channel=`, `getRecordingStatus`) sit under `/API10/` and are the likely route to clip search and download once the login is known.
- App playback RTSP format: `rtsp://<u>:<p>@127.0.0.1:<port>/cam/playback?channel=%d&starttime=%@&endtime=%@&streamType=%d`. On this recorder's 554 it fails with "Invalid data found" for start times `2026_11_07_20_00_00`, `20261107T200000Z`, `2026-11-07T20:00:00Z` and `20261107200000`. The time format is unknown, or the path is for another family.
- Next ways to get the login and time formats: capture the app's own traffic (iPhone on USB, `rvictl -s <UDID>`, then `tcpdump` on the `rvi0` interface while the app shows playback on home Wi-Fi), or disassemble `XMSession` in the binary. A capture is cheaper and gives the exact format. It only helps if the app reaches the recorder on the LAN, not through the TUTK relay.

## Events

- No ONVIF event stream. Polling `getinfo WorkState` (`AlarmState`) is possible.
- Better route: turn on `NetWork.NetEmail` and point it at a small SMTP receiver on the Mac. Motion and person alerts then arrive with snapshots. `NetWork.NetFTP` is a second route for clips. `NetAlarmCenter` exists but is likely proprietary.

## Sessions and users

- Viewer KeepAlive code handles Ret 105 (session lost) and reconnects. A second admin login may kick the first. Not tested.
- Plan step 1: the tool creates its own user via the CGI `usermanager` verb. the owner cannot use the web viewer while the cookie blocker is on, so the tool does it. Confirm the user list first and never change the admin account.

## Stack

- go2rtc as the video relay: RTSP in, WebRTC or MSE out to the browser. It handles HEVC for Safari and for Chrome on Mac with hardware decode, and can transcode with ffmpeg if needed.
- Python (FastAPI) back end. Reason: the DVRIP and CGI probes are already in Python, and `python-dvr` is a Python reference.
- Plain web front end served by the back end. Runs on the Mac first.
- Settings: read and back up all config before any `setconfig`. `SupportRestoreConfigV2` suggests a config export exists.

## Commands used

Probe scripts are in the session scratchpad, not the project. Their core calls:

```bash
# port scan (macOS nc)
nc -z -G 1 -w 1 192.168.1.$i $p

# RTSP check
ffprobe -v error -timeout 5000000 -rtsp_transport tcp -show_entries stream=codec_type,codec_name,width,height -of csv=p=0 "rtsp://$U:$ENC_PASS@192.168.1.100:554/ch01/0"

# still image
ffmpeg -v error -timeout 5000000 -rtsp_transport tcp -i "$URL" -frames:v 1 -y snapshots/camera-01.jpg
```

## Other notes

- Camera 1 shows bright IR glare streaks, most likely a spider web on the lens.
- Camera 2 has privacy masks set (black blocks at the top and right).
- `.env` holds `SWANN_HOST`, `SWANN_RTSP_PORT`, `SWANN_WEB_PORT`, `SWANN_USER`, `SWANN_PASS`. Not a git repo yet; add `.env` and `snapshots/` to `.gitignore` when one is made.

## Step 1 spike: listing recordings (2026-11-08)

Scripts: `the session scratchpad/spike_files.py`, `spike_calibrate.py`, `spike_bisect.py`, `spike_shape.py`.
Reference read: `OpenIPC/python-dvr` `dvrip.py` (`DVRIPCam.list_local_files`), saved at `scratchpad/ref-pythondvr/dvrip.py`.

### Route A is dead, and it was never about recordings

`OPLocalSearch` and `NetLocalSearch` search the LAN for IP cameras to add to the recorder, not
recordings. Proof, from the recorder's own `html/cfg/IPCan_set.js` line 383:

```js
function SearchDevice(){
    var req = {"Name":"OPLocalSearch"};
    req.OPLocalSearch = { "SearchProtocol" : "ONVIF" };
    ...
    }, pageTitle, "OPLocalSearch", -1, cgiCmd.opdev, req);
}, pageTitle, "NetLocalSearch", -1, cgiCmd.getconfig);
```

The earlier note that Route A was "the best evidenced" route was wrong. It read `main.js` line 1026
(which only sets a 10 second timeout for the verb) and never found the caller.

### The recorder's web interface has no viewer

`main.js` loads only `html/config_c7.html` and `html/cfg/<page>.html`. There is no live page and no
playback page. `gVar.sPage == "live"` and `== "playback"` are dead branches referring to an `ipcocx`
browser plugin that this firmware does not ship. So there is no plugin binary on the recorder to read
field names from, and the earlier "blank page" was not a broken viewer, it is a viewer that was removed.
(The Chrome cookie-blocker finding still stands for the config pages.)

### CGI request shape, confirmed from `js/plugin.js`

`{"Name": "<verb>", "<verb>": {...}, "Salt": "<salt>"}`. Verified against `this.Reboot`.
Config page ids, from `html/config_c7.html`, include `main_stream_set` and `sub_stream_set`, which is
where step 3's encoder config name lives. `html/cfg/main_stream_set.js` and `sub_stream_set.js` are
downloaded in the scratchpad and not yet read.

### DVRIP file search: framing is right, the request layout is not

Working on port 9000, header `BB2xII2xHI`, body JSON + `\x0a\x00`, body length `len+2`,
session from `int(SessionID, 16)`:

| Call | Result |
| --- | --- |
| 1000 login | Ret 100, 8 channels, AliveInterval 21 |
| 1452 `OPTimeQuery` | Ret 100, `"2026-11-08 11:37:55"`. Recorder clock is correct. |
| 1020 `SystemInfo` | Ret 100, BuildTime 2026-05-18 15:35:20 |
| 1998 (nonsense code) | Ret 102 "unsupported version" |
| 1440 `OPFileQuery`, no object | Ret 119 |
| 1440 `OPFileQuery`, any object | Ret 117 |

So framing, login and session handling are all proven correct by 1452 and 1020 on the same socket.
Code 1440 is recognised, because an unknown code gives 102 instead.

Return codes, from `python-dvr` `CODES`: **117 is "message format error", 119 is "no file found".**
The earlier note that treated 117 as "no files" was wrong, which is why the first three attempts looked
like an empty result rather than a rejected request.

### What was tried on 1440, and the pattern

Gives **117**: the exact `python-dvr` body; `DriverTypeMask` as int; `StreamType` as int; both as int;
`Channel` 1; `Type` `*`; no `Event`; `Event` `A`; object in a list; object as `""`;
**object as `{}`**; object as `{"Channel": 0}`.

Gives **119**: no `OPFileQuery` key at all; key as `null`; key renamed `OPFileQuery_v2`;
all criteria moved to the top level of the body.

Read it as: when the recorder cannot find an `OPFileQuery` object it skips the parse and answers 119.
When it does find one it parses it and rejects it as malformed, even when empty. An empty object giving
117 rules out "one bad field value" and rules out "an unknown key upsets it". The remaining explanation
is that this firmware requires fields we have not named, so every object so far is missing them.

Guessing more field names is the wrong next move. Field names must come from a source, not a guess.

### Both reference clients' field sets are rejected

`alexshpilkin/dvrip` (`dvrip/files.py`, saved at `scratchpad/ref-shpilkin/files.py`) sends a different,
smaller object than `python-dvr`: request 1440, reply 1441, and only five fields, with no
`DriverTypeMask` and no `StreamType`:

```python
class FileQuery(Object):
    start:   member('BeginTime', datetimetype)
    end:     member('EndTime', datetimetype)
    channel: member('Channel')
    event:   fixedmember('Event', '*')
    type:    member('Type')            # FileType is only 'h264' or 'jpg'
```

Its date format is `'%Y-%m-%d %H:%M:%S'`, the same one the recorder returns from `OPTimeQuery`, so the
time strings were never the problem. Sent exactly this set, with `Type` `h264` and `jpg`, channels 0 and
1, over 2 hour, 24 hour and 7 day windows: **Ret 117 every time** (`scratchpad/spike_files2.py`).

**Conclusion: `OPFileQuery` is closed on this firmware.** Two independent reference clients, one
exhaustive field matrix and a container-shape matrix all get 117. This is not a layout we have failed to
guess, it is a request the firmware refuses. Consistent with the rest of the picture: the web interface
has no playback page, and the Swann app uses `/API10/getRecordList` instead of port 9000.

### Playback claims succeed but never deliver video

`OPPlayBack` with `PlayMode: "ByTime"` needs no file name, so it does not depend on a file list.

| Call | Result |
| --- | --- |
| 1424 Claim, ByTime, ch0 | **Ret 100** |
| 1424 Claim, ByTime, ch1 | **Ret 100** |
| 1420 DownloadStart after claim, ch0 and ch1 | 0 packets, 0 bytes, socket times out |
| 1420 Start after claim, ch0 and ch1 | 0 packets, 0 bytes, socket times out |

Scripts: `scratchpad/spike_playback.py`, `spike_download.py`, `spike_download2.py`. Each case used a
fresh socket and login so a stalled stream could not affect the next one. The window was a one minute
range two hours before the recorder's own clock, on a disk that is full and recording.

Claim returning 100 for every channel and every range, including ranges with no data, suggests the claim
handler does not validate anything. Read together with the 117 on `OPFileQuery`, the open DVRIP playback
path on this firmware looks disabled rather than merely different.

**Three approaches to old footage have now failed: `OPFileQuery`, `OPPlayBack DownloadStart` and
`OPPlayBack Start`. Stopping on port 9000 per the three-strikes rule.**

### Step 3: the sub stream exists, its RTSP path is still unknown

`getability EncodeCapability` (Ret 100) reports `MaxBitrate` 131072 and:

```
EncodeInfo: MainStream    Enable true,  HaveAudio true,  CompressionMask 0x00000180
            ExtraStream2  Enable true,  HaveAudio true,  CompressionMask 0x00000180
            ExtraStream3  Enable false
            ExtraStream4  Enable false
            JPEGStream    Enable true,  HaveAudio true,  CompressionMask 0x00000180
```

So a second, smaller stream and a JPEG stream are both switched on in hardware. That matters, because the
fallback plan depends on recording something smaller than 4K.

But the encoder settings cannot be read over CGI. `main_stream_set.js` and `sub_stream_set.js` name
`AVEnc.Encode`, `EncodeCapability` and `NetUse.DigitalEncode`, and of those only `EncodeCapability`
answers. Tested and refused with Ret 607: `AVEnc.Encode`, `AVEnc.Encode.[0]`, `AVEnc.Encode.[1]`,
`NetUse.DigitalEncode`, `Simplify.Encode.[0]`, `Encode.[0]`, `AVEnc.EncodeStaticParam`,
`Camera.ParamEx.[0]`, `NetUse.NetDigital`. Answering with Ret 100: `NetUse.EncodeChDisplay`
(`displayChanelMask 0x0000000000000000`) and `Camera.Param.[0]`.

So the bitrate and resolution of `ExtraStream2` cannot be read or changed from the network on this
firmware. Changing it needs the recorder's own on-screen menu on the TV. The RTSP path that serves it is
also still unknown: `/ch01/1` and `&stream=1.sdp` both returned 3840x2160.
