/* Alerts. Reads what this machine has stored, which it copies from the recorder's
   own log every few minutes. The recorder forgets after about two and a half
   days. This machine does not. */

const API_ALERTS = "/api/alerts";
const API_SYNC = "/api/alerts/sync";

const REFRESH_MS = 30000;
const LIMIT_CHOICES = [100, 200, 500, 1000, 2000];
const DEFAULT_LIMIT = 200;
const ANY = "";
const SECONDS_IN_MINUTE = 60;
const SECONDS_IN_HOUR = 3600;
const MS_IN_DAY = 24 * 60 * 60 * 1000;
const BUTTON_RESET_MS = 4000;

const el = (id) => document.getElementById(id);
const nodes = {
  liveDot: el("live-dot"),
  checked: el("checked"),
  sync: el("sync"),
  problem: el("problem"),
  problemText: el("problem-text"),
  retry: el("retry"),
  figures: el("figures"),
  spanNote: el("span-note"),
  kind: el("kind"),
  camera: el("camera"),
  limit: el("limit"),
  count: el("count"),
  list: el("list"),
};

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

function lengthText(seconds, stillGoing) {
  if (stillGoing) return "still going";
  if (seconds === null || seconds === undefined) return "not known";
  if (seconds < SECONDS_IN_MINUTE) return seconds === 1 ? "1 second" : `${seconds} seconds`;
  if (seconds < SECONDS_IN_HOUR) {
    const minutes = Math.round(seconds / SECONDS_IN_MINUTE);
    return minutes === 1 ? "1 minute" : `${minutes} minutes`;
  }
  const hours = (seconds / SECONDS_IN_HOUR).toFixed(1);
  return `${hours} hours`;
}

function dayText(raw) {
  if (!raw) return "";
  const when = new Date(raw.replace(" ", "T"));
  if (Number.isNaN(when.getTime())) return raw;
  const today = new Date();
  const sameDay = when.toDateString() === today.toDateString();
  const yesterday = new Date(today.getTime() - MS_IN_DAY);
  if (sameDay) return "Today";
  if (when.toDateString() === yesterday.toDateString()) return "Yesterday";
  return when.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
}

function figure(key, value) {
  const box = make("div", "figure");
  box.append(
    make("span", "figure-key", key),
    make("span", "figure-value figure-value-big", value),
  );
  return box;
}

function fillPicker(picker, options, keep) {
  const wanted = keep === undefined ? picker.value : keep;
  picker.replaceChildren();
  for (const [value, label] of options) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    if (String(value) === String(wanted)) option.selected = true;
    picker.appendChild(option);
  }
}

function drawSummary(summary) {
  nodes.figures.replaceChildren(
    figure("Alerts kept", String(summary.total)),
    ...summary.kinds.slice(0, 3).map((k) => figure(k.label, String(k.count))),
    ...summary.cameras.map((c) => figure(c.label, String(c.count))),
  );
  if (summary.oldest && summary.newest) {
    nodes.spanNote.textContent =
      `Oldest ${summary.oldest}, newest ${summary.newest}. ` +
      "The recorder only remembers about two and a half days. This machine keeps them all.";
  } else {
    nodes.spanNote.textContent =
      "Nothing stored yet. This machine copies the recorder's log every five minutes.";
  }

  fillPicker(nodes.kind, [
    [ANY, "Everything"],
    ...summary.kinds.map((k) => [k.kind, `${k.label} (${k.count})`]),
  ]);
  fillPicker(nodes.camera, [
    [ANY, "Any camera"],
    ...summary.cameras.map((c) => [c.channel, `${c.label} (${c.count})`]),
  ]);
}

function drawList(alerts) {
  if (!alerts.length) {
    nodes.list.replaceChildren(make("p", "note", "No alerts match that choice."));
    return;
  }
  const rows = make("div", "rows");
  let lastDay = null;
  for (const alert of alerts) {
    const day = dayText(alert.startedAt);
    if (day !== lastDay) {
      rows.appendChild(make("div", "side-head", day));
      lastDay = day;
    }

    const line = make("div", "row");
    const dot = make("span", alert.stillGoing ? "dot dot-small" : "dot dot-small dot-good");
    line.appendChild(dot);

    const name = make("span", "row-name");
    name.append(
      make("span", "", alert.label),
      make("span", "row-sub", alert.camera),
    );
    line.appendChild(name);

    line.appendChild(make("span", "mono row-sub", alert.startedAt.slice(11)));
    line.appendChild(make("span", "spacer"));
    line.appendChild(
      make("span", "row-state", lengthText(alert.seconds, alert.stillGoing)),
    );
    rows.appendChild(line);
  }
  nodes.list.replaceChildren(rows);
}

async function load() {
  const params = new URLSearchParams({ limit: nodes.limit.value || DEFAULT_LIMIT });
  if (nodes.kind.value) params.set("kind", nodes.kind.value);
  if (nodes.camera.value !== ANY) params.set("channel", nodes.camera.value);
  try {
    const response = await fetch(`${API_ALERTS}?${params}`, { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || response.status);
    setProblem(null);
    drawSummary(data.summary);
    drawList(data.alerts);
    nodes.count.textContent = `showing ${data.alerts.length}`;
    nodes.checked.textContent = `Checked ${new Date().toTimeString().slice(0, 5)}`;
  } catch (error) {
    setProblem(`Could not read the alerts. ${error.message}`);
  }
}

nodes.sync.addEventListener("click", async () => {
  const label = nodes.sync.textContent;
  nodes.sync.disabled = true;
  nodes.sync.textContent = "Checking.";
  try {
    const response = await fetch(API_SYNC, { method: "POST" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || response.status);
    await load();
    nodes.sync.textContent = `Got ${data.stored}`;
  } catch (error) {
    nodes.sync.textContent = "Failed";
    setProblem(`Could not check the recorder. ${error.message}`);
  } finally {
    window.setTimeout(() => {
      nodes.sync.textContent = label;
      nodes.sync.disabled = false;
    }, BUTTON_RESET_MS);
  }
});

nodes.retry.addEventListener("click", load);
nodes.kind.addEventListener("change", load);
nodes.camera.addEventListener("change", load);
nodes.limit.addEventListener("change", load);

fillPicker(
  nodes.limit,
  LIMIT_CHOICES.map((n) => [n, String(n)]),
  DEFAULT_LIMIT,
);
window.setInterval(load, REFRESH_MS);
load();
