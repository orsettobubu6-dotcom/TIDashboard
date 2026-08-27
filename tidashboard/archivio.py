# -*- coding: utf-8 -*-
# Il registro dell'archivio: quali comuni ci sono nel GeoPackage, e da quale
# file ITF e' venuto ognuno.
#
# PERCHE' UN REGISTRO. Il GeoPackage sa gia' da se' quali dataset contiene
# (T_ILI2DB_DATASET, scritto da ili2gpkg), ma NON sa da quale file ITF sono
# arrivati. Quel percorso serve per due cose che il GeoPackage non puo' dare:
# esportare il DXF di un comune solo - il DXF nasce dall'ITF, non dal
# GeoPackage - e riaggiornare quel comune con --replace senza toccare gli
# altri. Quindi il registro sta DENTRO il GeoPackage, in una tabella nostra:
# cosi' l'archivio si descrive da solo e non dipende da un file di appoggio
# che si perde o si disallinea.
#
# IL NOME DEL DATASET E' IL NUMERO DI COMUNE, e viene dal dato, non dal nome
# del file. Il numero di comune e' quello che IdentAN porta gia' dentro
# (TI-CCC-SS, vedi cerca_fondo.comune_di): usandolo come nome del dataset, un
# fondo trovato dalla ricerca si riconduce al suo comune senza nessuna tabella
# di passaggio. Il nome del comune no: i nomi cambiano con le aggregazioni, e
# un --replace che cerca "Lavertezzo" fallirebbe il giorno che diventa altro.
import io
import os
import sqlite3

# La tabella del registro. Prefisso esplicito perche' vive accanto alle
# tabelle di ili2gpkg e a quelle di GeoPackage: chi apre il file deve vedere
# a colpo d'occhio che questa e' nostra.
TABELLA = "tidashboard_comuni"

# Nell'ITF il comune si dichiara qui. E' una tabella del modello, non
# un'intestazione: l'intestazione ITF porta solo MODL/TOPI/TABL.
TABELLA_ITF = "comune"

# Quante righe leggere al massimo cercando la tabella Comune. Un ITF di un
# comune sta sui tre milioni di righe e la tabella Comune puo' stare in fondo;
# il limite serve solo a non restare appesi su un file che non e' un ITF.
RIGHE_MAX = 5_000_000


class Comune(object):
    """Un comune come lo dichiara l'ITF.

    'numero' e' il numero di comune (le CCC di IdentAN), 'bfs' il numero
    federale. Tutti e due come stringa: sono identificativi, non quantita', e
    uno zero iniziale non va perso."""

    __slots__ = ("numero", "nome", "bfs")

    def __init__(self, numero, nome, bfs=None):
        self.numero = numero
        self.nome = nome
        self.bfs = bfs

    @property
    def dataset(self):
        """Il nome con cui questo comune vive nel GeoPackage."""
        return str(self.numero)

    @property
    def etichetta(self):
        return "%s (%s)" % (self.nome, self.numero) if self.nome else str(self.numero)

    def __eq__(self, altro):
        return (isinstance(altro, Comune) and self.numero == altro.numero
                and self.nome == altro.nome and self.bfs == altro.bfs)

    def __repr__(self):
        return "<Comune %s %s>" % (self.numero, self.nome)


def _spezza_obje(riga):
    """Da 'OBJE 22140 Lavertezzo 5112 422' a ('Lavertezzo', '5112', '422').

    Il nome puo' contenere spazi - 'Castel San Pietro' - quindi non si puo'
    tagliare per posizione. Si tiene invece che gli ULTIMI DUE campi sono
    numerici (BFS e numero di comune) e il PRIMO e' il TID: quel che sta in
    mezzo e' il nome, spazi compresi. Ritorna None se la forma non torna,
    perche' un nome inventato e' peggio di nessun nome."""
    pezzi = riga.split()
    # OBJE + tid + almeno un pezzo di nome + bfs + numero
    if len(pezzi) < 5 or pezzi[0] != "OBJE":
        return None
    if not (pezzi[-1].isdigit() and pezzi[-2].isdigit()):
        return None
    nome = " ".join(pezzi[2:-2]).strip()
    if not nome:
        return None
    return nome, pezzi[-2], pezzi[-1]


def leggi_comuni_itf(percorso_itf):
    """I comuni dichiarati dentro un ITF, nell'ordine in cui compaiono.

    RITORNA UNA LISTA, non un comune solo, e non e' pignoleria: una consegna
    puo' contenerne piu' d'uno, e in quel caso importarla sotto un nome di
    dataset solo mescolerebbe due comuni sotto un'etichetta sbagliata. Chi
    chiama deve poter vedere che ce n'e' piu' d'uno e fermarsi.

    Lista vuota se il file non c'e', non e' leggibile, o non dichiara nessun
    comune: l'assenza va distinta da un valore inventato."""
    if not percorso_itf or not os.path.isfile(str(percorso_itf)):
        return []
    trovati = []
    try:
        with io.open(str(percorso_itf), encoding="latin-1", errors="replace") as f:
            dentro = False
            for numero_riga, riga in enumerate(f):
                if numero_riga > RIGHE_MAX:
                    break
                riga = riga.rstrip()
                if riga.startswith("TABL "):
                    # Il confronto e' sul nome esatto della tabella: nel
                    # modello ci sono anche PosComune e SimboloComune, e un
                    # "comune in nome" li prenderebbe tutti.
                    dentro = riga[5:].strip().lower() == TABELLA_ITF
                elif riga.startswith("ETAB"):
                    if dentro:
                        break        # la tabella e' finita: non serve altro
                    dentro = False
                elif dentro and riga.startswith("OBJE"):
                    letto = _spezza_obje(riga)
                    if letto:
                        nome, bfs, numero = letto
                        trovati.append(Comune(numero, nome, bfs))
    except (IOError, OSError):
        return []
    return trovati


def comune_di_itf(percorso_itf):
    """Il comune di un ITF, se ne dichiara ESATTAMENTE uno.

    None quando non ce n'e' nessuno o ce n'e' piu' d'uno: sono due situazioni
    diverse fra loro ma uguali per chi chiama, che in nessuno dei due casi puo'
    dare un nome al dataset. Per distinguerle si usa leggi_comuni_itf."""
    trovati = leggi_comuni_itf(percorso_itf)
    return trovati[0] if len(trovati) == 1 else None


def _apri(percorso_gpkg, scrittura=False):
    if not percorso_gpkg:
        return None
    percorso = str(percorso_gpkg)
    # Il file deve esistere ANCHE in scrittura: sqlite3.connect lo crea, e
    # un percorso sbagliato nel campo del GeoPackage lascerebbe in giro un
    # file vuoto che somiglia a un archivio senza esserlo. L'archivio lo crea
    # ili2gpkg, non il registro.
    if not os.path.isfile(percorso):
        return None
    try:
        if scrittura:
            return sqlite3.connect(percorso)
        return sqlite3.connect("file:%s?mode=ro" % percorso, uri=True)
    except sqlite3.Error:
        return None


def prepara(percorso_gpkg):
    """Crea la tabella del registro se non c'e'. Vero se ora esiste."""
    con = _apri(percorso_gpkg, scrittura=True)
    if con is None:
        return False
    try:
        con.execute(
            'CREATE TABLE IF NOT EXISTS "%s" ('
            ' numero TEXT PRIMARY KEY,'
            ' nome TEXT,'
            ' bfs TEXT,'
            ' itf TEXT,'
            ' importato TEXT)' % TABELLA)
        con.commit()
        return True
    except sqlite3.Error:
        return False
    finally:
        con.close()


def registra(percorso_gpkg, comune, percorso_itf, quando=None):
    """Annota (o riannota) un comune nel registro. Vero se e' andata.

    Riannotare lo stesso numero SOVRASCRIVE: e' il caso del comune
    riaggiornato con --replace, dove il percorso dell'ITF puo' essere
    cambiato e quello vecchio non vale piu'."""
    if comune is None:
        return False
    if not prepara(percorso_gpkg):
        return False
    con = _apri(percorso_gpkg, scrittura=True)
    if con is None:
        return False
    try:
        con.execute(
            'INSERT OR REPLACE INTO "%s" (numero, nome, bfs, itf, importato)'
            ' VALUES (?, ?, ?, ?, ?)' % TABELLA,
            (str(comune.numero), comune.nome, comune.bfs,
             str(percorso_itf) if percorso_itf else None, quando))
        con.commit()
        return True
    except sqlite3.Error:
        return False
    finally:
        con.close()


def dimentica(percorso_gpkg, numero):
    """Toglie un comune dal registro. NON tocca i dati: cancellare le righe
    del dataset e' compito di ili2gpkg --delete, e farlo qui a meta' lascerebbe
    un archivio che si descrive male."""
    con = _apri(percorso_gpkg, scrittura=True)
    if con is None:
        return False
    try:
        con.execute('DELETE FROM "%s" WHERE numero = ?' % TABELLA, (str(numero),))
        con.commit()
        return True
    except sqlite3.Error:
        return False
    finally:
        con.close()


def registrati(percorso_gpkg):
    """I comuni annotati nel registro, per numero. Lista di dict con
    numero, nome, bfs, itf, importato."""
    con = _apri(percorso_gpkg)
    if con is None:
        return []
    try:
        righe = con.execute(
            'SELECT numero, nome, bfs, itf, importato FROM "%s"'
            ' ORDER BY CAST(numero AS INTEGER), numero' % TABELLA).fetchall()
    except sqlite3.Error:
        return []                    # tabella non ancora creata: archivio vuoto
    finally:
        con.close()
    return [{"numero": r[0], "nome": r[1], "bfs": r[2], "itf": r[3],
             "importato": r[4]} for r in righe]


def dataset_nel_gpkg(percorso_gpkg):
    """I dataset che ili2gpkg dichiara, letti da T_ILI2DB_DATASET.

    E' la verita' sui DATI, mentre 'registrati' e' la verita' sul nostro
    registro: le due possono divergere - un import fatto a mano fuori dal
    plugin, un registro perso - e vederle separate e' l'unico modo di
    accorgersene (vedi disallineati)."""
    con = _apri(percorso_gpkg)
    if con is None:
        return []
    nomi = []
    try:
        for (nome,) in con.execute("SELECT datasetname FROM T_ILI2DB_DATASET"):
            if nome and nome not in nomi:
                nomi.append(nome)
    except sqlite3.Error:
        return []
    finally:
        con.close()
    return sorted(nomi, key=lambda n: (len(n), n))


def _e_sqlite(percorso):
    """Header magico di SQLite. Serve a non scrivere dentro un file che non
    e' un database solo perche' si chiama .gpkg."""
    try:
        with open(str(percorso), "rb") as f:
            return f.read(16) == b"SQLite format 3\x00"
    except (IOError, OSError):
        return False


def porta_la_colonna_dataset(percorso_gpkg):
    """Le tabelle dei dati hanno T_datasetname?  True / False / None.

    E' IL CONTROLLO CHE DISTINGUE UN ARCHIVIO VECCHIO. Un GeoPackage creato
    prima del multi-comune - senza --createDatasetCol - non ha quella colonna:
    aggiungerci un secondo comune darebbe un archivio in cui le righe del
    primo non appartengono a nessuno, e nessun filtro per comune potrebbe piu'
    separarli. Meglio rifiutare e rifarlo.

    NONE QUANDO NON C'E' NIENTE DA GIUDICARE, cioe' quando di tabelle di dati
    non ce n'e' nemmeno una. Tornare False li' direbbe "manca la colonna"
    parlando di tabelle che non esistono, e manderebbe a rifare un archivio
    per il motivo sbagliato: una misura vuota non e' un esito."""
    con = _apri(percorso_gpkg)
    if con is None:
        return None
    try:
        tabelle = [r[0] for r in con.execute(
            "SELECT table_name FROM gpkg_contents WHERE data_type='features'")]
        if not tabelle:
            return None
        for tabella in tabelle[:20]:     # bastano poche: o c'e' ovunque o non c'e'
            colonne = [str(r[1]).lower()
                       for r in con.execute('PRAGMA table_info("%s")' % tabella)]
            if "t_datasetname" in colonne:
                return True
        return False
    except sqlite3.Error:
        return None
    finally:
        con.close()


# Le quattro decisioni possibili davanti a un ITF e a un archivio.
NUOVO = "nuovo"                  # archivio da creare: schema + dati
AGGIUNGI = "aggiungi"            # comune nuovo dentro un archivio che c'e' gia'
SOSTITUISCI = "sostituisci"      # comune gia' presente: si riaggiorna
RIFIUTA = "rifiuta"              # non si procede, e il motivo si dice


class Piano(object):
    """Che cosa fare, e perche'.

    'motivo' e' pieno SOLO quando l'azione e' RIFIUTA, e allora e' una frase
    da mostrare all'utente: un rifiuto senza motivo e' indistinguibile da un
    guasto."""

    __slots__ = ("azione", "comune", "motivo", "presenti")

    def __init__(self, azione, comune=None, motivo=None, presenti=None):
        self.azione = azione
        self.comune = comune
        self.motivo = motivo
        self.presenti = presenti or []

    @property
    def si_procede(self):
        return self.azione != RIFIUTA

    @property
    def serve_schema(self):
        return self.azione == NUOVO

    @property
    def flag_dati(self):
        """I flag di ili2gpkg per la fase dei dati, senza il file."""
        if not self.si_procede:
            return []
        primo = "--replace" if self.azione == SOSTITUISCI else "--import"
        return [primo, "--dataset", self.comune.dataset]

    @property
    def flag_schema(self):
        """I flag della creazione dello schema. --createDatasetCol e'
        OBBLIGATORIO qui e non un di piu': senza, l'archivio nasce gia'
        incapace di tenere separati i comuni."""
        if not self.serve_schema:
            return []
        return ["--schemaimport", "--createMetaInfo", "--createBasketCol",
                "--createDatasetCol", "--dataset", self.comune.dataset]

    def __repr__(self):
        return "<Piano %s %s>" % (self.azione, self.comune)


def pianifica(percorso_gpkg, percorso_itf, modello_atteso=None):
    """Decide che cosa fare per portare questo ITF dentro questo archivio.

    Non tocca niente: legge e basta. Chi chiama esegue - o mostra il motivo
    del rifiuto.

    'modello_atteso' se indicato viene confrontato con quello gia' presente
    nell'archivio: mescolare due modelli nello stesso GeoPackage produce
    tabelle che nessuno stile sa leggere."""
    comuni = leggi_comuni_itf(percorso_itf)
    if not comuni:
        return Piano(RIFIUTA, motivo=(
            "L'ITF non dichiara nessun comune (manca la tabella Comune, "
            "oppure la riga non ha la forma attesa). Senza il comune non si "
            "puo' dare un nome ai dati dentro l'archivio."))
    if len(comuni) > 1:
        return Piano(RIFIUTA, motivo=(
            "L'ITF dichiara %d comuni (%s). Importarli sotto un nome solo li "
            "renderebbe indistinguibili, e il DXF di uno conterrebbe anche "
            "gli altri. Vanno consegnati separati."
            % (len(comuni), ", ".join(c.etichetta for c in comuni))))
    comune = comuni[0]

    if not percorso_gpkg:
        return Piano(RIFIUTA, comune, "Manca il percorso del GeoPackage.")

    if not os.path.isfile(str(percorso_gpkg)):
        return Piano(NUOVO, comune)       # archivio da creare

    if not _e_sqlite(percorso_gpkg):
        return Piano(RIFIUTA, comune, (
            "Il file esiste ma non e' un GeoPackage (manca l'intestazione "
            "SQLite): %s. Non ci si scrive dentro." % percorso_gpkg))

    presenti = dataset_nel_gpkg(percorso_gpkg)
    modelli = _modelli_gpkg(percorso_gpkg)
    if not modelli:
        return Piano(RIFIUTA, comune, (
            "Il GeoPackage non e' stato prodotto da ili2gpkg (manca "
            "T_ILI2DB_MODEL): potrebbe essere il file di qualcun altro, e "
            "importarci dentro lo rovinerebbe."))
    if modello_atteso and modello_atteso not in modelli:
        return Piano(RIFIUTA, comune, (
            "L'archivio contiene il modello %s, l'importazione porterebbe %s. "
            "Due modelli nello stesso GeoPackage danno tabelle che gli stili "
            "non sanno leggere." % (", ".join(modelli), modello_atteso)))

    # SI CONTROLLA SEMPRE, non solo quando ci sono gia' dei comuni dentro.
    # Legandolo a 'presenti' restava scoperto il caso di uno schema creato dal
    # plugin vecchio la cui importazione dei dati era fallita: zero dataset,
    # tabelle senza T_datasetname, e il piano diceva "aggiungi". I dati
    # sarebbero finiti in tabelle incapaci di tenere separati i comuni, e il
    # danno si sarebbe visto solo al comune successivo.
    colonna = porta_la_colonna_dataset(percorso_gpkg)
    if colonna is None:
        return Piano(RIFIUTA, comune, (
            "Il GeoPackage non contiene nessuna tabella di dati: lo schema "
            "non c'e' o e' incompleto. Va rifatto da zero."))
    if not colonna:
        return Piano(RIFIUTA, comune, (
            "Questo archivio e' stato creato prima del supporto a piu' "
            "comuni: le tabelle non hanno la colonna T_datasetname. "
            "Aggiungendoci un comune, le righe gia' presenti resterebbero "
            "senza proprietario e nessun filtro potrebbe piu' separarle. "
            "Va rifatto da zero."))

    if comune.dataset in presenti:
        return Piano(SOSTITUISCI, comune, presenti=presenti)
    return Piano(AGGIUNGI, comune, presenti=presenti)


def _modelli_gpkg(percorso_gpkg):
    """I modelli registrati da ili2gpkg. Duplicato leggero di
    modello.modelli_di_gpkg per non far dipendere il registro da quel modulo:
    qui serve solo sapere SE ci sono e QUALI, senza il giudizio."""
    con = _apri(percorso_gpkg)
    if con is None:
        return []
    try:
        nomi = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND lower(name)='t_ili2db_model'")]
        if not nomi:
            return []
        modelli = []
        for (valore,) in con.execute("SELECT modelName FROM %s" % nomi[0]):
            for pezzo in str(valore or "").replace(";", " ").replace(",", " ").split():
                if pezzo and pezzo not in modelli:
                    modelli.append(pezzo)
        return modelli
    except sqlite3.Error:
        return []
    finally:
        con.close()


def disallineati(percorso_gpkg):
    """(nei_dati_non_a_registro, a_registro_non_nei_dati).

    Un archivio sano ha tutt'e due vuoti. Il primo caso vuol dire che qualcuno
    ha importato fuori dal plugin: quel comune c'e' ma non sappiamo da quale
    ITF, quindi non se ne puo' fare il DXF. Il secondo che il registro promette
    un comune che nei dati non c'e' piu'."""
    dati = set(dataset_nel_gpkg(percorso_gpkg))
    registro = set(r["numero"] for r in registrati(percorso_gpkg))
    return sorted(dati - registro), sorted(registro - dati)
