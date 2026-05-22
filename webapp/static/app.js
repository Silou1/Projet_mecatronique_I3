"use strict";

// ============ ÉTAT GLOBAL ============
const BOARD_SIZE = 6;
const SVG_VIEWBOX = 360;
const CELL = 50;         // taille d'une case en unités SVG
const MARGIN = 30;       // marge autour de la grille
let state = null;        // dernier state reçu
let consecutiveErrors = 0;
let pendingWallMode = null;  // synchro UI optimiste
const HAS_HOVER = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

const homeForm = {
  mode: "human_vs_ai",
  difficulty: "normal",
  speed: "normal",
};

// ============ HELPERS ÉTAT ============
function isHumanTurn(state) {
  if (!state || state.status !== "playing") return false;
  if (state.plateau && state.plateau.busy) return false;  // plateau physique en cours
  return !state.players[state.current_player].is_ai;
}

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
      dot.setAttribute("r", 9);
      dot.dataset.row = r;
      dot.dataset.col = c;
      dot.addEventListener("click", () => handleIntersectionClick(r, c));
      if (HAS_HOVER) {
        dot.addEventListener("mouseenter", () => {
          if (!state || !state.wall_placement_mode) return;
          if (!isHumanTurn(state)) return;
          dot.classList.add("hovered");
          addGhost(state.wall_placement_mode, r, c);
        });
        dot.addEventListener("mouseleave", () => {
          dot.classList.remove("hovered");
          clearGhost();
        });
      }
      layer.appendChild(dot);
    }
  }
}

function renderWalls(walls) {
  const layer = document.getElementById("walls-layer");
  const oldKeys = new Set([...layer.children].map(c => c.dataset.key));
  layer.innerHTML = "";
  for (const w of walls) {
    const key = `${w.orientation}-${w.row}-${w.col}`;
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("class", "wall" + (oldKeys.has(key) ? "" : " appearing"));
    rect.dataset.key = key;
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

function addGhost(orientation, row, col) {
  const layer = document.getElementById("ghost");
  const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  rect.setAttribute("class", "ghost-wall");
  if (orientation === "h") {
    const { x, y } = cellTopLeftXY(row + 1, col);
    rect.setAttribute("x", x);
    rect.setAttribute("y", y - 3);
    rect.setAttribute("width", CELL * 2);
    rect.setAttribute("height", 6);
  } else {
    const { x, y } = cellTopLeftXY(row, col + 1);
    rect.setAttribute("x", x - 3);
    rect.setAttribute("y", y);
    rect.setAttribute("width", 6);
    rect.setAttribute("height", CELL * 2);
  }
  rect.setAttribute("rx", "2");
  layer.replaceChildren(rect);
}

function clearGhost() {
  document.getElementById("ghost").replaceChildren();
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
  // Reset des classes a chaque rendu
  ind.classList.remove("ai-thinking", "turn-j1", "turn-j2");
  if (state.status !== "playing" && state.status !== "paused") {
    ind.textContent = "";
    return;
  }
  if (state.status === "paused") {
    ind.textContent = "Pause";
    return;
  }
  if (state.ai_thinking) {
    ind.textContent = "IA réfléchit";
    ind.classList.add("ai-thinking");
    return;
  }
  // Plateau physique en cours (mur en train de monter, chariot en train de bouger)
  if (state.plateau && state.plateau.busy) {
    ind.textContent = "Plateau en cours…";
    ind.classList.add("ai-thinking");  // réutilise le style "en attente"
    return;
  }
  // Couleur selon le joueur courant
  ind.classList.add(state.current_player === "j1" ? "turn-j1" : "turn-j2");
  if (state.mode === "ai_vs_ai") {
    ind.textContent = `Tour de ${state.current_player.toUpperCase()}`;
  } else if (state.mode === "human_vs_human") {
    ind.textContent = `AU TOUR DE ${state.current_player.toUpperCase()}`;
  } else /* human_vs_ai */ {
    ind.textContent = state.current_player === "j1" ? "TON TOUR" : "IA joue";
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

  // Note : le bouton "Commencer la partie" reste toujours actif sur l'accueil,
  // meme si un HOME du quit precedent est en cours (state.plateau.busy=true).
  // Le new_game gere le cas en sautant son propre HOME ; la transition est
  // fluide sur l'ecran de jeu via le busy flag.
}

let _prevWallMode = null;

function renderWallMode(state) {
  document.body.classList.toggle("wall-placement", !!state.wall_placement_mode);
  document.getElementById("btn-wall-h").classList.toggle("active", state.wall_placement_mode === "h");
  document.getElementById("btn-wall-v").classList.toggle("active", state.wall_placement_mode === "v");
  if (_prevWallMode !== state.wall_placement_mode) {
    clearGhost();
    _prevWallMode = state.wall_placement_mode;
  }
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

// ============ TRANSITION HvH ============
let _lastTransitionTurn = -1;

function maybeShowTransition(state) {
  if (state.mode !== "human_vs_human") return;
  if (state.status === "waiting") {
    _lastTransitionTurn = -1;  // reset au retour a l'accueil
    return;
  }
  if (state.status !== "playing") return;
  if (state.turn_count === _lastTransitionTurn) return;
  _lastTransitionTurn = state.turn_count;
  const delayMs = state.turn_count === 0 ? 0 : 500;
  document.getElementById("transition-text").textContent =
    `À toi ${state.current_player.toUpperCase()} !`;
  setTimeout(() => {
    // Re-verifier au moment d'afficher : l'utilisateur a pu quitter entre temps
    if (state.status === "playing") {
      document.getElementById("modal-transition").classList.remove("hidden");
    }
  }, delayMs);
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
  maybeShowTransition(state);
  // Rotation 180 du plateau au tour de J2 en HvH
  const board = document.getElementById("board");
  const flip = state.mode === "human_vs_human" && state.current_player === "j2" && state.status === "playing";
  board.classList.toggle("flipped", flip);
  // Halo pulse sur le pion du joueur courant
  const isPlaying = state.status === "playing";
  document.getElementById("pawn-j1").classList.toggle(
    "current", isPlaying && state.current_player === "j1"
  );
  document.getElementById("pawn-j2").classList.toggle(
    "current", isPlaying && state.current_player === "j2"
  );
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
  if (!isHumanTurn(state)) return;
  if (state.wall_placement_mode) return;  // pas en mode mur
  try {
    const next = await api("POST", "/api/move", { type: "deplacement", target: [row, col] });
    render(next);
  } catch (e) {
    showToast(`Coup impossible : ${e.message}`);
  }
}

async function handleIntersectionClick(row, col) {
  if (!state || !state.wall_placement_mode) return;
  if (!isHumanTurn(state)) return;
  const orientation = state.wall_placement_mode;
  try {
    const next = await api("POST", "/api/move", {
      type: "mur",
      orientation,
      row,
      col,
    });
    clearGhost();
    render(next);
  } catch (e) {
    clearGhost();
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
            document.getElementById("difficulty-block").classList.toggle("hidden", value === "human_vs_human");
          }
        }
      });
    });
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
    });
    render(next);
  });
  document.getElementById("btn-home-from-end").addEventListener("click", goHome);

  // Modal de transition entre tours (HvH)
  document.getElementById("btn-transition-ok").addEventListener("click", () => {
    document.getElementById("modal-transition").classList.add("hidden");
  });
}

// ============ STATUT PLATEAU ============
let statusPollTimer = null;

async function fetchStatus() {
  try {
    const resp = await fetch("/api/status");
    if (!resp.ok) return;
    const data = await resp.json();
    renderStatus(data);
  } catch (e) {
    // erreur reseau silencieuse, on retentera
  }
}

function renderStatus(s) {
  // Indicateur Client
  const clientDot = document.getElementById("status-client-dot");
  const clientText = document.getElementById("status-client-text");
  if (clientDot && clientText) {
    clientDot.className = "status-indicator dot-green";
    clientText.textContent = `Connecté · polling actif (${s.client.polling_interval_ms} ms)`;
  }

  // Indicateur Transport
  const tDot = document.getElementById("status-transport-dot");
  const tText = document.getElementById("status-transport-text");
  const tDetail = document.getElementById("status-transport-detail");
  if (tDot && tText && tDetail) {
    if (!s.transport.alive) {
      tDot.className = "status-indicator dot-red";
      tText.textContent = "Déconnecté";
      tDetail.textContent = s.transport.startup_error
        ? `Erreur : ${s.transport.startup_error}`
        : "Le transport ne répond plus.";
    } else if (s.transport.last_pong_age_seconds !== null && s.transport.last_pong_age_seconds >= 10) {
      tDot.className = "status-indicator dot-orange";
      tText.textContent = `Connecté · ${s.transport.description} (heartbeat en retard)`;
      tDetail.textContent = `Dernier PONG : il y a ${Math.round(s.transport.last_pong_age_seconds)} s`;
    } else {
      tDot.className = "status-indicator dot-green";
      tText.textContent = `Connecté · ${s.transport.description}`;
      if (s.transport.last_pong_age_seconds !== null) {
        const age = Math.round(s.transport.last_pong_age_seconds);
        const lat = s.transport.latency_avg_ms !== null
          ? `${Math.round(s.transport.latency_avg_ms)} ms` : "—";
        tDetail.textContent = `Dernier PONG : il y a ${age} s · Latence moyenne : ${lat}`;
      } else {
        tDetail.textContent = "Aucun PONG reçu pour l'instant.";
      }
    }
  }

  // Indicateur Plateau
  const pDot = document.getElementById("status-plateau-dot");
  const pText = document.getElementById("status-plateau-text");
  if (pDot && pText) {
    if (s.plateau.ready) {
      pDot.className = "status-indicator dot-green";
      pText.textContent = s.plateau.homed ? "Prêt · homing effectué" : "Prêt";
    } else {
      pDot.className = "status-indicator dot-grey";
      pText.textContent = "Indisponible";
    }
  }

  // Banniere degradee
  const banner = document.getElementById("banner-degraded");
  if (banner) {
    if (!s.transport.alive || s.transport.startup_error) {
      banner.classList.remove("hidden");
    } else {
      banner.classList.add("hidden");
    }
  }
}

function startStatusPolling() {
  if (statusPollTimer !== null) return;
  fetchStatus();
  statusPollTimer = setInterval(fetchStatus, 2000);
}

async function switchTransport(kind) {
  try {
    const resp = await fetch("/api/transport/switch", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({kind}),
    });
    const data = await resp.json();
    if (!data.success) {
      alert(`Bascule ${kind} échouée : ${data.error}`);
    }
    fetchStatus();
  } catch (e) {
    alert(`Erreur réseau lors de la bascule : ${e}`);
  }
}

function initStatusUI() {
  // Menu trois points (toggle)
  const btnMenu = document.getElementById("btn-menu");
  const menuDropdown = document.getElementById("menu-dropdown");
  if (btnMenu && menuDropdown) {
    btnMenu.addEventListener("click", (e) => {
      e.stopPropagation();
      menuDropdown.classList.toggle("hidden");
    });
    document.addEventListener("click", () => menuDropdown.classList.add("hidden"));
  }

  // Ouvrir panneau Statut
  const btnMenuStatus = document.getElementById("btn-menu-status");
  if (btnMenuStatus) {
    btnMenuStatus.addEventListener("click", () => {
      menuDropdown && menuDropdown.classList.add("hidden");
      document.getElementById("modal-status").classList.remove("hidden");
    });
  }

  // Fermer panneau Statut
  const btnClose = document.getElementById("btn-status-close");
  if (btnClose) {
    btnClose.addEventListener("click", () => {
      document.getElementById("modal-status").classList.add("hidden");
    });
  }

  // Boutons banniere
  const btnRetrySerial = document.getElementById("btn-retry-serial");
  const btnRetryWifi = document.getElementById("btn-retry-wifi");
  if (btnRetrySerial) btnRetrySerial.addEventListener("click", () => switchTransport("serial"));
  if (btnRetryWifi) btnRetryWifi.addEventListener("click", () => switchTransport("wifi"));
}

document.addEventListener("DOMContentLoaded", () => {
  renderCells();
  renderIntersections();
  initHandlers();
  initStatusUI();
  startStatusPolling();
  poll();
});
