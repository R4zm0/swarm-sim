# visualization/save_panel.py
"""
SavePanel  : panneau de sauvegarde  (touche S)
LoadPanel  : panneau de chargement  (touche L)

Deux panneaux distincts pour éviter les sauvegardes accidentelles.
Les saves sont filtrées par scénario courant.

Style :
    Fonds noirs opaques, texte blanc, police Arial.
    Bouton fermer Windows classique : carré gris avec un X noir.
"""

import pygame
from pathlib import Path
from core.save_load import save, load_state, scan_saves, saves_dir

# Palette
PANEL_BG    = (15, 15, 18)
HEADER_BG   = (35, 35, 45)
BORDER      = (220, 220, 230)
ROW_HOVER   = (45, 55, 75)
TEXT        = (235, 235, 240)
TEXT_DIM    = (140, 145, 155)
ACCENT      = (90, 150, 220)
BTN_SAVE    = (60, 130, 70)
BTN_SAVE_HV = (80, 170, 90)
INPUT_BG    = (25, 28, 35)
INPUT_BD    = (160, 170, 185)

# Bouton fermer Windows classique
CLOSE_BG       = (200, 200, 200)
CLOSE_BG_HV    = (235, 100, 100)
CLOSE_X        = (15, 15, 15)
CLOSE_X_HV     = (255, 255, 255)
CLOSE_W        = 24

W_SAVE, H_SAVE = 360, 130
W_LOAD, H_LOAD = 480, 340
ROW_H          = 36
MAX_VISIBLE    = 6
PAD            = 14


def _draw_close_button(surface, rect, mouse_pos) -> None:
    """Bouton fermer Windows classique : carré gris avec X noir."""
    hover = rect.collidepoint(mouse_pos)
    bg    = CLOSE_BG_HV if hover else CLOSE_BG
    fg    = CLOSE_X_HV  if hover else CLOSE_X
    pygame.draw.rect(surface, bg, rect)
    pygame.draw.rect(surface, (60, 60, 60), rect, 1)
    pad = 6
    pygame.draw.line(surface, fg, (rect.x + pad, rect.y + pad), (rect.right - pad, rect.bottom - pad), 2)
    pygame.draw.line(surface, fg, (rect.right - pad, rect.y + pad), (rect.x + pad, rect.bottom - pad), 2)


# ── Base ──────────────────────────────────────────────────────────────────────

class _BasePanel:
    def __init__(self):
        self.open        = False
        self._was_paused = False
        self._close_rect = pygame.Rect(0, 0, 0, 0)

    def show(self, sim_state):
        self.open            = True
        self._was_paused     = sim_state["paused"]
        sim_state["paused"]  = True

    def hide(self, sim_state):
        self.open            = False
        sim_state["paused"]  = self._was_paused

    def toggle(self, sim_state):
        if self.open:
            self.hide(sim_state)
        else:
            self.show(sim_state)

    def _draw_header(self, screen, px, py, w, title, font_med):
        pygame.draw.rect(screen, HEADER_BG, (px, py, w, 36))
        pygame.draw.line(screen, BORDER, (px, py + 36), (px + w, py + 36), 1)
        t = font_med.render(title, True, TEXT)
        screen.blit(t, (px + PAD, py + 18 - t.get_height() // 2))
        self._close_rect = pygame.Rect(px + w - CLOSE_W - 6, py + 6, CLOSE_W, CLOSE_W)
        _draw_close_button(screen, self._close_rect, pygame.mouse.get_pos())


# ── SAVE ──────────────────────────────────────────────────────────────────────

class SavePanel(_BasePanel):
    def __init__(self):
        super().__init__()
        self.name          = "quicksave"
        self._input_rect   = pygame.Rect(0, 0, 0, 0)
        self._save_btn     = pygame.Rect(0, 0, 0, 0)
        self.scenario_name = ""

    def draw(self, screen, font_sm, font_med):
        if not self.open:
            return
        sw, sh = screen.get_size()
        px = sw // 2 - W_SAVE // 2
        py = sh // 2 - H_SAVE // 2

        pygame.draw.rect(screen, PANEL_BG, (px, py, W_SAVE, H_SAVE))
        pygame.draw.rect(screen, BORDER,   (px, py, W_SAVE, H_SAVE), 1)

        self._draw_header(screen, px, py, W_SAVE, f"Sauvegarder  ,  {self.scenario_name}", font_med)

        # champ texte
        input_y = py + 56
        self._input_rect = pygame.Rect(px + PAD, input_y, W_SAVE - 120 - PAD * 2, 32)
        pygame.draw.rect(screen, INPUT_BG, self._input_rect)
        pygame.draw.rect(screen, INPUT_BD, self._input_rect, 1)
        txt = font_med.render(self.name, True, TEXT)
        screen.blit(txt, (self._input_rect.x + 8, input_y + 16 - txt.get_height() // 2))
        if pygame.time.get_ticks() % 1000 < 550:
            cx = self._input_rect.x + 8 + txt.get_width() + 1
            pygame.draw.line(screen, TEXT, (cx, input_y + 5), (cx, input_y + 27), 1)

        # bouton SAUVER
        self._save_btn = pygame.Rect(px + W_SAVE - 110 - PAD, input_y, 110, 32)
        mx, my = pygame.mouse.get_pos()
        bc = BTN_SAVE_HV if self._save_btn.collidepoint(mx, my) else BTN_SAVE
        pygame.draw.rect(screen, bc, self._save_btn)
        pygame.draw.rect(screen, BORDER, self._save_btn, 1)
        lbl = font_med.render("Sauvegarder", True, TEXT)
        screen.blit(lbl, (self._save_btn.centerx - lbl.get_width() // 2,
                          self._save_btn.centery - lbl.get_height() // 2))

    def handle_event(self, event, sim_state, world, scheduler, coverage):
        if not self.open:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.hide(sim_state); return True
            if event.key == pygame.K_RETURN:
                self._do_save(world, scheduler, coverage); return True
            if event.key == pygame.K_BACKSPACE:
                self.name = self.name[:-1]; return True
            if event.unicode and event.unicode.isprintable() and len(self.name) < 40:
                self.name += event.unicode; return True
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if self._close_rect.collidepoint(mx, my):
                self.hide(sim_state); return True
            if self._save_btn.collidepoint(mx, my):
                self._do_save(world, scheduler, coverage); return True
            return True
        return False

    def _do_save(self, world, scheduler, coverage):
        if not self.name.strip():
            return
        path = saves_dir(self.scenario_name) / f"{self.name.strip()}.json"
        save(world, scheduler, coverage, path)


# ── LOAD ──────────────────────────────────────────────────────────────────────

class LoadPanel(_BasePanel):
    def __init__(self):
        super().__init__()
        self.saves         = []
        self.scroll        = 0
        self.hovered       = -1
        self.scenario_name = ""
        self._row_rects    = []

    def show(self, sim_state):
        super().show(sim_state)
        self.saves  = scan_saves(self.scenario_name)
        self.scroll = 0

    def draw(self, screen, font_sm, font_med):
        if not self.open:
            return
        sw, sh = screen.get_size()
        px = sw // 2 - W_LOAD // 2
        py = sh // 2 - H_LOAD // 2

        pygame.draw.rect(screen, PANEL_BG, (px, py, W_LOAD, H_LOAD))
        pygame.draw.rect(screen, BORDER,   (px, py, W_LOAD, H_LOAD), 1)

        self._draw_header(screen, px, py, W_LOAD, f"Charger  ,  {self.scenario_name}", font_med)

        list_y  = py + 44
        visible = self.saves[self.scroll: self.scroll + MAX_VISIBLE]
        self._row_rects = []

        if not self.saves:
            msg = font_med.render("Aucune sauvegarde pour ce scénario.", True, TEXT_DIM)
            screen.blit(msg, (px + PAD, list_y + 40))
        else:
            for i, s in enumerate(visible):
                ry   = list_y + i * ROW_H
                rect = pygame.Rect(px + 1, ry, W_LOAD - 2, ROW_H)
                self._row_rects.append((rect, self.scroll + i))
                real_i = self.scroll + i
                if real_i == self.hovered:
                    pygame.draw.rect(screen, ROW_HOVER, rect)
                name_s = font_med.render(s["name"], True, TEXT)
                tick_s = font_sm.render(f"tick {s['tick']:,}", True, TEXT_DIM)
                date_s = font_sm.render(s["date"], True, TEXT_DIM)
                screen.blit(name_s, (px + PAD, ry + ROW_H // 2 - name_s.get_height() // 2))
                screen.blit(tick_s, (px + 230, ry + ROW_H // 2 - tick_s.get_height() // 2))
                screen.blit(date_s, (px + W_LOAD - PAD - date_s.get_width(),
                                     ry + ROW_H // 2 - date_s.get_height() // 2))
                pygame.draw.line(screen, (60, 65, 75), (px, ry + ROW_H - 1), (px + W_LOAD, ry + ROW_H - 1), 1)

            total = len(self.saves)
            if total > MAX_VISIBLE:
                track_h = MAX_VISIBLE * ROW_H
                thumb_h = max(20, int(track_h * MAX_VISIBLE / total))
                thumb_y = list_y + int(track_h * self.scroll / total)
                pygame.draw.rect(screen, (60, 65, 75), (px + W_LOAD - 5, list_y, 4, track_h))
                pygame.draw.rect(screen, BORDER,       (px + W_LOAD - 5, thumb_y, 4, thumb_h))

        hint = font_sm.render("Cliquez sur une sauvegarde pour charger.", True, TEXT_DIM)
        screen.blit(hint, (px + PAD, py + H_LOAD - hint.get_height() - 10))

    def handle_event(self, event, sim_state, world, scheduler, coverage):
        if not self.open:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.hide(sim_state); return True
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if self._close_rect.collidepoint(mx, my):
                self.hide(sim_state); return True
            for rect, idx in self._row_rects:
                if rect.collidepoint(mx, my) and idx < len(self.saves):
                    load_state(world, scheduler, coverage, self.saves[idx]["path"])
                    self.hide(sim_state); return True
            return True
        if event.type == pygame.MOUSEMOTION:
            self.hovered = -1
            for rect, idx in self._row_rects:
                if rect.collidepoint(event.pos):
                    self.hovered = idx
                    break
        if event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            sw, sh = pygame.display.get_surface().get_size()
            px, py = sw // 2 - W_LOAD // 2, sh // 2 - H_LOAD // 2
            if pygame.Rect(px, py, W_LOAD, H_LOAD).collidepoint(mx, my):
                self.scroll = max(0, min(len(self.saves) - MAX_VISIBLE, self.scroll - event.y))
                return True
        return False