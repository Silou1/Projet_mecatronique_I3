"use strict";

// ============ ÉTAT GLOBAL ============
const BOARD_SIZE = 6;
const SVG_VIEWBOX = 360;
const CELL = 50;         // taille d'une case en unités SVG
const MARGIN = 30;       // marge autour de la grille
let state = null;        // dernier state reçu
let consecutiveErrors = 0;
let pendingWallMode = null;  // synchro UI optimiste

const homeForm = {
  mode: "human_vs_ai",
  difficulty: "normal",
  speed: "normal",
  plateau_mode: false,
};

// ============ HELPERS GEO ============
function cellCenterXY(row, col) {
  // row 0 = haut, col 0 = gauche
  const x = MARGIN + col * CELL + CELL / 2;
  const y = MARGIN + row * CELL + CELL / 2;
  return { x, y };
}

function cellTopLeftXY(row, col) {
  return { x: MARGIN + col * CELL, y: MARGIN + row * CELL };
}

// ============ RENDER ============
function renderCells() {
  const layer = document.getElementById("cells");
  layer.innerHTML = "";
  for (let r = 0; r < BOARD_SIZE; r++) {
    for (let c = 0; c < BOARD_SIZE; c++) {
      const { x, y } = cellTopLeftXY(r, c);
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("class", "cell");
      rect.setAttribute("x", x);
      rect.setAttribute("y", y);
      rect.setAttribute("width", CELL);
      rect.setAttribute("height", CELL);
      rect.setAttribute("rx", "4");
      rect.dataset.row = r;
      rect.dataset.col = c;
      rect.addEventListener("click", () => handleCellClick(r, c));
      layer.appendChild(rect);
    }
  }
}

function renderIntersections() {
  // Les intersections sont les coins INTÉRIEURS de la grille,
  // soit (row, col) avec row ∈ [0, BOARD_SIZE-2] et col ∈ [0, BOARD_SIZE-2].
  // Un mur H couvre 2 cases en hauteur → row du mur = r, col = c
  // Un mur V couvre 2 cases en largeur → idem
  const layer = document.getElementById("intersections");
  layer.innerHTML = "";
  for (let r = 0; r < BOARD_SIZE - 1; r++) {
    for (let c = 0; c < BOARD_SIZE - 1; c++) {
      const { x, y } = cellTopLeftXY(r + 1, c);  // entre row r et r+1
      const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      dot.setAttribute("class", "intersection");
      // Position du marqueur selon orientation
      // On affiche un seul indicateur générique au coin (r+1, c+1)
      // → on stocke l'orientation au moment du clic
      dot.setAttribute("cx", x + CELL);
      dot.setAttribute("cy", y);
      dot.setAttribute("r", 7);
      dot.dataset.row = r;
      dot.dataset.col = c;
      dot.addEventListener("click", () => handleIntersectionClick(r, c));
      layer.appendChild(dot);
    }
  }
}

function renderWalls(walls) {
  const layer = document.getElementById("walls-layer");
  layer.innerHTML = "";
  for (const w of walls) {
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("class", "wall");
    if (w.orientation === "h") {
      // Mur horizontal entre row w.row et w.row+1, couvre cols w.col et w.col+1
      const { x, y } = cellTopLeftXY(w.row + 1, w.col);
      rect.setAttribute("x", x);
      rect.setAttribute("y", y - 3);
      rect.setAttribute("width", CELL * 2);
      rect.setAttribute("height", 6);
    } else {
      // Mur vertical entre col w.col et w.col+1, couvre rows w.row et w.row+1
      const { x, y } = cellTopLeftXY(w.row, w.col + 1);
      rect.setAttribute("x", x - 3);
      rect.setAttribute("y", y);
      rect.setAttribute("width", 6);
      rect.setAttribute("height", CELL * 2);
    }
    rect.setAttribute("rx", "2");
    layer.appendChild(rect);
  }
}

function renderPawns(players) {
  const { x: x1, y: y1 } = cellCenterXY(players.j1.position[0], players.j1.position[1]);
  const { x: x2, y: y2 } = cellCenterXY(players.j2.position[0], players.j2.position[1]);
  const p1 = document.getElementById("pawn-j1");
  const p2 = document.getElementById("pawn-j2");
  p1.setAttribute("cx", x1);
  p1.setAttribute("cy", y1);
  p2.setAttribute("cx", x2);
  p2.setAttribute("cy", y2);
}

function renderHeader(state) {
  document.getElementById("turn-count").textContent = state.turn_count;
  document.getElementById("j1-walls").textContent = state.players.j1.walls_remaining;
  document.getElementById("j2-walls").textContent = state.players.j2.walls_remaining;
  const ind = document.getElementById("turn-indicator");
  if (state.status !== "playing" && state.status !== "paused") {
    ind.textContent = "";
    ind.classList.remove("ai-thinking");
    return;
  }
  if (state.status === "paused") {
    ind.textContent = "Pause";
    ind.classList.remove("ai-thinking");
    return;
  }
  if (state.ai_thinking) {
    ind.textContent = "IA réfléchit";
    ind.classList.add("ai-thinking");
  } else if (state.mode === "ai_vs_ai") {
    ind.textContent = `Tour de ${state.current_player.toUpperCase()}`;
    ind.classList.remove("ai-thinking");
  } else {
    ind.textContent = state.current_player === "j1" ? "Ton tour" : "IA joue";
    ind.classList.remove("ai-thinking");
  }
}

function renderViews(state) {
  const home = document.getElementById("view-home");
  const game = document.getElementById("view-game");
  if (state.status === "waiting") {
    home.classList.remove("hidden");
    game.classList.add("hidden");
  } else {
    home.classList.add("hidden");
    game.classList.remove("hidden");
  }

  // Mode IA vs IA : affiche les contrôles de vitesse + pause
  const aiCtrls = document.getElementById("ai-vs-ai-controls");
  const moveActions = document.getElementById("game-actions");
  if (state.mode === "ai_vs_ai") {
    aiCtrls.classList.remove("hidden");
    moveActions.classList.add("hidden");
  } else {
    aiCtrls.classList.add("hidden");
    moveActions.classList.remove("hidden");
  }
}

function renderWallMode(state) {
  document.body.classList.toggle("wall-placement", !!state.wall_placement_mode);
  document.getElementById("btn-wall-h").classList.toggle("active", state.wall_placement_mode === "h");
  document.getElementById("btn-wall-v").classList.toggle("active", state.wall_placement_mode === "v");
}

function renderModal(state) {
  const modal = document.getElementById("modal-end");
  if (state.status === "finished" && state.winner) {
    document.getElementById("end-winner").textContent =
      `${state.winner.toUpperCase()} gagne en ${state.turn_count} tours !`;
    modal.classList.remove("hidden");
  } else {
    modal.classList.add("hidden");
  }
}

function renderPlateauToggle(state) {
  const toggle = document.getElementById("plateau-toggle");
  const hint = document.getElementById("plateau-hint");
  if (state.plateau.available) {
    toggle.disabled = false;
    hint.textContent = state.plateau.connected ? "Connecté" : "Disponible";
  } else {
    toggle.disabled = true;
    toggle.classList.remove("on");
    hint.textContent = "Plateau non détecté";
  }
}

function renderError(state) {
  if (state.last_error && state.last_error.code) {
    // Le serveur garde last_error jusqu'à new-game/quit ; on ne montre le toast
    // qu'une seule fois par code d'erreur grâce à une trace locale.
    if (state.last_error.code !== window._lastShownError) {
      showToast(state.last_error.message || state.last_error.code);
      window._lastShownError = state.last_error.code;
    }
  } else {
    window._lastShownError = null;
  }
}

function render(newState) {
  state = newState;
  document.getElementById("overlay-reconnect").classList.add("hidden");
  renderViews(state);
  if (state.status !== "waiting") {
    renderWalls(state.walls);
    renderPawns(state.players);
    renderHeader(state);
    renderWallMode(state);
  }
  renderModal(state);
  renderPlateauToggle(state);
  // Sync chip vitesse in-game avec le serveur
  const speedGroup = document.querySelector('[data-field="speed-ingame"]');
  if (speedGroup) {
    speedGroup.querySelectorAll(".chip").forEach(c => {
      c.classList.toggle("selected", c.dataset.value === state.speed);
    });
  }
  renderError(state);
}

// ============ ACTIONS UI ============
async function api(method, path, body) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const r = await fetch(path, opts);
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    const detail = data.detail || {};
    throw new Error(detail.message || detail.code || `HTTP ${r.status}`);
  }
  return r.json();
}

async function handleCellClick(row, col) {
  if (!state || state.status !== "playing") return;
  if (state.wall_placement_mode) return;  // pas en mode mur
  if (state.mode === "ai_vs_ai") return;
  if (state.current_player !== "j1") return;  // pas mon tour
  try {
    const next = await api("POST", "/api/move", { type: "deplacement", target: [row, col] });
    render(next);
  } catch (e) {
    showToast(`Coup impossible : ${e.message}`);
  }
}

async function handleIntersectionClick(row, col) {
  if (!state || !state.wall_placement_mode) return;
  if (state.current_player !== "j1") return;
  const orientation = state.wall_placement_mode;
  try {
    const next = await api("POST", "/api/move", {
      type: "mur",
      orientation,
      row,
      col,
    });
    render(next);
  } catch (e) {
    showToast(`Coup impossible : ${e.message}`);
  }
}

function showToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => t.classList.add("hidden"), 2500);
}

// ============ POLLING ============
async function poll() {
  try {
    const r = await fetch("/api/state");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    consecutiveErrors = 0;
    render(data);
  } catch (e) {
    consecutiveErrors++;
    if (consecutiveErrors >= 3) {
      document.getElementById("overlay-reconnect").classList.remove("hidden");
    }
  } finally {
    setTimeout(poll, 500);
  }
}

// ============ INIT ============
function initHandlers() {
  // Chip groups (accueil)
  document.querySelectorAll(".chip-group").forEach(group => {
    const field = group.dataset.field;
    group.querySelectorAll(".chip").forEach(chip => {
      chip.addEventListener("click", () => {
        group.querySelectorAll(".chip").forEach(c => c.classList.remove("selected"));
        chip.classList.add("selected");
        const value = chip.dataset.value;
        if (field === "speed-ingame") {
          api("POST", "/api/speed", { speed: value }).then(render).catch(e => showToast(e.message));
        } else {
          homeForm[field] = value;
          if (field === "mode") {
            document.getElementById("speed-block").classList.toggle("hidden", value !== "ai_vs_ai");
          }
        }
      });
    });
  });

  // Toggle plateau
  document.getElementById("plateau-toggle").addEventListener("click", e => {
    if (e.currentTarget.disabled) return;
    e.currentTarget.classList.toggle("on");
    homeForm.plateau_mode = e.currentTarget.classList.contains("on");
  });

  // Bouton start
  document.getElementById("btn-start").addEventListener("click", async () => {
    try {
      const next = await api("POST", "/api/new-game", homeForm);
      render(next);
    } catch (e) {
      showToast(e.message);
    }
  });

  // Boutons murs
  document.getElementById("btn-wall-h").addEventListener("click", async () => {
    const newMode = state.wall_placement_mode === "h" ? null : "h";
    await api("POST", "/api/wall-mode", { orientation: newMode }).then(render);
  });
  document.getElementById("btn-wall-v").addEventListener("click", async () => {
    const newMode = state.wall_placement_mode === "v" ? null : "v";
    await api("POST", "/api/wall-mode", { orientation: newMode }).then(render);
  });

  // Bouton retour accueil
  const goHome = async () => {
    if (state && state.status === "playing" && !confirm("Quitter la partie en cours ?")) return;
    const next = await api("POST", "/api/quit");
    render(next);
  };
  document.getElementById("btn-home").addEventListener("click", goHome);

  // Bouton pause/resume
  document.getElementById("btn-pause").addEventListener("click", async () => {
    const path = state.status === "paused" ? "/api/resume" : "/api/pause";
    const next = await api("POST", path);
    render(next);
    document.getElementById("btn-pause").textContent =
      next.status === "paused" ? "Reprendre" : "Pause";
  });

  // Modal fin de partie
  document.getElementById("btn-replay").addEventListener("click", async () => {
    const next = await api("POST", "/api/new-game", {
      mode: state.mode,
      difficulty: state.difficulty,
      plateau_mode: state.plateau.mode_active,
    });
    render(next);
  });
  document.getElementById("btn-home-from-end").addEventListener("click", goHome);
}

document.addEventListener("DOMContentLoaded", () => {
  renderCells();
  renderIntersections();
  initHandlers();
  poll();
});
