# Il DXF prodotto, riletto da GDAL: un secondo parere su quello che abbiamo
# scritto.
#
# PERCHE' SERVE UN SECONDO LETTORE. Il controllo strutturale che facevamo prima
# (_validate_dxf) legge il file con il nostro stesso codice: se sbagliamo a
# scrivere qualcosa e sbagliamo allo stesso modo a rileggerlo, il controllo
# passa e il difetto arriva in AutoCAD.
#
# GDAL e' il lettore giusto per questo mestiere: e' gia' dentro QGIS - nessuna
# dipendenza nuova, nessuna licenza da rispettare oltre a quelle che abbiamo
# gia' - ed e' un'implementazione completamente diversa dalla nostra.
#
# COSA PRENDE E COSA NO, MISURATO E NON SUPPOSTO. Il punto non e' che GDAL
# veda tutto: e' che sbaglia in punti diversi dai nostri. Provato costruendo
# apposta un DXF per ciascun difetto:
#
#   difetto                        GDAL
#   -----------------------------  -------------------------
#   tipo di entita' sconosciuto    SCARTA l'entita'
#   REGION (non supportata)        SCARTA l'entita'
#   POLYLINE senza vertici         SCARTA l'entita'
#   POLYLINE senza SEQEND          SCARTA (e lo dice in console)
#   VERTEX con flag 70=1           la legge
#   MLINE                          la legge
#   TEXT senza altezza             la legge
#   HATCH senza contorno           la legge
#
# La riga sul flag 70=1 merita una nota, perche' e' proprio il difetto che ci
# aveva morso: li' era EZDXF a scartare l'intera polilinea, non GDAL. I due
# lettori non si sostituiscono a vicenda - ciascuno vede quello che l'altro
# lascia passare - e questo controllo copre il primo elenco, non il secondo.
#
# L'INVARIANTE. Ogni entita' della sezione ENTITIES deve diventare esattamente
# una feature per GDAL, sullo stesso layer. Misurato sul DXF di Mendrisio (209
# MB): 468 622 scritte, 468 622 lette, scarto zero su tutti e 90 i layer. Se un
# giorno una modifica producesse entita' che un lettore indipendente scarta, lo
# scarto smetterebbe di essere zero e si vedrebbe subito, invece che in
# AutoCAD.
#
# DUE TRAPPOLE, ENTRAMBE VERIFICATE SUL POSTO:
#  - VERTEX e SEQEND non sono entita': sono le parti di una POLYLINE, che GDAL
#    (come AutoCAD) legge come un oggetto solo. Contandoli si otteneva
#    1 227 582 contro 468 622, cioe' un allarme continuo su un file sano;
#  - i blocchi NON vanno espansi. Con DXF_INLINE_BLOCKS=TRUE (il default) GDAL
#    sostituisce ogni INSERT con la geometria del blocco e i conti non tornano
#    piu' per costruzione: 468 622 INSERT diventano un numero diverso di
#    feature. Serve anche leggere il layer OGR "entities" per nome: il primo
#    layer e' "blocks", cioe' le definizioni, e sono 24.
import collections
import io
import os

# I limiti del sistema di riferimento nazionale MN95/LV95, arrotondati verso
# l'esterno. Un disegno che esce di qui non e' "un po' spostato": e' in un altro
# sistema di coordinate, o ha un oggetto con coordinate a zero che si porta
# dietro l'estensione.
LV95_EST = (2480000.0, 2840000.0)
LV95_NORD = (1070000.0, 1300000.0)

SOTTORECORD = ("VERTEX", "SEQEND")


class Esito(object):
    """Il risultato del confronto. 'problemi' vuoto = tutto a posto."""

    def __init__(self):
        self.scritte = 0
        self.lette = 0
        self.per_layer_scritte = {}
        self.per_layer_lette = {}
        self.scarti = []            # (layer, scritte, lette)
        self.non_dichiarati = []    # layer con entita' ma assenti dalla tabella LAYER
        self.vuoti = []             # layer dichiarati e senza entita' (informativo)
        self.estensione = None      # (minx, miny, maxx, maxy)
        self.problemi = []
        self.avvisi = []
        self.messaggi_gdal = []     # quello che GDAL segnala per conto suo
        self.leggibile = False

    @property
    def ok(self):
        return self.leggibile and not self.problemi


def conta_scritte(percorso):
    """Le entita' della sezione ENTITIES, per layer, come le abbiamo scritte.

    Lettura a COPPIE codice/valore, non riga per riga: il valore di un gruppo
    puo' essere "0" e una lettura riga-per-riga lo scambierebbe per l'inizio di
    una nuova entita' - difetto vero, trovato in _count_dxf_entities_stream."""
    per_layer = collections.Counter()
    per_tipo = collections.Counter()
    dentro = False
    tipo = None
    layer = None
    with io.open(percorso, "r", encoding="latin-1", errors="replace") as f:
        while True:
            codice = f.readline()
            if not codice:
                break
            valore = f.readline()
            if not valore:
                break
            codice = codice.strip()
            valore = valore.strip()
            if codice == "0":
                if valore == "SECTION":
                    continue
                if valore == "ENDSEC":
                    if dentro:
                        break            # la sezione ENTITIES e' finita
                    continue
                if tipo and dentro and tipo not in SOTTORECORD:
                    per_layer[layer or "(senza layer)"] += 1
                    per_tipo[tipo] += 1
                tipo = valore if dentro else None
                layer = None
            elif codice == "2" and valore == "ENTITIES":
                dentro = True
            elif codice == "8" and dentro:
                layer = valore
    if tipo and dentro and tipo not in SOTTORECORD:
        per_layer[layer or "(senza layer)"] += 1
        per_tipo[tipo] += 1
    return per_layer, per_tipo


def layer_dichiarati(percorso):
    """I nomi della tabella LAYER, cioe' i layer che il file DICHIARA.

    Un'entita' su un layer non dichiarato si disegna lo stesso, ma con i
    valori predefiniti: colore, spessore e tipo di linea decisi da chi apre il
    file invece che da noi. E' il modo silenzioso di perdere la conformita'."""
    nomi = []
    dentro_tabelle = False
    dentro_layer = False
    tipo = None
    with io.open(percorso, "r", encoding="latin-1", errors="replace") as f:
        while True:
            codice = f.readline()
            if not codice:
                break
            valore = f.readline()
            if not valore:
                break
            codice = codice.strip()
            valore = valore.strip()
            if codice == "2" and valore == "TABLES":
                dentro_tabelle = True
            elif codice == "2" and valore == "ENTITIES":
                break
            elif codice == "0" and dentro_tabelle:
                if valore == "TABLE":
                    tipo = "?"
                elif valore == "ENDTAB":
                    dentro_layer = False
                tipo = valore
            elif codice == "2" and tipo == "TABLE" and dentro_tabelle:
                dentro_layer = (valore == "LAYER")
                tipo = None
            elif codice == "2" and dentro_layer and tipo == "LAYER":
                nomi.append(valore)
    return nomi


def conta_lette(percorso, gdal=None, ogr=None):
    """Le feature che GDAL legge, per layer, piu' l'estensione complessiva.

    Ritorna (per_layer, estensione, errore, messaggi). I moduli si iniettano per
    i test: fuori da QGIS osgeo puo' non esserci, e il resto del modulo deve
    restare provabile lo stesso."""
    if gdal is None or ogr is None:
        try:
            from osgeo import gdal as _g, ogr as _o
        except ImportError as e:
            return collections.Counter(), None, "GDAL non disponibile: %s" % e, []
        gdal, ogr = _g, _o

    # I messaggi che GDAL scrive per conto suo valgono quanto il conteggio:
    # sulla POLYLINE senza SEQEND dice riga e file. Senza raccoglierli
    # finirebbero su stderr, cioe' in nessun posto che l'utente guardi.
    messaggi = []

    def _raccogli(classe, numero, testo):
        messaggi.append("%s (%s)" % (testo.strip(), numero))

    # L'opzione e' GLOBALE per il processo: si rimette com'era, altrimenti si
    # cambierebbe il comportamento del driver DXF per tutto QGIS.
    prima = gdal.GetConfigOption("DXF_INLINE_BLOCKS", None)
    gdal.SetConfigOption("DXF_INLINE_BLOCKS", "FALSE")
    gdal.PushErrorHandler(_raccogli)
    try:
        sorgente = ogr.Open(percorso)
        if sorgente is None:
            return (collections.Counter(), None,
                    "GDAL non riesce ad aprire il file come DXF", messaggi)
        strato = sorgente.GetLayerByName("entities")
        if strato is None:
            return (collections.Counter(), None,
                    "il DXF non ha una sezione ENTITIES leggibile", messaggi)
        per_layer = collections.Counter()
        minx = miny = float("inf")
        maxx = maxy = float("-inf")
        for feature in strato:
            per_layer[feature.GetField("Layer") or "(senza layer)"] += 1
            geometria = feature.GetGeometryRef()
            if geometria is not None and not geometria.IsEmpty():
                x0, x1, y0, y1 = geometria.GetEnvelope()
                minx = min(minx, x0); maxx = max(maxx, x1)
                miny = min(miny, y0); maxy = max(maxy, y1)
        sorgente = None
        estensione = None if minx == float("inf") else (minx, miny, maxx, maxy)
        return per_layer, estensione, "", messaggi
    except Exception as e:                  # anche gli errori nativi di GDAL
        return collections.Counter(), None, str(e), messaggi
    finally:
        gdal.PopErrorHandler()
        gdal.SetConfigOption("DXF_INLINE_BLOCKS", prima)


def verifica(percorso, gdal=None, ogr=None):
    """Il confronto completo. Ritorna un Esito."""
    esito = Esito()
    if not percorso or not os.path.isfile(percorso):
        esito.problemi.append("il DXF non esiste: %s" % (percorso or "(vuoto)"))
        return esito

    scritte, _tipi = conta_scritte(percorso)
    esito.per_layer_scritte = dict(scritte)
    esito.scritte = sum(scritte.values())

    lette, estensione, errore, messaggi = conta_lette(percorso, gdal, ogr)
    esito.messaggi_gdal = messaggi
    if errore:
        # Non poter rileggere il file e' esso stesso il risultato: e' quello che
        # succederebbe a chi lo apre.
        esito.problemi.append("GDAL non rilegge il DXF: %s" % errore)
        return esito
    esito.leggibile = True
    esito.per_layer_lette = dict(lette)
    esito.lette = sum(lette.values())
    esito.estensione = estensione

    for nome in sorted(set(scritte) | set(lette)):
        a, b = scritte.get(nome, 0), lette.get(nome, 0)
        if a != b:
            esito.scarti.append((nome, a, b))
    if esito.scarti:
        persi = sum(a - b for _n, a, b in esito.scarti if a > b)
        esito.problemi.append(
            "GDAL rilegge %d entita' su %d: %d scartate, su %d layer. "
            "Un'entita' che un lettore indipendente scarta e' un'entita' che "
            "AutoCAD non disegnera'." % (esito.lette, esito.scritte, persi,
                                         len(esito.scarti)))

    dichiarati = set(layer_dichiarati(percorso))
    if not dichiarati and any(lette.values()):
        # IL CONTROLLO SALTAVA IN SILENZIO. "Nessun layer dichiarato" veniva
        # trattato come "niente da confrontare", e il file passava: ma un DXF
        # con entita' e senza tabella LAYER e' esso stesso non conforme -
        # colore, spessore e tipo di linea di OGNI entita' li deciderebbe chi
        # apre il file. E' il caso peggiore di quello che il controllo cerca,
        # ed era l'unico a non essere segnalato.
        esito.problemi.append(
            "il file non ha la tabella LAYER: nessuno dei layer usati e' "
            "dichiarato, quindi colore, spessore e tipo di linea li decide "
            "chi apre il file. Un DXF cosi' non e' conforme.")
    if dichiarati:
        con_entita = set(n for n, v in lette.items() if v)
        mancanti = sorted(con_entita - dichiarati - set(["(senza layer)"]))
        if mancanti:
            esito.non_dichiarati = mancanti
            esito.problemi.append(
                "entita' su %d layer non dichiarati nella tabella LAYER (%s): "
                "colore, spessore e tipo di linea li decide chi apre il file, "
                "non noi." % (len(mancanti), ", ".join(mancanti[:6])))
        esito.vuoti = sorted(dichiarati - con_entita)

    if estensione:
        minx, miny, maxx, maxy = estensione
        fuori = (minx < LV95_EST[0] or maxx > LV95_EST[1]
                 or miny < LV95_NORD[0] or maxy > LV95_NORD[1])
        if fuori:
            esito.problemi.append(
                "il disegno esce dai limiti di MN95: E %.0f..%.0f, N %.0f..%.0f. "
                "Non e' uno spostamento, e' un altro sistema di coordinate - "
                "oppure un oggetto con coordinate a zero."
                % (minx, maxx, miny, maxy))
    return esito


def righe_di_esito(esito, quanti_scarti=8):
    """L'esito come righe di testo pronte per la console del plugin."""
    righe = []
    if not esito.leggibile:
        righe.extend("   ❌ %s" % p for p in esito.problemi)
        return righe
    righe.append("   🔁 Riletto da GDAL: %d entità su %d scritte"
                 % (esito.lette, esito.scritte))
    if esito.estensione:
        minx, miny, maxx, maxy = esito.estensione
        righe.append("   🗺️ Estensione: E %.0f..%.0f  N %.0f..%.0f"
                     % (minx, maxx, miny, maxy))
    for nome, a, b in esito.scarti[:quanti_scarti]:
        righe.append("   ❌ layer %s: scritte %d, rilette %d" % (nome, a, b))
    if len(esito.scarti) > quanti_scarti:
        righe.append("   ❌ ...e altri %d layer con scarto"
                     % (len(esito.scarti) - quanti_scarti))
    for p in esito.problemi:
        if not p.startswith("GDAL rilegge"):
            righe.append("   ❌ %s" % p)
    for m in esito.messaggi_gdal[:5]:
        righe.append("   ⚠️ GDAL segnala: %s" % m)
    if len(esito.messaggi_gdal) > 5:
        righe.append("   ⚠️ ...e altri %d messaggi da GDAL"
                     % (len(esito.messaggi_gdal) - 5))
    if esito.vuoti:
        # Non e' un difetto: alcuni layer sono dichiarati apposta e spenti.
        righe.append("   ℹ️ Layer dichiarati e senza entità: %d (%s%s)"
                     % (len(esito.vuoti), ", ".join(esito.vuoti[:5]),
                        ", ..." if len(esito.vuoti) > 5 else ""))
    if esito.ok:
        righe.append("   ✅ Nessuno scarto: ogni entità scritta è stata riletta")
    return righe
