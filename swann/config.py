"""Every constant for Better Swann UI lives here.

Nothing else in this project holds a literal value. If you need a number, a
path, a port, a timeout or a URL shape, add it here and import it.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_DIR / ".env"
WEB_DIR = PROJECT_DIR / "web"
DATA_DIR = PROJECT_DIR / "data"
MEDIA_DIR = PROJECT_DIR / "media"
SNAPSHOT_DIR = PROJECT_DIR / "snapshots"
BACKUP_DIR = DATA_DIR / "config-backups"
DB_PATH = DATA_DIR / "swann.db"

# ffmpeg is found below, once .env has been read.


# --------------------------------------------------------------------------
# .env loading
# --------------------------------------------------------------------------
def _load_env(path: Path) -> dict[str, str]:
    """Read a simple KEY=value file. Missing file gives an empty mapping."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw = line.split("=", 1)
        values[key.strip()] = raw.strip().strip('"').strip("'")
    return values


_ENV = _load_env(ENV_PATH)


def _env(key: str, default: str = "") -> str:
    """Environment wins over .env, so a shell override works without editing."""
    return os.environ.get(key, _ENV.get(key, default))


# --------------------------------------------------------------------------
# The recorder
# --------------------------------------------------------------------------
RECORDER_HOST = _env("SWANN_HOST")
RECORDER_USER = _env("SWANN_USER", "admin")
RECORDER_PASS = _env("SWANN_PASS")

CGI_PORT = int(_env("SWANN_WEB_PORT", "85"))
RTSP_PORT = int(_env("SWANN_RTSP_PORT", "554"))
DVRIP_PORT = int(_env("SWANN_DVRIP_PORT", "9000"))

# Only a fallback. The real number of camera sockets comes from the recorder
# itself, in SystemInfo. Set SWANN_CHANNELS if yours is not an 8 socket box.
CHANNEL_COUNT = int(_env("SWANN_CHANNELS", "8"))
# CGI and DVRIP count cameras from 0. RTSP counts from 1.
RTSP_CHANNEL_OFFSET = 1

# ffmpeg and ffprobe. Taken from PATH, so any install works. Set SWANN_FFMPEG
# if you keep it somewhere odd.
FFMPEG_BIN = _env("SWANN_FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
FFPROBE_BIN = _env("SWANN_FFPROBE") or shutil.which("ffprobe") or "ffprobe"


def missing_setup() -> list[str]:
    """Anything that must be set before the app can talk to a recorder."""
    gaps: list[str] = []
    if not RECORDER_HOST:
        gaps.append("SWANN_HOST is not set. Put your recorder's address in .env.")
    if not RECORDER_PASS:
        gaps.append("SWANN_PASS is not set. Put your recorder's password in .env.")
    if shutil.which(FFMPEG_BIN) is None and not Path(FFMPEG_BIN).exists():
        gaps.append(
            "ffmpeg was not found. Install it, for example `brew install ffmpeg`."
        )
    return gaps


# --------------------------------------------------------------------------
# CGI API, port 85
# --------------------------------------------------------------------------
CGI_URL_TEMPLATE = "http://{host}:{port}/cgi-bin/{verb}.cgi"
CGI_CONTENT_TYPE = "application/json"
CGI_TIMEOUT_SECONDS = 15.0
CGI_SEARCH_TIMEOUT_SECONDS = 30.0

# Verbs, read off the recorder's own js/plugin.js CgiClass.
VERB_LOGIN = "login"
VERB_GET_INFO = "getinfo"
VERB_GET_ABILITY = "getability"
VERB_GET_CHANNEL_ABILITY = "getchannelability"
VERB_GET_CONFIG = "getconfig"
VERB_SET_CONFIG = "setconfig"
VERB_OP_DEV = "opdev"
VERB_OP_CONTROL = "opcontrol"
VERB_GET_LOG = "getlog"
VERB_USER_MANAGER = "usermanager"

# Request names used with those verbs.
NAME_GET_SALT = "GetSalt"
NAME_LOGIN = "Login"
NAME_LOGOUT = "Logout"
NAME_KEEP_ALIVE = "KeepAlive"
NAME_SYSTEM_INFO = "SystemInfo"
NAME_STORAGE_INFO = "StorageInfo"
NAME_WORK_STATE = "WorkState"
NAME_SYSTEM_FUNCTION = "SystemFunction"
NAME_CHANNEL_ABILITY = "ChannelSystemFunction"
NAME_ENCODE_CAPABILITY = "EncodeCapability"
# The per camera encoder limits, read as a config, not as an ability.
NAME_DIGITAL_ABILITY = "NetUse.DigitalAbility"
# What a screen puts in its `limits` key to say it reads the encoder
# limits per camera. Only the video quality screen does.
LIMITS_ENCODER = "encoder"
NAME_OP_TIME_QUERY = "OPTimeQuery"

# Device operations, sent with the opdev verb.
NAME_OP_MACHINE = "OPMachine"
NAME_OP_TIME_SETTING = "OPTimeSetting"
NAME_OP_STORAGE_MANAGER = "OPStorageManager"
NAME_OP_DEFAULT_CONFIG = "OPDefaultConfigSwann"
NAME_OP_LOCAL_SEARCH = "OPLocalSearch"
OP_MACHINE_REBOOT = "Reboot"
OP_MACHINE_SHUTDOWN = "Shutdown"
# A factory reset is done one area at a time, not all at once. Read off the
# recorder's own page, rsui/cfg/syswh_mr.js line 10.
RESET_AREAS = (
    {"key": "DisPlay", "title": "Screen", "note": "What the recorder shows on a TV."},
    {"key": "Device", "title": "Cameras", "note": "Picture, sound and camera names."},
    {"key": "Record", "title": "Recording", "note": "What is saved and when."},
    {"key": "Network", "title": "Network", "note": "Its address on your home network."},
    {"key": "Alarm", "title": "Alerts", "note": "Movement, email and alert rules."},
    {"key": "System", "title": "System", "note": "Clock, language and accounts."},
    {"key": "Advanced", "title": "Advanced", "note": "Everything else."},
)
RESET_AREA_KEYS = tuple(area["key"] for area in RESET_AREAS)
# Typed by hand before anything that stops the cameras. Case does not matter.
CONFIRM_RESTART_WORD = "restart"
CONFIRM_RESET_WORD = "reset"
# Screens the plain editor cannot draw. The page checks these by name.
ACTION_LOG = "log"
ACTION_USERS = "users"
ACTION_DANGER = "danger"

# Tests and live control, sent with the opcontrol verb.
NAME_OP_MAIL_TEST = "OPMailTest"
NAME_OP_DDNS_TEST = "OPDDNSTest"
NAME_OP_PTZ_CONTROL = "OPPTZControl"
OP_MAIL_TEST_TIMEOUT_SECONDS = 20.0
OP_DDNS_TEST_TIMEOUT_SECONDS = 15.0

# The device log, sent with the getlog verb. Types read off Dev_log.js line 85.
NAME_OP_LOG_QUERY = "OPLogQuery"
LOG_TYPES = (
    "LogAll",
    "LogSystem",
    "LogConfig",
    "LogStorage",
    "LogAlarm",
    "LogRecord",
    "LogAccount",
)
LOG_TYPE_DEFAULT = "LogAll"
LOG_TYPE_SYSTEM = "LogSystem"
LOG_TYPE_ALARM = "LogAlarm"
LOG_PAGE_SIZE = 128
LOG_MAX_PAGES = 40

# Log row fields.
LOG_KEY_TIME = "Time"
LOG_KEY_TYPE = "Type"
LOG_KEY_DATA = "Data"
LOG_KEY_USER = "User"
LOG_KEY_POSITION = "Position"

# Row types seen on this recorder, counted over a full log sweep.
LOG_TYPE_REBOOT = "Reboot"
LOG_TYPE_SHUTDOWN = "ShutDown"
LOG_EVENT_START = "EventStart"
LOG_EVENT_STOP = "EventStop"

# When the recorder last started. Taken from the newest Reboot row in the log,
# because DeviceRunTime is total running time, not time since the last start.
BOOT_LOOKBACK_DAYS = 30
BOOT_CACHE_SECONDS = 300

# Users, sent with the usermanager verb.
NAME_GET_ALL_USER = "GetAllUser"
NAME_MODIFY_USER = "ModifyUser"
NAME_MODIFY_PASSWORD = "ModifyPassword"
NAME_ADD_USER = "AddUser"
NAME_DELETE_USER = "DelUser"
# The reply from GetAllUser.
USER_LIST_KEY = "Users"
USER_GROUP_KEY = "Groups"
USER_ADMIN_NAME = "admin"
# The recorder writes "Enable" or "Disable" into a field called Memo.
USER_MEMO_ON = "Enable"
USER_MEMO_OFF = "Disable"
# Never send these out of the app. They look scrambled, but the recorder
# logs you in with the scrambled form, so they are as good as a password.
USER_SECRET_FIELDS = frozenset({"Password", "PasswordV2", "NoMD5"})
# The device id the Swann password scrambler needs, and the name it uses.
CONFIG_TUTK = "NetWork.TUTKIOTC"
TUTK_ID_FIELD = "ID"
PASSWORD_ENCRYPT_TYPE = "Swann"

# Firmware, sent with the upgrade verb. Reading the state is safe. Sending an
# image is not, so only the read is wired up.
VERB_UPGRADE = "upgrade"
NAME_UPGRADE_STATUS = "UpgradeStatus"

# Config names proven to answer on this firmware. See PLAN-evidence.md.
CONFIG_RECORD = "Record"
CONFIG_EXT_RECORD = "ExtRecord"
CONFIG_GENERAL = "General.General"
CONFIG_NET_COMMON = "NetWork.NetCommon"
CONFIG_NET_EMAIL = "NetWork.NetEmail"
CONFIG_NET_NAT = "NetWork.Nat"
CONFIG_NET_RTSP = "NetWork.RTSP"
CONFIG_MOTION_DETECT = "Detect.MotionDetect"
CONFIG_STORAGE_POSITION = "Storage.StoragePosition"
CONFIG_CHANNEL_TITLE = "ChannelTitle"
CHANNEL_SUFFIX_TEMPLATE = "{name}.[{channel}]"

# Return codes. The recorder answers with these in a "Ret" field.
RET_OK = 100
RET_RESTART_NEEDED = 150
RET_UNKNOWN_NAME = 101
RET_NO_PERMISSION = 107
RET_SESSION_LOST = 105
RET_FORMAT_ERROR = 117
RET_NO_FILE_FOUND = 119
RET_NOT_SUPPORTED = 136
RET_CONFIG_NOT_FOUND = 607
RET_OK_CODES = (RET_OK, RET_RESTART_NEEDED)

# A write answers 100, or 603 when it needs a reboot to take effect. The
# recorder's own web interface treats both as success. See main.js:1085.
RET_NEED_REBOOT = 603
RET_WRITE_OK_CODES = (RET_OK, RET_RESTART_NEEDED, RET_NEED_REBOOT)


# --------------------------------------------------------------------------
# Backup. Every config name the recorder's own web interface reads or writes,
# taken from its 42 settings screens and then checked one at a time against
# this recorder. See PARITY-evidence.md for the screen by screen table.
# --------------------------------------------------------------------------

# Read whole, with no channel suffix. A per channel config comes back as a
# list of 8, one entry a channel, so there is no need to ask channel by channel.
BACKUP_CONFIG_NAMES = (
    # Display
    "AVEnc.VideoWidget",
    "fVideo.GUISet",
    "fVideo.Tour",
    "fVideo.VideoOut",
    "fVideo.OsdLogo",
    "fVideo.AudioAcquisitionMode",
    "NetUse.EncodeChDisplay",
    # Record and capture
    "Record",
    "Custom.SwannSNAP",
    # Network
    "NetWork.NetCommon",
    "NetWork.NetDHCP",
    "NetWork.NetDNS",
    "NetWork.Nat",
    "NetWork.Wifi",
    "NetWork.RTSP",
    "NetWork.Upnp",
    "NetWork.NetEmail",
    "NetWork.NetEmailExt.DefaultMail",
    "NetWork.NetEmailExt.EmailEncry",
    "NetWork.NetEmailExt.Interval",
    "NetWork.NetEmailExt.SendName",
    "NetWork.NetDDNS",
    "NetWork.NetIPFilterV2",
    "NetWork.NetFTP",
    "NetWork.DropBoxCloud",
    "NetWork.NetNTP",
    "NetWork.ChnStatus",
    "NetWork.RemoteDeviceV3",
    "NetWork.ChnMode",
    # Alarm and analytics
    "Detect.MotionDetect",
    "Detect.LossDetect",
    "Detect.Analyze",
    "Detect.Sound",
    "Detect.HumanDetectionDVR",
    "Detect.CarShapeDetection",
    "Detect.Analyze_Swann_Pid",
    "Detect.Analyze_Swann_Lcd",
    "Detect.Analyze_Swann_Sod",
    "Storage.StorageFailure",
    "Storage.StorageLowSpace",
    # Device and system
    "Uart.PTZ",
    "General.General",
    "General.Location",
    "General.AutoMaintain",
    "General.DstTimeOffset",
    "System.TimeZone",
    "System.ExUserMap",
    "Guide",
    # Swann's own additions on top of stock Xiongmai
    "Custom.SwannSpecialInfo",
    "Custom.SwannSpecialInfo.InfoAlarm",
    "Custom.SwannSpecialInfo.InfoDisplay",
    "Custom.SwannSpecialInfo.InfoRecord",
    "Custom.SwannSpecialInfo.InfoNetwork",
    "Custom.SwannSpecialInfo.InfoDevice",
    "Custom.SwannSpecialInfo.InfoAdvanced",
    "Custom.SwannAutoUpgrade",
    # These two are refused today. They are asked for anyway, so a firmware
    # update that adds them is picked up without editing this list.
    "Alarm.Deterrent",
    "NetWork.NetEmailExt.WorkSheetAbnormal",
)

# These answer only with a channel suffix, so they are read once per channel.
BACKUP_CHANNEL_CONFIG_NAMES = (
    "NetUse.DigitalEncode",
    "NetUse.DigitalAbility",
)

BACKUP_INFO_NAMES = (
    NAME_SYSTEM_INFO,
    NAME_STORAGE_INFO,
    NAME_WORK_STATE,
)

BACKUP_ABILITY_NAMES = (
    NAME_SYSTEM_FUNCTION,
    NAME_ENCODE_CAPABILITY,
)

BACKUP_CHANNEL_ABILITY_NAMES = (NAME_CHANNEL_ABILITY,)

# Names the old web interface uses that this recorder does not have. Each one
# was tried with and without a channel suffix. They are listed so a backup can
# say "expected" instead of "failed". See PARITY-evidence.md section 5.
BACKUP_EXPECTED_MISSING = {
    "AVEnc.Encode": "analogue only, this is a network recorder",
    "Simplify.Encode": "analogue only, this is a network recorder",
    "SnapShot": "analogue only, this is a network recorder",
    "Alarm.Deterrent": "not settled yet, the cameras may have no floodlight",
    "NetWork.NetEmailExt.WorkSheetAbnormal": "not settled yet, may fail in the old web interface too",
}

BACKUP_FILE_FORMAT = "%Y-%m-%d-%H%M%S"
BACKUP_FILE_SUFFIX = ".json"
BACKUP_LATEST_NAME = "latest.json"
BACKUP_JSON_INDENT = 1
BACKUP_PAUSE_SECONDS = 0.05

# The recorder reports AliveInterval 21, which is its timeout, not a send rate.
# Its own web interface sends KeepAlive every 10 seconds, so we match that.
KEEPALIVE_SECONDS = 10
LOGIN_RETRY_LIMIT = 1

# MD5_8, the Sofia hash. Charset read off the recorder's js/md5.js.
MD5_8_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
MD5_8_LENGTH = 8


# --------------------------------------------------------------------------
# DVRIP, port 9000
# --------------------------------------------------------------------------
DVRIP_HEADER_FORMAT = "BB2xII2xHI"
DVRIP_HEADER_LENGTH = 20
DVRIP_MAGIC = 255
DVRIP_VERSION = 0
DVRIP_BODY_TAIL = b"\x0a\x00"
DVRIP_TIMEOUT_SECONDS = 15.0
DVRIP_LOGIN_TYPE = "DVRIP-Web"
DVRIP_ENCRYPT_TYPE = "MD5"
DVRIP_SESSION_TEMPLATE = "0x%08X"

MSG_LOGIN = 1000
MSG_LOGOUT = 1002
MSG_KEEPALIVE = 1006
MSG_SYSTEM_INFO = 1020
MSG_GENERAL = 1042
MSG_TIME_QUERY = 1452
MSG_FILE_QUERY = 1440

# Shared date shape. The recorder uses it for OPTimeQuery both ways.
RECORDER_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# --------------------------------------------------------------------------
# RTSP and ffmpeg
# --------------------------------------------------------------------------
# Proved against this recorder with ffprobe. /live/chNN_S gives both streams,
# where S is 0 for the main one and 1 for the small one. The older /chNN/S
# shape answers too, but it hands back the main stream whatever S is asked for.
RTSP_URL_TEMPLATE = "rtsp://{user}:{password}@{host}:{port}/live/ch{channel:02d}_{stream}"
RTSP_STREAM_MAIN = 0
RTSP_STREAM_EXTRA = 1
RTSP_TRANSPORT = "tcp"

SNAPSHOT_TIMEOUT_SECONDS = 30
SNAPSHOT_QUALITY = 2
SNAPSHOT_NAME_TEMPLATE = "camera-{channel:02d}-{stamp}.jpg"
SNAPSHOT_STAMP_FORMAT = "%Y%m%d-%H%M%S"
# ffmpeg wants microseconds for its socket timeout.
FFMPEG_TIMEOUT_MICROSECONDS = 10_000_000
PROBE_DURATION_SECONDS = 10


# --------------------------------------------------------------------------
# Units. The recorder reports disk sizes in megabytes, as hex strings.
# --------------------------------------------------------------------------
MB_PER_GB = 1024
BYTES_PER_MB = 1024 * 1024
DISK_FULL_FREE_MB = 0

# Time. `DeviceRunTime` counts minutes, not seconds. Read as seconds it says
# 2 days, and the recorder had been on for months.
# Measured twice on the live recorder: 2 ticks over 90 seconds, then 6 ticks
# over 420 seconds. Together that is 8 ticks over 510 seconds, so about 64
# seconds a tick. Close enough to a minute, but not exact, so the uptime is
# rounded to whole months once it passes 30 days.
SECONDS_PER_MINUTE = 60
MINUTES_PER_HOUR = 60
HOURS_PER_DAY = 24
DAYS_PER_MONTH = 30


# --------------------------------------------------------------------------
# Web server
# --------------------------------------------------------------------------
APP_HOST = _env("SWANN_APP_HOST", "127.0.0.1")
APP_PORT = int(_env("SWANN_APP_PORT", "8750"))
APP_TITLE = "Swann"
STATIC_MOUNT = "/static"


# --------------------------------------------------------------------------
# Alerts, step 7
# --------------------------------------------------------------------------
SMTP_LISTEN_HOST = _env("SWANN_SMTP_HOST", "0.0.0.0")
SMTP_LISTEN_PORT = int(_env("SWANN_SMTP_PORT", "2525"))


def rtsp_url(channel: int, stream: int = RTSP_STREAM_MAIN) -> str:
    """Build an RTSP URL for a CGI channel number. Never log the result."""
    from urllib.parse import quote

    return RTSP_URL_TEMPLATE.format(
        user=RECORDER_USER,
        password=quote(RECORDER_PASS, safe=""),
        host=RECORDER_HOST,
        port=RTSP_PORT,
        channel=channel + RTSP_CHANNEL_OFFSET,
        stream=stream,
    )


def playback_url(channel: int, start: str, end: str) -> str:
    """Build a playback RTSP URL. Never log the result, it holds the password.

    `start` and `end` are already in PLAYBACK_TIME_FORMAT, on the recorder's
    own clock. See the playback notes above.
    """
    from urllib.parse import quote

    return PLAYBACK_URL_TEMPLATE.format(
        user=RECORDER_USER,
        password=quote(RECORDER_PASS, safe=""),
        host=RECORDER_HOST,
        port=RTSP_PORT,
        channel=channel + PLAYBACK_CHANNEL_OFFSET,
        start=start,
        end=end,
        stream=PLAYBACK_STREAM,
    )


def channel_config_name(name: str, channel: int) -> str:
    """Per-channel config names take a .[N] suffix, as in Name.[0]."""
    return CHANNEL_SUFFIX_TEMPLATE.format(name=name, channel=channel)


def ensure_dirs() -> None:
    """Make the folders the app writes into."""
    for path in (DATA_DIR, MEDIA_DIR, SNAPSHOT_DIR, BACKUP_DIR):
        path.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------
# Settings screens. One entry per screen in the recorder's own web interface,
# taken from its config_c7.html and then checked against this recorder.
# See PARITY-evidence.md for the screen by screen table.
#
# key          the url and id for the screen
# group        which heading it sits under
# title        what the person sees
# configs      config names it reads and writes, in order
# info         getinfo names it reads, which are never written
# note         one plain line shown under the title, or ""
# read_only    true when the screen shows facts and changes nothing
# action       a special screen the generic editor cannot draw
# --------------------------------------------------------------------------
# On a phone the settings menu is over 1,600 pixels tall, so it buries every
# screen below it. There it folds shut, and this is the word on the fold.
SETTINGS_MENU_LABEL = "Choose a screen"

SETTINGS_GROUPS = (
    "Cameras",
    "Recording",
    "Alerts",
    "Network",
    "Storage",
    "System",
    "Advanced",
)

SETTINGS_SCREENS = (
    # -- Cameras ----------------------------------------------------------
    {
        "key": "cameras",
        "group": "Cameras",
        "title": "Cameras",
        "note": "Which socket holds which camera, and how each one connects.",
        "configs": ("NetWork.ChnStatus", "NetWork.RemoteDeviceV3"),
    },
    {
        "key": "overlay",
        "group": "Cameras",
        "title": "On screen text",
        # Tested on the live recorder on 2026-11-08: the clock was dragged,
        # saved and read back, and the picture did not change. These are
        # network cameras, so each camera burns its own name and clock into
        # the picture. The recorder keeps these numbers but does not use them.
        "note": (
            "Drag the camera name and the clock to where you want them. "
            "Warning: on these cameras the recorder saves this but the "
            "picture does not change. Each camera draws its own name and "
            "clock. Change it on the camera itself."
        ),
        "configs": ("AVEnc.VideoWidget", "fVideo.OsdLogo"),
        "editor": "overlay",
    },
    {
        "key": "privacy",
        "group": "Cameras",
        "title": "Privacy blocks",
        "note": "Drag black boxes over anything the recording should not show.",
        "configs": ("AVEnc.VideoWidget",),
        "editor": "privacy",
    },
    {
        "key": "monitor",
        "group": "Cameras",
        "title": "Recorder's own screen",
        "note": "The layout on the monitor plugged into the recorder, not this page.",
        "configs": ("fVideo.GUISet", "fVideo.Tour", "fVideo.VideoOut"),
        "editor": "tour",
    },
    # -- Recording --------------------------------------------------------
    {
        "key": "recording",
        "group": "Recording",
        "title": "Recording and schedule",
        "note": "Drag across the week to say when each camera saves video.",
        "configs": ("Record", "ExtRecord", "Custom.SwannSpecialInfo.InfoRecord"),
        "editor": "week",
    },
    {
        "key": "quality",
        "group": "Recording",
        "title": "Video quality",
        "note": "Resolution, frame rate and bit rate, for the main and the second stream.",
        "configs": ("NetUse.DigitalEncode",),
        "per_channel": True,
        # This is the only screen the recorder states real limits for, so it
        # also reads each camera's ability reply and builds its dropdowns
        # from that. See `swann/limits.py`.
        "limits": LIMITS_ENCODER,
    },
    {
        "key": "quality-limits",
        "group": "Recording",
        "title": "What the cameras allow",
        "note": (
            "What each camera's encoder will take. The video quality screen "
            "already uses these numbers to build its dropdowns, so you do not "
            "have to read them. Most are packed, meaning one number holds a "
            "yes or no for every picture size at once. Read only."
        ),
        "configs": ("NetUse.DigitalAbility",),
        "per_channel": True,
        "read_only": True,
    },
    {
        "key": "stills",
        "group": "Recording",
        "title": "Still pictures",
        "note": "Drag across the week to say when the recorder saves snapshots.",
        "configs": ("Custom.SwannSNAP",),
        "editor": "week",
    },
    # -- Alerts -----------------------------------------------------------
    {
        "key": "motion",
        "group": "Alerts",
        "title": "Movement",
        "note": "Brush the parts of the picture the camera should watch.",
        "configs": ("Detect.MotionDetect", "Custom.SwannSpecialInfo.InfoAlarm"),
        "editor": "motion",
    },
    {
        "key": "people",
        "group": "Alerts",
        "title": "People and vehicles",
        "note": "Smarter detection that tells a person or a car from a moving branch.",
        "configs": ("Detect.HumanDetectionDVR", "Detect.CarShapeDetection"),
    },
    {
        "key": "sound",
        "group": "Alerts",
        "title": "Sound",
        "note": "Alerts when a camera hears something loud or sudden.",
        "configs": ("Detect.Sound",),
    },
    {
        "key": "area",
        "group": "Alerts",
        "title": "Area intrusion",
        "note": "Draw up to four shapes. The camera tells you when something goes in.",
        "configs": ("Detect.Analyze_Swann_Pid",),
        "editor": "shape",
    },
    {
        "key": "line",
        "group": "Alerts",
        "title": "Line crossing",
        "note": "Draw up to four lines. The camera tells you when something crosses one.",
        "configs": ("Detect.Analyze_Swann_Lcd",),
        "editor": "line",
    },
    {
        "key": "objects",
        "group": "Alerts",
        "title": "Objects left or taken",
        "note": "Draw up to four shapes. The camera watches for things left or taken.",
        "configs": ("Detect.Analyze_Swann_Sod",),
        "editor": "shape",
    },
    {
        "key": "analytics-schedule",
        "group": "Alerts",
        "title": "Smart alerts, shared settings",
        "note": (
            "The settings the three smart alert screens share. This recorder keeps "
            "no clock for them, so there are no hours to set here."
        ),
        "configs": ("Detect.Analyze",),
    },
    {
        "key": "deterrent",
        "group": "Alerts",
        "title": "Light and siren",
        "note": "The camera's floodlight and siren. Empty here, so these cameras may have none.",
        "configs": ("Alarm.Deterrent",),
    },
    {
        "key": "faults",
        "group": "Alerts",
        "title": "Fault warnings",
        "note": "Warnings about a lost camera or a disk problem.",
        "configs": (
            "Detect.LossDetect",
            "Storage.StorageFailure",
            "Storage.StorageLowSpace",
        ),
    },
    # -- Network ----------------------------------------------------------
    {
        "key": "network",
        "group": "Network",
        "title": "Network",
        "note": "The recorder's address on your home network. Get this wrong and the page stops loading.",
        "configs": (
            "NetWork.NetCommon",
            "NetWork.NetDHCP",
            "NetWork.NetDNS",
            "NetWork.Nat",
        ),
    },
    {
        "key": "ports",
        "group": "Network",
        "title": "Ports and streaming",
        "note": "Which doors the recorder keeps open, including the video stream.",
        "configs": ("NetWork.RTSP", "NetWork.Upnp"),
    },
    {
        "key": "wifi",
        "group": "Network",
        "title": "Wi-Fi",
        "note": "Only used if the recorder has a wireless adapter fitted.",
        "configs": ("NetWork.Wifi",),
    },
    {
        "key": "email",
        "group": "Network",
        "title": "Email",
        "note": "Where the recorder sends alert emails.",
        "configs": (
            "NetWork.NetEmail",
            "NetWork.NetEmailExt.DefaultMail",
            "NetWork.NetEmailExt.EmailEncry",
            "NetWork.NetEmailExt.Interval",
            "NetWork.NetEmailExt.SendName",
        ),
    },
    {
        "key": "ddns",
        "group": "Network",
        "title": "Dynamic DNS",
        "note": "Gives the recorder a fixed name even when your home address changes.",
        "configs": ("NetWork.NetDDNS",),
    },
    {
        "key": "ip-filter",
        "group": "Network",
        "title": "Allowed and blocked addresses",
        "note": "Which addresses may reach the recorder.",
        "configs": ("NetWork.NetIPFilterV2",),
    },
    {
        "key": "ftp",
        "group": "Network",
        "title": "FTP upload",
        "note": "Sends clips to a server of your own.",
        "configs": ("NetWork.NetFTP",),
    },
    {
        "key": "cloud",
        "group": "Network",
        "title": "Cloud storage",
        "note": "Sends clips to Dropbox.",
        "configs": ("NetWork.DropBoxCloud",),
    },
    {
        "key": "network-state",
        "group": "Network",
        "title": "Network state",
        "note": "What the recorder thinks its network looks like right now. Read only.",
        "configs": (
            "NetWork.NetCommon",
            "NetWork.NetDHCP",
            "NetWork.NetDNS",
            "NetWork.RTSP",
            "NetWork.Upnp",
        ),
        "read_only": True,
    },
    # -- Storage ----------------------------------------------------------
    {
        "key": "disk",
        "group": "Storage",
        "title": "Disk",
        "note": "The disk inside the recorder and how full it is.",
        "configs": ("General.General",),
        "info": ("StorageInfo",),
    },
    {
        "key": "log",
        "group": "Storage",
        "title": "Event log",
        "note": "Everything the recorder has written down. About two and a half days of it.",
        "configs": (),
        "action": "log",
        "read_only": True,
    },
    # -- System -----------------------------------------------------------
    {
        "key": "general",
        "group": "System",
        "title": "General",
        "note": "Name, language, video standard and the recorder's own menu.",
        "configs": (
            "General.General",
            "General.Location",
            "fVideo.AudioAcquisitionMode",
            "NetWork.ChnMode",
        ),
    },
    {
        "key": "clock",
        "group": "System",
        "title": "Date and time",
        "note": "The recorder's clock, the time zone and summer time.",
        "configs": (
            "General.Location",
            "General.DstTimeOffset",
            "System.TimeZone",
            "NetWork.NetNTP",
        ),
    },
    {
        "key": "users",
        "group": "System",
        "title": "Users",
        "note": "Accounts that may log in, and what each one is allowed to do.",
        "configs": ("System.ExUserMap",),
        "action": "users",
    },
    {
        "key": "camera-settings",
        "group": "System",
        "title": "Camera details",
        "note": "What each camera reports about itself. Read only.",
        "configs": ("NetWork.ChnStatus", "NetWork.RemoteDeviceV3"),
        "read_only": True,
    },
    {
        "key": "information",
        "group": "System",
        "title": "Recorder information",
        "note": "Model, firmware and serial number. Read only.",
        "configs": ("General.Location",),
        "info": ("SystemInfo", "StorageInfo"),
        "read_only": True,
    },
    {
        "key": "abilities",
        "group": "System",
        "title": "What this recorder supports",
        "note": (
            "Every feature the firmware says it has. A name starting "
            "`AnalogCap` is for the old camera sockets this recorder does not "
            "have, and `DigitalCap` is for network cameras, which is what is "
            "plugged in. Read only."
        ),
        "configs": (),
        "ability": ("SystemFunction", "EncodeCapability"),
        "read_only": True,
    },
    # -- Advanced ---------------------------------------------------------
    {
        "key": "ptz",
        "group": "Advanced",
        "title": "Camera movement",
        "note": "Settings for cameras that pan, tilt or zoom.",
        "configs": ("Uart.PTZ",),
    },
    {
        "key": "maintain",
        "group": "Advanced",
        "title": "Automatic restart",
        "note": "The recorder restarts itself on this day each week.",
        "configs": ("General.AutoMaintain",),
    },
    {
        "key": "auto-upgrade",
        "group": "Advanced",
        "title": "Automatic firmware update",
        "note": "Whether the recorder updates its own firmware.",
        "configs": ("Custom.SwannAutoUpgrade",),
    },
    {
        "key": "swann-extras",
        "group": "Advanced",
        "title": "Swann's own settings",
        "note": "Settings Swann added on top of the standard firmware.",
        "configs": (
            "Custom.SwannSpecialInfo",
            "Custom.SwannSpecialInfo.InfoAlarm",
            "Custom.SwannSpecialInfo.InfoDisplay",
            "Custom.SwannSpecialInfo.InfoRecord",
            "Custom.SwannSpecialInfo.InfoNetwork",
            "Custom.SwannSpecialInfo.InfoDevice",
            "Custom.SwannSpecialInfo.InfoAdvanced",
        ),
    },
    {
        "key": "setup-wizard",
        "group": "Advanced",
        "title": "Setup wizard",
        "note": "Whether the recorder shows its first time wizard.",
        "configs": ("Guide",),
    },
    {
        "key": "danger",
        "group": "Advanced",
        "title": "Restart and reset",
        "note": "Restart the recorder, or put every setting back to factory.",
        "configs": (),
        "action": "danger",
    },
)


# --------------------------------------------------------------------------
# Field labels and hints for the settings editor. A name not listed here is
# turned into words automatically, so this list is only for the ones where
# that reads badly or where a plain English hint helps.
# --------------------------------------------------------------------------
FIELD_TRUE_WORDS = ("1", "true", "yes", "on")
# A list this long is one entry per camera socket. The recorder pads some of
# them well past the 8 sockets it has: ChnStatus answers 32 and Uart.PTZ 64.
FIELD_CHANNEL_LENGTHS = (CHANNEL_COUNT, 16, 32, 64)
FIELD_HEX_NOTE = "A packed number the recorder writes in hex. Change it only if you know the layout."

FIELD_LABELS = {
    "AutoLogout": "Log the recorder's own menu out after",
    "AutoRebootDay": "Restart itself on",
    "AutoRebootHour": "Restart itself at",
    "AutoDeleteFilesDays": "Delete clips older than",
    "BandWidthTips": "Warn about bandwidth",
    "DSTEnd": "Summer time ends",
    "DSTStart": "Summer time begins",
    "DstTimeOffset": "Summer time shift",
    "EmailEncry": "Email encryption",
    "ExtraFormat": "Second stream, the smaller one",
    "FontSize": "Text size on the recorder's screen",
    "HddNum": "Number of disks",
    "MachineName": "Recorder name",
    "MainFormat": "Main stream, the recording one",
    "OverWrite": "When the disk is full",
    "RebootNum": "Restarts counted",
    "ScreenAutoShutdown": "Turn the recorder's screen off after",
    "ScreenSaveTime": "Screen saver after",
    "SendName": "Name on alert emails",
    "VideoOutPut": "Video output",
    "Recievers": "Send alerts to",
    "SendAddr": "Send alerts from",
    "MailServer": "Outgoing mail server",
    "UseSSL": "Use a secure connection",
    "DigitalEncode": "Video quality",
    "DigitalAbility": "What the camera allows",
    "ChnStatus": "Camera sockets",
    "RemoteDeviceV3": "Connected cameras",
    "NetIPFilterV2": "Address filter",
    "DropBoxCloud": "Dropbox",
    "NetNTP": "Internet time server",
    "NetDDNS": "Dynamic DNS",
    "NetFTP": "FTP upload",
    "Nat": "Swann cloud and remote access",
    "Upnp": "Automatic router setup",
    "RTSP": "Video streaming",
    "GUISet": "Recorder's own screen",
    "OsdLogo": "Logo on the picture",
    "AudioAcquisitionMode": "Microphone mode",
    "ChnMode": "Camera socket mode",
    "ExUserMap": "Account permissions",
    "TimeZone": "Time zone",
    "AutoMaintain": "Automatic restart",
    "SwannAutoUpgrade": "Automatic firmware update",
    "LossDetect": "Camera lost",
    "StorageFailure": "Disk failed",
    "StorageLowSpace": "Disk nearly full",
    "MotionDetect": "Movement detection",
    "HumanDetectionDVR": "Person detection",
    "CarShapeDetection": "Vehicle detection",
    "Analyze_Swann_Pid": "Area intrusion",
    "Analyze_Swann_Lcd": "Line crossing",
    "Analyze_Swann_Sod": "Object left or taken",
    "VideoWidget": "On screen text and privacy blocks",
    "SwannSNAP": "Still pictures",
    "ChnName": "Name",
    "CurRes": "Resolution now",
    "MaxRes": "Highest it can do",
    "Status": "Connection",
    "Enable": "Switched on",
    "HostIP": "Recorder address",
    "GateWay": "Router address",
    "Submask": "Subnet mask",
    "HttpPort": "Web page port",
    "TCPPort": "App port",
    "SSLPort": "Secure port",
    "MaxBps": "Bit rate limit",
    "FPS": "Frames a second",
    "Quality": "Picture quality",
    "Resolution": "Picture size",
    "GOP": "Keyframe gap",
    "Compression": "Video format",
    "AudioEnable": "Record sound",
    "VideoEnable": "Record video",
    "BitRateControl": "Bit rate mode",
}

# --------------------------------------------------------------------------
# The field guide.
#
# A number on its own says nothing. This table says what a setting does, what
# it is counted in, and how high it may go. `field_guide()` looks one up.
#
# A key is tried three ways, most exact first:
#   "Detect.MotionDetect/Level"       the config and the whole path
#   "Detect.MotionDetect/EventLatch"  the config and the last part of the path
#   "EventLatch"                      the last part on its own
# That matters because `Enable` is on 23 screens and `Port` on 10, and they do
# not mean the same thing on each.
#
# Each entry may hold:
#   help     one plain sentence, shown in the info panel
#   unit     what it is counted in, shown after the box
#   min/max  the limits. BOTH must be set for a limit to be used at all
#   step     how far apart the allowed values are, 1 if left out
#   choices  a fixed list of (value, title) pairs, which wins over min and max
#   source   where the limit came from, shown at the bottom of the panel
#
# TWO TIERS, and this is the whole safety rule:
#   Proven    the recorder reports the limit, or Swann's own page states it and
#             the live values agree. The control enforces it.
#   Not proven  `help` may say the usual range, but `min` and `max` are left
#             out, so the box stays free and nothing is clamped on a guess.
# This recorder answers Ret 100 to writes it then ignores, so a value quietly
# clamped to a wrong guess is worse than one the recorder refuses out loud.
# See FIELD-GUIDE-evidence.md.
# --------------------------------------------------------------------------

# Over this many steps a dropdown stops helping and a number box is better.
FIELD_CHOICE_LIMIT = 24

SOURCE_RECORDER = "The recorder reports this limit itself."
SOURCE_SWANN = "Read off Swann's own web page for this recorder."
SOURCE_PLAIN = "Not a recorder limit. This is just how counting works."
SOURCE_USUAL = "The recorder does not state a limit, so the box is not capped."

# A limit may only be used when its source says it was proven. SOURCE_USUAL
# means the opposite, so an entry that holds both is a contradiction and
# `_check_guide()` below stops the file loading.
SOURCE_PROVEN = (SOURCE_RECORDER, SOURCE_SWANN, SOURCE_PLAIN)

# Shared by every alert screen: movement, people, vehicles, sound, the three
# smart ones and the two fault ones. Same fields, same meaning on each.
_ALERT_GUIDE = {
    "Enable": {"help": "Turn this kind of alert on or off for this camera."},
    "AlarmOutEnable": {
        "help": "Close the recorder's alarm contacts when this happens. "
                "Nothing is wired to them here.",
    },
    "AlarmOutLatch": {
        "help": "How long the alarm contacts stay closed after the event.",
        "unit": "seconds",
    },
    "BeepEnable": {"help": "Make the recorder itself beep."},
    "EventLatch": {
        "help": "How long the recorder waits before it counts the same thing "
                "as a new event. Raise it to get fewer repeats.",
        "unit": "seconds",
    },
    "FTPEnable": {"help": "Upload the clip to an FTP server. Not set up here."},
    "LogEnable": {
        "help": "Write the event to the recorder's log. This app copies that "
                "log, so leave it on or the alert list goes empty.",
    },
    "MailEnable": {"help": "Send an email. Needs the email screen filled in."},
    "MessageEnable": {"help": "Send a push message to the Swann app."},
    "RecordEnable": {"help": "Save video when this happens."},
    "RecordLatch": {
        "help": "How long the recorder keeps saving after the event stops.",
        "unit": "seconds",
    },
    "SnapEnable": {"help": "Save a still picture as well as video."},
    "ShowInfo": {"help": "Draw a message on the recorder's own screen."},
    "TipEnable": {"help": "Show a warning box on the recorder's own screen."},
    "TourEnable": {
        "help": "Switch the recorder's own screen to this camera when it happens.",
    },
    "VoiceEnable": {"help": "Play a spoken warning out of the camera."},
    "VoiceTipInterval": {
        "help": "How long to wait before the spoken warning may play again.",
        "unit": "seconds",
    },
    "PtzEnable": {
        "help": "Move a motorised camera to a saved position. No camera here moves.",
    },
    "MatrixEnable": {"help": "Switch a second monitor to this camera."},
    "MsgtoNetEnable": {"help": "Tell any app that is watching."},
    "MultimediaMsgEnable": {"help": "Send a picture message. Needs a phone line."},
    "ShortMsgEnable": {"help": "Send a text message. Needs a phone line."},
    "MailManuEnable": {"help": "Attach the still picture to the email."},
    "AlarmInfo": {"help": "Your own wording for this alert. Usually left empty."},
    "VoiceType": {
        "help": "Which spoken warning to play. The recorder holds a numbered "
                "list of them and this picks one.",
    },
    "AlarmOutMask": {
        "help": "Which alarm contacts to close, packed into one number. "
                "Nothing is wired to them here.",
    },
    "MatrixMask": {
        "help": "Which second monitors to switch, packed into one number.",
    },
    "ShowInfoMask": {
        "help": "Which cameras show the message on the recorder's own screen, "
                "packed into one number.",
    },
    "SnapShotMask": {
        "help": "Which cameras take a still picture, packed into one number.",
    },
    "TourMask": {
        "help": "Which cameras the recorder's own screen switches to, packed "
                "into one number.",
    },
}

# The smart alert screens add these on top of the shared set.
_SMART_GUIDE = {
    "TypeHuman": {
        "help": "Count people. 1 is on and 0 is off.",
    },
    "TypeVehicle": {
        "help": "Count vehicles. 1 is on and 0 is off.",
    },
    "MinDist": {
        "help": "How far a thing must move before it counts. Bigger means fewer "
                "false alarms and more missed ones.",
    },
    "MinTime": {
        "help": "How long a thing must stay in the area before it counts.",
        "unit": "seconds",
    },
    "ShowRule": {
        "help": "Draw the area or line on the recorder's own screen.",
        "choices": ((0, "No"), (1, "Yes")),
        "source": SOURCE_SWANN,
    },
    "ShowTrack": {
        "help": "Draw a box around what it is following.",
        "choices": ((0, "No"), (1, "Yes")),
        "source": SOURCE_SWANN,
    },
    "PointNum": {"help": "How many corners the drawn area has. The drawing sets this."},
    "Valid": {"help": "Whether this rule is in use. The drawing sets this."},
    "Mode": {"help": "Which rule shape this is. The drawing sets this."},
    "x": {
        "help": "One corner's sideways position. The picture is 0 to 8192 "
                "across, whatever its real size. The drawing sets this.",
    },
    "y": {
        "help": "One corner's up and down position. The picture is 0 to 8192 "
                "down, whatever its real size. The drawing sets this.",
    },
}

FIELD_GUIDE: dict[str, dict[str, object]] = {
    # -- recording ---------------------------------------------------------
    "Record/PacketLength": {
        "help": "How long one saved video file is. Longer files mean fewer "
                "files on the disk. It does not change how much is recorded.",
        "unit": "minutes",
        "source": SOURCE_USUAL,
    },
    "Record/PreRecord": {
        "help": "How many seconds before the movement the recorder keeps. It "
                "always holds a few seconds in memory, so it can go back a little.",
        "unit": "seconds",
        "source": SOURCE_USUAL,
    },
    "Record/RecordMode": {
        "help": "Follow the week grid, or stop recording on this camera.",
        "choices": (("ConfigRecord", "Follow the week grid"),
                    ("ClosedRecord", "Do not record")),
        "source": SOURCE_SWANN,
    },
    "Record/Redundancy": {
        "help": "Write a second copy to a backup disk. This recorder has one disk.",
    },
    "RecordMask": {
        "help": "Which cameras this applies to, packed into one number. "
                "One bit per camera.",
    },
    # -- video quality -----------------------------------------------------
    "FPS": {
        "help": "How many pictures a second the camera sends. Lower uses less "
                "disk. Below about 10 movement starts to look jumpy.",
        "unit": "pictures a second",
    },
    "GOP": {
        "help": "How many pictures pass between full ones. A lower number "
                "makes the video easier to jump about in and bigger on disk.",
        "unit": "pictures",
    },
    "Quality": {
        "help": "Picture quality. 1 is the worst and higher is better. Only "
                "used when the bit rate mode is VBR.",
    },
    "BitRateControl": {
        "help": "VBR spends more data on busy pictures and less on still ones. "
                "CBR uses the same amount all the time.",
        "choices": (("VBR", "VBR, varies with the picture"),
                    ("CBR", "CBR, always the same")),
        "source": SOURCE_SWANN,
    },
    "NetUse.DigitalEncode/Video/BitRate": {
        "help": "How much data a second this stream uses. Higher is a cleaner "
                "picture and a fuller disk.",
        "unit": "kbit/s",
    },
    "NetUse.DigitalEncode/Audio/BitRate": {
        "help": "How much data a second the sound uses. 0 means the camera "
                "decides, which is what both cameras here do.",
        "unit": "kbit/s",
    },
    "Compression": {
        "help": "How the video is squashed. H.265 makes a smaller file than "
                "H.264 for the same picture, so more fits on the disk. Some "
                "older players cannot read H.265.",
    },
    "Resolution": {
        "help": "How big the picture is. Bigger is sharper and fills the disk "
                "faster. The main stream is what gets recorded. The second "
                "stream is small, for watching on a phone.",
    },
    "NetUse.DigitalEncode/MainFormat": {
        "help": "The big picture. This is what gets recorded and what you see "
                "full screen.",
    },
    "NetUse.DigitalEncode/ExtraFormat": {
        "help": "The small picture, sent alongside the big one. The grid and "
                "the phone app use it, because it needs far less network.",
    },
    "NetUse.DigitalEncode/SnapFormat": {
        "help": "The settings for a still picture, which is saved as a JPEG.",
    },
    "NetUse.DigitalEncode/MaxVolume": {
        "help": "Microphone loudness. 0 means the camera decides.",
    },
    "NetUse.DigitalEncode/SampleRate": {
        "help": "Sound sample rate. 0 means the camera decides.",
    },
    "AudioEnable": {"help": "Record sound as well as picture on this stream."},
    "VideoEnable": {"help": "Record this stream at all."},
    "NetUse.DigitalEncode/OSD": {
        "help": "Burn the camera name and clock into this stream. These cameras "
                "draw their own anyway, so this changes nothing here.",
    },
    # -- still pictures ----------------------------------------------------
    "Custom.SwannSNAP/AutoEn": {
        "help": "Save a still picture on a timer as well as on an alert.",
    },
    "Custom.SwannSNAP/StreamMode": {
        "help": "Which stream the still comes from. 0 is the main one.",
    },
    # -- general -----------------------------------------------------------
    "General.General/AutoLogout": {
        "help": "How long the recorder's own menu waits before it logs itself "
                "out. 0 means never.",
        "unit": "minutes",
        "source": SOURCE_USUAL,
    },
    "General.General/BandWidthTips": {
        "help": "Warn on the recorder's screen when the cameras ask for more "
                "data than it can take. 1 is on and 0 is off.",
    },
    "General.General/FontSize": {
        "help": "How big the text is on the recorder's own screen, in pixels.",
        "unit": "pixels",
        "source": SOURCE_USUAL,
    },
    "General.General/HddNum": {"help": "How many disks the recorder expects."},
    "General.General/MachineName": {
        "help": "What the recorder calls itself on your home network.",
    },
    "General.General/RebootNum": {"help": "How many times it has restarted."},
    "General.General/ScreenAutoShutdown": {
        "help": "Turn the recorder's own screen off after this long with "
                "nobody touching it. 0 means never.",
        "unit": "minutes",
        "source": SOURCE_USUAL,
    },
    "General.General/ScreenSaveTime": {
        "help": "Start the screen saver after this long. 0 means never.",
        "unit": "minutes",
        "source": SOURCE_USUAL,
    },
    "General.General/LocalNo": {
        "help": "The recorder's number for a remote control. Leave it at 0.",
    },
    "OverWrite": {
        "help": "The disk is full. `OverWrite` writes over the oldest video and "
                "`StopRecord` stops recording. Leave it on `OverWrite`.",
    },
    "VideoOutPut": {
        "help": "Which socket the recorder sends its own picture to. `Auto` "
                "lets it choose. `HDMI` and `VGA` are the two it has.",
    },
    "General.General/IranCalendarEnable": {
        "help": "Use the Iranian calendar. Leave it off.",
    },
    # -- date and time -----------------------------------------------------
    "General.Location/DateFormat": {
        "help": "The order of day, month and year on screen.",
        "choices": (("DDMMYY", "Day month year"),
                    ("MMDDYY", "Month day year"),
                    ("YYMMDD", "Year month day")),
        "source": SOURCE_SWANN,
    },
    "General.Location/TimeFormat": {
        "help": "A 24 hour clock, or am and pm.",
        "choices": (("24", "24 hour"), ("12", "12 hour")),
        "source": SOURCE_SWANN,
    },
    "General.Location/DSTRule": {
        "help": "Follow summer time.",
        "choices": (("On", "On"), ("Off", "Off")),
        "source": SOURCE_SWANN,
    },
    "General.Location/DateSeparator": {
        "help": "The mark between day, month and year. This recorder uses a "
                "slash.",
    },
    "General.Location/VideoFormat": {
        "help": "`PAL` is the UK one and allows up to 25 pictures a second. "
                "`NTSC` allows 30. Changing it restarts the recorder.",
    },
    "General.Location/WorkDay": {
        "help": "Which days count as work days, packed into one number.",
    },
    "General.Location/Year": {"help": "The year summer time starts. 0 means every year."},
    "General.Location/Month": {"help": "The month summer time starts.", "min": 1, "max": 12,
                               "source": SOURCE_PLAIN},
    "General.Location/Hour": {"help": "The hour summer time starts.", "min": 0, "max": 23,
                              "source": SOURCE_PLAIN},
    "General.Location/Minute": {"help": "The minute summer time starts.", "min": 0, "max": 59,
                                "source": SOURCE_PLAIN},
    "General.DstTimeOffset/OffsetTime": {
        "help": "How far the clock moves for summer time. The UK uses 60.",
        "unit": "minutes",
        "source": SOURCE_USUAL,
    },
    "NetWork.NetNTP/Enable": {
        "help": "Set the clock from the internet. Leave this on or the clock drifts.",
    },
    "NetWork.NetNTP/Name": {"help": "Which time server to ask. pool.ntp.org is fine."},
    "NetWork.NetNTP/Port": {
        "help": "The port for the time server. 123 is the standard one.",
        "min": 1,
        "max": 65535,
        "source": SOURCE_PLAIN,
    },
    "NetWork.NetNTP/UpdatePeriod": {
        "help": "How often to ask the time server.",
        "unit": "minutes",
        "source": SOURCE_USUAL,
    },
    "NetWork.NetNTP/TimeZone": {
        "help": "The recorder's own number for the time zone, not the hours "
                "offset. 13 is UK time on this firmware.",
    },
    # -- network -----------------------------------------------------------
    "HostIP": {
        "help": "The recorder's address on your home network. Change this and "
                "this app stops finding it until you use the new one.",
    },
    "GateWay": {"help": "Your router's address."},
    "Submask": {"help": "Which part of the address is your home network."},
    "NetWork.NetCommon/HttpPort": {
        "help": "The port the recorder's settings answer on. This app uses 85.",
        "min": 1,
        "max": 65535,
        "source": SOURCE_PLAIN,
    },
    "NetWork.NetCommon/TCPPort": {
        "help": "The port the Swann app talks to. 9000 here.",
        "min": 1,
        "max": 65535,
        "source": SOURCE_PLAIN,
    },
    "NetWork.NetCommon/SSLPort": {
        "help": "The secure port.",
        "min": 1,
        "max": 65535,
        "source": SOURCE_PLAIN,
    },
    "NetWork.NetCommon/UDPPort": {
        "help": "The port the Swann app uses to find the recorder.",
        "min": 1,
        "max": 65535,
        "source": SOURCE_PLAIN,
    },
    "NetWork.NetCommon/MaxBps": {
        "help": "Cap how much data the recorder sends out. 0 means no cap.",
        "unit": "kbit/s",
        "source": SOURCE_USUAL,
    },
    "NetWork.NetCommon/TCPMaxConn": {
        "help": "How many apps may watch at once.",
        "source": SOURCE_USUAL,
    },
    "NetWork.NetCommon/TransferPlan": {
        "help": "What to give up when the network is slow. `Quality` keeps the "
                "picture sharp, `Fluency` keeps it smooth and `Adaptive` "
                "decides on its own.",
    },
    "NetWork.NetCommon/MonMode": {
        "help": "How a watching app connects. `TCP` is the reliable one and "
                "what this recorder uses.",
    },
    "NetWork.NetDHCP/Enable": {
        "help": "Let the router hand out the recorder's address. Turning this "
                "off means typing one in by hand.",
    },
    "NetWork.Nat/NatEnable": {
        "help": "Let the Swann cloud reach this recorder from outside your home. "
                "Turn it off if you only ever use it on your own network.",
    },
    "NetWork.Nat/Port": {"help": "The port the Swann cloud uses."},
    "NetWork.Nat/XMeyeMTU": {
        "help": "The biggest packet the cloud link sends. 1500 is normal.",
        "source": SOURCE_USUAL,
    },
    # -- ports and streaming ----------------------------------------------
    "NetWork.RTSP/Port": {
        "help": "The port live and old video stream on. This app uses 554.",
        "min": 1,
        "max": 65535,
        "source": SOURCE_PLAIN,
    },
    "NetWork.RTSP/Anonymity": {
        "help": "Let anything on your network watch without a password. "
                "Leave it off.",
    },
    "NetWork.RTSP/IsServer": {
        "help": "Hand out video to other apps. This app needs it on.",
    },
    "NetWork.Upnp/Enable": {
        "help": "Ask the router to open ports on its own. Safer left off.",
    },
    "NetWork.Upnp/HTTPPort": {"help": "The outside port for the settings. 0 means none."},
    "NetWork.Upnp/MediaPort": {"help": "The outside port for video. 0 means none."},
    "NetWork.Upnp/MobilePort": {"help": "The outside port for the phone app. 0 means none."},
    # -- email -------------------------------------------------------------
    "NetWork.NetEmail/Enable": {"help": "Send an email when something happens."},
    "NetWork.NetEmail/Name": {
        "help": "Your email provider's outgoing server, such as smtp.gmail.com.",
    },
    "NetWork.NetEmail/Port": {
        "help": "The outgoing mail port. 587 for STARTTLS, 465 for SSL, 25 plain.",
        "min": 1,
        "max": 65535,
        "source": SOURCE_PLAIN,
    },
    "NetWork.NetEmail/UseSSL": {
        "help": "How the email is encrypted. 0 is none, 1 is SSL, 2 is TLS and "
                "3 is STARTTLS. Gmail on port 587 wants 3.",
        "source": SOURCE_USUAL,
    },
    "NetWork.NetEmail/Title": {"help": "The subject line on every alert email."},
    "NetWork.NetEmail/Anonymity": {"help": "Send without signing in. Almost never works."},
    "NetWork.NetEmailExt.Interval": {
        "help": "The shortest gap between two alert emails. It stops a busy "
                "night filling your inbox.",
        "unit": "minutes",
        "source": SOURCE_USUAL,
    },
    "Recievers": {
        "help": "Who gets the alert emails. The recorder spells this without "
                "the second c. That is its spelling, not a mistake here.",
    },
    "SendAddr": {"help": "The address the alerts come from."},
    # -- disk --------------------------------------------------------------
    "AutoDeleteFilesDays": {
        "help": "Delete clips older than this many days. 0 means never, and "
                "the disk writes over the oldest video instead.",
        "unit": "days",
        "source": SOURCE_USUAL,
    },
    "MaxFileLen": {"help": "The biggest one video file may be.", "unit": "MB"},
    "LowerLimit": {
        "help": "Warn when the free space drops under this.",
        "unit": "%",
        "min": 0,
        "max": 100,
        "source": SOURCE_PLAIN,
    },
    # -- the recorder's own screen -----------------------------------------
    "fVideo.GUISet/WindowAlpha": {
        "help": "How solid the menus look on the recorder's own screen. 128 is "
                "half see through and 255 is solid. Minus one means this "
                "recorder does not offer it.",
        "min": 128,
        "max": 255,
        "source": SOURCE_SWANN,
    },
    "fVideo.GUISet/ChannelTitleEnable": {"help": "Show the camera name on its own screen."},
    "fVideo.GUISet/TimeTitleEnable": {"help": "Show the clock on its own screen."},
    "fVideo.GUISet/RecordStateEnable": {"help": "Show whether it is recording."},
    "fVideo.GUISet/AlarmStateEnable": {"help": "Show when an alert is going off."},
    "fVideo.GUISet/AlarmGlint": {"help": "Flash the alert mark."},
    "fVideo.GUISet/Deflick": {"help": "Smooth out flicker from mains lighting."},
    "fVideo.GUISet/QRcodeEnable": {"help": "Show the code the Swann app scans."},
    "fVideo.GUISet/ChanWindowGridEnable": {"help": "Draw lines between the camera tiles."},
    "fVideo.Tour/Enable": {"help": "Cycle through the cameras on the recorder's own screen."},
    "fVideo.Tour/Interval": {
        "help": "How long each camera stays up while cycling.",
        "unit": "seconds",
        "source": SOURCE_USUAL,
    },
    "fVideo.Tour/Return": {"help": "Go back to where it was when the cycle ends."},
    "fVideo.VideoOut/Width": {"help": "How wide the recorder's own screen is, in pixels."},
    "fVideo.VideoOut/Height": {"help": "How tall the recorder's own screen is, in pixels."},
    # -- movement ----------------------------------------------------------
    "Detect.MotionDetect/Level": {
        "help": "How touchy movement detection is. Higher catches more and "
                "gives more false alarms. This recorder is set to 3.",
    },
    # -- people and vehicles ----------------------------------------------
    "Detect.HumanDetectionDVR/Level": {
        "help": "How sure the camera must be before it calls something a "
                "person. Higher is fussier.",
    },
    "Detect.CarShapeDetection/Level": {
        "help": "How sure the camera must be before it calls something a "
                "vehicle. Higher is fussier.",
    },
    "LoiterLatch": {
        "help": "How long a person or vehicle must stay before it counts as "
                "hanging about.",
        "unit": "seconds",
    },
    # -- the smart alert rules --------------------------------------------
    "Level": {"help": "How touchy this is. Higher catches more."},
    "ModuleType": {"help": "Which detector the camera uses. The recorder sets this."},
    "TypeLimit": {
        "help": "Only count things bigger than the smallest box. Off counts anything.",
    },
    "PerimeterEnable": {
        "help": "Watch the drawn area.",
        "choices": ((0, "No"), (1, "Yes")),
        "source": SOURCE_SWANN,
    },
    "TripWireEnable": {
        "help": "Watch the drawn lines.",
        "choices": ((0, "No"), (1, "Yes")),
        "source": SOURCE_SWANN,
    },
    "DirectionLimit": {"help": "Only count things going one way."},
    "ForbiddenDirection": {"help": "Which way is the wrong way."},
    "ForbiddenDir": {"help": "Which way across the line counts."},
    "IsDoubleDir": {"help": "Count a crossing either way."},
    # -- fault warnings ----------------------------------------------------
    "Storage.StorageFailure/Enable": {
        "help": "Warn when the recorder cannot read or write the disk.",
    },
    "Storage.StorageLowSpace/Enable": {
        "help": "Warn when the disk is nearly full.",
    },
    "Storage.StorageNotExist/Enable": {
        "help": "Warn when there is no disk at all.",
    },
    "Detect.LossDetect/Enable": {
        "help": "Warn when this camera stops sending a picture.",
    },
    "Detect.BlindDetect/Enable": {
        "help": "Warn when this camera's view is covered up.",
    },
    "Storage.StorageFailure/RebootEnable": {
        "help": "Restart the recorder when the disk keeps failing.",
    },
    "Storage.StorageFailure/IsRebooted": {
        "help": "Whether the recorder has already restarted over this. A note "
                "it keeps, not a setting.",
    },
    "Storage.StorageFailure/FailureNotiCnt": {
        "help": "How many times it has warned that the disk failed. A count, "
                "not a setting.",
    },
    "Storage.StorageFailure/RdErrNotiCnt": {
        "help": "How many times it has warned that it could not read the disk.",
    },
    "Storage.StorageFailure/WrErrNotiCnt": {
        "help": "How many times it has warned that it could not write to the disk.",
    },
    "Storage.StorageFailure/NoBitRateCnt": {
        "help": "How many times a camera sent nothing at all.",
    },
    "Storage.StorageFailure/CPUPacketBusy": {
        "help": "How many times the recorder ran out of room to work in.",
    },
    "Storage.StorageLowSpace/LowerLimitSpace": {
        "help": "Warn when the free space on the disk drops under this.",
        "unit": "%",
        "min": 0,
        "max": 100,
        "source": SOURCE_PLAIN,
    },
    "Storage.StorageLowSpace/LowSpaceNotiCnt": {
        "help": "How many times it has warned that the disk is nearly full.",
    },
    "Storage.StorageLowSpace/RecordTime": {
        "help": "Warn when there is less than this much video left before the "
                "oldest gets written over.",
        "unit": "days",
        "source": SOURCE_USUAL,
    },
    "Storage.StorageLowSpace/RecordTimeEnable": {
        "help": "Warn by days of video left instead of by free space.",
    },
    "Storage.StorageLowSpace/EnableType": {
        "help": "Which low space warning the recorder uses.",
    },
    # -- sound -------------------------------------------------------------
    "Detect.Sound/thresholdValue": {
        "help": "How loud a sound must be before it counts. Higher means only "
                "louder sounds set it off.",
    },
    # -- people and vehicles ----------------------------------------------
    "Detect.HumanDetectionDVR/Value": {
        "help": "The smallest a person may look before the camera counts them. "
                "The drawing sets this.",
    },
    "Detect.HumanDetectionDVR/X": {
        "help": "The width of the smallest person box. The drawing sets this.",
    },
    "Detect.HumanDetectionDVR/Y": {
        "help": "The height of the smallest person box. The drawing sets this.",
    },
    # -- on screen text and privacy blocks --------------------------------
    "AVEnc.VideoWidget/CoversNum": {
        "help": "How many privacy blocks are in use on this camera. The "
                "drawing sets this.",
    },
    "AVEnc.VideoWidget/EncodeBlend": {
        "help": "Burn this into the saved video.",
    },
    "AVEnc.VideoWidget/PreviewBlend": {
        "help": "Show this on the live picture too. A privacy block needs both "
                "this and the one above, or it only hides the recording.",
    },
    "AVEnc.VideoWidget/BackColor": {
        "help": "The colour behind the text, packed into one number.",
    },
    "AVEnc.VideoWidget/FrontColor": {
        "help": "The colour of the text, packed into one number.",
    },
    "fVideo.OsdLogo/Enable": {
        "help": "Show the maker's logo on the recorder's own screen.",
    },
    "fVideo.OsdLogo/Left": {"help": "How far in from the left the logo sits.", "unit": "pixels"},
    "fVideo.OsdLogo/Top": {"help": "How far down from the top the logo sits.", "unit": "pixels"},
    "fVideo.OsdLogo/FgTrans": {
        "help": "How see through the logo is. 0 is invisible and 255 is solid.",
    },
    "fVideo.OsdLogo/BgTrans": {
        "help": "How see through the box behind the logo is. 0 is invisible "
                "and 255 is solid.",
    },
    # -- the recorder's own screen, the rest -------------------------------
    "fVideo.GUISet/ChanStateRecEnable": {"help": "Show the recording mark on each tile."},
    "fVideo.GUISet/ChanStateMtdEnable": {"help": "Show the movement mark on each tile."},
    "fVideo.GUISet/ChanStateVlsEnable": {"help": "Show the lost camera mark on each tile."},
    "fVideo.GUISet/ChanStateLckEnable": {"help": "Show the locked mark on each tile."},
    "fVideo.GUISet/ChanStateBitRateEnable": {"help": "Show how much data each camera is sending."},
    "fVideo.GUISet/CarInfo": {"help": "Show number plate readings. No camera here does this."},
    "fVideo.GUISet/GPSInfo": {"help": "Show position readings. This recorder has no GPS."},
    "fVideo.GUISet/RemoteEnable": {"help": "Let a remote control work the menus."},
    "fVideo.Tour/Type": {
        "help": "Which split layout this camera picker is for. One picker per "
                "layout, not a running order.",
    },
    # -- network, the rest -------------------------------------------------
    "NetWork.NetCommon/MAC": {
        "help": "The recorder's own hardware address. It cannot be changed.",
    },
    "NetWork.NetCommon/HostName": {
        "help": "Another name the recorder answers to on your network.",
    },
    "NetWork.NetCommon/UseHSDownLoad": {
        "help": "Send saved video faster than real time when an app asks for it.",
    },
    "NetWork.NetDHCP/Interface": {
        "help": "Which network socket this is for. `eth0` is the wired one.",
    },
    "NetWork.NetDNS/Address": {
        "help": "Which server turns names into addresses. Your router's address "
                "usually works.",
    },
    "NetWork.NetDNS/SpareAddress": {
        "help": "A second name server, used if the first one does not answer.",
    },
    "NetWork.Nat/Addr": {"help": "The Swann cloud server this recorder checks in with."},
    "NetWork.Nat/DnsServer1": {"help": "The name server the cloud link uses."},
    "NetWork.Nat/DnsServer2": {"help": "A spare name server for the cloud link."},
    # -- ports and streaming, the rest ------------------------------------
    "NetWork.RTSP/UserName": {
        "help": "The name another app signs in with to watch video.",
    },
    "NetWork.RTSP/Password": {
        "help": "The password another app signs in with to watch video.",
    },
    "NetWork.RTSP/Name": {"help": "What the recorder calls its video service."},
    "NetWork.RTSP/IsClient": {
        "help": "Fetch video from somewhere else instead of handing it out. Leave it off.",
    },
    "NetWork.Upnp/State": {
        "help": "Whether the router actually opened the ports. A reading, not a setting.",
    },
    # -- email, the rest ---------------------------------------------------
    "NetWork.NetEmail/UserName": {
        "help": "The name you sign in to your email provider with, usually the "
                "full address.",
    },
    "NetWork.NetEmail/Password": {
        "help": "The password for that email account. Gmail needs an app "
                "password, not your normal one.",
    },
    "NetWork.NetEmailExt.DefaultMail": {
        "help": "Use Swann's own email server instead of your own. Then you do "
                "not fill in a server, name or password.",
    },
    "NetWork.NetEmailExt.EmailEncry": {
        "help": "How the email is encrypted, as a number. It must match the port.",
    },
    "NetWork.NetEmailExt.SendName": {
        "help": "The name the alert emails come from.",
    },
    # -- date and time, the rest ------------------------------------------
    "System.TimeZone/FirstUserTimeZone": {
        "help": "The recorder's own number for the time zone. 13 is UK time on "
                "this firmware.",
    },
    "System.TimeZone/timeMin": {
        "help": "Extra minutes on top of the time zone. Most zones need 0.",
        "unit": "minutes",
    },
    "NetWork.NetNTP/UserName": {"help": "A sign in name for the time server. Rarely needed."},
    "NetWork.NetNTP/Password": {"help": "A password for the time server. Rarely needed."},
    "NetWork.NetNTP/Anonymity": {"help": "Ask the time server without signing in. Normal."},
    # -- general, the rest -------------------------------------------------
    "General.Location/Language": {
        "help": "The language on the recorder's own screen. It does not change "
                "this app.",
    },
    "General.Location/Day": {"help": "The day summer time starts.", "min": 1, "max": 31,
                             "source": SOURCE_PLAIN},
    "General.Location/Week": {
        "help": "Which week of the month summer time starts in. 0 means use the "
                "day number instead.",
    },
    "General.Location/IranCalendar": {"help": "The Iranian calendar setting. Leave it at 0."},
    "General.AutoMaintain/AutoRebootDay": {
        "help": "The recorder restarts itself on this day. That is normal, and "
                "it is why a restart shows in the log every Sunday. It also "
                "takes a plain number, meaning every so many days, which this "
                "list does not offer.",
        "choices": (("Everyday", "Every day"), ("Monday", "Monday"),
                    ("Tuesday", "Tuesday"), ("Wednesday", "Wednesday"),
                    ("Thursday", "Thursday"), ("Friday", "Friday"),
                    ("Saturday", "Saturday"), ("Sunday", "Sunday"),
                    ("Never", "Never")),
        "source": SOURCE_SWANN,
    },
    "General.AutoMaintain/AutoRebootHour": {
        "help": "What time it restarts itself. Swann's own page counts this in "
                "minutes past midnight, where 30 means midnight. This recorder "
                "holds 0 and still restarts at midnight.",
    },
    "fVideo.AudioAcquisitionMode/AudioAcquisitionMode": {
        "help": "Where this camera's sound comes from. 0 is the camera's own "
                "microphone.",
    },
    # -- things that look like settings but are not ------------------------
    "AnalogCapPlay": {"help": "What the recorder can do. It is not a setting."},
    "DigitalCapPlay": {"help": "What the recorder can do. It is not a setting."},
    "NetWork.ChnMode/CurChnsMode": {
        "help": "Which camera socket layout the recorder is using now.",
    },
    "NetWork.ChnMode/TotalChnsModeNum": {
        "help": "How many camera socket layouts it can use.",
    },
    "Guide/GuideEnable": {
        "help": "Show the setup helper on the recorder's own screen at start up.",
    },
    "Custom.SwannAutoUpgrade/NVREnable": {
        "help": "Let the recorder update its own firmware.",
    },
    "Custom.SwannAutoUpgrade/IPCEnable": {
        "help": "Let the recorder update the cameras' firmware.",
    },
    "Custom.SwannAutoUpgrade/ConnectInternet": {
        "help": "Let it check Swann's servers for a new version.",
    },
    # -- the cameras screen ------------------------------------------------
    "NetWork.ChnStatus/ChnName": {
        "help": "What the camera calls itself. The recorder reads it from the "
                "camera, so this app cannot change it.",
    },
    "NetWork.ChnStatus/CurRes": {"help": "The picture size this camera is sending now."},
    "NetWork.ChnStatus/MaxRes": {"help": "The biggest picture this camera can send."},
    "NetWork.ChnStatus/Status": {
        "help": "Whether the camera is connected. `Connected` is good, "
                "`NoConfig` means the socket is empty.",
    },
    "NetWork.RemoteDeviceV3/Enable": {"help": "Use this camera socket at all."},
    "NetWork.RemoteDeviceV3/ConnType": {
        "help": "How the recorder talks to the camera. `IPC` is a network camera.",
    },
    "NetWork.RemoteDeviceV3/POEEnable": {
        "help": "Power the camera down its network cable.",
    },
    "NetWork.RemoteDeviceV3/EnCheckTime": {
        "help": "Set the camera's clock from the recorder's.",
    },
    "NetWork.RemoteDeviceV3/SynchResolution": {
        "help": "Let the recorder tell the camera which picture size to send.",
    },
    "NetWork.RemoteDeviceV3/SingleConnId": {
        "help": "The recorder's own number for this camera link.",
    },
    "NetWork.RemoteDeviceV3/TourIntv": {
        "help": "How long this camera stays up while the recorder cycles "
                "through them.",
        "unit": "seconds",
    },
    "IPAddress": {"help": "The camera's own address on your network."},
    "MacAddr": {"help": "The camera's hardware address. It cannot be changed."},
    "DevType": {"help": "What kind of device the recorder thinks this is."},
    "ConfName": {"help": "The recorder's own short name for this camera link."},
    "Channel": {
        "help": "Which picture stream to take from the camera. Most cameras "
                "only have one, so this is 1.",
    },
    # -- bits and pieces shared by several screens -------------------------
    "Address": {
        "help": "An address packed into one number. The plain version is in the "
                "box above or below it.",
    },
    "Custom.SwannSpecialInfo.InfoAlarm/AlarmPIR": {
        "help": "Swann's own copy of the movement grid. Write the plain one "
                "first and this one last, or the recorder reports a failure "
                "while it is still copying.",
    },
    "AVEnc.VideoWidget/Name": {
        "help": "The camera name drawn on the picture. These cameras draw "
                "their own, so this does nothing here.",
    },
    "AVEnc.VideoWidget/SerialNo": {
        "help": "The recorder's number drawn on the picture.",
    },
}

# The shared alert fields belong to every alert config, keyed by config name so
# `Enable` on the movement screen cannot be confused with `Enable` on FTP.
ALERT_CONFIGS = (
    "Detect.MotionDetect",
    "Detect.HumanDetectionDVR",
    "Detect.CarShapeDetection",
    "Detect.Sound",
    "Detect.LossDetect",
    "Detect.BlindDetect",
    "Detect.Analyze",
    "Detect.Analyze_Swann_Pid",
    "Detect.Analyze_Swann_Lcd",
    "Detect.Analyze_Swann_Sod",
    "Storage.StorageFailure",
    "Storage.StorageLowSpace",
    "Storage.StorageNotExist",
)
SMART_CONFIGS = (
    # `Detect.Analyze` is the shared one. It is not a schedule, whatever the
    # name suggests: it returns the same rule structure as the three below.
    "Detect.Analyze",
    "Detect.Analyze_Swann_Pid",
    "Detect.Analyze_Swann_Lcd",
    "Detect.Analyze_Swann_Sod",
)

for _config in ALERT_CONFIGS:
    for _leaf, _entry in _ALERT_GUIDE.items():
        FIELD_GUIDE.setdefault(f"{_config}/{_leaf}", _entry)
for _config in SMART_CONFIGS:
    for _leaf, _entry in _SMART_GUIDE.items():
        FIELD_GUIDE.setdefault(f"{_config}/{_leaf}", _entry)
del _config, _leaf, _entry


def _check_guide() -> None:
    """Stop a limit that calls itself unproven from being enforced anyway.

    `SOURCE_USUAL` says in words that the box is not capped. An entry that says
    that and also holds both ends of a limit would cap it, and the sentence
    Billy reads would be a lie. So it fails here instead, at start up.
    """
    for key, entry in FIELD_GUIDE.items():
        has_limit = entry.get("min") is not None and entry.get("max") is not None
        if has_limit and entry.get("source") not in SOURCE_PROVEN:
            raise ValueError(
                f"field guide {key!r} holds a limit but its source does not "
                "say the limit was proven"
            )
        if entry.get("choices") and entry.get("source") not in SOURCE_PROVEN:
            raise ValueError(
                f"field guide {key!r} holds a list of choices but its source "
                "does not say the list was proven"
            )


_check_guide()


def field_guide(config: str, path: str, name: str) -> dict[str, object]:
    """What we know about one field. An empty dict when we know nothing.

    Tried most exact first, so a leaf that means different things on
    different screens gets the right entry.
    """
    keys = [f"{config}/{path}"]
    # The box a field sits in, then the field on its own. `BitRate` means one
    # thing under `Video` and another under `Audio`, on the same screen.
    parts = path.split("/")
    if len(parts) > 1:
        keys.append(f"{config}/{parts[-2]}/{name}")
    keys.append(f"{config}/{name}")
    # A list of plain numbers has nothing on each entry worth naming, so the
    # list itself carries the help. `fVideo.AudioAcquisitionMode` is one number
    # per camera inside a box called `AudioAcquisitionMode`.
    first = path.split("/")[0]
    if first and first != path:
        keys.append(f"{config}/{first}")
    # And a few settings are one bare value, not a box of them.
    # `NetWork.NetEmailExt.Interval` is just a number.
    if "/" not in path:
        keys.append(config)
    keys.append(name)
    for key in keys:
        found = FIELD_GUIDE.get(key)
        if found:
            return found
    return {}


# --------------------------------------------------------------------------
# The encoder tables.
#
# Copied straight out of Swann's own web page for this recorder,
# `rsui/plugin.js` lines 41 to 200. The order matters: the recorder sends a
# picture size as a number, and that number is an index into this list.
#
# Checked against the live recorder on 2026-11-08. Camera 1 main stream reads
# 8M and 6144 kbit/s, which is the "usual" number in the 8M row. See
# FIELD-GUIDE-evidence.md section 2.2.
# --------------------------------------------------------------------------

# Index, name, PAL width, PAL height, NTSC width, NTSC height.
ENCODE_RESOLUTIONS = (
    ("D1", 704, 576, 704, 480),
    ("HD1", 704, 288, 720, 240),
    ("BCIF", 352, 576, 352, 480),
    ("CIF", 352, 288, 352, 240),
    ("QCIF", 176, 144, 176, 120),
    ("VGA", 640, 480, 640, 480),
    ("QVGA", 432, 320, 432, 320),
    ("SVCD", 480, 480, 480, 480),
    ("QQVGA", 160, 128, 160, 128),
    ("ND1", 240, 192, 240, 192),
    ("650TVL", 928, 576, 928, 480),
    ("720P", 1280, 720, 1280, 720),
    ("1_3M", 1280, 960, 1280, 960),
    ("UXGA", 1600, 1200, 1600, 1200),
    ("1080P", 1920, 1080, 1920, 1080),
    ("WUXGA", 1920, 1200, 1920, 1200),
    ("2_5M", 1872, 1408, 1872, 1408),
    ("3M", 2048, 1536, 2048, 1536),
    ("5M", 2560, 1920, 2560, 1920),
    ("1080N", 960, 1080, 960, 1080),
    ("4M", 2560, 1440, 2560, 1440),
    ("6M", 3072, 2048, 3072, 2048),
    ("8M", 3264, 2448, 3264, 2448),
    ("12M", 4000, 3000, 4000, 3000),
    ("4K", 3840, 2160, 3840, 2160),
    ("720N", 640, 720, 640, 720),
    ("WSVGA", 1024, 576, 1024, 576),
    ("NHD", 640, 360, 640, 360),
    ("3M_N", 1024, 1536, 1024, 1536),
    ("4M_N", 1280, 1440, 1280, 1440),
    ("5M_N", 1872, 1408, 1872, 1408),
    ("4K_N", 1920, 2160, 1920, 2160),
)

# Lowest, highest and usual bit rate in kbit/s, one row per picture size, in
# the same order as ENCODE_RESOLUTIONS. On this firmware H.264 and H.265 share
# one table, line for line, so there is only one here.
ENCODE_BITRATES = (
    (8, 2560, 2048),
    (384, 2048, 2048),
    (384, 2048, 2048),
    (8, 512, 512),
    (64, 512, 512),
    (512, 2048, 2048),
    (8, 1024, 1024),
    (512, 2048, 2048),
    (64, 512, 512),
    (64, 768, 768),
    (32, 2048, 2048),
    (1024, 4096, 2048),
    (1024, 5120, 4096),
    (1024, 4096, 4096),
    (1024, 4096, 4096),
    (1280, 4096, 4096),
    (1280, 8192, 6144),
    (1536, 8192, 6144),
    (2048, 8192, 6144),
    (1024, 4096, 2048),
    (1536, 8192, 6144),
    (1536, 8192, 6144),
    (1536, 8192, 6144),
    (1536, 8192, 6144),
    (2048, 8192, 6144),
    (512, 2048, 2048),
    (1024, 4096, 2048),
    (512, 2048, 2048),
    (1024, 5120, 4096),
    (1024, 8192, 4096),
    (1280, 8192, 6144),
    (1536, 8192, 6144),
)

# The gaps between the allowed bit rates. Below the first number, step by the
# second. This is `getGainValue()` in `rsui/plugin.js`, turned into a table.
# It keeps the bit rate list short: 8192 is reached in about 30 steps, not 8000.
ENCODE_BITRATE_STEPS = (
    (32, 8),
    (96, 16),
    (256, 32),
    (512, 64),
    (1024, 128),
    (2048, 256),
    (6144, 1024),
    (10241, 2048),
)

# The video formats, by the number the recorder uses. 7 is H.264 and 8 is
# H.265. This recorder reports only those two.
ENCODE_COMPRESSIONS = (
    "DIVX MPEG4",
    "MS MPEG4",
    "MPEG2",
    "MPEG1",
    "H.263",
    "MJPG",
    "FCC MPEG4",
    "H.264",
    "H.265",
    "",
)

# PAL is the UK one. The recorder's `videoFormat` is 0 for PAL and 1 for NTSC.
ENCODE_VIDEO_FORMAT_PAL = 0
ENCODE_FPS_MAX_PAL = 25
ENCODE_FPS_MAX_NTSC = 30
ENCODE_FPS_MIN = 1

# The keyframe gap has to be a whole number of seconds, so it steps by the
# frames a second. Proven on the live recorder on 2026-11-08, camera 1, main
# stream, with frames a second at 15: 15, 30 and 45 all landed, while 16, 20
# and 64 each got Ret 100 and were then read back unchanged. `IFrameRange`
# says 1 to 64 and says nothing about this, so it had to be found by writing.
ENCODE_GOP_STEPS_BY_FPS = True
ENCODE_GOP_NOTE = (
    "The recorder only takes a whole number of seconds here, so this counts "
    "up in steps of the frames a second."
)

# Picture quality runs 1 to 6. The recorder's own page shows a six item list
# and reads it back with `Quality - 1`.
ENCODE_QUALITY_MIN = 1
ENCODE_QUALITY_MAX = 6

# How a picture size reads in a dropdown: the recorder's own name plus the real
# number of pixels, because "8M" on its own says nothing.
ENCODE_SIZE_TITLE = "{name} ({width} by {height})"

# What the video quality screen calls each of the two streams.
ENCODE_STREAM_MAIN = "MainFormat"
ENCODE_STREAM_SUB = "ExtraFormat"

# The box inside a stream that holds the picture settings. The one beside it
# is `Audio`, which has a `BitRate` of its own and different limits.
ENCODE_SECTION_VIDEO = "Video"

# The field names inside a stream that the quality editor drives itself.
ENCODE_FIELD_RESOLUTION = "Resolution"
ENCODE_FIELD_BITRATE = "BitRate"
ENCODE_FIELD_COMPRESSION = "Compression"
ENCODE_FIELD_FPS = "FPS"
ENCODE_FIELD_GOP = "GOP"
ENCODE_FIELD_QUALITY = "Quality"

# Which fields on the video quality screen the recorder states a limit for.
# The page swaps these for a dropdown built from the camera's own reply, and
# leaves everything else as a plain box.
ENCODE_LIMIT_FIELDS = {
    "main": ENCODE_STREAM_MAIN,
    "sub": ENCODE_STREAM_SUB,
    "video": ENCODE_SECTION_VIDEO,
    "resolution": ENCODE_FIELD_RESOLUTION,
    "bitRate": ENCODE_FIELD_BITRATE,
    "compression": ENCODE_FIELD_COMPRESSION,
    "fps": ENCODE_FIELD_FPS,
    "gop": ENCODE_FIELD_GOP,
    "quality": ENCODE_FIELD_QUALITY,
}


def encode_bitrate_step(bitrate: int) -> int:
    """The gap to the next allowed bit rate, or 0 when there is none."""
    for ceiling, step in ENCODE_BITRATE_STEPS:
        if bitrate < ceiling:
            return step
    return 0


def encode_bitrate_choices(resolution: int) -> tuple[int, ...]:
    """Every bit rate the recorder allows for one picture size, in order."""
    if not 0 <= resolution < len(ENCODE_BITRATES):
        return ()
    low, high, _usual = ENCODE_BITRATES[resolution]
    out: list[int] = []
    value = low
    while value <= high:
        out.append(value)
        step = encode_bitrate_step(value)
        if step <= 0:
            break
        value += step
    return tuple(out)


def encode_mask_choices(mask: str, names: tuple[str, ...]) -> tuple[int, ...]:
    """Turn one of the recorder's hex ability masks into a list of indexes.

    The recorder says what a camera supports as a packed number, one bit per
    entry in `names`. Bit 0 is the first name.
    """
    try:
        bits = int(str(mask), 16)
    except (TypeError, ValueError):
        return ()
    return tuple(i for i in range(len(names)) if bits & (1 << i))


# NetWork.ChnStatus field names and values, read off the live recorder.
# It answers 32 entries even on an 8 socket recorder, so trim it.
CHN_STATUS_NAME_KEY = "ChnName"
CHN_STATUS_STATUS_KEY = "Status"
CHN_STATUS_RESOLUTION_KEY = "CurRes"
CHN_STATUS_MAX_RESOLUTION_KEY = "MaxRes"
CHN_STATUS_CONNECTED = "Connected"
CHN_STATUS_EMPTY = "NoConfig"

# How a camera socket is named on screen. The recorder counts from 0, people
# counts from 1.
CHANNEL_LABEL_TEMPLATE = "Camera {number}"

# Log page defaults.
LOG_DEFAULT_DAYS = 3
LOG_MAX_DAYS = 30


# Configs the recorder reports but will not take a write for. Shown as facts.
CONFIG_REPORT_ONLY = frozenset({
    "NetWork.ChnStatus",
    "NetUse.DigitalAbility",
    "ChannelTitle",
})


# --------------------------------------------------------------------------
# Visual settings editors.
#
# Nine screens hold a position or a time. A list of numbers cannot show
# either, so each of those screens draws on a camera picture or paints a
# week instead. Every name, size and index below was read off the live
# recorder, or off the recorder's own web page source, on 2026-11-08.
# Nothing here is a guess. See SETTINGS-UI-evidence.md for the proof.
# --------------------------------------------------------------------------

# A screen names one of these in SETTINGS_SCREENS, and the page draws that
# editor in place of the plain field list.
EDITOR_PRIVACY = "privacy"
EDITOR_OVERLAY = "overlay"
EDITOR_MOTION = "motion"
EDITOR_SHAPE = "shape"
EDITOR_LINE = "line"
EDITOR_WEEK = "week"
EDITOR_TOUR = "tour"

# The recorder puts every position in its own square, 0 to 8192 across and
# 0 to 8192 down, whatever the real picture size is. Proven in the
# recorder's own page source: rsui/cfg/chn_sp.js:52 and chn_live.js:129.
VISUAL_SPACE = 8192

# The smallest box a person can still grab, as a share of the picture.
VISUAL_MIN_SIZE = 0.03

# --- Privacy blocks, AVEnc.VideoWidget ------------------------------------
# Covers holds 8 slots but the recorder's own page only ever uses the first
# 4, so this does the same. rsui/cfg/chn_sp.js:5 sets nCoverNum = 4.
PRIVACY_COVERS_KEY = "Covers"
PRIVACY_COVERS_NUM_KEY = "CoversNum"
PRIVACY_COVER_LIMIT = 4
PRIVACY_POS_KEY = "RelativePos"
# RelativePos is two corners, not a corner and a size. chn_sp.js:52 to 70
# writes one corner into 0 and 1, the opposite corner into 2 and 3, then
# swaps them so left is under right and top is under bottom.
PRIVACY_POS_LEFT = 0
PRIVACY_POS_TOP = 1
PRIVACY_POS_RIGHT = 2
PRIVACY_POS_BOTTOM = 3
# EncodeBlend burns the block into the saved video. chn_sp.js:49 uses it as
# the "this block is in use" flag. PreviewBlend hides it on the live view as
# well, which the recorder's own page never sets. Proven on 2026-11-08: a
# block with EncodeBlend on and PreviewBlend off saves fine and still shows
# on the live picture, which reads as a block that did not work. So both go
# on together here.
PRIVACY_ON_KEY = "EncodeBlend"
PRIVACY_PREVIEW_KEY = "PreviewBlend"
PRIVACY_BACK_COLOR_KEY = "BackColor"

# --- On screen text, AVEnc.VideoWidget ------------------------------------
# Two labels per camera. Only the x and y are written. chn_live.js:129 to
# 132 leaves slots 2 and 3 alone, so this does too.
OVERLAY_LABELS = (
    {"key": "ChannelTitleAttribute", "title": "Camera name"},
    {"key": "TimeTitleAttribute", "title": "Clock"},
)
OVERLAY_POS_KEY = "RelativePos"
OVERLAY_POS_X = 0
OVERLAY_POS_Y = 1
OVERLAY_ON_KEY = "EncodeBlend"
OVERLAY_PREVIEW_KEY = "PreviewBlend"
OVERLAY_FRONT_COLOR_KEY = "FrontColor"
OVERLAY_BACK_COLOR_KEY = "BackColor"

# --- Movement brush -------------------------------------------------------
# The real grid lives in Swann's own config, as one hex string per row.
# Column j is bit j of that 32 bit number, counting from the low end.
# Proven in rsui/cfg/alarm_mv.js:257 to 275.
MOTION_SWANN_CONFIG = "Custom.SwannSpecialInfo.InfoAlarm"
MOTION_SWANN_REGION_PATH = "RegionAll/{channel}/Region/0"
# The grid's real size is counted off the recorder's own answer: one row per
# string it sends, and four columns per hex digit in a string. This firmware
# answers 32 strings of 8 digits, so 32 rows by 32 columns, and every one of
# them reads as watched.
#
# The recorder's own page hard codes 18 rows, but that page is a generic
# build: its recording screen reads Mask and TimeSection, which this
# firmware does not have at all. Where the two disagree, the recorder's own
# answer wins. The numbers below are only a fallback for a reply that
# cannot be counted.
MOTION_COLUMNS = 32
MOTION_ROWS = 32
MOTION_HEX_DIGITS = 8
# The recorder's own page writes the plain config in step with Swann's one,
# so this does the same. Both hold the same shape on this firmware.
MOTION_CONFIG = "Detect.MotionDetect"
MOTION_REGION_KEY = "Region"
MOTION_LEVEL_KEY = "Level"
MOTION_ENABLE_KEY = "Enable"
MOTION_LEVELS = (
    {"value": 1, "title": "Least sensitive"},
    {"value": 2, "title": "Low"},
    {"value": 3, "title": "Normal"},
    {"value": 4, "title": "High"},
    {"value": 5, "title": "Most sensitive"},
)

# --- Shapes and lines, the three smart alert screens ----------------------
# All three keep the same box of settings, which is why one tool draws for
# all of them.
SHAPE_RULE_PATH = "RuleConfig/PEARule"
SHAPE_BOUNDARY_PATH = "RuleConfig/PEARule/PerimeterRule/LimitPara/Boundary"
SHAPE_POINTS_KEY = "Points"
SHAPE_MODE_KEY = "Mode"
SHAPE_VALID_KEY = "Valid"
SHAPE_POINT_NUM_KEY = "PointNum"
# Points holds 16 slots, used as 4 shapes of 4 corners each. Shape i owns
# slots i*4 to i*4+3. rsui/cfg/Perimeter_Zone.js:229 to 246.
SHAPE_RULE_COUNT = 4
SHAPE_POINTS_PER_RULE = 4
SHAPE_ENABLE_KEY = "PerimeterEnable"
SHAPE_SHOW_KEY = "ShowRule"
SHAPE_TRACK_KEY = "ShowTrack"
SHAPE_TYPE_PATH = "RuleConfig/PEARule/PerimeterRule"
SHAPE_HUMAN_KEY = "TypeHuman"
SHAPE_VEHICLE_KEY = "TypeVehicle"
# Lines live in their own box of 8 slots, of which the recorder's own page
# uses 4. Perimeter_Line.js:255 and :670.
LINE_PATH = "RuleConfig/PEARule/TripWireRule/TripWire"
LINE_COUNT = 4
LINE_KEY = "Line"
LINE_START_KEY = "StartPt"
LINE_END_KEY = "EndPt"
LINE_DIR_KEY = "IsDoubleDir"
LINE_VALID_KEY = "Valid"
LINE_ENABLE_KEY = "TripWireEnable"
POINT_X_KEY = "x"
POINT_Y_KEY = "y"
# 0, 1 and 2 are the only values the recorder's own page offers.
# Perimeter_Line.js:29 to 32.
DIRECTION_CHOICES = (
    {"value": 0, "title": "Either way"},
    {"value": 1, "title": "One way, start to end"},
    {"value": 2, "title": "One way, end to start"},
)
# A shape or a line sitting at all zeros means nobody has drawn it.
# Perimeter_Zone.js:240 and Perimeter_Line.js:264.
SHAPE_EMPTY_VALUE = 0

# --- The week grid --------------------------------------------------------
# One letter per half hour, 48 letters for a day, 7 days for a week.
WEEK_SHEET_KEY = "ScheduleSheet"
WEEK_SLOTS_PER_DAY = 48
WEEK_SLOT_MINUTES = 30
WEEK_ON = "1"
WEEK_OFF = "0"
# Day 0 is Sunday. Proven on 2026-11-08, itself a Sunday: writing day 0 made
# camera 1 start recording at once, and camera 2 did not.
WEEK_DAYS = (
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
)
# Slot 0 is midnight. Proven the same way: slot 39 switched on recording at
# 19:52, and 39 half hours is 19:30.
WEEK_FIRST_SLOT_HOUR = 0

# Record.ScheduleSheet has 6 rows, one per thing that can start a recording.
# Only the three named below are used on this recorder. The other three read
# all zeros and are carried through untouched, because their meaning is not
# proven and a wrong guess would change when video is kept.
RECORD_SHEET_ROWS = (
    {
        "row": 0,
        "title": "All the time",
        "note": "Keeps video whether anything moves or not. Fills the disk fastest.",
    },
    {
        "row": 2,
        "title": "On movement",
        "note": "Keeps video when the camera sees movement. This is the normal one.",
    },
    {
        "row": 4,
        "title": "On people and vehicles",
        "note": "Keeps video when the camera picks out a person or a vehicle.",
    },
)
# Custom.SwannSNAP.ScheduleSheet has 3 rows, in the same order as the first
# three of the record sheet. rsui/cfg/Capture_Jh.js:7 names two of them.
STILLS_SHEET_ROWS = (
    {
        "row": 0,
        "title": "All the time",
        "note": "Saves a picture every so often, whether anything moves or not.",
    },
    {
        "row": 2,
        "title": "On movement",
        "note": "Saves a picture when the camera sees movement.",
    },
)
# Written in step with Record, the way the recorder's own page does it.
# rsui/cfg/record_jh.js:290.
RECORD_CONFIGS = ("Record", "ExtRecord")
STILLS_CONFIG = "Custom.SwannSNAP"

# --- The recorder's own camera tour ---------------------------------------
# Mask is one hex string per split layout, and camera N is bit N.
TOUR_MASK_KEY = "Mask"
TOUR_MASK_BITS = 32
TOUR_ENABLE_KEY = "Enable"
TOUR_INTERVAL_KEY = "Interval"
TOUR_TYPE_KEY = "Type"
TOUR_SPLITS = (
    {"index": 0, "title": "One camera at a time"},
    {"index": 1, "title": "Four at a time"},
    {"index": 2, "title": "Eight at a time"},
    {"index": 3, "title": "Nine at a time"},
)
TOUR_TYPE_TITLES = {
    "Monitor": "Normal cycling",
    "Alarm": "When an alarm goes off",
    "Montion": "When something moves",
}

# --- Colour swatches ------------------------------------------------------
# The recorder writes colours as one packed number in hex: see through,
# red, green, blue, two digits each.
COLOUR_PREFIX = "0x"
COLOUR_DIGITS = 8
COLOUR_KEYS = ("BackColor", "FrontColor")
COLOUR_ALPHA_MAX = 255

# The still picture the drawing editors use as a backdrop. The browser builds
# this URL itself, so the one copy lives here and app/main.py reads it too.
API_SNAPSHOT_TEMPLATE = "/api/live/{channel}/snapshot"

# Everything the page needs that is not in the values themselves. Shipped
# with each screen so the browser never has to hold a second copy.
def visual_settings() -> dict[str, object]:
    """The numbers and names the visual editors need, in one lump."""
    return {
        "space": VISUAL_SPACE,
        "minSize": VISUAL_MIN_SIZE,
        "privacy": {
            "coversKey": PRIVACY_COVERS_KEY,
            "countKey": PRIVACY_COVERS_NUM_KEY,
            "limit": PRIVACY_COVER_LIMIT,
            "posKey": PRIVACY_POS_KEY,
            "left": PRIVACY_POS_LEFT,
            "top": PRIVACY_POS_TOP,
            "right": PRIVACY_POS_RIGHT,
            "bottom": PRIVACY_POS_BOTTOM,
            "onKey": PRIVACY_ON_KEY,
            "previewKey": PRIVACY_PREVIEW_KEY,
            "colourKey": PRIVACY_BACK_COLOR_KEY,
        },
        "overlay": {
            "labels": [dict(label) for label in OVERLAY_LABELS],
            "posKey": OVERLAY_POS_KEY,
            "x": OVERLAY_POS_X,
            "y": OVERLAY_POS_Y,
            "onKey": OVERLAY_ON_KEY,
            "previewKey": OVERLAY_PREVIEW_KEY,
            "frontKey": OVERLAY_FRONT_COLOR_KEY,
            "backKey": OVERLAY_BACK_COLOR_KEY,
        },
        "motion": {
            "swannConfig": MOTION_SWANN_CONFIG,
            "swannPath": MOTION_SWANN_REGION_PATH,
            "config": MOTION_CONFIG,
            "regionKey": MOTION_REGION_KEY,
            "columns": MOTION_COLUMNS,
            "rows": MOTION_ROWS,
            "digits": MOTION_HEX_DIGITS,
            "levelKey": MOTION_LEVEL_KEY,
            "enableKey": MOTION_ENABLE_KEY,
            "levels": [dict(level) for level in MOTION_LEVELS],
        },
        "shape": {
            "rulePath": SHAPE_RULE_PATH,
            "boundaryPath": SHAPE_BOUNDARY_PATH,
            "pointsKey": SHAPE_POINTS_KEY,
            "modeKey": SHAPE_MODE_KEY,
            "validKey": SHAPE_VALID_KEY,
            "countKey": SHAPE_POINT_NUM_KEY,
            "rules": SHAPE_RULE_COUNT,
            "corners": SHAPE_POINTS_PER_RULE,
            "enableKey": SHAPE_ENABLE_KEY,
            "showKey": SHAPE_SHOW_KEY,
            "trackKey": SHAPE_TRACK_KEY,
            "typePath": SHAPE_TYPE_PATH,
            "humanKey": SHAPE_HUMAN_KEY,
            "vehicleKey": SHAPE_VEHICLE_KEY,
            "empty": SHAPE_EMPTY_VALUE,
        },
        "line": {
            "path": LINE_PATH,
            "count": LINE_COUNT,
            "lineKey": LINE_KEY,
            "startKey": LINE_START_KEY,
            "endKey": LINE_END_KEY,
            "dirKey": LINE_DIR_KEY,
            "validKey": LINE_VALID_KEY,
            "enableKey": LINE_ENABLE_KEY,
        },
        "point": {"x": POINT_X_KEY, "y": POINT_Y_KEY},
        "directions": [dict(choice) for choice in DIRECTION_CHOICES],
        "week": {
            "sheetKey": WEEK_SHEET_KEY,
            "slots": WEEK_SLOTS_PER_DAY,
            "slotMinutes": WEEK_SLOT_MINUTES,
            "on": WEEK_ON,
            "off": WEEK_OFF,
            "days": list(WEEK_DAYS),
            "firstHour": WEEK_FIRST_SLOT_HOUR,
            "recordRows": [dict(row) for row in RECORD_SHEET_ROWS],
            "stillsRows": [dict(row) for row in STILLS_SHEET_ROWS],
            "recordConfigs": list(RECORD_CONFIGS),
            "stillsConfig": STILLS_CONFIG,
        },
        "tour": {
            "maskKey": TOUR_MASK_KEY,
            "bits": TOUR_MASK_BITS,
            "enableKey": TOUR_ENABLE_KEY,
            "intervalKey": TOUR_INTERVAL_KEY,
            "typeKey": TOUR_TYPE_KEY,
            "splits": [dict(split) for split in TOUR_SPLITS],
            "typeTitles": dict(TOUR_TYPE_TITLES),
        },
        "colour": {
            "prefix": COLOUR_PREFIX,
            "digits": COLOUR_DIGITS,
            "keys": list(COLOUR_KEYS),
            "alphaMax": COLOUR_ALPHA_MAX,
        },
        "snapshot": API_SNAPSHOT_TEMPLATE,
        "channelLabel": CHANNEL_LABEL_TEMPLATE,
    }


# --------------------------------------------------------------------------
# Alerts. Built from the recorder's own log, which holds about 4096 rows, or
# two and a half days here. This machine copies them into its own store so the
# history keeps growing past what the recorder remembers.
# --------------------------------------------------------------------------
ALERT_SYNC_SECONDS = 300
ALERT_SYNC_DAYS = 3
ALERT_FIRST_SYNC_DELAY_SECONDS = 5
ALERT_PAGE_SIZE = 200
ALERT_MAX_PAGE_SIZE = 2000
ALERT_OPEN_MAX_SECONDS = 3600

# The log writes "MotionDetect,1". The number is the camera, counting from 1.
# Proof: this recorder has cameras in sockets 1 and 2 only, and the log carries
# "AdvPd,2" and "AdvVd,2". Counting from 0 that would be socket 3, which is
# empty and cannot raise anything.
ALERT_DATA_SEPARATOR = ","
ALERT_CHANNEL_BASE = 1

# What each kind is called in plain words.
ALERT_KIND_LABELS = {
    "MotionDetect": "Movement",
    "AdvPd": "Person",
    "AdvVd": "Vehicle",
    "HumanDetect": "Person",
    "FaceDetect": "Face",
    "PerimeterDetect": "Area intrusion",
    "CrossLineDetect": "Line crossed",
    "ObjectDetect": "Object left or taken",
    "SoundDetect": "Sound",
    "VideoBlind": "Camera covered",
    "VideoLoss": "Camera lost",
    "StorageFailure": "Disk problem",
    "StorageLowSpace": "Disk nearly full",
}
ALERT_KIND_UNKNOWN = "Other"

ALERTS_TABLE = "alerts"
ALERTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
  kind       TEXT NOT NULL,
  channel    INTEGER NOT NULL,
  started_at TEXT NOT NULL,
  ended_at   TEXT,
  seconds    INTEGER,
  PRIMARY KEY (kind, channel, started_at)
);
CREATE INDEX IF NOT EXISTS alerts_started ON alerts (started_at DESC);
"""


# --------------------------------------------------------------------------
# Live video. The cameras send H.265, which no browser plays reliably, so
# ffmpeg turns it into something a browser can show. This machine's own chip does
# the work, so this is cheap.
#
# Two ways out, because they trade off against each other:
#   pictures  a stream of JPEGs. Shows up in under a second, no sound.
#   video     H.264 with sound, in small files the browser stitches together.
#             About four seconds behind, because it has to make a file first.
# --------------------------------------------------------------------------
LIVE_DIR = DATA_DIR / "live"
LIVE_IDLE_STOP_SECONDS = 30
LIVE_START_TIMEOUT_SECONDS = 20
LIVE_POLL_SECONDS = 0.25
LIVE_STOP_GRACE_SECONDS = 5

# Shared ffmpeg input settings. TCP, because UDP drops 4K packets on wifi.
FFMPEG_INPUT_ARGS = (
    "-nostdin",
    "-loglevel", "error",
    "-rtsp_transport", "tcp",
    "-fflags", "nobuffer",
    "-flags", "low_delay",
    # Give up on a camera that has gone silent, so we can start again.
    # Without this a dead camera hangs the read for ever. The RTSP reader
    # calls this one "timeout" and wants microseconds.
    "-timeout", str(FFMPEG_TIMEOUT_MICROSECONDS),
)
# How long to wait before trying a camera again after it drops. The recorder
# restarts itself every Sunday at midnight, so this will happen every week.
LIVE_RETRY_SECONDS = 3

# Pictures. Scaled down because a browser grid never needs more.
MJPEG_WIDTH = 960
MJPEG_FPS = 8
MJPEG_QUALITY = 6
MJPEG_BOUNDARY = "swannframe"
MJPEG_CONTENT_TYPE = f"multipart/x-mixed-replace; boundary={MJPEG_BOUNDARY}"
MJPEG_READ_BYTES = 65536
# How many pieces are held for one viewer before frames start to be
# dropped, and how many times in a row it may be full before we decide the
# viewer has gone and cut it off.
MJPEG_QUEUE_SIZE = 8
MJPEG_MAX_BEHIND = 60
# Chrome keeps a picture stream's connection open after you leave the page,
# so the server cannot tell the viewer has gone. Each open page says hello
# every so often instead. A page that stops saying hello is cut off.
LIVE_CLIENT_PARAM = "client"
LIVE_CLIENT_QUIET_SECONDS = 60
JPEG_START = b"\xff\xd8"
JPEG_END = b"\xff\xd9"

# Video with sound. videotoolbox is this machine's own encoder chip.
HLS_VIDEO_ENCODER = "h264_videotoolbox"
HLS_VIDEO_BITRATE = "2500k"
HLS_AUDIO_ENCODER = "aac"
HLS_AUDIO_BITRATE = "64k"
HLS_AUDIO_CHANNELS = 1
# 44100 on purpose. Below 24000 the browser player guesses the sound is the
# HE-AAC kind, says so to the browser, and the video then refuses to play.
HLS_AUDIO_RATE = "44100"
HLS_SEGMENT_SECONDS = 1
HLS_SEGMENT_COUNT = 10
# Force a fresh full frame every piece, or the piece length follows the
# camera and comes out at 2.4 seconds, which makes the player run dry.
HLS_KEY_FRAMES = f"expr:gte(t,n_forced*{HLS_SEGMENT_SECONDS})"
# The camera sends sound a moment after it sends picture. This pads the start
# with silence so the two line up, or the browser waits for sound that is not
# there yet and the picture freezes.
HLS_AUDIO_FILTER = "aresample=async=1:first_pts=0"
# Hand the browser the list only once this many pieces exist. One piece is not
# enough: the browser runs out before the next one is written.
HLS_START_SEGMENTS = 3
HLS_PLAYLIST = "stream.m3u8"
HLS_SEGMENT_PATTERN = "seg%05d.ts"
# delete_segments: throw away pieces nobody can still reach.
# omit_endlist: never say "the end", because live video does not end.
# No append_list: the folder is wiped at every start, so there is nothing to
# append to, and it only adds a "gap here" mark the browser has to handle.
HLS_FLAGS = "delete_segments+omit_endlist"
HLS_MEDIA_TYPE = "application/vnd.apple.mpegurl"
HLS_SEGMENT_MEDIA_TYPE = "video/mp2t"

# A single still, for thumbnails and for the snapshot button.
SNAPSHOT_MEDIA_TYPE = "image/jpeg"
SNAPSHOT_WIDTH = 1280
SNAPSHOT_QUALITY = 3

LIVE_MODE_PICTURES = "pictures"
LIVE_MODE_VIDEO = "video"
LIVE_MODES = (LIVE_MODE_PICTURES, LIVE_MODE_VIDEO)


# --------------------------------------------------------------------------
# Old video (playback)
# --------------------------------------------------------------------------
# Read off the Swann Mac app on 2026-11-08, by capturing its own loopback.
# Playback is plain RTSP on the same port as live video. There is no secret
# header and no cloud. The app's /API10/ path is for settings, not video.
#
#   rtsp://user:pass@host:554/cam/playback
#       ?channel=N&starttime=<time>Z&endtime=<time>Z&streamType=0
#
# THE TIME IS THE RECORDER'S OWN CLOCK. The trailing Z looks like UTC and is
# not. Proof: we asked for 2026-11-07T23:23:05Z and the clock burnt into the
# returned picture read 07/11/2026 23:22:57, which is the recorder's local
# time. Event times come out of the recorder's log in the same clock, so
# nothing is ever converted. Do not add a UTC step here.
PLAYBACK_PATH = "/cam/playback"
PLAYBACK_URL_TEMPLATE = (
    "rtsp://{user}:{password}@{host}:{port}" + PLAYBACK_PATH
    + "?channel={channel}&starttime={start}&endtime={end}&streamType={stream}"
)
PLAYBACK_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
# streamType is accepted and then ignored. Both 0 and 1 hand back the 4K main
# stream, so the small stream is not an option here the way it is for live.
PLAYBACK_STREAM = 0
# Playback uses the plain channel number, with no +1 offset. Live video does
# use an offset, so the two are not the same.
PLAYBACK_CHANNEL_OFFSET = 0

# The recorder hands back only the video it actually has in the window, and
# rolls the start back to the nearest key frame, about 8 seconds. Recording is
# movement triggered, so a 4 second event sits inside a longer saved block.
# Asking wide and letting the recorder trim is the way to get the whole block.
CLIP_PAD_BEFORE_SECONDS = 30
CLIP_PAD_AFTER_SECONDS = 120
# What a person may ask for by hand, so one click cannot start an hour of work.
CLIP_MAX_SECONDS = 600
CLIP_DEFAULT_SECONDS = 60

CLIPS_DIR = DATA_DIR / "clips"
CLIP_PART_SUFFIX = ".part"
CLIP_SUFFIX = ".mp4"
CLIP_MEDIA_TYPE = "video/mp4"
# Clips are rebuilt on demand, so this folder is a cache, not a library.
CLIP_KEEP_SECONDS = 24 * 60 * 60
CLIP_MAKE_TIMEOUT_SECONDS = 300

# Two sizes. "view" is small and quick, for watching in the page. "full" keeps
# the recorder's own 4K, for saving.
CLIP_QUALITY_VIEW = "view"
CLIP_QUALITY_FULL = "full"
CLIP_QUALITIES = (CLIP_QUALITY_VIEW, CLIP_QUALITY_FULL)
CLIP_VIEW_HEIGHT = 720
CLIP_VIEW_SCALE = f"scale=-2:{CLIP_VIEW_HEIGHT}"
CLIP_VIDEO_ENCODER = "h264_videotoolbox"
CLIP_VIDEO_BITRATE_VIEW = "2500k"
CLIP_VIDEO_BITRATE_FULL = "12000k"
# The cameras send G.711 a-law, which an MP4 file cannot hold. Copying the
# audio fails with "Could not find tag for codec pcm_alaw", so it is always
# re-encoded. 8000 Hz plays fine in a plain MP4; the 44100 rule is for HLS.
CLIP_AUDIO_ENCODER = "aac"
CLIP_AUDIO_BITRATE = "96k"
# Named on purpose. The file is written as "<name>.mp4.part" so a half made
# clip is never served, and ffmpeg cannot guess the format from that ending.
CLIP_FORMAT = "mp4"
CLIP_FLAGS = ("-movflags", "+faststart")
# The recorder sends old video at normal speed, so a 40 second clip takes 40
# seconds to arrive. Waiting for the whole file before showing anything means
# staring at nothing. These flags make an MP4 the browser can start playing
# while it is still being written, so it starts in about two seconds instead.
# The cost is no seek bar past what has arrived, which is why Save still
# builds a whole file.
#
# Only these two flags. This ffmpeg answers "Undefined constant" for
# default_base_is_moof and then writes no file at all.
CLIP_STREAM_FLAGS = ("-movflags", "frag_keyframe+empty_moov")
CLIP_STREAM_CHUNK = 64 * 1024
CLIP_STREAM_FIRST_BYTES_SECONDS = 30
CLIP_NAME_TEMPLATE = "camera-{channel:02d}-{stamp}-{quality}" + CLIP_SUFFIX
CLIP_STAMP_FORMAT = "%Y%m%d-%H%M%S"
# What ffmpeg says when the recorder has nothing saved for that window.
CLIP_EMPTY_MARKERS = ("Invalid data found", "Server returned 4", "404 Not Found")
CLIP_EMPTY_MESSAGE = "There is no video saved for that time."


# --------------------------------------------------------------------------
# Camera names. The recorder calls them "Channel 01" and will not take a new
# name: ChannelTitle answers Ret 100 and ignores the write. The names burned
# into the picture come from the cameras themselves, over ONVIF, not from the
# recorder. So this app keeps its own names on this machine instead.
# --------------------------------------------------------------------------
NAMES_TABLE = "camera_names"
NAMES_SCHEMA = """
CREATE TABLE IF NOT EXISTS camera_names (
  channel INTEGER PRIMARY KEY,
  name    TEXT NOT NULL
);
"""
NAME_MAX_LENGTH = 40
