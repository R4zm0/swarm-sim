# visualization/utils.py
"""
Fonctions utilitaires de rendu — sans état, sans dépendance à pygame.display.

to_raw()         : coordonnées monde → pixels surface raw
blit_centered()  : colle un sprite centré sur une position
get_scaled_sprite() : scale un sprite avec cache (évite transform.scale chaque frame)
clear_sprite_cache() : vider le cache si les sprites changent
"""

import pygame


# ── Projection ────────────────────────────────────────────────────────────────

def to_raw(
    wx: float, wy: float,
    world_w: float, world_h: float,
    raw_w: int, raw_h: int,
) -> tuple[int, int]:
    """
    Coordonnées monde → pixels sur la surface raw.

    Paramètres
    ----------
    wx, wy         : position en unités monde
    world_w/h      : dimensions du monde
    raw_w/h        : dimensions de la surface raw

    Exemple
    -------
    to_raw(250, 500, 1000, 1000, 2048, 2048) → (512, 1024)
    """
    return (
        int(wx / world_w * raw_w),
        int(wy / world_h * raw_h),
    )


# ── Blit ──────────────────────────────────────────────────────────────────────

def blit_centered(
    surface: pygame.Surface,
    img: pygame.Surface,
    pos: tuple[int, int],
) -> None:
    """
    Colle `img` sur `surface` centré sur `pos`.
    Sans ça, pygame colle en haut-gauche — le sprite serait décalé.
    """
    x, y = pos
    surface.blit(img, (x - img.get_width() // 2, y - img.get_height() // 2))


# ── Cache de sprites scalés ───────────────────────────────────────────────────

_sprite_cache: dict[tuple, pygame.Surface] = {}


def get_scaled_sprite(
    img: pygame.Surface,
    world_size: float,
    zoom: float,
) -> pygame.Surface:
    """
    Retourne `img` scalé à la bonne taille pixel pour le zoom courant.
    Résultat mis en cache par (id(img), taille_px) transform.scale
    n'est appelé que si le zoom a changé.

    Paramètres
    ----------
    img        : surface source (PNG chargé)
    world_size : taille de l'objet en unités monde (ex: 30 pour 30m)
    zoom       : zoom courant de la caméra
    """
    px  = max(1, int(world_size * zoom))
    key = (id(img), px)
    if key not in _sprite_cache:
        _sprite_cache[key] = pygame.transform.scale(img, (px, px))
    return _sprite_cache[key]


def clear_sprite_cache() -> None:
    """Vider le cache — à appeler si les surfaces source changent."""
    _sprite_cache.clear()


# ── Surface raw ───────────────────────────────────────────────────────────────

def make_raw_surface(
    world_w: float,
    world_h: float,
    raw_max: int = 2048,
) -> tuple[pygame.Surface, int, int]:
    """
    Crée une surface raw proportionnelle au monde.
    La dimension la plus grande = raw_max, l'autre est calculée.

    Retourne (surface, raw_w, raw_h).
    """
    ratio = world_w / world_h
    if ratio >= 1.0:
        raw_w = raw_max
        raw_h = max(1, int(raw_max / ratio))
    else:
        raw_h = raw_max
        raw_w = max(1, int(raw_max * ratio))
    return pygame.Surface((raw_w, raw_h)), raw_w, raw_h
