import tkinter as tk

import pygame

import calcul as m
import engine as r


horloge = pygame.time.Clock()
cam = m.Camera(*r.ecran.get_size())

carte = None
seed = None
modeSelection = False
enSelection = False
panning = False
pansDeplace = False
pansDepuis = (0, 0)
debutSel = finSel = (0, 0)
selection = set()evendique = set()
marcher = True


def nouvelle():
    global carte, seed
    seed = m.nouvelleSeed()
    carte = m.genererCarte(seed)
    revendique.clear()
    selection.clear()


def copier():
    try:
        racine = tk.Tk()
        racine.withdraw()
        racine.clipboard_clear()
        racine.clipboard_append(str(seed))
        racine.update()
        racine.destroy()
    except Exception:
        pass


def basculer():
    global modeSelection, enSelection
    modeSelection = not modeSelection
    if not modeSelection:
        enSelection = False
        selection.clear()


def revendiquer():
    revendique.update({(l, c) for (l, c) in selection if carte[l][c] != "mer"})
    selection.clear()


def liberer():
    revendique.difference_update(selection)
    selection.clear()


def rectSel():
    (x1, y1), (x2, y2) = debutSel, finSel
    return pygame.Rect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))


def zoomCentre(sens):
    largeur, hauteur = r.ecran.get_size()
    cam.zoomer(sens, largeur / 2, hauteur / 2)


def touche(ev):
    k = ev.key
    x, y = pygame.mouse.get_pos()
    if k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
        cam.zoomer(1, x, y)
    elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
        cam.zoomer(-1, x, y)
    elif k == pygame.K_r:
        nouvelle()
    elif k == pygame.K_c:
        copier()
    elif k == pygame.K_s:
        basculer()
    elif k == pygame.K_v and selection:
        revendiquer()
    elif k == pygame.K_l and selection:
        liberer()
    elif k == pygame.K_ESCAPE:
        global marcher
        marcher = False


def traiter(ev):
    global enSelection, panning, pansDeplace, pansDepuis, debutSel, finSel, marcher
    if ev.type == pygame.QUIT:
        marcher = False
    elif ev.type == pygame.MOUSEWHEEL:
        cam.zoomer(ev.y, *pygame.mouse.get_pos())
    elif ev.type == pygame.MOUSEBUTTONDOWN:
        if ev.button == 1:
            if r.BOUTON_RESET.collidepoint(ev.pos):
                nouvelle()
            elif modeSelection:
                debutSel = finSel = ev.pos
                enSelection = True
            else:
                panning, pansDepuis, pansDeplace = True, ev.pos, False
        elif ev.button in (2, 3):
            panning, pansDepuis, pansDeplace = True, ev.pos, False
    elif ev.type == pygame.MOUSEMOTION:
        if enSelection:
            finSel = ev.pos
        elif panning:
            cam.glisser(*ev.rel)
            if abs(ev.pos[0] - pansDepuis[0]) + abs(ev.pos[1] - pansDepuis[1]) > m.SEUIL_CLIC:
                pansDeplace = True
    elif ev.type == pygame.MOUSEBUTTONUP and ev.button in (1, 2, 3):
        if enSelection:
            enSelection = False
            selection.clear()
            if abs(finSel[0] - debutSel[0]) + abs(finSel[1] - debutSel[1]) >= m.SEUIL_CLIC:
                selection.update(r.cellulesDansRect(cam, rectSel()))
        elif panning:
            panning = False
            if ev.button == 1 and not pansDeplace:
                cam.centrerSur(*ev.pos)
    elif ev.type == pygame.KEYDOWN:
        touche(ev)


def clavier():
    t = pygame.key.get_pressed()
    dx = (t[pygame.K_RIGHT] or t[pygame.K_d]) - (t[pygame.K_LEFT] or t[pygame.K_a] or t[pygame.K_q])
    dy = t[pygame.K_DOWN] - (t[pygame.K_UP] or t[pygame.K_w] or t[pygame.K_z])
    if dx or dy:
        cam.deplacer(dx, dy)


nouvelle()

while marcher:
    horloge.tick(60)
    for ev in pygame.event.get():
        traiter(ev)
    clavier()
    if pygame.mouse.get_focused() and not enSelection and not panning:
        cam.bord(*pygame.mouse.get_pos())
    cam.mettreAJour()

    apercu = r.cellulesDansRect(cam, rectSel()) if enSelection else set()
    r.ecran.fill("black")
    r.dessinerGrille(carte, cam, revendique, selection, apercu,
                     rectSel() if enSelection else None)
    pygame.display.flip()

pygame.quit()
