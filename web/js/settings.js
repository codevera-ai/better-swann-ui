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

/* How deep a group is allowed to show itself.
   The recorder's settings are a tree, nine levels deep in places. Drawing a
   box for every level gave boxes inside boxes inside boxes. Now only the
   config itself is a box. Inside it, the first level is a heading with a line
   under it, the second is a smaller heading, and anything deeper has no
   heading at all: its name joins the setting's own name as a small grey
   trail, so nothing is lost and nothing is nested. */
const DEPTH_SECTION = 1;
const DEPTH_SUB = 2;
const TRAIL_JOIN = " › ";
const NUMBER_ONLY = /^\d+$/;
const SWITCH_ON = "On";
const SWITCH_OFF = "Off";

/* The info icon beside a field name. A `<details>` fold, the same idea as the
   settings menu on a phone, because a hover tip does not exist on a phone and
   a real pop up box would block the page. */
const INFO_MARK = "i";
const INFO_OPEN = "What this does";
const RANGE_LINE = "Takes {low} to {high}.";
const RANGE_STEP = " In steps of {step}.";
const RANGE_UNIT = "Counted in {unit}.";
const CHOICE_UNKNOWN = "{value} (not in the list)";
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
/* Sizes and field names for the visual editors and the colour swatch. They
   arrive with every screen, from swann/config.py. */
let colourRules = {};
let colourKeys = [];
let showPlain = false;

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
/* The whole menu sits in a fold. On a wide screen the css shows the fold's
   contents whatever the fold says, and hides its handle. On a phone the menu
   is over 1,600 pixels tall, so there the handle shows and the fold starts
   shut. Picking a screen shuts it again, but only when the handle is on
   screen, so the css alone decides which way it behaves and no screen width
   is written twice. */
function drawMenu(groups, label) {
  const fold = make("details", "side-fold");
  const handle = make("summary", "side-summary", label || "");
  fold.appendChild(handle);
  for (const group of groups) {
    const box = make("div", "side-group");
    box.appendChild(make("div", "side-head", group.group));
    for (const screen of group.screens) {
      const link = make("button", "side-link", screen.title);
      link.type = "button";
      link.dataset.key = screen.key;
      if (screen.readOnly) link.appendChild(make("span", "side-tag", "read only"));
      link.addEventListener("click", () => {
        if (handle.offsetParent !== null) fold.open = false;
        openScreen(screen.key);
      });
      box.appendChild(link);
    }
    fold.appendChild(box);
  }
  nodes.side.replaceChildren(fold);
  /* Open it when the handle is hidden, which only the css decides. Chrome
     shows a shut fold's contents when the css says display, but Safari and
     Firefox do not, so say it out loud instead of leaning on that. */
  fold.open = handle.offsetParent === null;
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

/* Is this the value the recorder already has? Two lists or two boxes of
   settings both turn into the same word when forced into text, so compare
   those as JSON instead. */
function same(left, right) {
  if (left === right) return true;
  if (left !== null && typeof left === "object") {
    return JSON.stringify(left) === JSON.stringify(right);
  }
  if (right !== null && typeof right === "object") return false;
  return String(left) === String(right);
}

function queue(config, field, row, value) {
  const key = changeKey(config.key, field.path);
  if (same(value, field.value)) {
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

/* The same thing for the visual editors, which hand over a whole list or
   box of settings at a path of their own instead of one field at a time. */
function queuePath(config, path, value, before) {
  const key = changeKey(config.key, path);
  if (same(value, before)) {
    pending.delete(key);
  } else {
    pending.set(key, {
      name: config.name,
      channel: config.channel,
      path,
      value,
    });
  }
  drawSaveBar();
}

function control(config, field, row, readOnly) {
  // A value nobody can change is not a control. An empty box with a border
  // that refuses to be typed in is noise, so read it out as plain text.
  if (readOnly && field.kind !== KIND_EMPTY) {
    const shown = field.kind === KIND_BOOL
      ? (field.value ? SWITCH_ON : SWITCH_OFF)
      : String(field.value);
    return make("span", "field-flat", shown);
  }

  if (field.kind === KIND_BOOL) {
    const wrap = make("label", "switch");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = Boolean(field.value);
    box.disabled = readOnly;
    const text = make("span", "switch-text", box.checked ? SWITCH_ON : SWITCH_OFF);
    box.addEventListener("change", () => {
      text.textContent = box.checked ? SWITCH_ON : SWITCH_OFF;
      queue(config, field, row, box.checked);
    });
    wrap.append(box, text);
    return wrap;
  }

  if (field.kind === KIND_CHOICE) {
    // Changing the picture size changes which bit rates and which second
    // stream sizes the recorder will take, so that one row redraws the card.
    const after = field.redraw
      ? (value) => {
          setValueAtPath(config.fields, field.path, value);
          sizeChanged(config, field.path, value);
          redrawCard(config);
        }
      : null;
    return drawChoice(config, field, row, readOnly, field.choices, after);
  }

  if (field.kind === KIND_EMPTY) {
    return make("span", "muted", "not set");
  }

  // A packed colour reads as a hex number. A swatch writes the same number
  // back, so nobody has to know the layout.
  if (field.kind === KIND_HEX && colourKeys.includes(field.name) && !readOnly) {
    const holder = make("div", "colour-field");
    holder.append(window.visualColourRow(
      "", field.value, { colour: colourRules },
      (value) => queue(config, field, row, value),
    ));
    return holder;
  }

  const input = document.createElement("input");
  input.type = field.kind === KIND_INT ? "number" : "text";
  input.value = field.value === null || field.value === undefined ? "" : field.value;
  input.readOnly = readOnly;
  // A proven limit goes on the box itself, so the browser refuses a value the
  // recorder would refuse. Without one the box stays free, on purpose.
  if (field.kind === KIND_INT && field.min !== undefined && field.max !== undefined) {
    input.min = field.min;
    input.max = field.max;
    if (field.step) input.step = field.step;
  }
  input.addEventListener("input", () => {
    const raw = field.kind === KIND_INT && input.value !== "" ? Number(input.value) : input.value;
    queue(config, field, row, raw);
  });
  // The frames a second decides what the keyframe gap may be, so changing it
  // rebuilds the card. On `change`, not on every key press, or the card would
  // redraw under your fingers while you were still typing.
  if (field.redraw) {
    input.addEventListener("change", () => {
      if (input.value === "") return;
      const raw = Number(input.value);
      setValueAtPath(config.fields, field.path, raw);
      sizeChanged(config, field.path, raw);
      redrawCard(config);
    });
  }
  return input;
}

/* One dropdown. `choices` is a list of {value, title}. `after` runs once the
   change is queued, which is how a picture size rebuilds the bit rate list. */
function drawChoice(config, field, row, readOnly, choices, after) {
  const select = document.createElement("select");
  const list = choices || [];
  // A value the recorder already holds that is not in the list still has to
  // show, or the dropdown would quietly change it the moment anything saves.
  const known = list.some((choice) => same(choice.value, field.value));
  if (!known && field.value !== null && field.value !== undefined) {
    const option = document.createElement("option");
    option.value = String(field.value);
    option.textContent = fill(CHOICE_UNKNOWN, { value: field.value });
    option.selected = true;
    select.appendChild(option);
  }
  for (const choice of list) {
    const option = document.createElement("option");
    option.value = String(choice.value);
    option.textContent = choice.title === undefined ? String(choice.value) : choice.title;
    if (same(choice.value, field.value)) option.selected = true;
    select.appendChild(option);
  }
  select.disabled = readOnly;
  select.addEventListener("change", () => {
    // The browser hands back text. Send a number when the list held numbers,
    // because this firmware refuses a port sent as "554" instead of 554.
    const picked = list.find((choice) => String(choice.value) === select.value);
    const value = picked ? picked.value : select.value;
    queue(config, field, row, value);
    if (after) after(value);
  });
  return select;
}

/* -- the video quality limits -------------------------------------------

   One screen, video quality, is the only one the recorder states real limits
   for. It answers what each camera's encoder will take, and the server turns
   that into plain lists (`swann/limits.py`). Here those lists become
   dropdowns, and the second stream's list is rebuilt whenever the main
   stream's picture size changes, because the recorder ties the two together.

   Every name below comes from the server in `limitFields`, so no recorder
   field name is written into this file. */

function limitParts(field) {
  const names = currentScreen && currentScreen.limitFields;
  if (!names || !field.path) return null;
  const parts = field.path.split("/");
  // `<camera>/<stream>/Video/<leaf>` and nothing else. The same leaf names
  // live under `Audio` and under the still picture settings, where these
  // limits do not apply.
  if (parts.length !== 4 || parts[2] !== names.video) return null;
  if (parts[1] !== names.main && parts[1] !== names.sub) return null;
  return { stream: parts[1], leaf: parts[3], names, main: parts[1] === names.main };
}

function limitsFor(config) {
  const all = (currentScreen && currentScreen.limits) || null;
  if (!all) return null;
  return all[String(config.channel)] || null;
}

/* Follow a field path into the config's own field tree and read the value
   there. Used to find the picture size a bit rate list depends on. */
function valueAtPath(root, path) {
  const parts = path.split("/");
  let node = root;
  for (const part of parts) {
    if (!node || !node.children) return undefined;
    node = node.children.find((child) => {
      const own = (child.path || "").split("/");
      return own[own.length - 1] === part;
    });
  }
  return node ? node.value : undefined;
}

/* A picture size just changed. Two things can now be wrong, and both get put
   right here rather than sent to the recorder to be refused.

   The bit rate may be outside the new size's list. Swann's own page moves it
   to that size's usual value, so this does too.

   And the second stream's sizes depend on the main stream's size, so a main
   stream change can leave the second stream on a size it no longer allows. */
function sizeChanged(config, path, value) {
  const names = currentScreen && currentScreen.limitFields;
  const limits = limitsFor(config);
  if (!names || !limits) return;
  const parts = path.split("/");
  const stream = parts[1];
  const leaf = parts[3];

  snapGop(config, stream, names, limits);
  if (leaf !== names.resolution) return;
  snapBitRate(config, stream, names, limits);

  if (stream !== names.main) return;
  const subPath = `0/${names.sub}/${names.video}/${names.resolution}`;
  const allowed = (limits.sub && limits.sub[value]) || [];
  if (!allowed.length) return;
  const now = valueAtPath(config.fields, subPath);
  if (allowed.some((size) => size.value === now)) return;
  // Fall back to the biggest size the new main size allows, which is what the
  // list's last entry is: the recorder orders them smallest first.
  const pick = allowed[allowed.length - 1].value;
  setValueAtPath(config.fields, subPath, pick);
  queuePath(config, subPath, pick, now);
  snapBitRate(config, names.sub, names, limits);
}

/* The keyframe gap has to stay a whole number of seconds. When the frames a
   second changes, an old gap stops being one, so it moves to the nearest gap
   that is, rather than being sent and quietly ignored. */
function snapGop(config, stream, names, limits) {
  if (!limits.gop) return;
  const main = stream === names.main;
  const range = gopLimit(limits.gop[main ? "main" : "sub"], config, stream, names);
  if (!range || !range.choices) return;
  const path = `0/${stream}/${names.video}/${names.gop}`;
  const now = valueAtPath(config.fields, path);
  if (range.choices.some((choice) => choice.value === now)) return;
  let pick = range.choices[0].value;
  for (const choice of range.choices) {
    if (Math.abs(choice.value - now) < Math.abs(pick - now)) pick = choice.value;
  }
  setValueAtPath(config.fields, path, pick);
  queuePath(config, path, pick, now);
}

function snapBitRate(config, stream, names, limits) {
  const rates = bitRates(limits, config, stream, names);
  if (!rates) return;
  const path = `0/${stream}/${names.video}/${names.bitRate}`;
  const now = valueAtPath(config.fields, path);
  if (rates.values.includes(now)) return;
  setValueAtPath(config.fields, path, rates.usual);
  queuePath(config, path, rates.usual, now);
}

/* The keyframe gap. The recorder only takes a whole number of seconds, so the
   list is the frames a second, twice it, three times it, and so on up to the
   limit the recorder states. Proven by writing: 16 and 20 were ignored while
   15, 30 and 45 landed, with frames a second at 15. */
function gopLimit(range, config, stream, names) {
  if (!range) return null;
  if (!range.stepFps) return range;
  const step = Number(valueAtPath(config.fields, `0/${stream}/${names.video}/${names.fps}`));
  if (!step || step < 1) return range;
  const choices = [];
  for (let value = step; value <= range.max; value += step) {
    choices.push({ value, title: String(value) });
  }
  if (!choices.length) return range;
  return Object.assign({}, range, { choices, step });
}

/* Which bit rates one stream may use, from the picture size it is set to. */
function bitRates(limits, config, stream, names) {
  const path = `0/${stream}/${names.video}/${names.resolution}`;
  const size = valueAtPath(config.fields, path);
  const found = limits.bitrates && limits.bitrates[size];
  return found && found.values && found.values.length ? found : null;
}

function sizeList(limits, parts, config) {
  if (parts.main) return limits.main || [];
  // The second stream's sizes depend on which size the main stream is on.
  const mainPath = `0/${parts.names.main}/${parts.names.video}/${parts.names.resolution}`;
  const chosen = valueAtPath(config.fields, mainPath);
  return (limits.sub && limits.sub[chosen]) || [];
}

/* What the recorder will take for one video quality field, or null when it
   says nothing about it. */
function encoderLimit(config, field) {
  const parts = limitParts(field);
  if (!parts) return null;
  const limits = limitsFor(config);
  if (!limits) return null;
  const names = parts.names;

  if (parts.leaf === names.resolution) {
    const sizes = sizeList(limits, parts, config);
    return sizes.length ? { choices: sizes, redraw: true } : null;
  }
  if (parts.leaf === names.compression) {
    return limits.codecs && limits.codecs.length ? { choices: limits.codecs } : null;
  }
  if (parts.leaf === names.bitRate) {
    const rates = bitRates(limits, config, parts.stream, names);
    if (!rates) return null;
    return {
      choices: rates.values.map((rate) => ({ value: rate, title: String(rate) })),
    };
  }
  if (parts.leaf === names.fps) {
    // Changing the frames a second changes which keyframe gaps the recorder
    // will take, so this row redraws the card too.
    return limits.fps ? Object.assign({ redraw: true }, limits.fps) : null;
  }
  if (parts.leaf === names.quality) return limits.quality || null;
  if (parts.leaf === names.gop && limits.gop) {
    return gopLimit(limits.gop[parts.main ? "main" : "sub"], config, parts.stream, names);
  }
  return null;
}

function setValueAtPath(root, path, value) {
  const parts = path.split("/");
  let node = root;
  for (const part of parts) {
    if (!node || !node.children) return;
    node = node.children.find((child) => {
      const own = (child.path || "").split("/");
      return own[own.length - 1] === part;
    });
  }
  if (node) node.value = value;
}

/* The field as it should be drawn: what the guide knows about it, with a
   limit the recorder itself stated laid over the top. The recorder wins,
   because it is the only one that can refuse the write. */
function applyLimit(config, field) {
  const found = encoderLimit(config, field);
  if (!found) return field;
  const shown = Object.assign({}, field, found);
  if (found.choices) shown.kind = KIND_CHOICE;
  // The wording comes from the server, so there is one copy of it.
  const limits = limitsFor(config);
  if (limits && limits.source) shown.source = limits.source;
  return shown;
}

function fill(template, values) {
  return template.replace(/\{(\w+)\}/g, (whole, key) =>
    values[key] === undefined ? whole : String(values[key]));
}

/* The info fold beside a field name: what the setting does, what it is
   counted in, what it will take, and where that came from. Nothing is drawn
   when we know nothing, so the row stays as it was. */
function infoFold(field) {
  const lines = [];
  if (field.help) lines.push(field.help);
  // A rule that only shows up on one field, such as the keyframe gap having
  // to be a whole number of seconds.
  if (field.extra) lines.push(field.extra);
  if (field.unit) lines.push(fill(RANGE_UNIT, { unit: field.unit }));
  if (field.min !== undefined && field.max !== undefined) {
    let line = fill(RANGE_LINE, { low: field.min, high: field.max });
    if (field.step && field.step > 1) line += fill(RANGE_STEP, { step: field.step });
    lines.push(line);
  }
  if (field.source) lines.push(field.source);
  if (!lines.length) return null;

  const fold = make("details", "info");
  const mark = make("summary", "info-mark", INFO_MARK);
  mark.title = INFO_OPEN;
  mark.setAttribute("aria-label", INFO_OPEN);
  fold.appendChild(mark);
  const panel = make("div", "info-panel");
  for (const line of lines) panel.appendChild(make("p", "", line));
  fold.appendChild(panel);
  return fold;
}

/* A trail is only worth printing when it changes. Printing it on every row
   repeats the same grey line five or six times under one heading, which is
   the noise this whole pass is here to remove. `seen` remembers the last one
   printed inside the current card. */
/* The recorder counts list entries from 0. Everywhere a person reads a
   number on this page it counts from 1, so an unnamed entry does too. */
function readLabel(field) {
  const label = field.label || field.name || "";
  return NUMBER_ONLY.test(label) ? String(Number(label) + 1) : label;
}

function trailNode(trail, seen) {
  if (!trail || trail === seen.last) return null;
  seen.last = trail;
  return make("span", "field-trail", trail);
}

function drawField(config, field, readOnly, trail, seen) {
  const row = make("div", "field");
  // The path is on the row so a redraw can put the "waiting to save" mark
  // back on the right rows.
  if (field.path) row.dataset.path = field.path;
  const label = make("div", "field-label");
  const crumb = trailNode(trail, seen);
  if (crumb) {
    label.appendChild(crumb);
    // In two columns a trail only sits above the row it is printed on. Start
    // its block on a new line, or the row beside it reads as an orphan.
    row.classList.add("field-first");
  }
  // What the guide knows, with any limit the recorder itself stated on top.
  const shown = applyLimit(config, field);
  // The name and its info icon sit on one line, so the icon never pushes the
  // value column down.
  const line = make("div", "field-title");
  line.appendChild(make("span", "field-name", readLabel(shown)));
  const fold = infoFold(shown);
  if (fold) line.appendChild(fold);
  label.appendChild(line);
  // The hex warning tells you not to change a value by hand. On a value the
  // recorder will not let you change at all, it says nothing.
  if (shown.note && !(readOnly && shown.kind === KIND_HEX)) {
    label.appendChild(make("span", "field-note", shown.note));
  }
  row.append(label, control(config, shown, row, readOnly));
  return row;
}

/* Where a folded group's name goes in the trail. A group named with a bare
   number is one entry in a list, so it reads "Comb encode info 2", counting
   from 1 the way a person does, not "Comb encode info › 1". */
function joinTrail(trail, owner, label) {
  if (NUMBER_ONLY.test(label)) {
    const nth = Number(label) + 1;
    return trail ? `${trail} ${nth}` : `${owner} ${nth}`.trim();
  }
  return trail ? trail + TRAIL_JOIN + label : label;
}

/* One config's card. Kept in `cards` so a change that alters what another
   field will take can redraw just that card, with nothing refetched and
   nothing already queued lost. */
const cards = new Map();

function buildCard(data, config) {
  const card = make("section", "card card-fields");
  const head = make("div", "card-head");
  head.appendChild(make("h2", "", config.label));
  head.appendChild(make("span", "muted", config.name));
  card.appendChild(head);
  const locked = data.readOnly || config.readOnly;
  if (config.error) {
    card.appendChild(make("p", "note", config.error));
  } else {
    card.append(
      ...drawBranch(config, config.fields, locked, 0, "", config.label, { last: "" }),
    );
    if (config.readOnly && !data.readOnly) {
      card.appendChild(
        make("p", "note", "The recorder reports this. It will not take a change here."),
      );
    }
  }
  cards.set(config.key, card);
  return card;
}

function redrawCard(config) {
  const old = cards.get(config.key);
  if (!old || !currentScreen) return;
  const fresh = buildCard(currentScreen, config);
  old.replaceWith(fresh);
  // The highlight on every row already waiting to be saved has to go back on,
  // because the rows themselves are new.
  for (const change of pending.values()) {
    if (change.name !== config.name || change.channel !== config.channel) continue;
    const row = fresh.querySelector(`[data-path="${cssPath(change.path)}"]`);
    if (row) row.classList.add("field-changed");
  }
}

/* The path goes inside a quoted selector, so a quote or a backslash in it
   would break out. Only those two need escaping in a CSS string. */
function cssPath(path) {
  return String(path).replace(/["\\]/g, "\\$&");
}

/* Returns a flat list of rows and headings, never a box. The caller drops
   them straight into the config's one card. */
function drawBranch(config, field, readOnly, depth, trail, owner, seen) {
  if (field.kind !== KIND_GROUP && field.kind !== KIND_LIST) {
    return [drawField(config, field, readOnly, trail, seen)];
  }

  const label = field.label || field.name || "";
  const kids = field.children || [];
  if (!kids.length) {
    const row = make("div", "field");
    const side = make("div", "field-label");
    const crumb = trailNode(trail, seen);
    if (crumb) side.appendChild(crumb);
    side.appendChild(make("span", "field-name", label));
    row.append(side, make("span", "muted", "nothing in here"));
    return [row];
  }

  const out = [];
  let deeper = trail;
  let holder = owner;
  // A list whose entries are bare numbers gets no heading of its own. Each
  // entry's trail already reads "Comb encode info 2", so a heading above it
  // would only say the same words again.
  const numbered = kids.every((kid) => NUMBER_ONLY.test(kid.label || kid.name || ""));
  if (label && depth <= DEPTH_SUB && !numbered) {
    const head = make(
      "div",
      depth === DEPTH_SECTION ? "section-head" : "section-head section-sub",
    );
    head.appendChild(make("span", "section-name", label));
    if (field.kind === KIND_LIST && field.shown && field.shown.length < field.length) {
      head.appendChild(
        make("span", "muted", `showing ${field.shown.length} of ${field.length}`),
      );
    }
    out.push(head);
    // A heading starts a clean slate, so the trail under it is relative to it.
    deeper = "";
    holder = label;
    seen.last = "";
  } else if (label) {
    deeper = joinTrail(trail, owner, label);
  }

  for (const kid of kids) {
    out.push(...drawBranch(config, kid, readOnly, depth + 1, deeper, holder, seen));
  }
  return out;
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

  const state = make("span", "row-state", user.enabled ? SWITCH_ON : SWITCH_OFF);
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

/* -- the plain list, for when you want every last field ----------------- */
function plainSwitch(nowVisual) {
  const row = make("div", "toolbar");
  row.append(make("span", "spacer"));
  const go = make("button", "btn", nowVisual
    ? "Show every setting"
    : "Back to the picture");
  go.type = "button";
  go.addEventListener("click", () => {
    showPlain = nowVisual;
    openScreen(currentKey);
  });
  row.append(go);
  return row;
}

/* -- opening a screen -------------------------------------------------- */
async function openScreen(key) {
  // Moving to another screen starts on the picture again.
  if (key !== currentKey) showPlain = false;
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
  colourRules = (data.visual && data.visual.colour) || {};
  colourKeys = colourRules.keys || [];

  if (data.action === ACTION_LOG) return drawLog();
  if (data.action === ACTION_USERS) return drawUsers();
  if (data.action === ACTION_DANGER) return drawDanger(data);

  // A screen that holds a position or a time draws a picture or a week
  // instead of a field list. Every setting is still reachable, through the
  // "Show every setting" button.
  if (data.editor && !showPlain) {
    const drawn = window.visualEditor(data, queuePath);
    if (drawn) {
      const parts = [...drawn, plainSwitch(true)];
      if (!data.readOnly) parts.push(buildSaveBar());
      nodes.body.replaceChildren(...parts);
      drawSaveBar();
      return;
    }
  }

  const parts = [];
  if (data.editor) parts.push(plainSwitch(false));
  cards.clear();
  for (const config of data.configs) {
    parts.push(buildCard(data, config));
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
    drawMenu(menu.groups, menu.menuLabel);
    const first = menu.groups[0] && menu.groups[0].screens[0];
    const wanted = window.location.hash.replace("#", "");
    await openScreen(wanted || (first && first.key));
  } catch (error) {
    setProblem(`Could not load the settings menu. ${error.message}`);
  }
})();
