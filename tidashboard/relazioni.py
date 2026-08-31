# TIDashboard - dati della misurazione ufficiale svizzera in QGIS
# Copyright (C) 2026 Gabriele Peverelli
#
# Questo programma e' software libero: lo si puo' ridistribuire e modificare
# secondo i termini della GNU General Public License pubblicata dalla Free
# Software Foundation, versione 2 o (a scelta) una successiva. Il testo si
# trova nel file LICENSE distribuito insieme al programma.

# Le relazioni e i join fra i layer.
#
# DUE META', ed e' la divisione che rende utile questo modulo. LEGGERE le
# chiavi esterne dal GeoPackage e' sqlite3 e basta: nessun QGIS, nessun layer,
# nessuna finestra. APPLICARLE - creare QgsRelation e QgsVectorLayerJoinInfo -
# e' l'unica parte che ha bisogno di QGIS.
#
# Finche' stavano insieme dentro la finestra, la prima meta' era provabile
# solo avviando QGIS, cioe' nel lavoro di CI che dura minuti invece di dieci
# secondi. Ed e' la meta' dove i difetti veri sono successi: il nome MAIUSCOLO
# della tabella di metadati e il nome "nice" del layer usato come chiave (vedi
# le note qui sotto) sono costati entrambi un'assenza silenziosa di etichette
# su dati reali. Adesso quei due casi sono due prove che girano sempre.
#
# GLI ERRORI SI ALZANO, non si restituiscono come lista vuota. Un GeoPackage
# illeggibile e un GeoPackage senza chiavi esterne davano tutti e due [], che
# e' il modo per far passare per "niente da collegare" un file rotto. Chi
# legge alza sqlite3.Error; chi applica lo prende e lo scrive nel registro.
#
# IL PROGETTO ENTRA COME PARAMETRO, invece di prendere QgsProject.instance()
# qui dentro: in una prova il progetto aperto non e' quello che si vuole
# sporcare di relazioni.
import collections
import os
import sqlite3

try:
    from .ordinamento import CAMPO_ORI_SIMBOLO, PREFISSO_SIMBOLO, _raw_table_name
except ImportError:
    from ordinamento import CAMPO_ORI_SIMBOLO, PREFISSO_SIMBOLO, _raw_table_name


# I quattro pezzi di una chiave esterna. Era una tupla anonima: al quarto
# "riga[2]" si perde il filo di quale estremo sia il figlio e quale il padre,
# e in un join che va nel verso opposto agli altri (vedi orientamento_simboli)
# quel filo e' esattamente cio' che serve non perdere.
Chiave = collections.namedtuple(
    "Chiave", ("tabella_figlio", "colonna_figlio", "tabella_padre", "colonna_padre"))


def _zitto(_testo, _livello=None):
    """Registro di riposo: chi chiama senza log non stampa niente."""


def chiavi_esterne(percorso_gpkg, log=None):
    """Le chiavi esterne dichiarate nel GeoPackage, in ordine di lettura.

    Solo sqlite3: non tocca QGIS e non ha bisogno di un layer caricato.
    Alza sqlite3.Error se il file non e' leggibile - un file rotto non deve
    somigliare a un file senza relazioni.
    """
    log = log or _zitto
    trovate = []
    viste = set()

    # sqlite3.connect su un percorso inesistente CREA un database vuoto: la
    # lettura riuscirebbe con zero chiavi - un file rotto travestito da file
    # senza relazioni - e per giunta lascerebbe un sqlite finto al posto del
    # GeoPackage. Meglio dirlo prima, con l'errore che sqlite alza da se'
    # quando il file non si apre, cosi' chi chiama ne prende una sola specie.
    if not os.path.isfile(percorso_gpkg):
        raise sqlite3.OperationalError(
            "unable to open database file: %s" % percorso_gpkg)

    con = sqlite3.connect(str(percorso_gpkg))
    try:
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'sqlite_%'")
        tabelle = [riga[0] for riga in cur.fetchall()]
        log("   📋 Tabelle nel DB: %d" % len(tabelle))

        # 1. Vincoli FK veri (ci sono solo se lo schema e' stato creato con
        # --createFk).
        # PRAGMA non accetta il binding '?' sui nomi di tabella (solo sui
        # valori), quindi l'identificatore va quotato a mano: raddoppiare gli
        # apici interni e' la forma di escaping standard di SQL.
        for tabella in tabelle:
            cur.execute("PRAGMA foreign_key_list('%s')" % tabella.replace("'", "''"))
            for riga in cur.fetchall():
                colonna_figlio, tabella_padre = riga[3], riga[2]
                colonna_padre = riga[4] if riga[4] else "rowid"
                chiave = (tabella, colonna_figlio)
                if chiave not in viste:
                    trovate.append(Chiave(tabella, colonna_figlio, tabella_padre, colonna_padre))
                    viste.add(chiave)

        # 2. Ripiego: i metadati di ili2db (t_ili2db_column_prop, etichetta
        # ch.ehi.ili2db.foreignKey). Si riempie con --createMetaInfo anche
        # SENZA --createFk: e' il modo con cui ili2db lascia ricostruire le
        # relazioni quando lo schema non ha vincoli veri - che rifiuterebbero
        # l'import di dati con riferimenti mancanti.
        #
        # I nomi delle tabelle di metadati di ili2db sono in MAIUSCOLO
        # ("T_ILI2DB_COLUMN_PROP", verificato sul GeoPackage) e in SQLite il
        # confronto su sqlite_master.name distingue le maiuscole: senza
        # lower() questo ripiego non si attivava mai.
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' "
                    "AND lower(name)='t_ili2db_column_prop'")
        if cur.fetchone():
            cur.execute("SELECT tablename, columnname, setting FROM t_ili2db_column_prop "
                        "WHERE tag = 'ch.ehi.ili2db.foreignKey'")
            for tabella, colonna_figlio, tabella_padre in cur.fetchall():
                chiave = (tabella, colonna_figlio)
                if chiave not in viste:
                    trovate.append(Chiave(tabella, colonna_figlio, tabella_padre, "T_Id"))
                    viste.add(chiave)
        else:
            log("   ℹ️ t_ili2db_column_prop non presente "
                "(schemaimport senza --createMetaInfo)")
    finally:
        con.close()

    log("   🔗 Chiavi esterne trovate: %d" % len(trovate))
    return trovate


def per_tabella_raw(layers):
    """I layer indicizzati per nome RAW della tabella nel GeoPackage.

    DIFETTO VERO (segnalato dall'utente: niente testi ne' etichette su beni
    immobili e indirizzi degli edifici). Le chiavi esterne lette da
    sqlite_master e da t_ili2db_column_prop portano i nomi RAW delle tabelle,
    ma l'indice era costruito su layer.name(), gia' rinominato al nome
    "leggibile" in italiano nella fase precedente. Il confronto falliva quindi
    in silenzio - continue senza una riga di registro - per circa 123 join su
    128 in un caso reale, lasciando i layer Pos* senza il campo di testo del
    padre e percio' senza etichetta.

    Il nome RAW si recupera invece dalla URI di origine del layer OGR
    ("...gpkg|layername=xxx"), che non cambia comunque il layer sia stato
    rinominato.
    """
    return {_raw_table_name(layer): layer for layer in layers}


def solo_orientamento(chiave, per_tabella):
    """Vero se questa chiave riguarda una tabella "Simbolo*" SENZA geometria,
    cioe' una di quelle che servono solo a portare "Ori" sul padre.

    DIFETTO VERO, trovato misurando su una consegna vera: gli orientamenti
    collegati erano ZERO su undici chiavi Simbolo*, e nessuno se n'era
    accorto perche' l'unico segno era una riga di avviso in mezzo a centinaia.
    Il join diretto (figlio -> padre) e quello dell'orientamento (padre <-
    figlio) formano un ANELLO fra gli stessi due layer, e QGIS rifiuta il
    secondo che arriva. Provato: da solo il join dell'orientamento riesce e
    porta i valori giusti; dopo quello diretto, addJoin() risponde di no.

    Il diretto, su queste tabelle, non serviva a niente: portare i campi del
    padre su una tabella senza geometria, che non viene mai disegnata, non
    cambia nulla in mappa. Si salta quello - la relazione resta, e' la
    maschera dei dati che la usa - e l'anello non si forma.
    """
    figlio = per_tabella.get(chiave.tabella_figlio)
    padre = per_tabella.get(chiave.tabella_padre)
    if figlio is None or padre is None:
        return False
    if "simbolo" not in chiave.tabella_figlio.lower():
        return False
    from qgis.core import QgsWkbTypes
    # Solo le tabelle SENZA geometria: quelle che ce l'hanno si disegnano da
    # se' e il loro "Ori" lo usa il loro stesso stile.
    if figlio.geometryType() != QgsWkbTypes.NullGeometry:
        return False
    return figlio.fields().indexFromName("ori") >= 0


def collega_layer(percorso_gpkg, layers, progetto=None, log=None):
    """Crea relazioni e join fra i layer caricati.

    Restituisce (relazioni, join, orientamenti). Un GeoPackage illeggibile
    finisce nel registro e restituisce (0, 0, 0).
    """
    from qgis.core import Qgis, QgsProject, QgsRelation, QgsVectorLayerJoinInfo

    log = log or _zitto
    if not layers:
        log("   ⚠️ Nessun layer caricato, skip relazioni")
        return (0, 0, 0)

    progetto = progetto if progetto is not None else QgsProject.instance()
    log("   📊 Layer caricati: %d" % len(layers))
    per_tabella = per_tabella_raw(layers)

    try:
        chiavi = chiavi_esterne(percorso_gpkg, log)
    except sqlite3.Error as errore:
        log("   ❌ Errore lettura FK: %s" % errore, Qgis.Warning)
        return (0, 0, 0)

    relazioni = 0
    join = 0
    # Le chiavi che portano SOLO l'orientamento: la relazione si crea, il
    # join diretto no - altrimenti l'anello impedisce quello che conta.
    da_non_unire = {c for c in chiavi if solo_orientamento(c, per_tabella)}

    for chiave in chiavi:
        tabella_figlio, colonna_figlio, tabella_padre, colonna_padre = chiave
        layer_figlio = per_tabella.get(tabella_figlio)
        layer_padre = per_tabella.get(tabella_padre)
        if not layer_figlio or not layer_padre:
            continue

        campi_figlio = [c.name() for c in layer_figlio.fields()]
        campi_padre = [c.name() for c in layer_padre.fields()]
        if colonna_figlio not in campi_figlio or colonna_padre not in campi_padre:
            continue

        relazione = QgsRelation()
        relazione.setId("%s_%s" % (tabella_figlio, tabella_padre))
        relazione.setName("%s → %s" % (tabella_figlio, tabella_padre))
        relazione.setReferencingLayer(layer_figlio.id())
        relazione.setReferencedLayer(layer_padre.id())
        relazione.addFieldPair(colonna_figlio, colonna_padre)

        if relazione.isValid():
            progetto.relationManager().addRelation(relazione)
            relazioni += 1
            log("   ✅ Relazione: %s.%s → %s.%s"
                % (tabella_figlio, colonna_figlio, tabella_padre, colonna_padre))

        if chiave in da_non_unire:
            continue

        info = QgsVectorLayerJoinInfo()
        # QgsVectorLayerJoinInfo e' un binding SIP: assegnare l'attributo
        # direttamente (info.joinLayerId = ...) NON richiama il setter C++,
        # crea solo un attributo Python "ombra" che addJoin() ignora del
        # tutto, lasciando il join con i valori di default - e fallendo in
        # silenzio. Servono i setter espliciti. setJoinLayer() (puntatore
        # diretto) e' preferito a setJoinLayerId() per non dipendere dalla
        # risoluzione dell'ID tramite il progetto al momento dell'uso.
        info.setJoinLayer(layer_padre)
        info.setJoinFieldName(colonna_padre)
        info.setTargetFieldName(colonna_figlio)
        info.setUsingMemoryCache(True)
        info.setPrefix("%s_" % tabella_padre)
        if layer_figlio.addJoin(info):
            join += 1
            prefisso = ("%s_" % tabella_padre).lower()
            nuovi = [c.name() for c in layer_figlio.fields()
                     if c.name().lower().startswith(prefisso)]
            if not nuovi:
                log("   ⚠️ Join OK ma nessun campo con prefisso '%s_' su %s "
                    "(campi attuali: %s)"
                    % (tabella_padre, tabella_figlio,
                       [c.name() for c in layer_figlio.fields()]), Qgis.Warning)
        else:
            log("   ⚠️ Join fallito: %s.%s → %s.%s"
                % (tabella_figlio, colonna_figlio, tabella_padre, colonna_padre),
                Qgis.Warning)

    log("   📊 Relazioni create: %d" % relazioni)
    log("   📊 Join creati: %d" % join)
    orientamenti = orientamento_simboli(chiavi, per_tabella, log)
    return (relazioni, join, orientamenti)


def orientamento_simboli(chiavi, per_tabella, log=None):
    """Porta l'orientamento del simbolo dalle tabelle "Simbolo*" SENZA
    geometria sul layer del padre, con un join nel verso opposto a tutti gli
    altri.

    Cinque delle undici tabelle Simbolo* del modello - SimboloPunto_di_confine,
    SimboloPCGiurisdizionale, SimboloPFP1/2/3 - non hanno alcuna geometria:
    portano solo "Ori", cioe' l'orientamento con cui va disegnato il simbolo
    del punto a cui si riferiscono, e la relazione e' 1-c (IDENT sul
    riferimento), quindi al piu' una riga per padre. Non sono disegnabili di
    per se': l'unico modo di usarle e' portare "Ori" sul padre, che la
    geometria ce l'ha. Tutti gli altri join vanno figlio -> padre; questo e'
    l'unico che va padre <- figlio.

    Sui dati reali di Chiasso: 5637 punti di confine su 67919 portano un
    orientamento non nullo, e prima venivano disegnati tutti dritti.

    Il prefisso e' fisso (PREFISSO_SIMBOLO) e non derivato dal nome della
    tabella: gli stili cercano "simbolo_ori", uguale per tutti i temi, invece
    di dover ricostruire nomi come "beni_immobili_simbolopunto_di_confine_ori".
    """
    from qgis.core import Qgis, QgsVectorLayerJoinInfo

    log = log or _zitto
    fatti = 0
    for chiave in chiavi:
        # La stessa domanda che si fa collega_layer per saltare il join
        # diretto, fatta con la stessa funzione: se le due condizioni si
        # allontanassero, tornerebbe l'anello che questo evita.
        if not solo_orientamento(chiave, per_tabella):
            continue
        tabella_figlio, colonna_figlio, tabella_padre, colonna_padre = chiave
        layer_figlio = per_tabella[tabella_figlio]
        layer_padre = per_tabella[tabella_padre]
        if layer_padre.fields().indexFromName(CAMPO_ORI_SIMBOLO) >= 0:
            continue

        join = QgsVectorLayerJoinInfo()
        join.setJoinLayer(layer_figlio)
        join.setJoinFieldName(colonna_figlio)      # la FK del figlio...
        join.setTargetFieldName(colonna_padre)     # ...contro la chiave del padre
        join.setUsingMemoryCache(True)
        join.setPrefix(PREFISSO_SIMBOLO)
        join.setJoinFieldNamesSubset(["ori"])
        if layer_padre.addJoin(join):
            fatti += 1
            log("   🧭 Orientamento simbolo: %s.ori → %s.%s"
                % (tabella_figlio, tabella_padre, CAMPO_ORI_SIMBOLO))
        else:
            log("   ⚠️ Join orientamento fallito: %s → %s"
                % (tabella_figlio, tabella_padre), Qgis.Warning)

    if fatti:
        log("   📊 Orientamenti di simbolo collegati: %d" % fatti)
    return fatti
