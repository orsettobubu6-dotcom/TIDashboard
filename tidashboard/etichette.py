# TIDashboard - dati della misurazione ufficiale svizzera in QGIS
# Copyright (C) 2026 Gabriele Peverelli
#
# Questo programma e' software libero: lo si puo' ridistribuire e modificare
# secondo i termini della GNU General Public License pubblicata dalla Free
# Software Foundation, versione 2 o (a scelta) una successiva. Il testo si
# trova nel file LICENSE distribuito insieme al programma.

# Regole delle etichette testuali, estratte da tidashboard.py.
#
# Sono dati puri, senza dipendenze da QGIS: la tabella delle grandezze
# normative (cap.5 delle istruzioni federali) e le liste di tabelle Pos* che si
# discostano dai default del modello. Tenerle separate dal codice che le
# applica evita di doverle cercare dentro 5000 righe di interfaccia.
import re

# ==================================================================================================================
# 1bis. REGOLE ETICHETTE TESTUALI (cap. 5 Weisung-GB-it.pdf)
# ==================================================================================================================
# Ogni tabella "PosX" del modello ILI e' solo il punto di iscrizione: il testo vive
# sulla tabella "padre" X (referenziata via FK) e diventa disponibile sul layer solo
# dopo il join impostato in setup_relations_and_joins (campo "{tabella_padre}_{campo}").
# Un'unica famiglia "Cadastra" e' installata (non esistono famiglie separate
# "Cadastra Bold"/"Cadastra Italic"): lo stile va applicato con setBold()/setItalic().
# Formato: (sottostringa in t_low, campi candidati, grassetto, corsivo, dimensione pt)
# Grandezze delle scritture in MILLIMETRI di ALTEZZA MAIUSCOLA, riferite alla
# scala 1:1000 (circ154_allegato2 cap.5). Il documento definisce esplicitamente
# la grandezza come "l'altezza totale di una lettera maiuscola (H) misurata
# dalla linea di base sino all'estremita' superiore", cioe' lo scarto Cap-Base
# di INTERLIS: NON e' la dimensione del font (em), che e' un po' piu' grande -
# vedi _font_size_for_cap.
#
# Prima erano valori in PUNTI tipografici scelti a occhio (8-12 pt): le
# proporzioni fra le classi di scrittura non tornavano, e il cap.1.5.2 indica
# proprio nel rispetto delle proporzioni cio' che rende riconoscibile il piano a
# qualunque scala. Nome di localita' 4.5 e numero di edificio 1.8 stanno 2.5:1.
#
# DUE VALORI ERANO SBAGLIATI, e lo si e' visto solo rileggendo le tabelle del
# cap.5 nel testo in vigore (stato 1.2.2014) invece che nella trascrizione:
#  - numero_di_edificio stava a 1.5 invece di 1.8 (cap.5.5). Sono 7 672
#    iscrizioni sul solo comune di Mendrisio, cioe' la scrittura piu' numerosa
#    del piano dopo i numeri dei punti;
#  - nome_oggetto degli Oggetti singoli stava a 2.2 invece di 2.5 (cap.5.6). Il
#    2.2 esiste, ma e' di un'altra tabella: cap.5.9, elemento_condotta. Le due
#    tabelle stanno sulla stessa pagina e in una trascrizione a colonne il
#    valore era migrato da una all'altra.
# Il cap.5.6 prescrive per nome_oggetto la STESSA grandezza del cap.5.5: la
# regola specifica per gli Oggetti singoli resta solo a dire che il caso e'
# stato verificato, non perche' i due valori differiscano.
#
# I valori senza corrispondenza federale (numeri dei punti fissi e dei punti di
# confine, che il piano RF non rappresenta - cap.5.4 e 5.10 - e il punto quotato,
# estensione cantonale) usano 1.8mm, la grandezza delle altre etichette-numero.
TEXT_LABEL_RULES = (
    ("nome_del_luogo",         ("Nome",),        False, False, 4.5),  # normale
    ("nome_di_localita",       ("Nome",),        True,  False, 4.5),  # grassetto
    ("nome_locale",            ("Nome",),        False, True,  4.5),  # corsivo
    # Oggetti singoli: stessa tabella Pos* della Copertura del suolo e stessa
    # grandezza (cap.5.6 = cap.5.5 = 2.5). Deve stare PRIMA della voce generica:
    # _apply_labels_to_layer esce (return) al primo riscontro, quindi vince la
    # prima regola che combacia, non l'ultima.
    ("oggetti_singoli_posnome_oggetto", ("Nome",), False, True, 2.5),  # corsivo
    ("posnome_oggetto",        ("Nome",),        False, True,  2.5),  # corsivo (Copertura del suolo)
    ("posnome_localizzazione", ("Testo",),       False, True,  3.0),  # corsivo
    ("posnome_edificio",       ("Testo",),       False, False, 1.8),  # normale
    ("posnome_localita",       ("Testo",),       True,  False, 4.5),  # grassetto
    ("posnumero_casa",         ("Numero_casa",), False, False, 1.8),  # normale
    ("posnumero_di_edificio",  ("Numero",),      False, True,  1.8),  # corsivo (cap.5.5)
    # Numero_NE e' un numero di edificio della Copertura del suolo come
    # l'altro, e prende la stessa grandezza. Sui dati reali non ha iscrizioni
    # (PosNumero_NE: 0 righe su Mendrisio), quindi il valore non si vede - ma
    # lasciarlo diverso avrebbe solo aspettato dati che lo usano.
    ("posnumero_ne",           ("Numero",),      False, True,  1.8),  # corsivo (cap.5.5)
    ("posnumero_os",           ("Numero",),      False, True,  1.8),  # corsivo
    ("posnumero_oggetto",      ("Numero",),      False, True,  1.8),  # corsivo
    ("posfondo",               ("Numero",),      True,  False, 2.5),  # grassetto (numero_immobile)
    ("posoggetto_condotta",    ("Gestore",),     False, True,  2.2),  # corsivo
    ("possegnale",             ("Numero",),      False, False, 1.8),  # normale (opzionale)
    ("posmovimento",           ("Nome",),        False, True,  4.0),  # corsivo
    ("pospfp",                 ("Numero",),      False, False, 1.8),  # non rappresentato (cap.5.4)
    ("pospfa",                 ("Numero",),      False, False, 1.8),  # non rappresentato (cap.5.4)
    ("pospunto_di_confine",    ("Identificatore",), False, False, 1.8),
    ("pospcgiurisdizionale",   ("Identificatore",), False, False, 1.8),  # non rappr. (cap.5.10)
)

# Rapporto altezza-maiuscola / dimensione-font (em) del tipo di scrittura
# Cadastra: serve perche' la norma quota l'altezza della MAIUSCOLA mentre QGIS
# imposta la dimensione del font. Misurato con QFontMetricsF su un QFont con
# setPixelSize(1000), cioe' em = 1000 px esatti: capHeight = 729.0 px, identico
# per normale/grassetto/corsivo.
# NB: misurarlo con QFont(famiglia, corpo_in_PUNTI) da' un rapporto sbagliato
# (0.97), perche' capHeight() torna PIXEL mentre il corpo e' in punti: i due
# valori differiscono del fattore DPI/72. Verificato a valle sul render.

# Tabelle Pos* di MD01MUTI7MN95.ili i cui default HAli/VAli sono Left/Bottom
# (etichette-numero di punto: PFP/PFA/Segnale/Punto_quotato) invece di
# Center/Half (nomi/oggetti/altri numeri) - e che NON hanno il campo
# Dimensione (assente dal modello per queste tabelle). Verificato leggendo
# ogni "// non_definito= ... //" del modello per la relativa TABLE.
_POS_LEFT_BOTTOM_KEYWORDS = ("pospfp", "pospfa", "possegnale", "punto_quotato",
                             "pospunto_di_confine", "pospcgiurisdizionale")

# Etichette create e configurate, ma con la VISIBILITA' DEL LAYER (non
# dell'etichetta) spenta di default - richiesta esplicita dell'utente per
# Punto di confine (Beni immobili e giurisdizionale): il layer resta nel
# progetto/albero, gia' pronto con testo/font/posizione, ma parte deselezionato
# in modo che l'utente lo accenda solo quando serve davvero mostrare
# l'iscrizione dell'Identificatore.
_LABEL_LAYER_OFF_BY_DEFAULT = ("pospunto_di_confine", "pospcgiurisdizionale")

# Etichette create e configurate, ma con l'ETICHETTA STESSA (non il layer)
# spenta di default - richiesta esplicita dell'utente per i punti fissi
# PFP1/2/3 e PFA1/2: il layer (col proprio simbolo puntuale) resta visibile
# come sempre, solo il numero non si vede finche' non si riattiva
# manualmente l'etichetta da Proprieta' layer.
_LABEL_DISABLED_BY_DEFAULT = ("pospfp", "pospfa")

# Le uniche 3 tabelle Pos* del modello con l'attributo Stile (StileScrittura:
# normale/spaziato/altro) - "altro" e' un placeholder di estensione senza
# oggetti/semantica definita, trattato come "normale".
_POS_STILE_KEYWORDS = ("nome_locale", "nome_di_localita", "nome_del_luogo")

# I nomi di localita' in maiuscolo (cap. 5.7). Il capitolo dice:
#
#   "Raccomandazione: I nomi di localita' corrispondenti a delle borgate sono
#    da indicare preferibilmente con lettere maiuscole."
#
# E' una RACCOMANDAZIONE, non un obbligo, e per questo la spunta e' spenta di
# default: accenderla di serie cambierebbe l'aspetto di tutte le planimetrie
# gia' prodotte per una cosa che la norma non pretende.
#
# IL LIMITE. La norma dice "localita' CORRISPONDENTI A DELLE BORGATE", e il
# modello un posto dove dirlo ce l'ha: Nome_di_localita porta
#
#     Tipo: OPTIONAL TEXT*30; !! assegnato dal cantone
#
# Solo che nella consegna ticinese e' VUOTO - NULL su tutte e dieci le
# localita' del comune di prova. Un campo facoltativo che il Cantone non
# compila non e' un criterio: filtrarci sopra spegnerebbe la regola sempre.
#
# Si applica quindi a tutta la classe Nome_di_localita, che su Mendrisio
# contiene esattamente le dieci borgate - Arzo, Besazio, Capolago, Cragno,
# Genestrerio, Ligornetto, Mendrisio, Meride, Rancate, Tremona - ma altrove
# potrebbe contenere una localita' che borgata non e'. La regola e' giusta
# quasi sempre, non sempre; il giorno in cui il Cantone valorizzasse Tipo
# potrebbe diventare esatta.
#
# Il maiuscolo si fa al DISEGNO, non nel dato: nel GeoPackage i nomi stanno in
# minuscolo (zero su dieci maiuscoli, verificato), e cambiarli sarebbe
# riscrivere una consegna ufficiale per una questione di resa grafica.
KEYWORD_LOCALITA = "nome_di_localita"
_RE_UPPER = re.compile(r'^upper\("(.*)"\)$', re.DOTALL)


def iscrizione_localita(campo, maiuscolo):
    """(testo dell'etichetta, e' un'espressione) per il nome di localita'."""
    if not maiuscolo or not campo:
        return (campo, False)
    return ('upper("%s")' % campo.replace('"', '""'), True)


def campo_di_iscrizione(testo, e_espressione):
    """Il campo di partenza, qualunque sia lo stato attuale dell'etichetta.

    Serve per poter accendere e spegnere il maiuscolo su un layer gia'
    etichettato senza rifare l'importazione: senza questa, riaccendendolo due
    volte si otterrebbe upper("upper(...)")."""
    if not e_espressione:
        return testo
    dentro = _RE_UPPER.match(testo or "")
    return dentro.group(1).replace('""', '"') if dentro else testo

# ==================================================================================================================
# 1ter. PRIORITA' DELLE ETICHETTE IN CASO DI SOVRAPPOSIZIONE
# ==================================================================================================================
# Quando due scritte non ci stanno, qualcuna deve cedere. QGIS ha gia' un
# motore che decide (PAL): gli manca solo di sapere chi conta di piu', perche'
# senza indicazioni tratta tutti i layer alla pari (priorita' 5) e la scelta
# finisce per dipendere dall'ordine di disegno.
#
# La stessa scala e' applicata all'esportazione DXF da
# av2geobau_ti/AntiCollisioneEtichette.java, cosi' l'anteprima nel progetto e
# il disegno consegnato nascondono le stesse etichette invece di litigare.
#
# Perche' quest'ordine. In cima quello che identifica un confine
# giurisdizionale, che nel piano non puo' mancare. Poi i nomi e i numeri di
# fondo, che sono l'orientamento di chi legge. I numeri dei punti fissi e di
# confine stanno sotto perche' il piano RF non li rappresenta affatto (cap.5.4
# e 5.10): se cadono, cade un'informazione che nel piano ufficiale non ci
# sarebbe comunque. Ultimo il punto quotato, estensione cantonale.
#
# Scala QGIS: 0 = cede sempre, 10 = non cede mai.
_LABEL_PRIORITY = {
    "pospcgiurisdizionale": 10,
    "posnome_localita": 9,
    "nome_di_localita": 9,
    "nome_del_luogo": 9,
    "nome_locale": 8,
    "posfondo": 9,
    "posnumero_casa": 8,
    "posnome_edificio": 7,
    "posnome_oggetto": 7,
    "oggetti_singoli_posnome_oggetto": 7,
    "posnome_localizzazione": 7,
    "posnumero_di_edificio": 6,
    "posnumero_ne": 6,
    "posnumero_oggetto": 6,
    "posnumero_os": 6,
    "posoggetto_condotta": 6,
    "posmovimento": 6,
    "possegnale": 5,
    "pospfa": 4,
    "pospfp": 4,
    "pospunto_di_confine": 3,
    "punto_quotato": 2,
}
_LABEL_PRIORITY_DEFAULT = 5
