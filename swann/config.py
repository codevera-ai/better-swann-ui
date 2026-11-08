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
        "note": "The name and clock drawn on top of each camera's picture.",
        "configs": ("AVEnc.VideoWidget", "fVideo.OsdLogo"),
    },
    {
        "key": "privacy",
        "group": "Cameras",
        "title": "Privacy blocks",
        "note": "Black boxes that hide part of a camera's view, saved with the video.",
        "configs": ("AVEnc.VideoWidget",),
    },
    {
        "key": "monitor",
        "group": "Cameras",
        "title": "Recorder's own screen",
        "note": "The layout on the monitor plugged into the recorder, not this page.",
        "configs": ("fVideo.GUISet", "fVideo.Tour", "fVideo.VideoOut"),
    },
    # -- Recording --------------------------------------------------------
    {
        "key": "recording",
        "group": "Recording",
        "title": "Recording and schedule",
        "note": "When each camera records, and what triggers it.",
        "configs": ("Record", "Custom.SwannSpecialInfo.InfoRecord"),
    },
    {
        "key": "quality",
        "group": "Recording",
        "title": "Video quality",
        "note": "Resolution, frame rate and bit rate, for the main and the second stream.",
        "configs": ("NetUse.DigitalEncode",),
        "per_channel": True,
    },
    {
        "key": "quality-limits",
        "group": "Recording",
        "title": "What the cameras allow",
        "note": "The highest settings each camera will accept. Read only.",
        "configs": ("NetUse.DigitalAbility",),
        "per_channel": True,
        "read_only": True,
    },
    {
        "key": "stills",
        "group": "Recording",
        "title": "Still pictures",
        "note": "Snapshots the recorder saves beside the video, and when.",
        "configs": ("Custom.SwannSNAP",),
    },
    # -- Alerts -----------------------------------------------------------
    {
        "key": "motion",
        "group": "Alerts",
        "title": "Movement",
        "note": "Movement detection per camera, and what it sets off.",
        "configs": ("Detect.MotionDetect", "Custom.SwannSpecialInfo.InfoAlarm"),
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
        "note": "Alerts when something enters a shape you draw. Swann calls this PID.",
        "configs": ("Detect.Analyze_Swann_Pid",),
    },
    {
        "key": "line",
        "group": "Alerts",
        "title": "Line crossing",
        "note": "Alerts when something crosses a line you draw. Swann calls this LCD.",
        "configs": ("Detect.Analyze_Swann_Lcd",),
    },
    {
        "key": "objects",
        "group": "Alerts",
        "title": "Objects left or taken",
        "note": "Alerts when something appears or disappears. Swann calls this SOD.",
        "configs": ("Detect.Analyze_Swann_Sod",),
    },
    {
        "key": "analytics-schedule",
        "group": "Alerts",
        "title": "Smart alert schedule",
        "note": "The hours when the smarter detection is switched on.",
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
        "note": "Every feature the firmware says it has. Read only.",
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

FIELD_NOTES = {
    "OverWrite": "Leave this on, or recording stops when the disk fills up.",
    "HostIP": "Change this and this page stops loading until you use the new address.",
    "Recievers": "The recorder spells this field without the second c. That is its spelling, not a typo here.",
    "AutoRebootDay": "The recorder restarts itself on this day. That is normal.",
    "Nat": "This is how the Swann app reaches the recorder from outside your home.",
}

FIELD_CHOICES = {
    "AutoRebootDay": (
        "Everyday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
        "Never",
    ),
    "OverWrite": ("OverWrite", "StopRecord"),
    "VideoOutPut": ("Auto", "VGA", "HDMI", "LCD", "BT656", "TV"),
}


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
