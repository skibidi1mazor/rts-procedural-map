import math
import random
from collections import deque

import pygame


# ---------- Réglages ----------
MapLignes, MapColonnes = 200, 280
Aire = MapLignes * MapColonnes
Seed = None
PartMer = 0.55
TailleIleMin = Aire // 300
NbRivieres = 150
SeuilSource = 0.6

Fenetre = (1280, 800)
Rayon = 40
LargeurHex = math.sqrt(3) * Rayon
HauteurHex = 1.5 * Rayon
Vitesse, VitesseBord, MargeBord = 10, 12, 25
Lissage = 0.15
ZoomMin, ZoomMax, ZoomPas = 0.3, 3.0, 1.15
SeuilClic = 5

Couleurs = {
    "mer": (30, 90, 160), "riviere": (60, 130, 200), "plage": (238, 220, 165),
    "desert": (226, 196, 128), "terre": (160, 120, 72), "plaine": (140, 178, 80),
    "foret": (46, 96, 48), "pierre": (138, 134, 128), "montagne": (110, 104, 98),
    "neige": (245, 247, 250),
}
DeltasPair = ((-1, -1), (-1, 0), (1, -1), (1, 0), (0, -1), (0, 1))
DeltasImpair = ((-1, 0), (-1, 1), (1, 0), (1, 1), (0, -1), (0, 1))

pygame.init()
ecran = pygame.display.set_mode(Fenetre)
pygame.display.set_caption("Mini RTS")
police = pygame.font.SysFont(None, 26)
Temps = pygame.time.Clock()

seedActuelle = None
carte = None


def voisins(l, c):
    deltas = DeltasPair if l % 2 == 0 else DeltasImpair
    return [(l + dl, c + dc) for dl, dc in deltas
            if 0 <= l + dl < MapLignes and 0 <= c + dc < MapColonnes]


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


def bruit(echelle, octaves):
    total = [[0.0] * MapColonnes for _ in range(MapLignes)]
    amplitude = 1.0
    for _ in range(octaves):
        e = max(1.0, echelle)
        g = [[random.random() for _ in range(int(MapColonnes / e) + 2)]
             for _ in range(int(MapLignes / e) + 2)]
        for l in range(MapLignes):
            for c in range(MapColonnes):
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
    return [[max(0.0, 1 - ((c - MapColonnes / 2) / (MapColonnes / 2)) ** 2
                       - ((l - MapLignes / 2) / (MapLignes / 2)) ** 2)
             for c in range(MapColonnes)] for l in range(MapLignes)]


def genererEau(altitude, seuil):
    basse = {(l, c) for l in range(MapLignes) for c in range(MapColonnes)
             if altitude[l][c] < seuil}
    ocean = {(l, c) for (l, c) in basse
             if l in (0, MapLignes - 1) or c in (0, MapColonnes - 1)}
    file = deque(ocean)
    while file:
        for v in voisins(*file.popleft()):
            if v in basse and v not in ocean:
                ocean.add(v)
                file.append(v)

    toutes = {(l, c) for l in range(MapLignes) for c in range(MapColonnes)}
    for zone in zones(toutes - ocean):
        if len(zone) < TailleIleMin:
            ocean.update(zone)
    return [[(l, c) in ocean for c in range(MapColonnes)] for l in range(MapLignes)]


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
        for l in range(MapLignes):
            for c in range(MapColonnes):
                if eau[l][c]:
                    continue
                compte = {}
                for nl, nc in voisins(l, c):
                    if not eau[nl][nc]:
                        b = carte[nl][nc]
                        compte[b] = compte.get(b, 0) + 1
                if compte:
                    biome, nb = max(compte.items(), key=lambda kv: kv[1])
                    if nb >= 4:
                        nouvelle[l][c] = biome
        carte = nouvelle
    return carte


def poserPlages(carte, eau, hauteurs):
    for l in range(MapLignes):
        for c in range(MapColonnes):
            if not eau[l][c] and hauteurs[l][c] < 0.05:
                if any(eau[a][b] for a, b in voisins(l, c)):
                    carte[l][c] = "plage"


def descendre(depart, altitude, eau):
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
    sources = [(l, c) for l in range(MapLignes) for c in range(MapColonnes)
               if not eau[l][c] and hauteurs[l][c] > SeuilSource]
    if not sources:
        return
    for _ in range(NbRivieres):
        for l, c in descendre(random.choice(sources), altitude, eau) or []:
            carte[l][c] = "riviere"


def genererCarte():
    relief = bruit(MapColonnes / 4, 5)
    detail = bruit(MapColonnes / 12, 3)
    masque = masqueIle()
    altitude = normaliser([[0.55 * relief[l][c] + 0.15 * detail[l][c] + 0.30 * masque[l][c]
                            for c in range(MapColonnes)] for l in range(MapLignes)])

    seuil = sorted(v for ligne in altitude for v in ligne)[int(PartMer * Aire)]
    hauteurs = [[max(0.0, (altitude[l][c] - seuil) / (1 - seuil))
                 for c in range(MapColonnes)] for l in range(MapLignes)]

    eau = genererEau(altitude, seuil)
    humidite = bruit(MapColonnes / 6, 4)
    carte = [["mer" if eau[l][c] else biomeTerre(hauteurs[l][c], humidite[l][c])
              for c in range(MapColonnes)] for l in range(MapLignes)]

    carte = lisser(carte, eau)
    poserPlages(carte, eau, hauteurs)
    creerRivieres(carte, altitude, eau, hauteurs)
    return carte


def nouvelleCarte():
    global carte, seedActuelle
    seedActuelle = Seed if Seed is not None else random.randrange(1, 10 ** 9)
    random.seed(seedActuelle)
    carte = genererCarte()
