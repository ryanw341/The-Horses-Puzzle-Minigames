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
  { id: "fellout", title: "Fellout Terminal Puzzle", segments: ["Minigames", "Fellout Terminal Puzzle", "index.html"] },
  { id: "wire", title: "Wiring Puzzle", segments: ["Minigames", "Wire Puzzle", "WireGenEasy.html"] },
];

function openIframePuzzle({ id, title, context }) {
  const puzzle = BUILT_IN_PUZZLES.find((p) => p.id === id);
  const expectedOrigin = window.location?.origin;
  if (!puzzle || !expectedOrigin) return Promise.resolve(false);
  const segments = puzzle.segments ?? [];
  if (!segments.length) return Promise.resolve(false);
  const encodedPath = segments.map((part) => encodeURIComponent(part)).join("/");
  const token = (crypto?.randomUUID?.() ?? (() => {
    if (crypto?.getRandomValues) {
      const bytes = new Uint32Array(4);
      crypto.getRandomValues(bytes);
      return Array.from(bytes).map((b) => b.toString(16)).join("-");
    }
    return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  })());
  const srcUrl = new URL(`modules/${MODULE_ID}/${encodedPath}`, expectedOrigin);
  srcUrl.searchParams.set("parentOrigin", expectedOrigin);
  srcUrl.searchParams.set("token", token);
  const src = srcUrl.toString();
  return new Promise((resolve) => {
    let done = false;
    let iframe = null;
    const listener = async (ev) => {
      if (iframe && ev?.source !== iframe.contentWindow) return;
      if (ev?.origin !== expectedOrigin) return;
      if (ev?.data?.token !== token) return;
      if (ev?.data?.module !== MODULE_ID || ev?.data?.puzzle !== id || ev?.data?.action !== "solved") return;
      done = true;
      window.removeEventListener("message", listener);
      try {
        if (context?.kind === "door" && context?.wall) {
          await context.wall.document.update({ ds: CONST.WALL_DOOR_STATES.OPEN });
          ui.notifications?.info("Door unlocked.");
        } else if (context?.kind === "actor" && context?.token) {
          ui.notifications?.info("Access granted.");
        }
      } catch (err) {
        console.error(`${MODULE_ID} puzzle completion`, err);
      }
      resolve(true);
    };
    const dialog = new Dialog({
      title,
      content: `<iframe src="${src}" style="width:100%; height:600px; border:none;" sandbox="allow-scripts allow-same-origin allow-forms"></iframe>`,
      buttons: {},
      close: () => {
        window.removeEventListener("message", listener);
        if (!done) resolve(false);
      }
    });
    dialog.render(true);
    iframe = dialog.element?.find?.("iframe")?.get?.(0) ?? null;
    window.addEventListener("message", listener);
  });
}

function registerSettings() {
  game.settings.register(MODULE_ID, "enabledPackages", {
    name: "Enabled Puzzle Packages",
    hint: "List of puzzle IDs enabled globally.",
    scope: "world",
    config: true,
    type: Array,
    default: BUILT_IN_PUZZLES.map((p) => p.id),
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
      open: (context) => openIframePuzzle({ id: pkg.id, title: pkg.title, context })
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
});

// Export a small API to allow puzzles to register themselves when imported
export function registerPuzzle(pkg) { registry.register(pkg); }
export function openPuzzle(type, context) { return registry.open(type, context); }
