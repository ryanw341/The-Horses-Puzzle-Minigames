// The Horse's Puzzle Minigames core
// Minimal scaffolding: registry, settings, hooks, and opening puzzles

const MODULE_ID = "The-Horses-Puzzles";

class PuzzleRegistry {
  constructor() {
    this.packages = new Map(); // id -> {title, open, load?, configSchema?}
    this.enabled = new Set();
  }
  register(pkg) {
    if (!pkg?.id || !pkg?.title || typeof pkg.open !== "function") return;
    this.packages.set(pkg.id, pkg);
  }
  enable(id, value) {
    if (value) this.enabled.add(id); else this.enabled.delete(id);
    game.settings.set(MODULE_ID, "enabledPackages", Array.from(this.enabled));
  }
  isEnabled(id) { return this.enabled.has(id); }
  async open(type, context) {
    const pkg = this.packages.get(type);
    if (!pkg) return ui.notifications?.warn(`Puzzle not found: ${type}`);
    if (!this.isEnabled(type)) return ui.notifications?.warn(`Puzzle disabled: ${type}`);
    if (typeof pkg.load === "function") await pkg.load();
    return pkg.open(context);
  }
}

const registry = new PuzzleRegistry();

const BUILT_IN_PUZZLES = [
  { id: "fellout", title: "Fellout Terminal Puzzle", path: "Minigames/Fellout Terminal Puzzle/index.html" },
  { id: "wire", title: "Wiring Puzzle", path: "Minigames/Wire Puzzle/WireGenEasy.html" },
];

function openIframePuzzle({ id, title, path, context }) {
  const src = encodeURI(`modules/${MODULE_ID}/${path}`);
  return new Promise((resolve) => {
    let done = false;
    const listener = async (ev) => {
      if (ev?.data?.module !== MODULE_ID || ev?.data?.puzzle !== id || ev?.data?.action !== "solved") return;
      done = true;
      window.removeEventListener("message", listener);
      try {
        if (context?.kind === "door" && context?.wall) {
          await context.wall.document.update({ ds: CONST.WALL_DOOR_STATES.CLOSED });
          ui.notifications?.info("Door unlocked.");
        } else if (context?.kind === "actor" && context?.token) {
          ui.notifications?.info("Access granted.");
        }
      } catch (err) {
        console.error(`${MODULE_ID} puzzle completion`, err);
      }
      resolve(true);
    };
    window.addEventListener("message", listener);
    const dialog = new Dialog({
      title,
      content: `<iframe src="${src}" style="width:100%; height:600px; border:none;"></iframe>`,
      buttons: {},
      close: () => {
        window.removeEventListener("message", listener);
        if (!done) resolve(false);
      }
    });
    dialog.render(true);
  });
}

function registerSettings() {
  game.settings.register(MODULE_ID, "enabledPackages", {
    name: "Enabled Puzzle Packages",
    hint: "List of puzzle IDs enabled globally.",
    scope: "world",
    config: true,
    type: Array,
    default: ["fellout", "wire"],
  });
  game.settings.register(MODULE_ID, "defaultDoorPuzzle", {
    name: "Default Door Puzzle",
    hint: "Puzzle type applied to doors when enabled.",
    scope: "world",
    config: true,
    type: String,
    default: "",
    choices: () => Object.fromEntries(Array.from(registry.packages.entries()).map(([id, p]) => [id, p.title]))
  });
  game.settings.register(MODULE_ID, "defaultActorPuzzle", {
    name: "Default Actor Puzzle",
    hint: "Puzzle type applied to actors when enabled.",
    scope: "world",
    config: true,
    type: String,
    default: "",
    choices: () => Object.fromEntries(Array.from(registry.packages.entries()).map(([id, p]) => [id, p.title]))
  });
}

function applyEnabledFromSettings() {
  const enabled = game.settings.get(MODULE_ID, "enabledPackages") || [];
  registry.enabled = new Set(enabled);
}

function injectWallConfigFlags(app, html) {
  const tab = html.find(".tab[data-tab='door']");
  if (!tab.length) return;
  const enabled = app.object.getFlag(MODULE_ID, "enabled") || false;
  const type = app.object.getFlag(MODULE_ID, "type") || game.settings.get(MODULE_ID, "defaultDoorPuzzle") || "";
  const choices = Object.fromEntries(Array.from(registry.packages.entries()).map(([id, p]) => [id, p.title]));
  const select = `<select name="flags.${MODULE_ID}.type">${Object.entries(choices).map(([id, title]) => `<option value="${id}" ${id===type?"selected":""}>${title}</option>`).join("")}</select>`;
  const checkbox = `<input type="checkbox" name="flags.${MODULE_ID}.enabled" ${enabled?"checked":""}> Enable Puzzle`;
  const row = $(`<div class="form-group"><label>Puzzle</label><div class="form-fields">${checkbox}${select}</div></div>`);
  tab.append(row);
}

async function handleDoorClick(wrapped, event) {
  try {
    const doorControl = this; // DoorControl instance context
    const wall = doorControl.wall;
    const enabled = wall?.getFlag(MODULE_ID, "enabled");
    const type = wall?.getFlag(MODULE_ID, "type") || game.settings.get(MODULE_ID, "defaultDoorPuzzle");
    if (enabled && type) {
      event.preventDefault();
      event.stopPropagation();
      await registry.open(type, { kind: "door", wall, doorControl });
      return;
    }
  } catch (e) { console.error(e); }
  return wrapped(event);
}

function addActorHudButton(app, html) {
  const token = app.object;
  const enabled = token.document.getFlag(MODULE_ID, "enabled") || false;
  const type = token.document.getFlag(MODULE_ID, "type") || game.settings.get(MODULE_ID, "defaultActorPuzzle");
  if (!type) return;
  const btn = $(`<div class="control-icon" data-action="horse-puzzle" title="Puzzle"><i class="fas fa-puzzle-piece"></i></div>`);
  btn.on("click", async () => {
    if (!enabled) return ui.notifications?.warn("Puzzle not enabled for this actor.");
    await registry.open(type, { kind: "actor", token });
  });
  html.find(".col.right").append(btn);
}

Hooks.once("init", () => {
  // Setup settings early
  registerSettings();
});

Hooks.once("ready", () => {
  applyEnabledFromSettings();
  // Register bundled puzzles
  for (const pkg of BUILT_IN_PUZZLES) {
    registerPuzzle({
      id: pkg.id,
      title: pkg.title,
      open: (context) => openIframePuzzle({ ...pkg, context })
    });
  }

  // Wrap DoorControl left-click to route to puzzles when enabled
  if (globalThis.libWrapper) {
    libWrapper.register(MODULE_ID, "DoorControl.prototype._onLeftClick", handleDoorClick, "WRAPPER");
  } else {
    console.warn(`${MODULE_ID}: libWrapper is recommended for safe wrapping.`);
  }

  // Inject flags into WallConfig
  Hooks.on("renderWallConfig", injectWallConfigFlags);

  // Add actor HUD button
  Hooks.on("renderTokenHUD", addActorHudButton);

  // Listen for iframe-based puzzle completion
  window.addEventListener("message", (ev) => {
    const data = ev?.data;
    if (!data || data?.module !== MODULE_ID) return;
    if (data?.action === "solved") {
      const ctx = data?.context;
      if (ctx?.kind === "door" && ctx?.wall) {
        ctx.wall.document.update({ ds: CONST.WALL_DOOR_STATES.CLOSED });
        ui.notifications?.info("Door unlocked.");
      }
      if (ctx?.kind === "actor" && ctx?.token) {
        ui.notifications?.info("Access granted.");
      }
    }
  });
});

// Export a small API to allow puzzles to register themselves when imported
export function registerPuzzle(pkg) { registry.register(pkg); }
export function openPuzzle(type, context) { return registry.open(type, context); }
