# TIDashboard - dati della misurazione ufficiale svizzera in QGIS
# Copyright (C) 2026 Gabriele Peverelli
#
# Questo programma e' software libero: lo si puo' ridistribuire e modificare
# secondo i termini della GNU General Public License pubblicata dalla Free
# Software Foundation, versione 2 o (a scelta) una successiva. Il testo si
# trova nel file LICENSE distribuito insieme al programma.

"""Lettura di una coppia di coordinate scritta a mano.

Serve a centrare il foglio su un punto noto senza passare da un fondo: chi
ha gia' le coordinate di un punto di interesse le incolla e basta.

TRE FORME AMMESSE, riconosciute dall'ORDINE DI GRANDEZZA e non da un menu da
scegliere - chi incolla una coordinata sa gia' che cos'e', e fargliela anche
dichiarare e' un passaggio in piu' che si puo' sbagliare:

  MN95 (LV95)   2718000, 1082000     l'Est ha 7 cifre e comincia per 2
  MN03 (LV03)    718000,   82000     le vecchie coordinate, ancora in giro
  WGS84          45.87, 8.98         gradi decimali, es. da un telefono

NON si accettano i GON. Il gon e' un'unita' ANGOLARE: nel piano serve per la
rotazione del foglio, non per una posizione. Chiedere "coordinate in gon"
mescola due cose diverse, e accettarle vorrebbe dire indovinare da quale
punto e in che verso.

LA CONVERSIONE MN03 -> MN95 E' APPROSSIMATA: si sommano 2 000 000 all'Est e
1 000 000 al Nord. E' la trasformazione "veloce" pubblicata da swisstopo, con
un errore fino a ~1 metro rispetto alla trasformazione rigorosa, che
richiederebbe la griglia CHENyx06. Per centrare un foglio va benissimo - a
1:500 un metro sono 2 mm - ma chi legge il codice deve saperlo, e la funzione
lo dichiara nel risultato.
"""
import re

# I limiti del sistema nazionale, arrotondati verso l'esterno. Fuori di qui
# non e' una coordinata svizzera: meglio dirlo che centrare il foglio in
# mezzo al nulla.
LV95_EST = (2480000.0, 2840000.0)
LV95_NORD = (1070000.0, 1300000.0)

# Gli stessi limiti in MN03, cioe' senza i due offset.
OFFSET_EST = 2000000.0
OFFSET_NORD = 1000000.0

# Riquadro geografico che contiene la Svizzera, con abbondanza.
WGS84_LON = (5.5, 11.0)
WGS84_LAT = (45.5, 48.0)

# Separatori ammessi fra i due numeri: virgola, punto e virgola, barra o
# spazi. Il punto NON e' un separatore: e' il segno decimale.
_SEPARATORE = re.compile(r"[;,/\s]+")
# Gli apostrofi delle migliaia svizzere (2'718'000) e gli spazi unificatori.
_MIGLIAIA = re.compile(r"['’  ]")


class Coordinate(object):
    """Il risultato della lettura: due numeri in MN95 e come ci si e' arrivati."""

    __slots__ = ("est", "nord", "sistema", "approssimata")

    def __init__(self, est, nord, sistema, approssimata=False):
        self.est = est
        self.nord = nord
        self.sistema = sistema            # "MN95", "MN03", "WGS84"
        self.approssimata = approssimata

    def __repr__(self):
        return "Coordinate(%.3f, %.3f, %s%s)" % (
            self.est, self.nord, self.sistema,
            ", approssimata" if self.approssimata else "")

    def __eq__(self, altro):
        return (isinstance(altro, Coordinate)
                and abs(self.est - altro.est) < 1e-6
                and abs(self.nord - altro.nord) < 1e-6
                and self.sistema == altro.sistema)


def _numeri(testo):
    """I due numeri, o None. Tollera le forme in cui la gente scrive davvero:
    "E 2718000 N 1082000", "2'718'000/1'082'000", "2718000;1082000"."""
    if not testo:
        return None
    pulito = _MIGLIAIA.sub("", str(testo)).strip()
    # Le lettere degli assi si tolgono: "E"/"N" in italiano e tedesco,
    # "Y"/"X" nella tradizione topografica svizzera.
    pulito = re.sub(r"(?i)\b[ENYX]\s*[:=]?\s*", " ", pulito)
    pezzi = [p for p in _SEPARATORE.split(pulito.strip()) if p]
    if len(pezzi) != 2:
        return None
    try:
        return float(pezzi[0].replace(",", ".")), float(pezzi[1].replace(",", "."))
    except ValueError:
        return None


def _dentro(v, limiti):
    return limiti[0] <= v <= limiti[1]


def analizza(testo, trasforma_wgs84=None):
    """Legge una coppia di coordinate. Ritorna un Coordinate o None.

    'trasforma_wgs84' e' una funzione (lon, lat) -> (est, nord) iniettabile:
    fuori da QGIS non c'e' nessuna proiezione, e il resto del modulo deve
    restare provabile lo stesso.
    """
    numeri = _numeri(testo)
    if numeri is None:
        return None
    a, b = numeri

    # MN95: l'Est e' sempre maggiore del Nord, e questo li distingue anche se
    # arrivano invertiti - un errore facile, perche' il tedesco scrive
    # "Nord/Est" e l'italiano "Est/Nord".
    for est, nord in ((a, b), (b, a)):
        if _dentro(est, LV95_EST) and _dentro(nord, LV95_NORD):
            return Coordinate(est, nord, "MN95")

    # MN03: gli stessi limiti senza gli offset.
    for est, nord in ((a, b), (b, a)):
        if (_dentro(est + OFFSET_EST, LV95_EST)
                and _dentro(nord + OFFSET_NORD, LV95_NORD)):
            return Coordinate(est + OFFSET_EST, nord + OFFSET_NORD,
                              "MN03", approssimata=True)

    # WGS84 in gradi decimali. Qui l'ordine NON e' deducibile dai valori (in
    # Svizzera latitudine e longitudine non si sovrappongono, ma per poco):
    # si accetta sia "lat, lon" - la forma dei telefoni e delle mappe - sia
    # "lon, lat", scegliendo l'unica combinazione che cade in Svizzera.
    for lon, lat in ((b, a), (a, b)):
        if _dentro(lon, WGS84_LON) and _dentro(lat, WGS84_LAT):
            if trasforma_wgs84 is None:
                return None
            punto = trasforma_wgs84(lon, lat)
            if punto is None:
                return None
            return Coordinate(punto[0], punto[1], "WGS84")
    return None


def spiega(coord):
    """Una riga che dice cosa si e' capito. Vuota se non si e' capito niente."""
    if coord is None:
        return ""
    if coord.sistema == "MN95":
        return "E %.1f  N %.1f (MN95)" % (coord.est, coord.nord)
    if coord.sistema == "MN03":
        return ("E %.1f  N %.1f — lette come MN03 e convertite in MN95 con i "
                "due offset; la conversione rigorosa (griglia CHENyx06) puo' "
                "differire fino a un metro."
                % (coord.est, coord.nord))
    return "E %.1f  N %.1f — convertite da coordinate geografiche WGS84." % (
        coord.est, coord.nord)


def motivo_del_rifiuto(testo):
    """Perche' non si e' capito: serve a dire all'utente cosa sistemare,
    invece di un "non valido" che non aiuta nessuno."""
    if not (testo or "").strip():
        return ""
    if re.search(r"(?i)\bgon\b", testo):
        return ("Il gon e' un'unita' angolare, non una posizione: nel piano "
                "serve per la rotazione del foglio. Servono due coordinate.")
    numeri = _numeri(testo)
    if numeri is None:
        return ("Servono due numeri separati da virgola o spazio, per esempio "
                "2718000 1082000.")
    return ("Fuori dalla Svizzera: attesi E %.0f..%.0f e N %.0f..%.0f in MN95, "
            "oppure gradi WGS84." % (LV95_EST[0], LV95_EST[1],
                                     LV95_NORD[0], LV95_NORD[1]))
