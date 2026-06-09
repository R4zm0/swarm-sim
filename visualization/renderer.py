# visualization/renderer.py

import systems.detection as detection

"""
Renderer pygame pour swarm-sim.

Architecture raw surface :
    Tout le contenu du monde est dessiné sur une surface intermédiaire
    (raw_surf) en coordonnées raw, indépendamment du zoom et de la fenêtre.
    La projection (zoom, pan, crop) est appliquée en une seule passe à la fin.

    Avantages :
    - draw_world_raw() ne connaît pas le zoom → pas de zoom en paramètre
    - Ajouter un effet post-processing (fog of war, flou...) = une passe sur raw_surf
    - Minimap = pygame.transform.scale(raw_surf) gratuit

    Deux cas de projection :
    - Monde plus petit que l'écran (dézoom max) → scale entier + blit centré + bandes noires
    - Monde plus grand que l'écran (zoomé)      → subsurface crop + scale plein écran

Point d'entrée : run(world)
"""

import pygame
from core.world import World
from entities import drone
from visualization.utils import to_raw, blit_centered, make_raw_surface
from pathlib import Path
import numpy as np

# ── Configuration ──────────────────────────────────────────────────────────────

FPS          = 60
BG_WORLD     = (15, 15, 25)   # fond à l'intérieur du monde
BG_OUTSIDE   = ( 5,  5,  8)   # fond hors du monde (bandes noires)
WORLD_BORDER = (40, 55, 80)   # bordure du monde

DRONE_COLOR          = (80, 200, 255)
DRONE_WORLD_SIZE     = 30
DRONE_MIN_RADIUS     = 25
DRONE_RADIUS         = 100     # rayon de base en pixels
DRONE_SCALE_EXPONENT = 0.85   # 0 = taille fixe, 1 = scale complet avec zoom

MINIMAP_RATIO_W = 0.18
MINIMAP_RATIO_H = 0.20
MINIMAP_PAD     = 10
MINIMAP_BG      = (10, 12, 20)
MINIMAP_BORDER  = (50, 70, 100)
VIEWPORT_COLOR  = (80, 200, 255)
_ROOT = Path(__file__).parent.parent

# Chemin vers l'image de fond (None = pas de fond)
# Remplacer par le chemin vers ton image : "data/maps/ma_carte.png"
BACKGROUND_PATH = _ROOT / "data" / "maps" / "background.png"

# Raccourcis — ajouter une ligne pour documenter un nouveau contrôle
CONTROLS = [
    "scroll     zoom",
    "clic droit  pan",
    "R          reset",
]


def load_background(raw_w: int, raw_h: int) -> pygame.Surface | None:
    """
    Charge et scale l'image de fond aux dimensions de la raw surface.
    Retourne None si BACKGROUND_PATH est None ou si le fichier est introuvable.
    Appelé une seule fois au démarrage — pas de chargement à chaque frame.
    """
    if BACKGROUND_PATH is None:
        return None
    try:
        img = pygame.image.load(BACKGROUND_PATH).convert()
        return pygame.transform.scale(img, (raw_w, raw_h))
    except Exception as e:
        print(f"[renderer] background non chargé : {e}")
        return None


# ── Rendu du monde — éléments qui scalent avec le zoom ───────────────────────

def draw_world_raw(
    surface: pygame.Surface,
    raw_w: int,
    raw_h: int,
    world,
    background: pygame.Surface | None = None,
) -> None:
    """
    Dessiné sur raw_surf → visible dans la minimap, scale avec le zoom.
    Utiliser to_raw(wx, wy, world.W, world.H, raw_w, raw_h) pour positionner.

    Ajouter ici : terrain, zones, trajectoires.
    """

    # ── fond de carte ──
    if background is not None:
        surface.blit(background, (0, 0))
    
    alive_ids = np.where(world.alive_mask)[0]
    detected, friendly = detection.update(world)
    enemy_in_range = np.any(detected & ~friendly, axis=1)

    for idx, drone_id in enumerate(alive_ids):
        x, y = to_raw(
            world.positions[drone_id][0], world.positions[drone_id][1],
            world.W, world.H, raw_w, raw_h,
        )
        r   = max(4, int(world.components.arr("sensor_radius")[drone_id] / world.W * raw_w))
        col = (200, 60, 60) if enemy_in_range[idx] else (80, 150, 255)

        circle_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(circle_surf, col + (25,),  (r, r), r)
        pygame.draw.circle(circle_surf, col + (180,), (r, r), r, 1)
        surface.blit(circle_surf, (x - r, y - r))




    # ── terrain, zones... ──


# ── Overlay écran — éléments à taille fixe en pixels ─────────────────────────

def _world_to_screen(
    wx: float, wy: float,
    cam_x: float, cam_y: float,
    zoom: float,
    sw: int, sh: int,
) -> tuple[int, int]:
    """Coordonnées monde → pixels écran selon la caméra courante."""
    return (
        int((wx - cam_x) * zoom + sw / 2),
        int((wy - cam_y) * zoom + sh / 2),
    )


def draw_screen_overlay(
    surface: pygame.Surface,
    world,
    cam_x: float,
    cam_y: float,
    zoom: float,
) -> None:
    """
    Dessiné directement sur screen après projection — taille constante au zoom.
    Utiliser _world_to_screen() pour positionner.

    Ajouter ici : sprites drones, labels, marqueurs, cercles de portée.
    """
    sw, sh = surface.get_size()

    # soft scaling : réduit avec le dézoom mais moins vite que le zoom
    # DRONE_SCALE_EXPONENT : 0 = taille fixe, 1 = scale complet
    r = max(2, int(DRONE_RADIUS * zoom ** DRONE_SCALE_EXPONENT))

    # ── drones ──
    for drone in world.drones.values():
        x, y = _world_to_screen(
            drone.position[0], drone.position[1],
            cam_x, cam_y, zoom, sw, sh,
        )
        pygame.draw.circle(surface, DRONE_COLOR, (x, y), r)
        font = pygame.font.SysFont("Courier New", 11)
        surf = font.render(f"{drone.battery_level:.2f}", True, (180, 180, 180))
        surface.blit(surf, (x + r + 3, y - surf.get_height() // 2))


def draw_minimap_overlay(
    surface: pygame.Surface,
    world,
    mm_w: int,
    mm_h: int,
) -> None:
    """
    Même éléments que draw_screen_overlay mais sur la minimap.
    Utiliser to_raw() pour positionner — même projection que la minimap.
    Taille des éléments fixe et petite pour rester lisible sur la minimap.
    """
    # ── drones ──
    for drone in world.drones.values():
        x, y = to_raw(
            drone.position[0], drone.position[1],
            world.W, world.H, mm_w, mm_h,
        )
        pygame.draw.circle(surface, DRONE_COLOR, (x, y), 2)



# ── Projection raw → écran ────────────────────────────────────────────────────

def project_to_screen(
    screen: pygame.Surface,
    raw_surf: pygame.Surface,
    raw_w: int,
    raw_h: int,
    cam_x: float,
    cam_y: float,
    zoom: float,
    world,
) -> None:
    """
    Projette raw_surf sur l'écran selon la caméra courante.

    Cas A — monde plus petit que l'écran :
        Scale entier + blit centré. Bandes noires sur les côtés.
    Cas B — monde remplit l'écran (zoomé) :
        Subsurface crop de la zone visible + scale plein écran.
    """
    sw, sh = screen.get_size()

    world_px_w = world.W * zoom
    world_px_h = world.H * zoom

    if world_px_w < sw - 1 or world_px_h < sh - 1:
        # ── Cas A : monde plus petit que l'écran ──
        wpw = max(1, int(world_px_w))
        wph = max(1, int(world_px_h))
        scaled  = pygame.transform.scale(raw_surf, (wpw, wph))
        blit_x  = (sw - wpw) // 2
        blit_y  = (sh - wph) // 2
        screen.blit(scaled, (blit_x, blit_y))
        # bordure du monde
        pygame.draw.rect(screen, WORLD_BORDER, (blit_x, blit_y, wpw, wph), 1)

    else:
        # ── Cas B : monde remplit l'écran, crop la zone visible ──
        raw_cx     = cam_x / world.W * raw_w
        raw_cy     = cam_y / world.H * raw_h
        raw_view_w = (sw / zoom) / world.W * raw_w
        raw_view_h = (sh / zoom) / world.H * raw_h

        rx = int(max(0.0, raw_cx - raw_view_w / 2))
        ry = int(max(0.0, raw_cy - raw_view_h / 2))
        rw = max(1, min(raw_w - rx, int(raw_view_w) + 1))
        rh = max(1, min(raw_h - ry, int(raw_view_h) + 1))

        crop   = raw_surf.subsurface((rx, ry, rw, rh))
        scaled = pygame.transform.scale(crop, (sw, sh))
        screen.blit(scaled, (0, 0))


# ── Overlay contrôles ─────────────────────────────────────────────────────────

def draw_controls(surface: pygame.Surface) -> None:
    """Raccourcis en bas à gauche, fond semi-transparent."""
    font = pygame.font.SysFont("Courier New", 11)
    pad  = 6
    lh   = font.get_height() + 2
    w    = 130
    h    = len(CONTROLS) * lh + pad * 2

    overlay = pygame.Surface((w, h), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    surface.blit(overlay, (pad, surface.get_height() - h - pad))

    for i, line in enumerate(CONTROLS):
        surf = font.render(line, True, (120, 130, 150))
        surface.blit(surf, (pad * 2, surface.get_height() - h - pad + pad + i * lh))


# ── Boucle principale ─────────────────────────────────────────────────────────

def run(world: World, width: int = 800, height: int = 600) -> None:
    """
    Lance la fenêtre pygame et la boucle de rendu.
    Bloquant jusqu'à fermeture (ESC ou croix).
    """
    pygame.init()
    screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
    pygame.display.set_caption("swarm-sim")
    clock  = pygame.time.Clock()

    # ── surface raw (résolution fixe, proportionnelle au monde) ──
    raw_surf, RAW_W, RAW_H = make_raw_surface(world.W, world.H)

    # ── fond de carte — chargé une fois, scaled aux dims raw ──
    background = load_background(RAW_W, RAW_H)

    # surface minimap — recréée si la fenêtre change de taille
    mm_surf = pygame.Surface((1, 1))

    # ── état caméra ──
    zoom  = 1.0          # sera corrigé par reset_camera()
    cam_x = world.W / 2
    cam_y = world.H / 2

    # ── état drag ──
    dragging_cam     = False
    dragging_minimap = False
    drag_last        = (0, 0)

    # ── fonctions internes ────────────────────────────────────────────────────

    def minimap_rect(sw, sh, mm_w, mm_h) -> pygame.Rect:
        return pygame.Rect(sw - mm_w - MINIMAP_PAD, MINIMAP_PAD, mm_w, mm_h)

    def minimap_to_world(mx, my, mm_rect) -> tuple[float, float]:
        return (
            (mx - mm_rect.x) / mm_rect.width  * world.W,
            (my - mm_rect.y) / mm_rect.height * world.H,
        )

    def clamp_camera() -> None:
        """
        Maintient la caméra dans les limites du monde.
        - zoom min = monde entier visible
        - si monde tient dans une dimension → centré, pan bloqué
        - sinon → clamp aux bords
        """
        nonlocal zoom, cam_x, cam_y
        sw, sh = screen.get_size()

        zoom_min = min(sw / world.W, sh / world.H)
        zoom     = max(zoom_min, min(10.0, zoom))

        world_px_w = world.W * zoom
        world_px_h = world.H * zoom

        if world_px_w <= sw:
            cam_x = world.W / 2
        else:
            half_w = (sw / 2) / zoom
            cam_x  = max(half_w, min(world.W - half_w, cam_x))

        if world_px_h <= sh:
            cam_y = world.H / 2
        else:
            half_h = (sh / 2) / zoom
            cam_y  = max(half_h, min(world.H - half_h, cam_y))

    # ── state dict + actions clavier ─────────────────────────────────────────

    state = {"running": True}

    def reset_camera() -> None:
        nonlocal zoom, cam_x, cam_y
        sw, sh = screen.get_size()
        cam_x = world.W / 2
        cam_y = world.H / 2
        zoom  = min(sw / world.W, sh / world.H)

    # Pour ajouter un raccourci : KEY_ACTIONS[pygame.K_xxx] = callable
    KEY_ACTIONS = {
        pygame.K_ESCAPE: lambda: state.update(running=False),
        pygame.K_r:      reset_camera,
    }

    # ── handlers d'événements ─────────────────────────────────────────────────

    def on_quit(event):
        state["running"] = False

    def on_keydown(event):
        action = KEY_ACTIONS.get(event.key)
        if action:
            action()

    def on_videoresize(event):
        clamp_camera()

    def on_mousewheel(event):
        nonlocal zoom, cam_x, cam_y
        sw, sh = screen.get_size()
        mx, my = pygame.mouse.get_pos()
        wx = (mx - sw / 2) / zoom + cam_x
        wy = (my - sh / 2) / zoom + cam_y
        zoom *= 1.1 if event.y > 0 else 0.9
        cam_x = wx - (mx - sw / 2) / zoom
        cam_y = wy - (my - sh / 2) / zoom
        clamp_camera()

    def on_mousebuttondown(event):
        nonlocal dragging_cam, dragging_minimap, drag_last, cam_x, cam_y
        mx, my = event.pos
        if mm_rect.collidepoint(mx, my):
            cam_x, cam_y = minimap_to_world(mx, my, mm_rect)
            dragging_minimap = True
            clamp_camera()
        elif event.button in (2, 3):
            dragging_cam = True
            drag_last    = event.pos

    def on_mousebuttonup(event):
        nonlocal dragging_cam, dragging_minimap
        dragging_cam     = False
        dragging_minimap = False

    def on_mousemotion(event):
        nonlocal cam_x, cam_y, drag_last
        mx, my = event.pos
        if dragging_minimap and mm_rect.collidepoint(mx, my):
            cam_x, cam_y = minimap_to_world(mx, my, mm_rect)
            clamp_camera()
        elif dragging_cam:
            dx = mx - drag_last[0]
            dy = my - drag_last[1]
            cam_x -= dx / zoom
            cam_y -= dy / zoom
            drag_last = event.pos
            clamp_camera()

    # Pour ajouter un handler : EVENT_HANDLERS[pygame.XXXXX] = callable
    EVENT_HANDLERS = {
        pygame.QUIT:            on_quit,
        pygame.KEYDOWN:         on_keydown,
        pygame.VIDEORESIZE:     on_videoresize,
        pygame.MOUSEWHEEL:      on_mousewheel,
        pygame.MOUSEBUTTONDOWN: on_mousebuttondown,
        pygame.MOUSEBUTTONUP:   on_mousebuttonup,
        pygame.MOUSEMOTION:     on_mousemotion,
    }

    reset_camera()  # zoom initial = fit monde entier

    # ── boucle ───────────────────────────────────────────────────────────────

    while state["running"]:
        sw, sh = screen.get_size()

        mm_w = int(sw * MINIMAP_RATIO_W)
        mm_h = int(sh * MINIMAP_RATIO_H)
        
        if mm_surf.get_size() != (mm_w, mm_h):
            mm_surf = pygame.Surface((mm_w, mm_h))

        mm_rect = minimap_rect(sw, sh, mm_w, mm_h)

        # ── événements ───────────────────────────────────────────────────────

        for event in pygame.event.get():
            handler = EVENT_HANDLERS.get(event.type)
            if handler:
                handler(event)

        # ── dessin ───────────────────────────────────────────────────────────

        # 1. fond hors monde
        screen.fill(BG_OUTSIDE)

        # 2. rendu du monde sur la surface raw
        raw_surf.fill(BG_WORLD)
        draw_world_raw(raw_surf, RAW_W, RAW_H, world, background)

        # 3. projection raw → écran (gère zoom, pan, bandes noires)
        project_to_screen(screen, raw_surf, RAW_W, RAW_H,
                          cam_x, cam_y, zoom, world)

        # 4. éléments à taille fixe (drones, labels...) — par-dessus la projection
        draw_screen_overlay(screen, world, cam_x, cam_y, zoom)

        # 5. minimap : scale entier de raw_surf + overlay + viewport
        mm_surf.fill(MINIMAP_BG)
        pygame.transform.scale(raw_surf, (mm_w, mm_h), mm_surf)
        draw_minimap_overlay(mm_surf, world, mm_w, mm_h)

        vp_w = int((sw / zoom) / world.W * mm_w)
        vp_h = int((sh / zoom) / world.H * mm_h)
        vp_x = int(cam_x / world.W * mm_w - vp_w / 2)
        vp_y = int(cam_y / world.H * mm_h - vp_h / 2)
        pygame.draw.rect(mm_surf, VIEWPORT_COLOR, (vp_x, vp_y, vp_w, vp_h), 1)

        # 5. overlays (contrôles + minimap par-dessus tout)
        draw_controls(screen)
        screen.blit(mm_surf, mm_rect.topleft)
        pygame.draw.rect(screen, MINIMAP_BORDER, mm_rect, 1)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()