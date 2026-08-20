# TIDashboard - dati della misurazione ufficiale svizzera in QGIS
# Copyright (C) 2026 Gabriele Peverelli
#
# Questo programma e' software libero: lo si puo' ridistribuire e modificare
# secondo i termini della GNU General Public License pubblicata dalla Free
# Software Foundation, versione 2 o (a scelta) una successiva. Il testo si
# trova nel file LICENSE distribuito insieme al programma.

# Generatore di planimetrie (estratti stampabili del piano per il registro
# fondiario) a scala e rotazione scelte dall'utente.
#
# Tre vincoli normativi guidano il modulo:
#  - le SCALE ammesse sono solo quelle elencate da circ154_allegato2 cap.1.5.1;
#  - il CARTIGLIO deve riportare le NOVE iscrizioni obbligatorie del cap.1.5.7
#    nella versione in vigore (stato 1.2.2014); la versione marzo 2007 ne
#    elencava sette - vedi H_CARTIGLIO;
#  - le dimensioni di simboli e scritture sono definite per una scala di
#    RIFERIMENTO - 1:1000 per il piano RF (cap.1.5.2), 1:5000 per il piano di
#    base (Weisung-BP-AV cap.2.2) - e a scale diverse va applicato un FATTORE DI
#    PROPORZIONALITA': vedi fattore_proporzionale() e il suo limite di
#    leggibilita'.
#
# La rotazione e' espressa in GON (0-400), l'unita' angolare della misurazione
# ufficiale usata in tutto il progetto, e ruota la mappa ATTORNO AL CENTRO
# DELL'ELEMENTO MAPPA: il punto inquadrato resta fermo (verificato: scarto del
# centro 0.000000 m fino a 399 gon).
# PRECISAZIONE: quel centro NON coincide con il centro geometrico del foglio.
# La fascia del cartiglio occupa la parte bassa, quindi la mappa e' piu' in
# alto: misurato, il suo centro sta 16.0 mm sopra il centro del foglio in tutti
# e quattro i formati. E' il comportamento voluto - cio' che deve restare fermo
# e' il punto inquadrato, non un punto geometrico della carta - ma la
# distinzione va tenuta presente leggendo il codice.

import math
from datetime import datetime

from qgis.core import (
    QgsPrintLayout, QgsLayoutItemMap, QgsLayoutItemLabel, QgsLayoutItemScaleBar,
    QgsLayoutItemPicture, QgsLayoutItemMapGrid, QgsLayoutItemShape,
    QgsLayoutSize, QgsUnitTypes, QgsLayoutExporter,
    QgsRectangle, QgsLayoutMeasurement, QgsCoordinateReferenceSystem,
    QgsPointXY, QgsGeometry,
)
from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtGui import QColor, QFont

# Il nome RAW della tabella si legge da un posto solo: una seconda copia di
# quella riga prima o poi divergerebbe, e la copia sbagliata sarebbe sempre
# l'altra. Vedi la nota in ordinamento._raw_table_name sul difetto vero che
# quella funzione ha risolto (join falliti per 123 layer su 128).
try:
    from .ordinamento import _raw_table_name
except ImportError:      # importato come modulo top-level (test)
    from ordinamento import _raw_table_name

# PyQt6 (QGIS 4): gli enum delle classi Qt vanno referenziati nella forma
# annidata Classe.EnumType.Valore - QFont.Bold "piatto" lancia AttributeError.
_GRASSETTO = QFont.Weight.Bold

# Scale standard di rappresentazione del piano per il registro fondiario
# (circ154_allegato2 cap.1.5.1). Non sono un suggerimento: sono l'elenco
# chiuso delle scale ammesse.
SCALE_UFFICIALI_MU = (200, 250, 500, 1000, 2000, 2500, 5000, 10000)

# Formati foglio in mm (larghezza, altezza).
FORMATI = (
    ("A4 verticale",    210.0, 297.0),
    ("A4 orizzontale",  297.0, 210.0),
    ("A3 verticale",    297.0, 420.0),
    ("A3 orizzontale",  420.0, 297.0),
)

# Altezza del cartiglio in fondo al foglio, in mm.
# Alto abbastanza per NOVE iscrizioni, non sette. La versione dell'istruzione
# in vigore (stato 1.2.2014) ne elenca due in piu' rispetto a quella del 2007:
# il cenno sugli oggetti in progetto e quello sugli spostamenti permanenti di
# terreno. Erano 32 mm quando le righe da scrivere erano tre.
# Alzarlo e' sicuro: area_mappa() lo sottrae all'altezza del foglio e
# impronta_foglio() usa area_mappa(), quindi mappa e anteprima restano
# allineate da sole.
H_CARTIGLIO = 40.0

# Margine fra la cornice della mappa e il bordo del foglio. Deve ospitare le
# ANNOTAZIONI DI COORDINATA della griglia, che QGIS scrive fuori dalla cornice:
# una coordinata a 7 cifre in Arial 6 pt misura 7.4 mm, piu' la distanza dalla
# cornice. Con i precedenti 8.0 mm il testo eccedeva di poco e veniva tranciato
# dal bordo del foglio - nei render usciva "082000" invece di "1082000", cioe'
# un'iscrizione obbligatoria (cap.1.5.7) illeggibile.
MARGINE = 14.0
DIST_ANNOTAZIONI = 1.0

# Geometria interna del cartiglio (mm): padding e larghezza riservata alla
# freccia nord. Servono a tenere separate le tre colonne - testi, barra di
# scala, freccia - che prima si sovrapponevano.
PAD_CARTIGLIO = 3.0
W_FRECCIA = 18.0

LEGENDA_URL = "www.cadastre.ch/legende"

# Dicitura sul valore del documento. Il foglio prodotto qui ha titolo,
# cartiglio e simbologia di un prodotto ufficiale della misurazione, ma
# l'emissione di estratti ufficiali spetta all'autorita' competente: senza una
# dicitura esplicita puo' essere scambiato per un estratto ufficiale.
AVVERTENZA_VALORE_LEGALE = "Riproduzione senza valore legale"

# Le due iscrizioni obbligatorie aggiunte dalla versione in vigore del cap.
# 1.5.7 (la versione marzo 2007 ne elencava sette, questa ne elenca nove):
# il cenno sugli oggetti in progetto e quello sugli spostamenti permanenti di
# terreno. La nota a pie' di figura dell'istruzione dice "Esempio di frase,
# adeguamenti necessari": la formulazione e' libera, il cenno obbligatorio.
#
# Vanno dette VERE, non messe li' per riempire la casella: il plugin non
# rappresenta mai gli oggetti in progetto (regola del cap.1.5.3 applicata in
# stili.py, che da' un simbolo invisibile a ogni tabella "*Prog"), mentre le
# zone di movimento uno stile ce l'hanno - quindi quel cenno si decide
# guardando i layer del foglio.
CENNO_PROGETTO = "I beni immobili e gli oggetti in progetto non sono rappresentati."
CENNO_MOVIMENTO_SI = "Gli spostamenti permanenti di terreno sono rappresentati."
CENNO_MOVIMENTO_NO = "Gli spostamenti permanenti di terreno non sono rappresentati."


def cenno_spostamenti(layers):
    """Il cenno del cap.1.5.7 sugli spostamenti permanenti di terreno, deciso
    sui layer che finiscono davvero sul foglio: senza feature da disegnare
    scrivere "sono rappresentati" sarebbe falso."""
    for l in layers or []:
        try:
            nome = (l.name() or "").lower() + " " + (l.source() or "").lower()
        except Exception:
            continue
        if "movimento" in nome and "pos" not in nome.split("movimento")[0][-4:]:
            try:
                if l.featureCount() > 0:
                    return CENNO_MOVIMENTO_SI
            except Exception:
                pass
    return CENNO_MOVIMENTO_NO
C_AVVERTENZA = QColor(204, 0, 0)

# Titolo del foglio secondo il prodotto scelto nella dialog. Era fisso su
# "Piano per il registro fondiario": una planimetria estratta in modalita'
# PB-MU si intestava come un prodotto del registro fondiario, cioe' dichiarava
# il falso proprio nell'iscrizione piu' visibile (cap.1.5.7).
TITOLI_PRODOTTO = {
    "gb": "Piano per il registro fondiario",
    "bp": "Piano di base della misurazione ufficiale",
}

# Passi ammessi per la griglia di coordinate, in metri. Solo valori "tondi":
# le annotazioni sulla cornice sono coordinate nazionali e devono restare
# leggibili (2718000, non 2717925).
PASSI_GRIGLIA = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000)

# Distanza di riferimento fra due croci sulla carta, in mm. La griglia si
# sceglie prendendo il passo tondo che ci si avvicina di piu'.
PASSO_CARTA_MM = 100.0

# Semi-lunghezza dei bracci della croce di reticolo, in mm. Con 1.2 le croci
# erano appena percettibili sul foglio stampato.
LUNGHEZZA_CROCE = 2.0

# Quota della colonna centrale del cartiglio che la barra di scala puo'
# occupare: il resto serve alle etichette dei capisaldi, che sporgono oltre
# le estremita' della barra.
QUOTA_BARRA = 0.8

# Sistema di riferimento dei dati della misurazione ufficiale svizzera.
CRS_MU = "EPSG:2056"


def _svg_freccia_nord():
    """Percorso di una freccia nord fra gli SVG installati con QGIS. Ritorna
    None se non ne trova: in quel caso l'elemento resta senza immagine invece
    di far fallire la creazione della planimetria."""
    import os
    from qgis.core import QgsApplication
    candidati = ("NorthArrow_02.svg", "NorthArrow_01.svg", "NorthArrow_03.svg")
    for base in QgsApplication.svgPaths():
        for nome in candidati:
            percorso = os.path.join(base, "arrows", nome)
            if os.path.exists(percorso):
                return percorso
    return None


def gon_a_gradi(gon):
    """Converte gon (0-400, unita' della misurazione ufficiale) in gradi
    sessagesimali, che sono l'unita' usata da QGIS per la rotazione."""
    return (float(gon) % 400.0) * 0.9


def gradi_a_gon(gradi):
    """L'inverso: gradi sessagesimali -> gon, riportati in [0, 400).

    Serve a tradurre in gon un angolo misurato sul canvas, dove tutto e' in
    gradi: l'utente ruota il foglio col mouse e deve rileggere il valore
    nell'unita' della misurazione ufficiale."""
    return (float(gradi) / 0.9) % 400.0


def _formato(nome):
    for n, w, h in FORMATI:
        if n == nome:
            return w, h
    raise ValueError("formato sconosciuto: %s" % nome)


def intervallo_griglia(scala):
    """Passo della griglia di coordinate in metri: il valore TONDO che tiene le
    croci piu' vicino possibile a PASSO_CARTA_MM di carta.

    Prima era scala/10 arrotondato, che a 1:250 dava 25 m e a 1:2500 dava
    250 m: passi non tondi, con annotazioni di coordinata del tipo 2717925 al
    posto di 2717900. Ora quelle due scale ricevono 20 m e 200 m (80 mm di
    carta invece di 100), mentre per le altre sei scale ufficiali il risultato
    e' identico a prima."""
    obiettivo = PASSO_CARTA_MM / 1000.0 * float(scala)      # mm di carta -> m
    return float(min(PASSI_GRIGLIA, key=lambda p: abs(p - obiettivo)))


def _serie_125_non_oltre(valore):
    """Il piu' grande valore della serie 1-2-5 che non supera 'valore'
    (13.35 -> 10, 66.75 -> 50, 267 -> 200)."""
    if valore <= 0:
        return 0.0
    esponente = math.floor(math.log10(valore))
    mantissa = valore / 10.0 ** esponente
    for m in (5.0, 2.0, 1.0):
        if m <= mantissa + 1e-9:
            return m * 10.0 ** esponente
    return 5.0 * 10.0 ** (esponente - 1)


def _giu_serie_125(valore):
    """Il valore immediatamente inferiore nella serie 1-2-5 (100 -> 50 -> 20 ->
    10 -> 5 -> ...). Serve a rimpicciolire la barra di scala restando su
    capisaldi tondi."""
    if valore <= 0:
        return 0.0
    esponente = math.floor(math.log10(valore))
    mantissa = valore / 10.0 ** esponente
    for m in (5.0, 2.0, 1.0):
        if m < mantissa - 1e-9:
            return m * 10.0 ** esponente
    return 5.0 * 10.0 ** (esponente - 1)


# --- FATTORE DI PROPORZIONALITA' (cap.1.5.2) --------------------------------
# Scala per cui le istruzioni definiscono dimensioni e spessori. I DUE PRODOTTI
# HANNO RIFERIMENTI DIVERSI: il piano per il registro fondiario e' definito
# all'1:1000 (circ154_allegato2 cap.1.5.2), il piano di base all'1:5000
# (Weisung-BP-AV, che ripete "nella scala di riferimento 1:5'000" in ogni
# paragrafo del cap.2.2). Usare 1000 per entrambi sbagliava il fattore di
# cinque volte in PB-MU.
SCALA_RIFERIMENTO = {"gb": 1000, "bp": 5000}

# La scrittura piu' piccola prescritta dal cap.5 (numero di edificio, 1.5 mm di
# altezza-maiuscola) e l'altezza sotto la quale in stampa non si legge piu'.
# Il secondo valore e' una scelta nostra: la norma non fissa un minimo.
CAP_HEIGHT_MINIMA_NORMA = 1.5
CAP_HEIGHT_MINIMA_STAMPA = 1.2


def scala_che_contiene(dx, dy, formato="A4 verticale"):
    """La piu' GRANDE scala ufficiale (denominatore piu' piccolo, quindi piu'
    dettaglio) in cui un oggetto largo dx per dy metri sta dentro il foglio.
    None se non ci sta nemmeno a 1:10000.

    Serve perche' centrare il foglio su un fondo non basta: la scala resta
    quella scelta prima, e un fondo piu' grande del foglio viene tagliato
    senza che nessuno lo dica. Sui dati di Mendrisio, su A4 verticale, non ci
    sta il 25% dei fondi a 1:500 e il 7.7% a 1:1000.

    La rotazione non entra nel conto: si confronta il rettangolo circoscritto
    con il foglio non ruotato, che e' la condizione piu' severa. Un foglio
    ruotato puo' quindi contenere qualcosa che qui risulta fuori - meglio un
    avviso di troppo che un taglio silenzioso."""
    larghezza_mm, altezza_mm = area_mappa(formato)
    for scala in sorted(SCALE_UFFICIALI_MU):
        if (dx or 0) <= larghezza_mm / 1000.0 * scala and            (dy or 0) <= altezza_mm / 1000.0 * scala:
            return scala
    return None


# Quanto respiro lasciare fra l'oggetto e la cornice perche' il foglio si possa
# guardare. Non e' una prescrizione: e' che un fondo che tocca la cornice, o che
# ci finisce sotto per mezzo millimetro, sul foglio stampato sembra tagliato
# anche quando non lo e'. Sui dati di Mendrisio riguarda 197 fondi (1.8%) che
# oggi passano il controllo senza una parola.
MARGINE_CORTESIA = 5.0


def area_utile(formato, margine_mm=0.0):
    """L'area di mappa meno il respiro di cortesia."""
    larghezza, altezza = area_mappa(formato)
    return larghezza - 2 * margine_mm, altezza - 2 * margine_mm


def _ci_sta(dx, dy, formato, scala, margine_mm=0.0):
    larghezza, altezza = area_utile(formato, margine_mm)
    return ((dx or 0) <= larghezza / 1000.0 * scala and
            (dy or 0) <= altezza / 1000.0 * scala)


def estensione_ruotata(dx, dy, rotazione_gon):
    """L'ingombro di un rettangolo dx per dy visto da un foglio ruotato.

    Serve perche' il controllo di capienza confrontava l'oggetto con il foglio
    NON ruotato anche quando l'utente aveva impostato una rotazione: con il
    foglio girato di 50 gon un fondo che esce davvero dalla cornice non veniva
    segnalato. Ruotando il rettangolo circoscritto si resta dalla parte
    prudente - il rettangolo e' gia' piu' grande del fondo, e ruotandolo cresce
    ancora - quindi al massimo si avvisa di troppo, mai di meno."""
    if not rotazione_gon:
        return dx, dy
    angolo = math.radians(gon_a_gradi(rotazione_gon))
    co, si = abs(math.cos(angolo)), abs(math.sin(angolo))
    return dx * co + dy * si, dx * si + dy * co


def rettangolo_minimo(punti):
    """(dx, dy, rotazione_gon) del rettangolo circoscritto piu' PICCOLO.

    Il rettangolo allineato agli assi e' quello che si ottiene gratis da un
    extent, ma per un fondo lungo e stretto in diagonale e' molto piu' grande
    del necessario: girando il foglio ci starebbe. Sui dati di Mendrisio sono
    199 fondi (1.8%) che a 1:500 non ci stanno in nessun formato e ci
    starebbero solo ruotando.

    Il calcolo lo fa QGIS: QgsGeometry.orientedMinimumBoundingBox() esiste gia'
    e torna (geometria, area, angolo in gradi, larghezza, altezza). Qui si
    costruisce la geometria dai punti e si converte l'angolo in gon, che e'
    l'unita' usata dal resto del modulo e dalla misurazione ufficiale. La prima
    stesura di questa funzione riscriveva a mano rotating calipers e scafo
    convesso: codice in piu' da mantenere e da sbagliare, per fare quello che
    la libreria fa gia'.

    'punti' e' una sequenza di (x, y). Meno di tre punti distinti non
    definiscono un rettangolo: si ritorna l'ingombro allineato agli assi, che
    per un segmento o un punto e' anche la risposta giusta."""
    distinti = {(float(x), float(y)) for x, y in punti}
    if len(distinti) < 3:
        xs = [p[0] for p in distinti] or [0.0]
        ys = [p[1] for p in distinti] or [0.0]
        return max(xs) - min(xs), max(ys) - min(ys), 0.0
    geometria = QgsGeometry.fromMultiPointXY([QgsPointXY(x, y) for x, y in distinti])
    _rettangolo, _area, gradi, larghezza, altezza = geometria.orientedMinimumBoundingBox()
    if not larghezza or not altezza:
        xs = [p[0] for p in distinti]
        ys = [p[1] for p in distinti]
        return max(xs) - min(xs), max(ys) - min(ys), 0.0
    return larghezza, altezza, (gradi / 0.9) % 400.0


def rotazione_che_contiene(punti, centro, scala, formato="A4 verticale",
                           margine_mm=MARGINE_CORTESIA):
    """La rotazione del foglio, in gon, che fa entrare 'punti' nel foglio alla
    scala data. None se non basta nemmeno girarlo.

    Il candidato viene dal rettangolo circoscritto minimo, ma NON ci si fida
    dell'angolo: si verifica. Il segno della rotazione e' esattamente il genere
    di dettaglio che si sbaglia in silenzio (QGIS gira il contenuto in senso
    orario dentro una cornice ferma, quindi l'impronta sul terreno gira
    dall'altra parte - vedi impronta_foglio), e un segno invertito darebbe un
    consiglio che peggiora le cose. Si provano quindi l'angolo e il suo
    complemento, e si tiene quello che DAVVERO contiene tutti i vertici,
    misurato sull'impronta vera del foglio.

    Il centro e' quello su cui il foglio verra' davvero centrato, non quello
    ideale del rettangolo minimo: cosi' la risposta vale per il foglio che
    l'utente otterra', non per uno migliore che nessuno stampera'."""
    if not punti or centro is None:
        return None
    dx, dy, gon = rettangolo_minimo(punti)
    if not _ci_sta(min(dx, dy), max(dx, dy), formato, scala, margine_mm) and \
       not _ci_sta(max(dx, dy), min(dx, dy), formato, scala, margine_mm):
        return None                      # non ci sta comunque, inutile girare
    geometria = QgsGeometry.fromMultiPointXY([QgsPointXY(x, y) for x, y in punti])
    for candidata in (gon % 400.0, (gon + 100.0) % 400.0,
                      (-gon) % 400.0, (-gon + 100.0) % 400.0):
        foglio = _foglio_ristretto(centro, scala, formato, candidata, margine_mm)
        if foglio.contains(geometria):
            return candidata
    return None


def _foglio_ristretto(centro, scala, formato, rotazione_gon, margine_mm):
    """L'impronta del foglio rimpicciolita del margine di cortesia: e' l'area
    dentro cui un oggetto ci sta davvero, non quella in cui tocca la cornice."""
    punti = impronta_foglio(centro, scala, formato, rotazione_gon)
    poligono = QgsGeometry.fromPolygonXY([punti])
    if margine_mm:
        poligono = poligono.buffer(-margine_mm / 1000.0 * scala, 4)
    return poligono


def stato_capienza(punti, centro, scala, formato="A4 verticale", rotazione_gon=0.0,
                   margine_mm=MARGINE_CORTESIA):
    """Dove sta un oggetto rispetto al foglio messo in quella posizione:
    "dentro", "stretto" (ci sta ma a filo di cornice) o "fuori". None se non
    c'e' abbastanza informazione per dirlo.

    Serve al trascinamento del foglio: mentre lo si sposta la domanda non e'
    "quale scala serve" - quella e' gia' decisa - ma "il fondo che sto
    inquadrando e' ancora tutto dentro?". Risponde sull'impronta VERA, quella
    che finira' sul foglio, rotazione compresa."""
    if not punti or centro is None:
        return None
    geometria = QgsGeometry.fromMultiPointXY([QgsPointXY(x, y) for x, y in punti])
    intero = QgsGeometry.fromPolygonXY(
        [impronta_foglio(centro, scala, formato, rotazione_gon)])
    if not intero.contains(geometria):
        return "fuori"
    ristretto = _foglio_ristretto(centro, scala, formato, rotazione_gon, margine_mm)
    if ristretto.isEmpty() or not ristretto.contains(geometria):
        return "stretto"
    return "dentro"


def miglior_foglio(dx, dy, scala_voluta, formato_voluto="A4 verticale",
                   margine_mm=MARGINE_CORTESIA, rotazione_gon=0.0):
    """Come stampare un oggetto dx per dy metri, cercando di NON perdere scala.

    Ritorna (formato, scala, motivo) dove motivo dice cosa si e' dovuto
    cambiare: "" se andava gia' bene, "formato" se basta un altro foglio,
    "scala" se si e' dovuto rimpicciolire, None come formato se non ci sta
    nemmeno a 1:10000.

    Prima questa decisione era binaria: ci sta o non ci sta, e in caso negativo
    si proponeva solo una scala piu' piccola sullo stesso formato. Sui dati di
    Mendrisio a 1:500 e' una perdita evitabile per il 14.5% dei fondi (1 627 su
    11 205), che alla scala voluta ci starebbero benissimo su un altro formato:
    passare da 1:500 a 1:1000 dimezza il dettaglio di un piano che non aveva
    bisogno di perderlo.

    L'ordine di preferenza fra i formati: prima quello scelto dall'utente, poi
    l'altro orientamento della stessa carta (cambiare verso costa poco), poi il
    formato piu' grande. Fra due possibilita' vince sempre la scala piu'
    dettagliata."""
    candidati = [formato_voluto]
    girato = _altro_orientamento(formato_voluto)
    if girato:
        candidati.append(girato)
    for nome, _, _ in FORMATI:
        if nome not in candidati:
            candidati.append(nome)

    edx, edy = estensione_ruotata(dx, dy, rotazione_gon)
    for scala in sorted(SCALE_UFFICIALI_MU):
        if scala < scala_voluta:
            continue
        for formato in candidati:
            if not _ci_sta(edx, edy, formato, scala, margine_mm):
                continue
            if scala == scala_voluta and formato == formato_voluto:
                return formato, scala, ""
            if scala == scala_voluta:
                return formato, scala, "formato"
            return formato, scala, "scala"
    return None, None, "impossibile"


def _altro_orientamento(formato):
    """"A4 verticale" -> "A4 orizzontale" e viceversa."""
    for verso, opposto in (("verticale", "orizzontale"), ("orizzontale", "verticale")):
        if formato.endswith(verso):
            candidato = formato[: -len(verso)] + opposto
            return candidato if any(n == candidato for n, _, _ in FORMATI) else None
    return None


# Nessun comune svizzero e' largo piu' di questo: oltre, l'estensione
# dichiarata non descrive i dati.
LARGHEZZA_MAX_COMUNE = 50000.0

# Layer su cui centrare il foglio quando non c'e' una vista: sono l'oggetto
# stesso del piano.
LAYER_DI_CENTRAMENTO = ("bene_immobile", "punto_di_confine")


def estensione_reale(layer):
    """Estensione VERA di un layer, calcolata dalle geometrie quando quella
    dichiarata non e' credibile.

    ili2gpkg scrive in gpkg_contents un riquadro segnaposto pari ai limiti
    della Svizzera (E2480000..2850000, N1070000..1310000) invece
    dell'estensione dei dati, e QGIS si fida di quel valore: verificato su un
    GeoPackage reale di Chiasso, layer.extent() e updateExtents() restituivano
    entrambi tutta la Svizzera, con centro E2665000 N1190000 - cioe' l'Argovia.
    La planimetria di ripiego usciva quindi centrata a 150 km dai dati. Qui si
    riconosce il segnaposto dalla larghezza e si ricalcola scorrendo le
    geometrie.

    NON E' UN CASO RARO, E' LA REGOLA. Misurato sul GeoPackage di Mendrisio:
    dei 121 layer che dichiarano un'estensione, TUTTI E 121 portano il
    segnaposto (larghezza 370 km). La scorciatoia non scatta mai, quindi il
    costo di questa funzione e' sempre quello del ciclo sulle geometrie:
    11 160 oggetti per i beni immobili, 75 298 per i punti di confine.

    Un layer senza geometrie torna VUOTO, non il segnaposto: restituendo
    quest'ultimo bastava un solo layer vuoto - e ce ne sono parecchi, tutti i
    *Prog - per riaffogare l'unione in tutta la Svizzera."""
    estensione = layer.extent()
    if estensione.width() <= LARGHEZZA_MAX_COMUNE:
        return estensione
    vera = QgsRectangle()
    vera.setMinimal()
    for f in layer.getFeatures():
        g = f.geometry()
        if g and not g.isEmpty():
            vera.combineExtentWith(g.boundingBox())
    return vera


def _e_di_centramento(layer):
    """Il layer e' uno di quelli su cui ha senso centrare il foglio?

    Si guarda il nome RAW della tabella, non il titolo nel pannello: i layer
    vengono rinominati per la leggibilita' e il titolo non e' un
    identificatore."""
    nome = _raw_table_name(layer).lower()
    return any(nome.endswith(chiave) for chiave in LAYER_DI_CENTRAMENTO)


def centro_planimetria(layers, centro_fissato=None, centro_vista=None):
    """Centro del foglio, in ordine di precedenza: fondo scelto, vista
    corrente, primo layer di centramento, unione dei layer di centramento.

    La vista arriva come PARAMETRO invece di essere pescata da iface: cosi'
    la funzione si prova senza QGIS aperto, e chi la chiama resta l'unico a
    sapere che esiste un canvas.

    NON si usa l'unione di TUTTI i layer, come faceva la prima versione:
    basta un solo layer con geometrie anomale a portare il centro altrove.
    Riscontrato sui dati reali di Chiasso - Geometria_AN (aree di numerazione,
    29 oggetti) ha geometrie che si estendono da E2485409 a E2833842, cioe'
    mezza Svizzera, e da sola spostava il centro di 100 km."""
    if centro_fissato is not None:
        return centro_fissato
    if centro_vista is not None:
        return centro_vista

    spaziali = [l for l in (layers or []) if l and l.isSpatial()]
    for chiave in LAYER_DI_CENTRAMENTO:
        for lyr in spaziali:
            if not _raw_table_name(lyr).lower().endswith(chiave):
                continue
            if lyr.featureCount() > 0:
                reale = estensione_reale(lyr)
                if not reale.isEmpty():
                    return reale.center()

    # Ripiego, ristretto ai SOLI layer di centramento. Unire tutto costerebbe
    # 315 920 geometrie sul GeoPackage di Mendrisio (nessun layer ha
    # un'estensione dichiarata credibile, vedi estensione_reale) e
    # rimetterebbe in gioco proprio i layer anomali che il ciclo qui sopra
    # evita apposta.
    #
    # Serve al caso in cui featureCount() torni -1: alcuni provider non
    # sanno dire quanti oggetti hanno, il ciclo qui sopra li salta tutti, e
    # senza questo ripiego un GeoPackage perfettamente valido resterebbe
    # senza centro.
    estensione = QgsRectangle()
    estensione.setMinimal()
    for lyr in spaziali:
        if not _e_di_centramento(lyr):
            continue
        reale = estensione_reale(lyr)
        if not reale.isEmpty():
            estensione.combineExtentWith(reale)
    return None if estensione.isEmpty() else estensione.center()


def rotazione_che_salva_la_scala(punti, centro, scala, formato="A4 verticale"):
    """Se girando il foglio l'oggetto ci sta alla scala voluta: su quale
    formato e di quanto. (None, None) se non basta.

    Si provano TUTTI i formati, nello stesso ordine di preferenza di
    miglior_foglio. Fermarsi all'A4 sembrava prudente ed era invece inutile:
    sui dati di Mendrisio, dei 1 248 fondi che a 1:500 non ci stanno dritti in
    nessun formato, quelli recuperabili girando il foglio sono 214, e NESSUNO
    di questi ci sta su un A4 - il rettangolo minimo e' piu' piccolo
    dell'ingombro dritto, ma non tanto da rientrare nel foglio piccolo. Con la
    sola coppia A4 la funzione non scattava mai.

    Senza il contorno (WKB troncato, o ripiego su PosFondo) non si puo'
    calcolare il rettangolo minimo e si risponde di no."""
    if not punti or centro is None:
        return None, None
    candidati = [formato]
    altro = _altro_orientamento(formato)
    if altro:
        candidati.append(altro)
    for nome, _w, _h in FORMATI:
        if nome not in candidati:
            candidati.append(nome)
    for nome in candidati:
        giro = rotazione_che_contiene(punti, centro, scala, nome)
        if giro is not None:
            return nome, giro
    return None, None


def fattore_proporzionale(scala, prodotto="gb", lettera_norma=False):
    """Fattore da applicare a dimensioni e distanze quando la scala del foglio
    differisce dalla scala di riferimento del prodotto (cap.1.5.2 per il piano
    RF, cap.2.2 del Weisung-BP-AV per il piano di base).

    Il testo della norma: "la dimensione dei simboli e quella delle scritture
    nel presente documento sono definite per la scala 1:1000. Per una
    rappresentazione in un'altra scala, l'utilizzatore e' invitato ad adottare
    un fattore di riduzione o d'ingrandimento al fine di garantire le
    proporzioni". Il cap.2.3.2 del Weisung-BP-AV lo ribadisce per le trame:
    anche le distanze fra i simboli vi sono integrate.

    INGRANDIMENTI (scale piu' dettagliate dell'1:1000): fattore pieno, 1000/scala.
    RIDUZIONI: il fattore pieno e' inapplicabile alla lettera - a 1:10000
    varrebbe 0.1 e la scrittura piu' piccola (1.5 mm) scenderebbe a 0.15 mm,
    cioe' non stampabile. Si applica quindi un limite inferiore, calcolato
    perche' quella scrittura non scenda mai sotto CAP_HEIGHT_MINIMA_STAMPA.
    E' uno scostamento dichiarato dalla lettera della norma, non una svista:
    il verbo usato e' "e' invitato" (non "deve") e il cap.5.1 ammette gia' di
    adattare la grandezza delle scritture allo spazio disponibile.

    Il limite NON e' un caso raro: morde su 4 delle 8 scale ufficiali del piano
    RF (1:2000, 1:2500, 1:5000, 1:10000, dove il fattore vero sarebbe 0.50,
    0.40, 0.20 e 0.10 e viene invece portato a 0.80) e su una del piano di base
    (1:10000, 0.50 -> 0.80). A 1:10000 il piano RF disegna quindi otto volte
    piu' grande della lettera della norma. Per questo il fattore applicato
    viene ora scritto nel cartiglio quando differisce.

    'lettera_norma' applica il fattore pieno senza limite inferiore. Serve a
    chi vuole la proporzione esatta e accetta che a 1:10000 la scrittura piu'
    piccola scenda a 0.15 mm, cioe' non si stampi: e' una scelta di conformita'
    formale contro leggibilita', e chi la fa deve saperlo (vedi
    fattore_illeggibile)."""
    riferimento = SCALA_RIFERIMENTO.get(prodotto, SCALA_RIFERIMENTO["gb"])
    pieno = float(riferimento) / float(scala)
    if lettera_norma:
        return pieno
    minimo = CAP_HEIGHT_MINIMA_STAMPA / CAP_HEIGHT_MINIMA_NORMA
    return max(pieno, minimo)


def fattore_illeggibile(fattore):
    """Altezza della scrittura piu' piccola con questo fattore, e se scende
    sotto la soglia di stampa. Ritorna (altezza_mm, illeggibile)."""
    altezza = CAP_HEIGHT_MINIMA_NORMA * float(fattore)
    return altezza, altezza < CAP_HEIGHT_MINIMA_STAMPA


def nota_fattore(scala, prodotto="gb", lettera_norma=False):
    """Testo da affiancare alla scala nel cartiglio, oppure "" se il fattore
    applicato coincide con quello della norma e non c'e' nulla da dichiarare.

    Senza questa nota lo scostamento resta scritto solo nel README e invisibile
    a chi riceve il foglio stampato."""
    riferimento = SCALA_RIFERIMENTO.get(prodotto, SCALA_RIFERIMENTO["gb"])
    pieno = float(riferimento) / float(scala)
    applicato = fattore_proporzionale(scala, prodotto, lettera_norma)
    if abs(applicato - pieno) < 1e-9:
        return ""
    # Accenti veri, non l'apostrofo ASCII usato nei commenti: questo testo
    # finisce STAMPATO nel cartiglio, accanto a "Comune di ...".
    return ("segni e scritte ×%.2f anziché ×%.2f "
            "(cap. 1.5.2, limite di leggibilità)" % (applicato, pieno))


def _layers_proporzionati(project, layers, scala, prodotto="gb", log=None,
                          lettera_norma=False):
    """Copie dei layer con il fattore del cap.1.5.2 applicato, per il solo
    foglio.

    QGIS 4.2 offre il meccanismo giusto - la "scala di riferimento" del
    renderer, che moltiplica dimensioni e distanze per riferimento/scala
    corrente (misurato: marcatore da 3.0 mm reso a 5.9 mm su un foglio 1:500
    con riferimento 1000) - ma e' una proprieta' del LAYER, non del layout:
    impostarla sui layer veri cambierebbe anche il disegno sul canvas, dove
    l'utente zooma liberamente e i simboli sparirebbero alle scale piccole.
    Era esattamente il difetto per cui un primo tentativo di applicare il
    fattore era stato tolto. Si lavora quindi su CLONI, che vivono nel progetto
    ma fuori dall'albero e servono solo a questo foglio.

    Impostando riferimento = fattore x scala si ottiene esattamente il fattore
    voluto, limite di leggibilita' compreso."""
    fattore = fattore_proporzionale(scala, prodotto, lettera_norma)
    if abs(fattore - 1.0) < 1e-9 or project is None:
        return list(layers), []
    riferimento = fattore * float(scala)
    cloni = []
    for l in layers:
        try:
            c = l.clone()
        except Exception:
            cloni.append(l)      # meglio il layer originale che nessun layer
            continue
        c.setName(l.name())
        r = c.renderer()
        if r is not None and hasattr(r, "setReferenceScale"):
            r.setReferenceScale(riferimento)
        project.addMapLayer(c, False)     # nel progetto, ma non nell'albero
        cloni.append(c)
    if log:
        log("   📐 Fattore di proporzionalita' x%.2f (prodotto %s, riferimento "
            "1:%d, scala di riferimento applicata %.0f su %d layer)"
            % (fattore, prodotto, SCALA_RIFERIMENTO.get(prodotto, 1000),
               riferimento, len(cloni)))
        nota = nota_fattore(scala, prodotto, lettera_norma)
        if nota:
            log("   ⚠️ Scostamento dalla lettera della norma: %s. "
                "La nota compare nel cartiglio." % nota)
        altezza, illeggibile = fattore_illeggibile(fattore)
        if illeggibile:
            log("   ⚠️ Lettera della norma: la scrittura piu' piccola scende a "
                "%.2f mm (soglia di stampa %.2f mm). Il foglio e' proporzionato "
                "alla norma ma NON si stampa leggibile."
                % (altezza, CAP_HEIGHT_MINIMA_STAMPA))
    return cloni, [c.id() for c in cloni if c not in layers]


def _rimuovi_cloni(project, layout):
    """Toglie dal progetto i cloni creati per un foglio che viene sostituito:
    senza, ogni rigenerazione ne lascerebbe dietro un centinaio."""
    if project is None or layout is None:
        return 0
    ids = layout.customProperty("tidashboard/cloni", "")
    ids = [i for i in str(ids).split("|") if i]
    for i in ids:
        project.removeMapLayer(i)
    return len(ids)


def _layers_visibili(project, layers, log=None):
    """I layer da mettere sul foglio: quelli spaziali CHE SONO ACCESI
    nell'albero del progetto.

    Prima si prendevano tutti i layer caricati, ignorando le spunte: cosi'
    finivano sul piano anche quelli che il plugin spegne apposta perche' il
    piano per il registro fondiario non li rappresenta - gli identificatori dei
    punti di confine (cap.5.10) e quelli dei punti giurisdizionali. Riscontrato
    su un estratto reale di Chiasso a 1:500: dieci numeri a dieci cifre stampati
    sopra il disegno, che nell'estratto ufficiale non ci sono.

    Se l'albero non e' interrogabile (uso da script senza progetto) si ripiega
    su tutti i layer spaziali, com'era prima."""
    spaziali = [l for l in layers if l and l.isSpatial()]
    radice = project.layerTreeRoot() if project else None
    if radice is None:
        return spaziali
    visibili = []
    for l in spaziali:
        nodo = radice.findLayer(l.id())
        if nodo is None or nodo.isVisible():
            visibili.append(l)
    if log and len(visibili) != len(spaziali):
        log("   ℹ️ Esclusi dal foglio %d layer spenti nell'albero"
            % (len(spaziali) - len(visibili)))
    return visibili


def ordina_come_il_progetto(project, layers):
    """I layer nell'ordine di disegno del progetto, non in quello di
    caricamento.

    QUI STAVA UN DIFETTO SERIO. Il plugin applica al progetto l'ordine di
    disegno del cap.1.5.4 con setCustomLayerOrder - punti fissi e di confine
    sempre davanti, copertura del suolo sempre in fondo - ma la planimetria
    riceveva l'elenco dei layer CARICATI e lo passava cosi' com'era a
    QgsLayoutItemMap.setLayers(), che disegna il primo in cima. Risultato: sul
    canvas la gerarchia era giusta, sul FOGLIO STAMPATO no, e le linee di
    confine finivano sopra i punti di confine - segnalato guardando un PDF
    reale, dove la linea passa dentro l'anello del punto.

    L'ordine si legge dal progetto invece di ricalcolarlo qui: la regola sta
    in un posto solo (ordinamento.py, applicato in fase 4), e due copie della
    stessa gerarchia prima o poi divergono.

    I layer che nell'ordine personalizzato non compaiono restano in coda,
    nell'ordine ricevuto: e' il caso d'uso da script, dove un ordine
    personalizzato puo' non esserci affatto."""
    radice = project.layerTreeRoot() if project else None
    if radice is None or not radice.hasCustomLayerOrder():
        return list(layers)
    posizione = {l.id(): i for i, l in enumerate(radice.customLayerOrder()) if l}
    in_coda = len(posizione)
    return sorted(layers, key=lambda l: posizione.get(l.id(), in_coda))


def area_mappa(formato):
    """Dimensioni in mm della finestra di mappa: il foglio meno i margini e la
    fascia del cartiglio. Sta qui, e non dentro crea_planimetria, perche' la
    stessa geometria serve all'anteprima dell'ingombro sul canvas: se le due
    divergessero l'anteprima mostrerebbe un rettangolo diverso dal foglio."""
    larghezza, altezza = _formato(formato)
    return larghezza - 2 * MARGINE, altezza - 2 * MARGINE - H_CARTIGLIO


def impronta_foglio(centro, scala, formato="A4 verticale", rotazione_gon=0.0):
    """I quattro vertici (chiusi: il primo e' ripetuto in coda) della porzione
    di terreno inquadrata dal foglio, in coordinate del terreno.

    Il verso della rotazione non e' stato dedotto: ruotando la mappa di r gon
    QGIS gira il CONTENUTO in senso orario dentro una cornice ferma, quindi
    l'impronta sul terreno gira in senso antiorario. Il test lo verifica
    confrontando questi vertici con QgsLayoutItemMap.visibleExtentPolygon()."""
    map_w, map_h = area_mappa(formato)
    mezzo_x = map_w / 2000.0 * scala          # mm di carta -> m di terreno
    mezzo_y = map_h / 2000.0 * scala
    angolo = math.radians(gon_a_gradi(rotazione_gon))
    cos_a, sin_a = math.cos(angolo), math.sin(angolo)
    return [QgsPointXY(centro.x() + dx * cos_a - dy * sin_a,
                       centro.y() + dx * sin_a + dy * cos_a)
            for dx, dy in ((-mezzo_x, -mezzo_y), (mezzo_x, -mezzo_y),
                           (mezzo_x, mezzo_y), (-mezzo_x, mezzo_y),
                           (-mezzo_x, -mezzo_y))]


def maniglia_rotazione(centro, scala, formato="A4 verticale", rotazione_gon=0.0):
    """Il punto per cui si afferra il foglio per ruotarlo: meta' del lato
    SUPERIORE dell'impronta.

    Il lato superiore e non un vertice: a rotazione zero sta a nord del
    centro, quindi la maniglia indica anche da che parte guarda il foglio -
    un vertice sarebbe ambiguo fra quattro."""
    punti = impronta_foglio(centro, scala, formato, rotazione_gon)
    # impronta_foglio produce i vertici in ordine: (-x,-y), (+x,-y), (+x,+y),
    # (-x,+y) e la chiusura. I due superiori sono quindi il terzo e il quarto.
    alto_destra, alto_sinistra = punti[2], punti[3]
    return QgsPointXY((alto_destra.x() + alto_sinistra.x()) / 2.0,
                      (alto_destra.y() + alto_sinistra.y()) / 2.0)


def rotazione_verso(centro, punto):
    """La rotazione in gon che porta la maniglia sotto 'punto'. None se il
    punto coincide col centro, dove un angolo non esiste.

    IL VERSO NON E' DEDOTTO A OCCHIO. impronta_foglio ruota l'impronta in
    senso ANTIORARIO (vedi la sua docstring: QGIS gira il contenuto in senso
    orario dentro una cornice ferma), quindi a rotazione r la maniglia sta a
    r gon in senso antiorario da nord. Qui si inverte quella relazione, e un
    test la percorre in tutti e due i sensi su tutto il giro: e' l'unico modo
    di non sbagliare un segno che a occhio sembra sempre giusto."""
    dx = punto.x() - centro.x()
    dy = punto.y() - centro.y()
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return None
    # atan2 misura da EST in senso antiorario; la maniglia a rotazione zero
    # sta a NORD, cioe' 90 gradi piu' avanti.
    return gradi_a_gon(math.degrees(math.atan2(dy, dx)) - 90.0)


def crea_planimetria(project, layers, centro, scala, formato="A4 verticale",
                     rotazione_gon=0.0, comune="", data_validita=None,
                     nome=None, log=None, prodotto="gb", lettera_norma=False):
    """Costruisce (e registra nel progetto) il layout di una planimetria.

    'centro'  QgsPointXY su cui centrare il foglio.
    'scala'   denominatore, deve appartenere a SCALE_UFFICIALI_MU.
    'rotazione_gon' rotazione della mappa attorno al centro del foglio.
    'data_validita' data dei dati per l'iscrizione "Stato al" (gg.mm.aaaa);
                  se assente si ripiega sulla data odierna.
    'prodotto' 'gb' (registro fondiario) o 'bp' (piano di base): decide il
                  titolo del foglio.
    'lettera_norma' applica il fattore del cap.1.5.2 senza il limite di
                  leggibilita': proporzione esatta, ma alle scale piccole le
                  scritture non si stampano piu'. Vedi fattore_proporzionale.
    Ritorna il QgsLayout creato.
    """
    def _log(msg):
        if log:
            log(msg)

    if int(scala) not in SCALE_UFFICIALI_MU:
        raise ValueError(
            "scala 1:%s non ammessa dal cap.1.5.1; ammesse: %s"
            % (scala, ", ".join("1:%d" % s for s in SCALE_UFFICIALI_MU)))

    if prodotto not in TITOLI_PRODOTTO:
        raise ValueError("prodotto sconosciuto: %s (attesi: %s)"
                         % (prodotto, ", ".join(sorted(TITOLI_PRODOTTO))))
    if not (comune or "").strip():
        # Il chiamante da script puo' avere motivi suoi per lasciarlo vuoto,
        # ma non deve poter succedere in silenzio: e' una delle sette
        # iscrizioni obbligatorie. Dalla dialog il campo e' invece bloccante.
        _log("   ⚠️ Comune non indicato: il cartiglio resta senza "
             "un'iscrizione obbligatoria (cap.1.5.7)")

    larghezza, altezza = _formato(formato)
    # La data odierna e' solo il ripiego per i chiamanti che non ne passano una
    # (test, uso da script): "Stato al" e' la data di validita' dei dati, che
    # l'interfaccia fa scegliere all'utente. Vedi il campo data_validita.
    data_validita = data_validita or datetime.now().strftime("%d.%m.%Y")
    # Il nome include centro e rotazione: rigenerando LO STESSO estratto il
    # layout viene sostituito (comportamento voluto), mentre due estratti di
    # zone o orientamenti diversi convivono. Col vecchio nome, legato solo a
    # formato e scala, la seconda planimetria cancellava silenziosamente la
    # prima - verificato.
    if not nome:
        nome = "Planimetria_%s_1-%d_E%d_N%d" % (
            formato.replace(" ", "_"), scala, round(centro.x()), round(centro.y()))
        if rotazione_gon:
            nome += "_%.0fgon" % float(rotazione_gon)

    # QgsPrintLayout, non QgsLayout: solo il primo ha un nome e puo' essere
    # registrato nel gestore layout del progetto (QgsLayout.setName non esiste).
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(nome)
    pagina = layout.pageCollection().page(0)
    pagina.setPageSize(QgsLayoutSize(larghezza, altezza, QgsUnitTypes.LayoutMillimeters))

    # ------------------------------------------------------------- mappa
    # Occupa il foglio meno i margini e la fascia del cartiglio. E' centrata
    # orizzontalmente per costruzione; la rotazione avviene attorno al centro
    # dell'elemento mappa, che e' cio' che l'utente percepisce come "centro
    # del foglio".
    map_w, map_h = area_mappa(formato)
    mappa = QgsLayoutItemMap(layout)
    layout.addLayoutItem(mappa)
    mappa.attemptSetSceneRect(QRectF(MARGINE, MARGINE, map_w, map_h))
    # CRS ESPLICITO, prima di estensione e scala: senza, QGIS non sa mettere in
    # relazione le unita' della mappa con i millimetri del foglio e la scala
    # diventa priva di senso - misurato: 1:86'110'078 senza setScale, ed
    # estensione azzerata (0x0 m) con setScale, quindi un foglio vuoto o
    # ingrandito a caso. Non ci si puo' affidare al CRS del progetto: puo'
    # essere non impostato.
    mappa.setCrs(QgsCoordinateReferenceSystem(CRS_MU))
    id_cloni = []
    if layers:
        # L'ordine PRIMA del filtro sui visibili e prima dei cloni: entrambi
        # conservano l'ordine che ricevono, quindi basta metterlo qui.
        visibili = _layers_visibili(project, ordina_come_il_progetto(project, layers), _log)
        per_il_foglio, id_cloni = _layers_proporzionati(project, visibili, scala,
                                                        prodotto, _log,
                                                        lettera_norma)
        mappa.setLayers(per_il_foglio)
    # setExtent PRIMA di setScale: l'estensione fissa il centro, la scala poi
    # ridimensiona attorno a quel centro senza spostarlo.
    mezzo_x = map_w / 2000.0 * scala      # mm -> m sul terreno
    mezzo_y = map_h / 2000.0 * scala
    mappa.setExtent(QgsRectangle(centro.x() - mezzo_x, centro.y() - mezzo_y,
                                 centro.x() + mezzo_x, centro.y() + mezzo_y))
    mappa.setScale(float(scala))
    mappa.setMapRotation(gon_a_gradi(rotazione_gon))
    mappa.setFrameEnabled(True)
    mappa.setFrameStrokeWidth(QgsLayoutMeasurement(0.3, QgsUnitTypes.LayoutMillimeters))

    # Riferimento alla rete di coordinate nazionali (cap.1.5.7): croci nel
    # disegno e valori delle coordinate sulla cornice.
    #
    # COSA SI AGGIORNA DA SOLO E COSA NO (misurato):
    #  - posizione delle croci e valori delle coordinate: ricalcolati a ogni
    #    disegno dall'estensione corrente, quindi seguono da soli pan, zoom e
    #    rotazione;
    #  - PASSO della griglia: fissato QUI in base alla scala richiesta. Se la
    #    scala viene poi cambiata a mano nel compositore il passo NON si
    #    adegua: misurato, un layout creato a 1:1000 (passo 100 m) e portato a
    #    1:5000 mostra ~10 croci in larghezza invece di 2. Per riallinearlo
    #    basta rigenerare la planimetria dalla dialog con la nuova scala.
    griglia = mappa.grid()
    griglia.setEnabled(True)
    griglia.setStyle(QgsLayoutItemMapGrid.Cross)
    passo = intervallo_griglia(scala)
    griglia.setIntervalX(passo)
    griglia.setIntervalY(passo)
    griglia.setCrossLength(LUNGHEZZA_CROCE)
    griglia.setAnnotationEnabled(True)
    griglia.setAnnotationPrecision(0)
    griglia.setAnnotationFont(QFont("Arial", 6))
    griglia.setAnnotationFrameDistance(DIST_ANNOTAZIONI)
    # Spessore del reticolo: il PB-MU lo fissa a 0.12 mm (Weisung-BP-AV
    # §2.2.11), il piano RF non lo prescrive e si tiene lo 0.1 usato finora.
    griglia.setGridLineWidth(0.12 if prodotto == "bp" else 0.1)
    # Ogni coordinata dichiara la propria famiglia con la lettera E o N.
    #
    # Le linee di griglia restano allineate al sistema nazionale anche quando il
    # foglio e' ruotato, percio' con la rotazione tagliano tutti e quattro i lati
    # della cornice: sullo stesso bordo comparivano Est e Nord alternate
    # (misurato a 50 gon, bordo sinistro dall'alto: 1082000, 2717900, 1081900,
    # 2718000) senza nulla che dicesse quale fosse quale.
    # La via ovvia - riservare i lati verticali alle Nord e quelli orizzontali
    # alle Est - e' stata provata e scartata: le linee Est che escono solo dai
    # lati verticali perdevano del tutto l'annotazione (due Est su tre, sempre a
    # 50 gon), cioe' si risolveva la confusione buttando via l'informazione, che
    # per un'iscrizione obbligatoria (cap.1.5.7) e' peggio.
    # Le coordinate sui bordi VERTICALI si scrivono in verticale, come sui piani
    # ufficiali: orizzontali occupavano il margine in larghezza (ed e' il motivo
    # per cui MARGINE ha dovuto crescere fino a 14 mm) e spezzavano la lettura
    # del bordo. In verticale il margine serve solo all'altezza del carattere.
    griglia.setAnnotationDirection(QgsLayoutItemMapGrid.Vertical,
                                   QgsLayoutItemMapGrid.Left)
    griglia.setAnnotationDirection(QgsLayoutItemMapGrid.VerticalDescending,
                                   QgsLayoutItemMapGrid.Right)
    griglia.setAnnotationFormat(QgsLayoutItemMapGrid.CustomFormat)
    griglia.setAnnotationExpression(
        "CASE WHEN @grid_axis = 'x' THEN 'E ' ELSE 'N ' END"
        " || to_string(round(@grid_number))")

    # -------------------------------------------------------- cartiglio
    y_cart = altezza - MARGINE - H_CARTIGLIO
    riquadro = QgsLayoutItemShape(layout)
    riquadro.setShapeType(QgsLayoutItemShape.Rectangle)
    riquadro.attemptSetSceneRect(QRectF(MARGINE, y_cart, larghezza - 2 * MARGINE, H_CARTIGLIO))
    layout.addLayoutItem(riquadro)

    # Le NOVE iscrizioni obbligatorie del cap.1.5.7, disposte su TRE COLONNE che
    # non si toccano: testi a sinistra, rotazione e barra di scala al centro,
    # freccia nord a destra. La versione precedente posizionava gli elementi a
    # frazioni fisse della larghezza e i riquadri si sovrapponevano in tutti i
    # formati (barra/dettagli 16x8 mm, freccia/titolo 18x5 mm, rotazione/
    # dettagli 11x6 mm): non si notava solo perche' i testi di prova erano
    # corti, ma un nome di comune lungo li avrebbe fatti collidere davvero.
    x_testo = MARGINE + PAD_CARTIGLIO
    x_freccia = larghezza - MARGINE - PAD_CARTIGLIO - W_FRECCIA
    x_fine_centro = x_freccia - PAD_CARTIGLIO
    w_utile = x_fine_centro - x_testo
    w_sinistra = w_utile * 0.55
    x_centro_col = x_testo + w_sinistra + PAD_CARTIGLIO
    w_centro = x_fine_centro - x_centro_col

    # Il titolo occupa la sola colonna di sinistra e non piu' tutta la
    # larghezza: accanto va la dicitura sul valore legale, e due riquadri
    # sovrapposti farebbero scattare il controllo di collisione del cartiglio.
    titolo = QgsLayoutItemLabel(layout)
    titolo.setText(TITOLI_PRODOTTO[prodotto])
    titolo.setFont(QFont("Arial", 12, _GRASSETTO))
    layout.addLayoutItem(titolo)
    titolo.attemptSetSceneRect(QRectF(x_testo, y_cart + 2, w_sinistra, 7))

    # Il foglio ha il titolo, il cartiglio e la simbologia di un prodotto
    # ufficiale della misurazione: senza una dicitura esplicita chi lo riceve
    # puo' scambiarlo per un estratto emesso dall'autorita' competente.
    # In rosso perche' si legga prima del resto.
    avvertenza = QgsLayoutItemLabel(layout)
    avvertenza.setText(AVVERTENZA_VALORE_LEGALE)
    avvertenza.setFont(QFont("Arial", 10, _GRASSETTO))
    avvertenza.setFontColor(C_AVVERTENZA)
    layout.addLayoutItem(avvertenza)
    avvertenza.attemptSetSceneRect(QRectF(x_centro_col, y_cart + 2, w_centro, 7))

    sottotitolo = QgsLayoutItemLabel(layout)
    sottotitolo.setText("Comune di %s" % (comune or "—"))
    sottotitolo.setFont(QFont("Arial", 10))
    layout.addLayoutItem(sottotitolo)
    sottotitolo.attemptSetSceneRect(QRectF(x_testo, y_cart + 10, w_sinistra, 6))

    # La nota sul fattore del cap.1.5.2 sta SULLA RIGA DELLA SCALA, non su una
    # riga sua: il cartiglio e' alto H_CARTIGLIO (32 mm) e questo blocco arriva
    # gia' a y+30, quindi una quarta riga uscirebbe dal riquadro. E' anche il
    # punto giusto dove leggerla, accanto al denominatore a cui si riferisce.
    nota = nota_fattore(scala, prodotto, lettera_norma)
    # "Stato al" e non "Allestimento" come nella figura dell'istruzione:
    # l'iscrizione obbligatoria e' "una data di validita'", e la data che
    # scriviamo e' quella dei DATI, non quella in cui il foglio e' stato
    # prodotto. "Allestimento" sarebbe una data diversa e la dichiarerebbe
    # sbagliata.
    dettagli = QgsLayoutItemLabel(layout)
    dettagli.setText("Scala 1:%d%s\nStato al: %s\n%s\n%s\nLegenda: %s"
                     % (scala, ("  —  " + nota) if nota else "",
                        data_validita, CENNO_PROGETTO,
                        cenno_spostamenti(layers), LEGENDA_URL))
    dettagli.setFont(QFont("Arial", 8))
    layout.addLayoutItem(dettagli)
    dettagli.attemptSetSceneRect(QRectF(x_testo, y_cart + 17, w_sinistra, 21))

    if rotazione_gon:
        rot = QgsLayoutItemLabel(layout)
        rot.setText("Rotazione: %.1f gon" % float(rotazione_gon))
        rot.setFont(QFont("Arial", 8))
        layout.addLayoutItem(rot)
        rot.attemptSetSceneRect(QRectF(x_centro_col, y_cart + 10, w_centro, 6))

    # Direzione del nord (cap.1.5.7). E' AGGANCIATA alla mappa con
    # setLinkedMap + NorthMode: cosi' la freccia si orienta da sola in base
    # alla rotazione della mappa e continua a indicare il nord. Una "N" fissa
    # in un angolo sarebbe sbagliata non appena si ruota il foglio, che e'
    # proprio il caso d'uso di questo modulo.
    percorso_freccia = _svg_freccia_nord()
    freccia = QgsLayoutItemPicture(layout)
    layout.addLayoutItem(freccia)
    if percorso_freccia:
        freccia.setPicturePath(percorso_freccia)
    freccia.setLinkedMap(mappa)
    freccia.setNorthMode(QgsLayoutItemPicture.GridNorth)
    freccia.attemptSetSceneRect(QRectF(x_freccia, y_cart + 4, W_FRECCIA, 24))
    if not percorso_freccia:
        # Senza SVG l'elemento immagine resterebbe VUOTO e la direzione del
        # nord - iscrizione obbligatoria - sparirebbe senza che nessuno se ne
        # accorga. Si ripiega su una "N" ruotata come la freccia (stessa
        # rotazione calcolata da QGIS per il nord) e si avvisa nel log.
        ripiego = QgsLayoutItemLabel(layout)
        ripiego.setText("N\u2191")
        ripiego.setFont(QFont("Arial", 11, _GRASSETTO))
        layout.addLayoutItem(ripiego)
        ripiego.attemptSetSceneRect(QRectF(x_freccia, y_cart + 10, W_FRECCIA, 10))
        ripiego.setItemRotation(freccia.pictureRotation())
        _log("   \u26A0\uFE0F Freccia nord SVG non trovata fra gli SVG di QGIS: "
             "ripiego su una 'N' orientata. Direzione del nord comunque presente.")

    # Barra di scala. La larghezza NON va imposta: forzandola con
    # attemptSetSceneRect la barra veniva stirata o compressa nella colonna
    # senza che i suoi capisaldi cambiassero, quindi la lunghezza disegnata non
    # corrispondeva piu' ai metri annotati - una barra di scala che mente.
    # Qui si sceglie invece il caposaldo (serie 1-2-5) piu' grande che ci sta,
    # si lascia dimensionare la barra da sola e si posiziona il risultato.
    barra = QgsLayoutItemScaleBar(layout)
    barra.setStyle("Single Box")
    layout.addLayoutItem(barra)
    barra.setLinkedMap(mappa)
    barra.setFont(QFont("Arial", 7))
    barra.applyDefaultSize()          # sceglie l'unita' di misura (m o km)
    barra.setNumberOfSegments(2)
    barra.setNumberOfSegmentsLeft(0)
    # Caposaldo tondo: il piu' grande della serie 1-2-5 che occupa al massimo
    # QUOTA_BARRA della colonna. Il valore proposto da applyDefaultSize non e'
    # tondo (misurato: 8 m a 1:500, 75 m a 1:5000) e su una barra di scala i
    # capisaldi vanno letti a colpo d'occhio. mapUnitsPerScaleBarUnit tiene
    # conto dell'unita' scelta sopra, cosi' il conto vale sia in m sia in km.
    terreno_disponibile = w_centro * QUOTA_BARRA / 1000.0 * scala
    per_segmento = _serie_125_non_oltre(
        terreno_disponibile / 2.0 / max(barra.mapUnitsPerScaleBarUnit(), 1e-9))
    if per_segmento > 0:
        barra.setUnitsPerSegment(per_segmento)
    barra.update()
    barra.resizeToMinimumWidth()
    # Rete di sicurezza: le etichette dei capisaldi sporgono oltre le estremita'
    # della barra, quindi l'ingombro reale supera la lunghezza disegnata. Se non
    # entra comunque nella colonna si scende di un gradino nella serie.
    for _ in range(8):
        if barra.sizeWithUnits().width() <= w_centro:
            break
        ridotto = _giu_serie_125(barra.unitsPerSegment())
        if ridotto <= 0:
            break
        barra.setUnitsPerSegment(ridotto)
        barra.update()
        barra.resizeToMinimumWidth()
    dim = barra.sizeWithUnits()
    barra.attemptSetSceneRect(QRectF(x_centro_col, y_cart + 18,
                                     dim.width(), dim.height()))

    # I cloni proporzionati appartengono a QUESTO foglio: si annotano sul
    # layout, cosi' sostituendolo si possono togliere dal progetto.
    layout.setCustomProperty("tidashboard/cloni", "|".join(id_cloni))

    gestore = project.layoutManager()
    esistente = gestore.layoutByName(nome)
    if esistente:
        n = _rimuovi_cloni(project, esistente)
        gestore.removeLayout(esistente)
        _log("   \u2139\uFE0F Sostituita la planimetria omonima gia' presente ('%s')" % nome
             + (", rimossi %d layer di servizio" % n if n else ""))
    gestore.addLayout(layout)
    _log("   📐 Planimetria '%s': %s, 1:%d, rotazione %.1f gon, griglia %d m"
         % (nome, formato, scala, float(rotazione_gon), passo))
    _log("      (cambiando la scala nel compositore il passo della griglia "
         "resta %d m: rigenera da qui per riadattarlo)" % passo)
    return layout


def esporta_pdf(layout, percorso):
    """Esporta il layout in PDF. Ritorna (ok, messaggio)."""
    exporter = QgsLayoutExporter(layout)
    impostazioni = QgsLayoutExporter.PdfExportSettings()
    impostazioni.dpi = 300      # cap.3.1 delle prescrizioni cantonali: min 300 dpi
    esito = exporter.exportToPdf(percorso, impostazioni)
    if esito == QgsLayoutExporter.Success:
        return True, percorso
    return False, "codice di errore %s" % esito
