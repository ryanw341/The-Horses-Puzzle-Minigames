# The Horse's Puzzle Minigames

A core Foundry VTT module that provides a registry, settings, and HUD integrations for puzzle minigames attached to doors and actors. Individual puzzles live under their own folders and register with this core. The module is intentionally a host architecture: each minigame can be toggled on/off in settings so an unfinished or broken puzzle never takes down the core module or any other puzzles.

- Module ID: The-Horses-Puzzles
- Foundry target: v13+

## Features
- Enable/disable puzzle packages via world settings
- Per-door flags: enable + choose puzzle type
- Actor HUD button to launch puzzles when enabled
- API for puzzle packages to register and open

## Structure
```
The Horse's Puzzle Minigames/
  module.json
  scripts/
    core.js
  puzzles/
    fellout/
      index.js
      templates/
        fellout.html
    wire/
      index.js
      puzzle.html
      Pyodide/
        ...
```

## Installation

### From Foundry VTT
1. In Foundry VTT, go to the "Add-on Modules" tab
2. Click "Install Module"
3. Paste the manifest URL:
   ```
   https://raw.githubusercontent.com/ryanw341/The-Horses-Puzzle-Minigames/main/module.json
   ```
4. Click "Install"

### Manual Installation
1. Download the latest `module.zip` from the [Releases](https://github.com/ryanw341/The-Horses-Puzzle-Minigames/releases) page
2. Extract it to your Foundry VTT `Data/modules/The-Horses-Puzzles` directory
3. Restart Foundry VTT

## Getting Started
1. Enable the module in your world
2. In World Settings, enable the desired puzzle packages and set defaults
3. On a door, open WallConfig and enable puzzle + choose type
4. On an actor token, enable puzzle via flags; use the HUD button to launch

## Local Demo
For a quick offline preview, download the `LocalDemo` folder and open `Puzzles Demo.html`. It lets you enable or hide individual puzzles and run them directly in the browser for smoke testing without Foundry.

## Package API
Puzzle packages should `import { registerPuzzle } from 'modules/The-Horses-Puzzles/scripts/core.js'` and call:
```
registerPuzzle({
  id: 'fellout',
  title: 'Fellout Terminal',
  load: async () => {},
  open: async (context) => { /* render UI and resolve */ }
});
```

## Development

For information about creating releases, see [RELEASE.md](RELEASE.md).
