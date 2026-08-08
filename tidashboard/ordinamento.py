# TIDashboard - dati della misurazione ufficiale svizzera in QGIS
# Copyright (C) 2026 Gabriele Peverelli
#
# Questo programma e' software libero: lo si puo' ridistribuire e modificare
# secondo i termini della GNU General Public License pubblicata dalla Free
# Software Foundation, versione 2 o (a scelta) una successiva. Il testo si
# trova nel file LICENSE distribuito insieme al programma.

# Ordine di disegno dei layer e raggruppamento dell'albero, estratti da
# tidashboard.py.
#
# L'ordine z non e' una preferenza estetica: riproduce quello con cui il
# software ufficiale (GEOS Pro) definisce i simboli, dal primo piano allo
# sfondo. Senza, QGIS disegna i layer nell'ordine casuale in cui le tabelle
# compaiono nel GeoPackage.


# Ordine di disegno (z-order) del piano: tabella delle PRIORITA' del cap.1.5.4
# dell'istruzione federale "Rappresentazione del «Piano per il registro
# fondiario»", dal primo piano (indice 0) allo sfondo. Senza gestirlo
# esplicitamente, QGIS disegna i layer nell'ordine casuale di dichiarazione
# delle tabelle nel GeoPackage.
#
# VERSIONE DI RIFERIMENTO: del 9 marzo 2007, STATO 1° FEBBRAIO 2014 - cioe'
# quella IN VIGORE, non la "versione marzo 2007" allegata alla circolare
# ticinese 154. La 154 e' stata annullata e sostituita dalla circolare 202 del
# 27 settembre 2012 ("Questa circolare annulla e sostituisce la circolare 154
# del 30 maggio 2007"), e la tabella e' stata poi ancora modificata dalla
# circolare federale MO 2014/01, trasmessa in Ticino con la circolare 210.
# Vedi NORME.md.
#
# Le tre differenze rispetto alla versione 2007, che questa sequenza recepisce:
#   1. la CROCE DELLA RETE passa da ULTIMA a PRIMA della tabella;
#   2. i segni di superficie degli OGGETTI SINGOLI escono dal blocco "Oggetti
#      singoli" (che resta con punti e linee) e vanno in PENULTIMA posizione;
#   3. la RIPARTIZIONE DEI PIANI sale sopra i segni di superficie della
#      copertura del suolo.
#
# Le voci pure testuali ("_txt", posizioni di iscrizione) sono escluse: le
# etichette QGIS si disegnano comunque sempre sopra a tutti i layer,
# indipendentemente dall'ordine z.
GEOS_ZORDER_SEQUENCE = (
    # 1. Margine_di_piano: croce della rete. Nel 2007 era l'ULTIMA riga della
    # tabella; ora e' la prima, cioe' le croci vanno sopra ogni altra cosa.
    "margine_del_piano_crocetta_reticolo",
    # 2. Punti di confini giurisdizionali.
    "confini_comunali_pcgiurisdizionale",
    # 3. Punti fissi, nell'ordine dato: PFP1, PFA1, PFP2, PFA2, PFP3, PFA3.
    "punti_fissctgria1_pfp1", "punti_fissctgria1_pfa1",
    "punti_fissctgria2_pfp2", "punti_fissctgria2_pfa2",
    "punti_fissctgria3_pfp3", "punti_fissctgria3_pfa3",
    # 4. Beni immobili: punto di confine / simbolo di materializzazione.
    "beni_immobili_punto_di_confine",
    # 5-8. Confini, dal nazionale al comunale.
    "confini_nazionali_parte_confine_nazionale",
    "confini_cantonali_parte_confine_cantonale",
    "confini_dstrttali_parteconfinedistrettuale",
    "confini_comunali_confine_comunale",
    # 9. Beni immobili: 1. Linea ausiliaria, 2. Numero dell'immobile,
    # 3. Geometria - la linea ausiliaria va quindi disegnata PRIMA (piu' in
    # primo piano) della geometria, non dopo.
    "beni_immobili_posfondo_linea_ausiliaria",
    "beni_immobili_posfondoprog_linea_ausiliaria",
    "beni_immobili_bene_immobile",
    "beni_immobili_dpssp",
    "beni_immobili_miniera",
    # 10. Zone di franamento (territori di spostamento permanente di terreno,
    # art. 660a CC): riga NUOVA rispetto al 2007. In Ticino la circolare 202 la
    # dichiara OBBLIGATORIA sul piano rilasciato nel Cantone; la visibilita' e'
    # decisa altrove (stili.py), qui conta solo dove va disegnata.
    "zone_di_movimento_movimento",
    # 11-13. Nomenclatura, CAP e localita', Indirizzo degli edifici: sono tutte
    # ISCRIZIONI, quindi etichette - vedi la nota sopra, non hanno voce qui.
    # 14. Oggetti singoli: 1. segni convenzionali dei PUNTI, 2. delle LINEE.
    # I segni di SUPERFICIE non stanno piu' qui: sono scesi in fondo (punto 19).
    "oggetti_singoli_elemento_puntiforme",
    "oggetti_singoli_simboloelemento_lineare",
    "oggetti_singoli_elemento_lineare",
    # Estensione cantonale (circ.202 allegato 2): il limite legale del bosco e'
    # un oggetto lineare degli oggetti singoli, quindi resta in questo blocco.
    # La voce "prog" va PRIMA della piu' corta: _zorder_priority sceglie la
    # prima voce contenuta nel nome della tabella, e "..._limite_del_bosco" e'
    # sottostringa di "..._limite_del_boscoprog" - con l'ordine inverso la
    # seconda non veniva mai raggiunta (voce morta). Qui i due indici sono
    # adiacenti, quindi non cambiava il disegno, ma la trappola resta.
    "limit_lgl_dl_bsco_limite_del_boscoprog",
    "limit_lgl_dl_bsco_limite_del_bosco",
    # 15. Copertura del suolo: oggetti LINEARI. Nel nostro caso sono i contorni
    # del poligono SuperficieCS, che e' un layer solo e non si puo' spezzare in
    # due posizioni z: vedi la nota al punto 20.
    # 16. Condotte: 1. gestore, 2. puntuali, 3. lineari. Nella versione in
    # vigore il blocco NON contiene piu' gli oggetti con superficie; quello che
    # abbiamo lo si tiene qui, adiacente ai lineari, perche' la tabella non gli
    # assegna piu' una posizione propria.
    "condotte_segnale",
    "condotte_elemento_puntiforme",
    "condotte_elemento_lineare",
    "condotte_elemento_con_superficie",
    # 17. Ripartizione dei piani: geometria del confine. Prima stava quasi in
    # fondo; ora sta SOPRA i segni di superficie.
    "ripartizin_d_pani_geometria_piano",
    # 18. Copertura del suolo: segni di superficie tipo "Edificio" (griglia).
    # NON SEPARABILE: gli edifici sono regole dentro lo stesso layer poligonale
    # della copertura del suolo, e un layer QGIS occupa una sola posizione z.
    # Restano quindi con il resto della copertura, al punto 20. E' l'unico
    # punto della tabella che non si riesce a riprodurre per intero.
    # 19. Oggetti singoli: segni delle SUPERFICI - penultima posizione.
    "oggetti_singoli_elemento_con_superficie",
    "oggetti_singoli_simboloel_con_superficie",
    # 20. Copertura del suolo: segni di superficie, altri tipi - ultima.
    "copertura_dl_solo_superficiecs",
    "copertura_dl_solo_simbolosuperficiecs",
    # Fuori tabella: elementi di impaginazione del foglio, sempre sul fondo.
    "margine_del_piano_elemento_lineare",
    "margine_del_piano_superficie_disegno",
)

# Categorizzazione di riserva (5 livelli) per i temi non coperti dalla legenda GEOS
# sopra (es. Aree_di_numerazione, CAP_localita, Zone_di_movimento, Tronco_di_strada):
# usata solo come fallback, dopo aver verificato che nessuna voce di
# GEOS_ZORDER_SEQUENCE corrisponda.
Z_ORDER_TIERS = (
    ("punto_singolo", "punto_fisso_ausiliario", "punto_quotato", "entrata_edificio"),
    ("elemento_puntiforme", "segnale"),
    ("elemento_lineare", "linea_coordinate", "crocetta_reticolo", "simbololayout",
     "tronco_di_strada"),
    ("aree_di_numerzone", "zone_di_movimento"),
    ("nome_locale", "nome_di_localita", "zona_denominata", "cap_localita"),
)

# Generi di Elemento_con_superficie (Oggetti_singoli) da trattare come
# Copertura del suolo per ordine di disegno/legenda, non come gli altri
# generi della stessa tabella - vedi il relativo split di layer in Fase
# 3quater (setup_layers). "serbatoio" condivide lo stesso trattamento
# cromatico di edificio_sotterraneo in _gen_stile_elemento_con_superficie
# (riquadro grigio chiaro pieno/nessun riempimento), stessa logica quindi
# anche per l'ordine di disegno.
EDIFICIO_SOTTERRANEO_GENERI = ("edificio_sotterraneo", "edificio_sotterraneo_indipendente",
                               "parte_sotterranea_di_edificio", "serbatoio")


# Prefisso del join INVERSO che porta l'orientamento del simbolo dalle tabelle
# "Simbolo*" senza geometria sul layer del padre. Fisso e corto apposta: gli
# stili devono poter cercare un nome prevedibile ("simbolo_ori") invece di
# ricostruire il nome della tabella figlia, che cambia da tema a tema.
PREFISSO_SIMBOLO = "simbolo_"
CAMPO_ORI_SIMBOLO = PREFISSO_SIMBOLO + "ori"


def _raw_table_name(layer):
    """Nome RAW della tabella GeoPackage sorgente di un layer OGR (es.
    "oggetti_singoli_elemento_con_superficie"), indipendente da come il
    layer e' stato rinominato nel pannello (vedi _nice_layer_name). Letto
    dalla source URI ("...gpkg|layername=xxx"), non da layer.name() - vedi
    la nota in setup_relations_and_joins sul bug reale che questo ha
    risolto (join falliti per ~123 layer su 128)."""
    src = layer.source()
    marker = "layername="
    idx = src.find(marker)
    if idx >= 0:
        return src[idx + len(marker):].split("|")[0]
    return layer.name()

def _zorder_priority(t_low):
    """Indice di priorita' nell'ordine di disegno (0 = primo piano/sopra a tutto).
    Priorita' assoluta alle tabelle elencate esplicitamente in GEOS_ZORDER_SEQUENCE
    (ordine autorevole del software ufficiale); le tabelle non presenti ricadono
    sulla categorizzazione di riserva Z_ORDER_TIERS, agganciata subito dopo
    l'ultima voce nota per non alterare l'ordine gia' verificato."""
    for i, name in enumerate(GEOS_ZORDER_SEQUENCE):
        if name in t_low:
            return i
    fallback_base = len(GEOS_ZORDER_SEQUENCE)
    for i, keywords in enumerate(Z_ORDER_TIERS):
        if any(k in t_low for k in keywords):
            return fallback_base + i
    return fallback_base + len(Z_ORDER_TIERS)

def _zorder_debug_info(t_low):
    """Come _zorder_priority, ma restituisce anche IL MOTIVO della
    classificazione (quale pattern ha fatto match e in quale elenco) - solo
    per il log dettagliato di Fase 4, cosi' un caso come "perche' il tema X
    finisce sopra/sotto il tema Y" si legge direttamente dal log invece di
    dover essere investigato ogni volta da zero."""
    for i, name in enumerate(GEOS_ZORDER_SEQUENCE):
        if name in t_low:
            return i, f'GEOS_ZORDER_SEQUENCE[{i}]="{name}"'
    fallback_base = len(GEOS_ZORDER_SEQUENCE)
    for i, keywords in enumerate(Z_ORDER_TIERS):
        matched = [k for k in keywords if k in t_low]
        if matched:
            return fallback_base + i, f'Z_ORDER_TIERS[{i}] (fallback) match={matched}'
    return fallback_base + len(Z_ORDER_TIERS), "nessun match (ultimo livello, fondo assoluto)"

# Raggruppamento del pannello Layers di QGIS negli stessi 12 livelli
# gerarchici di GEOS_ZORDER_SEQUENCE (circ154 cap. 1.5.4), cosi' l'albero
# rispecchia visivamente l'ordine di disegno invece di restare un elenco
# piatto di ~50-100 tabelle con nomi tecnici. Riusa le stesse sottostringhe
# GIA' VERIFICATE di GEOS_ZORDER_SEQUENCE/Z_ORDER_TIERS (non un elenco nuovo
# da riverificare), solo raggruppate sotto titoli leggibili invece che in
# un'unica sequenza piatta - stessa idea del progetto "Pro" (RF_LAYER_GROUPS),
# portata qui senza toccare _zorder_priority/GEOS_ZORDER_SEQUENCE (l'ordine
# di disegno resta calcolato esattamente come prima, il raggruppamento e'
# solo visuale). Le tabelle non coperte da nessun pattern qui finiscono nel
# gruppo di riserva "90 Altri layer geometrici" (vedi _reorganize_layer_tree),
# non silenziosamente perse.
RF_LAYER_GROUPS = (
    # Pattern deliberatamente SPECIFICI (es. "pcgiurisdizionale" invece di
    # "confini_comunali") per i temi al vertice della gerarchia (01/03), cosi'
    # da vincere sul pattern piu' GENERICO di un tema successivo che
    # condivide lo stesso prefisso tabella (es. "confini_comunali_
    # confine_comunale" -> gruppo 04, non 01): l'ordine dei gruppi qui sotto
    # e' quindi significativo, il primo pattern che corrisponde vince (vedi
    # _rf_group_for_table). Dove non c'e' ambiguita' si usa invece il
    # prefisso di TOPIC intero (es. "oggetti_singoli"), cosi' da catturare
    # in un colpo solo anche le tabelle Pos*/Tenuta_a_giorno* gemelle dello
    # stesso tema (es. "oggetti_singoli_posnumero_os",
    # "oggetti_singoli_tenuta_a_giornoos") senza doverle elencare una per una.
    # Nomi ESATTI richiesti dall'utente (2 turni di correzione: prima lo
    # schema "<Topic> (<Ruolo>)", poi l'ordine Topic/Ruolo invertito rispetto
    # al tentativo precedente) - "Confine giurisdizionale" e "Beni immobili"
    # condividono lo stesso schema a 2 gruppi (Punti di confine / Linee).
    ("01 Confine giurisdizionale (Punti di confine)", (
        "pcgiurisdizionale",
    )),
    ("02 Punti fissi (PFP/PFA)", (
        "punti_fissctgria1", "punti_fissctgria2", "punti_fissctgria3",
        "pto_fisso_ausil", "fisso_ausil", "pf_aus",
    )),
    ("03 Beni immobili (Punti di confine)", (
        "punto_di_confine",
    )),
    ("04 Confine giurisdizionale (Linee)", (
        "confine_nazionale", "confine_cantonale", "confinedistrettuale",
        "confine_comunale", "confini_comunali",
    )),
    # Bene_immobile/DPSSP/Miniera sono geometricamente poligoni, ma
    # concettualmente sono il CONTORNO/confine del bene immobile (esattamente
    # come Confine_comunale, anch'esso un poligono ma raggruppato sopra in
    # "04 ... (Linee)", non per il tipo di geometria ma per il ruolo
    # semantico) - stesso schema a 2 gruppi di "Confine giurisdizionale".
    ("05 Beni immobili (Linee)", (
        "beni_immobili",
    )),
    ("06 Nomenclatura", (
        "nome_del_luogo", "nome_di_localita", "nome_locale", "nomenclatura",
    )),
    ("07 CAP e localita", (
        "cap_localita", "insieme_di_localita",
    )),
    ("08 Indirizzi degli edifici", (
        "indirzz_dgl_dfici", "posnumero_casa", "posnome_edificio",
        "posnome_localizzazione", "entrata_edificio", "tronco_di_strada",
        "zona_denominata",
    )),
    ("09 Oggetti singoli", (
        "oggetti_singoli",
    )),
    ("10 Copertura del suolo", (
        "copertura_dl_solo", "limit_lgl_dl_bsco",
    )),
    ("11 Condotte", (
        "condotte",
    )),
    ("12 Margine del piano e ripartizione", (
        "margine_del_piano", "margine_dl_pano",
        "ripartizin_d_pani", "ripartizionegt",
    )),
)

def _rf_group_for_table(t_low):
    """Titolo del gruppo RF_LAYER_GROUPS per un nome tabella, o None se
    nessun pattern corrisponde (va nel gruppo di riserva)."""
    for title, pats in RF_LAYER_GROUPS:
        if any(p in t_low for p in pats):
            return title
    return None

def _rf_group_debug_info(t_low):
    """Come _rf_group_for_table, ma restituisce anche il pattern che ha
    fatto match (o il motivo del fallback) - per il log dettagliato di
    Fase 4bis."""
    for title, pats in RF_LAYER_GROUPS:
        matched = [p for p in pats if p in t_low]
        if matched:
            return title, f"match={matched}"
    return "90 Altri layer geometrici", "nessun pattern RF_LAYER_GROUPS corrispondente"

# §1.5.4 nota: da 1:5000 in poi i punti di confine (non le altre geometrie)
# possono essere tralasciati nella rappresentazione - restano quindi visibili
# solo a scale piu' dettagliate (denominatore <= questo valore).
CONFINE_POINTS_MIN_SCALE = 5000
