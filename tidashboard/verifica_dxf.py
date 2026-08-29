# Il DXF prodotto, riletto da GDAL: un secondo parere su quello che abbiamo
# scritto.
#
# PERCHE' SERVE UN SECONDO LETTORE. Il controllo strutturale che facevamo prima
# (controlla_struttura, qui sotto) legge il file con il nostro stesso codice:
# se sbagliamo a
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
import math
import os

# I limiti del sistema di riferimento nazionale MN95/LV95, arrotondati verso
# l'esterno. Un disegno che esce di qui non e' "un po' spostato": e' in un altro
# sistema di coordinate, o ha un oggetto con coordinate a zero che si porta
# dietro l'estensione.
LV95_EST = (2480000.0, 2840000.0)
LV95_NORD = (1070000.0, 1300000.0)

SOTTORECORD = ("VERTEX", "SEQEND")


# Quanto puo' spostarsi un arco per colpa delle cifre con cui e' scritto,
# prima che sia un problema. Un decimo di millimetro sul terreno: due ordini
# di grandezza sotto la tolleranza di un punto di confine, e comunque
# invisibile su carta a qualunque delle otto scale del cap. 1.5.1.
SCOSTAMENTO_ARCO_MAX = 0.0001


def _cifre_decimali(testo):
    return len(testo.split(".")[1]) if "." in testo else 0


def archi_imprecisi(percorso, soglia=SCOSTAMENTO_ARCO_MAX):
    """Gli archi scritti con troppe poche cifre per la loro corda.

    COSA SI PUO' CONTROLLARE, e cosa no. Nel DXF non c'e' l'arco di partenza:
    c'e' solo il bulge, cioe' quello che abbiamo scritto noi. Confrontarlo con
    "l'originale" e' impossibile da qui. Cio' che invece si controlla dal file
    da solo e' se le cifre scritte BASTANO per quella corda.

    Il bulge e' tan(theta/4) e vale la relazione esatta

        saetta = bulge * corda / 2

    quindi mezza unita' dell'ultima cifra scritta sposta l'arco di
    (0.5 * 10^-cifre) * corda / 2. Lineare, e senza le divergenze del raggio -
    che per un arco dolce tende all'infinito e da' numeri enormi per uno
    scostamento invisibile.

    PERCHE' ESISTE. Il bulge usava la stessa precisione delle coordinate LV95,
    tre decimali, che per un metro e' il millimetro e per un rapporto fra 0 e 1
    e' pochissimo: fino a 37 mm di scostamento su una corda di 150 m, e due
    archi del comune di prova avevano un bulge sotto 0.0005, cioe' scritti come
    ZERO - due archi diventati segmenti retti. Il difetto non poteva emergere
    dal confronto con GDAL, che rilegge fedelmente il numero impreciso che gli
    abbiamo dato: un secondo parere vede solo cio' che sta nel file.

    Ritorna [(scostamento_m, corda_m, bulge, cifre)], i peggiori per primi."""
    trovati = []
    with open(percorso, "r", encoding="latin-1", errors="replace") as f:
        tipo = None
        x = y = None
        bulge = None
        cifre = 0
        precedente = None        # (x, y, bulge_testo, cifre) del vertice prima
        while True:
            codice = f.readline()
            if not codice:
                break
            valore = f.readline()
            if not valore:
                break
            codice, valore = codice.strip(), valore.strip()
            if codice == "0":
                if tipo == "VERTEX" and x is not None and y is not None:
                    if precedente is not None and precedente[2]:
                        corda = math.hypot(x - precedente[0], y - precedente[1])
                        errore = 0.5 * 10 ** (-precedente[3]) * corda / 2.0
                        if errore > soglia:
                            trovati.append((errore, corda, precedente[2],
                                            precedente[3]))
                    precedente = (x, y, bulge, cifre)
                elif valore != "VERTEX":
                    precedente = None    # la polilinea e' finita
                tipo = valore
                x = y = None
                bulge = None
                cifre = 0
            elif tipo == "VERTEX":
                if codice == "10":
                    x = float(valore)
                elif codice == "20":
                    y = float(valore)
                # Un bulge nullo non e' un arco: e' il caso normale, e
                # tenerlo separato dal codice 42 rendeva la condizione
                # annidata senza dire nulla di piu'.
                elif codice == "42" and abs(float(valore)) > 1e-12:
                    bulge = valore
                    cifre = _cifre_decimali(valore)
    trovati.sort(reverse=True)
    return trovati


# Quanto puo' spostarsi una coordinata fra l'ITF e il DXF prima che sia un
# problema. Un decimo di millimetro: sia l'ITF sia il DXF scrivono i metri con
# tre decimali, quindi una coordinata riportata fedelmente e' IDENTICA e la
# deviazione e' zero esatto. La soglia esiste per il giorno in cui qualcuno
# introducesse una trasformazione, non perche' ci si aspetti uno scarto.
TOLLERANZA_COORDINATE = 0.0001

# Oltre questo, due punti non sono "lo stesso punto spostato": sono due punti
# diversi. Serve perche' il DXF contiene anche elementi che il piano COLLOCA -
# i simboli delle trame di riempimento, le etichette spostate
# dall'anticollisione - e accoppiarli al punto sorgente piu' vicino misurerebbe
# una distanza che non e' una deviazione.
RAGGIO_ACCOPPIAMENTO = 0.01

# Quota minima di coordinate riportate IDENTICHE perche' la conversione sia
# credibile.
#
# PERCHE' SERVE, e non basta lo scarto massimo. Provando a ingannare il
# controllo con guasti veri, uno scostamento GRANDE gli sfugge: se tutte le
# coordinate si spostano di un metro, nessuna trova piu' il proprio punto di
# origine entro il raggio, tutte finiscono fra le "collocate dal piano" e lo
# scarto massimo torna 0.0010 m - un numero rassicurante e falso. Il segnale
# vero non e' lo scarto: e' il CROLLO delle coordinate identiche.
#
# La soglia non e' scelta a occhio. Misurata su due comuni interi:
#     5112000101   65 925 su  90 735 = 72.7%
#     5251000201   98 731 su 130 949 = 75.4%
# contro i casi guasti costruiti apposta:
#     tutto spostato di 5 mm            0.0%
#     tutto spostato di 1 m             0.6%
#     arrotondato al centimetro         0.7%
#     arrotondato al decimetro          0.008%
# Fra il 73% del sano e l'1% del rotto c'e' un abisso: meta' e' lontana da
# tutt'e due.
QUOTA_IDENTICHE_MINIMA = 0.5


def coordinate_itf(percorso):
    """Tutte le coordinate LV95 di un ITF, senza bisogno del modello.

    L'INTERLIS 1 scrive le coordinate in chiaro: nei record STPT/LIPT/ARCP
    delle geometrie lineari, e dentro l'OBJE per i punti singoli. Non serve
    quindi il modello compilato (.imd) che il driver GDAL pretenderebbe: si
    cercano le COPPIE DI TOKEN CONSECUTIVI in cui il primo cade nella gamma
    est e il secondo nella gamma nord di MN95. Le due gamme non si
    sovrappongono a nessun altro attributo del modello - le date sono
    otto cifre, gli identificatori interi fuori scala - quindi il
    riconoscimento non ha bisogno di sapere che cosa sta leggendo."""
    punti = []
    with open(percorso, "r", encoding="latin-1", errors="replace") as f:
        for riga in f:
            token = riga.split()
            for i in range(len(token) - 1):
                try:
                    x = float(token[i])
                except ValueError:
                    continue
                if not (LV95_EST[0] <= x <= LV95_EST[1]):
                    continue
                try:
                    y = float(token[i + 1])
                except ValueError:
                    continue
                if LV95_NORD[0] <= y <= LV95_NORD[1]:
                    punti.append((x, y))
    return punti


def deviazione_coordinate(percorso_itf, percorso_dxf,
                          tolleranza=TOLLERANZA_COORDINATE,
                          raggio=RAGGIO_ACCOPPIAMENTO):
    """Di quanto la conversione ha spostato le coordinate del file di origine.

    Ritorna un dizionario con max_x, max_y (metri), quante coordinate sono
    identiche, quante spostate entro il raggio, e quante il piano COLLOCA da
    se'. L'ultima categoria non e' un difetto: il DXF contiene i simboli delle
    trame di riempimento e le etichette che l'anticollisione sposta apposta,
    che nell'ITF non esistono a quelle coordinate.

    MISURATO sul comune di prova, e il risultato e' la ragione per cui questo
    controllo ha senso: 65 925 coordinate IDENTICHE, e nelle fasce "entro 1 mm"
    e "entro 1 cm" ZERO. Non c'e' una fascia intermedia - o la coordinata e'
    la stessa, o e' un altro punto. E' esattamente la firma di una conversione
    che non tocca le coordinate, ed e' cio' che questo controllo permette di
    dimostrare invece di affermare.

    IL LIMITE, dichiarato: oltre il raggio non si distingue una coordinata
    spostata da un punto diverso. Un ipotetico spostamento di dieci centimetri
    finirebbe fra i "collocati" invece che fra gli "spostati": per questo il
    loro numero viene riportato, cosi' che una sua variazione si veda."""
    griglia = collections.defaultdict(list)
    for x, y in coordinate_itf(percorso_itf):
        griglia[(int(x), int(y))].append((x, y))

    esito = {"max_x": 0.0, "max_y": 0.0, "identiche": 0, "spostate": 0,
             "collocate": 0, "peggiore": None}
    per_layer = collections.Counter()
    identiche_layer = collections.Counter()
    with open(percorso_dxf, "r", encoding="latin-1", errors="replace") as f:
        tipo = layer = None
        x = None
        while True:
            codice = f.readline()
            if not codice:
                break
            valore = f.readline()
            if not valore:
                break
            codice, valore = codice.strip(), valore.strip()
            if codice == "0":
                tipo = valore
            elif codice == "8":
                layer = valore
            elif codice == "10":
                try:
                    x = float(valore)
                except ValueError:
                    x = None
            elif codice == "20" and x is not None:
                try:
                    y = float(valore)
                except ValueError:
                    x = None
                    continue
                # Solo la geometria: il punto di allineamento di un testo
                # (gruppo 11) e' calcolato, non riportato.
                if tipo in ("VERTEX", "POINT", "INSERT") \
                        and LV95_EST[0] <= x <= LV95_EST[1] \
                        and LV95_NORD[0] <= y <= LV95_NORD[1]:
                    vicini = []
                    for i in (-1, 0, 1):
                        for j in (-1, 0, 1):
                            vicini.extend(griglia.get((int(x) + i, int(y) + j), ()))
                    scelto = None
                    if vicini:
                        scelto = min(vicini, key=lambda q: (q[0] - x) ** 2
                                     + (q[1] - y) ** 2)
                    per_layer[layer] += 1
                    if scelto is None:
                        esito["collocate"] += 1
                    else:
                        dx, dy = abs(scelto[0] - x), abs(scelto[1] - y)
                        if dx == 0.0 and dy == 0.0:
                            esito["identiche"] += 1
                            identiche_layer[layer] += 1
                        elif dx <= raggio and dy <= raggio:
                            esito["spostate"] += 1
                            if max(dx, dy) > max(esito["max_x"], esito["max_y"]):
                                esito["peggiore"] = (layer, tipo, dx, dy)
                            esito["max_x"] = max(esito["max_x"], dx)
                            esito["max_y"] = max(esito["max_y"], dy)
                        else:
                            esito["collocate"] += 1
                x = None
    confrontate = esito["identiche"] + esito["spostate"] + esito["collocate"]
    esito["confrontate"] = confrontate
    esito["quota_identiche"] = (float(esito["identiche"]) / confrontate
                                if confrontate else 0.0)
    esito["oltre_tolleranza"] = (esito["max_x"] > tolleranza
                                 or esito["max_y"] > tolleranza)
    # Il secondo verdetto, indipendente dal primo: vedi QUOTA_IDENTICHE_MINIMA.
    #
    # E VALE ANCHE QUANDO NON C'E' NIENTE DA CONFRONTARE. La prima versione
    # chiedeva "confrontate > 0", e scambiando X con Y nel DXF - una prova
    # costruita apposta per ingannarlo - i punti uscivano dalle gamme di MN95,
    # non ne restava nessuno, e "zero confronti" usciva come "Max deviation
    # 0.0000 m": una misura VUOTA riportata come esito buono, sul file piu'
    # rotto di tutti. Un controllo che non ha potuto controllare niente non ha
    # trovato niente di buono.
    esito["troppe_non_coincidono"] = \
        esito["quota_identiche"] < QUOTA_IDENTICHE_MINIMA

    # La ripartizione per layer, dal peggiore in giu'. Serve a DIRE DOVE quando
    # un allarme e' gia' scattato, non a farne scattare uno suo.
    #
    # Ci avevo messo un allarme autonomo: fuori dalla banda 10%-99.5% il layer
    # e' "a meta'", quindi sospetto. L'idea veniva da una misura vera - su due
    # comuni interi i layer stanno o in alto o in basso, mai in mezzo - ma il
    # margine e' risultato di due decimi di punto: il layer sano piu' basso sta
    # al 99.7% e la soglia al 99.5%, tarati su due soli comuni. Un allarme
    # cosi' stretto, il giorno che sbaglia, sbaglia su una consegna buona, e un
    # controllo che grida al lupo lo si spegne - portandosi via anche la parte
    # che funziona. Il caso che quell'allarme copriva (una PARTE dei punti di
    # un layer spostata di molto, il resto esatto) non ha nemmeno un meccanismo
    # noto che lo produca: gli errori veri del convertitore sono sistematici,
    # e quelli si vedono nello scarto massimo.
    quote = []
    for nome, quanti in per_layer.items():
        if quanti < 20:
            continue                 # troppo pochi per dire qualcosa
        quote.append((nome, identiche_layer[nome] / float(quanti), quanti))
    quote.sort(key=lambda t: t[1])
    esito["per_layer"] = quote
    return esito


def righe_deviazione(dev):
    """Le righe da mostrare, nella forma richiesta."""
    righe = ["Max X deviation: %.4f m" % dev["max_x"],
             "Max Y deviation: %.4f m" % dev["max_y"],
             "coordinate identiche: %d di %d (%.1f%%)   spostate: %d   "
             "collocate dal piano: %d"
             % (dev["identiche"], dev.get("confrontate", 0),
                100.0 * dev.get("quota_identiche", 0.0), dev["spostate"],
                dev["collocate"])]
    if not dev.get("confrontate"):
        righe.append(
            "ATTENZIONE: nessuna coordinata confrontabile. Nel DXF non c'e' "
            "un solo punto nelle gamme di MN95, oppure nell'ITF non ce n'e' "
            "nessuna: il controllo non ha potuto verificare niente, e questo "
            "NON vuol dire che sia tutto a posto.")
    elif dev.get("troppe_non_coincidono"):
        # Si dice la cosa vera, non lo scarto massimo: quando quasi nulla
        # coincide, quel numero e' calcolato su una manciata di accoppiamenti
        # casuali e vale meno di zero, perche' rassicura.
        righe.append(
            "ATTENZIONE: solo il %.1f%% delle coordinate si ritrova identico "
            "nel DXF. Lo scarto massimo qui sopra e' calcolato sui pochi punti "
            "accoppiati e NON misura lo spostamento vero."
            % (100.0 * dev["quota_identiche"]))
    if dev.get("oltre_tolleranza") or dev.get("troppe_non_coincidono"):
        # Solo qui: a referto sano queste righe sarebbero una parete di numeri
        # tutti uguali a 100.0%, e nessuno le leggerebbe piu'.
        for nome, quota, quanti in dev.get("per_layer", [])[:5]:
            righe.append("   layer %s: %.1f%% identiche su %d coordinate"
                         % (nome, 100.0 * quota, quanti))
    return righe


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


# Quanto si legge in testa e in coda per il controllo strutturale. Un DXF di un
# comune arriva a decine di MB: la SECTION sta nelle prime righe e l'EOF
# nell'ultima, e leggere tutto per trovarle sarebbe uno spreco.
RIGHE_IN_TESTA = 80
BYTE_IN_CODA = 8000
DIMENSIONE_MINIMA = 200
LAYER_NEL_CAMPIONE = 12


def conta_entita(percorso, quanti_layer=LAYER_NEL_CAMPIONE):
    """I tipi di entita' nella sezione ENTITIES, contati leggendo il file riga
    per riga senza caricarlo in memoria.

    IL DXF E' FATTO DI COPPIE: una riga col codice, una col valore. Non tenerne
    il conto e guardare ogni riga per conto suo sembra funzionare finche' non
    capita un VALORE uguale a "0" - e capita di continuo: ogni VERTEX 2d
    finisce con 70/0, ogni HATCH con 98/0. Quel valore veniva scambiato per il
    codice di una nuova entita', la riga dopo (il vero codice) veniva mangiata
    come se fosse un tipo, e il conteggio non si risincronizzava piu': tre
    VERTEX e un SEQEND risultavano una entita' sola."""
    conteggio = {}
    totale = 0
    layer, visti = [], set()
    dentro = False
    try:
        with open(str(percorso), "r", encoding="latin-1",
                     errors="replace") as f:
            for riga in f:
                codice = riga.strip()
                grezzo = f.readline()
                if not grezzo:
                    break
                valore = grezzo.strip()
                if not dentro:
                    if valore == "ENTITIES":
                        dentro = True
                    continue
                if codice == "0" and valore == "ENDSEC":
                    break
                if codice == "0":
                    conteggio[valore] = conteggio.get(valore, 0) + 1
                    totale += 1
                elif codice == "8":
                    if valore and valore not in visti and len(visti) < quanti_layer:
                        visti.add(valore)
                        layer.append(valore)
    except OSError as e:
        return {"_errore": str(e), "_totale": 0, "_layer": []}
    conteggio["_totale"] = totale
    conteggio["_layer"] = layer
    return conteggio


def controlla_struttura(percorso):
    """Controlli strutturali minimi su un DXF appena esportato: esiste, non e'
    vuoto, ha SECTION ed EOF, contiene almeno un'entita'. Ritorna
    (va_bene, righe) con le righe gia' pronte per la console.

    NON RIPARA NULLA. I difetti noti - LTYPE a lunghezza 0, $HANDSEED
    segnaposto - sono risolti alla fonte nel writer Java. Serve solo a far
    emergere subito un file strutturalmente incompleto, invece di scoprirlo
    aprendolo in AutoCAD.

    E' un controllo che legge il file CON IL NOSTRO STESSO CODICE, quindi non
    sostituisce la rilettura con GDAL (vedi verifica): sono due mestieri
    diversi, e questo e' il piu' debole dei due."""
    righe = []
    percorso = str(percorso)
    if not os.path.isfile(percorso):
        return False, ["   ❌ DXF non creato: %s" % percorso]
    dimensione = os.path.getsize(percorso)
    righe.append("   📏 Dimensione DXF: %d byte" % dimensione)
    if dimensione < DIMENSIONE_MINIMA:
        righe.append("   ❌ DXF sospettosamente piccolo (probabile file "
                     "vuoto/corrotto).")
        return False, righe

    testa, coda = [], []
    try:
        with open(percorso, "r", encoding="latin-1", errors="replace") as f:
            for i, riga in enumerate(f):
                if i >= RIGHE_IN_TESTA:
                    break
                testa.append(riga.rstrip("\n"))
            f.seek(max(0, dimensione - BYTE_IN_CODA))
            coda = f.read().splitlines()[-40:]
    except OSError as e:
        righe.append("   ⚠️ Lettura DXF fallita: %s" % e)
        return False, righe

    if not any(r.strip() == "SECTION" for r in testa):
        righe.append("   ⚠️ Nessuna SECTION trovata in testa al DXF "
                     "(formato inatteso).")
    if any(r.strip() == "EOF" for r in coda + testa):
        righe.append("   ✅ EOF presente")
    else:
        righe.append("   ⚠️ EOF assente in coda al DXF (file troncato?).")

    conteggio = conta_entita(percorso)
    if "_errore" in conteggio:
        righe.append("   ⚠️ Analisi entità fallita: %s" % conteggio["_errore"])
        return True, righe
    totale = conteggio.pop("_totale", 0)
    campione = conteggio.pop("_layer", [])
    righe.append("   📊 Entità in ENTITIES: %d" % totale)
    if totale <= 0:
        righe.append("   ❌ Nessuna entità geometrica trovata nel DXF.")
        return False, righe
    primi = sorted(conteggio.items(), key=lambda kv: -kv[1])[:8]
    righe.append("   📊 Tipi principali: "
                 + ", ".join("%s=%d" % kv for kv in primi))
    if campione:
        righe.append("   📋 Layer (campione): " + ", ".join(campione))
    return True, righe


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
    with open(percorso, "r", encoding="latin-1", errors="replace") as f:
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
    with open(percorso, "r", encoding="latin-1", errors="replace") as f:
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
            from osgeo import gdal as _g
            from osgeo import ogr as _o
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

    # Gli archi scritti con troppe poche cifre per la loro corda: un
    # controllo sul NUMERO che abbiamo messo nel file, non sull'entita' che
    # GDAL rilegge. E' l'unica famiglia di difetti che il secondo parere non
    # puo' vedere - GDAL rilegge fedelmente anche un bulge impreciso.
    imprecisi = archi_imprecisi(percorso)
    if imprecisi:
        peggiore, corda, bulge, cifre = imprecisi[0]
        esito.problemi.append(
            "%d archi scritti con troppe poche cifre: il peggiore si sposta di "
            "%.1f mm (bulge %s, %d decimali, corda %.1f m). Con quel numero di "
            "cifre l'arco che il CAD ricostruisce non e' quello misurato."
            % (len(imprecisi), peggiore * 1000, bulge, cifre, corda))

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
        con_entita = {n for n, v in lette.items() if v}
        mancanti = sorted(con_entita - dichiarati - {"(senza layer)"})
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
