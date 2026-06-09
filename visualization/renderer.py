# visualization/renderer.py
"""
Renderer pygame pour swarm-sim.

Architecture raw surface :
    Tout le contenu du monde est dessiné sur une surface intermédiaire
    (raw_surf) en coordonnées raw, indépendamment du zoom et de la fenêtre.
    La projection (zoom, pan, crop) est appliquée en une seule passe à la fin.

Point d'entrée : run(world, zone=None, coverage=None, sim_state=None)
"""

import pygame
import numpy as np
from pathlib import Path

from core.world import World
from environment.zone import PatrolZone
from systems.coverage import CoverageMap
from visualization.utils import to_raw, make_raw_surface
import systems.detection as detection

# ── Configuration ──────────────────────────────────────────────────────────────

FPS          = 60
BG_WORLD     = (15, 15, 25)
BG_OUTSIDE   = ( 5,  5,  8)
WORLD_BORDER = (40, 55, 80)

DRONE_COLOR     = (80, 200, 255)
DRONE_RADIUS    = 100
DRONE_SCALE_EXP = 0.85

ZONE_FILL_COLOR   = (60, 180,  80,  18)
ZONE_BORDER_COLOR = (60, 180,  80, 200)

WAYPOINT_COLOR    = (255, 220,  60)
WAYPOINT_RADIUS   = 12
TARGET_LINE_COLOR = (255, 220,  60, 120)

SENSOR_FRIENDLY_COLOR = ( 80, 150, 255)
SENSOR_ENEMY_COLOR    = (200,  60,  60)
SENSOR_FILL_ALPHA     = 25
SENSOR_BORDER_ALPHA   = 180

MINIMAP_RATIO_W = 0.18
MINIMAP_RATIO_H = 0.20
MINIMAP_PAD     = 10
MINIMAP_BG      = (10, 12, 20)
MINIMAP_BORDER  = (50, 70, 100)
VIEWPORT_COLOR  = (80, 200, 255)

_ROOT           = Path(__file__).parent.parent
BACKGROUND_PATH = _ROOT / "data" / "maps" / "background.png"

SPEED_LEVELS = [0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0]

CONTROLS = [
    "scroll     zoom",
    "clic droit  pan",
    "R          reset",
    "D          debug",
    "─────────────",
    "space      pause",
    "->          Etape suivante",
]


# ── Assets ─────────────────────────────────────────────────────────────────────

def load_background(raw_w: int, raw_h: int) -> pygame.Surface | None:
    if BACKGROUND_PATH is None:
        return None
    try:
        img = pygame.image.load(BACKGROUND_PATH).convert()
        return pygame.transform.scale(img, (raw_w, raw_h))
    except Exception as e:
        print(f"[renderer] background non chargé : {e}")
        return None


# ── Raw surface ────────────────────────────────────────────────────────────────

def _draw_zone(surface, raw_w, raw_h, world, zone) -> None:
    pts = [to_raw(x, y, world.W, world.H, raw_w, raw_h) for x, y in zone.vertices]
    if len(pts) < 3:
        return
    s = pygame.Surface((raw_w, raw_h), pygame.SRCALPHA)
    pygame.draw.polygon(s, ZONE_FILL_COLOR, pts)
    surface.blit(s, (0, 0))
    s2 = pygame.Surface((raw_w, raw_h), pygame.SRCALPHA)
    pygame.draw.polygon(s2, ZONE_BORDER_COLOR, pts, 3)
    surface.blit(s2, (0, 0))


def _draw_coverage_perimeter(surface, raw_w, raw_h, world, coverage) -> None:
    pts, values = coverage.points, coverage.values
    for i in range(len(pts)):
        v = float(values[i])
        if v < 0.5:
            t   = v / 0.5
            col = (int(220), int(60 + 100 * t), 40)
        else:
            t   = (v - 0.5) / 0.5
            col = (int(220 - 160 * t), int(160 + 60 * t), 40)
        x, y = to_raw(pts[i][0], pts[i][1], world.W, world.H, raw_w, raw_h)
        pygame.draw.circle(surface, col, (x, y), 3)


def _draw_waypoints(surface, raw_w, raw_h, world, zone) -> None:
    n = world.n_alive
    if n == 0:
        return
    for wp in zone.waypoints(n):
        x, y = to_raw(wp[0], wp[1], world.W, world.H, raw_w, raw_h)
        r    = WAYPOINT_RADIUS
        pts  = [(x, y-r), (x+r, y), (x, y+r), (x-r, y)]
        pygame.draw.polygon(surface, WAYPOINT_COLOR, pts)
        pygame.draw.polygon(surface, (255, 255, 255), pts, 1)


def _draw_target_lines(surface, raw_w, raw_h, world) -> None:
    s = pygame.Surface((raw_w, raw_h), pygame.SRCALPHA)
    for drone_id in np.where(world.alive_mask)[0]:
        x0, y0 = to_raw(world.positions[drone_id][0], world.positions[drone_id][1], world.W, world.H, raw_w, raw_h)
        x1, y1 = to_raw(world.targets[drone_id][0],   world.targets[drone_id][1],   world.W, world.H, raw_w, raw_h)
        pygame.draw.line(s, TARGET_LINE_COLOR, (x0, y0), (x1, y1), 2)
    surface.blit(s, (0, 0))


def _draw_sensor_circles(surface, raw_w, raw_h, world) -> None:
    alive_ids = np.where(world.alive_mask)[0]
    if len(alive_ids) == 0:
        return
    detected, friendly = detection.update(world)
    enemy_in_range     = np.any(detected & ~friendly, axis=1)
    for idx, drone_id in enumerate(alive_ids):
        x, y = to_raw(world.positions[drone_id][0], world.positions[drone_id][1], world.W, world.H, raw_w, raw_h)
        r    = max(4, int(world.components.arr("sensor_radius")[drone_id] * world.components.arr("sensor_efficiency")[drone_id] / world.W * raw_w))
        col  = SENSOR_ENEMY_COLOR if enemy_in_range[idx] else SENSOR_FRIENDLY_COLOR
        cs   = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(cs, col + (SENSOR_FILL_ALPHA,),   (r, r), r)
        pygame.draw.circle(cs, col + (SENSOR_BORDER_ALPHA,), (r, r), r, 1)
        surface.blit(cs, (x - r, y - r))


def draw_world_raw(surface, raw_w, raw_h, world, zone=None, coverage=None, background=None, debug=False) -> None:
    if background is not None:
        surface.blit(background, (0, 0))
    if zone is not None:
        _draw_zone(surface, raw_w, raw_h, world, zone)
        if coverage is not None:
            _draw_coverage_perimeter(surface, raw_w, raw_h, world, coverage)
        if debug:
            _draw_waypoints(surface, raw_w, raw_h, world, zone)
            _draw_target_lines(surface, raw_w, raw_h, world)
    _draw_sensor_circles(surface, raw_w, raw_h, world)


# ── Screen overlay ─────────────────────────────────────────────────────────────

def _world_to_screen(wx, wy, cam_x, cam_y, zoom, sw, sh):
    return (int((wx - cam_x) * zoom + sw / 2), int((wy - cam_y) * zoom + sh / 2))


def draw_screen_overlay(surface, world, cam_x, cam_y, zoom, font, debug=False) -> None:
    sw, sh = surface.get_size()
    r = max(2, int(DRONE_RADIUS * zoom ** DRONE_SCALE_EXP))
    for drone in world.drones.values():
        x, y = _world_to_screen(drone.position[0], drone.position[1], cam_x, cam_y, zoom, sw, sh)
        pygame.draw.circle(surface, DRONE_COLOR, (x, y), r)
        if debug:
            lbl = font.render(f"{drone.battery_level:.2f}", True, (180, 180, 180))
            surface.blit(lbl, (x + r + 3, y - lbl.get_height() // 2))


def draw_minimap_overlay(surface, world, mm_w, mm_h) -> None:
    for drone in world.drones.values():
        x, y = to_raw(drone.position[0], drone.position[1], world.W, world.H, mm_w, mm_h)
        pygame.draw.circle(surface, DRONE_COLOR, (x, y), 2)


# ── HUD ───────────────────────────────────────────────────────────────────────

def draw_controls(surface, font, debug) -> None:
    pad = 6
    lh  = font.get_height() + 2
    w, h = 140, len(CONTROLS) * lh + pad * 2
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill((0, 0, 0, 180))
    surface.blit(s, (pad, surface.get_height() - h - pad))
    for i, line in enumerate(CONTROLS):
        col = (180, 220, 100) if (line.startswith("D") and debug) \
            else (40, 45, 55) if line.startswith("─") \
            else (120, 130, 150)
        surface.blit(font.render(line, True, col), (pad * 2, surface.get_height() - h - pad + pad + i * lh))


def draw_coverage_hud(surface, font_sm, coverage, debug) -> None:
    m      = coverage.metrics()
    sw, sh = surface.get_size()
    pad    = 10
    bar_w, bar_h = 160, 10
    bar_x  = sw - bar_w - pad
    bar_y  = sh - bar_h - pad

    pygame.draw.rect(surface, (30, 30, 40), (bar_x, bar_y, bar_w, bar_h))
    fill = int(bar_w * m["coverage_ratio"])
    col  = (80, 200, 80) if m["coverage_ratio"] > 0.75 else (220, 180, 0) if m["coverage_ratio"] > 0.40 else (220, 60, 60)
    if fill > 0:
        pygame.draw.rect(surface, col, (bar_x, bar_y, fill, bar_h))
    pygame.draw.rect(surface, (60, 70, 90), (bar_x, bar_y, bar_w, bar_h), 1)
    lbl = font_sm.render(f"coverage {m['coverage_ratio']*100:.0f}%", True, (160, 170, 180))
    surface.blit(lbl, (bar_x, bar_y - lbl.get_height() - 2))

    if not debug:
        return
    lines = [f"ratio    {m['coverage_ratio']*100:.1f}%", f"quality  {m['mean_value']*100:.1f}%",
             f"max gap  {m['max_gap']*100:.1f}%", f"decay    {coverage.decay:.4f}"]
    lh = font_sm.get_height() + 2
    ph = len(lines) * lh + pad
    py = bar_y - bar_h - ph - 4
    bg = pygame.Surface((bar_w, ph), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 160))
    surface.blit(bg, (bar_x, py))
    for i, line in enumerate(lines):
        surface.blit(font_sm.render(line, True, (160, 180, 160)), (bar_x + 6, py + pad // 2 + i * lh))


def draw_debug_badge(surface, font) -> None:
    lbl = font.render("  DEBUG  ", True, (15, 15, 25), (255, 220, 60))
    surface.blit(lbl, (10, 10))


# ── Playback bar (bouton pause + slider vitesse) ───────────────────────────────

_BTN_W, _BTN_H   = 32, 24
_SLIDER_W        = 140
_SLIDER_H        = 6
_HANDLE_R        = 7
_BAR_PAD         = 8
_BAR_H           = max(_BTN_H, _HANDLE_R * 2) + _BAR_PAD * 2
_BAR_W           = _BTN_W + 10 + _SLIDER_W + 40 + _BAR_PAD * 2


def _speed_to_idx(speed: float) -> int:
    return min(range(len(SPEED_LEVELS)), key=lambda i: abs(SPEED_LEVELS[i] - speed))


def _draw_play_icon(surface, cx, cy, size, col) -> None:
    """Triangle plein pointant à droite — icône play."""
    h = size
    w = int(h * 0.85)
    pts = [(cx - w//2, cy - h//2), (cx - w//2, cy + h//2), (cx + w//2, cy)]
    pygame.draw.polygon(surface, col, pts)


def _draw_pause_icon(surface, cx, cy, size, col) -> None:
    """Deux rectangles — icône pause."""
    bar_w = max(2, size // 4)
    bar_h = size
    gap   = max(2, size // 4)
    x0    = cx - bar_w - gap // 2
    x1    = cx + gap // 2
    y0    = cy - bar_h // 2
    pygame.draw.rect(surface, col, (x0, y0, bar_w, bar_h))
    pygame.draw.rect(surface, col, (x1, y0, bar_w, bar_h))


def draw_playback_bar(surface, font_sm, font_med, sim_state) -> dict:
    """
    Barre de lecture — bouton pause/play (dessiné) + slider vitesse.
    Retourne les rects interactifs pour la gestion des clics.
    """
    sw, sh = surface.get_size()
    paused = sim_state["paused"]
    speed  = sim_state["speed"]

    bar_x = sw // 2 - _BAR_W // 2
    bar_y = sh - _BAR_H - 6

    # fond sobre
    bg = pygame.Surface((_BAR_W, _BAR_H), pygame.SRCALPHA)
    bg.fill((8, 10, 16, 200))
    pygame.draw.rect(bg, (35, 42, 55), (0, 0, _BAR_W, _BAR_H), 1)
    surface.blit(bg, (bar_x, bar_y))

    # ── bouton pause/play ─────────────────────────────────────────────────────
    btn_x    = bar_x + _BAR_PAD
    btn_y    = bar_y + (_BAR_H - _BTN_H) // 2
    btn_rect = pygame.Rect(btn_x, btn_y, _BTN_W, _BTN_H)
    btn_cx   = btn_x + _BTN_W // 2
    btn_cy   = btn_y + _BTN_H // 2

    # fond bouton
    pygame.draw.rect(surface, (22, 28, 38), btn_rect)
    pygame.draw.rect(surface, (45, 55, 70), btn_rect, 1)

    icon_col = (180, 185, 195)
    icon_sz  = _BTN_H - 10
    if paused:
        _draw_play_icon(surface, btn_cx, btn_cy, icon_sz, icon_col)
    else:
        _draw_pause_icon(surface, btn_cx, btn_cy, icon_sz, icon_col)

    # ── slider vitesse ────────────────────────────────────────────────────────
    sl_x    = btn_x + _BTN_W + 12
    sl_cy   = bar_y + _BAR_H // 2
    sl_rect = pygame.Rect(sl_x, sl_cy - _SLIDER_H // 2, _SLIDER_W, _SLIDER_H)

    # track
    pygame.draw.rect(surface, (25, 32, 44), sl_rect)
    pygame.draw.rect(surface, (40, 50, 65), sl_rect, 1)

    # fill
    idx    = _speed_to_idx(speed)
    t      = idx / (len(SPEED_LEVELS) - 1)
    fill_w = int(_SLIDER_W * t)
    if fill_w > 0:
        pygame.draw.rect(surface, (55, 90, 130), (sl_x, sl_cy - _SLIDER_H // 2, fill_w, _SLIDER_H))

    # handle
    hx = sl_x + fill_w
    pygame.draw.circle(surface, (130, 155, 185), (hx, sl_cy), _HANDLE_R)
    pygame.draw.circle(surface, (80, 105, 140),  (hx, sl_cy), _HANDLE_R, 1)

    # label vitesse
    lbl = font_sm.render(f"{speed:.2g}x", True, (110, 125, 145))
    surface.blit(lbl, (sl_x + _SLIDER_W + 8, sl_cy - lbl.get_height() // 2))

    return {"btn": btn_rect, "slider": sl_rect}


# ── Projection raw → écran ────────────────────────────────────────────────────

def project_to_screen(screen, raw_surf, raw_w, raw_h, cam_x, cam_y, zoom, world) -> None:
    sw, sh     = screen.get_size()
    world_px_w = world.W * zoom
    world_px_h = world.H * zoom
    if world_px_w < sw - 1 or world_px_h < sh - 1:
        wpw, wph = max(1, int(world_px_w)), max(1, int(world_px_h))
        scaled   = pygame.transform.scale(raw_surf, (wpw, wph))
        bx, by   = (sw - wpw) // 2, (sh - wph) // 2
        screen.blit(scaled, (bx, by))
        pygame.draw.rect(screen, WORLD_BORDER, (bx, by, wpw, wph), 1)
    else:
        raw_cx     = cam_x / world.W * raw_w
        raw_cy     = cam_y / world.H * raw_h
        raw_view_w = (sw / zoom) / world.W * raw_w
        raw_view_h = (sh / zoom) / world.H * raw_h
        rx  = int(max(0.0, raw_cx - raw_view_w / 2))
        ry  = int(max(0.0, raw_cy - raw_view_h / 2))
        rw  = max(1, min(raw_w - rx, int(raw_view_w) + 1))
        rh  = max(1, min(raw_h - ry, int(raw_view_h) + 1))
        screen.blit(pygame.transform.scale(raw_surf.subsurface((rx, ry, rw, rh)), (sw, sh)), (0, 0))


# ── Boucle principale ─────────────────────────────────────────────────────────

def run(
    world:     World,
    zone:      PatrolZone  | None = None,
    coverage:  CoverageMap | None = None,
    sim_state: dict        | None = None,
    width:     int = 800,
    height:    int = 600,
) -> None:
    pygame.init()
    screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
    pygame.display.set_caption("swarm-sim")
    clock  = pygame.time.Clock()

    font_sm  = pygame.font.SysFont("Courier New", 11)
    font_med = pygame.font.SysFont("Courier New", 13)

    raw_surf, RAW_W, RAW_H = make_raw_surface(world.W, world.H)
    background = load_background(RAW_W, RAW_H)
    mm_surf    = pygame.Surface((1, 1))

    zoom  = 1.0
    cam_x = world.W / 2
    cam_y = world.H / 2

    dragging_cam      = False
    dragging_minimap  = False
    dragging_slider   = False
    drag_last         = (0, 0)

    _sim      = sim_state if sim_state is not None else {"paused": False, "speed": 1.0, "step": False}
    state     = {"running": True, "debug": False}
    bar_rects = {}   # mis à jour chaque frame par draw_playback_bar

    # ── helpers ───────────────────────────────────────────────────────────────

    def minimap_rect(sw, sh, mm_w, mm_h):
        return pygame.Rect(sw - mm_w - MINIMAP_PAD, MINIMAP_PAD, mm_w, mm_h)

    def minimap_to_world(mx, my, r):
        return ((mx - r.x) / r.width * world.W, (my - r.y) / r.height * world.H)

    def clamp_camera():
        nonlocal zoom, cam_x, cam_y
        sw, sh   = screen.get_size()
        zoom     = max(min(sw / world.W, sh / world.H), min(10.0, zoom))
        wpw, wph = world.W * zoom, world.H * zoom
        cam_x    = world.W / 2 if wpw <= sw else max((sw/2)/zoom, min(world.W-(sw/2)/zoom, cam_x))
        cam_y    = world.H / 2 if wph <= sh else max((sh/2)/zoom, min(world.H-(sh/2)/zoom, cam_y))

    def reset_camera():
        nonlocal zoom, cam_x, cam_y
        sw, sh = screen.get_size()
        cam_x, cam_y = world.W / 2, world.H / 2
        zoom = min(sw / world.W, sh / world.H)

    def slider_x_to_speed(mx):
        """Convertit une position x en vitesse depuis le slider."""
        sl = bar_rects.get("slider")
        if sl is None:
            return
        t   = max(0.0, min(1.0, (mx - sl.x) / sl.width))
        idx = round(t * (len(SPEED_LEVELS) - 1))
        _sim["speed"] = SPEED_LEVELS[idx]

    # ── handlers ──────────────────────────────────────────────────────────────

    KEY_ACTIONS = {
        pygame.K_ESCAPE: lambda: state.update(running=False),
        pygame.K_r:      reset_camera,
        pygame.K_d:      lambda: state.update(debug=not state["debug"]),
        pygame.K_SPACE:  lambda: _sim.update(paused=not _sim["paused"]),
        pygame.K_RIGHT:  lambda: _sim.update(step=True),
    }

    def on_quit(e):        state["running"] = False
    def on_keydown(e):
        a = KEY_ACTIONS.get(e.key)
        if a: a()
    def on_videoresize(e): clamp_camera()

    def on_mousewheel(e):
        nonlocal zoom, cam_x, cam_y
        sw, sh = screen.get_size()
        mx, my = pygame.mouse.get_pos()
        wx = (mx - sw/2) / zoom + cam_x
        wy = (my - sh/2) / zoom + cam_y
        zoom *= 1.1 if e.y > 0 else 0.9
        cam_x = wx - (mx - sw/2) / zoom
        cam_y = wy - (my - sh/2) / zoom
        clamp_camera()

    def on_mousebuttondown(e):
        nonlocal dragging_cam, dragging_minimap, dragging_slider, drag_last, cam_x, cam_y
        mx, my = e.pos
        btn = bar_rects.get("btn")
        sl  = bar_rects.get("slider")

        if btn and btn.collidepoint(mx, my):
            _sim["paused"] = not _sim["paused"]
        elif sl and pygame.Rect(sl.x - _HANDLE_R, sl.y - _HANDLE_R * 2,
                                sl.width + _HANDLE_R * 2, sl.height + _HANDLE_R * 4).collidepoint(mx, my):
            dragging_slider = True
            slider_x_to_speed(mx)
        elif mm_rect.collidepoint(mx, my):
            cam_x, cam_y = minimap_to_world(mx, my, mm_rect)
            dragging_minimap = True
            clamp_camera()
        elif e.button in (2, 3):
            dragging_cam = True
            drag_last    = e.pos

    def on_mousebuttonup(e):
        nonlocal dragging_cam, dragging_minimap, dragging_slider
        dragging_cam = dragging_minimap = dragging_slider = False

    def on_mousemotion(e):
        nonlocal cam_x, cam_y, drag_last
        mx, my = e.pos
        if dragging_slider:
            slider_x_to_speed(mx)
        elif dragging_minimap and mm_rect.collidepoint(mx, my):
            cam_x, cam_y = minimap_to_world(mx, my, mm_rect)
            clamp_camera()
        elif dragging_cam:
            cam_x -= (mx - drag_last[0]) / zoom
            cam_y -= (my - drag_last[1]) / zoom
            drag_last = e.pos
            clamp_camera()

    EVENT_HANDLERS = {
        pygame.QUIT:            on_quit,
        pygame.KEYDOWN:         on_keydown,
        pygame.VIDEORESIZE:     on_videoresize,
        pygame.MOUSEWHEEL:      on_mousewheel,
        pygame.MOUSEBUTTONDOWN: on_mousebuttondown,
        pygame.MOUSEBUTTONUP:   on_mousebuttonup,
        pygame.MOUSEMOTION:     on_mousemotion,
    }

    reset_camera()

    # ── boucle ────────────────────────────────────────────────────────────────

    while state["running"]:
        sw, sh = screen.get_size()
        debug  = state["debug"]

        mm_w = int(sw * MINIMAP_RATIO_W)
        mm_h = int(sh * MINIMAP_RATIO_H)
        if mm_surf.get_size() != (mm_w, mm_h):
            mm_surf = pygame.Surface((mm_w, mm_h))
        mm_rect = minimap_rect(sw, sh, mm_w, mm_h)

        for event in pygame.event.get():
            h = EVENT_HANDLERS.get(event.type)
            if h: h(event)

        screen.fill(BG_OUTSIDE)

        raw_surf.fill(BG_WORLD)
        draw_world_raw(raw_surf, RAW_W, RAW_H, world, zone, coverage, background, debug)

        project_to_screen(screen, raw_surf, RAW_W, RAW_H, cam_x, cam_y, zoom, world)

        draw_screen_overlay(screen, world, cam_x, cam_y, zoom, font_med, debug)

        mm_surf.fill(MINIMAP_BG)
        pygame.transform.scale(raw_surf, (mm_w, mm_h), mm_surf)
        draw_minimap_overlay(mm_surf, world, mm_w, mm_h)
        vp_w = int((sw / zoom) / world.W * mm_w)
        vp_h = int((sh / zoom) / world.H * mm_h)
        vp_x = int(cam_x / world.W * mm_w - vp_w / 2)
        vp_y = int(cam_y / world.H * mm_h - vp_h / 2)
        pygame.draw.rect(mm_surf, VIEWPORT_COLOR, (vp_x, vp_y, vp_w, vp_h), 1)

        draw_controls(screen, font_med, debug)
        bar_rects = draw_playback_bar(screen, font_sm, font_med, _sim)
        if coverage is not None:
            draw_coverage_hud(screen, font_sm, coverage, debug)
        if debug:
            draw_debug_badge(screen, font_med)

        screen.blit(mm_surf, mm_rect.topleft)
        pygame.draw.rect(screen, MINIMAP_BORDER, mm_rect, 1)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()