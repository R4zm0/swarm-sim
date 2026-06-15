# scenario_editor.py
"""
Éditeur de scénarios pour swarm-sim.

À placer à la RACINE du projet (à côté de main.py) et lancer depuis là :

    python scenario_editor.py                # nouveau scénario
    python scenario_editor.py mon_scenario   # édite data/scenarios/mon_scenario.json

Produit un JSON directement chargeable par core/scenario_loader.load.

Réutilise le code existant :
    - core.world.World            → dimensions du monde (W, H)
    - core.config_loader          → types de drones disponibles (depuis drones.json)
    - environment.zone.PatrolZone → prévisualisation du placement réel des drones

Contrôles
---------
    Modes (clic gauche dans le canvas) :
        1  Polygone   : ajoute un sommet ; Retour arrière = supprime le dernier
        2  Ennemis    : ajoute un ennemi ; clic droit = supprime le plus proche
        3  Spawn      : place le point d'apparition des drones
        4  Pan        : déplace la vue (sinon : clic molette pour pan partout)

    Vue :
        molette       : zoom
        clic molette  : pan
        R             : recentrer

    Fond de carte :
        glisser-déposer un PNG/JPG sur la fenêtre → copié dans data/maps/ + sélectionné
        B             : faire défiler les images déjà présentes dans data/maps/

    Panneau de droite (clic) :
        nom / description : clic pour éditer au clavier
        drones            : boutons +/- par type
        coverage          : boutons +/- (n_samples, decay, threshold)

    Ctrl+S : sauvegarder dans data/scenarios/<nom>.json
"""

import sys
import os
import json
import shutil
from pathlib import Path

# ── Permet les imports du projet quel que soit le cwd ──────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
import numpy as np

from core.world import World
from core.config_loader import load_drone_configs
from environment.zone import PatrolZone

# ── Constantes monde (réutilisées du World) ────────────────────────────────────
WORLD_W, WORLD_H = World.W, World.H

SCENARIOS_DIR = Path("data/scenarios")
MAPS_DIR      = Path("data/maps")

# ── Palette (cohérente avec mission_select / renderer) ─────────────────────────
BG            = (10, 12, 18)
WORLD_BG      = (22, 26, 34)
WORLD_BORDER  = (60, 80, 110)
PANEL_BG      = (14, 17, 25)
PANEL_BORDER  = (40, 50, 68)
TEXT          = (200, 208, 222)
TEXT_DIM      = (110, 120, 140)
TEXT_BRIGHT   = (225, 232, 245)
ACCENT        = (80, 150, 235)
ACCENT_DIM    = (40, 75, 125)
BTN_BG        = (32, 44, 66)
BTN_HOVER     = (48, 72, 110)
BTN_ACTIVE    = (55, 110, 80)
FIELD_BG      = (24, 28, 38)
FIELD_FOCUS   = (40, 55, 80)
OK_GREEN      = (90, 200, 120)
ERR_RED       = (225, 90, 90)

POLY_LINE     = (70, 190, 110)
POLY_VERT     = (255, 220, 90)
ENEMY_COL     = (225, 80, 80)
SPAWN_COL     = (90, 210, 120)
WP_COL        = (90, 160, 255)
DROP_HINT     = (120, 135, 160)

PANEL_W = 300
PAD     = 12
ROW_H   = 30


# ── Éditeur ────────────────────────────────────────────────────────────────────

class Editor:
    MODES = ["polygone", "ennemis", "spawn", "pan"]

    def __init__(self, load_name: str | None = None):
        self.vertices: list[list[float]] = []     # sommets du polygone (monde)
        self.enemies:  list[list[float]] = []     # positions ennemis (monde)
        self.spawn:    list[float] | None = None  # point d'apparition
        self.name        = "nouveau"
        self.description  = ""
        self.background   = None                   # nom de fichier dans data/maps/

        # coverage (valeurs par défaut alignées sur CoverageMap.from_scenario)
        self.cov_n      = 500
        self.cov_decay  = 0.0
        self.cov_thresh = 0.5

        # Types de drones disponibles → {type_key: count}
        self.drone_types = list(load_drone_configs().keys())
        self.drone_counts = {t: 0 for t in self.drone_types}
        if self.drone_types:
            self.drone_counts[self.drone_types[0]] = 4   # défaut

        self.mode  = "polygone"
        self.focus = None          # champ texte actif : "name" | "description" | None
        self.status = ("", 0)      # (message, timestamp, ok)

        # backgrounds disponibles
        self.bg_files = self._scan_maps()

        if load_name:
            self._load(load_name)

    # ── Scan des fonds de carte ───────────────────────────────────────────────
    def _scan_maps(self) -> list[str]:
        MAPS_DIR.mkdir(parents=True, exist_ok=True)
        out = []
        for ext in ("*.png", "*.jpg", "*.jpeg"):
            out += [p.name for p in sorted(MAPS_DIR.glob(ext))]
        return out

    def cycle_background(self):
        if not self.bg_files:
            self.background = None
            return
        # cycle : None → fichier0 → fichier1 → ... → None
        opts = [None] + self.bg_files
        cur = opts.index(self.background) if self.background in opts else 0
        self.background = opts[(cur + 1) % len(opts)]

    def import_background(self, src_path: str) -> tuple[bool, str]:
        """Importe un PNG/JPG lâché sur la fenêtre : copie dans data/maps/ + sélectionne."""
        src = Path(src_path)
        if src.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            return False, f"format non supporté : {src.suffix}"
        if not src.exists():
            return False, "fichier introuvable"
        MAPS_DIR.mkdir(parents=True, exist_ok=True)
        dst = MAPS_DIR / src.name
        try:
            if src.resolve() != dst.resolve():   # évite de se copier sur soi-même
                shutil.copy2(src, dst)
        except Exception as ex:
            return False, f"copie échouée : {ex}"
        self.bg_files = self._scan_maps()         # rafraîchit la liste
        self.background = src.name
        return True, f"fond importé → data/maps/{src.name}"

    # ── Comptes ───────────────────────────────────────────────────────────────
    @property
    def total_drones(self) -> int:
        return sum(self.drone_counts.values())

    # ── Sauvegarde / chargement ───────────────────────────────────────────────
    def to_dict(self) -> dict:
        drones = []
        for t, c in self.drone_counts.items():
            drones += [{"type": t, "team": 0} for _ in range(c)]
        spawn = self.spawn if self.spawn is not None else (
            self.vertices[0] if self.vertices else [WORLD_W / 2, WORLD_H / 2]
        )
        return {
            "name":        self.name.strip() or "scenario",
            "description": self.description.strip(),
            "background":  self.background,
            "spawn":       [round(spawn[0], 1), round(spawn[1], 1)],
            "zone":        {"vertices": [[round(x, 1), round(y, 1)] for x, y in self.vertices]},
            "coverage":    {"n_samples": self.cov_n, "decay": self.cov_decay, "threshold": self.cov_thresh},
            "drones":      drones,
            "enemies":     [{"position": [round(x, 1), round(y, 1)]} for x, y in self.enemies],
        }

    def save(self) -> tuple[bool, str]:
        if len(self.vertices) < 3:
            return False, "polygone : 3 sommets minimum"
        if self.total_drones == 0:
            return False, "aucun drone défini"
        if not self.name.strip():
            return False, "nom vide"
        SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
        safe = self.name.strip().replace("/", "_").replace("\\", "_")
        path = SCENARIOS_DIR / f"{safe}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return True, f"sauvegardé → {path}"

    def _load(self, name: str):
        path = SCENARIOS_DIR / (name if name.endswith(".json") else f"{name}.json")
        if not path.exists():
            return
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        self.name        = d.get("name", path.stem)
        self.description = d.get("description", "")
        self.background  = d.get("background")
        self.vertices    = [list(map(float, v)) for v in d.get("zone", {}).get("vertices", [])]
        self.enemies     = [list(map(float, e["position"])) for e in d.get("enemies", [])]
        if "spawn" in d:
            self.spawn = list(map(float, d["spawn"]))
        cov = d.get("coverage", {})
        self.cov_n      = int(cov.get("n_samples", 500))
        self.cov_decay  = float(cov.get("decay", 0.0))
        self.cov_thresh = float(cov.get("threshold", 0.5))
        self.drone_counts = {t: 0 for t in self.drone_types}
        for drone in d.get("drones", []):
            t = drone.get("type")
            if t in self.drone_counts:
                self.drone_counts[t] += 1


# ── Caméra ─────────────────────────────────────────────────────────────────────

class Camera:
    def __init__(self, screen_w, screen_h):
        self.zoom = min((screen_w - PANEL_W) / WORLD_W, screen_h / WORLD_H) * 0.92
        self.cx = WORLD_W / 2
        self.cy = WORLD_H / 2

    def w2s(self, wx, wy, sw, sh):
        return (int((wx - self.cx) * self.zoom + (sw - PANEL_W) / 2),
                int((wy - self.cy) * self.zoom + sh / 2))

    def s2w(self, sx, sy, sw, sh):
        return ((sx - (sw - PANEL_W) / 2) / self.zoom + self.cx,
                (sy - sh / 2) / self.zoom + self.cy)

    def reset(self, sw, sh):
        self.zoom = min((sw - PANEL_W) / WORLD_W, sh / WORLD_H) * 0.92
        self.cx, self.cy = WORLD_W / 2, WORLD_H / 2


# ── Application ─────────────────────────────────────────────────────────────────

def run(load_name=None):
    pygame.init()
    screen = pygame.display.set_mode((1200, 760), pygame.RESIZABLE)
    pygame.display.set_caption("swarm-sim — éditeur de scénarios")
    clock = pygame.time.Clock()

    font    = pygame.font.SysFont("Segoe UI,DejaVu Sans,Arial", 14)
    font_sm = pygame.font.SysFont("Segoe UI,DejaVu Sans,Arial", 12)
    font_lg = pygame.font.SysFont("Segoe UI,DejaVu Sans,Arial", 18, bold=True)

    ed  = Editor(load_name)
    cam = Camera(*screen.get_size())

    bg_cache = {"name": None, "size": None, "surf": None}
    panning = False
    pan_last = (0, 0)
    dragging_over = False     # un fichier survole la fenêtre (DROPBEGIN/DROPCOMPLETE)
    ui_rects = {}             # rempli à chaque frame, utilisé pour le hit-testing

    def set_status(msg, ok=True):
        ed.status = (msg, pygame.time.get_ticks(), ok)

    def load_bg_surface(sw, sh):
        """Charge + scale le fond sur le rectangle monde à l'écran (avec cache)."""
        if not ed.background:
            return None
        x0, y0 = cam.w2s(0, 0, sw, sh)
        x1, y1 = cam.w2s(WORLD_W, WORLD_H, sw, sh)
        size = (max(1, x1 - x0), max(1, y1 - y0))
        if bg_cache["name"] == ed.background and bg_cache["size"] == size:
            return bg_cache["surf"], (x0, y0)
        path = MAPS_DIR / ed.background
        if not path.exists():
            return None
        try:
            img = pygame.image.load(str(path)).convert()
            surf = pygame.transform.scale(img, size)
        except Exception:
            return None
        bg_cache.update(name=ed.background, size=size, surf=surf)
        return surf, (x0, y0)

    def nearest_enemy(wx, wy):
        if not ed.enemies:
            return -1
        d = [(wx - e[0]) ** 2 + (wy - e[1]) ** 2 for e in ed.enemies]
        return int(np.argmin(d))

    def clamp_world(wx, wy):
        return [float(np.clip(wx, 0, WORLD_W)), float(np.clip(wy, 0, WORLD_H))]

    # ── Boucle ────────────────────────────────────────────────────────────────
    running = True
    while running:
        sw, sh = screen.get_size()
        mx, my = pygame.mouse.get_pos()
        canvas = mx < sw - PANEL_W
        ctrl = pygame.key.get_mods() & pygame.KMOD_CTRL

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False

            # ── Glisser-déposer d'un fichier (SDL2 / pygame ≥ 2) ──────────────
            elif e.type == pygame.DROPFILE:
                ok, msg = ed.import_background(e.file)
                set_status(msg, ok)
                bg_cache["name"] = None         # force le rechargement du fond
                dragging_over = False
            elif hasattr(pygame, "DROPBEGIN") and e.type == pygame.DROPBEGIN:
                dragging_over = True
            elif hasattr(pygame, "DROPCOMPLETE") and e.type == pygame.DROPCOMPLETE:
                dragging_over = False

            elif e.type == pygame.KEYDOWN:
                # Édition de champ texte prioritaire
                if ed.focus in ("name", "description"):
                    if e.key == pygame.K_RETURN or e.key == pygame.K_ESCAPE:
                        ed.focus = None
                    elif e.key == pygame.K_BACKSPACE:
                        cur = getattr(ed, ed.focus)
                        setattr(ed, ed.focus, cur[:-1])
                    elif e.unicode and e.unicode.isprintable():
                        cur = getattr(ed, ed.focus)
                        if len(cur) < 60:
                            setattr(ed, ed.focus, cur + e.unicode)
                    continue
                # Raccourcis (hors saisie texte)
                if ctrl and e.key == pygame.K_s:
                    ok, msg = ed.save(); set_status(msg, ok)
                elif e.key == pygame.K_1: ed.mode = "polygone"
                elif e.key == pygame.K_2: ed.mode = "ennemis"
                elif e.key == pygame.K_3: ed.mode = "spawn"
                elif e.key == pygame.K_4: ed.mode = "pan"
                elif e.key == pygame.K_b: ed.cycle_background(); bg_cache["name"] = None
                elif e.key == pygame.K_r: cam.reset(sw, sh)
                elif e.key == pygame.K_BACKSPACE and ed.mode == "polygone" and ed.vertices:
                    ed.vertices.pop()
                elif e.key == pygame.K_ESCAPE:
                    running = False

            elif e.type == pygame.MOUSEWHEEL and canvas:
                wx, wy = cam.s2w(mx, my, sw, sh)
                cam.zoom *= 1.1 if e.y > 0 else 0.9
                cam.zoom = max(0.005, min(0.2, cam.zoom))
                nx, ny = cam.s2w(mx, my, sw, sh)
                cam.cx += wx - nx
                cam.cy += wy - ny

            elif e.type == pygame.MOUSEBUTTONDOWN:
                # 1) Panneau ?
                hit = None
                for key, rect in ui_rects.items():
                    if rect.collidepoint(mx, my):
                        hit = key; break
                if hit is not None:
                    _handle_ui_click(ed, hit, set_status, bg_cache)
                    if hit not in ("name", "description"):
                        ed.focus = None
                    continue
                ed.focus = None

                # 2) Pan (molette, ou bouton gauche en mode pan)
                if e.button == 2 or (e.button == 1 and ed.mode == "pan" and canvas):
                    panning = True; pan_last = e.pos; continue

                # 3) Canvas selon le mode
                if not canvas:
                    continue
                wx, wy = cam.s2w(mx, my, sw, sh)
                wx, wy = clamp_world(wx, wy)
                if ed.mode == "polygone" and e.button == 1:
                    ed.vertices.append([wx, wy])
                elif ed.mode == "ennemis":
                    if e.button == 1:
                        ed.enemies.append([wx, wy])
                    elif e.button == 3:
                        i = nearest_enemy(wx, wy)
                        if i >= 0:
                            ed.enemies.pop(i)
                elif ed.mode == "spawn" and e.button == 1:
                    ed.spawn = [wx, wy]

            elif e.type == pygame.MOUSEBUTTONUP:
                panning = False

            elif e.type == pygame.MOUSEMOTION and panning:
                cam.cx -= (e.pos[0] - pan_last[0]) / cam.zoom
                cam.cy -= (e.pos[1] - pan_last[1]) / cam.zoom
                pan_last = e.pos

        # ── Rendu ──────────────────────────────────────────────────────────────
        screen.fill(BG)
        _draw_canvas(screen, ed, cam, sw, sh, load_bg_surface, font_sm, font_lg, dragging_over)
        ui_rects = _draw_panel(screen, ed, sw, sh, font, font_sm, font_lg, mx, my)
        _draw_status(screen, ed, sw, sh, font)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


# ── Clics panneau ───────────────────────────────────────────────────────────────

def _handle_ui_click(ed, key, set_status, bg_cache):
    if key == "name":
        ed.focus = "name"
    elif key == "description":
        ed.focus = "description"
    elif key == "bg":
        ed.cycle_background(); bg_cache["name"] = None
    elif key == "save":
        ok, msg = ed.save(); set_status(msg, ok)
    elif key == "clear_poly":
        ed.vertices.clear()
    elif key == "clear_enemies":
        ed.enemies.clear()
    elif key.startswith("drone+"):
        t = key[6:]; ed.drone_counts[t] = min(999, ed.drone_counts[t] + 1)
    elif key.startswith("drone-"):
        t = key[6:]; ed.drone_counts[t] = max(0, ed.drone_counts[t] - 1)
    elif key == "covn+": ed.cov_n = min(5000, ed.cov_n + 50)
    elif key == "covn-": ed.cov_n = max(10, ed.cov_n - 50)
    elif key == "covd+": ed.cov_decay = round(min(0.1, ed.cov_decay + 0.001), 4)
    elif key == "covd-": ed.cov_decay = round(max(0.0, ed.cov_decay - 0.001), 4)
    elif key == "covt+": ed.cov_thresh = round(min(1.0, ed.cov_thresh + 0.05), 2)
    elif key == "covt-": ed.cov_thresh = round(max(0.0, ed.cov_thresh - 0.05), 2)
    elif key.startswith("mode_"):
        ed.mode = key[5:]


# ── Dessin canvas ────────────────────────────────────────────────────────────────

def _draw_canvas(screen, ed, cam, sw, sh, load_bg, font_sm, font_lg, dragging_over):
    cw = sw - PANEL_W
    canvas_rect = pygame.Rect(0, 0, cw, sh)
    screen.set_clip(canvas_rect)

    # rectangle monde + fond
    x0, y0 = cam.w2s(0, 0, sw, sh)
    x1, y1 = cam.w2s(WORLD_W, WORLD_H, sw, sh)
    pygame.draw.rect(screen, WORLD_BG, (x0, y0, x1 - x0, y1 - y0))
    bg = load_bg(sw, sh)
    if bg:
        surf, pos = bg
        screen.blit(surf, pos)
    pygame.draw.rect(screen, WORLD_BORDER, (x0, y0, x1 - x0, y1 - y0), 1)

    # prévisualisation des slots de patrouille (réutilise PatrolZone.waypoints)
    if len(ed.vertices) >= 3 and ed.total_drones > 0:
        try:
            zone = PatrolZone(np.array(ed.vertices, dtype=float))
            for wp in zone.waypoints(min(ed.total_drones, 300)):
                px, py = cam.w2s(wp[0], wp[1], sw, sh)
                pygame.draw.circle(screen, WP_COL, (px, py), 4)
                pygame.draw.circle(screen, (255, 255, 255), (px, py), 4, 1)
        except Exception:
            pass

    # polygone
    if ed.vertices:
        pts = [cam.w2s(x, y, sw, sh) for x, y in ed.vertices]
        if len(pts) >= 2:
            closed = pts + [pts[0]] if len(pts) >= 3 else pts
            pygame.draw.lines(screen, POLY_LINE, len(pts) >= 3, closed, 2)
        for i, (px, py) in enumerate(pts):
            pygame.draw.circle(screen, POLY_VERT, (px, py), 6)
            pygame.draw.circle(screen, (40, 40, 40), (px, py), 6, 1)
            if i == 0:
                screen.blit(font_sm.render("1", True, (30, 30, 30)), (px - 3, py - 7))

    # ennemis
    for ex, ey in ed.enemies:
        px, py = cam.w2s(ex, ey, sw, sh)
        pygame.draw.circle(screen, ENEMY_COL, (px, py), 9, 2)
        pygame.draw.line(screen, ENEMY_COL, (px - 5, py - 5), (px + 5, py + 5), 2)
        pygame.draw.line(screen, ENEMY_COL, (px + 5, py - 5), (px - 5, py + 5), 2)

    # spawn
    sp = ed.spawn if ed.spawn is not None else (ed.vertices[0] if ed.vertices else None)
    if sp is not None:
        px, py = cam.w2s(sp[0], sp[1], sw, sh)
        pygame.draw.circle(screen, SPAWN_COL, (px, py), 10)
        pygame.draw.circle(screen, (20, 60, 30), (px, py), 10, 2)
        screen.blit(font_sm.render("S", True, (15, 40, 25)), (px - 4, py - 8))

    # overlay "déposez un PNG" quand un fichier survole la fenêtre
    if dragging_over:
        ov = pygame.Surface((cw, sh), pygame.SRCALPHA)
        ov.fill((20, 40, 70, 120))
        pygame.draw.rect(ov, (120, 180, 255), (8, 8, cw - 16, sh - 16), 3, border_radius=10)
        screen.blit(ov, (0, 0))
        t = font_lg.render("Déposez un PNG pour le définir comme fond", True, (220, 235, 255))
        screen.blit(t, (cw // 2 - t.get_width() // 2, sh // 2 - t.get_height() // 2))

    screen.set_clip(None)


# ── Dessin panneau ───────────────────────────────────────────────────────────────

def _draw_panel(screen, ed, sw, sh, font, font_sm, font_lg, mx, my):
    rects = {}
    px0 = sw - PANEL_W
    pygame.draw.rect(screen, PANEL_BG, (px0, 0, PANEL_W, sh))
    pygame.draw.line(screen, PANEL_BORDER, (px0, 0), (px0, sh), 1)

    x = px0 + PAD
    w = PANEL_W - 2 * PAD
    y = PAD

    screen.blit(font_lg.render("ÉDITEUR", True, TEXT_BRIGHT), (x, y)); y += 30

    # ── Modes ────────────────────────────────────────────────────────────────
    screen.blit(font_sm.render("MODE", True, ACCENT), (x, y)); y += 18
    bw = (w - 3 * 6) // 4
    for i, m in enumerate(Editor.MODES):
        r = pygame.Rect(x + i * (bw + 6), y, bw, 26)
        active = ed.mode == m
        hover = r.collidepoint(mx, my)
        col = BTN_ACTIVE if active else (BTN_HOVER if hover else BTN_BG)
        pygame.draw.rect(screen, col, r, border_radius=4)
        lbl = font_sm.render(f"{i+1} {m[:4]}", True, TEXT_BRIGHT if active else TEXT)
        screen.blit(lbl, (r.centerx - lbl.get_width() // 2, r.centery - lbl.get_height() // 2))
        rects[f"mode_{m}"] = r
    y += 26 + 14

    # ── Champs texte ─────────────────────────────────────────────────────────
    y = _field(screen, font, font_sm, rects, x, y, w, "Nom", ed.name, ed.focus == "name", "name")
    y = _field(screen, font, font_sm, rects, x, y, w, "Description", ed.description, ed.focus == "description", "description")

    # ── Background ───────────────────────────────────────────────────────────
    screen.blit(font_sm.render("FOND (B pour changer)", True, ACCENT), (x, y)); y += 18
    r = pygame.Rect(x, y, w, 26)
    hover = r.collidepoint(mx, my)
    pygame.draw.rect(screen, BTN_HOVER if hover else FIELD_BG, r, border_radius=4)
    pygame.draw.rect(screen, PANEL_BORDER, r, 1, border_radius=4)
    bgname = ed.background or "(aucun)"
    screen.blit(font_sm.render(bgname, True, TEXT), (r.x + 8, r.centery - 7))
    rects["bg"] = r
    y += 26 + 4
    screen.blit(font_sm.render("ou glissez un PNG sur la fenêtre", True, DROP_HINT), (x, y))
    y += 14 + 10

    # ── Drones par type ──────────────────────────────────────────────────────
    screen.blit(font_sm.render(f"DRONES (total : {ed.total_drones})", True, ACCENT), (x, y)); y += 18
    for t in ed.drone_types:
        r_lbl = pygame.Rect(x, y, w - 96, 26)
        pygame.draw.rect(screen, FIELD_BG, r_lbl, border_radius=4)
        screen.blit(font_sm.render(t, True, TEXT), (r_lbl.x + 8, r_lbl.centery - 7))
        cnt = font_sm.render(str(ed.drone_counts[t]), True, TEXT_BRIGHT)
        screen.blit(cnt, (r_lbl.right - 22, r_lbl.centery - 7))
        rm = pygame.Rect(x + w - 90, y, 42, 26)
        rp = pygame.Rect(x + w - 42, y, 42, 26)
        for rr, lab, kk in ((rm, "-", f"drone-{t}"), (rp, "+", f"drone+{t}")):
            hover = rr.collidepoint(mx, my)
            pygame.draw.rect(screen, BTN_HOVER if hover else BTN_BG, rr, border_radius=4)
            l = font.render(lab, True, TEXT_BRIGHT)
            screen.blit(l, (rr.centerx - l.get_width() // 2, rr.centery - l.get_height() // 2))
            rects[kk] = rr
        y += 30
    y += 10

    # ── Coverage ─────────────────────────────────────────────────────────────
    screen.blit(font_sm.render("COVERAGE", True, ACCENT), (x, y)); y += 18
    y = _stepper(screen, font, font_sm, rects, x, y, w, "n_samples", str(ed.cov_n), "covn", mx, my)
    y = _stepper(screen, font, font_sm, rects, x, y, w, "decay", f"{ed.cov_decay:.3f}", "covd", mx, my)
    y = _stepper(screen, font, font_sm, rects, x, y, w, "threshold", f"{ed.cov_thresh:.2f}", "covt", mx, my)
    y += 8

    # ── Clear + Save ─────────────────────────────────────────────────────────
    for lab, kk, col in (("Vider polygone", "clear_poly", BTN_BG),
                         ("Vider ennemis", "clear_enemies", BTN_BG)):
        r = pygame.Rect(x, y, w, 24)
        hover = r.collidepoint(mx, my)
        pygame.draw.rect(screen, BTN_HOVER if hover else col, r, border_radius=4)
        l = font_sm.render(lab, True, TEXT)
        screen.blit(l, (r.centerx - l.get_width() // 2, r.centery - l.get_height() // 2))
        rects[kk] = r
        y += 28

    r = pygame.Rect(x, sh - 44, w, 32)
    hover = r.collidepoint(mx, my)
    pygame.draw.rect(screen, (60, 150, 90) if hover else (45, 120, 72), r, border_radius=5)
    l = font.render("SAUVEGARDER  (Ctrl+S)", True, TEXT_BRIGHT)
    screen.blit(l, (r.centerx - l.get_width() // 2, r.centery - l.get_height() // 2))
    rects["save"] = r

    return rects


def _field(screen, font, font_sm, rects, x, y, w, label, value, focused, key):
    screen.blit(font_sm.render(label.upper(), True, ACCENT), (x, y)); y += 18
    r = pygame.Rect(x, y, w, 28)
    pygame.draw.rect(screen, FIELD_FOCUS if focused else FIELD_BG, r, border_radius=4)
    pygame.draw.rect(screen, ACCENT if focused else PANEL_BORDER, r, 1, border_radius=4)
    txt = value + ("|" if focused and pygame.time.get_ticks() % 1000 < 500 else "")
    screen.blit(font.render(txt, True, TEXT_BRIGHT), (r.x + 8, r.centery - 9))
    rects[key] = r
    return y + 28 + 12


def _stepper(screen, font, font_sm, rects, x, y, w, label, value, key, mx, my):
    r_lbl = pygame.Rect(x, y, w - 96, 26)
    pygame.draw.rect(screen, FIELD_BG, r_lbl, border_radius=4)
    screen.blit(font_sm.render(label, True, TEXT), (r_lbl.x + 8, r_lbl.centery - 7))
    v = font_sm.render(value, True, TEXT_BRIGHT)
    screen.blit(v, (r_lbl.right - v.get_width() - 8, r_lbl.centery - 7))
    rm = pygame.Rect(x + w - 90, y, 42, 26)
    rp = pygame.Rect(x + w - 42, y, 42, 26)
    for rr, lab, kk in ((rm, "-", f"{key}-"), (rp, "+", f"{key}+")):
        hover = rr.collidepoint(mx, my)
        pygame.draw.rect(screen, BTN_HOVER if hover else BTN_BG, rr, border_radius=4)
        l = font.render(lab, True, TEXT_BRIGHT)
        screen.blit(l, (rr.centerx - l.get_width() // 2, rr.centery - l.get_height() // 2))
        rects[kk] = rr
    return y + 30


def _draw_status(screen, ed, sw, sh, font):
    msg = ed.status[0]
    if not msg:
        return
    if len(ed.status) >= 2 and pygame.time.get_ticks() - ed.status[1] > 4000:
        return
    ok = ed.status[2] if len(ed.status) > 2 else True
    col = OK_GREEN if ok else ERR_RED
    t = font.render(msg, True, col)
    bg = pygame.Surface((t.get_width() + 16, t.get_height() + 8))
    bg.fill((0, 0, 0))
    screen.blit(bg, (12, sh - 36))
    screen.blit(t, (20, sh - 32))


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    run(arg)