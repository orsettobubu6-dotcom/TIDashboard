# TIDashboard - dati della misurazione ufficiale svizzera in QGIS
# Copyright (C) 2026 Gabriele Peverelli
#
# Questo programma e' software libero: lo si puo' ridistribuire e modificare
# secondo i termini della GNU General Public License pubblicata dalla Free
# Software Foundation, versione 2 o (a scelta) una successiva. Il testo si
# trova nel file LICENSE distribuito insieme al programma.

# Lettura del nome del comune dai dati INTERLIS, per non farlo digitare a mano.
#
# Il comune e' una delle nove iscrizioni obbligatorie del cartiglio
# (circ154_allegato2 cap.1.5.7): scriverlo a mano vuol dire poterlo sbagliare,
# mentre nel modello MD01MUTI7MN95 c'e' gia', in due punti:
#
#  - Margine_del_piano.Layout_del_piano.Nome_comune - e' il nome pensato
#    proprio per l'intestazione di un piano, quindi ha la precedenza;
#  - Confini_comunali.Comune.Nome - l'elenco dei comuni del perimetro; una
#    consegna puo' contenerne piu' d'uno (aggregazioni, exclavi), percio' si
#    restituisce una lista e la scelta resta all'utente.
#
# I nomi delle tabelle non sono cablati: ili2gpkg li compone da topic e classe
# in minuscolo, ma la regola e' cambiata fra le versioni, quindi si cercano per
# forma (suffisso del nome, colonne presenti) leggendo il catalogo del
# GeoPackage.
import os
import re
import sqlite3

# Colonna dedicata all'intestazione del piano: dove c'e', vince.
COL_NOME_PIANO = "nome_comune"
# Tabella dell'elenco comuni: nome che finisce per "_comune" (o "comune") con
# una colonna "nome".
SUFFISSO_TABELLA_COMUNE = "comune"
COL_NOME = "nome"


def _tabelle(con):
    return [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]


def _colonne(con, tabella):
    return [r[1].lower() for r in con.execute('PRAGMA table_info("%s")' % tabella)]


# La colonna con cui ili2gpkg tiene separati i comuni dentro un archivio.
COL_DATASET = "t_datasetname"


def _valori(con, tabella, colonna, comune=None):
    """Valori distinti, non vuoti, nell'ordine in cui compaiono.

    'comune' RESTRINGE AL SOLO COMUNE indicato (il numero, che e' il nome del
    dataset). Serve perche' un archivio puo' contenere piu' comuni e le
    risposte che ne escono finiscono nell'intestazione e nel cartiglio del
    piano, che parlano di UN comune: senza il filtro, il piano di Coldrerio
    dichiarava la data di Lavertezzo.

    Se la colonna del dataset non c'e' - archivio di un comune solo, fatto
    prima del multi-comune - il filtro si ignora invece di dare zero risultati:
    li' tutte le righe sono di quell'unico comune, e la risposta senza filtro
    e' gia' quella giusta."""
    dove, valori = "", ()
    if comune and COL_DATASET in _colonne(con, tabella):
        dove = ' WHERE "%s" = ?' % COL_DATASET
        valori = (str(comune),)
    visti = []
    for (v,) in con.execute(
            'SELECT DISTINCT "%s" FROM "%s"%s' % (colonna, tabella, dove), valori):
        testo = (v or "").strip() if isinstance(v, str) else ""
        if testo and testo not in visti:
            visti.append(testo)
    return visti


def leggi_comuni(percorso_gpkg, comune=None):
    """Nomi di comune trovati nel GeoPackage, i piu' attendibili per primi.

    'comune' e' il numero del comune attivo: indicandolo si legge SOLO quello,
    che e' cio' che va in intestazione quando l'archivio ne contiene piu' d'uno
    (senza, l'intestazione diventava "Coldrerio, Lavertezzo").

    Ritorna una lista vuota se il file non c'e', non e' leggibile o non
    contiene nessuna delle due fonti: l'assenza del dato non deve impedire di
    produrre la planimetria, solo di darlo per scontato."""
    if not percorso_gpkg or not os.path.isfile(str(percorso_gpkg)):
        return []
    try:
        # Sola lettura: il GeoPackage puo' essere aperto da QGIS nello stesso
        # momento, e questa e' una consultazione, non una modifica.
        con = sqlite3.connect("file:%s?mode=ro" % str(percorso_gpkg), uri=True)
    except sqlite3.Error:
        return []

    nomi = []
    try:
        tabelle = _tabelle(con)
        # 1) il nome pensato per l'intestazione del piano
        for tabella in tabelle:
            if tabella.startswith(("gpkg_", "rtree_", "sqlite_")):
                continue
            if COL_NOME_PIANO in _colonne(con, tabella):
                for nome in _valori(con, tabella, COL_NOME_PIANO, comune):
                    if nome not in nomi:
                        nomi.append(nome)
        # 2) l'elenco dei comuni del perimetro
        for tabella in tabelle:
            if not tabella.lower().endswith(SUFFISSO_TABELLA_COMUNE):
                continue
            if COL_NOME not in _colonne(con, tabella):
                continue
            for nome in _valori(con, tabella, COL_NOME, comune):
                if nome not in nomi:
                    nomi.append(nome)
    except sqlite3.Error:
        return nomi
    finally:
        con.close()
    return nomi


# Tabelle di attualizzazione del modello: ogni tema ne ha una, e portano la
# data dell'ultimo aggiornamento di quel tema.
PREFISSO_TENUTA = "tenuta_a_giorno"
# Il modello (MD01MUTI7MN95.ili, TABLE Tenuta_a_giorno_Comune) dice: "Per gli
# aggiornamenti futuri, la data da inserire e' In_vigore. Data1 corrisponde ai
# vecchi aggiornamenti e non viene piu' usato". Si prova quindi prima in_vigore.
COLONNE_DATA = ("in_vigore", "data1")
# Una data ISO, aaaa-mm-gg. Serve a distinguerla da una data scritta all'uso
# svizzero (12.03.2024), che ha esattamente la stessa lunghezza.
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def data_estrazione_itf(percorso_itf):
    """Data di estrazione del file ITF, letta dalla data di modifica del file.

    L'ITF NON contiene una data al suo interno: verificato sull'intestazione di
    una consegna reale, che porta solo MTID, MODL e il filtro di esportazione.
    L'unica traccia di quando e' stato prodotto e' quindi il timestamp del file.

    Si usa la data di MODIFICA e non quella di creazione: la seconda, su
    Windows, e' il momento in cui la copia locale e' stata scritta (cioe' quando
    l'hai scaricata), mentre la prima viene conservata dalla copia e risale a
    quando il sistema di esportazione ha scritto il file. Riscontrato su una
    consegna reale: modifica 02.09.2024, creazione della copia 07.08.2025.

    LIMITE: e' un dato del file system, non del contenuto. Se il file viene
    riscritto o trasferito con strumenti che non conservano il timestamp, la
    data cambia. Per questo resta una proposta, modificabile nell'interfaccia.

    Ritorna 'gg.mm.aaaa' oppure "" se il file non c'e'."""
    import datetime
    if not percorso_itf or not os.path.isfile(str(percorso_itf)):
        return ""
    try:
        quando = os.stat(str(percorso_itf)).st_mtime
    except OSError:
        return ""
    return datetime.datetime.fromtimestamp(quando).strftime("%d.%m.%Y")


def leggi_data_validita(percorso_gpkg, comune=None):
    """Data di validita' dei dati, letta dalle tabelle di attualizzazione.

    "Stato al" nel cartiglio e' la data dei DATI, non quella della stampa: sta
    nell'ITF, in Tenuta_a_giorno_* (una per tema). Si prende la piu' RECENTE fra
    tutti i temi, che e' lo stato della consegna nel suo insieme.

    Ritorna 'gg.mm.aaaa' oppure "" se il dato non c'e'."""
    if not percorso_gpkg or not os.path.isfile(str(percorso_gpkg)):
        return ""
    try:
        con = sqlite3.connect("file:%s?mode=ro" % str(percorso_gpkg), uri=True)
    except sqlite3.Error:
        return ""
    massima = ""
    try:
        for tabella in _tabelle(con):
            if PREFISSO_TENUTA not in tabella.lower():
                continue
            colonne = _colonne(con, tabella)
            for nome in COLONNE_DATA:
                if nome not in colonne:
                    continue
                for v in _valori(con, tabella, nome, comune):
                    # ili2gpkg le scrive ISO (aaaa-mm-gg): il confronto fra
                    # stringhe in quel formato e' gia' cronologico.
                    #
                    # SI CONTROLLA IL FORMATO, non la lunghezza. Il filtro era
                    # len(v) == 10, e una data scritta all'uso svizzero -
                    # "12.03.2024" - ha esattamente dieci caratteri: passava,
                    # e poi lo split("-") qui sotto alzava ValueError su un
                    # dato che nessuno aveva promesso fosse ISO.
                    if _ISO.match(v or "") and v > massima:
                        massima = v
                break
    except sqlite3.Error:
        pass
    finally:
        con.close()
    if not massima:
        return ""
    anno, mese, giorno = massima.split("-")
    return "%s.%s.%s" % (giorno, mese, anno)


def gpkg_dei_layer(layers):
    """Percorso del GeoPackage da cui provengono i layer caricati.

    Si ricava dalla source dei layer ("...gpkg|layername=xxx") invece che dal
    campo di testo dell'interfaccia: quel campo puo' essere stato cambiato dopo
    l'importazione, i layer no."""
    for layer in (layers or []):
        try:
            sorgente = layer.source()
        except Exception:
            continue
        percorso = sorgente.split("|", 1)[0]
        if percorso.lower().endswith(".gpkg") and os.path.isfile(percorso):
            return percorso
    return ""
