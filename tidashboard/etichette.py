# TIDashboard - dati della misurazione ufficiale svizzera in QGIS
# Copyright (C) 2026 Gabriele Peverelli
#
# Questo programma e' software libero: lo si puo' ridistribuire e modificare
# secondo i termini della GNU General Public License pubblicata dalla Free
# Software Foundation, versione 2 o (a scelta) una successiva. Il testo si
# trova nel file LICENSE distribuito insieme al programma.

# Regole delle etichette testuali, estratte da tidashboard.py.
#
# Sono dati puri, senza dipendenze: la tabella delle grandezze normative
# (cap.5 delle istruzioni federali) e le liste di tabelle Pos* che si
# discostano dai default del modello. Tenerle separate dal codice che le
# applica evita di doverle cercare dentro 5000 righe di interfaccia.


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
# proporzioni fra le classi di scrittura non tornavano (nome di localita' 4.5mm
# e numero di edificio 1.5mm devono stare 3:1, stavano 1.5:1), e il cap.1.5.2
# indica proprio nel rispetto delle proporzioni cio' che rende riconoscibile il
# piano a qualunque scala.
#
# I valori senza corrispondenza federale (numeri dei punti fissi e dei punti di
# confine, che il piano RF non rappresenta - cap.5.4 e 5.10 - e il punto quotato,
# estensione cantonale) usano 1.8mm, la grandezza delle altre etichette-numero.
TEXT_LABEL_RULES = (
    ("nome_del_luogo",         ("Nome",),        False, False, 4.5),  # normale
    ("nome_di_localita",       ("Nome",),        True,  False, 4.5),  # grassetto
    ("nome_locale",            ("Nome",),        False, True,  4.5),  # corsivo
    # Oggetti singoli: stessa tabella Pos* della Copertura del suolo, ma il
    # cap.5.6 prescrive 2.2 invece dei 2.5 del cap.5.5. Deve stare PRIMA della
    # voce generica: _apply_labels_to_layer esce (return) al primo riscontro,
    # quindi vince la prima regola che combacia, non l'ultima.
    ("oggetti_singoli_posnome_oggetto", ("Nome",), False, True, 2.2),  # corsivo
    ("posnome_oggetto",        ("Nome",),        False, True,  2.5),  # corsivo (Copertura del suolo)
    ("posnome_localizzazione", ("Testo",),       False, True,  3.0),  # corsivo
    ("posnome_edificio",       ("Testo",),       False, False, 1.8),  # normale
    ("posnome_localita",       ("Testo",),       True,  False, 4.5),  # grassetto
    ("posnumero_casa",         ("Numero_casa",), False, False, 1.8),  # normale
    ("posnumero_di_edificio",  ("Numero",),      False, True,  1.5),  # corsivo
    ("posnumero_ne",           ("Numero",),      False, True,  1.5),  # corsivo
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
