# Scaricamento dei dati della misurazione ufficiale dal portale del Cantone
# Ticino (data.geo.ti.ch).
#
# PERCHE' NON geodienste.ch: quel portale pubblica la MU di tutti i cantoni nel
# MODELLO FEDERALE (MD01MUCH24MN95I, versione 24). Il plugin, il jar av2geobau_ti
# e tutte le tabelle di stile lavorano invece sul MODELLO CANTONALE TICINESE
# MD01MUTI7MN95 (versione 1.7), che e' un modello diverso: nomi di classe,
# attributi e domini non coincidono. Un ITF preso da geodienste non
# attraverserebbe la catena senza riscriverla. Il portale cantonale pubblica
# esattamente il modello che serve - verificato leggendo la riga MODL di un
# archivio scaricato.
#
# COM'E' FATTO IL PORTALE (verificato sul posto, non dedotto):
#  - l'indice sta su ?p=ti_mu_version1_7_mn95 ed e' una tabella HTML con una
#    riga per comune: archivio, nome, data, dimensione;
#  - il link della tabella porta a una pagina di dettaglio, NON all'archivio;
#  - l'archivio vero sta su /geodata/ti_mu_version1_7_mn95/<codice>.zip e si
#    scarica senza sessione ne' cookie;
#  - dentro l'archivio ci sono tre file: <codice>.itf, <codice>.itf.md5 e
#    <codice>.log.
#
# L'IMPRONTA SI CONTROLLA. Il file .itf.md5 contiene l'MD5 dell'ITF calcolato
# dal Cantone: si ricalcola dopo l'estrazione e si confronta. Un ITF troncato da
# una connessione caduta a meta' e' altrimenti indistinguibile da uno buono
# finche' ili2gpkg non fallisce a meta' importazione, con un errore che parla
# d'altro.
import hashlib
import os
import re
import zipfile
from urllib.request import Request, urlopen

# Il portale e' un TYPO3: l'identificativo del prodotto e' la versione del
# modello, quindi cambiera' se e quando il Cantone passera' a un modello nuovo.
PRODOTTO = "ti_mu_version1_7_mn95"
URL_INDICE = "https://data.geo.ti.ch/?p=" + PRODOTTO
URL_ARCHIVIO = "https://data.geo.ti.ch/geodata/%s/%%s" % PRODOTTO
URL_CONDIZIONI = ("https://www4.ti.ch/dt/sg/sai/ugeo/temi/geoportale-ticino/"
                  "geoportale/condizioni-di-utilizzo")
MODELLO_ATTESO = "MD01MUTI7MN95"

# Il portale non e' un servizio a contratto: un'attesa lunga e' un guasto, non
# una coda. Trenta secondi per l'indice (81 KB), di piu' per gli archivi, che
# arrivano a 30 MB.
TIMEOUT_INDICE = 30
TIMEOUT_ARCHIVIO = 300

# Il portale risponde in ISO-8859-1 e lo dichiara: i nomi con accento
# (Brè, Someo) escono a pezzi se li si legge come UTF-8.
CODIFICA_PAGINA = "iso-8859-1"

_INTESTAZIONE = {"User-Agent": "TIDashboard (QGIS plugin)"}

# Una riga della tabella: quattro celle in quest'ordine. Il link all'archivio e'
# l'unica ancora affidabile della riga - il resto e' formattazione, e cambia.
_RIGA = re.compile(
    r'<a[^>]+href="[^"]*[?&]f=(?P<archivio>[^"&]+\.zip)"[^>]*>.*?</a>\s*</td>'
    r'\s*<td[^>]*>(?P<nome>.*?)</td>'
    r'\s*<td[^>]*>(?P<data>.*?)</td>'
    r'\s*<td[^>]*>(?P<dimensione>.*?)</td>',
    re.S | re.I)
_TAG = re.compile(r"<[^>]+>")


class ComuneMU(object):
    """Una riga dell'indice: l'archivio di un comune (o di una comunanza)."""

    __slots__ = ("archivio", "nome", "data", "dimensione")

    def __init__(self, archivio, nome, data, dimensione):
        self.archivio = archivio
        self.nome = nome
        self.data = data
        self.dimensione = dimensione

    @property
    def codice(self):
        """Il numero che da' il nome a tutto: 5304000101.zip -> 5304000101.
        E' anche il nome dell'ITF che si trova dentro."""
        return self.archivio[:-4] if self.archivio.endswith(".zip") else self.archivio

    @property
    def url(self):
        return URL_ARCHIVIO % self.archivio

    def __repr__(self):
        return "ComuneMU(%s, %s, %s, %s)" % (self.archivio, self.nome,
                                             self.data, self.dimensione)


def _testo(html):
    return _TAG.sub("", html).replace("&nbsp;", " ").strip()


def leggi_indice(html):
    """L'elenco dei comuni a partire dalla pagina dell'indice.

    Funzione pura, cosi' il formato della pagina si prova su un campione
    salvato invece che sulla rete: e' l'unica parte che il Cantone puo'
    cambiare sotto i piedi senza preavviso."""
    comuni = []
    visti = set()
    for m in _RIGA.finditer(html or ""):
        archivio = m.group("archivio").strip()
        if archivio in visti:
            continue        # la stessa riga compare due volte nelle pagine con filtro
        visti.add(archivio)
        comuni.append(ComuneMU(archivio, _testo(m.group("nome")),
                               _testo(m.group("data")),
                               _testo(m.group("dimensione"))))
    return comuni


def _apri(url, timeout):
    return urlopen(Request(url, headers=_INTESTAZIONE), timeout=timeout)


def scarica_indice(apri=None):
    """L'elenco dei comuni, dalla rete. 'apri' esiste per i test."""
    apri = apri or _apri
    risposta = apri(URL_INDICE, TIMEOUT_INDICE)
    try:
        grezzo = risposta.read()
    finally:
        chiudi = getattr(risposta, "close", None)
        if chiudi:
            chiudi()
    return leggi_indice(grezzo.decode(CODIFICA_PAGINA, "replace"))


def scarica_archivio(comune, cartella, progresso=None, annullato=None,
                     apri=None):
    """Scarica lo zip di un comune. Ritorna il percorso del file scaricato.

    'progresso' riceve (byte_finora, byte_totali) - totali puo' essere 0 se il
    server non dichiara la lunghezza. 'annullato' e' una funzione che, tornando
    True, interrompe: senza, un download da 30 MB su una linea lenta bloccherebbe
    l'utente fino alla fine o fino al timeout."""
    apri = apri or _apri
    url = comune.url if isinstance(comune, ComuneMU) else str(comune)
    nome = url.rsplit("/", 1)[-1]
    destinazione = os.path.join(cartella, nome)
    # Si scrive su un file provvisorio e si rinomina alla fine: un archivio
    # interrotto non deve restare in giro con il nome di uno buono.
    parziale = destinazione + ".parte"
    risposta = apri(url, TIMEOUT_ARCHIVIO)
    try:
        try:
            totali = int(risposta.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            totali = 0
        fatti = 0
        with open(parziale, "wb") as uscita:
            while True:
                if annullato and annullato():
                    raise InterruttoDallUtente()
                pezzo = risposta.read(64 * 1024)
                if not pezzo:
                    break
                uscita.write(pezzo)
                fatti += len(pezzo)
                if progresso:
                    progresso(fatti, totali)
    except BaseException:
        if os.path.exists(parziale):
            os.remove(parziale)
        raise
    finally:
        chiudi = getattr(risposta, "close", None)
        if chiudi:
            chiudi()
    if os.path.exists(destinazione):
        os.remove(destinazione)
    os.rename(parziale, destinazione)
    return destinazione


class InterruttoDallUtente(Exception):
    pass


class ArchivioNonValido(Exception):
    pass


def _nome_sicuro(nome):
    """Il nome di un membro dell'archivio, ridotto al solo nome di file.

    Uno zip puo' contenere percorsi assoluti o con '..' e far scrivere fuori
    dalla cartella di destinazione (Zip Slip). Che l'archivio arrivi da un
    portale pubblico su HTTPS non e' un controllo: e' una provenienza.

    Regola: una risalita ('..'), un percorso assoluto o una lettera di unita'
    sono un rifiuto, non una forma da assecondare - negli archivi del Cantone
    ci sono tre file piatti e nient'altro. Una sottocartella qualsiasi viene
    invece appiattita alla sola foglia, che e' innocua."""
    nome = (nome or "").replace("\\", "/")
    pezzi = nome.split("/")
    if (nome.startswith("/") or ":" in nome
            or any(p in ("..", ".") for p in pezzi)):
        raise ArchivioNonValido("nome di file non ammesso nell'archivio: %r" % nome)
    foglia = pezzi[-1]
    if not foglia:
        raise ArchivioNonValido("nome di file non ammesso nell'archivio: %r" % nome)
    return foglia


def _md5(percorso):
    somma = hashlib.md5()
    with open(percorso, "rb") as f:
        for pezzo in iter(lambda: f.read(1024 * 1024), b""):
            somma.update(pezzo)
    return somma.hexdigest().upper()


def estrai_itf(percorso_zip, cartella, log=None):
    """Estrae l'ITF (e i file che l'accompagnano) e ne controlla l'impronta.

    Ritorna il percorso dell'ITF estratto. Solleva ArchivioNonValido se l'ITF
    non c'e', se un nome di file e' pericoloso o se l'MD5 non torna."""
    with zipfile.ZipFile(percorso_zip) as z:
        membri = [(n, _nome_sicuro(n)) for n in z.namelist()]
        itf = [(n, f) for n, f in membri if f.lower().endswith(".itf")]
        if not itf:
            raise ArchivioNonValido(
                "nell'archivio non c'e' nessun .itf: %s"
                % ", ".join(f for _n, f in membri))
        for nome, foglia in membri:
            with z.open(nome) as dentro:
                with open(os.path.join(cartella, foglia), "wb") as fuori:
                    while True:
                        pezzo = dentro.read(1024 * 1024)
                        if not pezzo:
                            break
                        fuori.write(pezzo)
    percorso_itf = os.path.join(cartella, itf[0][1])
    atteso = os.path.join(cartella, itf[0][1] + ".md5")
    if os.path.exists(atteso):
        with open(atteso, "rb") as f:
            dichiarato = f.read().decode("ascii", "replace").strip().upper()
        calcolato = _md5(percorso_itf)
        if dichiarato and dichiarato != calcolato:
            os.remove(percorso_itf)
            raise ArchivioNonValido(
                "l'impronta dell'ITF non torna: il Cantone dichiara %s, il file "
                "scaricato vale %s. Scaricalo di nuovo." % (dichiarato, calcolato))
        if log:
            log("   🔒 Impronta MD5 verificata: %s" % calcolato)
    elif log:
        log("   ⚠️ L'archivio non porta il file .md5: impronta non verificata")
    return percorso_itf


def modello_dichiarato(percorso_itf):
    """La riga MODL dell'ITF, cioe' il modello dei dati. Si legge solo la testa
    del file: l'intestazione INTERLIS 1 sta nelle prime righe e i file arrivano
    a centinaia di MB."""
    try:
        with open(percorso_itf, "rb") as f:
            testa = f.read(4096).decode("latin-1", "replace")
    except OSError:
        return ""
    m = re.search(r"^MODL\s+(\S+)", testa, re.M)
    return m.group(1) if m else ""
