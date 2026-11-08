/* Settings. Draws an editor for whatever the recorder reports, then saves the
   fields that changed. Nothing here knows the name of any one setting: the
   shape of the value decides the control. */

const API_MENU = "/api/settings";
const API_SCREEN = "/api/settings/";
const API_LOG = "/api/log";
const API_USERS = "/api/users";
const API_BACKUP = "/api/backup";

const KIND_BOOL = "bool";
const KIND_INT = "int";
const KIND_TEXT = "text";
const KIND_HEX = "hex";
const KIND_CHOICE = "choice";
const KIND_GROUP = "group";
const KIND_LIST = "list";
const KIND_EMPTY = "empty";

const ACTION_LOG = "log";
const ACTION_USERS = "users";
const ACTION_DANGER = "danger";

const DEPTH_NESTED = 1;
const API_RESTART = "/api/restart";
const API_RESET = "/api/reset";
const CONFIRM_RESTART = "restart";
const CONFIRM_RESET = "reset";
const RESTART_NOTE =
  "The recorder goes off for a minute or two. Nothing is saved while it is " +
  "off, and live view will stop until it is back. It restarts itself every " +
  "Sunday at midnight anyway, so this is safe.";
const RESET_NOTE =
  "This wipes the ticked part of the settings back to how it left the " +
  "factory. Network wipes the address on your home network, so the app may " +
  "not find the recorder afterwards. Save a backup first, with the button " +
  "at the top right. This cannot be undone from here.";
const USER_GROUPS = ["admin", "user"];
const USERS_NOTE =
  "The recorder has a fixed set of accounts. Its own screen cannot add or " +
  "remove one either, only change what each may do. The boss account is " +
  "locked here on purpose, because this app logs in as it. To change a " +
  "password, use the recorder's own screen.";
const LOG_DAY_CHOICES = [1, 3, 7, 30];
const LOG_DEFAULT_DAYS = 3;
const SAVE_RESET_MS = 6000;

const el = (id) => document.getElementById(id);
const nodes = {
  liveDot: el("live-dot"),
  problem: el("problem"),
  problemText: el("problem-text"),
  retry: el("retry"),
  backup: el("backup"),
  side: el("side"),
  title: el("screen-title"),
  note: el("screen-note"),
  body: el("body"),
};

/* The field changes waiting to be saved, keyed so one field cannot queue twice. */
const pending = new Map();
let currentKey = null;
let currentScreen = null;

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

async function getJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || data.detail || `${response.status}`);
  return data;
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || data.detail || `${response.status}`);
  return data;
}

/* -- the menu ---------------------------------------------------------- */
function drawMenu(groups) {
  const parts = [];
  for (const group of groups) {
    const box = make("div", "side-group");
    box.appendChild(make("div", "side-head", group.group));
    for (const screen of group.screens) {
      const link = make("button", "side-link", screen.title);
      link.type = "button";
      link.dataset.key = screen.key;
      if (screen.readOnly) link.appendChild(make("span", "side-tag", "read only"));
      link.addEventListener("click", () => openScreen(screen.key));
      box.appendChild(link);
    }
    parts.push(box);
  }
  nodes.side.replaceChildren(...parts);
}

function markMenu(key) {
  for (const link of nodes.side.querySelectorAll(".side-link")) {
    if (link.dataset.key === key) {
      link.setAttribute("aria-current", "true");
    } else {
      link.removeAttribute("aria-current");
    }
  }
}

/* -- drawing one field ------------------------------------------------- */
function changeKey(configKey, path) {
  return `${configKey}|${path}`;
}

function queue(config, field, row, value) {
  const key = changeKey(config.key, field.path);
  if (value === field.value || String(value) === String(field.value)) {
    pending.delete(key);
    row.classList.remove("field-changed");
  } else {
    pending.set(key, {
      name: config.name,
      channel: config.channel,
      path: field.path,
      value,
    });
    row.classList.add("field-changed");
  }
  drawSaveBar();
}

function control(config, field, row, readOnly) {
  if (field.kind === KIND_BOOL) {
    const wrap = make("label", "switch");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = Boolean(field.value);
    box.disabled = readOnly;
    const text = make("span", "switch-text", box.checked ? "On" : "Off");
    box.addEventListener("change", () => {
      text.textContent = box.checked ? "On" : "Off";
      queue(config, field, row, box.checked);
    });
    wrap.append(box, text);
    return wrap;
  }

  if (field.kind === KIND_CHOICE) {
    const select = document.createElement("select");
    const options = field.choices.includes(field.value)
      ? field.choices
      : [field.value, ...field.choices];
    for (const choice of options) {
      const option = document.createElement("option");
      option.value = choice;
      option.textContent = choice;
      if (choice === field.value) option.selected = true;
      select.appendChild(option);
    }
    select.disabled = readOnly;
    select.addEventListener("change", () => queue(config, field, row, select.value));
    return select;
  }

  if (field.kind === KIND_EMPTY) {
    return make("span", "muted", "not set");
  }

  const input = document.createElement("input");
  input.type = field.kind === KIND_INT ? "number" : "text";
  input.value = field.value === null || field.value === undefined ? "" : field.value;
  input.readOnly = readOnly;
  input.addEventListener("input", () => {
    const raw = field.kind === KIND_INT && input.value !== "" ? Number(input.value) : input.value;
    queue(config, field, row, raw);
  });
  return input;
}

function drawField(config, field, readOnly) {
  const row = make("div", "field");
  const label = make("div", "field-label");
  label.appendChild(make("span", "field-name", field.label || field.name));
  if (field.note) label.appendChild(make("span", "field-note", field.note));
  row.append(label, control(config, field, row, readOnly));
  return row;
}

function drawBranch(config, field, readOnly, depth) {
  if (field.kind !== KIND_GROUP && field.kind !== KIND_LIST) {
    return drawField(config, field, readOnly);
  }

  const kids = field.children || [];
  if (!kids.length) {
    const row = make("div", "field");
    row.append(
      make("div", "field-label", field.label || field.name),
      make("span", "muted", "nothing in here"),
    );
    return row;
  }

  const box = make("div", depth >= DEPTH_NESTED ? "fieldset fieldset-depth" : "fieldset");
  if (field.label) {
    const head = make("div", "fieldset-head", field.label);
    if (field.kind === KIND_LIST && field.shown && field.shown.length < field.length) {
      head.appendChild(
        make("span", "muted", `showing ${field.shown.length} of ${field.length}`),
      );
    }
    box.appendChild(head);
  }
  for (const kid of kids) box.appendChild(drawBranch(config, kid, readOnly, depth + 1));
  return box;
}

/* -- the save bar ------------------------------------------------------ */
let saveBar = null;
let saveNote = null;
let saveButton = null;

function drawSaveBar() {
  if (!saveBar) return;
  const count = pending.size;
  saveBar.classList.toggle("hidden", count === 0);
  if (count > 0) {
    saveNote.textContent =
      count === 1 ? "1 change not saved yet" : `${count} changes not saved yet`;
    saveButton.disabled = false;
  }
}

function buildSaveBar() {
  saveBar = make("div", "savebar hidden");
  saveNote = make("p", "note", "");
  saveButton = make("button", "btn btn-go", "Save changes");
  saveButton.type = "button";
  const undo = make("button", "btn", "Undo");
  undo.type = "button";
  undo.addEventListener("click", () => openScreen(currentKey));
  saveButton.addEventListener("click", save);
  saveBar.append(saveNote, make("span", "spacer"), undo, saveButton);
  return saveBar;
}

async function save() {
  if (!pending.size) return;
  saveButton.disabled = true;
  saveNote.textContent = "Saving.";
  try {
    const data = await postJson(API_SCREEN + currentKey, {
      changes: [...pending.values()],
    });
    const lines = data.results.map((r) => {
      const where = r.channel === null ? r.name : `${r.name} camera ${r.channel + 1}`;
      return `${where}: ${r.message}`;
    });
    pending.clear();
    await openScreen(currentKey);
    saveNote.textContent = data.saved ? "Saved." : lines.join("  ");
    saveBar.classList.remove("hidden");
    saveButton.disabled = true;
    if (data.saved) window.setTimeout(drawSaveBar, SAVE_RESET_MS);
  } catch (error) {
    saveNote.textContent = `Could not save. ${error.message}`;
    saveButton.disabled = false;
  }
}

/* -- read only tables -------------------------------------------------- */
function table(headings, rows) {
  const scroller = make("div", "scroller");
  const node = document.createElement("table");
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const heading of headings) {
    const cell = document.createElement("th");
    cell.textContent = heading;
    headRow.appendChild(cell);
  }
  head.appendChild(headRow);
  const body = document.createElement("tbody");
  for (const row of rows) {
    const line = document.createElement("tr");
    for (const cell of row) {
      const td = document.createElement("td");
      if (cell instanceof Node) td.appendChild(cell);
      else td.textContent = cell === null || cell === undefined ? "" : String(cell);
      line.appendChild(td);
    }
    body.appendChild(line);
  }
  node.append(head, body);
  scroller.appendChild(node);
  return scroller;
}

function logPill(type) {
  if (type === "EventStart") return make("span", "pill pill-warm", "started");
  if (type === "EventStop") return make("span", "pill", "stopped");
  if (type === "Reboot" || type === "ShutDown") return make("span", "pill pill-bad", type);
  return make("span", "pill", type);
}

async function drawLog() {
  const card = make("section", "card");
  const bar = make("div", "toolbar");
  bar.appendChild(make("label", "", "Show the last"));
  const picker = document.createElement("select");
  for (const days of LOG_DAY_CHOICES) {
    const option = document.createElement("option");
    option.value = days;
    option.textContent = days === 1 ? "1 day" : `${days} days`;
    if (days === LOG_DEFAULT_DAYS) option.selected = true;
    picker.appendChild(option);
  }
  const kind = document.createElement("select");
  for (const [value, label] of [
    ["LogAll", "Everything"],
    ["LogAlarm", "Alerts"],
    ["LogSystem", "Starts and stops"],
    ["LogConfig", "Setting changes"],
    ["LogStorage", "Disk"],
    ["LogRecord", "Recording"],
    ["LogAccount", "Logins"],
  ]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    kind.appendChild(option);
  }
  const count = make("span", "muted", "");
  bar.append(picker, kind, make("span", "spacer"), count);
  card.appendChild(bar);
  const holder = make("div", "stack", "Loading the log.");
  card.appendChild(holder);
  nodes.body.replaceChildren(card);

  async function load() {
    holder.replaceChildren(make("p", "note", "Loading the log."));
    try {
      const data = await getJson(`${API_LOG}?type=${kind.value}&days=${picker.value}`);
      count.textContent = `${data.rows.length} entries`;
      if (!data.rows.length) {
        holder.replaceChildren(
          make("p", "note", "Nothing in the log for that choice."),
        );
        return;
      }
      holder.replaceChildren(
        table(
          ["When", "What", "Detail", "Who"],
          data.rows.map((row) => [
            make("span", "mono", row.Time || ""),
            logPill(row.Type || ""),
            row.Data || "",
            row.User || "",
          ]),
        ),
      );
    } catch (error) {
      holder.replaceChildren(make("p", "note", `Could not read the log. ${error.message}`));
    }
  }

  picker.addEventListener("change", load);
  kind.addEventListener("change", load);
  await load();
}

/* -- accounts ----------------------------------------------------------- */
async function drawUsers() {
  const card = make("section", "card");
  card.appendChild(make("h2", "", "Accounts"));
  const holder = make("div", "stack");
  const note = make("p", "note", "Reading the accounts.");
  card.append(holder, note);
  nodes.body.replaceChildren(card);

  async function load() {
    try {
      const data = await getJson(API_USERS);
      holder.replaceChildren(...(data.users || []).map((u) => userCard(u, data, load)));
      note.textContent = USERS_NOTE;
    } catch (error) {
      note.textContent = `Could not read the accounts. ${error.message}`;
    }
  }
  await load();
}

function userCard(user, data, reload) {
  const box = make("div", "panel");
  const head = make("div", "toolbar");
  head.append(make("strong", "", user.name));
  if (user.isAdmin) head.append(make("span", "pill", "Boss account"));
  head.append(make("span", "spacer"));

  const state = make("span", "row-state", user.enabled ? "On" : "Off");
  head.append(state);
  box.appendChild(head);

  const row = make("div", "toolbar");

  const onOff = document.createElement("button");
  onOff.type = "button";
  onOff.className = "btn";
  onOff.textContent = user.enabled ? "Turn off" : "Turn on";
  onOff.disabled = user.isAdmin;
  row.append(onOff);

  const groupLabel = make("label", "", "Group");
  groupLabel.htmlFor = `group-${user.name}`;
  const group = document.createElement("select");
  group.id = `group-${user.name}`;
  for (const name of USER_GROUPS) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    if (name === user.group) option.selected = true;
    group.appendChild(option);
  }
  group.disabled = user.isAdmin;
  row.append(groupLabel, group);
  row.append(make("span", "spacer"));
  row.append(make("span", "muted", `${user.rights.length} things allowed`));
  box.appendChild(row);

  const rights = make("details", "");
  rights.appendChild(make("summary", "", "What this account may do"));
  const list = make("div", "chips");
  const boxes = new Map();
  for (const right of data.allRights) {
    const label = make("label", "chip");
    const tick = document.createElement("input");
    tick.type = "checkbox";
    tick.checked = user.rights.includes(right);
    tick.disabled = user.isAdmin;
    boxes.set(right, tick);
    label.append(tick, make("span", "", humanRight(right)));
    list.appendChild(label);
  }
  rights.appendChild(list);
  box.appendChild(rights);

  const save = document.createElement("button");
  save.type = "button";
  save.className = "btn btn-go";
  save.textContent = "Save this account";
  save.disabled = user.isAdmin;
  const said = make("p", "note", "");
  box.append(save, said);

  async function send(body, button) {
    const was = button.textContent;
    button.disabled = true;
    button.textContent = "Saving.";
    try {
      const reply = await postJson(`${API_USERS}/${encodeURIComponent(user.name)}`, body);
      said.textContent = reply.message;
      await reload();
    } catch (error) {
      said.textContent = `Could not save. ${error.message}`;
      button.textContent = was;
      button.disabled = false;
    }
  }

  onOff.addEventListener("click", () => send({ enabled: !user.enabled }, onOff));
  save.addEventListener("click", () =>
    send(
      {
        group: group.value,
        rights: [...boxes.entries()].filter(([, t]) => t.checked).map(([r]) => r),
      },
      save,
    ),
  );
  return box;
}

/* "QueryLog" reads better as "Query log". */
function humanRight(right) {
  const spaced = right.replace(/_/g, " ").replace(/([a-z])([A-Z])/g, "$1 $2");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1).toLowerCase();
}

/* -- restart and put back ----------------------------------------------- */
function wordBox(id, word) {
  const label = make("label", "", `Type ${word} to allow this`);
  label.htmlFor = id;
  const field = document.createElement("input");
  field.type = "text";
  field.id = id;
  field.autocomplete = "off";
  field.spellcheck = false;
  field.placeholder = word;
  return { label, field };
}

function drawDanger(data) {
  nodes.body.replaceChildren(dangerRestart(), dangerReset(data));
}

function dangerRestart() {
  const card = make("section", "card");
  card.appendChild(make("h2", "", "Restart the recorder"));
  card.appendChild(make("p", "note", RESTART_NOTE));

  const typed = wordBox("restart-word", CONFIRM_RESTART);
  const row = make("div", "toolbar");
  row.append(typed.label, typed.field);
  card.appendChild(row);

  const go = make("button", "btn btn-danger", "Restart it now");
  go.type = "button";
  const said = make("p", "note", "");
  card.append(go, said);

  go.addEventListener("click", async () => {
    if (typed.field.value.trim().toLowerCase() !== CONFIRM_RESTART) {
      said.textContent = `Type ${CONFIRM_RESTART} in the box first.`;
      return;
    }
    go.disabled = true;
    go.textContent = "Restarting.";
    try {
      const reply = await postJson(API_RESTART, { confirm: typed.field.value });
      said.textContent = reply.message;
    } catch (error) {
      said.textContent = `It did not restart. ${error.message}`;
    } finally {
      typed.field.value = "";
      window.setTimeout(() => {
        go.textContent = "Restart it now";
        go.disabled = false;
      }, SAVE_RESET_MS);
    }
  });
  return card;
}

function dangerReset(data) {
  const card = make("section", "card");
  card.appendChild(make("h2", "", "Put settings back to factory"));
  card.appendChild(make("p", "note", RESET_NOTE));

  const list = make("div", "chips");
  const boxes = new Map();
  for (const area of data.resetAreas || []) {
    const label = make("label", "chip");
    const tick = document.createElement("input");
    tick.type = "checkbox";
    boxes.set(area.key, tick);
    label.title = area.note;
    label.append(tick, make("span", "", area.title));
    list.appendChild(label);
  }
  card.appendChild(list);

  const typed = wordBox("reset-word", CONFIRM_RESET);
  const row = make("div", "toolbar");
  row.append(typed.label, typed.field);
  card.appendChild(row);

  const go = make("button", "btn btn-danger", "Put the ticked ones back");
  go.type = "button";
  const said = make("p", "note", "");
  card.append(go, said);

  go.addEventListener("click", async () => {
    const areas = {};
    let any = false;
    for (const [key, tick] of boxes) {
      areas[key] = tick.checked;
      if (tick.checked) any = true;
    }
    if (!any) {
      said.textContent = "Tick at least one thing first.";
      return;
    }
    if (typed.field.value.trim().toLowerCase() !== CONFIRM_RESET) {
      said.textContent = `Type ${CONFIRM_RESET} in the box first.`;
      return;
    }
    go.disabled = true;
    go.textContent = "Putting back.";
    try {
      const reply = await postJson(API_RESET, {
        confirm: typed.field.value,
        areas,
      });
      said.textContent = reply.message;
    } catch (error) {
      said.textContent = `Nothing was put back. ${error.message}`;
    } finally {
      typed.field.value = "";
      for (const tick of boxes.values()) tick.checked = false;
      window.setTimeout(() => {
        go.textContent = "Put the ticked ones back";
        go.disabled = false;
      }, SAVE_RESET_MS);
    }
  });
  return card;
}

/* -- raw read only blocks ---------------------------------------------- */
function drawRaw(title, value) {
  const card = make("section", "card");
  card.appendChild(make("h2", "", title));
  const rows = [];
  walk(value, "", rows);
  card.appendChild(table(["Setting", "Value"], rows));
  return card;
}

function walk(value, path, rows) {
  if (value === null || value === undefined) {
    rows.push([path, "not set"]);
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => walk(item, path ? `${path} ${index + 1}` : String(index + 1), rows));
    return;
  }
  if (typeof value === "object") {
    for (const [key, item] of Object.entries(value)) {
      walk(item, path ? `${path} / ${key}` : key, rows);
    }
    return;
  }
  rows.push([path, make("span", "mono", String(value))]);
}

/* -- opening a screen -------------------------------------------------- */
async function openScreen(key) {
  currentKey = key;
  pending.clear();
  markMenu(key);
  nodes.body.replaceChildren(make("p", "note", "Reading the recorder."));
  nodes.title.textContent = "Loading";
  nodes.note.textContent = "";

  let data;
  try {
    data = await getJson(API_SCREEN + key);
  } catch (error) {
    setProblem(`Could not read that screen. ${error.message}`);
    nodes.body.replaceChildren();
    return;
  }
  setProblem(null);
  currentScreen = data;
  nodes.title.textContent = data.title;
  nodes.note.textContent = data.note || "";
  document.title = `${data.title} - Settings`;

  if (data.action === ACTION_LOG) return drawLog();
  if (data.action === ACTION_USERS) return drawUsers();
  if (data.action === ACTION_DANGER) return drawDanger(data);

  const parts = [];
  for (const config of data.configs) {
    const card = make("section", "card");
    const head = make("div", "card-head");
    head.appendChild(make("h2", "", config.label));
    head.appendChild(make("span", "muted", config.name));
    card.appendChild(head);
    const locked = data.readOnly || config.readOnly;
    if (config.error) {
      card.appendChild(make("p", "note", config.error));
    } else {
      card.appendChild(drawBranch(config, config.fields, locked, 0));
      if (config.readOnly && !data.readOnly) {
        card.appendChild(
          make("p", "note", "The recorder reports this. It will not take a change here."),
        );
      }
    }
    parts.push(card);
  }
  for (const [name, value] of Object.entries(data.info || {})) {
    parts.push(drawRaw(name, value));
  }
  for (const [name, value] of Object.entries(data.ability || {})) {
    parts.push(drawRaw(name, value));
  }
  if (!data.readOnly) parts.push(buildSaveBar());
  nodes.body.replaceChildren(...parts);
  drawSaveBar();
}

/* -- backup ------------------------------------------------------------ */
nodes.backup.addEventListener("click", async () => {
  const label = nodes.backup.textContent;
  nodes.backup.disabled = true;
  nodes.backup.textContent = "Backing up.";
  try {
    const data = await postJson(API_BACKUP, {});
    nodes.backup.textContent = data.ok ? "Backed up" : "Backup had a problem";
    setProblem(data.ok ? null : `Backup: ${data.summary}`);
  } catch (error) {
    nodes.backup.textContent = "Backup failed";
    setProblem(`Could not back up. ${error.message}`);
  } finally {
    window.setTimeout(() => {
      nodes.backup.textContent = label;
      nodes.backup.disabled = false;
    }, SAVE_RESET_MS);
  }
});

nodes.retry.addEventListener("click", () => openScreen(currentKey));

/* -- start ------------------------------------------------------------- */
(async function start() {
  try {
    const menu = await getJson(API_MENU);
    drawMenu(menu.groups);
    const first = menu.groups[0] && menu.groups[0].screens[0];
    const wanted = window.location.hash.replace("#", "");
    await openScreen(wanted || (first && first.key));
  } catch (error) {
    setProblem(`Could not load the settings menu. ${error.message}`);
  }
})();
