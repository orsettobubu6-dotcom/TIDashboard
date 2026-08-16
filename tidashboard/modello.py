# Il modello dei dati: quale sia, e se e' quello su cui il plugin e' tarato.
#
# PERCHE' UN MODULO A PARTE. Il controllo serviva prima in un punto solo (lo
# scaricamento dal portale) e stava li'. Ma il modello sbagliato puo' entrare da
# ogni porta - un ITF ricevuto per posta, un GeoPackage importato mesi fa da
# qualcun altro, un secondo ITF scelto a mano per la sola conversione DXF - e un
# controllo che sta in una porta sola non e' un controllo, e' un promemoria.
# Qui c'e' la definizione, e ogni passo la chiama.
#
# COSA CAMBIA FRA I DUE MODELLI. Il Ticino usa MD01MUTI7MN95 (modello cantonale,
# versione 1.7). La Confederazione pubblica gli stessi temi in MD01MUCH24MN95I
# (versione 24): e' quello che si scarica da geodienste.ch, e non e' una
# variante ma un modello diverso - classi, attributi e domini non coincidono.
# Tutta la catena del plugin (nomi di tabella, regole di stile, ordine di
# disegno, mappature del traduttore DXF) e' scritta sul primo.
#
# DOVE STA SCRITTO IL MODELLO:
#  - in un ITF (INTERLIS 1) sta nella riga MODL dell'intestazione, entro le
#    prime righe del file;
#  - in un GeoPackage prodotto da ili2gpkg sta nella tabella T_ILI2DB_MODEL,
#    colonna modelName.
import os
import re
import sqlite3

MODELLO_ATTESO = "MD01MUTI7MN95"

# Il modello federale, citato per nome: quando compare, il messaggio puo' dire
# da dove arriva il file invece di limitarsi a dire che e' diverso.
MODELLO_FEDERALE = "MD01MUCH24MN95I"

# Esiti possibili. Si distingue "diverso" da "non trovato" perche' meritano
# risposte diverse: il primo e' un fatto certo e ferma il lavoro, il secondo e'
# un'incertezza e si limita ad avvisare. Trattarli allo stesso modo vorrebbe
# dire o bloccare su un dubbio o lasciar passare una certezza.
OK = "ok"
DIVERSO = "diverso"
NON_TROVATO = "non_trovato"
NON_LEGGIBILE = "non_leggibile"

_MODL = re.compile(r"^MODL\s+(\S+)", re.M)

# L'intestazione INTERLIS 1 sta nelle prime righe; i file arrivano a 200 MB e
# leggerli interi per una riga sarebbe assurdo.
_TESTA = 4096


def modello_di_itf(percorso):
    """Il modello dichiarato da un ITF, o "" se non si trova."""
    try:
        with open(percorso, "rb") as f:
            testa = f.read(_TESTA).decode("latin-1", "replace")
    except OSError:
        return ""
    m = _MODL.search(testa)
    return m.group(1) if m else ""


def modelli_di_gpkg(percorso):
    """I modelli registrati da ili2gpkg in un GeoPackage.

    Lista, non stringa singola: un GeoPackage puo' portare piu' di un modello
    importato. Vuota se la tabella non c'e' - cioe' se il GeoPackage non e'
    stato prodotto da ili2gpkg, il che e' esso stesso un'informazione."""
    if not os.path.isfile(percorso):
        return []
    try:
        # Sola lettura e senza creare il file: aprire in scrittura un
        # GeoPackage che QGIS sta gia' usando lo bloccherebbe.
        con = sqlite3.connect("file:%s?mode=ro" % percorso.replace("?", "%3f"),
                              uri=True)
    except sqlite3.Error:
        return []
    try:
        nomi = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND lower(name)='t_ili2db_model'")]
        if not nomi:
            return []
        modelli = []
        for (valore,) in con.execute("SELECT modelName FROM %s" % nomi[0]):
            for pezzo in re.split(r"[;,\s]+", str(valore or "")):
                if pezzo and pezzo not in modelli:
                    modelli.append(pezzo)
        return modelli
    except sqlite3.Error:
        return []
    finally:
        con.close()


def controlla_itf(percorso):
    """(esito, modello) per un ITF."""
    if not percorso or not os.path.isfile(percorso):
        return NON_LEGGIBILE, ""
    trovato = modello_di_itf(percorso)
    if not trovato:
        return NON_TROVATO, ""
    return (OK if trovato == MODELLO_ATTESO else DIVERSO), trovato


def controlla_gpkg(percorso):
    """(esito, modello) per un GeoPackage prodotto da ili2gpkg."""
    if not percorso or not os.path.isfile(percorso):
        return NON_LEGGIBILE, ""
    modelli = modelli_di_gpkg(percorso)
    if not modelli:
        return NON_TROVATO, ""
    if MODELLO_ATTESO in modelli:
        return OK, MODELLO_ATTESO
    return DIVERSO, ", ".join(modelli)


def spiega(esito, modello, cosa="il file"):
    """Il messaggio da mostrare, o "" quando non c'e' niente da dire.

    Il testo nomina il modello trovato e quello atteso: "modello sbagliato"
    senza i due nomi obbliga chi legge a indovinare quale file ha in mano."""
    if esito == OK:
        return ""
    if esito == DIVERSO:
        testo = ("%s dichiara il modello %s invece di %s: le tabelle, gli stili "
                 "e le mappature DXF del plugin sono scritti sul modello "
                 "cantonale e non riconoscerebbero queste classi."
                 % (cosa[0].upper() + cosa[1:], modello, MODELLO_ATTESO))
        if MODELLO_FEDERALE in (modello or ""):
            testo += (" %s e' il modello federale pubblicato da geodienste.ch; "
                      "l'equivalente cantonale si scarica dal pulsante "
                      "\"Cantone...\"." % MODELLO_FEDERALE)
        return testo
    if esito == NON_TROVATO:
        return ("In %s non si trova la dichiarazione del modello: non posso "
                "verificare che sia %s." % (cosa, MODELLO_ATTESO))
    return ""


def e_bloccante(esito):
    """Un modello DIVERSO ferma il lavoro; un modello che non si trova no.

    Il primo e' un fatto letto nel file, e proseguire vorrebbe dire far girare
    per minuti un'importazione che non puo' che fallire. Il secondo e'
    un'incertezza nostra - un'intestazione insolita, un file troncato in testa -
    e bloccare su un dubbio toglierebbe all'utente una decisione che e' sua."""
    return esito == DIVERSO
