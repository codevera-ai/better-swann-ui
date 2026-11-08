/* Clips. Old video off the recorder.

   The recorder keeps no list of clips, so the movement alerts this machine
   has stored are the list. Each alert sits inside a longer saved block, and
   the recorder trims whatever window we ask for down to what it really has.

   The recorder sends old video at normal speed, so the server streams it
   while it arrives. Playing starts in about three seconds instead of waiting
   for the whole clip. Saving builds a whole file first, so it can be seeked. */

const API_CLIPS = "/api/clips";
const API_CLIP_FILE = (channel) => `/api/clips/${channel}/clip.mp4`;
const API_HEALTH = "/api/health";

const LENGTH_CHOICES = [15, 30, 60, 120, 300, 600];
const DEFAULT_LENGTH = 60;
const SECONDS_IN_MINUTE = 60;
const STARTING_TEXT = "Getting it off the recorder";
const SAVING_TEXT = "Building the file, this takes as long as the clip";
const SAVE_RESET_MS = 4000;
const NO_VIDEO_STATUS = 404;

const el = (id) => document.getElementById(id);
const nodes = {
  liveDot: el("live-dot"),
  kept: el("kept"),
  problem: el("problem"),
  problemText: el("problem-text"),
  retry: el("retry"),
  video: el("video"),
  playerEmpty: el("player-empty"),
  playing: el("playing"),
  save: el("save"),
  camera: el("camera"),
  day: el("day"),
  count: el("count"),
  list: el("list"),
  rangeNote: el("range-note"),
  when: el("when"),
  howlong: el("howlong"),
  watch: el("watch"),
};

let state = { channel: 0, day: null, cameras: [], days: [], clips: [], current: null };

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

function lengthText(seconds) {
  if (seconds < SECONDS_IN_MINUTE) {
    return seconds === 1 ? "1 second" : `${seconds} seconds`;
  }
  const minutes = seconds / SECONDS_IN_MINUTE;
  return minutes === 1 ? "1 minute" : `${minutes} minutes`;
}

function dayText(day) {
  const when = new Date(`${day}T00:00:00`);
  const today = new Date();
  const yesterday = new Date(today.getTime() - 86400000);
  const same = (a, b) => a.toDateString() === b.toDateString();
  if (same(when, today)) return "Today";
  if (same(when, yesterday)) return "Yesterday";
  return when.toLocaleDateString("en-GB", {
    weekday: "short", day: "numeric", month: "short",
  });
}

function clockText(stamp) {
  return stamp.slice(11, 19);
}

/* The alert rows carry the recorder's own label, like "Camera 1". The name
   you gave the camera lives on this machine, so take it from there. */
function cameraLabel(channel) {
  const found = state.cameras.find((camera) => camera.channel === channel);
  return found ? found.label : `Camera ${channel + 1}`;
}

function fill(select, items, chosen) {
  select.replaceChildren();
  items.forEach(({ value, text }) => {
    const option = make("option", null, text);
    option.value = value;
    if (String(value) === String(chosen)) option.selected = true;
    select.append(option);
  });
}

/* -- playing ------------------------------------------------------------ */

function clipUrl(clip, extra = {}) {
  const url = new URL(API_CLIP_FILE(clip.channel), window.location.origin);
  url.searchParams.set("start", clip.startedAt);
  if (clip.endedAt) url.searchParams.set("end", clip.endedAt);
  if (clip.alert !== false) url.searchParams.set("alert", "true");
  Object.entries(extra).forEach(([key, value]) =>
    url.searchParams.set(key, value));
  return url.toString();
}

async function play(clip, title) {
  state.current = clip;
  nodes.playerEmpty.classList.add("hidden");
  nodes.save.classList.remove("hidden");
  nodes.save.disabled = false;
  nodes.save.textContent = "Save this clip";
  nodes.playing.textContent = `${title}. ${STARTING_TEXT}`;
  setProblem(null);

  nodes.video.src = clipUrl(clip);
  try {
    await nodes.video.play();
    nodes.playing.textContent = title;
  } catch (error) {
    // Autoplay can be refused. The controls still work.
    nodes.playing.textContent = title;
  }
}

nodes.video.addEventListener("error", async () => {
  if (!state.current) return;
  // Ask again plainly, so the server's own words reach the page.
  try {
    const reply = await fetch(clipUrl(state.current), { method: "GET" });
    const body = await reply.json().catch(() => ({}));
    setProblem(body.detail || "That clip would not play.");
  } catch {
    setProblem("That clip would not play.");
  }
  nodes.playing.textContent = "Nothing playing";
});

nodes.save.addEventListener("click", () => {
  if (!state.current) return;
  nodes.save.disabled = true;
  nodes.save.textContent = SAVING_TEXT;
  window.location.href = clipUrl(state.current, {
    save: "true", quality: "full",
  });
  window.setTimeout(() => {
    nodes.save.disabled = false;
    nodes.save.textContent = "Save this clip";
  }, SAVE_RESET_MS);
});

/* -- the list ----------------------------------------------------------- */

function drawList() {
  nodes.list.replaceChildren();
  if (!state.clips.length) {
    nodes.list.append(make("p", "note", "Nothing was seen on that day."));
    nodes.count.textContent = "";
    return;
  }
  nodes.count.textContent = `${state.clips.length} moments`;

  state.clips.forEach((clip) => {
    const row = make("button", "row row-tap");
    row.type = "button";
    row.append(make("span", "row-time", clockText(clip.startedAt)));
    row.append(make("span", "row-kind", clip.label));
    row.append(make("span", "spacer"));
    row.append(make("span", "row-length", lengthText(clip.seconds || 1)));
    row.addEventListener("click", () => {
      document.querySelectorAll(".row-tap[aria-current]").forEach((old) =>
        old.removeAttribute("aria-current"));
      row.setAttribute("aria-current", "true");
      play(clip, `${cameraLabel(clip.channel)}, `
        + `${dayText(clip.startedAt.slice(0, 10))} at ${clockText(clip.startedAt)}`);
    });
    nodes.list.append(row);
  });
}

async function load() {
  try {
    const url = new URL(API_CLIPS, window.location.origin);
    url.searchParams.set("channel", state.channel);
    if (state.day) url.searchParams.set("day", state.day);
    const reply = await fetch(url);
    if (!reply.ok) throw new Error(`the server said ${reply.status}`);
    const data = await reply.json();

    state.cameras = data.cameras;
    state.days = data.days;
    state.clips = data.clips;
    if (!state.day && data.days.length) state.day = data.days[0].day;

    fill(nodes.camera, state.cameras.map((camera) => ({
      value: camera.channel, text: camera.label,
    })), state.channel);
    fill(nodes.day, state.days.map((day) => ({
      value: day.day, text: `${dayText(day.day)} (${day.count})`,
    })), state.day);

    // The very first load asks with no day, so it comes back unfiltered and
    // the newest day gets picked here instead.
    if (state.day) {
      state.clips = state.clips.filter((clip) =>
        clip.startedAt.startsWith(state.day));
    }
    drawList();
    setProblem(null);
  } catch (error) {
    setProblem(`The clip list could not be read. ${error.message}`);
  }
}

/* -- any time ----------------------------------------------------------- */

async function loadRange() {
  try {
    const reply = await fetch(API_HEALTH);
    if (!reply.ok) return;
    const data = await reply.json();
    const disk = data.disk || {};
    if (!disk.oldestVideo || !disk.newestVideo) return;
    nodes.rangeNote.textContent =
      `The recorder holds video from ${disk.oldestVideo} to ${disk.newestVideo}.`;
    nodes.when.min = disk.oldestVideo.replace(" ", "T");
    nodes.when.max = disk.newestVideo.replace(" ", "T");
    nodes.when.value = disk.newestVideo.replace(" ", "T");
  } catch {
    // The picker still works without bounds.
  }
}

nodes.watch.addEventListener("click", () => {
  if (!nodes.when.value) {
    setProblem("Pick a start time first.");
    return;
  }
  const start = nodes.when.value.replace("T", " ");
  const seconds = Number(nodes.howlong.value);
  const end = new Date(new Date(nodes.when.value).getTime() + seconds * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  const endText = `${end.getFullYear()}-${pad(end.getMonth() + 1)}-${pad(end.getDate())}`
    + ` ${pad(end.getHours())}:${pad(end.getMinutes())}:${pad(end.getSeconds())}`;
  play(
    { channel: state.channel, startedAt: start, endedAt: endText, alert: false },
    `From ${start}, ${lengthText(seconds)}`,
  );
});

/* -- start -------------------------------------------------------------- */

nodes.camera.addEventListener("change", () => {
  state.channel = Number(nodes.camera.value);
  state.day = null;
  load();
});
nodes.day.addEventListener("change", () => {
  state.day = nodes.day.value;
  load();
});
nodes.retry.addEventListener("click", () => {
  setProblem(null);
  load();
});

fill(nodes.howlong, LENGTH_CHOICES.map((seconds) => ({
  value: seconds, text: lengthText(seconds),
})), DEFAULT_LENGTH);

load();
loadRange();
