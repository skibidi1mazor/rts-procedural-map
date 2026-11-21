import math
import random
from collections import deque

import pygame


# ---------- Réglages ----------
LIGNES, COLONNES = 500, 500
AIRE = LIGNES * COLONNES
SEED = 7379338383                      # None = aléatoire ; un nombre = carte fixe
PART_MER = 0.55
ILE_MIN = AIRE // 300
NB_RIVIERES = 150
SEUIL_SOURCE = 0.6
RAYON = 40
LARGEUR_HEX = math.sqrt(3) * RAYON
HAUTEUR_HEX = 1.5 * RAYON
VITESSE, VITESSE_BORD, MARGE_BORD = 10, 12, 25
LISSAGE = 0.15
ZOOM_MIN, ZOOM_MAX, ZOOM_PAS = 0.05, 3.0, 1.15
TAILLE_MIN_HEX = 4               # taille minimale (px) d'une case à l'écran
FACTEUR_MAX = 32
SEUIL_CLIC = 5
DELTAS_PAIR = ((-1, -1), (-1, 0), (1, -1), (1, 0), (0, -1), (0, 1))
DELTAS_IMPAIR = ((-1, 0), (-1, 1), (1, 0), (1, 1), (0, -1), (0, 1))

COULEURS = {
    "mer": (30, 90, 160),
    "plage": (235, 215, 150),
    "desert": (220, 190, 110),
    "plaine": (150, 190, 80),
    "foret": (40, 120, 50),
    "terre": (140, 100, 60),
    "pierre": (120, 120, 125),
    "montagne": (90, 90, 95),
    "neige": (240, 240, 245),
    "riviere": (60, 150, 230),
}


# ---------- Grille ----------
def voisins(l, c):
    deltas = DELTAS_PAIR if l % 2 == 0 else DELTAS_IMPAIR
    return [(l + dl, c + dc) for dl, dc in deltas
            if 0 <= l + dl < LIGNES and 0 <= c + dc < COLONNES]


def zones(ensemble):
    restantes, resultat = set(ensemble), []
    while restantes:
        depart = restantes.pop()
        zone, file = [depart], deque([depart])
        while file:
            for v in voisins(*file.popleft()):
                if v in restantes:
                    restantes.remove(v)
                    zone.append(v)
                    file.append(v)
        resultat.append(zone)
    return resultat


def normaliser(grille):
    plat = [v for ligne in grille for v in ligne]
    mini, maxi = min(plat), max(plat)
    etendue = (maxi - mini) or 1
    return [[(v - mini) / etendue for v in ligne] for ligne in grille]


# ---------- Génération ----------
def bruit(echelle, octaves):
    """Bruit lissé multi-échelles : grandes formes d'abord, détails ensuite."""
    total = [[0.0] * COLONNES for _ in range(LIGNES)]
    amplitude = 1.0
    for _ in range(octaves):
        e = max(1.0, echelle)
        g = [[random.random() for _ in range(int(COLONNES / e) + 2)]
             for _ in range(int(LIGNES / e) + 2)]
        for l in range(LIGNES):
            for c in range(COLONNES):
                y, x = l / e, c / e
                y0, x0 = int(y), int(x)
                fy, fx = y - y0, x - x0
                sy, sx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
                haut = g[y0][x0] + (g[y0][x0 + 1] - g[y0][x0]) * sx
                bas = g[y0 + 1][x0] + (g[y0 + 1][x0 + 1] - g[y0 + 1][x0]) * sx
                total[l][c] += amplitude * (haut + (bas - haut) * sy)
        amplitude /= 2
        echelle /= 2
    return normaliser(total)


def masqueIle():
    return [[max(0.0, 1 - ((c - COLONNES / 2) / (COLONNES / 2)) ** 2
                       - ((l - LIGNES / 2) / (LIGNES / 2)) ** 2)
             for c in range(COLONNES)] for l in range(LIGNES)]


def genererEau(altitude, seuil):
    """La mer est l'eau reliée au bord. Les petites terres isolées deviennent de la mer."""
    basse = {(l, c) for l in range(LIGNES) for c in range(COLONNES) if altitude[l][c] < seuil}
    ocean = {(l, c) for (l, c) in basse if l in (0, LIGNES - 1) or c in (0, COLONNES - 1)}
    file = deque(ocean)
    while file:
        for v in voisins(*file.popleft()):
            if v in basse and v not in ocean:
                ocean.add(v)
                file.append(v)
    toutes = {(l, c) for l in range(LIGNES) for c in range(COLONNES)}
    for zone in zones(toutes - ocean):
        if len(zone) < ILE_MIN:
            ocean.update(zone)
    return [[(l, c) in ocean for c in range(COLONNES)] for l in range(LIGNES)]


def biomeTerre(hauteur, humidite):
    if hauteur < 0.45:
        return "desert" if humidite < 0.30 else "plaine" if humidite < 0.55 else "foret"
    if hauteur < 0.75:
        return "terre" if humidite < 0.40 else "foret" if humidite < 0.80 else "plaine"
    if hauteur < 0.90:
        return "pierre" if humidite < 0.40 else "montagne"
    return "neige"


def lisser(carte, eau, passes=2):
    for _ in range(passes):
        nouvelle = [ligne[:] for ligne in carte]
        for l in range(LIGNES):
            for c in range(COLONNES):
                if eau[l][c]:
                    continue
                compte = {}
                for nl, nc in voisins(l, c):
                    if not eau[nl][nc]:
                        compte[carte[nl][nc]] = compte.get(carte[nl][nc], 0) + 1
                if compte:
                    biome, nb = max(compte.items(), key=lambda kv: kv[1])
                    if nb >= 4:
                        nouvelle[l][c] = biome
        carte = nouvelle
    return carte


def poserPlages(carte, eau, hauteurs):
    for l in range(LIGNES):
        for c in range(COLONNES):
            if not eau[l][c] and hauteurs[l][c] < 0.05:
                if any(eau[a][b] for a, b in voisins(l, c)):
                    carte[l][c] = "plage"


def descendre(depart, altitude, eau):
    """Suit la pente vers la mer. Renvoie None si la rivière se bloque."""
    chemin, (l, c) = [depart], depart
    while True:
        nl, nc = min(voisins(l, c), key=lambda v: altitude[v[0]][v[1]])
        if eau[nl][nc]:
            return chemin
        if altitude[nl][nc] >= altitude[l][c]:
            return None
        chemin.append((nl, nc))
        l, c = nl, nc


def creerRivieres(carte, altitude, eau, hauteurs):
    sources = [(l, c) for l in range(LIGNES) for c in range(COLONNES)
               if not eau[l][c] and hauteurs[l][c] > SEUIL_SOURCE]
    if not sources:
        return
    for _ in range(NB_RIVIERES):
        for l, c in descendre(random.choice(sources), altitude, eau) or []:
            carte[l][c] = "riviere"


def nouvelleSeed():
    return SEED if SEED is not None else random.randrange(1, 10 ** 9)


def genererCarte(seed):
    random.seed(seed)
    relief = bruit(COLONNES / 4, 5)
    detail = bruit(COLONNES / 12, 3)
    masque = masqueIle()
    altitude = normaliser([[0.55 * relief[l][c] + 0.15 * detail[l][c] + 0.30 * masque[l][c]
                            for c in range(COLONNES)] for l in range(LIGNES)])
    seuil = sorted(v for ligne in altitude for v in ligne)[int(PART_MER * AIRE)]
    hauteurs = [[max(0.0, (altitude[l][c] - seuil) / (1 - seuil)) for c in range(COLONNES)]
                for l in range(LIGNES)]
    eau = genererEau(altitude, seuil)
    humidite = bruit(COLONNES / 6, 4)
    carte = [["mer" if eau[l][c] else biomeTerre(hauteurs[l][c], humidite[l][c])
              for c in range(COLONNES)] for l in range(LIGNES)]
    carte = lisser(carte, eau)
    poserPlages(carte, eau, hauteurs)
    creerRivieres(carte, altitude, eau, hauteurs)
    return carte


# ---------- Caméra ----------
class Camera:
    def __init__(self, largeur, hauteur):
        self.largeur, self.hauteur = largeur, hauteur
        self.x = self.y = self.xc = self.yc = 0.0
        self.zoom = self.zc = 1.0

    def centre(self, l, c):
        decalage = LARGEUR_HEX / 2 if l % 2 else 0
        x = c * LARGEUR_HEX + decalage
        y = l * HAUTEUR_HEX + RAYON
        return x, y

    def ecran(self, l, c):
        x, y = self.centre(l, c)
        return (x - self.x) * self.zoom, (y - self.y) * self.zoom

    def plage(self):
        l0 = max(0, int(self.y / HAUTEUR_HEX) - 1)
        l1 = min(LIGNES, int((self.y + self.hauteur / self.zoom) / HAUTEUR_HEX) + 2)
        c0 = max(0, int(self.x / LARGEUR_HEX) - 1)
        c1 = min(COLONNES, int((self.x + self.largeur / self.zoom) / LARGEUR_HEX) + 2)
        return l0, l1, c0, c1

    def caseSous(self, px, py):
        wx, wy = px / self.zoom + self.x, py / self.zoom + self.y
        l0 = round((wy - RAYON) / HAUTEUR_HEX)
        meilleur, dmin = None, float("inf")
        for l in range(l0 - 1, l0 + 2):
            if not 0 <= l < LIGNES:
                continue
            c0 = round((wx - (LARGEUR_HEX / 2 if l % 2 else 0)) / LARGEUR_HEX)
            for c in range(c0 - 1, c0 + 2):
                if 0 <= c < COLONNES:
                    x, y = self.centre(l, c)
                    d = (x - wx) ** 2 + (y - wy) ** 2
                    if d < dmin:
                        meilleur, dmin = (l, c), d
        return meilleur

    def limiter(self):
        maxX = max(0, COLONNES * LARGEUR_HEX + LARGEUR_HEX / 2 - self.largeur / self.zc)
        maxY = max(0, LIGNES * HAUTEUR_HEX + RAYON - self.hauteur / self.zc)
        self.xc = max(0, min(self.xc, maxX))
        self.yc = max(0, min(self.yc, maxY))

    def mettreAJour(self):
        self.zoom += (self.zc - self.zoom) * LISSAGE
        self.x += (self.xc - self.x) * LISSAGE
        self.y += (self.yc - self.y) * LISSAGE

    def zoomer(self, sens, px, py):
        mx, my = px / self.zoom + self.x, py / self.zoom + self.y
        self.zc = max(ZOOM_MIN, min(ZOOM_MAX, self.zc * ZOOM_PAS ** sens))
        self.xc = mx - px / self.zc
        self.yc = my - py / self.zc
        self.limiter()

    def cibler(self, x, y):
        self.xc = x - self.largeur / (2 * self.zc)
        self.yc = y - self.hauteur / (2 * self.zc)
        self.limiter()

    def centrerSur(self, px, py):
        case = self.caseSous(px, py)
        if case:
            self.cibler(*self.centre(*case))

    def glisser(self, dx, dy):
        self.x -= dx / self.zoom
        self.y -= dy / self.zoom
        self.xc, self.yc = self.x, self.y
        self.limiter()

    def deplacer(self, dx, dy):
        pas = VITESSE / self.zc
        self.xc += pas * dx
        self.yc += pas * dy
        self.limiter()

    def bord(self, x, y):
        p = VITESSE_BORD / self.zc
        self.xc += p * ((x > self.largeur - MARGE_BORD) - (x < MARGE_BORD))
        self.yc += p * ((y > self.hauteur - MARGE_BORD) - (y < MARGE_BORD))
        self.limiter()


# ---------- Mipmaps ----------
def reduire(niveau):
    nl, nc = len(niveau), len(niveau[0])
    resultat = []
    for L in range(0, nl, 2):
        ligne = []
        for C in range(0, nc, 2):
            bloc = [niveau[l][c]
                    for l in range(L, min(L + 2, nl))
                    for c in range(C, min(C + 2, nc))]
            ligne.append("riviere" if "riviere" in bloc else max(set(bloc), key=bloc.count))
        resultat.append(ligne)
    return resultat


def preparerMipmaps(carte):
    niveaux = {1: carte}
    f = 1
    while f < FACTEUR_MAX:
        niveaux[f * 2] = reduire(niveaux[f])
        f *= 2
    return niveaux


def facteurPourZoom(zoom):
    f = 1
    while f < FACTEUR_MAX and RAYON * f * zoom < TAILLE_MIN_HEX:
        f *= 2
    return f


# ---------- Rendu ----------
def dessinerDetail(surf, cam, carte):
    l0, l1, c0, c1 = cam.plage()
    r = RAYON * cam.zoom
    offsets = [(r * math.cos(math.radians(30 + 60 * k)),
                r * math.sin(math.radians(30 + 60 * k))) for k in range(6)]
    for l in range(l0, l1):
        for c in range(c0, c1):
            x, y = cam.ecran(l, c)
            pts = [(x + dx, y + dy) for dx, dy in offsets]
            pygame.draw.polygon(surf, COULEURS[carte[l][c]], pts)


def dessinerMip(surf, cam, grille, f):
    l0, l1, c0, c1 = cam.plage()
    m0, m1 = max(0, l0 // f), min(len(grille), l1 // f + 1)
    n0, n1 = max(0, c0 // f), min(len(grille[0]), c1 // f + 1)
    w = math.ceil(f * LARGEUR_HEX * cam.zoom) + 1
    h = math.ceil(f * HAUTEUR_HEX * cam.zoom) + 1
    for L in range(m0, m1):
        for C in range(n0, n1):
            x = (C * f * LARGEUR_HEX - cam.x) * cam.zoom
            y = (L * f * HAUTEUR_HEX - cam.y) * cam.zoom
            pygame.draw.rect(surf, COULEURS[grille[L][C]], (int(x), int(y), w, h))


def dessiner(surf, cam, carte, mipmaps):
    surf.fill((0, 0, 0))
    f = facteurPourZoom(cam.zoom)
    dessinerDetail(surf, cam, carte) if f == 1 else dessinerMip(surf, cam, mipmaps[f], f)


# ---------- Programme principal ----------
def main():
    pygame.init()
    ecran = pygame.display.set_mode((1280, 800), pygame.RESIZABLE)
    pygame.display.set_caption("Carte hexagonale")
    horloge = pygame.time.Clock()

    seed = nouvelleSeed()
    print("Seed :", seed)
    print("Génération de la carte...")
    carte = genererCarte(seed)
    mipmaps = preparerMipmaps(carte)
    print("Prêt.")

    largeur, hauteur = ecran.get_size()
    cam = Camera(largeur, hauteur)
    cam.cibler(COLONNES * LARGEUR_HEX / 2, LIGNES * HAUTEUR_HEX / 2)
    cam.x, cam.y = cam.xc, cam.yc

    glisse = False
    dernier = (0, 0)
    distance = 0

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                return
            elif ev.type == pygame.VIDEORESIZE:
                cam.largeur, cam.hauteur = ev.w, ev.h
                ecran = pygame.display.set_mode((ev.w, ev.h), pygame.RESIZABLE)
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                if ev.button == 4:
                    cam.zoomer(1, *ev.pos)
                elif ev.button == 5:
                    cam.zoomer(-1, *ev.pos)
                elif ev.button == 1:
                    glisse, dernier, distance = True, ev.pos, 0
            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                glisse = False
                if distance < SEUIL_CLIC:
                    cam.centrerSur(*ev.pos)
            elif ev.type == pygame.MOUSEMOTION and glisse:
                dx, dy = ev.pos[0] - dernier[0], ev.pos[1] - dernier[1]
                dernier = ev.pos
                distance += abs(dx) + abs(dy)
                cam.glisser(dx, dy)

        touches = pygame.key.get_pressed()
        dx = int(touches[pygame.K_RIGHT]) - int(touches[pygame.K_LEFT])
        dy = int(touches[pygame.K_DOWN]) - int(touches[pygame.K_UP])
        if dx or dy:
            cam.deplacer(dx, dy)
        if not glisse and pygame.mouse.get_focused():
            cam.bord(*pygame.mouse.get_pos())

        cam.mettreAJour()
        dessiner(ecran, cam, carte, mipmaps)
        pygame.display.flip()
        horloge.tick(60)


if __name__ == "__main__":
    main()
