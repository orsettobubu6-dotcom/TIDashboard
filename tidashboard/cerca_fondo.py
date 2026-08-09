# TIDashboard - dati della misurazione ufficiale svizzera in QGIS
# Copyright (C) 2026 Gabriele Peverelli
#
# Questo programma e' software libero: lo si puo' ridistribuire e modificare
# secondo i termini della GNU General Public License pubblicata dalla Free
# Software Foundation, versione 2 o (a scelta) una successiva. Il testo si
# trova nel file LICENSE distribuito insieme al programma.

# Ricerca di un fondo nel GeoPackage, modello MD01MUTI7MN95, TOPIC
# Beni_immobili.
#
# QUI NON SI IMPORTA QGIS. La ricerca e' interrogazione di un GeoPackage,
# cioe' di un file SQLite: tenerla separata dall'interfaccia la rende
# provabile senza costruire una finestra, ed e' il motivo per cui anche le
# estensioni si calcolano leggendo il formato invece di chiedere a QGIS.
#
# LE DUE COSE DA SAPERE SUL MODELLO
#
# 1. La chiave di un fondo NON e' il numero: e' la coppia (IdentAN, Numero).
#    IdentAN e' composto TICCCSS, dove CCC e' il numero del comune (quello
#    fiscale cantonale, cfr. Comune.Nofisc) e SS il numero di SEZIONE. Molti
#    comuni ticinesi hanno piu' sezioni, e lo stesso numero si ripete in
#    ognuna: su Mendrisio (TI632, dieci sezioni) il numero 99 esiste in tutte
#    e dieci. Per questo cerca() restituisce SEMPRE una lista e non il primo
#    risultato: scegliere per conto dell'utente vorrebbe dire portarlo sul
#    fondo sbagliato nove volte su dieci, senza dirglielo.
#
# 2. Il Fondo NON ha geometria. La geometria sta sulle sue parti -
#    Bene_immobile, DPSSP, Miniera - e un fondo puo' averne piu' d'una
#    (Superficie_totale nel modello esiste proprio per quel caso), quindi
#    l'estensione e' l'unione delle parti. Se non ce n'e' nessuna si ripiega
#    su PosFondo, che e' il punto di iscrizione del numero: non e' la
#    geometria del fondo, ma dice dove si trova, ed e' meglio di niente.
import os
import re
import sqlite3
import struct

# Numero massimo di risultati restituiti. Non e' una preferenza: senza,
# cercare un numero frequente su un cantone intero riempirebbe l'elenco di
# migliaia di righe che nessuno scorre.
LIMITE_RISULTATI = 50

# Suffissi delle tabelle. Non si cablano i nomi completi: ili2gpkg li compone
# da topic e classe e la regola e' cambiata fra le versioni (vedi la stessa
# scelta in dati_comune.py). Si cercano per forma.
SUFFISSO_FONDO = "_fondo"
SUFFISSI_PARTI = ("_bene_immobile", "_dpssp", "_miniera")
SUFFISSO_POSFONDO = "_posfondo"
SUFFISSO_COMUNE = "_comune"

# Gli oggetti "in progetto" non fanno parte del contenuto del piano (cap.
# 1.5.3) e non sono un fondo esistente: si escludono per difetto.
SUFFISSO_PROG = "prog"


class FondoTrovato(object):
    """Un fondo, con quanto serve per mostrarlo e per andarci sopra.

    'extent' e 'centro' sono in EPSG:2056 e possono essere None: un fondo
    senza geometria ne' PosFondo esiste nei dati ma non si sa dove sia, e
    dirlo e' piu' onesto che centrarsi su coordinate inventate."""

    __slots__ = ("identan", "numero", "sezione", "comune_nr", "comune",
                 "egrid", "validita", "integralita", "genere", "superficie",
                 "extent", "centro", "origine_geometria", "n_parti")

    def __init__(self, **kw):
        for nome in self.__slots__:
            setattr(self, nome, kw.get(nome))

    @property
    def etichetta(self):
        """Riga da mostrare nell'elenco. La SEZIONE viene per prima dopo il
        numero: e' l'informazione che distingue due risultati altrimenti
        identici, e metterla in fondo la renderebbe invisibile."""
        pezzi = ["Fondo %s" % (self.numero or "?")]
        if self.sezione:
            pezzi.append("sezione %s" % self.sezione)
        if self.comune:
            pezzi.append(self.comune)
        if self.superficie:
            pezzi.append("%s m²" % self.superficie)
        if self.validita and self.validita != "in_vigore":
            pezzi.append(self.validita)
        if self.extent is None:
            pezzi.append("senza geometria")
        return " · ".join(pezzi)

    def __repr__(self):
        return "<FondoTrovato %s/%s>" % (self.identan, self.numero)


def sezione_di(identan):
    """Le ultime due cifre di IdentAN (TICCCSS). None se non e' della forma
    attesa: meglio nessuna sezione che una inventata tagliando una stringa
    di lunghezza diversa."""
    if not identan:
        return None
    testo = str(identan).strip()
    if len(testo) < 3 or not testo[-2:].isdigit():
        return None
    return testo[-2:]


def comune_di(identan):
    """Le cifre del comune in IdentAN (TICCCSS): quanto sta fra il prefisso
    cantonale e le due cifre di sezione."""
    if not identan:
        return None
    testo = str(identan).strip()
    cifre = "".join(c for c in testo if c.isdigit())
    if len(cifre) < 3:
        return None
    return cifre[:-2] or None


def normalizza_numero(numero):
    """Forma di confronto del numero di fondo.

    Gli zeri iniziali si tolgono SOLO se il numero e' tutto cifre: '0452' e
    '452' sono lo stesso fondo, ma un numero che contiene lettere (parti di
    fondo, casi cantonali) va confrontato per come e' scritto, altrimenti
    '0A' e 'A' verrebbero confusi."""
    if numero is None:
        return None
    testo = str(numero).strip()
    if not testo:
        return None
    if testo.isdigit():
        return str(int(testo))
    return testo


# "452-01", "452 / 01", "452/1", "452.01": numero e sezione in un campo solo.
# Il separatore e' uno qualunque fra - / . spazio, con spazi facoltativi
# attorno; la sezione e' di una o due cifre.
_SEPARATO = re.compile(r"^\s*(?P<numero>[0-9A-Za-z]+)\s*[-/.\s]\s*(?P<sezione>\d{1,2})\s*$")


def analizza_ricerca(testo):
    """Divide un testo di ricerca in (numero, sezione).

    Serve perche' il modo naturale di scrivere un fondo di un comune con
    sezioni e' "452-01", non due campi separati. Se non c'e' separatore la
    sezione resta None e la ricerca la cerchera' in tutte."""
    if not testo:
        return None, None
    testo = str(testo).strip()
    if not testo:
        return None, None
    m = _SEPARATO.match(testo)
    if m:
        return m.group("numero"), m.group("sezione").zfill(2)
    return testo, None


# --- lettura del GeoPackage ------------------------------------------------

def _tabelle(con):
    return [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]


def _colonne(con, tabella):
    return [r[1].lower() for r in con.execute('PRAGMA table_info("%s")' % tabella)]


def _senza_prog(nomi):
    return [n for n in nomi if not n.lower().endswith(SUFFISSO_PROG)]


def _trova_tabelle(con, includi_prog=False):
    """Individua per forma le tabelle che servono. Ritorna un dizionario;
    'fondo' e' l'unica indispensabile."""
    tutte = _tabelle(con)
    def per_suffisso(suffisso):
        trovate = [t for t in tutte if t.lower().endswith(suffisso)]
        return trovate if includi_prog else _senza_prog(trovate)

    fondo = None
    for t in per_suffisso(SUFFISSO_FONDO):
        # La tabella giusta e' quella con la chiave del modello: cosi' non si
        # confonde con eventuali omonimie (p.es. una vista o PosFondo).
        col = _colonne(con, t)
        if "identan" in col and "numero" in col:
            fondo = t
            break
    parti = []
    for suffisso in SUFFISSI_PARTI:
        for t in per_suffisso(suffisso):
            col = _colonne(con, t)
            riferimento = [c for c in col if c.endswith("_di")]
            if "geometria" in col and riferimento:
                parti.append((t, riferimento[0]))
    posfondo = None
    for t in per_suffisso(SUFFISSO_POSFONDO):
        col = _colonne(con, t)
        if "pos" in col and any(c.endswith("_di") for c in col):
            posfondo = (t, [c for c in col if c.endswith("_di")][0])
            break
    comune = None
    for t in tutte:
        if t.lower().endswith(SUFFISSO_COMUNE) and "nome" in _colonne(con, t):
            comune = t
            break
    return {"fondo": fondo, "parti": parti, "posfondo": posfondo, "comune": comune}


def _envelope(blob):
    """Estensione di una geometria GeoPackage, letta dall'INTESTAZIONE del
    blob invece che decodificando la geometria.

    Il formato GPKG mette un envelope facoltativo subito dopo l'intestazione
    di 8 byte; il bit 0 dei flag da' l'ordine dei byte e i bit 1-3 dicono
    quante coordinate ha (1 = xy, cioe' quattro double: minx, maxx, miny,
    maxy). Verificato sui dati reali: flag 0x02 -> big endian, envelope xy, e
    i byte 4-7 valgono 2056, cioe' proprio EPSG:2056.

    Ritorna (xmin, ymin, xmax, ymax) oppure None se l'envelope non c'e' -
    caso ammesso dal formato, e in quel caso non si prova a decodificare la
    geometria: si ripiega piu' in alto su PosFondo."""
    if not blob or len(blob) < 8:
        return None
    b = bytes(blob)
    if b[0:2] != b"GP":
        return None
    flag = b[3]
    ordine = "<" if (flag & 1) else ">"
    codice = (flag >> 1) & 7
    if codice != 1:                      # 0 = assente; 2..4 = con z/m
        if codice in (2, 3, 4):
            n = {2: 6, 3: 6, 4: 8}[codice]
            valori = struct.unpack_from(ordine + "%dd" % n, b, 8)
            return (valori[0], valori[2], valori[1], valori[3])
        return None
    minx, maxx, miny, maxy = struct.unpack_from(ordine + "4d", b, 8)
    return (minx, miny, maxx, maxy)


def _punto(blob):
    """Coordinate di un POINT GeoPackage, per il ripiego su PosFondo. Se
    l'envelope c'e' lo si usa; altrimenti si legge il WKB, che per un punto
    e' corto e sicuro da decodificare."""
    est = _envelope(blob)
    if est:
        return (est[0], est[1])
    if not blob or len(blob) < 8:
        return None
    b = bytes(blob)
    flag = b[3]
    codice = (flag >> 1) & 7
    salta = 8 + {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}.get(codice, 0)
    if len(b) < salta + 21:
        return None
    ordine = "<" if b[salta] else ">"
    tipo = struct.unpack_from(ordine + "I", b, salta + 1)[0]
    if tipo % 1000 != 1:                 # non e' un punto
        return None
    x, y = struct.unpack_from(ordine + "2d", b, salta + 5)
    return (x, y)


def _unione(estensioni):
    valide = [e for e in estensioni if e]
    if not valide:
        return None
    return (min(e[0] for e in valide), min(e[1] for e in valide),
            max(e[2] for e in valide), max(e[3] for e in valide))


def _nomi_comune(con, tabella):
    """{numero fiscale: nome} dalla tabella dei comuni. Il numero fiscale e'
    il CCC di IdentAN, quindi permette di dare un nome alla sezione trovata."""
    if not tabella:
        return {}
    col = _colonne(con, tabella)
    if "nofisc" not in col:
        return {}
    fuori = {}
    for nofisc, nome in con.execute('SELECT nofisc, nome FROM "%s"' % tabella):
        if nofisc is not None:
            fuori[str(nofisc)] = nome
    return fuori


def sezioni_disponibili(percorso_gpkg):
    """Elenco ordinato delle sezioni presenti (le SS di IdentAN), per
    riempire la casella a discesa. Lista vuota se il comune non ha sezioni o
    se il file non si legge."""
    con = _apri(percorso_gpkg)
    if con is None:
        return []
    try:
        t = _trova_tabelle(con)
        if not t["fondo"]:
            return []
        viste = set()
        for (identan,) in con.execute('SELECT DISTINCT identan FROM "%s"' % t["fondo"]):
            s = sezione_di(identan)
            if s:
                viste.add(s)
        return sorted(viste)
    except sqlite3.Error:
        return []
    finally:
        con.close()


def _apri(percorso_gpkg):
    if not percorso_gpkg or not os.path.isfile(str(percorso_gpkg)):
        return None
    try:
        # Sola lettura: la ricerca non deve poter toccare i dati.
        return sqlite3.connect("file:%s?mode=ro" % str(percorso_gpkg), uri=True)
    except sqlite3.Error:
        return None


def cerca(percorso_gpkg, numero=None, sezione=None, comune=None, egrid=None,
          solo_in_vigore=True, includi_prog=False, limite=LIMITE_RISULTATI):
    """Cerca i fondi che corrispondono ai criteri indicati.

    Ritorna SEMPRE una lista, anche con un solo risultato: la
    disambiguazione fra sezioni e' obbligatoria (vedi la nota in testa al
    modulo) e restituire un oggetto solo inviterebbe a saltarla.

    'numero'  numero del fondo; accetta anche "452-01" (vedi analizza_ricerca)
    'sezione' due cifre; se indicata vince su quella dedotta dal numero
    'comune'  nome o numero fiscale del comune
    'egrid'   identificatore federale; se indicato basta da solo
    'solo_in_vigore' esclude i fondi contestati
    'includi_prog'   include gli oggetti in progetto (per difetto no)
    """
    con = _apri(percorso_gpkg)
    if con is None:
        return []
    try:
        return _cerca(con, numero, sezione, comune, egrid, solo_in_vigore,
                      includi_prog, limite)
    except sqlite3.Error:
        return []
    finally:
        con.close()


def _cerca(con, numero, sezione, comune, egrid, solo_in_vigore, includi_prog,
           limite):
    t = _trova_tabelle(con, includi_prog)
    if not t["fondo"]:
        return []
    col_fondo = _colonne(con, t["fondo"])

    # Il numero puo' portarsi dietro la sezione ("452-01"): si divide qui, e
    # una sezione indicata a parte ha comunque la precedenza.
    numero_pulito, sezione_dal_numero = analizza_ricerca(numero)
    sezione = (sezione or sezione_dal_numero or "").strip() or None
    if sezione:
        sezione = sezione.zfill(2)

    # I CRITERI DI RICERCA sono il numero e l'EGRID; sezione, comune e
    # validita' sono FILTRI, cioe' restringono un risultato, non lo cercano.
    # Senza questa distinzione una ricerca a campi vuoti passava comunque
    # (bastava il filtro sulla validita' a rendere la clausola non vuota) e
    # restituiva i primi 50 fondi del comune, come se li avesse trovati.
    if not (numero and str(numero).strip()) and not (egrid and str(egrid).strip()):
        return []

    dove, valori = [], []
    if egrid and "egris_egrid" in col_fondo:
        dove.append("UPPER(egris_egrid) = ?")
        valori.append(str(egrid).strip().upper())
    if numero_pulito:
        # Il confronto e' sulla forma normalizzata, ma il numero e' TEXT nel
        # modello: si confronta anche la forma grezza, cosi' un numero non
        # numerico continua a trovarsi.
        norm = normalizza_numero(numero_pulito)
        dove.append("(numero = ? OR numero = ? OR "
                    "(numero GLOB '[0-9]*' AND NOT numero GLOB '*[^0-9]*' "
                    " AND CAST(numero AS INTEGER) = CAST(? AS INTEGER)))")
        valori += [str(numero_pulito).strip(), norm, norm]
    if sezione:
        dove.append("substr(identan, -2) = ?")
        valori.append(sezione)
    if solo_in_vigore and "validita" in col_fondo:
        dove.append("validita = 'in_vigore'")
    if comune:
        nomi = _nomi_comune(con, t["comune"])
        testo = str(comune).strip()
        numeri = [k for k, v in nomi.items()
                  if v and v.lower() == testo.lower()] or [testo]
        segnaposti = ",".join("?" for _ in numeri)
        # CCC di IdentAN: tutto quello che sta fra "TI" e le due cifre finali.
        dove.append("substr(identan, 3, length(identan) - 4) IN (%s)" % segnaposti)
        valori += [str(n) for n in numeri]

    if not dove:
        return []

    sql = ('SELECT T_Id, identan, numero, %s, %s, %s, %s, %s FROM "%s" WHERE %s '
           'ORDER BY identan, numero LIMIT ?'
           % ("egris_egrid" if "egris_egrid" in col_fondo else "NULL",
              "validita" if "validita" in col_fondo else "NULL",
              "integralita" if "integralita" in col_fondo else "NULL",
              "genere" if "genere" in col_fondo else "NULL",
              "superficie_totale" if "superficie_totale" in col_fondo else "NULL",
              t["fondo"], " AND ".join(dove)))
    righe = con.execute(sql, valori + [int(limite)]).fetchall()
    if not righe:
        return []

    nomi = _nomi_comune(con, t["comune"])
    ids = [r[0] for r in righe]
    estensioni, quante = _estensioni_parti(con, t["parti"], ids)
    mancanti = [i for i in ids if i not in estensioni]
    ripiego = _estensioni_posfondo(con, t["posfondo"], mancanti)

    fuori = []
    for (tid, identan, num, egr, val, integ, gen, sup) in righe:
        est = estensioni.get(tid)
        origine = "geometria" if est else None
        if est is None:
            est = ripiego.get(tid)
            origine = "posizione del numero" if est else None
        centro = None
        if est:
            centro = ((est[0] + est[2]) / 2.0, (est[1] + est[3]) / 2.0)
        cnum = comune_di(identan)
        fuori.append(FondoTrovato(
            identan=identan, numero=num, sezione=sezione_di(identan),
            comune_nr=cnum, comune=nomi.get(cnum), egrid=egr, validita=val,
            integralita=integ, genere=gen, superficie=sup,
            extent=est, centro=centro, origine_geometria=origine,
            n_parti=quante.get(tid, 0)))
    return fuori


def _estensioni_parti(con, parti, ids):
    """Estensione di ogni fondo come UNIONE delle sue parti: un fondo puo'
    essere fatto di piu' Bene_immobile/DPSSP/Miniera, e prendere solo il
    primo darebbe un'estensione che non contiene il resto."""
    per_id, quante = {}, {}
    if not ids:
        return per_id, quante
    segnaposti = ",".join("?" for _ in ids)
    for tabella, riferimento in parti:
        sql = ('SELECT "%s", geometria FROM "%s" WHERE "%s" IN (%s)'
               % (riferimento, tabella, riferimento, segnaposti))
        for tid, blob in con.execute(sql, ids):
            est = _envelope(blob)
            if not est:
                continue
            quante[tid] = quante.get(tid, 0) + 1
            per_id[tid] = _unione([per_id.get(tid), est])
    return per_id, quante


def _estensioni_posfondo(con, posfondo, ids):
    """Ripiego: il punto di iscrizione del numero. Non e' la geometria del
    fondo - e' dove si scrive il suo numero - ma dice in che parte del piano
    si trova."""
    fuori = {}
    if not posfondo or not ids:
        return fuori
    tabella, riferimento = posfondo
    segnaposti = ",".join("?" for _ in ids)
    sql = ('SELECT "%s", pos FROM "%s" WHERE "%s" IN (%s)'
           % (riferimento, tabella, riferimento, segnaposti))
    for tid, blob in con.execute(sql, ids):
        p = _punto(blob)
        if p:
            fuori[tid] = (p[0], p[1], p[0], p[1])
    return fuori
