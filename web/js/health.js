/* Health page. Asks the server for the recorder's state and fills the page in. */

const API_HEALTH = "/api/health";
const REFRESH_MS = 10000;
const CLOCK_TICK_MS = 1000;
const FRESH_SECONDS = 20;
const MEGABYTES_IN_GIGABYTE = 1024;
const PERCENT_FULL = 100;
const SHORT_DATE_LENGTH = 16;
const MILLISECONDS_IN_DAY = 24 * 60 * 60 * 1000;

const el = (id) => document.getElementById(id);

const nodes = {
  liveDot: el("live-dot"),
  checked: el("checked"),
  clock: el("clock"),
  problem: el("problem"),
  problemText: el("problem-text"),
  retry: el("retry"),
  diskState: el("disk-state"),
  diskUsed: el("disk-used"),
  diskFree: el("disk-free"),
  diskTotal: el("disk-total"),
  diskKept: el("disk-kept"),
  diskMeter: el("disk-meter"),
  diskNote: el("disk-note"),
  diskFoot: el("disk-foot"),
  cameraCount: el("camera-count"),
  cameraRows: el("camera-rows"),
  cameraNote: el("camera-note"),
  recorderFacts: el("recorder-facts"),
};

let lastClock = null;
let lastClockAt = 0;

function space(gigabytes) {
  if (gigabytes === null || gigabytes === undefined) return "--";
  if (gigabytes < 1) return `${Math.round(gigabytes * MEGABYTES_IN_GIGABYTE)} MB`;
  return `${gigabytes.toFixed(2)} GB`;
}

function bitrate(kbps) {
  if (!kbps) return "no video";
  return `${kbps} kbit/s`;
}

/* How far back the video goes, from the oldest and newest clip times.
   The recorder's own FreeTotalTime is not used here. It swings from 200 to 1155
   hours within a day, so it is a guess at room left, not footage held. */
function spanText(oldest, newest) {
  if (!oldest || !newest) return "--";
  const from = new Date(oldest.replace(" ", "T"));
  const to = new Date(newest.replace(" ", "T"));
  if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) return "--";
  const days = Math.round((to - from) / MILLISECONDS_IN_DAY);
  if (days < 1) return "under a day";
  return days === 1 ? "1 day" : `${days} days`;
}

function shortDate(raw) {
  if (!raw) return null;
  return raw.slice(0, SHORT_DATE_LENGTH);
}

function setProblem(message) {
  if (message) {
    nodes.problemText.textContent = message;
    nodes.problem.classList.remove("hidden");
  } else {
    nodes.problem.classList.add("hidden");
  }
}

function row(camera) {
  const line = document.createElement("div");
  line.className = camera.inUse ? "row" : "row row-idle";

  const dot = document.createElement("span");
  dot.className = camera.recording
    ? "dot dot-small"
    : camera.inUse
      ? "dot dot-small dot-good"
      : "dot dot-small dot-idle";
  line.appendChild(dot);

  const name = document.createElement("span");
  name.className = "row-name";
  const title = document.createElement("span");
  title.textContent = camera.label;
  name.appendChild(title);
  // The recorder often names a channel after its own number, so do not say it twice.
  const channelText = `Channel ${camera.index + 1}`;
  if (camera.label.replace(/0(\d)/, "$1") !== channelText) {
    const sub = document.createElement("span");
    sub.className = "row-sub";
    sub.textContent = channelText;
    name.appendChild(sub);
  }
  line.appendChild(name);

  const rate = document.createElement("span");
  rate.className = "mono row-sub";
  rate.textContent = bitrate(camera.bitrateKbps);
  line.appendChild(rate);

  line.appendChild(Object.assign(document.createElement("span"), {
    className: "spacer",
  }));

  const state = document.createElement("span");
  state.className = "row-state";
  state.textContent = camera.recording ? "Saving now" : "Watching, nothing to save";
  line.appendChild(state);

  return line;
}

/* The spare sockets are not interesting one by one, so sum them up. */
function emptyRow(count) {
  const line = document.createElement("div");
  line.className = "row row-idle";
  const dot = document.createElement("span");
  dot.className = "dot dot-small dot-idle";
  const text = document.createElement("span");
  text.textContent = count === 1 ? "1 socket is empty" : `${count} sockets are empty`;
  line.append(dot, text);
  return line;
}

function fact(key, value) {
  const line = document.createElement("div");
  line.className = "kv";
  const k = document.createElement("span");
  k.className = "kv-key";
  k.textContent = key;
  const v = document.createElement("span");
  v.className = "kv-value";
  v.textContent = value || "not given";
  line.append(k, v);
  return line;
}

function diskText(disk, overwrite) {
  if (!disk) return "The recorder did not report a disk.";
  if (disk.percentUsed === null || disk.percentUsed === undefined) {
    return "The disk is fitted, but the recorder did not say how full it is.";
  }
  if (disk.isFull && overwrite) {
    return "The disk is full, so the oldest video is written over. That is how it is meant to work. A bigger disk would keep more days.";
  }
  if (disk.isFull && !overwrite) {
    return "The disk is full and writing over the oldest video is switched off. New video is not being saved. Turn that setting on, or fit a bigger disk.";
  }
  return `${disk.percentUsed}% of the disk is used.`;
}

function cameraText(data) {
  if (!data.recordingScheduled) {
    return "No recording is scheduled, so nothing is being saved. Check the record schedule on the recorder.";
  }
  const saving = data.channels.filter((c) => c.recording).length;
  if (saving > 0) {
    return "Your cameras save video when something moves. Right now something is moving.";
  }
  return "Your cameras save video when something moves. Nothing is moving, so nothing is being saved this second. That is normal.";
}

function paint(data) {
  setProblem(data.reachable ? null : data.error || "The recorder did not answer.");
  nodes.liveDot.className = data.reachable ? "dot dot-good" : "dot dot-bad";

  const disk = data.disk;
  nodes.diskState.textContent = disk && disk.state
    ? (disk.healthy ? "Healthy" : `Reports ${disk.state}`)
    : "";
  nodes.diskUsed.textContent = space(disk ? disk.usedGb : null);
  nodes.diskFree.textContent = space(disk ? disk.freeGb : null);
  nodes.diskTotal.textContent = space(disk ? disk.totalGb : null);
  nodes.diskKept.textContent = disk
    ? spanText(disk.oldestVideo, disk.newestVideo)
    : "--";
  const percent = disk && disk.percentUsed !== null
    ? Math.min(disk.percentUsed, PERCENT_FULL)
    : 0;
  nodes.diskMeter.style.setProperty("--fill", `${percent}%`);
  nodes.diskMeter.className = disk && disk.isFull ? "meter-fill" : "meter-fill meter-fill-good";
  nodes.diskNote.textContent = diskText(disk, data.overwriteOldest);

  const footParts = [];
  if (disk && disk.oldestVideo) footParts.push(`Oldest  ${shortDate(disk.oldestVideo)}`);
  if (disk && disk.newestVideo) footParts.push(`Newest  ${shortDate(disk.newestVideo)}`);
  if (disk && disk.model) footParts.push(disk.model);
  if (disk && disk.spaceText) footParts.push(`Recorder says ${disk.spaceText}`);
  nodes.diskFoot.replaceChildren(...footParts.map((text) => {
    const span = document.createElement("span");
    span.textContent = text;
    return span;
  }));

  nodes.cameraCount.textContent =
    `${data.camerasInUse} of ${data.channelCount} sockets in use`;
  const used = data.channels.filter((c) => c.inUse);
  const spare = data.channels.length - used.length;
  const cameraRows = used.map(row);
  if (spare > 0) cameraRows.push(emptyRow(spare));
  nodes.cameraRows.replaceChildren(...cameraRows);
  nodes.cameraNote.textContent = cameraText(data);

  const device = data.device || {};
  nodes.recorderFacts.replaceChildren(
    fact("Firmware", device.firmware),
    fact("Hardware", device.hardware),
    fact("Built", device.build_time),
    fact("Serial number", device.serial),
    fact("On since restart", device.uptimeText),
    fact("Total time running", device.totalRunText),
    fact("Last restart", device.boot_time || "not in the log"),
    fact("Camera sockets", String(data.channelCount)),
    fact("Recorder clock", device.recorder_clock),
  );

  if (device.recorder_clock) {
    lastClock = device.recorder_clock;
    lastClockAt = Date.now();
  }
}

function tickClock() {
  if (!lastClock) return;
  const elapsed = Math.floor((Date.now() - lastClockAt) / CLOCK_TICK_MS);
  const base = new Date(lastClock.replace(" ", "T"));
  if (Number.isNaN(base.getTime())) {
    nodes.clock.textContent = lastClock;
    return;
  }
  base.setSeconds(base.getSeconds() + elapsed);
  nodes.clock.textContent = base.toTimeString().slice(0, 8);
}

function tickChecked(at) {
  const seconds = Math.floor((Date.now() - at) / CLOCK_TICK_MS);
  if (seconds < FRESH_SECONDS) {
    nodes.checked.textContent = seconds <= 1 ? "Checked just now" : `Checked ${seconds} seconds ago`;
  } else {
    nodes.checked.textContent = `Checked ${seconds} seconds ago`;
  }
}

let lastCheckedAt = Date.now();

async function refresh() {
  try {
    const response = await fetch(API_HEALTH, { cache: "no-store" });
    const data = await response.json();
    paint(data);
  } catch (error) {
    setProblem("The page could not reach the server on this machine.");
    nodes.liveDot.className = "dot dot-bad";
  } finally {
    lastCheckedAt = Date.now();
  }
}

nodes.retry.addEventListener("click", refresh);
setInterval(refresh, REFRESH_MS);
setInterval(() => {
  tickClock();
  tickChecked(lastCheckedAt);
}, CLOCK_TICK_MS);
refresh();
