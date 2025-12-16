import { registerPuzzle } from "modules/The-Horses-Puzzles/scripts/core.js";

// Fellout Terminal puzzle package entry
// Expects template at modules/The-Horses-Puzzles/Minigames/fellout/templates/fellout.html

class FelloutApp extends Application {
  static get defaultOptions() {
    return foundry.utils.mergeObject(super.defaultOptions, {
      id: "fellout-terminal-puzzle",
      title: "Fellout Terminal",
      template: `modules/The-Horses-Puzzles/Minigames/fellout/templates/fellout.html`,
      classes: ["fellout-terminal"],
      width: 720,
      height: 540,
      popOut: true,
      resizable: true
    });
  }
  activateListeners(html) {
    super.activateListeners(html);
    // Simple success hook: look for a button with data-action="unlock"
    html.on("click", "[data-action='unlock']", () => {
      // Notify core via postMessage or direct call
      window.postMessage({ module: "The-Horses-Puzzles", action: "solved", context: this.context }, "*");
      this.close();
    });
  }
  async renderWithContext(context) {
    this.context = context;
    return this.render(true);
  }
}

registerPuzzle({
  id: "fellout",
  title: "Fellout Terminal",
  load: async () => {
    // no-op for now; could lazy-load CSS/assets
  },
  open: async (context) => {
    const app = new FelloutApp();
    await app.renderWithContext(context);
  }
});

export default function init() { /* optional init */ }