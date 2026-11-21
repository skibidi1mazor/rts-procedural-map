# Tuto — Génération procédurale d’une carte hexagonale

Ce projet utilise Python et Pygame pour créer automatiquement une carte composée de cases hexagonales. Le programme calcule l’altitude de chaque case afin de placer la mer, les plaines, les forêts et les montagnes. Il ajoute ensuite les plages près de la mer et trace des rivières qui suivent les pentes du terrain. Une graine (`Seed`) fixe permet de reproduire exactement la même carte.

## Sommaire

1. [Pavage hexagonal](#pavage-hexagonal)
2. [Création du relief](#création-du-relief)
3. [Biomes terrestres](#biomes-terrestres)
4. [Plages et rivières](#plages-et-rivières)
5. [Résultat final](#résultat-final)

## Réglages du programme

```python
LIGNES, COLONNES = 1000, 1000
AIRE = LIGNES * COLONNES
SEED = None                       # None = aléatoire ; un nombre = carte fixe
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
TAILLE_MIN_HEX = 4
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
```

Ces réglages définissent la taille de la carte, le niveau de la mer, le nombre de rivières, les dimensions des hexagones, le déplacement et le zoom. Le dictionnaire `COULEURS` associe chaque terrain à une couleur.

## Pavage hexagonal

### Dessiner un hexagone

Chaque sommet est placé à la distance `r` du centre `(x, y)`. Le premier sommet utilise un angle de 30 degrés, puis chaque angle suivant augmente de 60 degrés.

$$
\theta_k = 30^\circ + 60^\circ k \qquad (k = 0, 1, 2, 3, 4, 5)
$$

Le cosinus donne le déplacement horizontal et le sinus le déplacement vertical :

$$
x_k = x + r\cos(\theta_k)
\qquad
y_k = y + r\sin(\theta_k)
$$

```python
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
```

Pour chaque case visible, `cam.ecran(l, c)` donne la position du centre. Le programme ajoute les six décalages pour obtenir les sommets, puis `pygame.draw.polygon()` dessine l’hexagone.

### Grille hexagonale

La carte contient 1 000 lignes et 1 000 colonnes, soit 1 000 000 de cases. Chaque case est repérée par sa ligne `l` et sa colonne `c`. Les lignes impaires sont décalées vers la droite.

Sur une même ligne, les centres des hexagones sont espacés de $\sqrt{3}\,R$. La ligne suivante est placée à $1,5R$ sous la précédente. Une ligne sur deux est décalée horizontalement de $\frac{\sqrt{3}R}{2}$.

$$
x = \left(c + \frac{l \bmod 2}{2}\right)\sqrt{3}R
\qquad
y = 1{,}5Rl + R
$$

```python
LIGNES, COLONNES = 1000, 1000

def centre(self, l, c):
    decalage = LARGEUR_HEX / 2 if l % 2 else 0
    x = c * LARGEUR_HEX + decalage
    y = l * HAUTEUR_HEX + RAYON
    return x, y
```

### Calcul des voisines

Pour trouver une voisine, le programme ajoute un déplacement $(\Delta l, \Delta c)$ à la position de la case :

$$
(l_{voisine}, c_{voisine}) = (l + \Delta l, c + \Delta c)
$$

```python
DELTAS_PAIR = ((-1, -1), (-1, 0), (1, -1), (1, 0), (0, -1), (0, 1))
DELTAS_IMPAIR = ((-1, 0), (-1, 1), (1, 0), (1, 1), (0, -1), (0, 1))

def voisins(l, c):
    deltas = DELTAS_PAIR if l % 2 == 0 else DELTAS_IMPAIR
    return [
        (l + dl, c + dc)
        for dl, dc in deltas
        if 0 <= l + dl < LIGNES and 0 <= c + dc < COLONNES
    ]
```

La dernière condition conserve uniquement les cases situées dans les limites de la carte.

## Création du relief

Le programme attribue une altitude à chacune des 1 000 000 de cases. Il combine un relief principal, des détails plus fins et un masque d’île qui favorise les altitudes élevées au centre.

$$
B(l,c)=0{,}55R(l,c)+0{,}15D(l,c)+0{,}30M(l,c)
$$

- $R(l,c)$ représente le relief principal.
- $D(l,c)$ représente les petits détails.
- $M(l,c)$ représente le masque d’île.

Les altitudes sont ensuite normalisées entre 0 et 1 :

$$
A(l,c)=\frac{B(l,c)-B_{\min}}{B_{\max}-B_{\min}}
$$

```python
relief = bruit(COLONNES / 4, 5)
detail = bruit(COLONNES / 12, 3)
masque = masqueIle()
altitude = normaliser([
    [0.55 * relief[l][c] + 0.15 * detail[l][c] + 0.30 * masque[l][c]
     for c in range(COLONNES)]
    for l in range(LIGNES)
])
```

La fonction `bruit()` superpose plusieurs couches de valeurs aléatoires lissées. Le masque d’île donne une valeur maximale au centre et diminue vers les bords.

## Biomes terrestres

Pour chaque case, le programme utilise son altitude normalisée $A(l,c)$ et son humidité $U(l,c)$ :

| Altitude $A$ | Terrain selon l’humidité $U$ |
| --- | --- |
| $A < 0{,}45$ | Désert si $U < 0{,}30$, plaine si $0{,}30 \le U < 0{,}55$, forêt sinon |
| $0{,}45 \le A < 0{,}75$ | Terre si $U < 0{,}40$, forêt si $0{,}40 \le U < 0{,}80$, plaine sinon |
| $0{,}75 \le A < 0{,}90$ | Pierre si $U < 0{,}40$, montagne sinon |
| $A \ge 0{,}90$ | Neige quelle que soit l’humidité |

```python
def biomeTerre(hauteur, humidite):
    if hauteur < 0.45:
        return "desert" if humidite < 0.30 else "plaine" if humidite < 0.55 else "foret"
    if hauteur < 0.75:
        return "terre" if humidite < 0.40 else "foret" if humidite < 0.80 else "plaine"
    if hauteur < 0.90:
        return "pierre" if humidite < 0.40 else "montagne"
    return "neige"
```

Enfin, `lisser()` rend les zones terrestres plus régulières. Si au moins quatre voisines terrestres appartiennent au même biome, la case peut prendre ce biome.

## Plages et rivières

### Plages

Une case terrestre devient une plage si sa hauteur relative est inférieure à 0,05 et si elle touche au moins une case de mer :

$$
p \notin \text{Mer}
\quad \text{et} \quad
h(p) < 0{,}05
\quad \text{et} \quad
V(p) \cap \text{Mer} \ne \varnothing
$$

```python
def poserPlages(carte, eau, hauteurs):
    for l in range(LIGNES):
        for c in range(COLONNES):
            if not eau[l][c] and hauteurs[l][c] < 0.05:
                if any(eau[a][b] for a, b in voisins(l, c)):
                    carte[l][c] = "plage"
```

### Rivières

Une case peut servir de source si elle est sur terre et si sa hauteur relative dépasse 0,60 :

$$
p \notin \text{Mer}
\quad \text{et} \quad
h(p) > 0{,}60
$$

À chaque étape, `descendre()` choisit la voisine ayant la plus basse altitude :

$$
q = \underset{v \in V(p)}{\arg\min}\,A(v)
$$

```python
def creerRivieres(carte, altitude, eau, hauteurs):
    sources = [(l, c) for l in range(LIGNES) for c in range(COLONNES)
               if not eau[l][c] and hauteurs[l][c] > SEUIL_SOURCE]
    if not sources:
        return
    for _ in range(NB_RIVIERES):
        for l, c in descendre(random.choice(sources), altitude, eau) or []:
            carte[l][c] = "riviere"
```

S’il existe des sources, le programme réalise 150 essais. Seuls les trajets descendants qui atteignent la mer sont marqués comme rivières.

## Résultat final

Le programme génère une carte de 1 000 lignes sur 1 000 colonnes. Chaque hexagone est coloré selon son terrain : mer, plage, désert, plaine, forêt, terre, pierre, montagne, neige ou rivière.

On peut se déplacer sur la carte, zoomer pour observer les détails et modifier la graine pour obtenir une autre génération.
