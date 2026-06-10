# visualization/mission_select.py
"""
Écran de sélection de mission — affiché au lancement avant la sim.

Deux colonnes :
    Nouvelle mission  — charge un scénario JSON depuis data/scenarios/
    Reprendre         — charge un scénario + restaure un save depuis data/saves/

Retourne un dict :
    {
        "world":            World,
        "zone":             PatrolZone,
        "coverage":         CoverageMap,
        "scenario_path":    Path,
        "save_to_restore":  Path | None,
    }
Retourne None si l'utilisateur ferme la fenêtre.
"""

import json
import pygame
from pathlib import Path

SCENARIOS_DIR = Path("data/scenarios")
SAVES_DIR     = Path("data/saves")

# Palette identique au renderer
BG           = (10, 12, 18)
PANEL_BG     = (14, 17, 25)
BORDER       = (40, 50, 68)
HEADER       = (18, 22, 32)
TEXT         = (160, 170, 185)
TEXT_BRIGHT  = (210, 220, 235)
TEXT_DIM     = (75,  85, 105)
ACCENT       = (65, 125, 195)
ACCENT_DIM   = (40,  75, 125)
ROW_HOVER    = (28,  36,  54)
ROW_SEL      = (32,  52,  88)
BTN_BG       = (32,  48,  75)
BTN_HOVER    = (48,  75, 118)
BTN_START    = (38,  90,  55)
BTN_START_HV = (55, 130,  80)

ROW_H = 52
PAD   = 16


def _scan_scenarios() -> list[dict]:
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(SCENARIOS_DIR.glob("*.json")):
        try:
            with open(p) as f:
                d = json.load(f)
            out.append({
                "path":        p,
                "name":        d.get("name", p.stem),
                "description": d.get("description", ""),
                "n_drones":    len(d.get("drones", [])),
                "n_enemies":   len(d.get("enemies", [])),
            })
        except Exception:
            pass
    return out


def _scan_saves() -> list[dict]:
    SAVES_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(SAVES_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(p) as f:
                d = json.load(f)
            out.append({
                "path":     p,
                "name":     p.stem,
                "tick":     d["meta"]["tick"],
                "date":     d["meta"]["saved_at"][:16].replace("T", " "),
            })
        except Exception:
            pass
    return out


def run_select(width: int = 900, height: int = 560) -> dict | None:
    """
    Affiche l'écran de sélection. Bloquant jusqu'à la sélection ou fermeture.
    """
    pygame.init()
    screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
    pygame.display.set_caption("swarm-sim")
    clock  = pygame.font.init() or pygame.time.Clock()
    clock  = pygame.time.Clock()

    font_sm  = pygame.font.SysFont("Courier New", 11)
    font_med = pygame.font.SysFont("Courier New", 13)
    font_lg  = pygame.font.SysFont("Courier New", 17, bold=True)

    scenarios = _scan_scenarios()
    saves     = _scan_saves()

    sel_scenario = 0 if scenarios else -1
    sel_save     = -1   # -1 = pas de save sélectionné (nouvelle partie)
    hover_sc     = -1
    hover_sv     = -1

    def _draw_row(surface, rect, text_main, text_sub, selected, hovered, font_m, font_s):
        col = ROW_SEL if selected else ROW_HOVER if hovered else None
        if col:
            pygame.draw.rect(surface, col, rect)
        t1 = font_m.render(text_main, True, TEXT_BRIGHT if selected else TEXT)
        t2 = font_s.render(text_sub,  True, ACCENT if selected else TEXT_DIM)
        surface.blit(t1, (rect.x + PAD, rect.y + 8))
        surface.blit(t2, (rect.x + PAD, rect.y + 8 + t1.get_height() + 2))
        pygame.draw.line(surface, BORDER, (rect.x, rect.bottom - 1), (rect.right, rect.bottom - 1), 1)

    running = True
    result  = None

    while running:
        sw, sh = screen.get_size()
        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_RETURN and sel_scenario >= 0:
                    result  = _build_result(scenarios[sel_scenario], saves, sel_save)
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # scénarios
                for i, rect in enumerate(sc_rects):
                    if rect.collidepoint(mx, my):
                        sel_scenario = i
                        sel_save     = -1

                # saves
                for i, rect in enumerate(sv_rects):
                    if rect.collidepoint(mx, my):
                        sel_save = i

                # bouton démarrer
                if btn_rect.collidepoint(mx, my) and sel_scenario >= 0:
                    result  = _build_result(scenarios[sel_scenario], saves, sel_save)
                    running = False

        # ── Rendu ─────────────────────────────────────────────────────────────
        screen.fill(BG)

        col_w    = sw // 2 - PAD
        top_y    = 70
        list_h   = sh - top_y - 80

        # ── titre ─────────────────────────────────────────────────────────────
        title = font_lg.render("SWARM-SIM", True, TEXT_BRIGHT)
        sub   = font_sm.render("Sélectionnez une mission", True, TEXT_DIM)
        screen.blit(title, (sw // 2 - title.get_width() // 2, 16))
        screen.blit(sub,   (sw // 2 - sub.get_width() // 2,   16 + title.get_height() + 4))

        # ── colonne gauche — scénarios ────────────────────────────────────────
        lx  = PAD
        hdr = font_med.render("NOUVELLE MISSION", True, ACCENT)
        screen.blit(hdr, (lx, top_y - 22))
        pygame.draw.line(screen, ACCENT_DIM, (lx, top_y - 6), (lx + col_w - PAD, top_y - 6), 1)

        panel_sc = pygame.Surface((col_w - PAD, list_h), pygame.SRCALPHA)
        panel_sc.fill((*PANEL_BG, 220))
        pygame.draw.rect(panel_sc, BORDER, (0, 0, col_w - PAD, list_h), 1)
        screen.blit(panel_sc, (lx, top_y))

        sc_rects = []
        hover_sc = -1
        for i, sc in enumerate(scenarios):
            rect = pygame.Rect(lx, top_y + i * ROW_H, col_w - PAD, ROW_H)
            sc_rects.append(rect)
            if rect.collidepoint(mx, my):
                hover_sc = i
            sub_txt = f"{sc['n_drones']} drones · {sc['n_enemies']} ennemis — {sc['description'][:35]}"
            _draw_row(screen, rect, sc["name"], sub_txt, i == sel_scenario, i == hover_sc, font_med, font_sm)

        if not scenarios:
            msg = font_sm.render("Aucun scénario dans data/scenarios/", True, TEXT_DIM)
            screen.blit(msg, (lx + PAD, top_y + list_h // 2))

        # ── colonne droite — saves ────────────────────────────────────────────
        rx  = sw // 2 + PAD
        hdr = font_med.render("REPRENDRE", True, ACCENT)
        screen.blit(hdr, (rx, top_y - 22))
        pygame.draw.line(screen, ACCENT_DIM, (rx, top_y - 6), (rx + col_w - PAD, top_y - 6), 1)

        panel_sv = pygame.Surface((col_w - PAD, list_h), pygame.SRCALPHA)
        panel_sv.fill((*PANEL_BG, 220))
        pygame.draw.rect(panel_sv, BORDER, (0, 0, col_w - PAD, list_h), 1)
        screen.blit(panel_sv, (rx, top_y))

        sv_rects = []
        hover_sv = -1
        for i, sv in enumerate(saves):
            rect = pygame.Rect(rx, top_y + i * ROW_H, col_w - PAD, ROW_H)
            sv_rects.append(rect)
            if rect.collidepoint(mx, my):
                hover_sv = i
            sub_txt = f"tick {sv['tick']:,} · {sv['date']}"
            _draw_row(screen, rect, sv["name"], sub_txt, i == sel_save, i == hover_sv, font_med, font_sm)

        if not saves:
            msg = font_sm.render("Aucune sauvegarde", True, TEXT_DIM)
            screen.blit(msg, (rx + PAD, top_y + list_h // 2))

        # ── hint save sélectionné ─────────────────────────────────────────────
        if sel_save >= 0:
            hint = font_sm.render(
                f"Reprendre : {saves[sel_save]['name']}  —  cliquez sur un scénario pour continuer",
                True, (120, 160, 100),
            )
            screen.blit(hint, (PAD, sh - 60))

        # ── bouton démarrer ───────────────────────────────────────────────────
        btn_w    = 160
        btn_h    = 36
        btn_rect = pygame.Rect(sw // 2 - btn_w // 2, sh - btn_h - 12, btn_w, btn_h)
        bc = BTN_START_HV if btn_rect.collidepoint(mx, my) else BTN_START
        if sel_scenario < 0:
            bc = (30, 35, 42)
        pygame.draw.rect(screen, bc, btn_rect)
        pygame.draw.rect(screen, (60, 130, 80) if sel_scenario >= 0 else BORDER, btn_rect, 1)
        lbl = font_med.render("DÉMARRER  ▶", True, TEXT_BRIGHT if sel_scenario >= 0 else TEXT_DIM)
        screen.blit(lbl, (btn_rect.centerx - lbl.get_width() // 2,
                           btn_rect.centery - lbl.get_height() // 2))

        pygame.display.flip()
        clock.tick(60)

    return result


def _build_result(scenario: dict, saves: list, sel_save: int) -> dict:
    """Charge le monde depuis le scénario sélectionné."""
    from core.scenario_loader import load
    world, zone, coverage = load(scenario["path"])
    return {
        "world":           world,
        "zone":            zone,
        "coverage":        coverage,
        "scenario_path":   scenario["path"],
        "save_to_restore": saves[sel_save]["path"] if sel_save >= 0 else None,
    }