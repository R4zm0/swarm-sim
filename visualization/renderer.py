# visualization/renderer.py
import pygame
import numpy as np
from core.world import World
FPS = 60
BG = (15, 15, 25)
DRONE_COLOR = (80, 200, 255)
DRONE_RADIUS = 6


def run(world: World, width: int = 800, height: int = 600) -> None:
    pygame.init()
    screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
    pygame.display.set_caption("swarm-sim")
    clock = pygame.time.Clock()

    # caméra : centre du monde visible + zoom
    zoom = 1.0
    cam_x = world.W / 2
    cam_y = world.H / 2

    dragging = False
    drag_last = (0, 0)

    def world_to_screen(wx, wy):
        sw = screen.get_width()
        sh = screen.get_height()
        sx = int((wx - cam_x) * zoom + sw / 2)
        sy = int((wy - cam_y) * zoom + sh / 2)
        return sx, sy

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:  # reset caméra
                    zoom = 1.0
                    cam_x = world.W / 2
                    cam_y = world.H / 2

            elif event.type == pygame.MOUSEWHEEL:
                # zoom centré sur la position souris
                mx, my = pygame.mouse.get_pos()
                sw, sh = screen.get_width(), screen.get_height()
                # position monde sous la souris avant zoom
                wx = (mx - sw / 2) / zoom + cam_x
                wy = (my - sh / 2) / zoom + cam_y
                zoom *= 1.1 if event.y > 0 else 0.9
                zoom = max(0.1, min(10.0, zoom))
                # repositionne la caméra pour garder le point fixe
                cam_x = wx - (mx - sw / 2) / zoom
                cam_y = wy - (my - sh / 2) / zoom

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button in (2, 3):  # clic milieu ou droit = pan
                    dragging = True
                    drag_last = event.pos

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button in (2, 3):
                    dragging = False

            elif event.type == pygame.MOUSEMOTION:
                if dragging:
                    dx = event.pos[0] - drag_last[0]
                    dy = event.pos[1] - drag_last[1]
                    cam_x -= dx / zoom
                    cam_y -= dy / zoom
                    drag_last = event.pos

        screen.fill(BG)

        for drone in world.drones.values():
            x, y = world_to_screen(drone.position[0], drone.position[1])
            pygame.draw.circle(screen, DRONE_COLOR, (x, y), DRONE_RADIUS)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()