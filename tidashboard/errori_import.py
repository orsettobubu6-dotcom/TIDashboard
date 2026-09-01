# TIDashboard - dati della misurazione ufficiale svizzera in QGIS
# Copyright (C) 2026 Gabriele Peverelli
#
# Questo programma e' software libero: lo si puo' ridistribuire e modificare
# secondo i termini della GNU General Public License pubblicata dalla Free
# Software Foundation, versione 2 o (a scelta) una successiva. Il testo si
# trova nel file LICENSE distribuito insieme al programma.

# Gli errori che ili2gpkg segnala durante l'importazione.
#
# QUASI TUTTO QUI DENTRO E' TESTO. Riconoscere una riga di log, ritrovare nel
# file ITF le due righe OBJE in conflitto, cavarne le coordinate, misurare la
# distanza e dire se e' un doppione o una collisione di numerazione: sono
# espressioni regolari e letture di file, niente QGIS, niente finestra. La
# sola parte che ha bisogno di QGIS sono i cinquanta righe che mettono i punti
# sulla mappa.
#
# Finche' stava dentro la finestra, per provare una qualsiasi di queste cose
# bisognava costruire un dialogo: infatti l'unica parte provata davvero era
# l'euristica delle coordinate, chiamata come metodo statico dalla classe.
#
# LA DIAGNOSI E' LA COSA CHE VALE, e non e' ovvia. Due punti di confine con lo
# stesso identificativo possono essere due cose opposte: lo stesso punto
# registrato due volte (un doppione da togliere) oppure due punti veri a cui e'
# stato dato per sbaglio lo stesso numero (una collisione di numerazione). Il
# log di Java non lo dice; la distanza fra i due sì. Sotto il metro e' un
# doppione, sopra e' una collisione - e sono due correzioni diverse per chi
# tiene l'ITF.
#
# LA GRAVITA' DELLE RIGHE SI DEDUCE DALL'EMOJI, come per verifica_dxf.py: qui
# Qgis non c'e', quindi il registro riceve una stringa e basta, e la traduzione
# da "⚠️" a Qgis.Warning la fa la finestra in un posto solo
# (TIDashboardDialog._livello_di_riga). Passare un livello numerico da qui
# significherebbe conoscere Qgis, che e' esattamente cio' che rende provabile
# questo modulo senza QGIS.
import collections
import re

# "Error: line 1183131: MD01MUTI7MN95.Beni_immobili.Punto_di_confine: tid
# 46560: Unique constraint MD01MUTI7MN95.Beni_immobili.Punto_di_confine.
# Constraint2 is violated! Values TI63201, 140602 already exist in Object:
# 40497" - riga vera, da una consegna vera.
RE_UNICITA = re.compile(
    r"^Error: line (\d+): ([\w.]+): tid (\d+): "
    r"Unique constraint ([\w.]+) is violated! "
    r"Values (.+) already exist in Object: (\d+)$"
)

# I messaggi che la coordinata ce l'hanno gia' dentro, e che prima restavano
# semplici righe di log: "Warning: arc is straight at (2719339.225,
# 1081435.757, NaN)". Sono geolocalizzati all'origine: non c'e' bisogno di
# andarli a cercare nell'ITF come per i vincoli di unicita'.
RE_LIVELLO = re.compile(r"^(Error|Warning): (.+)$")

# Sotto questa distanza i due oggetti sono lo stesso punto fisico.
METRI_STESSO_PUNTO = 1.0

# Oltre questo numero di righe la scansione dell'ITF si ferma. Un ITF di
# produzione supera il milione di righe; il limite evita che un file
# malformato faccia girare a vuoto per sempre.
RIGHE_MAX = 3_000_000

Violazione = collections.namedtuple(
    "Violazione", ("riga", "classe", "tid", "vincolo", "valori", "tid_esistente"))


def _zitto(_testo, _livello=None):
    """Registro di riposo: chi chiama senza log non stampa niente."""


def leggi_riga(riga):
    """Che cosa dice questa riga del log di ili2gpkg.

    Restituisce ("unicita", Violazione), oppure ("punto", dict) per un
    messaggio di validazione che porta con se' una coordinata, oppure None.
    """
    pulita = riga.strip()
    unicita = RE_UNICITA.match(pulita)
    if unicita:
        return ("unicita", Violazione(
            riga=int(unicita.group(1)), classe=unicita.group(2),
            tid=unicita.group(3), vincolo=unicita.group(4),
            valori=unicita.group(5), tid_esistente=unicita.group(6)))

    livello = RE_LIVELLO.match(pulita)
    if not livello:
        return None
    coordinata = coordinate_lv95(riga)
    if not coordinata:
        return None
    return ("punto", {
        "livello": "errore" if livello.group(1) == "Error" else "avviso",
        "tipo": "validazione",
        "messaggio": livello.group(2).strip(),
        "x": coordinata[0], "y": coordinata[1], "tid": "", "riga": 0,
    })


def coordinate_lv95(riga_obje):
    """Euristica indipendente dalla classe ILI.

    RESTA UN'EURISTICA, pensata SOLO per arricchire i messaggi di errore
    (coordinate indicative nei log), non per ricostruire geometrie vere:
    cerca nella riga una COPPIA di numeri con la virgola che compaiano
    consecutivamente sulla STESSA riga e cadano, nell'ordine, negli intervalli
    LV95 svizzeri E [2'480'000, 2'840'000] e N [1'070'000, 1'310'000]
    (estremi nazionali con margine).

    La versione precedente prendeva i primi due numeri "plausibili" dovunque
    nella riga, con intervalli piu' larghi e SENZA richiedere l'adiacenza:
    i falsi positivi su quote e attributi numerici erano facili (una quota
    1234567.89 seguita da un valore 2450000.0). Piu' affidabile che assumere
    la posizione esatta del campo Geometria, che cambia da classe a classe.
    """
    numeri = re.findall(r"-?\d+\.\d+", riga_obje)
    for i in range(len(numeri) - 1):
        est, nord = float(numeri[i]), float(numeri[i + 1])
        if 2_480_000 <= est <= 2_840_000 and 1_070_000 <= nord <= 1_310_000:
            return est, nord
    return None


def blocco_tabella(percorso_itf, attorno_a, righe_max=RIGHE_MAX, log=None):
    """Inizio ("TABL <Classe>") e fine ("ETAB") del blocco che contiene la
    riga 'attorno_a' (contata da 1).

    Legge il file una volta sola in streaming, senza tenerlo in memoria: un
    ITF di produzione puo' superare il milione di righe. Se il file supera
    'righe_max' la scansione si ferma, e il troncamento finisce nel registro:
    in quel caso un risultato mancante NON vuol dire "blocco assente" ma solo
    "non cercato oltre".
    """
    log = log or _zitto
    inizio = nome = fine = None
    with open(percorso_itf, "r", encoding="utf-8", errors="replace") as f:
        for i, grezza in enumerate(f, start=1):
            if i > righe_max:
                log("      ⚠️ Analisi ITF troncata a %s righe (limite di scansione): "
                    "il blocco tabella cercato, se sta oltre questo punto, non e' "
                    "stato letto." % format(righe_max, ","))
                break
            if grezza.startswith("TABL"):
                inizio = i
                nome = grezza.strip()
            if i >= attorno_a and grezza.startswith("ETAB"):
                fine = i
                break
    return inizio, nome, fine


def oggetti_per_tid(percorso_itf, inizio, fine, tids):
    """Le righe OBJE grezze dei 'tid' cercati, limitandosi all'intervallo
    [inizio, fine] - un solo blocco TABL...ETAB, non l'intero file."""
    cercati = set(tids)
    trovati = {}
    with open(percorso_itf, "r", encoding="utf-8", errors="replace") as f:
        for i, grezza in enumerate(f, start=1):
            if i < inizio:
                continue
            if i > fine or len(trovati) == len(cercati):
                break
            if grezza.startswith("OBJE"):
                pezzi = grezza.split()
                if len(pezzi) >= 2 and pezzi[1] in cercati:
                    trovati[pezzi[1]] = grezza.strip()
    return trovati


def analizza(violazioni, percorso_itf, log=None):
    """Da un elenco di violazioni di unicita' a un riepilogo leggibile.

    Per ogni conflitto cerca nell'ITF le due righe OBJE coinvolte e - quando
    ci riesce - le coordinate e la distanza fra i due punti, cosi' si capisce
    subito se e' un doppione (stesso punto, due tid) o una collisione di
    numerazione (punti diversi, stesso identificativo).

    Restituisce (righe_tabella, punti): le prime per la scheda "Errori nei
    dati", i secondi per il layer sulla mappa. La scheda dice COSA non va, il
    layer dice DOVE, e sono due domande diverse.
    """
    log = log or _zitto
    if not violazioni:
        log("   ℹ️ Nessun errore di vincolo di unicità riconosciuto nel log sopra: "
            "controlla i messaggi \"Error:\" per il dettaglio.")
        return ([], [])

    log("\n🔬 Analisi automatica: %d violazione/i di vincolo di unicità" % len(violazioni))
    righe_tabella = []
    punti = []
    # I blocchi gia' individuati, per non riscandire l'ITF a ogni violazione:
    # i conflitti di una consegna stanno quasi sempre nella STESSA tabella, e
    # su un ITF da un milione di righe ogni scansione costa secondi. I blocchi
    # non si sovrappongono, quindi basta chiedersi se la riga cade in uno gia'
    # noto.
    blocchi = []

    for errore in violazioni:
        vincolo_corto = errore.vincolo.split(".")[-1]
        tabella = errore.classe.split(".")[-1]
        riga = {
            "tabella": tabella,
            "vincolo": vincolo_corto,
            "valori": errore.valori,
            "tid": "%s ↔ %s" % (errore.tid, errore.tid_esistente),
            "riga": errore.riga,
            "diagnosi": "",
        }
        righe_tabella.append(riga)
        log("\n   📋 Tabella: %s  |  Vincolo: %s" % (tabella, vincolo_corto))
        log("      Valori duplicati: %s" % errore.valori)
        log("      Oggetto nuovo (tid %s, riga ITF %d) in conflitto con oggetto "
            "già importato (tid %s)" % (errore.tid, errore.riga, errore.tid_esistente))
        try:
            inizio = fine = None
            for a, b in blocchi:
                if a <= errore.riga <= b:
                    inizio, fine = a, b
                    break
            if inizio is None:
                inizio, _nome, fine = blocco_tabella(percorso_itf, errore.riga, log=log)
                if inizio and fine:
                    blocchi.append((inizio, fine))
            if not inizio or not fine:
                log("      ⚠️ Non trovo i confini del blocco tabella nell'ITF per "
                    "il dettaglio.")
                riga["diagnosi"] = "blocco tabella non individuato nell'ITF"
                continue

            oggetti = oggetti_per_tid(percorso_itf, inizio, fine,
                                      [errore.tid, errore.tid_esistente])
            coord_a = coordinate_lv95(oggetti[errore.tid]) if errore.tid in oggetti else None
            coord_b = (coordinate_lv95(oggetti[errore.tid_esistente])
                       if errore.tid_esistente in oggetti else None)
            if not (coord_a and coord_b):
                riga["diagnosi"] = "coordinate non estratte (formato riga inatteso)"
                log("      ℹ️ Coordinate non estratte automaticamente "
                    "(formato riga inatteso).")
                continue

            distanza = ((coord_a[0] - coord_b[0]) ** 2
                        + (coord_a[1] - coord_b[1]) ** 2) ** 0.5
            # Gli stessi due punti finiscono anche sulla mappa.
            for tid, (x, y) in ((errore.tid, coord_a), (errore.tid_esistente, coord_b)):
                punti.append({
                    "livello": "errore", "tipo": "vincolo di unicità",
                    "messaggio": "%s: valori duplicati %s" % (vincolo_corto, errore.valori),
                    "x": x, "y": y, "tid": tid, "riga": errore.riga,
                })
            log("      Coordinate: A=(%.1f, %.1f)  B=(%.1f, %.1f)  →  distanza %.0f m"
                % (coord_a[0], coord_a[1], coord_b[0], coord_b[1], distanza))
            if distanza < METRI_STESSO_PUNTO:
                riga["diagnosi"] = "doppione: stesso punto, distanza %.1f m" % distanza
                log("      → Stesso punto fisico registrato due volte "
                    "(probabile doppione da rimuovere).")
            else:
                riga["diagnosi"] = ("collisione di numerazione: punti diversi, "
                                    "distanza %.0f m" % distanza)
                log("      → Punti fisicamente DIVERSI: collisione di numerazione "
                    "(due punti distinti con lo stesso identificativo), non un doppione.")
        except OSError as errore_io:
            riga["diagnosi"] = "lettura ITF fallita"
            log("      ⚠️ Lettura ITF fallita durante l'analisi: %s" % errore_io)

    log("\n   💡 Non è un problema risolvibile qui: i dati sorgente vanno corretti da chi "
        "gestisce l'ITF (assegna un identificativo diverso a uno dei due punti). "
        "Per procedere comunque con l'import (i duplicati restano nel GeoPackage così "
        "come sono), attiva \"Disabilita validazione\" nei parametri avanzati e "
        "rilancia. L'elenco completo è nella scheda \"Errori nei dati\".")
    return (righe_tabella, punti)


def punti_distinti(punti, log=None):
    """Lo stesso difetto viene segnalato piu' volte.

    Sul comune di prova le otto avvertenze "arc is straight" stanno su DUE
    posizioni sole, ripetute quattro volte ciascuna - una per ogni anello che
    passa di li'. Impilare quattro punti identici non aggiunge niente e rende
    ambiguo il clic sulla mappa.
    """
    log = log or _zitto
    visti = set()
    distinti = []
    for p in punti:
        chiave = (p["livello"], p["tipo"], p["messaggio"],
                  round(p["x"], 3), round(p["y"], 3))
        if chiave in visti:
            continue
        visti.add(chiave)
        distinti.append(p)
    if len(distinti) < len(punti):
        log("   ℹ️ %d segnalazioni ripetute sulla stessa posizione accorpate"
            % (len(punti) - len(distinti)))
    return distinti


def crea_layer(punti, progetto=None, log=None):
    """Mette sulla mappa i problemi trovati dalla validazione.

    Con due punti di confine che hanno lo stesso identificativo, sapere se
    distano 8 metri o 8 chilometri cambia cosa si va a controllare sul
    terreno - e per arrivarci prima bisognava copiare le coordinate dal log e
    incollarle a mano.

    Restituisce il layer, o None se non c'e' niente da mostrare.
    """
    from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer

    log = log or _zitto
    if not punti:
        return None
    progetto = progetto if progetto is not None else QgsProject.instance()

    layer = QgsVectorLayer(
        "Point?crs=EPSG:2056&field=livello:string(10)&field=tipo:string(40)"
        "&field=messaggio:string(400)&field=tid:string(20)&field=riga:integer",
        "Errori di validazione", "memory")
    punti = punti_distinti(punti, log)

    elementi = []
    for p in punti:
        elemento = QgsFeature(layer.fields())
        elemento.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(p["x"], p["y"])))
        elemento.setAttributes([p["livello"], p["tipo"], p["messaggio"],
                                str(p.get("tid") or ""), int(p.get("riga") or 0)])
        elementi.append(elemento)
    layer.dataProvider().addFeatures(elementi)
    layer.updateExtents()
    applica_stile(layer)
    progetto.addMapLayer(layer)

    errori = sum(1 for p in punti if p["livello"] == "errore")
    log("   🗺️ Layer «Errori di validazione»: %d punti (%d errori, %d avvisi). "
        "Clic destro sul layer → Zoom sul layer per vederli."
        % (len(punti), errori, len(punti) - errori))
    return layer


def applica_stile(layer):
    """Rosso gli errori, arancione gli avvisi, e l'etichetta col messaggio: un
    puntino senza scritta costringe comunque ad aprire la tabella."""
    from qgis.core import QgsMarkerSymbol, QgsRuleBasedRenderer

    radice = QgsRuleBasedRenderer.Rule(None)
    for livello, colore in (("errore", "198,40,40"), ("avviso", "230,145,0")):
        simbolo = QgsMarkerSymbol.createSimple({
            "name": "circle", "color": colore + ",180",
            "outline_color": "255,255,255", "outline_width": "0.4", "size": "4"})
        regola = QgsRuleBasedRenderer.Rule(
            simbolo, filterExp='"livello" = \'%s\'' % livello, label=livello)
        radice.appendChild(regola)
    layer.setRenderer(QgsRuleBasedRenderer(radice))
