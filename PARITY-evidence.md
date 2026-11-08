# Parity audit: the recorder's own web UI versus this tool

Written 2026-11-08, after the owner asked whether the new tool will have everything the old web UI has.

Source: the recorder's own web files, downloaded from `http://192.168.1.100:85/` and kept in the session
scratchpad at `.../scratchpad/rsui/`. 50 files, 47 of them settings screens under `rsui/cfg/`.

## 1. The old web UI is settings only

`rsui/index.html` lines 59 to 71 contain the entire top menu. It holds exactly one button:

```html
<div class="Menu">
    <div class="menuBox" id="ConfigMenu">
        <div id="configBtn" class="menuBtn" data-name="">Remove Setting</div>
    </div>
</div>
```

"Remove Setting" is a mangled "Remote Setting". There is no Live button, no Playback button and no Path
button. `main.js:900` lists `["LiveMenu", "PlayBackMenu", "ConfigMenu", "PathMenu"]` and `index.html:87-90`
declares `<div class="Page" id="live">` and `id="playback"`, but no markup ever shows them and no menu
entry ever loads them. They are dead leftovers from the generic Xiongmai build.

This independently confirms the earlier finding in `PLAN-evidence.md`: the browser interface has no live
view and no playback. Swann's own support says the same for ADVANX.

**So full parity with the old web UI means matching its settings, not its video.** The live view, the
playback and the alert list in `BUILD-PLAN.md` are all additions beyond parity.

## 2. The API surface, from `rsui/plugin.js` lines 243 to 404

Every request is `POST http://<host>:85/cgi-bin/<verb>.cgi` with a JSON body carrying `Salt`.

| Verb | What it does | In `swann/cgi.py`? |
| --- | --- | --- |
| `login` | GetSalt, GetPreLoginInfo, Login, Logout, KeepAlive | yes |
| `getconfig` | read one config by name | yes |
| `getability` | read a device ability | yes |
| `getchannelability` | read a channel ability | yes |
| `getinfo` | read SystemInfo, StorageInfo, and so on | yes |
| `setconfig` | **write one config** | **no** |
| `opdev` | OPMachine (reboot), OPTimeSetting, OPMailTest, OPDDNSTest, OPLocalSearch, OPStorageManager, OPDefaultConfigSwann | partly, `op_dev` exists but none of these are wired up |
| `getlog` | read the device log | **no** |
| `usermanager` | GetAllUser, ModifyUser, ModifyPassword | **no** |
| `opcontrol` | control commands, used by PTZ | **no** |
| `upgrade` | UpgradeStart, UpgradeData, UpgradeStatus | **no** |
| `resetpwd` | SetLanguage, CheckSafetyAnswer, CheckVerifyCode, SetNewPassword | **no** |

`VERB_SET_CONFIG`, `VERB_OP_CONTROL`, `VERB_GET_LOG` and `VERB_USER_MANAGER` are already named in
`swann/config.py` lines 84 to 88, but no method calls them.

**Nothing has ever been written to the recorder in this project. Every request so far has been a read.**
So `setconfig` is unproven. Until one safe write succeeds, full control cannot be promised.

## 3. Every screen in the old web UI

From `rsui/config_c7.html`. Nine groups, 36 menu entries, 6 of them hidden by default with
`style="display:none"` (the web UI un-hides some based on device ability).

### Display
| Screen | File | Config names it touches |
| --- | --- | --- |
| IP Channels (hidden) | `IPCan_set.js` | NetWork.ChnStatus, NetWork.RemoteDeviceV3 |
| Live | `chn_live.js` | AVEnc.VideoWidget, Custom.SwannSpecialInfo.InfoDisplay, NetWork.ChnStatus, NetWork.RemoteDeviceV3 |
| Display Configuration | `chn_display.js` | fVideo.GUISet, fVideo.Tour, fVideo.VideoOut, Custom.SwannSpecialInfo.InfoDisplay |
| Privacy Zone | `chn_sp.js` | AVEnc.VideoWidget |

### Record
| Screen | File | Config names it touches |
| --- | --- | --- |
| Rec Parameters | `record_pz.js` | Record, Custom.SwannSpecialInfo.InfoRecord |
| Rec Schedule | `record_jh.js` | Record |
| MainStream | `main_stream_set.js` | AVEnc.Encode, Simplify.Encode, NetUse.DigitalEncode, NetUse.DigitalAbility, NetUse.EncodeChDisplay, General.Location, NetWork.ChnStatus, NetWork.RemoteDeviceV3 |
| SubStream | `sub_stream_set.js` | same set as MainStream |

### Capture
| Screen | File | Config names it touches |
| --- | --- | --- |
| Capture | `Capture_Set.js` | Custom.SwannSNAP, AVEnc.Encode, General.Location |
| Capture Schedule | `Capture_Jh.js` | Custom.SwannSNAP |

### Network
| Screen | File | Config names it touches |
| --- | --- | --- |
| NetWork | `net_base.js` | NetWork.NetCommon, NetWork.NetDHCP, NetWork.NetDNS, NetWork.Nat |
| Wi-Fi | `Net_wireless.js` | NetWork.Wifi |
| Port Configuration | `port_configuration.js` | NetWork.NetCommon, NetWork.RTSP, NetWork.Upnp, Custom.SwannSpecialInfo.InfoNetwork |
| Email Setting | `net_email.js` | NetWork.NetEmail, NetWork.NetEmailExt (DefaultMail, EmailEncry, Interval, SendName) |
| Email Schedule | `email_jh.js` | NetWork.NetEmailExt.WorkSheetEmail, NetWork.NetEmailExt.WorkSheetAbnormal |
| DDNS | `net_ddns.js` | NetWork.NetDDNS |
| IP Filter | `IPFilter_list.js` | NetWork.NetIPFilterV2 |
| FTP | `FTP_Set.js` | `NetWork.NetFTP`, confirmed by live read. The screen's own JS was not downloaded, see section 7 |

### Alarm
| Screen | File | Config names it touches |
| --- | --- | --- |
| Detection | `alarm_mv.js` | Detect.MotionDetect, Custom.SwannSpecialInfo.InfoAlarm, NetWork.ChnStatus, NetWork.RemoteDeviceV3 |
| Deterrent | `flood_light.js` | Alarm.Deterrent, Custom.SwannSpecialInfo.InfoAlarm |

### Analytics
| Screen | File | Config names it touches |
| --- | --- | --- |
| PD, people detection | `Human_Detection.js` | Detect.HumanDetectionDVR, Detect.CarShapeDetection, Detect.Analyze, Alarm_PD |
| Sound Detection | `Sound_Detection.js` | Detect.Sound, Alarm_SD |
| PID (hidden) | `Perimeter_Zone.js` | Detect.Analyze_Swann_Pid, Detect.Analyze, Alarm_PID |
| LCD (hidden) | `Perimeter_Line.js` | Detect.Analyze_Swann_Lcd, Detect.Analyze, Alarm_PID |
| SOD (hidden) | `GoodsLost_Legacy.js` | Detect.Analyze_Swann_Sod, Detect.Analyze |
| Analytics Schedule (hidden) | `record_smart.js` | Detect.Analyze |

### Device
| Screen | File | Config names it touches |
| --- | --- | --- |
| HDD | `sysinf_hdd.js` | StorageInfo, StorageNo, Record, SnapShot, General.General, General.AutoMaintain. Writes go through `opdev` OPStorageManager |
| Log Info | `Dev_log.js` | uses the `getlog` verb |
| PTZ | `chn_yt.js` | Uart.PTZ, Custom.SwannSpecialInfo.InfoDevice. Moves go through `opcontrol` |
| Cloud Storage | `SwannClo_Sto.js` | NetWork.DropBoxCloud |

### System
| Screen | File | Config names it touches |
| --- | --- | --- |
| General | `syspm_general.js` | General.General, General.Location, fVideo.OsdLogo, fVideo.AudioAcquisitionMode, NetWork.ChnMode, NetWork.NetCommon, Guide |
| Date and Time | `syspm_dst.js` | General.General, General.Location, General.DstTimeOffset, System.TimeZone, NetWork.NetNTP. Writes go through `opdev` OPTimeSetting |
| User | `syspm_user.js` | System.ExUserMap, RecordConfig, SnapConfig, StorageManager. Uses the `usermanager` verb |
| Information | `sysinf_base.js` | read only: General.Location, NetWork.NetCommon, NetWork.Wifi, StorageInfo, Custom.SwannSpecialInfo.InfoNetwork |
| Channel Info | `Chn_Info.js` | read only: Simplify.Encode, NetUse.*, NetWork.ChnStatus, NetWork.RemoteDeviceV3, General.Location |
| Record Info | `Rec_Info.js` | read only: Record, Simplify.Encode, NetUse.*, Custom.SwannSpecialInfo.InfoRecord |
| Network State | `sysinf_net.js` | read only: NetWork.NetCommon, NetWork.NetDHCP, NetWork.NetDNS, NetWork.RTSP, NetWork.Upnp |

### Advanced
| Screen | File | Config names it touches |
| --- | --- | --- |
| System Upgrade (hidden) | `syswh_sj.js` | uses the `upgrade` verb and `upgrade.cgi?Name=UpgradeData` |
| Load Default | `syswh_mr.js` | Alarm, Record. Writes go through `opdev` OPDefaultConfigSwann |
| Maintain | `auto_wh.js` | General.AutoMaintain, Custom.SwannSpecialInfo.InfoAdvanced |
| Events | `alarm_yc.js` | Detect.LossDetect, Storage.StorageFailure, Storage.StorageLowSpace |
| Auto Upgrade | `syswh_au.js` | Custom.SwannAutoUpgrade |

## 4. Count

Counted from `rsui/config_c7.html`:

- **42 screens.** 36 are visible by default. 6 carry `style="display:none"` and the web UI un-hides them
  based on device ability: IP Channels, PID, LCD, SOD, Analytics Schedule and System Upgrade.
- 9 top level groups. The two Analytics group headers are containers, not screens, so they are not counted.
- 59 distinct config names.
- 12 CGI verbs, 5 of which the tool can already call.

Caveat on the tables in section 3: the config names were pulled out by pattern matching, so a few entries
are not config names at all. `Dev_log.js` "Record" and "StorageDeviceError" are log categories.
`syswh_mr.js` "Alarm" and "Record" are reset categories. `syspm_user.js` "RecordConfig" and "SnapConfig"
are permission names. Each screen gets its own proper read when it is built.

## 5. Live test: which of those 59 names this recorder actually has

Run against `192.168.1.100` on 2026-11-08. Script kept at
`.../scratchpad/spike_names.py` and `spike_names2.py`.

**57 of 59 names read successfully. 2 refused. 3 more are analogue-only and do not apply.**

Six names only work with a channel suffix, exactly as `main.js:1058-1066` builds them: `getconfig` appends
`.[N]` to the name when the channel is not -1.

| Name | Result |
| --- | --- |
| `NetUse.DigitalEncode.[0]` and `.[1]` | OK. This is the real MainStream and SubStream config on this recorder |
| `NetUse.DigitalAbility.[0]` | OK. Gives the allowed ranges, for example `IFrameRange main_min 1 main_max 64` |
| `NetWork.NetEmailExt.DefaultMail` | OK, `true` |
| `NetWork.NetEmailExt.EmailEncry` | OK, `1` |
| `NetWork.NetEmailExt.Interval` | OK, `30` |
| `NetWork.NetEmailExt.SendName` | OK, `"NVR-8ADVANX"` |

Not applicable, this is a pure network recorder with no analogue inputs, so the analogue encoder configs
are absent. `main_stream_set.js:84` reads `AVEnc.Encode` for analogue channels and line 101 reads
`NetUse.DigitalEncode` for network channels. Only the second applies here.

| Name | Result |
| --- | --- |
| `AVEnc.Encode`, with and without a channel | Ret 607 |
| `Simplify.Encode` | Ret 607 |
| `SnapShot` | Ret 607 |

Genuinely refused, and both need settling when their screen is built:

| Name | Result | Note |
| --- | --- | --- |
| `NetWork.NetEmailExt.WorkSheetEmail.[0]` | Ret 607 | the Email Schedule screen's per channel sheet |
| `NetWork.NetEmailExt.WorkSheetAbnormal` | Ret 607 | `email_jh.js:29` reads exactly this name with channel -1. So the Email Schedule screen probably fails on this firmware in the real web UI too. Worth checking in Chrome before building it |

**Correction, same day.** `Alarm.Deterrent` answered Ret 607 in the first sweep but reads fine now. Read
six times in a row it answered Ret 100 every time, with the value `[null, null]`: a list of 2, one entry
per connected camera, both empty. So the name exists and the Deterrent screen can be built, but these two
cameras appear to have no floodlight to control. The earlier 607 is not reproducible. The one difference
was that a second admin login was active at the time, which matters, see section 10.

Also confirmed present and readable: `NetWork.NetFTP` (dict of 4), so the FTP screen is real.
`getability SystemFunction` says `NetServerFunction.NetFTP: true` and `OtherFunction.SupportFTPTest: true`.

All three hidden analytics configs read fine on this recorder, as lists of 8 channels:
`Detect.Analyze_Swann_Pid`, `Detect.Analyze_Swann_Lcd` and `Detect.Analyze_Swann_Sod`. So PID, LCD and SOD
are buildable here even though the old UI hides them.

## 6. How a write is shaped

`alarm_mv.js:316` is a real write in the old UI:

```js
}, pageTitle, "Detect.MotionDetect", -1, cgiCmd.setconfig, cfg);
```

`main.js:1085-1101` then posts the body straight to `setconfig.cgi` and treats `Ret 100` and `Ret 603` as
success. `Ret 107` means "no parameter". For `NetWork.NetCommon` it also treats any negative Ret as
success, because changing the recorder's own address kills the reply.

## 7. The static web files need a different key from the API

The 44 screen files in `rsui/cfg/` were downloaded through Chrome, using the owner's own browser session. Three
did not come down: `FTP_Set.js`, `mInteSM_Basic_item.js` and `mInteSM_RecSche_item.js`. Each holds the
61 byte body `CheckHeaderData interface failed, not find Authorization word`.

Tested again from this tool's own logged in session: **every** static path returns 401 with that same body,
including `index.html`, `main.js` and files that definitely exist. The tool's httpx cookie jar is empty,
because this API carries its session in the JSON `Salt` field, not in a cookie.

So the recorder has two separate doors:

- `/cgi-bin/*.cgi` takes the `Salt` session. **This is open and every settings read works through it.**
- static files and `/API10/` want an `Authorization` header. This is shut, and it is the same blocker as
  the parked playback question.

This does not hold up the settings work. It only means the last two screen files cannot be read for
reference, so those two screens get built from their live config instead. Both are menu containers whose
markup is already in `config_c7.html`, so only `FTP_Set.js` is a real loss, and `NetWork.NetFTP` reads fine.

## 8. What is not parity, but the owner also wants

These are in `BUILD-PLAN.md` and have no equivalent in the old web UI at all:

- live view in the browser (the old UI has none)
- playback of old footage (the old UI has none, and see `PLAN-evidence.md` for why this is hard)
- an alert list and alert history (the old UI only sets alarms up, it never shows what happened)
- a settings backup, so a wrong change can be undone

## 9. The honest risk

`Custom.SwannSpecialInfo.*` and `Custom.Swann*` are Swann's own additions on top of stock Xiongmai. Several
screens read them to decide which fields to show. They are read with `getconfig` like any other name, so
they should work, but each one needs reading off the live recorder before a screen is built. An unknown
name answers `Ret 607`.

`setconfig` has never been called in this project. The first write must be to something harmless and
reversible, with the old value read and saved first.

## 10. Step 3 is built: the settings backup

`swann/backup.py`, `scripts/backup_settings.py`, run with `make backup`. Read only. It never writes.

Verified against the live recorder on 2026-11-08:

```
ok: 67 settings read, 1 not on this recorder, as expected, 12 skipped on empty camera sockets
  Saved to  ./data/config-backups/2026-11-08-142809.json
  Not on this recorder, which is expected:
    NetWork.NetEmailExt.WorkSheetAbnormal
  Skipped 12 settings on empty camera sockets.
```

The file is about 680 KB of JSON. It holds 57 named configs, `NetUse.DigitalEncode` and
`NetUse.DigitalAbility` per camera, `SystemInfo`, `StorageInfo`, `WorkState`, the `SystemFunction` and
`EncodeCapability` abilities and the `ChannelSystemFunction` channel ability. Every run also overwrites
`data/config-backups/latest.json`.

The 12 skipped settings are `NetUse.DigitalEncode.[2]` to `.[7]` and `NetUse.DigitalAbility.[2]` to `.[7]`.
Those sockets hold no camera, so the setting does not exist. The backup counts them separately from a real
failure, so a clean run reports zero failures.

### It is restorable

Checked by walking the saved JSON for field names containing pass, pwd, key, secret or token, printing the
name and whether it is set but never the value. The restorable secrets are all there:

```
config.Custom.SwannSpecialInfo.InfoDefaultEmail[0].Password  (str, set)
config.Custom.SwannSpecialInfo.InfoDefaultEmail[1].Password  (str, set)
config.NetWork.NetDDNS[0..4].DDNSKey                         (str, set)
config.NetWork.NetEmail.MailServer.Password                  (str, empty)
config.NetWork.NetFTP.Server.Password                        (str, empty)
config.NetWork.RTSP.Server.Password                          (str, empty)
config.NetWork.Wifi.Keys                                     (str, ...)
```

`net_email.js:47` reads the SMTP password from `cfg.MailServer.Password`, which is the nested field above,
so email is restorable too. Most are empty only because those services are not set up on this recorder.

**So `data/config-backups/` holds real credentials.** `data/` is in `.gitignore`. Never print a value out
of these files.

### Caution: two admin logins at once

The recorder's login is per user, and a second login can push the first out. During this work a background
uvicorn server held one admin session while a spike script opened another. That is the one difference
between the sweep where `Alarm.Deterrent` answered 607 and the six later reads where it answered 100.

It is not proven to be the cause, but it is the only variable that changed, and it is a known property of
this firmware. So:

- Prefer running a backup through the app's own shared session rather than a second login.
- Treat a lone, unrepeatable 607 as suspect, not as proof a setting is absent.

## 11. Correction: DeviceRunTime is a lifetime total, not uptime

Earlier this file and the health page read `DeviceRunTime` as time since the last start. Wrong.

`getlog` with `Type: LogSystem` over 30 days returns exactly two rows on this recorder:

```
2026-11-08 00:05:09  ShutDown  2026-11-08 00:05:09(2)
2026-11-08 00:05:41  Reboot    2026-11-08 00:05:09
```

So the recorder restarted at 00:05 on 2026-11-08. At 14:36 the same day `DeviceRunTime` read `0x00034168`,
which is 213,352. As minutes that is 148 days. Both cannot describe the same span, so the counter is a
lifetime total that survives a restart.

`General.AutoMaintain` explains the restart: `{"AutoDeleteFilesDays": 0, "AutoRebootDay": "Sunday",
"AutoRebootHour": 0}`. 2026-11-08 is a Sunday. The recorder restarts itself every Sunday at midnight.

The health page now shows both, read from different places:

| Line | Source |
| --- | --- |
| On since restart | now minus the newest `Reboot` row in `LogSystem` |
| Last restart | that row's `Time` |
| Total time running | `DeviceRunTime`, rounded to whole months |

Measured tick rate stays about 64 to 66 seconds, not a clean 60, so the lifetime total keeps its rounding.

## 12. The log replaces the planned email alert catcher

A full sweep of `getlog` `LogAll` over a year returns 4096 rows in 32 pages, covering
2026-11-06 01:07:33 to now. So the recorder keeps about 4096 log rows, which is two and a half days here.

Row types in that sweep:

```
EventStart 1937   EventStop 1937   LogIn 85   LogOut 84   Logout 21
Record 19   SaveConfig 6   Login 4   ShutDown 1   Reboot 1   WFS1 1
```

Most common `Data` values:

```
MotionDetect,1                              3868
admin,DVRIP-Web:192.168.1.50                98
admin,DVRIP-DSS:192.168.1.50                71
.rtsp:192.168.1.50                          19
Record Search                                19
.rtsp:192.168.1.50(password error)           4
AdvPd,2                                       2
AdvVd,2                                       2
```

One row looks like this:

```json
{"Data": "MotionDetect,1", "Position": 0, "Time": "2026-11-06 01:07:04",
 "Type": "EventStart", "User": "System"}
```

**So the alert history is already on the recorder and it hands it over.** `Data` carries the kind and the
channel, `Type` says start or stop, `Time` is exact. `AdvPd` is people detection and `AdvVd` is vehicle
detection, both on channel 2.

This is better than the planned step of having the recorder email each alert to the Mac, so that step is
dropped. The Mac copies the log into its own store instead, which means history keeps growing past the
recorder's two and a half days.

Worth noting for later: 3868 of the 3872 motion rows are channel 1. Channel 2 produced only four advanced
events. Either the second camera sees almost nothing, or its motion detection is set differently.

## 13. The write half of the client is built

Added to `swann/cgi.py`, with `RET_WRITE_OK_CODES` passed as `ok_codes` so a write accepts Ret 603:

| Method | Verb | Tested |
| --- | --- | --- |
| `get_log` | `getlog` | yes, returns rows once a `BeginTime` and `EndTime` are given. With no range it returns `[]` |
| `get_users` | `usermanager` `GetAllUser` | yes, 1595 characters of accounts and authority lists |
| `upgrade_status` | `upgrade` `UpgradeStatus` | **no, answers Ret 0.** Not a code this firmware documents. Firmware upgrade is the least useful screen, so it is left for last |
| `set_config` | `setconfig` | see section 14 |
| `op_control` | `opcontrol` | not yet, used by the email and DDNS tests and by PTZ |
| `user_manage` | `usermanager` | not yet, it writes |
| `reboot` | `opdev` `OPMachine` | not yet, it restarts the recorder |

`set_config` refuses to run at all if `login_info.DataUseAES` ever turns true, because a config write would
then need encrypting and a plain write could corrupt it. This recorder reports false.

`RecorderSession.write_config` reads the old value through the same lock before writing, and returns a
`WriteOutcome` holding that old value, so any change can be put back.

## 14. Step 5: the first writes, proven and put back

Three writes were made to the live recorder on 2026-11-08, each one read back and then restored. Script at
`.../scratchpad/spike_write2.py`. Nothing was left changed.

| Config | Shape | Change | Took effect | Restored |
| --- | --- | --- | --- | --- |
| `General.General` | nested fields in a dict | `AutoLogout` 60 to 61 | **yes** | yes |
| `NetWork.NetEmailExt.Interval` | a plain number | 30 to 31 | **yes** | yes |
| `ChannelTitle` | a list of 8 strings | socket 1 to "Camera 1" | **no** | yes |

All three answered Ret 100. So Ret 100 alone does not prove a change landed, which is why every write in
this tool reads the value back.

The two that worked settle the question: **`setconfig` works on this recorder and full control is real.**

`General.General.AutoLogout` is how long the recorder's own on screen menu waits before logging itself out.
`NetWork.NetEmailExt.Interval` is minutes between alert emails, and email is not set up here. Both were
picked because changing them affects nothing in use.

### ChannelTitle is a special case

`ChannelTitle` accepts a write, answers Ret 100 and ignores it. Tried on an empty socket and on a connected
camera, with the same result. These are network cameras, so the camera's name most likely lives on the
camera itself and reaches the recorder through `NetWork.RemoteDeviceV3`. To be settled when the Display
screens are built. It is a label only, so nothing depends on it.

### Earlier test on an empty socket, for the record

The very first write wrote `ChannelTitle` back unchanged, which answered Ret 100 and left the value alone,
as expected. The second changed socket 8, an empty one, which also answered Ret 100 and changed nothing.
At that point the cause was not yet known to be `ChannelTitle` itself.
