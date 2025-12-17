# The Horse's Fellout Hacking Puzzle

Foundry VTT module that adds a Fallout-style terminal hacking lock for doors. The module ID is `the-horses-hacking-puzzle` and the UI label is "The Horse's Fellout Hacking Puzzle".

## Installation

1) Drop this folder into your Foundry `Data/modules` directory.
2) In Foundry, install/enable the module. (Add the manifest URL if hosting; locally, this folder is enough.)

## Settings (Configure Settings → Module Settings → The Horse's Fellout Hacking Puzzle)

- `Word Length`
- `Attempts`
- `Timer (seconds)` (0 disables the timer)
- `Max Resets` (blank = unlimited after start)
- `Terminal Color`

## Using on a Door

1) Open the Door configuration (wall config → Door tab → 3-dots menu).
2) Under **Horse's Puzzles**:
   - Enable **Puzzle Lock**
   - Choose **Puzzle Type** → `Fellout Hacking Puzzle`
3) Set the door state to **Locked**. When a player clicks the locked door, the puzzle appears. On success, the door unlocks automatically.

## Extending Puzzle Types

The door UI already includes a puzzle-type dropdown. Future puzzles can be added by extending the select options and handling their type in `scripts/puzzle.js` (the current implementation keys on `type === 'fellout'`).

## Development Notes

- Core puzzle logic lives in `scripts/puzzle.js` and uses `templates/fellout.html`.
- Word lists and defaults remain in `game.json` and are fetched at runtime.
- The legacy standalone prototype (`index.html`) is still present for reference but is not used by the Foundry module.
