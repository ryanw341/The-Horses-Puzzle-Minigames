const MODULE_ID = "the-horses-hacking-puzzle";
const MODULE_TITLE = "The Horse's Fellout Hacking Puzzle";

Hooks.once("init", () => {
  game.settings.register(MODULE_ID, "wordLength", {
    name: "Word Length",
    hint: "Length of candidate passwords.",
    scope: "world",
    config: true,
    type: Number,
    default: 6,
    range: { min: 3, max: 12, step: 1 }
  });
  game.settings.register(MODULE_ID, "attempts", {
    name: "Attempts",
    hint: "Attempts before lockout.",
    scope: "world",
    config: true,
    type: Number,
    default: 4,
    range: { min: 1, max: 10, step: 1 }
  });
  game.settings.register(MODULE_ID, "timerSeconds", {
    name: "Timer (seconds)",
    hint: "Countdown before lockout. Set 0 to disable timer.",
    scope: "world",
    config: true,
    type: Number,
    default: 120,
    range: { min: 0, max: 900, step: 5 }
  });
  game.settings.register(MODULE_ID, "maxResets", {
    name: "Max Resets",
    hint: "Limit resets after the puzzle is started. Blank for unlimited.",
    scope: "world",
    config: true,
    type: Number,
    default: null
  });
  game.settings.register(MODULE_ID, "terminalColor", {
    name: "Terminal Color",
    hint: "Primary terminal color.",
    scope: "world",
    config: true,
    type: String,
    default: "#ff1717"
  });
});

const WORD_START = "\u0007";
const WORD_END = "\u0008";

function escapeText(str) {
  return str.replace(/[&<>]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;"}[c]));
}

function likeness(a, b) {
  let count = 0;
  for (let i = 0; i < a.length; i++) if (a[i] === b[i]) count++;
  return count;
}

function pickWords(dict, count, length) {
  const filtered = dict.filter(w => w.length === length);
  const arr = [...filtered];
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr.slice(0, Math.min(count, arr.length));
}

function randChar() {
  const chars = '!@#$%^&*+-/\\|;:\'".,?';
  return chars[Math.floor(Math.random() * chars.length)];
}

function generateTerminalColumns(words, width = 12, rows = 17, wordLength = 5) {
  const totalLines = rows;
  const makeColumn = () => {
    const lines = [];
    for (let r = 0; r < totalLines; r++) {
      let line = '';
      for (let c = 0; c < width; c++) line += randChar();
      lines.push(line);
    }
    return lines;
  };
  const A = makeColumn();
  const B = makeColumn();
  const usedRangesA = new Map();
  const usedRangesB = new Map();
  const embed = (columnLines, word, usedRanges) => {
    for (let attempt = 0; attempt < 20; attempt++) {
      const lineIdx = Math.floor(Math.random() * columnLines.length);
      const startIdx = Math.floor(Math.random() * (width - word.length));
      const endIdx = startIdx + word.length - 1;
      const ranges = usedRanges.get(lineIdx) || [];
      const overlaps = ranges.some(([s, e]) => !(endIdx < s - 1 || startIdx > e + 1));
      if (overlaps) continue;
      const line = columnLines[lineIdx];
      const withWord = line.slice(0, startIdx) + WORD_START + word + WORD_END + line.slice(startIdx + word.length);
      columnLines[lineIdx] = withWord;
      ranges.push([startIdx, endIdx]);
      usedRanges.set(lineIdx, ranges);
      return true;
    }
    return false;
  };
  const half = Math.ceil(words.length / 2);
  const leftWords = words.slice(0, half);
  const rightWords = words.slice(half);
  leftWords.forEach(w => embed(A, w, usedRangesA));
  rightWords.forEach(w => embed(B, w, usedRangesB));
  return { A, B };
}

async function loadConfig() {
  const defaults = {
    wordLength: 6,
    attempts: 4,
    timerSeconds: 120,
    maxResets: null,
    terminalColor: "#ff1717",
    dictionary: [],
    wordList: [],
    allowBrackets: true,
    bracketPairs: [
      { open: "(", close: ")" },
      { open: "[", close: "]" },
      { open: "{", close: "}" },
      { open: "<", close: ">" }
    ]
  };
  let cfg = defaults;
  try {
    const res = await fetch(`modules/${MODULE_ID}/game.json`);
    if (res.ok) {
      cfg = { ...defaults, ...(await res.json()) };
    }
  } catch (err) {
    console.warn(`${MODULE_ID} | falling back to defaults`, err);
  }
  cfg.wordLength = game.settings.get(MODULE_ID, "wordLength");
  cfg.attempts = game.settings.get(MODULE_ID, "attempts");
  cfg.timerSeconds = game.settings.get(MODULE_ID, "timerSeconds");
  cfg.maxResets = game.settings.get(MODULE_ID, "maxResets");
  cfg.terminalColor = game.settings.get(MODULE_ID, "terminalColor") || cfg.terminalColor;
  return cfg;
}

class HorseFelloutApp extends Application {
  static get defaultOptions() {
    return {
      ...super.defaultOptions,
      id: `${MODULE_ID}-app`,
      title: MODULE_TITLE,
      template: `modules/${MODULE_ID}/templates/fellout.html`,
      width: 960,
      height: "auto",
      resizable: true
    };
  }

  constructor(opts = {}) {
    super(opts);
    this.wall = opts.wall ?? null;
    this.onSuccess = opts.onSuccess ?? (() => {});
    this.state = null;
    this._interval = null;
  }

  async getData() {
    if (!this.state) {
      const cfg = await loadConfig();
      await this._resetState(cfg, false);
    }
    return {};
  }

  async close(options) {
    if (this._interval) clearInterval(this._interval);
    return super.close(options);
  }

  activateListeners(html) {
    super.activateListeners(html);
    this.html = html;
    html.find('[data-action="start"]').on('click', () => this._start());
    html.find('[data-action="reset"]').on('click', () => this._reset());
    html.on('click', '[data-word]', ev => this._guess(ev));
    this._applyTheme();
    this._renderState();
    if (!this._interval) {
      this._interval = setInterval(() => {
        if (this.state?.started && !this.state?.over && this.state.config.timerSeconds > 0) this._renderState();
      }, 1000);
    }
  }

  _applyTheme() {
    const color = this.state.config.terminalColor;
    const root = document.documentElement;
    root.style.setProperty('--terminal-color', color);
    root.style.setProperty('--border-color', color);
    const rgb = parseInt(color.slice(1), 16);
    const r = Math.min(255, ((rgb >> 16) & 0xff) + 102);
    const g = Math.min(255, ((rgb >> 8) & 0xff) + 102);
    const b = Math.min(255, (rgb & 0xff) + 102);
    const lighter = `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
    root.style.setProperty('--addr-color', lighter);
  }

  async _resetState(cfg, preserveTimer, keepStarted = false) {
    const src = cfg.wordList?.length ? cfg.wordList : cfg.dictionary;
    const words = pickWords(src, 12, cfg.wordLength);
    const secret = words[Math.floor(Math.random() * words.length)];
    const columns = generateTerminalColumns(words, 12, 17, cfg.wordLength);
    const now = Date.now();
    const timerEnd = cfg.timerSeconds && cfg.timerSeconds > 0 && preserveTimer && this.state?.timerEnd ? this.state.timerEnd : (cfg.timerSeconds ? now + cfg.timerSeconds * 1000 : 0);
    this.state = {
      config: cfg,
      words,
      secret,
      remaining: cfg.attempts,
      resetsUsed: preserveTimer && this.state ? this.state.resetsUsed : 0,
      log: [],
      disabled: new Set(),
      over: false,
      locked: false,
      started: keepStarted,
      timerEnd,
      columns
    };
  }

  async _start() {
    if (this.state.started) return;
    this.state.started = true;
    if (this.state.config.timerSeconds) this.state.timerEnd = Date.now() + this.state.config.timerSeconds * 1000;
    this._renderState();
  }

  async _reset() {
    if (this.state.locked) {
      this.state.log.push('>TERMINAL LOCKED. GM reset required.');
      return this._renderState();
    }
    if (this.state.config.maxResets !== null && this.state.config.maxResets !== undefined && this.state.started) {
      if (this.state.resetsUsed >= this.state.config.maxResets) {
        this.state.log.push('>NO RESETS REMAINING');
        return this._renderState();
      }
      this.state.resetsUsed++;
    }
    const cfg = this.state.config;
    await this._resetState(cfg, true, true);
    this._renderState(true);
  }

  async _guess(event) {
    if (!this.state || this.state.over || !this.state.started) return;
    const word = event.currentTarget.dataset.word;
    if (this.state.disabled.has(word)) return;
    this.state.disabled.add(word);
    const like = likeness(word, this.state.secret);
    this.state.log.push(`>${word} - LIKENESS ${like}/${this.state.secret.length}`);
    if (word === this.state.secret) {
      this.state.over = true;
      this.state.locked = false;
      this.state.log.push('>ACCESS GRANTED');
      this._unlockDoor();
      return this._renderState();
    }
    this.state.remaining = Math.max(0, this.state.remaining - 1);
    if (this.state.remaining === 0) {
      this.state.over = true;
      this.state.locked = true;
      this.state.log.push('>LOCKOUT');
    }
    this._renderState();
  }

  async _unlockDoor() {
    if (this.onSuccess) {
      try { await this.onSuccess(); } catch (err) { console.error(`${MODULE_ID} unlock`, err); }
    }
  }

  _renderState(isReset = false) {
    if (!this.html) return;
    const { columns, remaining, config, log, over, locked, secret, timerEnd, started, resetsUsed } = this.state;
    const colA = this.html.find('[data-col="A"]')[0];
    const colB = this.html.find('[data-col="B"]')[0];
    colA.innerHTML = '';
    colB.innerHTML = '';
    const addrBase = 0x9a30;
    const makeLineHTML = (addr, text) => {
      const div = document.createElement('div');
      div.classList.add('line');
      const addrSpan = document.createElement('span');
      addrSpan.classList.add('addr');
      addrSpan.textContent = `0x${addr.toString(16).toUpperCase()}`;
      const dataSpan = document.createElement('span');
      dataSpan.classList.add('data');
      const safe = escapeText(text).replace(new RegExp(`${WORD_START}(.*?)${WORD_END}`, 'g'), '<span data-word="$1" class="word">$1</span>');
      dataSpan.innerHTML = safe;
      div.appendChild(addrSpan);
      div.appendChild(dataSpan);
      return div;
    };
    const rows = Math.min(columns.A.length, columns.B.length);
    for (let r = 0; r < rows; r++) {
      const addrA = addrBase + r * 0x20;
      const addrB = addrBase + r * 0x20 + 0x10;
      colA.appendChild(makeLineHTML(addrA, columns.A[r]));
      colB.appendChild(makeLineHTML(addrB, columns.B[r]));
    }
    const attemptsEl = this.html.find('[data-field="attempts"]')[0];
    let attemptsText = `ATTEMPTS REMAINING: ${'●'.repeat(remaining)}${'○'.repeat(Math.max(0, config.attempts - remaining))}`;
    if (config.maxResets !== null && config.maxResets !== undefined) {
      const resetsLeft = config.maxResets - (resetsUsed || 0);
      attemptsText += `  |  RESETS: ${resetsLeft}/${config.maxResets}`;
    }
    attemptsEl.textContent = attemptsText;

    const timerEl = this.html.find('[data-field="timer"]')[0];
    if (started && config.timerSeconds && config.timerSeconds > 0) {
      const left = Math.max(0, Math.ceil((timerEnd - Date.now()) / 1000));
      timerEl.textContent = ` | TIMER: ${left}s`;
      if (!over && left === 0) {
        this.state.log.push('>LOCKOUT (TIMEOUT)');
        this.state.over = true;
        this.state.locked = true;
      }
    } else {
      timerEl.textContent = '';
    }

    const logEl = this.html.find('[data-field="log"]')[0];
    const entries = ['Welcome to HORSECO Industries (TM) Termlink', 'Password Required', ''];
    logEl.textContent = entries.concat(log).join('\n');

    const leftPanel = this.html.find('#horse-left')[0];
    leftPanel.querySelectorAll('.overlay').forEach(o => o.remove());
    if (over) {
      const overlay = document.createElement('div');
      overlay.classList.add('overlay');
      overlay.textContent = locked ? 'TERMINAL LOCKED' : 'ACCESS GRANTED';
      leftPanel.appendChild(overlay);
      const terminal = this.html.find('.terminal')[0];
      terminal.classList.remove('animate-flash', 'animate-success');
      terminal.classList.add(locked ? 'animate-flash' : 'animate-success');
      setTimeout(() => terminal.classList.remove('animate-flash', 'animate-success'), 1500);
    } else if (isReset) {
      const terminal = this.html.find('.terminal')[0];
      terminal.classList.add('animate-glitch');
      setTimeout(() => terminal.classList.remove('animate-glitch'), 500);
    }
  }
}

function installDoorConfigHook() {
  Hooks.on('renderWallConfig', (app, html) => {
    const wall = app.document ?? app.object;
    if (!wall || wall.door === CONST.WALL_DOOR_TYPES.NONE) return;
    const flags = wall.getFlag(MODULE_ID, 'config') || {};
    const enabled = flags.enabled ?? false;
    const type = flags.type ?? 'fellout';
    const form = $(
      `<fieldset>
        <legend>Horse's Puzzles</legend>
        <div class="form-group">
          <label>Enable Puzzle Lock</label>
          <input type="checkbox" name="flags.${MODULE_ID}.config.enabled" ${enabled ? 'checked' : ''}/>
        </div>
        <div class="form-group">
          <label>Puzzle Type</label>
          <select name="flags.${MODULE_ID}.config.type">
            <option value="fellout" ${type === 'fellout' ? 'selected' : ''}>Fellout Hacking Puzzle</option>
          </select>
        </div>
      </fieldset>`
    );
    const doorTab = html.find('.tab[data-tab="door"]');
    if (doorTab.length) doorTab.append(form); else html.append(form);
  });
}

function installDoorInteractionHook() {
  if (DoorControl.prototype._horsePuzzleWrapped) return;
  const orig = DoorControl.prototype._onMouseDown;
  DoorControl.prototype._onMouseDown = async function (event) {
    if (!canvas?.ready) return orig.call(this, event);
    const wall = this.wall?.document ?? this.wall;
    if (!wall) return orig.call(this, event);
    const flags = wall.getFlag(MODULE_ID, 'config');
    if (!flags?.enabled || (flags?.type ?? 'fellout') !== 'fellout') return orig.call(this, event);
    if (wall.ds !== CONST.WALL_DOOR_STATES.LOCKED) return orig.call(this, event);
    if (event?.data?.button !== 0) return orig.call(this, event);
    event.stopPropagation();
    event.preventDefault();
    const app = new HorseFelloutApp({
      wall,
      onSuccess: async () => {
        await wall.update({ ds: CONST.WALL_DOOR_STATES.CLOSED });
        ui.notifications?.info('Door unlocked.');
      }
    });
    app.render(true);
    return false;
  };
  DoorControl.prototype._horsePuzzleWrapped = true;
}

Hooks.once('ready', () => {
  installDoorConfigHook();
  installDoorInteractionHook();
});
