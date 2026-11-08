# Better Swann UI

A replacement for the Swann Security app, for your own machine.

It talks straight to a Swann recorder on your home network. Nothing goes to the
internet. No account, no cloud, no app store.

## What you get

- **Live view.** Every camera in a grid. Click one to fill the screen. Sound on
  a button. Save a still.
- **Old video.** Pick a moment, or any time at all, and watch it. Save it as an
  MP4. No cloud and no Swann app.
- **Alerts.** Everything the cameras have seen, newest first. The recorder
  forgets after about two and a half days. This keeps the lot.
- **Health.** Disk, uptime, firmware, which cameras are plugged in.
- **Settings.** All 40 screens the recorder's own web page has, and a few it
  does not. Read and write.
- **Backup.** Save every recorder setting to a file before you change anything.
- **An MCP server.** So you can ask an LLM to do all of the above.

## About old video

There is no clip list on these recorders, and you do not need one. You ask for
a time window and the recorder hands back whatever it saved. This app lists
every moment the cameras spotted, so you click a time instead of hunting
through a blank timeline.

Two things to expect. The recorder sends old video at normal speed, so a 40
second clip takes 40 seconds to arrive. Watching starts in about three seconds
anyway, because the clip plays while it downloads. Saving waits for the whole
file, because a saved file has to be seekable.

## Will it work with my recorder?

It was built against a Swann ADVANX, firmware V1.0.49-8ADVANX. Underneath,
that is Xiongmai (XMeye) firmware, which Swann, and a lot of other brands, put
their badge on.

It will probably work if your recorder:

- answers on port 85 with a page that asks you to log in, and
- has port 554 open for live video.

Run `make check` and it will tell you in about five seconds.

## Setting it up

You need Python 3.12 or newer and ffmpeg. On a Mac:

```
brew install python ffmpeg
```

Then:

```
git clone https://github.com/codevera-ai/better-swann-ui.git
cd better-swann-ui
make setup
```

That makes a `.env` file for you. Open it and fill in two things:

```
SWANN_HOST=192.168.1.100     your recorder's address
SWANN_PASS=                  your recorder's password
```

Do not know the address? It is in the recorder's own menu under Network, or in
your router's list of devices.

Now check it works:

```
make check
```

You should see your firmware, your disk and your cameras. If you do, start it:

```
make run
```

Open http://127.0.0.1:8750.

To stop it: `make stop`.

## Every command

| Command | What it does |
| --- | --- |
| `make setup` | Install everything and make your `.env` |
| `make check` | Ask the recorder if it is there. Changes nothing |
| `make run` | Start the app in the background |
| `make dev` | Start it in this window, reloading when you edit a file |
| `make stop` | Stop it |
| `make backup` | Save every recorder setting to a file |
| `make mcp-setup` | Install the MCP server |

## Driving it with an LLM

There is an MCP server, so Claude or any MCP client can read your cameras and
change your settings by asking.

```
make mcp-setup
claude mcp add swann --scope local -- $(pwd)/mcp_server/run.sh
```

The app has to be running (`make run`). Then you can say things like:

- "What has the back camera seen today?"
- "Take a picture from camera 2."
- "How full is the disk?"
- "Turn the email alerts off."

It has 15 tools. The two that can stop your cameras recording, restart and
factory reset, will not fire unless you say the word out loud.

## Things worth knowing

- **One login.** The recorder only keeps one login per user. If this app is
  running, the Swann phone app may get pushed out, and the other way round.
  Give the app its own recorder account if that bothers you.
- **Back up before you change settings.** `make backup` writes every setting to
  `data/config-backups/`. That folder holds real passwords, so it is git
  ignored. Keep it that way.
- **The recorder sometimes says yes and does nothing.** Camera names are the
  known case. So the app reads every setting back after writing it, and tells
  you when the two do not match.
- **Movement only.** Most of these recorders only save when something moves. So
  "not recording" on the health page is normal, not a fault.

## What is inside

```
swann/config.py    every constant, loads .env
swann/cgi.py       the recorder's JSON API on port 85
swann/session.py   one shared login, kept alive
swann/health.py    turns recorder replies into something readable
swann/settings.py  the 40 settings screens, read and write
swann/alerts.py    copies the recorder's log into SQLite, forever
swann/live.py      ffmpeg: pictures for the grid, video with sound
swann/playback.py  old video: any time window, as a clip you can save
swann/users.py     accounts, with every password stripped out
swann/backup.py    reads every setting to a file
app/main.py        the web routes
web/               the pages
mcp_server/        the MCP server
```

Every number, name and timeout lives in `swann/config.py`. Nothing else in the
project holds a literal value.

## How it was worked out

There is no public documentation for this protocol. Everything here was read off
a real recorder, or off the recorder's own web page. The notes are in the repo:

- `PARITY-evidence.md`, all 42 screens of the recorder's own page, every
  config name, and which ones answer.
- `PLAN-evidence.md`, what the recorder can and cannot do, with the proof.
- `BUILD-PLAN-evidence.md`, how the app is put together and why.

## Licence

MIT. Do what you like with it.

It is not made by, or connected to, Swann. "Swann" is their name, not mine.
