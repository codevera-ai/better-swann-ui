/* Visual settings editors.

   Nine settings screens hold a position or a time. The plain field list
   cannot show either, so those screens draw on a still from the camera, or
   paint a week, instead.

   Nothing in here knows a recorder number. Every size, field name and index
   arrives with the screen, from swann/config.py, so there is one copy of
   each. The only numbers below are about this page: how big a drag handle
   is, and how long a hint stays up.

   The recorder puts every position in its own square, 0 up to "space",
   whatever the real picture size is. A box at half that number sits halfway
   across, so turning one into a percentage is all the maths needed. */

const HANDLE_CLASS = "shot-handle";
const BOX_CLASS = "shot-box";
const CHIP_CLASS = "shot-chip";
const PERCENT = 100;
const POINTER_PRIMARY = 0;
const DEFAULT_BOX = { left: 0.35, top: 0.35, right: 0.65, bottom: 0.65 };
const DEFAULT_LINE = { x1: 0.3, y1: 0.5, x2: 0.7, y2: 0.5 };
const DEFAULT_SHAPE = [
  { x: 0.3, y: 0.3 },
  { x: 0.7, y: 0.3 },
  { x: 0.7, y: 0.7 },
  { x: 0.3, y: 0.7 },
];
const SVG_NS = "http://www.w3.org/2000/svg";
const HEX_BASE = 16;
const BITS_PER_DIGIT = 4;
const HOURS_IN_DAY = 24;
const MINUTES_IN_HOUR = 60;
const HOUR_LABEL_STEP = 3;
const PAD = 2;
const PAINT_ON = "on";
const PAINT_OFF = "off";

/* ---------------------------------------------------------------- bits -- */

/* A row of the movement grid is one number written in hex. Column 0 is the
   lowest bit. Read off rsui/cfg/alarm_mv.js:257. */
function readRow(text, columns) {
  const value = Number.parseInt(String(text).replace(/^0x/i, ""), HEX_BASE) || 0;
  const cells = [];
  for (let column = 0; column < columns; column += 1) {
    // Shifting past 31 wraps round in JavaScript, so divide instead.
    cells.push(Boolean(Math.floor(value / Math.pow(2, column)) % 2));
  }
  return cells;
}

function writeRow(cells, digits, prefix) {
  let value = 0;
  cells.forEach((on, column) => {
    if (on) value += Math.pow(2, column);
  });
  return prefix + value.toString(HEX_BASE).toUpperCase().padStart(digits, "0");
}

function bitSet(text, bit) {
  const value = Number.parseInt(String(text).replace(/^0x/i, ""), HEX_BASE) || 0;
  return Boolean(Math.floor(value / Math.pow(2, bit)) % 2);
}

function withBit(text, bit, on, digits, prefix) {
  let value = Number.parseInt(String(text).replace(/^0x/i, ""), HEX_BASE) || 0;
  const weight = Math.pow(2, bit);
  const already = Boolean(Math.floor(value / weight) % 2);
  if (on && !already) value += weight;
  if (!on && already) value -= weight;
  return prefix + value.toString(HEX_BASE).toUpperCase().padStart(digits, "0");
}

/* ------------------------------------------------------------- helpers -- */

function tag(name, className, text) {
  const node = document.createElement(name);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function svgTag(name, className) {
  const node = document.createElementNS(SVG_NS, name);
  if (className) node.setAttribute("class", className);
  return node;
}

function button(label, className) {
  const node = tag("button", className || "btn", label);
  node.type = "button";
  return node;
}

function clamp(value) {
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}

function percent(fraction) {
  return `${fraction * PERCENT}%`;
}

/* Every camera on these screens is a slot in one long list, so the path to
   a field starts with the camera's own number. */
function join(...parts) {
  return parts.filter((part) => part !== "" && part !== null).join("/");
}

function cameraTitle(channel, visual) {
  return visual.channelLabel.replace("{number}", channel + 1);
}

/* ------------------------------------------------------------ the shot -- */

/* A still from the camera with a layer on top you can draw on. The layer is
   plain HTML boxes and one SVG sheet, both measured in percentages, so the
   drawing lines up at any size and on a phone. */
function shot(channel, visual) {
  const frame = tag("div", "shot");
  const picture = document.createElement("img");
  picture.className = "shot-img";
  picture.alt = `A still from ${cameraTitle(channel, visual)}`;
  picture.src = visual.snapshot.replace("{channel}", String(channel));
  picture.addEventListener("error", () => {
    frame.classList.add("shot-blank");
  });

  const sheet = svgTag("svg", "shot-svg");
  sheet.setAttribute("viewBox", `0 0 ${visual.space} ${visual.space}`);
  sheet.setAttribute("preserveAspectRatio", "none");

  const layer = tag("div", "shot-layer");
  frame.append(picture, sheet, layer);

  /* Where a pointer is, as a share of the picture from 0 to 1. */
  function at(event) {
    const box = frame.getBoundingClientRect();
    return {
      x: clamp((event.clientX - box.left) / box.width),
      y: clamp((event.clientY - box.top) / box.height),
    };
  }

  /* Follow a pointer until it is let go. Works for mouse, pen and finger,
     because every one of them sends pointer events. */
  function drag(node, onMove, onDone) {
    node.addEventListener("pointerdown", (event) => {
      if (event.button !== POINTER_PRIMARY) return;
      event.preventDefault();
      event.stopPropagation();
      node.setPointerCapture(event.pointerId);
      // Count the press itself, so a single tap paints one cell and a drag
      // measures from where it started, not from the first wobble.
      onMove(at(event), event);
      const move = (moving) => onMove(at(moving), moving);
      const up = () => {
        node.removeEventListener("pointermove", move);
        node.removeEventListener("pointerup", up);
        node.removeEventListener("pointercancel", up);
        if (onDone) onDone();
      };
      node.addEventListener("pointermove", move);
      node.addEventListener("pointerup", up);
      node.addEventListener("pointercancel", up);
    });
  }

  return { node: frame, layer, sheet, at, drag, reload: () => {
    picture.src = `${visual.snapshot.replace("{channel}", String(channel))}?t=${Date.now()}`;
  } };
}

/* A card per camera, with the picture on the left and its controls beside. */
function cameraCard(channel, visual) {
  const card = tag("section", "card");
  const head = tag("div", "card-head");
  head.append(tag("h2", "", cameraTitle(channel, visual)));
  card.append(head);
  const split = tag("div", "shot-split");
  card.append(split);
  return { card, split, head };
}

/* ------------------------------------------------- privacy blocks -------- */

function privacyEditor(data, queuePath) {
  const visual = data.visual;
  const rules = visual.privacy;
  const config = data.configs.find((one) => one.fields);
  if (!config) return null;
  const parts = [];

  for (const channel of data.channels) {
    const live = config.value[channel];
    if (!live) continue;
    const before = live[rules.coversKey].slice(0, rules.limit);
    // A copy to change, so the old values stay for an undo.
    const covers = before.map((cover) => ({
      on: Boolean(cover[rules.onKey]) || Boolean(cover[rules.previewKey]),
      left: cover[rules.posKey][rules.left] / visual.space,
      top: cover[rules.posKey][rules.top] / visual.space,
      right: cover[rules.posKey][rules.right] / visual.space,
      bottom: cover[rules.posKey][rules.bottom] / visual.space,
    }));

    const { card, split } = cameraCard(channel, visual);
    const view = shot(channel, visual);
    const side = tag("div", "shot-side");
    split.append(view.node, side);

    const count = tag("p", "note", "");
    const add = button("Add a block", "btn btn-go");
    const bar = tag("div", "toolbar");
    bar.append(add, tag("span", "spacer"), count);
    side.append(bar);
    const list = tag("div", "stack");
    side.append(list);
    side.append(
      tag("p", "note",
        "A block hides that part on the live view and in the saved video. "
        + "What it hides is gone for good."),
    );

    function save() {
      const next = live[rules.coversKey].map((cover, index) => {
        if (index >= rules.limit) return cover;
        const box = covers[index];
        const spot = cover[rules.posKey].slice();
        spot[rules.left] = Math.round(Math.min(box.left, box.right) * visual.space);
        spot[rules.top] = Math.round(Math.min(box.top, box.bottom) * visual.space);
        spot[rules.right] = Math.round(Math.max(box.left, box.right) * visual.space);
        spot[rules.bottom] = Math.round(Math.max(box.top, box.bottom) * visual.space);
        // Both flags together, so the block hides the saved video and the
        // live view. One without the other reads as a block that failed.
        return {
          ...cover,
          [rules.onKey]: box.on,
          [rules.previewKey]: box.on,
          [rules.posKey]: spot,
        };
      });
      const live_on = covers.filter((box) => box.on).length;
      queuePath(config, join(channel, rules.coversKey), next,
        live[rules.coversKey]);
      queuePath(config, join(channel, rules.countKey), live_on,
        live[rules.countKey]);
    }

    function draw() {
      view.layer.replaceChildren();
      list.replaceChildren();
      const on = covers.filter((box) => box.on).length;
      count.textContent = on === 1 ? "1 block in use" : `${on} blocks in use`;
      add.disabled = on >= rules.limit;

      covers.forEach((box, index) => {
        if (!box.on) return;
        const node = tag("div", BOX_CLASS);
        node.style.left = percent(Math.min(box.left, box.right));
        node.style.top = percent(Math.min(box.top, box.bottom));
        node.style.width = percent(Math.abs(box.right - box.left));
        node.style.height = percent(Math.abs(box.bottom - box.top));
        node.append(tag("span", "shot-tag", String(index + 1)));
        const grip = tag("div", HANDLE_CLASS);
        node.append(grip);
        view.layer.append(node);

        let held = null;
        view.drag(node, (spot) => {
          if (!held) {
            held = { x: spot.x - box.left, y: spot.y - box.top };
          }
          const width = box.right - box.left;
          const height = box.bottom - box.top;
          box.left = clamp(spot.x - held.x);
          box.top = clamp(spot.y - held.y);
          box.right = clamp(box.left + width);
          box.bottom = clamp(box.top + height);
          node.style.left = percent(box.left);
          node.style.top = percent(box.top);
        }, () => {
          held = null;
          draw();
          save();
        });

        view.drag(grip, (spot) => {
          box.right = clamp(Math.max(spot.x, box.left + visual.minSize));
          box.bottom = clamp(Math.max(spot.y, box.top + visual.minSize));
          node.style.width = percent(box.right - box.left);
          node.style.height = percent(box.bottom - box.top);
        }, () => {
          draw();
          save();
        });

        const row = tag("div", "toolbar");
        row.append(tag("strong", "", `Block ${index + 1}`));
        row.append(tag("span", "spacer"));
        const drop = button("Remove");
        drop.addEventListener("click", () => {
          box.on = false;
          draw();
          save();
        });
        row.append(drop);
        list.append(row);
      });

      if (!on) {
        list.append(tag("p", "note", "No blocks yet. The whole picture is saved."));
      }
    }

    add.addEventListener("click", () => {
      const slot = covers.findIndex((box) => !box.on);
      if (slot < 0) return;
      covers[slot] = { on: true, ...DEFAULT_BOX };
      draw();
      save();
    });

    draw();
    parts.push(card);
  }
  return parts;
}

/* ------------------------------------------------- on screen text -------- */

function overlayEditor(data, queuePath) {
  const visual = data.visual;
  const rules = visual.overlay;
  const config = data.configs.find(
    (one) => one.value && one.value[data.channels[0]]
      && one.value[data.channels[0]][rules.labels[0].key],
  );
  if (!config) return null;
  const parts = [];

  for (const channel of data.channels) {
    const live = config.value[channel];
    if (!live) continue;
    const { card, split } = cameraCard(channel, visual);
    const view = shot(channel, visual);
    const side = tag("div", "shot-side");
    split.append(view.node, side);
    side.append(
      tag("p", "note", "Drag either label. The recorder draws them on the video too."),
    );

    for (const label of rules.labels) {
      const field = live[label.key];
      if (!field) continue;
      const spot = {
        x: field[rules.posKey][rules.x] / visual.space,
        y: field[rules.posKey][rules.y] / visual.space,
      };

      const chip = tag("div", CHIP_CLASS, label.title);
      chip.style.left = percent(spot.x);
      chip.style.top = percent(spot.y);
      view.layer.append(chip);

      let held = null;
      view.drag(chip, (at) => {
        if (!held) held = { x: at.x - spot.x, y: at.y - spot.y };
        spot.x = clamp(at.x - held.x);
        spot.y = clamp(at.y - held.y);
        chip.style.left = percent(spot.x);
        chip.style.top = percent(spot.y);
      }, () => {
        held = null;
        const next = field[rules.posKey].slice();
        next[rules.x] = Math.round(spot.x * visual.space);
        next[rules.y] = Math.round(spot.y * visual.space);
        queuePath(config, join(channel, label.key, rules.posKey), next,
          field[rules.posKey]);
      });

      const row = tag("div", "panel");
      row.append(tag("strong", "", label.title));
      row.append(switchRow(
        "Draw it on the saved video",
        Boolean(field[rules.onKey]),
        (on) => queuePath(config, join(channel, label.key, rules.onKey), on,
          field[rules.onKey]),
      ));
      row.append(switchRow(
        "Show it on the live view",
        Boolean(field[rules.previewKey]),
        (on) => queuePath(config, join(channel, label.key, rules.previewKey), on,
          field[rules.previewKey]),
      ));
      row.append(colourRow(
        "Text colour", field[rules.frontKey], visual,
        (value) => queuePath(config, join(channel, label.key, rules.frontKey),
          value, field[rules.frontKey]),
      ));
      row.append(colourRow(
        "Background", field[rules.backKey], visual,
        (value) => queuePath(config, join(channel, label.key, rules.backKey),
          value, field[rules.backKey]),
      ));
      side.append(row);
    }
    parts.push(card);
  }
  return parts;
}

/* --------------------------------------------------- movement brush ------ */

function motionEditor(data, queuePath) {
  const visual = data.visual;
  const rules = visual.motion;
  const swann = data.configs.find((one) => one.name === rules.swannConfig);
  const detect = data.configs.find((one) => one.name === rules.config);
  if (!swann || !detect || !swann.value || !detect.value) return null;
  const parts = [];

  for (const channel of data.channels) {
    const path = rules.swannPath.replace("{channel}", String(channel));
    const stored = readAt(swann.value, path);
    const live = detect.value[channel];
    if (!Array.isArray(stored) || !live) continue;

    // Count the real grid off the recorder's own answer: one row per string
    // it sent, four columns per hex digit. Fall back to the numbers from
    // config.py only if the answer cannot be counted.
    const digits = String(stored[0] || "").replace(/^0x/i, "").length
      || rules.digits;
    const columns = digits * BITS_PER_DIGIT || rules.columns;
    const rowCount = stored.length || rules.rows;
    const grid = [];
    for (let row = 0; row < rowCount; row += 1) {
      grid.push(readRow(stored[row], columns));
    }

    const { card, split } = cameraCard(channel, visual);
    const view = shot(channel, visual);
    const side = tag("div", "shot-side");
    split.append(view.node, side);

    const cells = [];
    const mesh = tag("div", "brush");
    mesh.style.setProperty("--brush-cols", String(columns));
    mesh.style.setProperty("--brush-rows", String(rowCount));
    for (let row = 0; row < rowCount; row += 1) {
      cells.push([]);
      for (let column = 0; column < columns; column += 1) {
        const cell = tag("div", "brush-cell");
        mesh.append(cell);
        cells[row].push(cell);
      }
    }
    view.layer.append(mesh);

    function paintCell(row, column, on) {
      grid[row][column] = on;
      cells[row][column].classList.toggle("brush-on", on);
    }

    function show() {
      for (let row = 0; row < rowCount; row += 1) {
        for (let column = 0; column < columns; column += 1) {
          cells[row][column].classList.toggle("brush-on", grid[row][column]);
        }
      }
    }

    /* Write the same grid into both configs, the way the recorder's own
       page does. Each one keeps its own number of rows, so a row it holds
       that the brush does not reach is left exactly as it was read. */
    function intoConfig(rows) {
      const out = rows.slice();
      for (let row = 0; row < out.length && row < rowCount; row += 1) {
        const width = String(out[row] || "").replace(/^0x/i, "").length
          || digits;
        out[row] = writeRow(
          grid[row].slice(0, width * BITS_PER_DIGIT),
          width, visual.colour.prefix,
        );
      }
      return out;
    }

    /* The plain config goes first and Swann's one last. Writing Swann's
       makes the recorder copy the grid into the plain one by itself, so
       with the other order the plain write is read back mid copy and the
       page wrongly says the recorder ignored it. */
    function save() {
      const mine = live[rules.regionKey];
      if (Array.isArray(mine)) {
        queuePath(detect, join(channel, rules.regionKey), intoConfig(mine),
          mine);
      }
      queuePath(swann, path, intoConfig(stored), stored);
    }

    /* Brushing fills the whole block between where you started and where
       you are now, the same way the recorder's own page does it. */
    let mode = null;
    let from = null;
    let started = null;
    view.drag(mesh, (at) => {
      const row = Math.min(rowCount - 1, Math.floor(at.y * rowCount));
      const column = Math.min(columns - 1, Math.floor(at.x * columns));
      if (mode === null) {
        mode = grid[row][column] ? PAINT_OFF : PAINT_ON;
        from = { row, column };
        started = grid.map((line) => line.slice());
      }
      grid.forEach((line, y) => line.forEach((_, x) => {
        grid[y][x] = started[y][x];
      }));
      const firstRow = Math.min(from.row, row);
      const lastRow = Math.max(from.row, row);
      const firstCol = Math.min(from.column, column);
      const lastCol = Math.max(from.column, column);
      for (let y = firstRow; y <= lastRow; y += 1) {
        for (let x = firstCol; x <= lastCol; x += 1) {
          paintCell(y, x, mode === PAINT_ON);
        }
      }
      show();
    }, () => {
      mode = null;
      from = null;
      started = null;
      save();
    });

    const bar = tag("div", "toolbar");
    const all = button("Watch it all");
    const none = button("Watch nothing");
    all.addEventListener("click", () => {
      grid.forEach((row, y) => row.forEach((_, x) => { grid[y][x] = true; }));
      show();
      save();
    });
    none.addEventListener("click", () => {
      grid.forEach((row, y) => row.forEach((_, x) => { grid[y][x] = false; }));
      show();
      save();
    });
    bar.append(all, none);
    side.append(bar);

    side.append(switchRow(
      "Watch this camera for movement",
      Boolean(live[rules.enableKey]),
      (on) => queuePath(detect, join(channel, rules.enableKey), on,
        live[rules.enableKey]),
    ));
    side.append(chooseRow(
      "How easily it triggers",
      rules.levels,
      live[rules.levelKey],
      (value) => queuePath(detect, join(channel, rules.levelKey), value,
        live[rules.levelKey]),
    ));
    side.append(
      tag("p", "note",
        "Brush the parts to watch. Leave out a road or a tree and you get "
        + "fewer alerts you do not want."),
    );

    show();
    parts.push(card);
  }
  return parts;
}

/* -------------------------------------------------------- shapes --------- */

function shapeEditor(data, queuePath) {
  const visual = data.visual;
  const rules = visual.shape;
  const point = visual.point;
  const config = data.configs[0];
  if (!config || !config.value) return null;
  const parts = [];

  for (const channel of data.channels) {
    const live = config.value[channel];
    if (!live) continue;
    const bounds = readAt(live, rules.boundaryPath);
    const rule = readAt(live, rules.rulePath);
    const types = readAt(live, rules.typePath);
    if (!bounds || !rule) continue;

    // 16 slots, used as 4 shapes of 4 corners.
    const shapes = [];
    for (let index = 0; index < rules.rules; index += 1) {
      const corners = [];
      for (let corner = 0; corner < rules.corners; corner += 1) {
        const slot = bounds[rules.pointsKey][index * rules.corners + corner] || {};
        corners.push({
          x: (slot[point.x] || 0) / visual.space,
          y: (slot[point.y] || 0) / visual.space,
        });
      }
      const drawn = corners.some((spot) => spot.x !== 0 || spot.y !== 0);
      shapes.push({
        corners,
        drawn,
        mode: bounds[rules.modeKey][index] || 0,
        on: Boolean(bounds[rules.validKey][index]),
      });
    }

    const { card, split } = cameraCard(channel, visual);
    const view = shot(channel, visual);
    const side = tag("div", "shot-side");
    split.append(view.node, side);

    const add = button("Add a shape", "btn btn-go");
    const bar = tag("div", "toolbar");
    const count = tag("p", "note", "");
    bar.append(add, tag("span", "spacer"), count);
    side.append(bar);
    const list = tag("div", "stack");
    side.append(list);

    function save() {
      const points = bounds[rules.pointsKey].slice();
      const modes = bounds[rules.modeKey].slice();
      const valid = bounds[rules.validKey].slice();
      shapes.forEach((shape, index) => {
        shape.corners.forEach((spot, corner) => {
          const slot = index * rules.corners + corner;
          points[slot] = shape.drawn
            ? {
                [point.x]: Math.round(spot.x * visual.space),
                [point.y]: Math.round(spot.y * visual.space),
              }
            : { [point.x]: rules.empty, [point.y]: rules.empty };
        });
        modes[index] = shape.drawn ? shape.mode : 0;
        valid[index] = shape.on ? 1 : 0;
      });
      const base = join(channel, rules.boundaryPath);
      queuePath(config, join(base, rules.pointsKey), points,
        bounds[rules.pointsKey]);
      queuePath(config, join(base, rules.modeKey), modes, bounds[rules.modeKey]);
      queuePath(config, join(base, rules.validKey), valid,
        bounds[rules.validKey]);
      const drawn = shapes.filter((shape) => shape.drawn).length;
      queuePath(config, join(base, rules.countKey),
        drawn * rules.corners, bounds[rules.countKey]);
    }

    function draw() {
      view.sheet.replaceChildren();
      view.layer.replaceChildren();
      list.replaceChildren();
      const drawn = shapes.filter((shape) => shape.drawn).length;
      count.textContent = drawn === 1 ? "1 shape" : `${drawn} shapes`;
      add.disabled = drawn >= rules.rules;

      shapes.forEach((shape, index) => {
        if (!shape.drawn) return;
        const outline = svgTag("polygon", shape.on ? "shot-poly" : "shot-poly shot-faint");
        outline.setAttribute(
          "points",
          shape.corners
            .map((spot) => `${spot.x * visual.space},${spot.y * visual.space}`)
            .join(" "),
        );
        view.sheet.append(outline);

        shape.corners.forEach((spot, corner) => {
          const grip = tag("div", HANDLE_CLASS);
          grip.classList.add("shot-handle-free");
          grip.style.left = percent(spot.x);
          grip.style.top = percent(spot.y);
          view.layer.append(grip);
          view.drag(grip, (at) => {
            shape.corners[corner] = { x: at.x, y: at.y };
            grip.style.left = percent(at.x);
            grip.style.top = percent(at.y);
            outline.setAttribute(
              "points",
              shape.corners
                .map((one) => `${one.x * visual.space},${one.y * visual.space}`)
                .join(" "),
            );
          }, () => save());
        });

        const row = tag("div", "panel");
        const head = tag("div", "toolbar");
        head.append(tag("strong", "", `Shape ${index + 1}`));
        head.append(tag("span", "spacer"));
        const drop = button("Remove");
        drop.addEventListener("click", () => {
          shape.drawn = false;
          draw();
          save();
        });
        head.append(drop);
        row.append(head);
        row.append(switchRow("Watch this shape", shape.on, (on) => {
          shape.on = on;
          draw();
          save();
        }));
        row.append(chooseRow(
          "Which way counts", visual.directions, shape.mode, (value) => {
            shape.mode = value;
            save();
          },
        ));
        list.append(row);
      });

      if (!drawn) {
        list.append(tag("p", "note", "No shapes yet. Nothing is being watched."));
      }
    }

    add.addEventListener("click", () => {
      const slot = shapes.findIndex((shape) => !shape.drawn);
      if (slot < 0) return;
      shapes[slot].drawn = true;
      shapes[slot].on = true;
      shapes[slot].corners = DEFAULT_SHAPE.map((spot) => ({ ...spot }));
      draw();
      save();
    });

    side.append(switchRow(
      "Switch this on for this camera",
      Boolean(live.Enable),
      (on) => queuePath(config, join(channel, "Enable"), on, live.Enable),
    ));
    side.append(switchRow(
      "Show the shapes on the video",
      Boolean(rule[rules.showKey]),
      (on) => {
        queuePath(config, join(channel, rules.rulePath, rules.showKey), on ? 1 : 0,
          rule[rules.showKey]);
        queuePath(config, join(channel, rules.rulePath, rules.trackKey), on ? 1 : 0,
          rule[rules.trackKey]);
      },
    ));
    if (types) {
      side.append(switchRow(
        "Count people", Boolean(types[rules.humanKey]),
        (on) => queuePath(config, join(channel, rules.typePath, rules.humanKey),
          on ? 1 : 0, types[rules.humanKey]),
      ));
      side.append(switchRow(
        "Count vehicles", Boolean(types[rules.vehicleKey]),
        (on) => queuePath(config, join(channel, rules.typePath, rules.vehicleKey),
          on ? 1 : 0, types[rules.vehicleKey]),
      ));
    }

    draw();
    parts.push(card);
  }
  return parts;
}

/* ---------------------------------------------------------- lines -------- */

function lineEditor(data, queuePath) {
  const visual = data.visual;
  const rules = visual.line;
  const shapeRules = visual.shape;
  const point = visual.point;
  const config = data.configs[0];
  if (!config || !config.value) return null;
  const parts = [];

  for (const channel of data.channels) {
    const live = config.value[channel];
    if (!live) continue;
    const wires = readAt(live, rules.path);
    const rule = readAt(live, shapeRules.rulePath);
    const types = readAt(live, shapeRules.typePath);
    if (!Array.isArray(wires) || !rule) continue;

    const lines = [];
    for (let index = 0; index < rules.count; index += 1) {
      const wire = wires[index] || {};
      const spots = wire[rules.lineKey];
      const start = (spots && spots[rules.startKey]) || {};
      const end = (spots && spots[rules.endKey]) || {};
      const made = {
        x1: (start[point.x] || 0) / visual.space,
        y1: (start[point.y] || 0) / visual.space,
        x2: (end[point.x] || 0) / visual.space,
        y2: (end[point.y] || 0) / visual.space,
      };
      lines.push({
        ...made,
        drawn: made.x1 !== 0 || made.y1 !== 0 || made.x2 !== 0 || made.y2 !== 0,
        dir: wire[rules.dirKey] || 0,
        on: Boolean(wire[rules.validKey]),
      });
    }

    const { card, split } = cameraCard(channel, visual);
    const view = shot(channel, visual);
    const side = tag("div", "shot-side");
    split.append(view.node, side);

    const add = button("Add a line", "btn btn-go");
    const count = tag("p", "note", "");
    const bar = tag("div", "toolbar");
    bar.append(add, tag("span", "spacer"), count);
    side.append(bar);
    const list = tag("div", "stack");
    side.append(list);

    function save() {
      const next = wires.map((wire, index) => {
        if (index >= rules.count) return wire;
        const line = lines[index];
        const places = line.drawn
          ? [line.x1, line.y1, line.x2, line.y2]
          : [0, 0, 0, 0];
        return {
          ...wire,
          [rules.lineKey]: {
            [rules.startKey]: {
              [point.x]: Math.round(places[0] * visual.space),
              [point.y]: Math.round(places[1] * visual.space),
            },
            [rules.endKey]: {
              [point.x]: Math.round(places[2] * visual.space),
              [point.y]: Math.round(places[3] * visual.space),
            },
          },
          [rules.dirKey]: line.drawn ? line.dir : 0,
          [rules.validKey]: line.on ? 1 : 0,
        };
      });
      queuePath(config, join(channel, rules.path), next, wires);
    }

    function draw() {
      view.sheet.replaceChildren();
      view.layer.replaceChildren();
      list.replaceChildren();
      const drawn = lines.filter((line) => line.drawn).length;
      count.textContent = drawn === 1 ? "1 line" : `${drawn} lines`;
      add.disabled = drawn >= rules.count;

      lines.forEach((line, index) => {
        if (!line.drawn) return;
        const stroke = svgTag("line", line.on ? "shot-line" : "shot-line shot-faint");
        const place = () => {
          stroke.setAttribute("x1", String(line.x1 * visual.space));
          stroke.setAttribute("y1", String(line.y1 * visual.space));
          stroke.setAttribute("x2", String(line.x2 * visual.space));
          stroke.setAttribute("y2", String(line.y2 * visual.space));
        };
        place();
        view.sheet.append(stroke);

        [["x1", "y1"], ["x2", "y2"]].forEach(([keyX, keyY], end) => {
          const grip = tag("div", `${HANDLE_CLASS} shot-handle-free`);
          grip.append(tag("span", "shot-end", end === 0 ? "A" : "B"));
          grip.style.left = percent(line[keyX]);
          grip.style.top = percent(line[keyY]);
          view.layer.append(grip);
          view.drag(grip, (at) => {
            line[keyX] = at.x;
            line[keyY] = at.y;
            grip.style.left = percent(at.x);
            grip.style.top = percent(at.y);
            place();
          }, () => save());
        });

        const row = tag("div", "panel");
        const head = tag("div", "toolbar");
        head.append(tag("strong", "", `Line ${index + 1}`));
        head.append(tag("span", "spacer"));
        const drop = button("Remove");
        drop.addEventListener("click", () => {
          line.drawn = false;
          draw();
          save();
        });
        head.append(drop);
        row.append(head);
        row.append(switchRow("Watch this line", line.on, (on) => {
          line.on = on;
          draw();
          save();
        }));
        row.append(chooseRow(
          "Which way counts", visual.directions, line.dir, (value) => {
            line.dir = value;
            save();
          },
        ));
        list.append(row);
      });

      if (!drawn) {
        list.append(tag("p", "note", "No lines yet. Nothing is being watched."));
      }
    }

    add.addEventListener("click", () => {
      const slot = lines.findIndex((line) => !line.drawn);
      if (slot < 0) return;
      Object.assign(lines[slot], DEFAULT_LINE, { drawn: true, on: true });
      draw();
      save();
    });

    side.append(switchRow(
      "Switch this on for this camera",
      Boolean(live.Enable),
      (on) => queuePath(config, join(channel, "Enable"), on, live.Enable),
    ));
    if (types) {
      side.append(switchRow(
        "Count people", Boolean(types[shapeRules.humanKey]),
        (on) => queuePath(config,
          join(channel, shapeRules.typePath, shapeRules.humanKey),
          on ? 1 : 0, types[shapeRules.humanKey]),
      ));
      side.append(switchRow(
        "Count vehicles", Boolean(types[shapeRules.vehicleKey]),
        (on) => queuePath(config,
          join(channel, shapeRules.typePath, shapeRules.vehicleKey),
          on ? 1 : 0, types[shapeRules.vehicleKey]),
      ));
    }
    side.append(
      tag("p", "note",
        "A is the first end, B is the second. Set which way counts, or leave "
        + "it on either way."),
    );

    draw();
    parts.push(card);
  }
  return parts;
}

/* ------------------------------------------------------- the week -------- */

function slotText(slot, week) {
  const minutes = slot * week.slotMinutes
    + week.firstHour * MINUTES_IN_HOUR;
  const hour = Math.floor(minutes / MINUTES_IN_HOUR) % HOURS_IN_DAY;
  const minute = minutes % MINUTES_IN_HOUR;
  return `${String(hour).padStart(PAD, "0")}:${String(minute).padStart(PAD, "0")}`;
}

/* One painted week for one trigger, on one camera. */
function weekGrid(sheet, row, week, onChange) {
  const box = tag("div", "week");
  const cells = [];

  const spine = tag("div", "week-hours");
  const slotsPerHour = MINUTES_IN_HOUR / week.slotMinutes;
  for (let hour = 0; hour < HOURS_IN_DAY; hour += 1) {
    const mark = tag("div", "week-hour",
      hour % HOUR_LABEL_STEP === 0 ? String(hour) : "");
    mark.style.setProperty("--span", String(slotsPerHour));
    spine.append(mark);
  }
  box.append(tag("div", "week-corner", ""), spine);

  week.days.forEach((day, index) => {
    box.append(tag("div", "week-day", day.slice(0, HOUR_LABEL_STEP)));
    const strip = tag("div", "week-strip");
    strip.style.setProperty("--week-slots", String(week.slots));
    cells.push([]);
    for (let slot = 0; slot < week.slots; slot += 1) {
      const cell = tag("div", "week-cell");
      cell.title = `${day}, ${slotText(slot, week)}`;
      strip.append(cell);
      cells[index].push(cell);
    }
    box.append(strip);
  });

  function show() {
    week.days.forEach((_, day) => {
      const text = sheet[row][day] || "";
      for (let slot = 0; slot < week.slots; slot += 1) {
        cells[day][slot].classList.toggle("week-on", text[slot] === week.on);
      }
    });
  }

  function set(day, slot, on) {
    const text = sheet[row][day].split("");
    text[slot] = on ? week.on : week.off;
    sheet[row][day] = text.join("");
    cells[day][slot].classList.toggle("week-on", on);
  }

  function spot(event) {
    const bounds = box.getBoundingClientRect();
    const first = cells[0][0].getBoundingClientRect();
    const column = Math.floor(
      (event.clientX - first.left) / (first.width || 1),
    );
    const rowSize = first.height || 1;
    const line = Math.floor((event.clientY - first.top) / rowSize);
    if (column < 0 || column >= week.slots) return null;
    if (line < 0 || line >= week.days.length) return null;
    if (event.clientX > bounds.right || event.clientY > bounds.bottom) return null;
    return { day: line, slot: column };
  }

  /* Dragging fills the whole block between where you started and where you
     are now, so one drag can cover Monday to Friday, nine to five. Dragging
     back out of it puts those hours back. */
  box.addEventListener("pointerdown", (event) => {
    if (event.button !== POINTER_PRIMARY) return;
    const from = spot(event);
    if (!from) return;
    event.preventDefault();
    box.setPointerCapture(event.pointerId);
    const started = sheet[row].slice();
    const mode = sheet[row][from.day][from.slot] === week.on
      ? PAINT_OFF
      : PAINT_ON;

    const fill = (to) => {
      sheet[row] = started.slice();
      const firstDay = Math.min(from.day, to.day);
      const lastDay = Math.max(from.day, to.day);
      const firstSlot = Math.min(from.slot, to.slot);
      const lastSlot = Math.max(from.slot, to.slot);
      for (let day = firstDay; day <= lastDay; day += 1) {
        for (let slot = firstSlot; slot <= lastSlot; slot += 1) {
          set(day, slot, mode === PAINT_ON);
        }
      }
      show();
    };
    fill(from);

    const move = (moving) => {
      const next = spot(moving);
      if (next) fill(next);
    };
    const up = () => {
      box.removeEventListener("pointermove", move);
      box.removeEventListener("pointerup", up);
      box.removeEventListener("pointercancel", up);
      onChange();
    };
    box.addEventListener("pointermove", move);
    box.addEventListener("pointerup", up);
    box.addEventListener("pointercancel", up);
  });

  show();
  return { node: box, show };
}

function weekEditor(data, queuePath) {
  const visual = data.visual;
  const week = visual.week;
  const isStills = Boolean(
    data.configs.find((one) => one.name === week.stillsConfig),
  );
  const rows = isStills ? week.stillsRows : week.recordRows;
  const mainName = isStills ? week.stillsConfig : week.recordConfigs[0];
  const main = data.configs.find((one) => one.name === mainName);
  if (!main || !main.value) return null;
  // The recorder's own page writes the plain and the extra copy together, so
  // this does the same. Anything missing is simply skipped.
  const alsoNames = isStills ? [] : week.recordConfigs.slice(1);
  const also = alsoNames
    .map((name) => data.configs.find((one) => one.name === name))
    .filter((one) => one && one.value);

  const parts = [];
  for (const channel of data.channels) {
    const live = main.value[channel];
    if (!live || !Array.isArray(live[week.sheetKey])) continue;
    const sheet = live[week.sheetKey].map((day) => day.slice());

    const { card } = cameraCard(channel, visual);
    const body = tag("div", "stack");
    card.append(body);

    function save() {
      queuePath(main, join(channel, week.sheetKey), sheet,
        live[week.sheetKey]);
      for (const other of also) {
        const theirs = other.value[channel];
        if (!theirs || !Array.isArray(theirs[week.sheetKey])) continue;
        // Keep any rows this page does not show exactly as they were.
        const copy = theirs[week.sheetKey].map((day) => day.slice());
        for (const one of rows) {
          if (sheet[one.row]) copy[one.row] = sheet[one.row].slice();
        }
        queuePath(other, join(channel, week.sheetKey), copy,
          theirs[week.sheetKey]);
      }
    }

    for (const one of rows) {
      if (!sheet[one.row]) continue;
      const panel = tag("div", "panel");
      const head = tag("div", "toolbar");
      head.append(tag("strong", "", one.title));
      head.append(tag("span", "spacer"));
      const all = button("All week");
      const clear = button("Clear");
      head.append(all, clear);
      panel.append(head);
      panel.append(tag("p", "note", one.note));
      const grid = weekGrid(sheet, one.row, week, save);
      panel.append(grid.node);
      all.addEventListener("click", () => {
        sheet[one.row] = sheet[one.row].map(() => week.on.repeat(week.slots));
        grid.show();
        save();
      });
      clear.addEventListener("click", () => {
        sheet[one.row] = sheet[one.row].map(() => week.off.repeat(week.slots));
        grid.show();
        save();
      });
      body.append(panel);
    }

    // Any row this page does not name is carried through untouched. Say so
    // only when one of them actually holds something.
    const shown = new Set(rows.map((one) => one.row));
    const others = sheet
      .map((_, index) => index)
      .filter((index) => !shown.has(index))
      .filter((index) => sheet[index].some((day) => day.includes(week.on)));
    if (others.length) {
      body.append(tag("p", "note",
        "This camera also uses a trigger this page cannot name. It is left "
        + "exactly as it is."));
    }

    parts.push(card);
  }
  return parts;
}

/* -------------------------------------------------- the camera tour ------ */

function tourEditor(data, queuePath) {
  const visual = data.visual;
  const rules = visual.tour;
  const config = data.configs.find(
    (one) => Array.isArray(one.value)
      && one.value[0] && Array.isArray(one.value[0][rules.maskKey]),
  );
  if (!config) return null;
  const parts = [];

  config.value.forEach((tour, index) => {
    const card = tag("section", "card");
    const head = tag("div", "card-head");
    const title = rules.typeTitles[tour[rules.typeKey]] || tour[rules.typeKey];
    head.append(tag("h2", "", title));
    card.append(head);

    card.append(switchRow(
      "Cycle the cameras on the recorder's own screen",
      Boolean(tour[rules.enableKey]),
      (on) => queuePath(config, join(index, rules.enableKey), on,
        tour[rules.enableKey]),
    ));
    card.append(numberRow(
      "Seconds on each one", tour[rules.intervalKey],
      (value) => queuePath(config, join(index, rules.intervalKey), value,
        tour[rules.intervalKey]),
    ));

    const mask = tour[rules.maskKey].slice();
    for (const split of rules.splits) {
      if (split.index >= mask.length) continue;
      const panel = tag("div", "panel");
      panel.append(tag("strong", "", split.title));
      const chips = tag("div", "chips");
      for (const channel of data.channels) {
        const label = tag("label", "chip");
        const tick = document.createElement("input");
        tick.type = "checkbox";
        tick.checked = bitSet(mask[split.index], channel);
        tick.addEventListener("change", () => {
          mask[split.index] = withBit(
            mask[split.index], channel, tick.checked,
            visual.colour.digits, visual.colour.prefix,
          );
          queuePath(config, join(index, rules.maskKey), mask,
            tour[rules.maskKey]);
        });
        label.append(tick, tag("span", "", cameraTitle(channel, visual)));
        chips.append(label);
      }
      panel.append(chips);
      card.append(panel);
    }
    parts.push(card);
  });

  if (parts.length) {
    parts[0].prepend(tag("p", "note",
      "This is the monitor plugged into the recorder, not this page."));
  }
  return parts;
}

/* ------------------------------------------------- small shared rows ----- */

function switchRow(label, on, onChange) {
  const row = tag("div", "field");
  row.append(tag("div", "field-label", label));
  const wrap = tag("label", "switch");
  const box = document.createElement("input");
  box.type = "checkbox";
  box.checked = on;
  const text = tag("span", "switch-text", on ? "On" : "Off");
  box.addEventListener("change", () => {
    text.textContent = box.checked ? "On" : "Off";
    onChange(box.checked);
  });
  wrap.append(box, text);
  row.append(wrap);
  return row;
}

function chooseRow(label, choices, value, onChange) {
  const row = tag("div", "field");
  row.append(tag("div", "field-label", label));
  const pick = document.createElement("select");
  for (const choice of choices) {
    const option = document.createElement("option");
    option.value = String(choice.value);
    option.textContent = choice.title;
    if (Number(choice.value) === Number(value)) option.selected = true;
    pick.append(option);
  }
  pick.addEventListener("change", () => onChange(Number(pick.value)));
  row.append(pick);
  return row;
}

function numberRow(label, value, onChange) {
  const row = tag("div", "field");
  row.append(tag("div", "field-label", label));
  const input = document.createElement("input");
  input.type = "number";
  input.value = value;
  input.addEventListener("input", () => onChange(Number(input.value)));
  row.append(input);
  return row;
}

/* The recorder writes a colour as one packed number: see through, red,
   green, blue. A swatch and a slider write the same number back. */
function splitColour(text, colour) {
  const value = String(text || "").replace(/^0x/i, "").padStart(colour.digits, "0");
  return {
    alpha: Number.parseInt(value.slice(0, PAD), HEX_BASE) || 0,
    rgb: `#${value.slice(PAD)}`,
  };
}

function packColour(alpha, rgb, colour) {
  const alphaText = Math.round(alpha).toString(HEX_BASE).padStart(PAD, "0");
  return (colour.prefix + alphaText + rgb.replace("#", "")).toUpperCase()
    .replace("0X", colour.prefix);
}

function colourRow(label, text, visual, onChange) {
  const colour = visual.colour;
  const parted = splitColour(text, colour);
  const row = tag("div", "field");
  row.append(tag("div", "field-label", label));
  const holder = tag("div", "colour");
  const swatch = document.createElement("input");
  swatch.type = "color";
  swatch.value = parted.rgb;
  const fade = document.createElement("input");
  fade.type = "range";
  fade.min = "0";
  fade.max = String(colour.alphaMax);
  fade.value = String(parted.alpha);
  fade.setAttribute("aria-label", `${label}, how solid it is`);
  const send = () => onChange(packColour(Number(fade.value), swatch.value, colour));
  swatch.addEventListener("change", send);
  fade.addEventListener("change", send);
  holder.append(swatch, fade);
  row.append(holder);
  return row;
}

/* ------------------------------------------------------------- paths ----- */

/* Follow a slash separated path into a value, the same way the server does. */
function readAt(value, path) {
  let here = value;
  for (const part of String(path).split("/").filter(Boolean)) {
    if (here === null || here === undefined) return null;
    here = Array.isArray(here) ? here[Number(part)] : here[part];
  }
  return here === undefined ? null : here;
}

/* ------------------------------------------------------------ the door --- */

const EDITORS = {
  privacy: privacyEditor,
  overlay: overlayEditor,
  motion: motionEditor,
  shape: shapeEditor,
  line: lineEditor,
  week: weekEditor,
  tour: tourEditor,
};

/* Draw the editor a screen asks for, or give nothing back so the plain
   field list is used instead. */
function visualEditor(data, queuePath) {
  if (!data.editor || !data.visual) return null;
  const build = EDITORS[data.editor];
  if (!build) return null;
  try {
    const parts = build(data, queuePath);
    return parts && parts.length ? parts : null;
  } catch (error) {
    // A firmware that answers a shape we have not seen must not take the
    // whole screen down, so fall back to the plain field list.
    window.console.warn(`The ${data.editor} editor could not draw.`, error);
    return null;
  }
}

window.visualEditor = visualEditor;
window.visualColourRow = colourRow;
window.visualSplitColour = splitColour;
