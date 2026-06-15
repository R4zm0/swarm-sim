# visualization/end_screen.py
"""
Écran de fin / pause-bilan de simulation.

Ouvert par main.py quand :
    - tous les drones sont morts        → sim_state["finished"]  (fin "naturelle")
    - l'utilisateur appuie sur F         → sim_state["show_end"]  (pause manuelle)

Actions, selon l'état du monde à l'ouverture :
    - drones encore vivants → champ de nom + ENREGISTRER, et bouton REPRENDRE
    - tous morts            → EXPORTER LES MÉTRIQUES (CSV, nom auto horodaté)
    dans les deux cas       → RETOUR AU MENU et QUITTER

show(...) renvoie : "resume" | "menu" | "quit".
    ("resume" n'est possible que s'il reste des drones vivants.)
"""

import pygame
from datetime import datetime

from core.save_load import save, saves_dir

# Palette (cohérente avec mission_select)
BG          = (10, 12, 18)
PANEL_BG    = (16, 20, 30)
BORDER      = (40, 50, 68)
TEXT        = (200, 208, 222)
TEXT_BRIGHT = (225, 232, 245)
TEXT_DIM    = (110, 120, 140)
ACCENT      = (80, 150, 235)
OK_GREEN    = (90, 200, 120)
ERR_RED     = (225, 90, 90)
BTN_BG      = (32, 44, 66)
BTN_HOVER   = (48, 72, 110)
BTN_RESUME  = (45, 95, 130)
BTN_RES_HV  = (60, 120, 165)
BTN_PRIMARY = (45, 120, 72)
BTN_PRIM_HV = (60, 150, 90)
BTN_QUIT    = (120, 45, 50)
BTN_QUIT_HV = (160, 60, 66)
INPUT_FOCUS = (40, 55, 80)

PANEL_W, PANEL_H = 460, 470
PAD = 24


def _button(screen, font, rect, label, base, hover, mx, my):
    col = hover if rect.collidepoint(mx, my) else base
    pygame.draw.rect(screen, col, rect, border_radius=6)
    pygame.draw.rect(screen, BORDER, rect, 1, border_radius=6)
    t = font.render(label, True, TEXT_BRIGHT)
    screen.blit(t, (rect.centerx - t.get_width() // 2, rect.centery - t.get_height() // 2))


def show(world, scheduler, coverage, logger, scenario_name: str = "run") -> str:
    # Réutilise la surface existante (le renderer ne quitte pas pygame).
    screen = pygame.display.get_surface()
    if screen is None:
        pygame.init()
        screen = pygame.display.set_mode((900, 600), pygame.RESIZABLE)
    clock = pygame.time.Clock()

    font_sm  = pygame.font.SysFont("Segoe UI,DejaVu Sans,Arial", 13)
    font_med = pygame.font.SysFont("Segoe UI,DejaVu Sans,Arial", 15)
    font_lg  = pygame.font.SysFont("Segoe UI,DejaVu Sans,Arial", 24, bold=True)

    finished = world.n_alive == 0
    summ     = logger.summary() if logger is not None else {"n_samples": 0}

    name      = f"fin_{datetime.now().strftime('%H%M%S')}"   # nom de save proposé
    status    = ""        # message après une action
    status_ok = True

    def do_save():
        nonlocal status, status_ok
        nm = name.strip()
        if not nm:
            status, status_ok = "nom vide", False
            return
        safe = nm.replace("/", "_").replace("\\", "_")
        path = saves_dir(scenario_name) / f"{safe}.json"
        save(world, scheduler, coverage, path)
        status, status_ok = f"partie enregistrée → {path}", True

    def do_export():
        nonlocal status, status_ok
        if logger is None or summ.get("n_samples", 0) == 0:
            status, status_ok = "aucune métrique à exporter", False
            return
        path = logger.to_csv(scenario_name=scenario_name)
        status, status_ok = f"métriques exportées → {path}", True

    while True:
        sw, sh = screen.get_size()
        mx, my = pygame.mouse.get_pos()

        px = sw // 2 - PANEL_W // 2
        py = sh // 2 - PANEL_H // 2
        bw = PANEL_W - 2 * PAD

        # Boutons empilés depuis le bas. "Reprendre" seulement si survivants.
        quit_rect    = pygame.Rect(px + PAD, py + PANEL_H - 54,  bw, 38)
        menu_rect    = pygame.Rect(px + PAD, py + PANEL_H - 100, bw, 38)
        primary_rect = pygame.Rect(px + PAD, py + PANEL_H - 146, bw, 38)
        resume_rect  = pygame.Rect(px + PAD, py + PANEL_H - 192, bw, 38) if not finished else None
        input_rect   = pygame.Rect(px + PAD, py + PANEL_H - 238, bw, 32) if not finished else None

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "quit"

            elif e.type == pygame.KEYDOWN:
                if not finished:
                    # le clavier alimente le champ de nom
                    if e.key == pygame.K_RETURN:
                        do_save()
                    elif e.key == pygame.K_ESCAPE:
                        return "resume"          # Échap = reprendre quand on peut
                    elif e.key == pygame.K_BACKSPACE:
                        name = name[:-1]
                    elif e.unicode and e.unicode.isprintable() and len(name) < 40:
                        name += e.unicode
                else:
                    if e.key == pygame.K_RETURN:
                        return "menu"
                    elif e.key == pygame.K_ESCAPE:
                        return "quit"

            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if resume_rect and resume_rect.collidepoint(mx, my):
                    return "resume"
                elif primary_rect.collidepoint(mx, my):
                    do_export() if finished else do_save()
                elif menu_rect.collidepoint(mx, my):
                    return "menu"
                elif quit_rect.collidepoint(mx, my):
                    return "quit"

        # ── Rendu ──────────────────────────────────────────────────────────────
        screen.fill(BG)
        pygame.draw.rect(screen, PANEL_BG, (px, py, PANEL_W, PANEL_H), border_radius=10)
        pygame.draw.rect(screen, BORDER,   (px, py, PANEL_W, PANEL_H), 1, border_radius=10)

        title = "SIMULATION TERMINÉE" if finished else "SIMULATION EN PAUSE"
        tcol  = OK_GREEN if finished else ACCENT
        t = font_lg.render(title, True, tcol)
        screen.blit(t, (px + PANEL_W // 2 - t.get_width() // 2, py + PAD))

        sub = "tous les drones sont morts" if finished else f"{world.n_alive} drone(s) encore en vol"
        s = font_sm.render(sub, True, TEXT_DIM)
        screen.blit(s, (px + PANEL_W // 2 - s.get_width() // 2, py + PAD + 34))

        # Bilan
        y = py + PAD + 64
        lines = [f"tick final : {scheduler.tick_count:,}"]
        if summ.get("n_samples", 0) > 0:
            lines += [
                f"couverture moyenne : {summ['ratio_mean'] * 100:.1f} %",
                f"couverture min / max : {summ['ratio_min'] * 100:.1f} %  /  {summ['ratio_max'] * 100:.1f} %",
                f"trou max : {summ['gap_max'] * 100:.1f} %",
                f"échantillons : {summ['n_samples']}",
            ]
        else:
            lines += ["(pas de métriques de couverture)"]
        for line in lines:
            screen.blit(font_med.render(line, True, TEXT), (px + PAD, y))
            y += 23

        # Champ de nom (mode save uniquement)
        if not finished:
            lbl = font_sm.render("Nom de la sauvegarde :", True, ACCENT)
            screen.blit(lbl, (input_rect.x, input_rect.y - 18))
            pygame.draw.rect(screen, INPUT_FOCUS, input_rect, border_radius=4)
            pygame.draw.rect(screen, ACCENT, input_rect, 1, border_radius=4)
            txt = font_med.render(name, True, TEXT_BRIGHT)
            screen.blit(txt, (input_rect.x + 8, input_rect.centery - txt.get_height() // 2))
            if pygame.time.get_ticks() % 1000 < 550:
                cx = input_rect.x + 8 + txt.get_width() + 1
                pygame.draw.line(screen, TEXT_BRIGHT, (cx, input_rect.y + 6), (cx, input_rect.bottom - 6), 1)

        # Boutons
        if resume_rect:
            _button(screen, font_med, resume_rect, "Reprendre  (Échap)", BTN_RESUME, BTN_RES_HV, mx, my)
        if finished:
            _button(screen, font_med, primary_rect, "Exporter les métriques (CSV)", BTN_PRIMARY, BTN_PRIM_HV, mx, my)
        else:
            _button(screen, font_med, primary_rect, "Enregistrer la partie", BTN_PRIMARY, BTN_PRIM_HV, mx, my)
        _button(screen, font_med, menu_rect, "Retour au menu", BTN_BG, BTN_HOVER, mx, my)
        _button(screen, font_med, quit_rect, "Quitter", BTN_QUIT, BTN_QUIT_HV, mx, my)

        if status:
            col = OK_GREEN if status_ok else ERR_RED
            st = font_sm.render(status, True, col)
            screen.blit(st, (sw // 2 - st.get_width() // 2, py + PANEL_H + 14))

        pygame.display.flip()
        clock.tick(60)