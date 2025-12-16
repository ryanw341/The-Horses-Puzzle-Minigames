Hooks.once("ready", () => {
  const MODID = "my-puzzle";

  game.modules.get(MODID).api = {
    open(opts = {}) {
      const src = opts.src ?? "modules/my-puzzle/templates/puzzle.html";
      const html = `
        <div style="width:100%;height:100%;padding:0;margin:0;">
          <iframe src="${src}" style="width:100%;height:100%;border:0;"></iframe>
        </div>`;

      new Dialog({
        title: "Wiring Puzzle",
        content: html,
        buttons: {            // ← REQUIRED in v12
          close: { label: "Close" }
        }
      }, {
        width: 840,
        height: 720,
        resizable: true,
        id: `${MODID}-dlg`
      }).render(true);
    }
  };

  console.log(`${MODID} ready`);
});
