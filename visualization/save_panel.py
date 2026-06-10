# visualization/save_panel.py
"""
SaveLoadPanel — overlay pygame pour gérer les sauvegardes.

Ouverture : touche S ou L dans la sim.
La sim se met en pause automatiquement à l'ouverture.

UI :
    ┌──────────────────────────────────┐
    │  SAVES                      [X]  │
    ├──────────────────────────────────┤
    │  quicksave   tick 1234  2026-01  │  ← clic = charger
    │  patrol_v2   tick 5678  2026-01  │
    │  ...                             │
    ├──────────────────────────────────┤
    │  [nom_______________]  [SAUVER]  │
    └──────────────────────────────────┘
"""

import json
import pygame
from pathlib import Path


SAVES_DIR = Path("data/saves")

# Palette
BG          = (12, 14, 20, 235)
BORDER      = (45, 55, 72)
HEADER_BG   = (18, 22, 32)
ROW_HOVER   = (30, 38, 55)
ROW_SEL     = (35, 55, 90)
TEXT        = (170, 180, 195)
TEXT_DIM    = (80,  90, 110)
TEXT_BRIGHT = (210, 220, 235)
ACCENT      = (70, 130, 200)
ACCENT_DIM  = (45,  80, 130)
BTN_BG      = (35,  50,  75)
BTN_HOVER   = (50,  75, 115)
CLOSE_COL   = (160,  60,  60)
INPUT_BG    = (18,  24,  36)
INPUT_BD    = (55,  70,  95)

W, H        = 440, 340
ROW_H       = 34
MAX_VISIBLE = 6
PAD         = 14


def _scan() -> list[dict]:
    """Scanne data/saves/*.json et retourne les métadonnées triées par date."""
    SAVES_DIR.mkdir(parents=True, exist_ok=True)
    saves = []
    for p in sorted(SAVES_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(p) as f:
                data = json.load(f)
            saves.append({
                "path":     p,
                "name":     p.stem,
                "tick":     data["meta"]["tick"],
                "date":     data["meta"]["saved_at"][:16].replace("T", " "),
            })
        except Exception:
            pass
    return saves


class SaveLoadPanel:

    def __init__(self) -> None:
        self.open      = False
        self.saves     = []
        self.scroll    = 0
        self.hovered   = -1
        self.name      = "quicksave"
        self.cursor    = len(self.name)
        self._was_paused = False
        self._row_rects  = []
        self._close_rect = pygame.Rect(0, 0, 0, 0)
        self._save_btn   = pygame.Rect(0, 0, 0, 0)
        self._input_rect = pygame.Rect(0, 0, 0, 0)



    # ── Ouverture / fermeture ─────────────────────────────────────────────────

    def show(self, sim_state: dict) -> None:
        self.open        = True
        self.saves       = _scan()
        self.scroll      = 0
        self._was_paused = sim_state["paused"]
        sim_state["paused"] = True

    def hide(self, sim_state: dict) -> None:
        self.open = False
        sim_state["paused"] = self._was_paused

    def toggle(self, sim_state: dict) -> None:
        if self.open:
            self.hide(sim_state)
        else:
            self.show(sim_state)

    # ── Rendu ─────────────────────────────────────────────────────────────────

    def draw(self, screen: pygame.Surface, font_sm: pygame.font.Font, font_med: pygame.font.Font) -> None:
        if not self.open:
            return

        sw, sh = screen.get_size()
        px     = sw // 2 - W // 2
        py     = sh // 2 - H // 2

        # fond principal
        panel = pygame.Surface((W, H), pygame.SRCALPHA)
        panel.fill(BG)
        pygame.draw.rect(panel, BORDER, (0, 0, W, H), 1)
        screen.blit(panel, (px, py))

        # ── header ───────────────────────────────────────────────────────────
        pygame.draw.rect(screen, HEADER_BG, (px, py, W, 36))
        pygame.draw.line(screen, BORDER, (px, py + 36), (px + W, py + 36), 1)

        t = font_med.render("SAUVEGARDES", True, TEXT_BRIGHT)
        screen.blit(t, (px + PAD, py + 36 // 2 - t.get_height() // 2))

        # bouton fermer
        self._close_rect = pygame.Rect(px + W - 30, py + 4, 26, 26)
        pygame.draw.rect(screen, (35, 18, 18), self._close_rect)
        pygame.draw.rect(screen, CLOSE_COL, self._close_rect, 1)
        x = font_med.render("✕", True, CLOSE_COL)
        screen.blit(x, (self._close_rect.centerx - x.get_width() // 2,
                        self._close_rect.centery - x.get_height() // 2))

        # ── liste des saves ───────────────────────────────────────────────────
        list_y  = py + 36 + 4
        visible = self.saves[self.scroll: self.scroll + MAX_VISIBLE]

        self._row_rects = []
        for i, s in enumerate(visible):
            ry   = list_y + i * ROW_H
            rect = pygame.Rect(px + 1, ry, W - 2, ROW_H)
            self._row_rects.append((rect, self.scroll + i))

            real_i = self.scroll + i
            col_bg = ROW_HOVER if real_i == self.hovered else HEADER_BG if i % 2 == 0 else None
            if col_bg:
                pygame.draw.rect(screen, col_bg, rect)

            name_surf = font_med.render(s["name"], True, TEXT_BRIGHT if real_i == self.hovered else TEXT)
            tick_surf = font_sm.render(f"tick {s['tick']:,}", True, TEXT_DIM)
            date_surf = font_sm.render(s["date"], True, TEXT_DIM)

            screen.blit(name_surf, (px + PAD, ry + ROW_H // 2 - name_surf.get_height() // 2))
            screen.blit(tick_surf, (px + 180, ry + ROW_H // 2 - tick_surf.get_height() // 2))
            screen.blit(date_surf, (px + W - PAD - date_surf.get_width(),
                                    ry + ROW_H // 2 - date_surf.get_height() // 2))

            pygame.draw.line(screen, BORDER,
                             (px, ry + ROW_H - 1), (px + W, ry + ROW_H - 1), 1)

        # placeholder si vide
        if not self.saves:
            msg = font_sm.render("Aucune sauvegarde", True, TEXT_DIM)
            screen.blit(msg, (px + W // 2 - msg.get_width() // 2,
                              list_y + MAX_VISIBLE * ROW_H // 2))

        # scrollbar
        total = len(self.saves)
        if total > MAX_VISIBLE:
            track_h  = MAX_VISIBLE * ROW_H
            thumb_h  = max(20, int(track_h * MAX_VISIBLE / total))
            thumb_y  = list_y + int(track_h * self.scroll / total)
            pygame.draw.rect(screen, BORDER, (px + W - 5, list_y, 4, track_h))
            pygame.draw.rect(screen, ACCENT_DIM, (px + W - 5, thumb_y, 4, thumb_h))

        # séparateur
        sep_y = list_y + MAX_VISIBLE * ROW_H + 6
        pygame.draw.line(screen, BORDER, (px, sep_y), (px + W, sep_y), 1)

        # ── zone de saisie + bouton save ──────────────────────────────────────
        input_y = sep_y + 8
        btn_w   = 90
        input_w = W - btn_w - PAD * 3

        # champ texte
        self._input_rect = pygame.Rect(px + PAD, input_y, input_w, 28)
        pygame.draw.rect(screen, INPUT_BG, self._input_rect)
        pygame.draw.rect(screen, INPUT_BD, self._input_rect, 1)

        # texte + curseur clignotant
        txt  = font_med.render(self.name, True, TEXT_BRIGHT)
        screen.blit(txt, (self._input_rect.x + 6, input_y + 28 // 2 - txt.get_height() // 2))
        if pygame.time.get_ticks() % 1000 < 550:
            cx = self._input_rect.x + 6 + txt.get_width() + 1
            cy = input_y + 4
            pygame.draw.line(screen, TEXT, (cx, cy), (cx, cy + 20), 1)

        # bouton SAUVER
        self._save_btn = pygame.Rect(px + PAD * 2 + input_w, input_y, btn_w, 28)
        mx, my = pygame.mouse.get_pos()
        btn_col = BTN_HOVER if self._save_btn.collidepoint(mx, my) else BTN_BG
        pygame.draw.rect(screen, btn_col, self._save_btn)
        pygame.draw.rect(screen, ACCENT, self._save_btn, 1)
        lbl = font_med.render("SAUVER", True, TEXT_BRIGHT)
        screen.blit(lbl, (self._save_btn.centerx - lbl.get_width() // 2,
                          self._save_btn.centery - lbl.get_height() // 2))

    # ── Gestion événements ────────────────────────────────────────────────────

    def handle_event(
        self,
        event: pygame.event.Event,
        sim_state: dict,
        world, scheduler, coverage,
    ) -> bool:
        """
        Traite un événement. Retourne True si l'événement est consommé
        (empêche le renderer de le traiter aussi).
        """
        if not self.open:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.hide(sim_state)
                return True
            if event.key == pygame.K_RETURN:
                self._do_save(world, scheduler, coverage)
                return True
            if event.key == pygame.K_BACKSPACE:
                self.name = self.name[:-1]
                return True
            if event.unicode and event.unicode.isprintable() and len(self.name) < 40:
                self.name += event.unicode
                return True
            return True   # absorbe toutes les touches quand le panel est ouvert

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if self._close_rect.collidepoint(mx, my):
                self.hide(sim_state)
                return True
            if self._save_btn.collidepoint(mx, my):
                self._do_save(world, scheduler, coverage)
                return True
            if self._input_rect.collidepoint(mx, my):
                return True
            for rect, idx in self._row_rects:
                if rect.collidepoint(mx, my) and idx < len(self.saves):
                    self._do_load(self.saves[idx]["path"], world, scheduler, coverage)
                    return True
            return True   # clic dans le panel mais hors éléments = absorbe quand même

        if event.type == pygame.MOUSEMOTION:
            self.hovered = -1
            for rect, idx in self._row_rects:
                if rect.collidepoint(event.pos):
                    self.hovered = idx
                    break

        if event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            sw, sh = pygame.display.get_surface().get_size()
            px     = sw // 2 - W // 2
            py     = sh // 2 - H // 2
            if pygame.Rect(px, py, W, H).collidepoint(mx, my):
                self.scroll = max(0, min(len(self.saves) - MAX_VISIBLE,
                                         self.scroll - event.y))
                return True

        return False

    # ── Actions ───────────────────────────────────────────────────────────────

    def _do_save(self, world, scheduler, coverage) -> None:
        if not self.name.strip():
            return
        from core.save_load import save
        path = SAVES_DIR / f"{self.name.strip()}.json"
        save(world, scheduler, coverage, path)
        self.saves = _scan()

    def _do_load(self, path: Path, world, scheduler, coverage) -> None:
        from core.save_load import load_state
        load_state(world, scheduler, coverage, path)
        self.saves = _scan()