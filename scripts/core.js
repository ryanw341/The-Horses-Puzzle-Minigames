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

function registerSettings() {
  game.settings.register(MODULE_ID, "enabledPackages", {
    name: "Enabled Puzzle Packages",
    hint: "List of puzzle IDs enabled globally.",
    scope: "world",
    config: true,
    type: Array,
    default: [],
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
  // Try to auto-register default packages located under Minigames/<id>/index.js
  const defaults = ["fellout", "wire"]; // extend as you add more
  for (const id of defaults) {
    const path = `../Minigames/${id}/index.js`;
    import(path).then(mod => {
      if (mod?.default && typeof mod.default === "function") {
        // allow default export to call registerPuzzle internally
        mod.default({ MODULE_ID, registerPuzzle });
      }
      if (mod?.register && typeof mod.register === "function") {
        mod.register({ MODULE_ID, registerPuzzle });
      }
      // Some packages may export a metadata object
      if (mod?.pkg) registerPuzzle(mod.pkg);
      // Refresh settings choices after registration
      // Note: Foundry builds choices at open time; users may need to reopen settings UI.
    }).catch(err => {
      console.debug(`${MODULE_ID}: Package ${id} not found at`, path, err?.message);
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