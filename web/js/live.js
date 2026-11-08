/* Live view. The grid shows a stream of pictures, which is under a second
   behind. Click a camera to fill the screen, and turn sound on there, which
   swaps to real video and costs about five seconds of delay. */

/* A browser keeps a picture stream's connection open even after you leave
   the page, so this machine cannot tell you have gone. Every page makes its own
   name and sends it with each request. This machine cuts off any name that has
   stopped asking. */
const CLIENT_ID = `p${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
const CLIENT_PARAM = "client";

const API_CAMERAS = `/api/cameras?${CLIENT_PARAM}=${CLIENT_ID}`;
const API_PICTURES = (channel) =>
  `/api/live/${channel}/pictures?${CLIENT_PARAM}=${CLIENT_ID}`;
const API_SNAPSHOT = (channel, main) =>
  `/api/live/${channel}/snapshot${main ? "?main=true" : ""}`;
const API_VIDEO = (channel) => `/api/live/${channel}/video/stream.m3u8`;
const API_NAME = (channel) => `/api/cameras/${channel}/name`;

const HLS_SCRIPT = "https://cdnjs.cloudflare.com/ajax/libs/hls.js/1.5.17/hls.min.js";
const HLS_MIME = "application/vnd.apple.mpegurl";
/* This machine writes a plain playlist, not a low latency one, so leave low
   latency mode off. Start two pieces from the end to keep the lag small. */
const HLS_OPTIONS = { liveSyncDurationCount: 4, backBufferLength: 10 };
const MAX_MENDS = 3;
/* One clear pixel. Pointing a picture at this cuts off the stream it was on. */
const BLANK_PICTURE =
  "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
const GRID_PAUSED_TEXT = "Paused.";
const GRID_HIDDEN_TEXT = "One camera is full screen.";
const VIDEO_NOTE =
  "Video with sound. About six seconds behind, because this machine has to " +
  "build each piece before your browser can play it.";
const CAMERA_REFRESH_MS = 20000;
const SNAPSHOT_NAME = (label) =>
  `${label.replace(/\s+/g, "-").toLowerCase()}-${new Date()
    .toISOString()
    .slice(0, 19)
    .replace(/[:T]/g, "")}.jpg`;

const el = (id) => document.getElementById(id);
const nodes = {
  liveDot: el("live-dot"),
  pause: el("pause"),
  rename: el("rename"),
  sheetRename: el("sheet-rename"),
  problem: el("problem"),
  problemText: el("problem-text"),
  retry: el("retry"),
  grid: el("grid"),
  sheet: el("sheet"),
  sheetTitle: el("sheet-title"),
  sheetStage: el("sheet-stage"),
  sheetNote: el("sheet-note"),
  sheetSound: el("sheet-sound"),
  sheetSave: el("sheet-save"),
  sheetClose: el("sheet-close"),
};

let cameras = [];
let paused = false;
let openCamera = null;
let openPlayer = null;
let hlsReady = null;

function make(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function setProblem(message) {
  if (message) {
    nodes.problemText.textContent = message;
    nodes.problem.classList.remove("hidden");
    nodes.liveDot.className = "dot dot-bad";
  } else {
    nodes.problem.classList.add("hidden");
    nodes.liveDot.className = "dot dot-good";
  }
}

/* A fresh query string each time, so a paused stream really restarts. */
function freshPictures(channel) {
  return `${API_PICTURES(channel)}&t=${Date.now()}`;
}

function tile(camera) {
  const box = make("div", "tile");
  box.tabIndex = 0;
  box.setAttribute("role", "button");
  box.setAttribute("aria-label", `${camera.label}, open full screen`);

  const waiting = make("div", "tile-waiting", "Starting the picture.");
  box.appendChild(waiting);

  const picture = document.createElement("img");
  picture.alt = camera.label;
  picture.addEventListener("load", () => waiting.remove(), { once: true });
  picture.addEventListener("error", () => {
    waiting.textContent = "This camera is not sending a picture.";
    box.appendChild(waiting);
  });
  picture.src = freshPictures(camera.channel);
  box.appendChild(picture);

  const bar = make("div", "tile-bar");
  bar.append(
    make("span", "tile-name", camera.label),
    make("span", "spacer"),
    make(
      "span",
      "tile-state",
      camera.recording ? "Saving now" : camera.resolution || "Watching",
    ),
  );
  box.appendChild(bar);

  const open = () => openFull(camera);
  box.addEventListener("click", open);
  box.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      open();
    }
  });
  box.dataset.channel = camera.channel;
  return box;
}

function drawGrid() {
  if (openCamera) return; // One camera fills the screen, so the grid can wait.
  if (!cameras.length) {
    nodes.grid.replaceChildren(
      make("p", "note", "No cameras are plugged into the recorder."),
    );
    return;
  }
  nodes.grid.replaceChildren(...cameras.map(tile));
}

/* A browser only holds a few streams to one address at once, and a picture
   stream never ends. So always cut one off before starting another, or the
   next thing you ask for waits forever. */
function stopGrid(message) {
  for (const picture of nodes.grid.querySelectorAll("img")) {
    picture.src = BLANK_PICTURE;
    picture.remove();
  }
  for (const old of nodes.grid.querySelectorAll(".tile-waiting")) old.remove();
  for (const box of nodes.grid.querySelectorAll(".tile")) {
    box.appendChild(make("div", "tile-waiting", message));
  }
}

/* -- one camera, full screen ------------------------------------------- */
function loadHls() {
  if (hlsReady) return hlsReady;
  hlsReady = new Promise((resolve, reject) => {
    if (window.Hls) return resolve(window.Hls);
    const script = document.createElement("script");
    script.src = HLS_SCRIPT;
    script.onload = () => resolve(window.Hls);
    script.onerror = () => reject(new Error("could not load the video player"));
    document.head.appendChild(script);
  });
  return hlsReady;
}

function clearPlayer() {
  if (openPlayer && openPlayer.destroy) openPlayer.destroy();
  openPlayer = null;
  for (const picture of nodes.sheetStage.querySelectorAll("img")) {
    picture.src = BLANK_PICTURE;
  }
  nodes.sheetStage.replaceChildren();
}

function showPictures(camera) {
  clearPlayer();
  const picture = document.createElement("img");
  picture.alt = camera.label;
  picture.src = freshPictures(camera.channel);
  nodes.sheetStage.appendChild(picture);
  nodes.sheetSound.textContent = "Turn sound on";
  nodes.sheetNote.textContent =
    "Pictures only, and under a second behind. Turn sound on for real video, " +
    "which adds about five seconds of delay.";
}

/* Chrome says it can play HLS and then cannot, so the player script comes
   first and the browser's own player is only the fallback. */
async function showVideo(camera) {
  clearPlayer();
  nodes.sheetNote.textContent = "Starting the video and sound.";
  const video = document.createElement("video");
  video.controls = true;
  video.autoplay = true;
  video.muted = false;
  video.playsInline = true;
  nodes.sheetStage.appendChild(video);

  const url = API_VIDEO(camera.channel);
  try {
    let Hls = null;
    try {
      Hls = await loadHls();
    } catch (ignored) {
      Hls = null;
    }
    if (Hls && Hls.isSupported()) {
      const player = new Hls(HLS_OPTIONS);
      let mends = 0;
      player.on(Hls.Events.ERROR, (event, data) => {
        if (!data.fatal) return;
        // Try to mend it a few times before giving up on it.
        if (mends < MAX_MENDS) {
          mends += 1;
          nodes.sheetNote.textContent = "The video hiccupped. Starting it again.";
          if (data.type === Hls.ErrorTypes.NETWORK_ERROR) player.startLoad();
          else player.recoverMediaError();
          return;
        }
        nodes.sheetNote.textContent =
          `The video stopped. ${data.details}. Turn sound off to go back to pictures.`;
      });
      player.loadSource(url);
      player.attachMedia(video);
      openPlayer = player;
    } else if (video.canPlayType(HLS_MIME)) {
      video.src = url;
    } else {
      throw new Error("this browser cannot play it");
    }

    nodes.sheetSound.textContent = "Turn sound off";
    try {
      await video.play();
      nodes.sheetNote.textContent = VIDEO_NOTE;
    } catch (blocked) {
      video.muted = true;
      await video.play().catch(() => {});
      nodes.sheetNote.textContent =
        "The browser blocked the sound. Press the speaker on the player to " +
        "turn it on. " + VIDEO_NOTE;
    }
  } catch (error) {
    nodes.sheetNote.textContent = `Could not start the video. ${error.message}`;
    showPictures(camera);
  }
}

function openFull(camera) {
  stopGrid(GRID_HIDDEN_TEXT);
  openCamera = camera;
  nodes.sheetTitle.textContent = camera.label;
  nodes.sheet.classList.remove("hidden");
  showPictures(camera);
}

function closeFull() {
  clearPlayer();
  nodes.sheet.classList.add("hidden");
  openCamera = null;
  if (!paused) drawGrid();
}

nodes.sheetClose.addEventListener("click", closeFull);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && openCamera) closeFull();
});

nodes.sheetSound.addEventListener("click", () => {
  if (!openCamera) return;
  const hasVideo = nodes.sheetStage.querySelector("video");
  if (hasVideo) showPictures(openCamera);
  else showVideo(openCamera);
});

nodes.sheetSave.addEventListener("click", async () => {
  if (!openCamera) return;
  const label = nodes.sheetSave.textContent;
  nodes.sheetSave.disabled = true;
  nodes.sheetSave.textContent = "Saving.";
  try {
    const response = await fetch(API_SNAPSHOT(openCamera.channel, true));
    if (!response.ok) throw new Error(await response.text());
    const blob = await response.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = SNAPSHOT_NAME(openCamera.label);
    link.click();
    URL.revokeObjectURL(link.href);
    nodes.sheetSave.textContent = "Saved";
  } catch (error) {
    nodes.sheetSave.textContent = "Could not save";
    nodes.sheetNote.textContent = `The still did not save. ${error.message}`;
  } finally {
    window.setTimeout(() => {
      nodes.sheetSave.textContent = label;
      nodes.sheetSave.disabled = false;
    }, 3000);
  }
});

/* -- naming a camera ---------------------------------------------------- */
async function renameCamera(camera) {
  const wanted = window.prompt(
    `What should camera ${camera.channel + 1} be called?\n\n` +
      "This name is kept on this machine. The recorder will not take a new name, " +
      "and the name burned into the picture belongs to the camera itself.",
    camera.named ? camera.label : "",
  );
  if (wanted === null) return;
  try {
    const response = await fetch(API_NAME(camera.channel), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: wanted }),
    });
    if (!response.ok) throw new Error(response.status);
    await loadCameras();
    drawGrid();
    if (openCamera && openCamera.channel === camera.channel) {
      const fresh = cameras.find((c) => c.channel === camera.channel);
      if (fresh) {
        openCamera = fresh;
        nodes.sheetTitle.textContent = fresh.label;
      }
    }
  } catch (error) {
    setProblem(`Could not save the name. ${error.message}`);
  }
}

nodes.rename.addEventListener("click", async () => {
  for (const camera of cameras) {
    // eslint-disable-next-line no-await-in-loop
    await renameCamera(camera);
  }
});

nodes.sheetRename.addEventListener("click", () => {
  if (openCamera) renameCamera(openCamera);
});

/* -- pause -------------------------------------------------------------- */
nodes.pause.addEventListener("click", () => {
  paused = !paused;
  nodes.pause.textContent = paused ? "Play" : "Pause";
  if (paused) stopGrid(GRID_PAUSED_TEXT);
  else drawGrid();
});

/* -- start -------------------------------------------------------------- */
async function loadCameras() {
  try {
    const response = await fetch(API_CAMERAS, { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || response.status);
    setProblem(null);
    const before = cameras.map((c) => `${c.channel}:${c.recording}:${c.label}`).join(",");
    cameras = data.cameras;
    const after = cameras.map((c) => `${c.channel}:${c.recording}:${c.label}`).join(",");
    // Only redraw when something changed, or every tile would restart.
    if (before !== after && !paused) drawGrid();
  } catch (error) {
    setProblem(`Could not ask the recorder which cameras are plugged in. ${error.message}`);
  }
}

nodes.retry.addEventListener("click", async () => {
  await loadCameras();
  drawGrid();
});

(async function start() {
  await loadCameras();
  drawGrid();
  window.setInterval(loadCameras, CAMERA_REFRESH_MS);
})();
