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
#  - il CARTIGLIO deve riportare le 7 iscrizioni obbligatorie del cap.1.5.7;
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
    QgsPointXY,
)
from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtGui import QColor, QFont

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
H_CARTIGLIO = 32.0

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


def fattore_proporzionale(scala, prodotto="gb"):
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
    adattare la grandezza delle scritture allo spazio disponibile."""
    riferimento = SCALA_RIFERIMENTO.get(prodotto, SCALA_RIFERIMENTO["gb"])
    pieno = float(riferimento) / float(scala)
    minimo = CAP_HEIGHT_MINIMA_STAMPA / CAP_HEIGHT_MINIMA_NORMA
    return max(pieno, minimo)


def _layers_proporzionati(project, layers, scala, prodotto="gb", log=None):
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
    fattore = fattore_proporzionale(scala, prodotto)
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


def crea_planimetria(project, layers, centro, scala, formato="A4 verticale",
                     rotazione_gon=0.0, comune="", data_validita=None,
                     nome=None, log=None, prodotto="gb"):
    """Costruisce (e registra nel progetto) il layout di una planimetria.

    'centro'  QgsPointXY su cui centrare il foglio.
    'scala'   denominatore, deve appartenere a SCALE_UFFICIALI_MU.
    'rotazione_gon' rotazione della mappa attorno al centro del foglio.
    'data_validita' data dei dati per l'iscrizione "Stato al" (gg.mm.aaaa);
                  se assente si ripiega sulla data odierna.
    'prodotto' 'gb' (registro fondiario) o 'bp' (piano di base): decide il
                  titolo del foglio.
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
        visibili = _layers_visibili(project, layers, _log)
        per_il_foglio, id_cloni = _layers_proporzionati(project, visibili, scala,
                                                        prodotto, _log)
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

    # Le 7 iscrizioni obbligatorie del cap.1.5.7, disposte su TRE COLONNE che
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

    dettagli = QgsLayoutItemLabel(layout)
    dettagli.setText("Scala 1:%d\nStato al: %s\nLegenda: %s"
                     % (scala, data_validita, LEGENDA_URL))
    dettagli.setFont(QFont("Arial", 8))
    layout.addLayoutItem(dettagli)
    dettagli.attemptSetSceneRect(QRectF(x_testo, y_cart + 17, w_sinistra, 13))

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
