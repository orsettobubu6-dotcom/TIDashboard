# TIDashboard - dati della misurazione ufficiale svizzera in QGIS
# Copyright (C) 2026 Gabriele Peverelli
#
# Questo programma e' software libero: lo si puo' ridistribuire e modificare
# secondo i termini della GNU General Public License pubblicata dalla Free
# Software Foundation, versione 2 o (a scelta) una successiva. Il testo si
# trova nel file LICENSE distribuito insieme al programma.

# Generatori di stile: quale simbologia spetta a ciascuna tabella del modello
# MD01MUTI7MN95. Estratti da tidashboard.py.
#
# Qui sta il "cosa si disegna"; il "come" (font, SVG, costruttori di simboli)
# e' in simbologia.py e i colori normativi in colori.py.
#
# Sono raccolti in un MIXIN e non in funzioni libere: erano gia' metodi che
# usano self.log() per raccontare cosa riconoscono, e trasformarli in funzioni
# avrebbe voluto dire toccarne il corpo uno per uno - 1000 righe di modifiche
# per un trasloco. Cosi' il codice si sposta invariato e
# TIDashboardDialog._gen_stile_* resta raggiungibile dove lo cercano i test.
from qgis.PyQt.QtGui import QColor
from qgis.core import (QgsExpression, QgsLineSymbol, QgsMarkerSymbol,
                       QgsProperty, QgsRuleBasedRenderer)

try:
    from .colori import *          # noqa: F401,F403 - costanti C_*
    from .simbologia import (_FONT_INK_FRACTION, apply_rule, build_sym, fill_dash,
                             gbc, genere_in, make_fill, make_font_marker_line,
                             make_font_point_pattern, make_hatch, make_line,
                             make_point_pattern, make_simple_marker,
                             make_true_font_marker_with_mask)
except ImportError:
    from colori import *           # noqa: F401,F403
    from simbologia import (_FONT_INK_FRACTION, apply_rule, build_sym, fill_dash,
                            gbc, genere_in, make_fill, make_font_marker_line,
                            make_font_point_pattern, make_hatch, make_line,
                            make_point_pattern, make_simple_marker,
                            make_true_font_marker_with_mask)


# Denominatore da cui il PB-MU cambia il colore dell'edificio
# (Weisung-BP-AV §2.3.2: "1:2'500 e 1:5'000" da una parte, "1:10'000" dall'altra).
SCALA_EDIFICIO_ROSA_ACCESO = 10000

# Spessori propri del PB-MU, riferiti all'1:5000 (Weisung-BP-AV cap.2.2).
# Il piano RF li ha diversi (circ154_allegato2 cap.3) e restano quelli in
# modalita' "gb".
#  §2.2.4 copertura del suolo: 0.20 mm, tranne strada_sentiero 0.25
#  §2.2.10 altimetria: 0.15 mm, curve principali 0.25
#  §2.2.11 reticolo delle coordinate: 0.12 mm (applicato in planimetria.py)
LARGHEZZA_BP_STRADA_SENTIERO = 0.25
LARGHEZZA_BP_ALTIMETRIA = 0.15

# Grandezza dei tasti roccia (1) e pietraia/sabbia (2), circ154_allegato2 cap.4.
# Vale anche come PASSO della trama: la norma da' "Distanza: 0", cioe' nessuna
# spaziatura aggiunta fra un glifo e il successivo.
DIM_ROCCIA = 2.0


class StiliMixin:
    """Metodi di generazione degli stili, innestati in TIDashboardDialog."""

    def _get_renderer_for_table(self, class_name, t_low, mode, geom_type_name="", layer=None):
        """Determina il renderer appropriato per la tabella."""
        is_gb = (mode == "gb")

        # Tabelle di attualizzazione (Tenuta_a_giorno*) e oggetti "in progetto"
        # (suffisso *Prog): non fanno parte del contenuto del piano (cap. 1.5.3
        # istruzioni federali). Vanno escluse esplicitamente PRIMA di ogni altro
        # controllo, sia per evitare falsi positivi per sottostringa (es.
        # "Tenuta_a_giornoPFP1" contiene "pfp"), sia per non lasciarle con il
        # colore casuale di default di QGIS: gli assegnamo un simbolo invisibile
        # del tipo di geometria corretto.
        if "tenuta_a_giorno" in t_low or "prog" in t_low:
            reason = "tabella di attualizzazione" if "tenuta_a_giorno" in t_low else "oggetto 'in progetto'"
            self.log(f"   ⏭️ {reason}, non rappresentato sul piano -> simbolo invisibile")
            return self._gen_stile_invisibile(geom_type_name)

        # Linea_ausiliaria: attributo geometrico OPZIONALE di PosFondo(Prog)/
        # PosNome_Edificio/PosNome_localizzazione ("tratto di collegamento" tra
        # l'etichetta e l'oggetto a cui si riferisce, MD01MUTI7MN95.ili) - ili2db
        # lo esporta come tabella propria (es. "beni_immobili_posfondo_linea_
        # ausiliaria", geometria COMPOUNDCURVE). Va riconosciuta PRIMA del
        # controllo "PosX" qui sotto: il nome contiene "_pos..." per via della
        # tabella padre, ma NON e' un punto di iscrizione etichetta, e' una linea
        # vera che va disegnata (altrimenti riceveva erroneamente un simbolo
        # invisibile di tipo PUNTO su un layer di tipo LINEA, che QGIS non applica
        # correttamente e lascia lo stile casuale di default -> "linea in piu' non
        # voluta" accanto ai numeri di fondo).
        if "linea_ausiliaria" in t_low:
            self.log("   🎯 Riconosciuto: Linea_ausiliaria -> Stile linea di richiamo etichetta")
            return self._gen_stile_linea_ausiliaria(is_gb)

        # Tabelle "PosX": in tutto il modello ILI sono SEMPRE e SOLO il punto di
        # iscrizione di un'etichetta (campi Pos/Ori/HAli/VAli/Dimensione), mai un
        # oggetto reale. Il vero simbolo vive sulla tabella "X" associata (che ha
        # una propria Geometria). Vanno intercettate PRIMA di ogni altro
        # controllo, perche' altrimenti "PosPFP1", "PosPunto_di_confine", ecc.
        # matcherebbero per sottostringa lo stesso controllo della tabella dati
        # "PFP1"/"Punto_di_confine", ereditandone regole che filtrano su campi
        # (Segno, Accessibilita...) che su "PosX" non esistono.
        if t_low.startswith("pos") or "_pos" in t_low:
            self.log("   🏷️ Punto di iscrizione etichetta -> simbolo invisibile (gestito dalle etichette)")
            return self._gen_stile_invisibile(geom_type_name)

        # Tabelle "SimboloX": simboli ausiliari opzionali (direzione della corrente,
        # freccia nord, ecc.) che dipendono dal Genere della tabella "X" associata
        # (non disponibile qui senza un join). Per non lasciarle con il colore
        # casuale di default, usiamo un punto invisibile finche' non e' implementata
        # la logica specifica per ciascun tipo. SimboloSuperficieCS fa eccezione:
        # implementata (vedi _gen_stile_simbolo_superficie_cs), esclusa qui per
        # evitare che sia intercettata da questo fallback generico.
        if (t_low.startswith("simbolo") or "_simbolo" in t_low) and "simbolosuperficiecs" not in t_low:
            self.log("   🏷️ Simbolo ausiliario -> simbolo invisibile (non ancora differenziato per Genere)")
            return self._gen_stile_invisibile(geom_type_name)

        # SimboloSuperficieCS: DEVE precedere il controllo generico "superficiecs"
        # subito sotto (_gen_stile_superficiecs, per il poligono SuperficieCS) -
        # "superficiecs" e' una sottostringa di "simbolosuperficiecs", quindi
        # verrebbe intercettata per prima se il controllo fosse dopo.
        if "SimboloSuperficieCS" in class_name or "simbolosuperficiecs" in t_low:
            self.log("   🎯 Riconosciuto: SimboloSuperficieCS -> Stile simbolo su superficie")
            return self._gen_stile_simbolo_superficie_cs(is_gb)

        # === SUPERFICI ===
        if "SuperficieCS" in class_name or "superficiecs" in t_low:
            self.log("   🎯 Riconosciuto: SuperficieCS -> Stile copertura suolo")
            return self._gen_stile_superficiecs(is_gb)
        if "Elemento_con_superficie" in class_name or "elemento_con_superficie" in t_low:
            self.log("   🎯 Riconosciuto: Elemento_con_superficie -> Stile oggetti con superficie")
            return self._gen_stile_elemento_con_superficie(is_gb)

        # === LINEE ===
        if "Elemento_lineare" in class_name or "elemento_lineare" in t_low:
            self.log("   🎯 Riconosciuto: Elemento_lineare -> Stile oggetti lineari")
            return self._gen_stile_elemento_lineare(is_gb)
        if "Bene_immobile" in class_name or "bene_immobile" in t_low:
            self.log("   🎯 Riconosciuto: Bene_immobile -> Stile confini proprietà")
            return self._gen_stile_bene_immobile(is_gb)
        # DPSSP e Miniera condividono il campo "genere_di_linea" con Bene_immobile,
        # ma lo stato "in vigore" e' interrotto (non continuo): stile dedicato.
        if any(k in class_name for k in ["DPSSP", "Miniera"]) or any(k in t_low for k in ["dpssp", "miniera"]):
            self.log("   🎯 Riconosciuto: DPSSP/Miniera -> Stile confini proprietà")
            return self._gen_stile_dpssp_miniera(is_gb)
        if "Confine_comunale" in class_name or "confine_comunale" in t_low:
            self.log("   🎯 Riconosciuto: Confine_comunale -> Stile confine comunale")
            return self._gen_stile_confine_comunale(is_gb)
        if "Confine_cantonale" in class_name or "confine_cantonale" in t_low:
            self.log("   🎯 Riconosciuto: Confine_cantonale -> Stile confine cantonale")
            return self._gen_stile_confine_cantonale(is_gb)
        if "Confine_nazionale" in class_name or "confine_nazionale" in t_low:
            self.log("   🎯 Riconosciuto: Confine_nazionale -> Stile confine nazionale")
            return self._gen_stile_confine_nazionale(is_gb)
        # Nome classe ILI reale "ParteConfineDistrettuale" (senza underscore tra
        # "Confine" e "Distrettuale", diversamente da Confine_comunale/cantonale/nazionale)
        if "Distrettuale" in class_name or "distrettuale" in t_low:
            self.log("   🎯 Riconosciuto: Confine_distrettuale -> Stile confine distrettuale")
            return self._gen_stile_confine_distrettuale(is_gb)
        if "Limite_del_bosco" in class_name or "limite_legale_del_bosco" in t_low:
            self.log("   🎯 Riconosciuto: Limite_del_bosco -> Stile limite bosco")
            return self._gen_stile_limiti_bosco(is_gb)
        if "Tronco_di_strada" in class_name or "tronco_di_strada" in t_low:
            self.log("   🎯 Riconosciuto: Tronco_di_strada -> Stile asse stradale")
            return self._gen_stile_tronco_strada(is_gb)
        # Nota: il controllo precedente confrontava "Altimetria" con class_name (che
        # contiene solo il nome della classe, es. "Linea", mai il nome del topic),
        # quindi non poteva mai scattare. Il tema Altimetria non fa comunque parte
        # del piano per il registro fondiario (cap. 1.5.3 istruzioni federali).
        if class_name == "Linea" or t_low.endswith("_linea") or t_low == "linea":
            self.log("   ⏭️ Altimetria (Linea): tema non rappresentato sul piano -> invisibile")
            return self._gen_stile_invisibile(geom_type_name)
        if "Superficie_vuota" in class_name or "superficie_vuota" in t_low:
            self.log("   ⏭️ Altimetria (Superficie_vuota): tema non rappresentato sul piano -> invisibile")
            return self._gen_stile_invisibile(geom_type_name)

        # === PUNTI ===
        if "Elemento_puntiforme" in class_name or "elemento_puntiforme" in t_low:
            self.log("   🎯 Riconosciuto: Elemento_puntiforme -> Stile oggetti puntiformi")
            return self._gen_stile_elemento_puntiforme(is_gb)
        # Punto_singolo (punto non altrimenti classificato, in piu' topic) e
        # Punto_fisso_ausiliario (punti fissi ausiliari senza tenuta a giorno):
        # nessun simbolo specifico documentato -> punto generico nero.
        if "Punto_singolo" in class_name or "Punto_fisso_ausiliario" in class_name \
           or "punto_singolo" in t_low or "punto_fisso_ausiliario" in t_low:
            self.log("   🎯 Riconosciuto: Punto_singolo/Punto_fisso_ausiliario -> Punto generico")
            return self._gen_stile_punto_generico()
        # PCGiurisdizionale ha lo stesso campo "Segno: Materiale" di Punto_di_confine.
        if "Punto_di_confine" in class_name or "PCGiurisdizionale" in class_name \
           or "punto_di_confine" in t_low or "pcgiurisdizionale" in t_low:
            self.log("   🎯 Riconosciuto: Punto_di_confine/PCGiurisdizionale -> Stile punti di confine")
            return self._gen_stile_punto_di_confine(is_gb, layer)
        if "PFP" in class_name or "pfp" in t_low:
            self.log("   🎯 Riconosciuto: PFP -> Stile punti fissi planimetrici")
            return self._gen_stile_pfp(is_gb, t_low)
        if "PFA" in class_name or "pfa" in t_low:
            self.log("   🎯 Riconosciuto: PFA -> Stile punti fissi altimetrici")
            return self._gen_stile_pfa(is_gb, t_low)
        if "Punto_quotato" in class_name or "punto_quotato" in t_low:
            self.log("   🎯 Riconosciuto: Punto_quotato -> Stile punto quotato")
            return self._gen_stile_altimetria_punti(is_gb)
        if "Segnale" in class_name or "segnale" in t_low:
            self.log("   🎯 Riconosciuto: Segnale -> Stile segnale condotta")
            return self._gen_stile_segnale_condotta(is_gb)

        # === POLIGONI AMMINISTRATIVI ===
        # Perimetro_numerazione: circ154_allegato2 cap.1.5.3 lo elenca fra i temi
        # NON rappresentati sul piano per il registro fondiario, e non compare
        # nemmeno fra i temi del piano di base (Weisung-BP-AV, che al cap.2.2 va
        # da Copertura del suolo a Reticolo delle coordinate senza citarlo).
        # Non appartiene quindi a nessuno dei due prodotti: e' una suddivisione
        # amministrativa, come RipartizioneGT qui sotto.
        if "Aree_di_numerazione" in class_name or "area_di_numerazione" in t_low or "geometriaan" in t_low:
            self.log("   ⏭️ Aree di numerazione: suddivisione amministrativa, non "
                     "rappresentata sul piano (cap.1.5.3) -> invisibile")
            return self._gen_stile_invisibile(geom_type_name)
        # Il topic "Ripartizione_dei_piani" viene abbreviato in modo aggressivo da
        # ili2db (es. "ripartizin_d_pani"), quindi il nome tabella non contiene piu'
        # "ripartizione" per intero: serve anche il controllo diretto sul nome classe
        # ILI (non abbreviato) "Geometria_Piano".
        # RipartizioneGT/Grado_di_tolleranza e' un concetto amministrativo interno
        # (classificazione GT1-GT5 della precisione di rilievo), diverso da
        # Ripartizione_dei_piani/Geometria_Piano (i fogli di mappa veri e propri):
        # va intercettato PRIMA e separatamente, altrimenti "Ripartizione" in
        # class_name (che matcherebbe anche "RipartizioneGT") gli farebbe
        # ereditare per errore lo stile e l'etichetta "Foglio di mappa".
        if "RipartizioneGT" in class_name or "Grado_di_tolleranza" in class_name \
           or "ripartizionegt" in t_low or "grado_di_tolleranza" in t_low:
            self.log("   ⏭️ RipartizioneGT: classificazione amministrativa, non rappresentata sul piano -> invisibile")
            return self._gen_stile_invisibile(geom_type_name)
        # Ripartizione_dei_piani (i fogli di mappa): stessa sorte delle aree di
        # numerazione - escluso dal piano RF dal cap.1.5.3 e assente dai temi
        # del piano di base. Prima veniva disegnato con una banda grigia da
        # 10 mm, che sul foglio copriva tutto cio' che le stava sotto.
        if "Ripartizione" in class_name or "Geometria_Piano" in class_name \
           or "ripartizione" in t_low or "ripartizin" in t_low:
            self.log("   ⏭️ Ripartizione dei piani: suddivisione amministrativa, "
                     "non rappresentata sul piano (cap.1.5.3) -> invisibile")
            return self._gen_stile_invisibile(geom_type_name)
        if "Zone_di_movimento" in class_name or "movimento" in t_low:
            self.log("   🎯 Riconosciuto: Zone_di_movimento -> Stile zona movimento")
            return self._gen_stile_zone_movimento(is_gb)
        if "CAP" in class_name or "cap_localita" in t_low:
            self.log("   🎯 Riconosciuto: CAP_localita -> Stile CAP/località")
            return self._gen_stile_cap_localita(is_gb)
        if "Margine" in class_name or "margine_del_piano" in t_low:
            self.log("   🎯 Riconosciuto: Margine_del_piano -> Stile margine piano")
            return self._gen_stile_margine_piano(is_gb, geom_type_name)

        # === NOMENCLATURA E INDIRIZZI ===
        # (le tabelle "PosX", incluse PosNome_locale/PosNome_di_localita/PosNome_del_luogo
        # e PosNumero_casa/PosNome_localizzazione/PosNome_edificio, sono gia' intercettate
        # sopra dal controllo generico "PosX" -> simbolo invisibile).
        # Nome_locale/Nome_di_localita sono superfici (AREA) che servono solo da supporto
        # geometrico: il contenuto visibile e' gestito dall'etichetta sul punto associato.
        if "Nome_locale" in class_name or "Nome_di_localita" in class_name \
           or "nome_locale" in t_low or "nome_di_localita" in t_low:
            self.log("   🎯 Riconosciuto: Nomenclatura (area) -> superficie invisibile")
            return self._gen_stile_invisibile("POLYGON")
        if "Entrata_edificio" in class_name or "entrata_edificio" in t_low:
            self.log("   🎯 Riconosciuto: Entrata_edificio -> Stile testo (etichette)")
            return self._gen_stile_indirizzi_edifici(is_gb)
        # Zona_denominata: superficie di supporto per un nome di zona (analoga a
        # Nome_locale/Nome_di_localita di Nomenclatura), il contenuto visibile e'
        # gestito dall'etichetta sul punto PosNome_localizzazione associato.
        if "Zona_denominata" in class_name or "zona_denominata" in t_low:
            self.log("   🎯 Riconosciuto: Zona_denominata -> superficie invisibile")
            return self._gen_stile_invisibile("POLYGON")
        # Origine_piano_sinottico: punto tecnico ausiliario (geometria secondaria di
        # Layout_del_piano) usato solo per posizionare l'inserto del piano sinottico,
        # non fa parte del contenuto rappresentato sul piano (cap. 1.5.3 istruzioni federali).
        if "Origine_piano_sinottico" in class_name or "origine_piano_sinottico" in t_low:
            self.log("   ⏭️ Origine_piano_sinottico: punto tecnico ausiliario -> invisibile")
            return self._gen_stile_invisibile("POINT")

        self.log(f"   ❌ Nessun riconoscimento per: {class_name} / {t_low}")
        return None

    # --- RENDERER SPECIFICI ---
    # Nota: il Piano per il registro fondiario (GB) e' rappresentato esclusivamente
    # in bianco e nero (istruzioni federali marzo 2007, cap. 1.5.6); i colori esatti
    # (CMYK, da Weisung-BP-AV-it.pdf) valgono per il Piano di base (PB-MU).
    def _gen_stile_invisibile(self, geom_type_name):
        """Simbolo completamente invisibile, per geometrie che non vanno mostrate
        (tabelle di attualizzazione, oggetti in progetto, punti di iscrizione
        etichetta, superfici di solo supporto geometrico)."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Invisibile")
        gtype = (geom_type_name or "").upper()
        if "POINT" in gtype:
            sym = build_sym('point', [make_simple_marker("circle", 0.01, QColor(0, 0, 0, 0))])
        elif "LINE" in gtype or "CURVE" in gtype:
            sym = build_sym('line', [make_line(QColor(0, 0, 0, 0), 0.01)])
        else:
            sym = build_sym('fill', [make_fill(None, QColor(0, 0, 0, 0), 0.0, "no")])
        apply_rule(root, sym, "", "Invisibile")
        return QgsRuleBasedRenderer(root)

    def _gen_stile_linea_ausiliaria(self, is_gb):
        """Linea di richiamo (Linea_ausiliaria) che collega un'etichetta
        (numero di fondo, nome edificio, nome localizzazione) al relativo
        oggetto quando non puo' essere scritta direttamente su di esso.
        Non e' un confine ne' un oggetto del piano: linea sottile grigia,
        visivamente distinta dalle linee di confine (nere, piu' spesse) per
        non essere scambiata per un limite reale. Nessuna larghezza/colore
        ufficiale documentata per questo tratto (assente da av2geobau)."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Linea_ausiliaria")
        c = C_NERO if is_gb else C_TRAMA_50
        sym = build_sym('line', [make_line(c, 0.10)])
        apply_rule(root, sym, "", "Linea di richiamo etichetta")
        return QgsRuleBasedRenderer(root)

    def _gen_stile_punto_generico(self):
        """Punto generico nero, per tabelle puntuali senza un simbolo ufficiale
        documentato (es. Punto_singolo, Punto_fisso_ausiliario)."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Punto_generico")
        sym = build_sym('point', [make_simple_marker("circle", 0.6, C_NERO)])
        apply_rule(root, sym, "", "Punto generico")
        return QgsRuleBasedRenderer(root)

    def _gen_stile_superficiecs(self, is_gb):
        """Stile per SuperficieCS. Tutti i filtri usano genere_in() (non il
        confronto diretto "Genere" = 'x') perche' Genere_CS e' gerarchico -
        vedi genere_in()."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("SuperficieCS")

        # Edificio: colore RGB(255,191,191) in PB-MU (bordo marrone), trama grigia 30% in GB (bordo nero)
        edificio_c = C_TRAMA_30 if is_gb else C_EDIFICIO
        edificio_out = C_NERO if is_gb else C_BP_EDIFICIO_CONTORNO
        if is_gb:
            apply_rule(root, build_sym('fill', [make_fill(edificio_c, edificio_out, 0.20)]),
                       genere_in(['edificio']), "Edificio")
        else:
            # Nel PB-MU l'edificio cambia colore a 1:10000 (Weisung-BP-AV
            # §2.3.2): rosa acceso, riempimento e contorno dello stesso colore.
            # Due regole con intervallo di scala, invece di una sola: il colore
            # dipende dalla scala di rappresentazione, non dal dato.
            r_fine = apply_rule(root, build_sym('fill', [make_fill(edificio_c, edificio_out, 0.20)]),
                                genere_in(['edificio']), "Edificio")
            # ATTENZIONE ai nomi QGIS, che sono controintuitivi e verificati a
            # mano: setMinimumScale e' il limite SUPERIORE del denominatore ed
            # e' ESCLUSIVO, setMaximumScale e' quello inferiore ed e' inclusivo.
            # Quindi "fino a 1:10000 escluso" = setMinimumScale(10000).
            r_fine.setMinimumScale(SCALA_EDIFICIO_ROSA_ACCESO)
            r_largo = apply_rule(root, build_sym(
                'fill', [make_fill(C_BP_EDIFICIO_10000, C_BP_EDIFICIO_10000, 0.20)]),
                genere_in(['edificio']), "Edificio (1:10000)")
            r_largo.setMaximumScale(SCALA_EDIFICIO_ROSA_ACCESO)

        # Acque: colore RGB(179,230,255) con bordo blu scuro in PB-MU; in GB solo bordo nero, senza riempimento
        # (include le sottocategorie foglia di corso_acqua/bacino_idrico previste da Genere_CS)
        acqua_fill = None if is_gb else C_ACQUA
        acqua_out = C_NERO if is_gb else C_BP_ACQUA_BORDO
        apply_rule(root, build_sym('fill', [make_fill(acqua_fill, acqua_out, 0.20)]),
                   genere_in(['specchio_acqua', 'corso_acqua', 'fiume', 'torrente', 'canale',
                              'bacino_idrico', 'piscina', 'altro_bacino_idrico']), "Acque")

        # Strada-sentiero: senza riempimento (solo bordo), su richiesta utente -
        # rimosso il grigio CMYK(0,0,0,25) precedentemente usato.
        # Sotto-genere "sentiero": bordo interrotto1 (1.5/0.5mm) invece di
        # continuo, unico caso del gruppo con una linetype diversa da
        # continua per valore esatto di circ154_allegato4.pdf ("Genere di
        # linea per gli oggetti supplementari del modello cantonale",
        # LIVELLO Copertura del suolo: "strada (sentiero) = interrotto1",
        # tutti gli altri sotto-generi = continua).
        # Spessore: 0.20 mm nel piano RF (circ154_allegato2 cap.3), 0.25 nel
        # PB-MU, dove il Weisung §2.2.4 fa di "strada_sentiero" l'unica
        # eccezione allo 0.20 della copertura del suolo.
        w_strada = 0.20 if is_gb else LARGHEZZA_BP_STRADA_SENTIERO
        apply_rule(root, build_sym('fill', fill_dash(None, C_NERO, w_strada, "1.5;0.5")),
                   genere_in(['sentiero']), "Strada-sentiero (sentiero)")
        apply_rule(root, build_sym('fill', [make_fill(None, C_NERO, w_strada)]),
                   genere_in(['strada_sentiero', 'nazionale', 'cantonale', 'comunale',
                              'altra_strada']), "Strada-sentiero")

        # Marciapiede / Aeroporto: senza riempimento (solo bordo), su richiesta utente -
        # rimosso il grigio CMYK(0,0,0,12) precedentemente usato
        apply_rule(root, build_sym('fill', [make_fill(None, C_NERO, 0.20)]),
                   genere_in(['marciapiede', 'aeroporto']), "Marciapiede / Aeroporto")

        # Ferrovia: bianco con bordo nero tratteggiato. circ154_allegato2
        # cap.3.4 la elenca fra i generi "interrotto1" (non continuo).
        apply_rule(root, build_sym('fill', fill_dash(C_BIANCO, C_NERO, 0.20, "1.5;0.5")),
                   genere_in(['ferrovia']), "Ferrovia")

        # Bosco fitto: colore RGB(156,255,152) in PB-MU, trama punteggiata nera in GB
        if is_gb:
            sym = build_sym('fill', fill_dash(None, C_NERO, 0.20, "1.5;0.5",
                                              [make_point_pattern(C_NERO, d=2.0, size=0.3)]))
        else:
            sym = build_sym('fill', fill_dash(C_BOSCO, C_NERO, 0.20, "1.5;0.5"))
        apply_rule(root, sym, genere_in(['bosco_fitto']), "Bosco fitto")

        # Altro bosco: trama punteggiata nera, stesso principio di bosco_fitto/
        # pascolo (distanza 4mm, punto 0.3mm) - circ154_allegato2 cap.4: le trame
        # punteggiate di bosco/pascolo sono l'unica eccezione esplicita del
        # documento alla regola del grigio 50%, restando nere in entrambe le varianti
        if is_gb:
            sym = build_sym('fill', fill_dash(None, C_NERO, 0.20, "1.5;0.5",
                                              [make_point_pattern(C_NERO, d=4.0, size=0.3)]))
        else:
            sym = build_sym('fill', [make_fill(C_BOSCO, C_NERO, 0.0, "no")])
            sym.setOpacity(0.5)
        apply_rule(root, sym, genere_in(['altro_bosco']), "Altro bosco")

        # Vigna: trama a punti col simbolo Cadastra Symbol tasto 'b' (H=3,
        # distanza 10mm) - circ154_allegato2 cap.4. Grigio 50% in GB (valore di
        # trama a mezzatinta prescritto dal documento), verde in PB-MU (direttiva cantonale)
        apply_rule(root, build_sym('fill', fill_dash(None, C_NERO, 0.20, "1.5;0.5", [
            make_font_point_pattern('b', C_TRAMA_50 if is_gb else C_VIGNA_TRAMA, d=10.0, size=3.0)
        ])), genere_in(['vigna']), "Vigna")

        # Torbiera: trama a punti col simbolo Cadastra Symbol tasto 'd' (L=3.5,
        # distanza 10mm) - circ154_allegato2 cap.4
        apply_rule(root, build_sym('fill', fill_dash(None, C_NERO, 0.20, "1.5;0.5", [
            make_font_point_pattern('d', C_TRAMA_50 if is_gb else C_TORB_TRAMA, d=10.0, size=3.5)
        ])), genere_in(['torbiera']), "Torbiera")

        # Canneti: trama a punti col simbolo Cadastra Symbol tasto 'c' (H=3,
        # distanza 10mm) - circ154_allegato2 cap.4
        apply_rule(root, build_sym('fill', fill_dash(None, C_NERO, 0.20, "1.5;0.5", [
            make_font_point_pattern('c', C_TRAMA_50 if is_gb else C_CANN_TRAMA, d=10.0, size=3.0)
        ])), genere_in(['canneti']), "Canneti")

        # Pascolo boscato fitto: verde trasparente in PB-MU, trama punteggiata nera in GB (distanza 8)
        if is_gb:
            sym = build_sym('fill', fill_dash(None, C_NERO, 0.20, "1.5;0.5",
                                              [make_point_pattern(C_NERO, d=8.0, size=0.3)]))
        else:
            sym = build_sym('fill', [make_fill(C_PASCOLO_BOSC, C_NERO, 0.0, "no")])
            sym.setOpacity(0.65)
        apply_rule(root, sym, genere_in(['pascolo_boscato_fitto']), "Pascolo boscato fitto")

        # Pascolo boscato rado: stesso principio, trama punteggiata nera piu' rada (distanza 16)
        if is_gb:
            sym = build_sym('fill', fill_dash(None, C_NERO, 0.20, "1.5;0.5",
                                              [make_point_pattern(C_NERO, d=16.0, size=0.3)]))
        else:
            sym = build_sym('fill', [make_fill(C_PASCOLO_BOSC, C_NERO, 0.0, "no")])
            sym.setOpacity(0.65)
        apply_rule(root, sym, genere_in(['pascolo_boscato_rado']), "Pascolo boscato rado")

        # Fascia boscata: verde trasparente in PB-MU, solo bordo tratteggiato nero in GB
        if is_gb:
            sym = build_sym('fill', fill_dash(None, C_NERO, 0.20, "1.5;0.5"))
        else:
            sym = build_sym('fill', [make_fill(C_FASCIA_BOSC, C_NERO, 0.0, "no")])
            sym.setOpacity(0.65)
        apply_rule(root, sym, genere_in(['fascia_boscata']), "Fascia boscata")

        # Roccia: trama a simbolo tasto '1' (Symbol_1_Fels.svg), non tratteggio
        # generico - circ154_allegato2 cap.4 pag.20 ("simboli associati a
        # superfici"): grandezza 2.0mm, "Distanza da definire: 0" - il valore
        # "0" indicato dall'utente per questa voce significa letteralmente
        # simboli affiancati/sovrapposti senza spazi bianchi tra loro (non
        # "non specificato" come interpretato in una versione precedente,
        # che usava 8mm lasciando vistosi vuoti bianchi tra i simboli).
        #
        # "Distanza: 0" significa NESSUNA SPAZIATURA AGGIUNTA: il tasto e' un
        # elemento di FONT pensato per riempire una superficie, quindi si posa
        # affiancato a se' stesso e il passo della trama coincide con la
        # grandezza del simbolo (2.0 mm). Lo conferma l'illustrazione della
        # norma: vigna, torbiera e canneto (distanza 10) hanno simboli staccati
        # con bianco intorno, roccia e pietraia formano invece una texture
        # continua.
        # Prima si usava d=1.4mm - piu' STRETTO del glifo, quindi sovrapposto -
        # piu' un fondo grigio chiaro sotto la trama, aggiunto per eliminare i
        # vuoti bianchi residui. Entrambi cadono: il bianco fra i segni fa parte
        # della trama (si vede nell'illustrazione della norma), e coprirlo
        # alterava la resa d'insieme, che e' proprio cio' che il cap.4 regola.
        apply_rule(root, build_sym('fill', fill_dash(None, C_NERO, 0.20, "1.5;0.5", [
            make_font_point_pattern('1', c=C_TRAMA_50, d=DIM_ROCCIA, size=DIM_ROCCIA)
        ])), genere_in(['roccia']), "Roccia")

        # Pietraia, sabbia: trama a simbolo tasto '2' (Symbol_2_Geroell_Sand.svg),
        # stessa fonte/pagina di Roccia sopra, stessa lettura di "Distanza: 0".
        apply_rule(root, build_sym('fill', fill_dash(None, C_NERO, 0.20, "1.5;0.5", [
            make_font_point_pattern('2', c=C_TRAMA_50, d=DIM_ROCCIA, size=DIM_ROCCIA)
        ])), genere_in(['pietraia_sabbia']), "Pietraia / Sabbia")

        # Ghiacciaio, nevaio: blu trasparente in PB-MU, solo bordo tratteggiato nero in GB
        if is_gb:
            sym = build_sym('fill', fill_dash(None, C_NERO, 0.20, "1.5;0.5"))
        else:
            sym = build_sym('fill', fill_dash(C_GHIACCIAIO, C_NERO, 0.20, "1.5;0.5"))
            sym.setOpacity(0.5)
        apply_rule(root, sym, genere_in(['ghiacciaio_nevaio']), "Ghiacciaio / Nevaio")

        # Campi / Prati / Altro: bordo tratteggiato, nessun riempimento - gia' invariato
        apply_rule(root, build_sym('fill', fill_dash(None, C_NERO, 0.20, "1.5;0.5")),
                   genere_in(['campo_prato_pascolo', 'altro_humus', 'altra_coltura_intensiva',
                              'altra_senza_vegetazione', 'altro_rivestimento_duro',
                              'cava_di_ghiaia_discarica']), "Campi / Prati / Altro")

        # Giardino: verde in PB-MU, solo bordo tratteggiato nero in GB
        giardino_c = None if is_gb else C_GIARDINO
        apply_rule(root, build_sym('fill', fill_dash(giardino_c, gbc(is_gb, C_GIARDINO), 0.20, "1.5;0.5")),
                   genere_in(['giardino']), "Giardino")

        return QgsRuleBasedRenderer(root)

    def _gen_stile_elemento_lineare(self, is_gb):
        """Stile per Elemento_lineare - Spessori e tratteggi esatti da circ154_allegato2
        (cap. 3.5 "Tema: Oggetti singoli"): tutti i generi a 0.20mm eccetto sentiero
        (0.30mm); nessun genere del dominio Genere_OS deve restare senza regola,
        altrimenti la feature risulta invisibile (nessuna regola di fallback
        esiste in un QgsRuleBasedRenderer con filtri tutti espliciti). Tutti i
        filtri usano genere_in() perche' Genere_OS e' gerarchico - vedi genere_in()."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Elemento_lineare")

        # Muro, Arginatura, ecc.: continuo 0.20mm (include scala_importante,
        # grotta_entrata_di_caverna, masso_erratico, monumento, palo_antenna,
        # torre_panoramica: generi tipicamente puntiformi ma presenti anche nel
        # dominio di Elemento_lineare secondo circ154_allegato2, senza i quali la
        # feature resterebbe invisibile se mai rappresentata come linea; include anche
        # concimaia/riparo_fonico/serra, "continua" da circ154_allegato4.pdf cap. 3.3)
        apply_rule(root, build_sym('line', [make_line(C_NERO, 0.20)]),
                   genere_in(['muro', 'arginatura', 'ruscello', 'fontana', 'ponte_passerella',
                              'banchina', 'rovina_oggetto_archeologico', 'briglia', 'silo_torre_gasometro',
                              'zoccolo_massiccio', 'ciminiera', 'pilastro', 'debarcadero', 'scala_importante',
                              'grotta_entrata_di_caverna', 'masso_erratico', 'monumento', 'palo_antenna',
                              'torre_panoramica', 'concimaia', 'riparo_fonico', 'serra']),
                   "Muro / Arginatura / Ruscello")

        # Accesso_lago come oggetto lineare: interrotto1 1.5/0.5, spessore 0.20mm
        # (circ154_allegato4.pdf cap. 3.3: eccezione cantonale che estende l'uso di
        # "Interrotto1" - normalmente riservato al tema Copertura del suolo - anche
        # a questo genere supplementare di Oggetti singoli)
        # Accesso al lago (oggetto lineare): interrotto2 1.0/0.7.
        # Circ202_Allegato2 (settembre 2012) lo ha cambiato da interrotto1;
        # inoltre circ154_allegato2 cap.3.5 vieta interrotto1 in questo tema.
        apply_rule(root, build_sym('line', [make_line(C_NERO, 0.20, "1.0;0.7")]),
                   genere_in(['accesso_lago']), "Accesso al lago")

        # Muro di sostegno: stesso spessore (0.20mm) di muro, come da direttiva
        # cantonale (circ154_allegato4.pdf, cap. 3.3 "LIVELLO Oggetti singoli"):
        # "muro (muro di sostegno)-parte sporgente" = continua, "-parte interrata"
        # = punteggiato, nessuna differenza di spessore rispetto a "muro (muro)".
        apply_rule(root, build_sym('line', [make_line(C_NERO, 0.20, "0.5;0.5")]),
                   f"{genere_in(['muro_di_sostegno'])} AND \"genere_di_linea\" = 'parte_interrata'",
                   "Muro di sostegno (interrato)")
        apply_rule(root, build_sym('line', [make_line(C_NERO, 0.20)]),
                   f"{genere_in(['muro_di_sostegno'])} AND (\"genere_di_linea\" <> 'parte_interrata' "
                   "OR \"genere_di_linea\" IS NULL)", "Muro di sostegno")

        # Muro divisorio: interrotto2 1.0/0.7 secondo Circ202_Allegato2
        # (settembre 2012), che sostituisce l'"interrotto" 2.5/0.7 del
        # precedente circ154_allegato4 (2007).
        apply_rule(root, build_sym('line', [make_line(C_NERO, 0.20, "1.0;0.7")]),
                   genere_in(['muro_divisorio']), "Muro divisorio")

        # Sentiero: interrotto2 1.0/0.7, spessore 0.30mm (eccezione di spessore rispetto al tema)
        apply_rule(root, build_sym('line', [make_line(C_NERO, 0.30, "1.0;0.7")]),
                   genere_in(['sentiero']), "Sentiero")

        # Edificio sotterraneo, Tunnel, Serbatoio: punteggiato 0.5/0.5, spessore 0.20mm
        apply_rule(root, build_sym('line', [make_line(C_NERO, 0.20, "0.5;0.5")]),
                   genere_in(['edificio_sotterraneo', 'edificio_sotterraneo_indipendente',
                              'parte_sotterranea_di_edificio', 'acqua_sotterranea_canalizzata',
                              'serbatoio', 'tunnel_sottopassaggio_galleria']), "Sotterraneo / Tunnel")

        # Altra parte di edificio, Riparo: interrotto2 1.0/0.7, spessore 0.20mm
        apply_rule(root, build_sym('line', [make_line(C_NERO, 0.20, "1.0;0.7")]),
                   genere_in(['altra_parte_di_edificio', 'scala', 'altra_parte_costruttiva',
                              'riparo', 'fascia_boscata', 'riparo_antivalanghe']), "Riparo / Fascia boscata")

        # Linea aerea ad alta tensione, Condotta forzata: mista 6.5/1.0/1.0/1.0/1.0/1.0, spessore 0.20mm
        apply_rule(root, build_sym('line', [make_line(C_NERO, 0.20, "6.5;1.0;1.0;1.0;1.0;1.0")]),
                   genere_in(['linea_aerea_ad_alta_tensione', 'condotta_forzata']), "Alta tensione")

        # Teleferica, Telecabina/Seggiovia, Teleferica per il materiale, Binari ferrovia,
        # Asse, Traghetto: tutti "misto2" 10/1.0/1.8/1.0, spessore 0.20mm (circ154_allegato2)
        apply_rule(root, build_sym('line', [make_line(C_NERO, 0.20, "10;1.0;1.8;1.0")]),
                   genere_in(['teleferica', 'telecabina_seggiovia', 'teleferica_per_il_materiale',
                              'binari_ferrovia', 'asse', 'traghetto']),
                   "Teleferica / Binari ferrovia / Asse")

        # Scilift: colore speciale CMYK(37,80,100,0) in PB-MU / nero in GB, misto2 10/1.0/1.8/1.0, spessore 0.20mm
        apply_rule(root, build_sym('line', [make_line(gbc(is_gb, QColor(102, 51, 0)), 0.20, "10;1.0;1.8;1.0")]),
                   genere_in(['scilift']), "Scilift")

        return QgsRuleBasedRenderer(root)

    def _gen_stile_elemento_puntiforme(self, is_gb):
        """Stile per Elemento_puntiforme - Con maschera per leggibilità. Tutti i
        filtri usano genere_in() perche' Genere_OS e' gerarchico - vedi genere_in()."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Elemento_puntiforme")

        # Albero isolato importante: tasto o, H=4mm, colore verde CMYK(80,34,100,0) in PB-MU / nero in GB
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('o', sz=4.0, c=gbc(is_gb, C_VIGNA_TRAMA))),
                   genere_in(['albero_importante']), "Albero isolato")

        # Masso erratico: tasto g, L=4mm, nero
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('g', sz=4.0)),
                   genere_in(['masso_erratico']), "Masso erratico")

        # Sorgente: tasto i, H=4mm, colore blu CMYK(70,60,0,0) in PB-MU / nero in GB
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('i', sz=4.0, c=gbc(is_gb, C_TORB_TRAMA))),
                   genere_in(['sorgente']), "Sorgente")

        # Monumento: tasto k, H=4mm, nero
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('k', sz=4.0)),
                   genere_in(['monumento']), "Monumento")

        # Palo/Antenna: tasto h, H=4mm, nero
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('h', sz=4.0)),
                   genere_in(['palo_antenna']), "Palo/Antenna")

        # Torre panoramica: tasto p, H=4mm, nero
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('p', sz=4.0)),
                   genere_in(['torre_panoramica']), "Torre panoramica")

        # Traghetto: tasto n, H=5mm, nero
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('n', sz=5.0)),
                   genere_in(['traghetto']), "Traghetto")

        # Grotta/Entrata caverna: tasto f, H=4mm, nero
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('f', sz=4.5)),
                   genere_in(['grotta_entrata_di_caverna']), "Grotta")

        # Rovina: tasto u, H=4mm, nero. NOTA: il font "CadastraSymbol Mask" non
        # ha un glifo corretto per 'u' (ripiega su un fallback testuale, vedi
        # _FONT_INK_FRACTION) - l'alone per questo simbolo risultera'
        # visibilmente sbagliato, difetto accettato esplicitamente dall'utente.
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('u', sz=4.0)),
                   genere_in(['rovina_oggetto_archeologico']), "Rovina")

        # Statua/Crocefisso/Cappella: tasto y, nero (verificato sulla legenda ufficiale
        # cantonale, gruppo Ogg_X_Elemento_puntiforme - non "j" come nella tabella
        # generica federale)
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('y', sz=4.0)),
                   genere_in(['cappella_statua_crocifisso']), "Statua/Crocefisso/Cappella")

        # Punto di riferimento: tasto q, nero (mancante nella tabella generica
        # federale, verificato sulla legenda ufficiale cantonale)
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('q', sz=3.0)),
                   genere_in(['punto_di_riferimento']), "Punto di riferimento")

        # Acqua sotterranea canalizzata / Ruscello come punto (es. direzione della
        # corrente): tasto a. Questi Genere sono normalmente rappresentati come
        # linea (Elemento_lineare); qui si copre il caso in cui compaiano come
        # Elemento_puntiforme (verificato sulla legenda ufficiale cantonale).
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('a', sz=4.0)),
                   genere_in(['acqua_sotterranea_canalizzata', 'ruscello']),
                   "Direzione della corrente")

        apply_rule(root, build_sym('point', [make_simple_marker("circle", 0.6, C_NERO)]),
                   "", "Punto generico")

        return QgsRuleBasedRenderer(root)

    def _gen_stile_simbolo_superficie_cs(self, is_gb):
        """Stile per SimboloSuperficieCS (circ154_allegato2 cap.2.3 pag.11,
        cap.4 pag.19): un simbolo singolo posizionato ENTRO una SuperficieCS,
        alternativo alla trama ripetuta, per i pochi Genere per cui il
        documento lo prescrive esplicitamente (commento ILI subito prima di
        "TABLE SimboloSuperficieCS"): rivestimento_duro.bacino_idrico e
        acque.specchio_acqua -> tasto 'e' (Bacino idrico/specchio d'acqua,
        L=4mm); acque.corso_acqua (fiume/torrente/canale) -> tasto 'a'
        (direzione della corrente, H=6mm), orientato secondo l'attributo
        "Ori" nativo della tabella (non serve il join sul padre, a
        differenza di "Genere" - vedi ILI: "Ori: OPTIONAL Rotazione //
        non_definito= 0.0 //"). Stessa conversione Ori(gon)->gradi QGIS gia'
        usata per le etichette in _apply_pos_text_attrs, qui applicata alla
        rotazione del simbolo invece che del testo."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("SimboloSuperficieCS")

        # bacino_idrico ha 2 figli nel dominio ILI (piscina, altro_bacino_idrico -
        # vedi "bacino_idrico (piscina, altro_bacino_idrico)" nel modello): sono
        # i valori foglia REALMENTE usati nei dati (verificato su un GeoPackage
        # reale, 99+3 feature su 131 totali) - il nodo "bacino_idrico" da solo
        # non compare mai come valore foglia, va quindi elencato coi suoi figli
        # e non captato dal solo genere_in(['bacino_idrico']) (che matcherebbe
        # solo il valore esatto o un suffisso diretto ".bacino_idrico", non
        # ".bacino_idrico.piscina").
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask(
            'e', sz=4.0, c=gbc(is_gb, C_ACQUA))),
                   genere_in(['bacino_idrico', 'piscina', 'altro_bacino_idrico', 'specchio_acqua']),
                   "Bacino idrico/specchio d'acqua")

        # NB: la conversione qui e' DIVERSA da quella usata per la rotazione
        # del TESTO in _apply_pos_text_attrs ((ori-100)*0.9) - verificato
        # empiricamente con un render isolato a Ori=0/100/200/300 (attesi
        # N/E/S/W): QgsMarkerSymbol.setDataDefinedAngle ruota in senso
        # ORARIO a partire dal disegno nativo del glifo (gia' orientato a
        # Nord/su), la stessa convenzione della bussola usata da "Ori" -
        # nessun offset di -100 necessario qui (quello serve solo per la
        # rotazione TESTO, che in QGIS usa la convenzione matematica
        # antioraria-da-Est).
        corrente_sym = build_sym('point', make_true_font_marker_with_mask('a', sz=6.0))
        corrente_sym.setDataDefinedAngle(
            QgsProperty.fromExpression('coalesce("ori", 0) * 0.9'))
        apply_rule(root, corrente_sym,
                   genere_in(['corso_acqua', 'fiume', 'torrente', 'canale']),
                   "Direzione della corrente")

        return QgsRuleBasedRenderer(root)

    def _gen_stile_bene_immobile(self, is_gb):
        """Stile per Bene_immobile - spessori verificati sulla legenda ufficiale
        cantonale (Leg_PpiRF_MD01MUTI7MN95, gruppo Ben_X_Bene_immobile_Genere_di_linea):
        tutti gli stati usano 0.40mm, variano solo nel tratteggio. NB: la geometria
        di Bene_immobile e' un'AREA (CURVEPOLYGON), non una linea: serve un simbolo
        'fill' trasparente (solo contorno) - un QgsLineSymbol non e' compatibile
        con un layer poligonale e non verrebbe disegnato affatto."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Bene_immobile")
        confine_c = gbc(is_gb, C_BP_CONFINE)

        # Confine in vigore: continuo 0.40mm
        apply_rule(root, build_sym('fill', [make_fill(None, confine_c, 0.40)]),
                   "\"genere_di_linea\" = 'non_definito' OR \"genere_di_linea\" IS NULL", "Confine in vigore")

        # Confine contestato: interrotto3 4.0/1.0, spessore 0.40mm
        apply_rule(root, build_sym('fill', fill_dash(None, confine_c, 0.40, "4.0;1.0")),
                   "\"genere_di_linea\" = 'contestato'", "Confine contestato")

        # Confine incompleto: limite del foglio 1.5/1.0, spessore 0.40mm
        apply_rule(root, build_sym('fill', fill_dash(None, confine_c, 0.40, "1.5;1.0")),
                   "\"genere_di_linea\" = 'incompleto'", "Confine incompleto")

        return QgsRuleBasedRenderer(root)

    def _gen_stile_dpssp_miniera(self, is_gb):
        """Stile per DPSSP/Miniera - spessori verificati sulla legenda ufficiale
        cantonale (gruppi Ben_X_DPSSP_Genere_di_linea / Ben_X_Miniera_Genere_di_linea).
        A differenza di Bene_immobile, lo stato "in vigore" (Genere_di_linea non
        definito) e' rappresentato con tratto interrotto, non continuo; tutti gli
        stati usano comunque 0.40mm. NB: geometria AREA (CURVEPOLYGON) come
        Bene_immobile -> simbolo 'fill' trasparente, non 'line'."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("DPSSP_Miniera")
        confine_c = gbc(is_gb, C_BP_CONFINE)

        # In vigore: interrotto 2.5/0.7, spessore 0.40mm
        apply_rule(root, build_sym('fill', fill_dash(None, confine_c, 0.40, "2.5;0.7")),
                   "\"genere_di_linea\" = 'non_definito' OR \"genere_di_linea\" IS NULL", "In vigore")

        # Contestato: interrotto3 4.0/1.0, spessore 0.40mm
        apply_rule(root, build_sym('fill', fill_dash(None, confine_c, 0.40, "4.0;1.0")),
                   "\"genere_di_linea\" = 'contestato'", "Contestato")

        # Incompleto: limite del foglio 1.5/1.0, spessore 0.40mm
        apply_rule(root, build_sym('fill', fill_dash(None, confine_c, 0.40, "1.5;1.0")),
                   "\"genere_di_linea\" = 'incompleto'", "Incompleto")

        return QgsRuleBasedRenderer(root)

    def _gen_stile_confine_comunale(self, is_gb):
        """Stile per Confine_comunale - 3.5/1.0/1.0/1.0; 0.40mm se in_vigore, altrimenti 0.30mm.
        NB: geometria AREA (CURVEPOLYGON, il confine comunale e' un poligono chiuso)
        -> simbolo 'fill' trasparente, non 'line' (a differenza di Confine_cantonale/
        nazionale/distrettuale, la cui geometria e' invece una linea/COMPOUNDCURVE)."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Confine_comunale")
        c = gbc(is_gb, C_BP_CONFINE)
        apply_rule(root, build_sym('fill', fill_dash(None, c, 0.40, "3.5;1.0;1.0;1.0")),
                   "\"genere_di_linea\" = 'in_vigore'", "Confine comunale (in vigore)")
        apply_rule(root, build_sym('fill', fill_dash(None, c, 0.30, "3.5;1.0;1.0;1.0")),
                   "\"genere_di_linea\" <> 'in_vigore' OR \"genere_di_linea\" IS NULL", "Confine comunale")
        return QgsRuleBasedRenderer(root)

    def _gen_stile_confine_cantonale(self, is_gb):
        """Stile per Confine_cantonale - linea sottile + simbolo Cadastra Symbol
        tasto '4' ripetuto ogni 4.5mm (3.0+1.5), come da "Tasto alfanumerico
        simbolo CADASTRA" in circ154_allegato2.pdf; spessore linea base 0.40mm
        se in_vigore, altrimenti 0.30mm."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Confine_cantonale")
        c = gbc(is_gb, C_BP_CONFINE)
        apply_rule(root, build_sym('line', [make_line(c, 0.40), make_font_marker_line('4', 4.5, c, sz=1.2)]),
                   "\"Validita\" = 'in_vigore'", "Confine cantonale (in vigore)")
        apply_rule(root, build_sym('line', [make_line(c, 0.30), make_font_marker_line('4', 4.5, c, sz=1.2)]),
                   "\"Validita\" <> 'in_vigore' OR \"Validita\" IS NULL", "Confine cantonale")
        return QgsRuleBasedRenderer(root)

    def _gen_stile_confine_nazionale(self, is_gb):
        """Stile per Confine_nazionale - linea sottile + simbolo Cadastra Symbol
        tasto '3' ripetuto ogni 4.0mm (2.0+2.0), come da "Tasto alfanumerico
        simbolo CADASTRA" in circ154_allegato2.pdf; spessore linea base 0.40mm
        se in_vigore, altrimenti 0.30mm."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Confine_nazionale")
        c = gbc(is_gb, C_BP_CONFINE)
        apply_rule(root, build_sym('line', [make_line(c, 0.40), make_font_marker_line('3', 4.0, c, sz=1.0)]),
                   "\"Validita\" = 'in_vigore'", "Confine nazionale (in vigore)")
        apply_rule(root, build_sym('line', [make_line(c, 0.30), make_font_marker_line('3', 4.0, c, sz=1.0)]),
                   "\"Validita\" <> 'in_vigore' OR \"Validita\" IS NULL", "Confine nazionale")
        return QgsRuleBasedRenderer(root)

    def _gen_stile_confine_distrettuale(self, is_gb):
        """Stile per Confine_distrettuale - 3.5/1.0/1.0/1.0/1.0/1.0; 0.40mm se in_vigore, altrimenti 0.30mm"""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Confine_distrettuale")
        c = gbc(is_gb, C_BP_CONFINE)
        apply_rule(root, build_sym('line', [make_line(c, 0.40, "3.5;1.0;1.0;1.0;1.0;1.0")]),
                   "\"Validita\" = 'in_vigore'", "Confine distrettuale (in vigore)")
        apply_rule(root, build_sym('line', [make_line(c, 0.30, "3.5;1.0;1.0;1.0;1.0;1.0")]),
                   "\"Validita\" <> 'in_vigore' OR \"Validita\" IS NULL", "Confine distrettuale")
        return QgsRuleBasedRenderer(root)

    def _gen_stile_punto_di_confine(self, is_gb, layer=None):
        """Stile per Punto_di_confine / PCGiurisdizionale - con maschera.
        Il campo del modello e' "Segno" (dominio Materiale), non "Simbolo".
        Mappatura verificata sulla legenda ufficiale cantonale
        (Leg_PpiRF_MD01MUTI7MN95, gruppi Con_X_PCGiurisdizionale_si/_no):
        il Cantone usa una legenda semplificata rispetto alla tabella generica
        federale (niente tasto "S" separato per la croce: confluisce in "Q"
        insieme a bullone/campanile).
        Su PCGiurisdizionale, quando "cippo_giurisdizionale" = 'si' (punto di
        confine giurisdizionale rilevante), si usano i tasti P/Q/R al posto di
        E/F/G/H (Punto_di_confine non ha questo campo).
        NB: ili2db esporta i nomi dei campi in minuscolo ("segno",
        "cippo_giurisdizionale") anche se nel modello ILI sono scritti con la
        maiuscola iniziale - confermato via QML esportato dal layer reale
        (campo <field name="segno">). Vanno quindi referenziati in minuscolo
        nei filtri, altrimenti nessuna regola scatta mai e tutto ricade sul
        fallback "Punto generico".
        BUG CORRETTO QUI: l'assunzione precedente era che
        '"cippo_giurisdizionale" IS NULL' valutasse a TRUE quando il campo
        manca del tutto dalla tabella (vero per Punto_di_confine, che non ha
        mai questo campo) - falso. QgsExpression genera un vero e proprio
        errore di valutazione ("Field 'cippo_giurisdizionale' not found",
        verificato con un render headless reale su beni_immobili_punto_di_confine),
        non NULL: l'intera espressione AND diventa non valutabile e la regola
        NON scatta mai, per NESSUN valore di "segno". Risultato: ogni punto di
        Punto_di_confine ricadeva sempre sul fallback "Punto generico" (cerchio
        pieno nero, senza alone bianco) - la causa reale sia del "sembra sotto
        alle altre linee" sia del "si vedono complementi neri" segnalati
        dall'utente (un punto nero pieno senza alone si confonde con qualunque
        linea nera sotto, indipendentemente dall'ordine dei layer). Soluzione:
        controllare l'ESISTENZA del campo (non il suo valore) sul layer
        passato, e costruire l'albero di regole SENZA il livello
        giurisdizionale ne' la guardia AND quando il campo non esiste
        affatto (come su Punto_di_confine), invece di generare un'espressione
        che referenzia comunque un campo assente."""
        has_giur_field = layer is not None and layer.fields().indexFromName("cippo_giurisdizionale") >= 0
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Punto_di_confine")
        # Il dominio Materiale e' gerarchico (croce_scolpito(croce, scolpito),
        # altro(campanile, altro)): usa genere_in(field="segno") invece del
        # confronto diretto, per lo stesso motivo di Genere_CS/Genere_OS.

        if has_giur_field:
            non_giurisdizionale = "(\"cippo_giurisdizionale\" IS NULL OR \"cippo_giurisdizionale\" <> 'si')"
            giurisdizionale = "\"cippo_giurisdizionale\" = 'si'"

            # --- Punto di confine giurisdizionale rilevante: tasti P/Q/R ---
            apply_rule(root, build_sym('point', make_true_font_marker_with_mask('P', sz=3.4)),
                       f"{giurisdizionale} AND {genere_in(['termine_cippo', 'termine_artificiale'], field='segno')}",
                       "Termine giurisdizionale rilevante")
            apply_rule(root, build_sym('point', make_true_font_marker_with_mask('Q', sz=3.4)),
                       f"{giurisdizionale} AND {genere_in(['bullone', 'campanile', 'croce_scolpito', 'croce', 'scolpito'], field='segno')}",
                       "Bollone/Croce giurisdizionale rilevante")
            apply_rule(root, build_sym('point', make_true_font_marker_with_mask('R', sz=3.4)),
                       f"{giurisdizionale} AND {genere_in(['tubo', 'palo_picchetto'], field='segno')}",
                       "Tubo/Picchetto giurisdizionale rilevante")
            # Non materializzato giurisdizionale: composito N (anello, con maschera N) + I (interruzione) -
            # N da solo e' un anello giurisdizionale generico, I e' lo stesso
            # tasto che indica "non materializzato" nella tabella non
            # giurisdizionale: la combinazione resta necessaria (non e' un
            # dettaglio della resa SVG, e' il significato del simbolo).
            apply_rule(root, build_sym('point', make_true_font_marker_with_mask('N', sz=3.4)
                                        + make_true_font_marker_with_mask('I', sz=0.4, halo_scale=3.0)),
                       f"{giurisdizionale} AND {genere_in(['non_materializzato'], field='segno')}",
                       "Non materializzato giurisdizionale rilevante")
        else:
            non_giurisdizionale = None

        def guarded(expr):
            return f"{non_giurisdizionale} AND {expr}" if non_giurisdizionale else expr

        # --- Materializzazione standard: tasti E/F/G/H ---
        # Su richiesta esplicita dell'utente, maschera e font hanno la STESSA
        # dimensione per E/F/G/H (halo_scale=1.0, invece del default 1.25 che
        # ingrandisce l'alone rispetto al glifo nero): niente margine bianco
        # oltre il contorno del simbolo.
        # Termine/Termine artificiale: tasto E, diametro 1.4mm, con maschera
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('E', sz=1.4, halo_scale=1.0)),
                   guarded(genere_in(['termine_cippo', 'termine_artificiale'], field='segno')), "Termine")

        # Bollone (anche "altro.campanile"): tasto F, diametro 1.0mm, con maschera
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('F', sz=1.0, halo_scale=1.0)),
                   guarded(genere_in(['bullone', 'campanile'], field='segno')), "Bollone")

        # Tubo/Picchetto: tasto G, diametro 0.8mm, con maschera
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('G', sz=0.8, halo_scale=1.0)),
                   guarded(genere_in(['tubo', 'palo_picchetto'], field='segno')), "Tubo/Picchetto")

        # Croce: tasto H, 0.8/2.4mm, con maschera
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('H', sz=2.4, halo_scale=1.0)),
                   guarded(genere_in(['croce_scolpito', 'croce', 'scolpito'], field='segno')), "Croce")

        # Non materializzato: tasto I, con maschera (caso non giurisdizionale).
        # Diametro nero base da circ154_allegato2 cap.2.2 pag.9-10 (⌀0.4mm,
        # tasto I; l'1.2mm della stessa voce e' la zona di interruzione della
        # linea attorno al punto, non il punto stesso) - ridotto qui a 0.3mm
        # con halo_scale=2.6 (invece del default 1.25): valore scelto su
        # richiesta esplicita dell'utente dopo verifica visiva del render,
        # per un alone abbastanza largo da restare leggibile quando il
        # simbolo cade su una linea nera.
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('I', sz=0.4, halo_scale=3.0)),
                   guarded(genere_in(['non_materializzato'], field='segno')), "Non materializzato")

        apply_rule(root, build_sym('point', [make_simple_marker("circle", 0.6, C_NERO)]),
                   "", "Punto generico")

        return QgsRuleBasedRenderer(root)

    def _gen_stile_pfp(self, is_gb, t_low):
        """Stile per PFP1/PFP2/PFP3 - Con maschera.
        PFP1/PFP2 distinguono accessibile/inaccessibile con il campo "Accessibilita".
        PFP3 (campo "Segno": Materiale) usa i tasti J/K/L/M quando materializzato
        su termine/bollone/tubo/croce, altrimenti N (mappatura verificata sulla
        legenda ufficiale cantonale, gruppo Pun_X_PFP3 - non "O", che in questo
        progetto non risulta usato).
        NB: campi referenziati in minuscolo ("segno", "accessibilita") perche'
        ili2db esporta i nomi dei campi tutti minuscoli indipendentemente dalla
        capitalizzazione nel modello ILI - confermato via QML esportato da un
        layer reale (vedi anche _gen_stile_punto_di_confine)."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Punti fissi PFP")

        if "pfp3" in t_low:
            apply_rule(root, build_sym('point', make_true_font_marker_with_mask('J', sz=2.4)),
                       genere_in(['termine_cippo', 'termine_artificiale'], field='segno'), "PFP3 su termine")
            apply_rule(root, build_sym('point', make_true_font_marker_with_mask('K', sz=2.4)),
                       genere_in(['bullone', 'campanile'], field='segno'), "PFP3 su bollone")
            apply_rule(root, build_sym('point', make_true_font_marker_with_mask('L', sz=2.4)),
                       genere_in(['tubo', 'palo_picchetto'], field='segno'), "PFP3 su tubo/picchetto")
            apply_rule(root, build_sym('point', make_true_font_marker_with_mask('M', sz=2.4)),
                       genere_in(['croce_scolpito', 'croce', 'scolpito'], field='segno'), "PFP3 su croce")
            # PFP3 non materializzato (o Segno non valorizzato): tasto N
            apply_rule(root, build_sym('point', make_true_font_marker_with_mask('N', sz=3.0)),
                       f"{genere_in(['non_materializzato'], field='segno')} OR \"segno\" IS NULL", "PFP3")
        else:
            # PFP1+2 accessibile: tasto A, 3.2mm
            apply_rule(root, build_sym('point', make_true_font_marker_with_mask('A', sz=3.2)),
                       "\"accessibilita\" = 'accessibile'", "PFP1+2 accessibile")

            # PFP1+2 inaccessibile: tasto B, 3.0mm
            # O3.6 = estensione esterna del simbolo secondo circ154_allegato2
            # cap.2.2 ("3.0 / O0.8 / O3.6": 3.0 e' la croce interna).
            apply_rule(root, build_sym('point', make_true_font_marker_with_mask('B', sz=3.6)),
                       "\"accessibilita\" = 'inaccessibile'", "PFP1+2 inaccessibile")

        return QgsRuleBasedRenderer(root)

    def _gen_stile_pfa(self, is_gb, t_low):
        """Stile per PFA1/PFA2/PFA3 - Con maschera.
        PFA1-2 e PFA3 non condividono un campo distintivo: la scelta del simbolo
        dipende dalla tabella di provenienza (t_low)."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Punti fissi PFA")

        if "pfa3" in t_low:
            # PFA3: tasto D, diametro 1.8mm
            apply_rule(root, build_sym('point', make_true_font_marker_with_mask('D', sz=1.8)),
                       "", "PFA3")
        else:
            # PFA1-2: tasto C, diametro 1.8mm
            apply_rule(root, build_sym('point', make_true_font_marker_with_mask('C', sz=1.8)),
                       "", "PFA1-2")

        return QgsRuleBasedRenderer(root)

    def _gen_stile_segnale_condotta(self, is_gb):
        """Stile per la tabella Segnale (Topic Condotte) - campo Genere_del_punto"""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Segnale_condotta")

        # Segnale: tasto l, H=4mm, nero
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('l', sz=4.0)),
                   "\"Genere_del_punto\" = 'segnale'", "Segnale condotta")

        # Tavola/Cippo: tasto m, H=4mm, nero
        apply_rule(root, build_sym('point', make_true_font_marker_with_mask('m', sz=4.0)),
                   "\"Genere_del_punto\" = 'tavola_cippo'", "Tavola/Cippo condotta")

        apply_rule(root, build_sym('point', [make_simple_marker("circle", 0.6, C_NERO)]),
                   "", "Punto generico")

        return QgsRuleBasedRenderer(root)

    def _gen_stile_elemento_con_superficie(self, is_gb):
        """Stile per Elemento_con_superficie (oggetti singoli poligonali). Il perimetro
        usa lo stesso vocabolario di tratteggio genere-per-genere di Elemento_lineare
        (circ154_allegato2 cap. 3.5, spessore 0.20mm), applicato come contorno di un
        riempimento trasparente, ad eccezione di edificio_sotterraneo/serbatoio che
        mantengono il riempimento colorato/a trama gia' verificato."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Elemento_con_superficie")

        # Edificio sotterraneo: verificato sulla legenda ufficiale (Leggenda
        # del piano per il registro fondiario, pag.3 "Trame") - riquadro
        # grigio chiaro pieno in b/n, NESSUN riempimento (solo bordo
        # puntinato) in colore. Corretto qui: la versione precedente usava un
        # riempimento rosa in PB-MU (mai mostrato dalla legenda ufficiale per
        # questa voce - il rosa e' riservato a "Edificio", riga sopra nella
        # stessa tabella) e una trama a punti aggiuntiva non presente nel
        # riquadro originale. Contorno punteggiato 0.5/0.5 confermato.
        sott_c = C_TRAMA_10 if is_gb else None
        apply_rule(root, build_sym('fill', fill_dash(sott_c, C_NERO, 0.20, "0.5;0.5")),
                   genere_in(['edificio_sotterraneo', 'edificio_sotterraneo_indipendente',
                              'parte_sotterranea_di_edificio']), "Edificio sotterraneo")

        # Serbatoio: stesso trattamento cromatico dell'edificio sotterraneo, contorno punteggiato
        apply_rule(root, build_sym('fill', fill_dash(sott_c, C_NERO, 0.20, "0.5;0.5")),
                   genere_in(['serbatoio']), "Serbatoio")

        # Muro di sostegno: stesso spessore (0.20mm) di muro, come da direttiva
        # cantonale (circ154_allegato4.pdf); contorno punteggiato se parte interrata,
        # continuo altrimenti - nessuna differenza di spessore rispetto a "muro".
        apply_rule(root, build_sym('fill', fill_dash(None, C_NERO, 0.20, "0.5;0.5")),
                   f"{genere_in(['muro_di_sostegno'])} AND \"genere_di_linea\" = 'parte_interrata'",
                   "Muro di sostegno (interrato)")
        apply_rule(root, build_sym('fill', [make_fill(None, C_NERO, 0.20)]),
                   f"{genere_in(['muro_di_sostegno'])} AND (\"genere_di_linea\" <> 'parte_interrata' "
                   "OR \"genere_di_linea\" IS NULL)", "Muro di sostegno")

        # Muro divisorio: interrotto2 1.0/0.7 secondo Circ202_Allegato2
        # (settembre 2012), che sostituisce l'"interrotto" 2.5/0.7 del 2007.
        apply_rule(root, build_sym('fill', fill_dash(None, C_NERO, 0.20, "1.0;0.7")),
                   genere_in(['muro_divisorio']), "Muro divisorio")

        # Continuo: nessun riempimento, contorno pieno 0.20mm (include anche
        # concimaia/riparo_fonico/serra/accesso_lago come oggetto con superficie,
        # tutti "continua" da circ154_allegato4.pdf cap. 3.3)
        apply_rule(root, build_sym('fill', [make_fill(None, C_NERO, 0.20)]),
                   genere_in(['muro', 'arginatura',
                              'ruscello', 'fontana', 'ponte_passerella', 'banchina',
                              'rovina_oggetto_archeologico', 'briglia', 'silo_torre_gasometro',
                              'zoccolo_massiccio', 'ciminiera', 'pilastro', 'debarcadero', 'scala_importante',
                              'grotta_entrata_di_caverna', 'masso_erratico', 'monumento', 'palo_antenna',
                              'torre_panoramica', 'concimaia', 'riparo_fonico', 'serra', 'accesso_lago']),
                   "Muro / Arginatura / Ruscello")

        # Interrotto2 1.0/0.7: nessun riempimento
        apply_rule(root, build_sym('fill', fill_dash(None, C_NERO, 0.20, "1.0;0.7")),
                   genere_in(['altra_parte_di_edificio', 'scala', 'altra_parte_costruttiva',
                              'riparo', 'fascia_boscata', 'riparo_antivalanghe']), "Riparo / Fascia boscata")

        # Punteggiato 0.5/0.5: nessun riempimento (Tunnel/Acqua sotterranea canalizzata)
        apply_rule(root, build_sym('fill', fill_dash(None, C_NERO, 0.20, "0.5;0.5")),
                   genere_in(['acqua_sotterranea_canalizzata', 'tunnel_sottopassaggio_galleria']),
                   "Tunnel / Acqua sotterranea canalizzata")

        # Misto1 6.5/1.0/1.0/1.0/1.0/1.0: nessun riempimento (Alta tensione/Condotta forzata)
        apply_rule(root, build_sym('fill', fill_dash(None, C_NERO, 0.20, "6.5;1.0;1.0;1.0;1.0;1.0")),
                   genere_in(['linea_aerea_ad_alta_tensione', 'condotta_forzata']), "Alta tensione")

        # Misto2 10/1.0/1.8/1.0: nessun riempimento (Teleferica/Binari ferrovia/Asse/Traghetto)
        apply_rule(root, build_sym('fill', fill_dash(None, C_NERO, 0.20, "10;1.0;1.8;1.0")),
                   genere_in(['teleferica', 'telecabina_seggiovia', 'teleferica_per_il_materiale',
                              'binari_ferrovia', 'asse', 'traghetto']), "Teleferica / Binari ferrovia / Asse")

        # Altri oggetti con superficie non altrimenti classificati (es. sottocategorie di "altro":
        # concimaia, riparo_fonico, serra, accesso_lago - nessuna specifica federale reperita)
        # Ripiego per generi non mappati: 0.20 mm come tutto il tema e
        # interrotto2, perche' circ154_allegato2 cap.3.5 vieta interrotto1 qui.
        apply_rule(root, build_sym('fill', fill_dash(None, C_NERO, 0.20, "1.0;0.7")),
                   "", "Altro oggetto con superficie")

        return QgsRuleBasedRenderer(root)

    def _gen_stile_indirizzi_edifici(self, is_gb):
        """Stile per Indirizzi_edifici (simbolo invisibile, gestito da etichette)"""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Indirizzi_edifici")
        sym = build_sym('point', [make_simple_marker("circle", 0.01, QColor(0, 0, 0, 0))])
        apply_rule(root, sym, "", "Testo indirizzo")
        return QgsRuleBasedRenderer(root)

    def _gen_stile_tronco_strada(self, is_gb):
        """Stile per Tronco_di_strada (assi stradali) - invisibile su richiesta utente."""
        return self._gen_stile_invisibile("LINE")

    def _gen_stile_altimetria_punti(self, is_gb):
        """Stile per Punto_quotato.

        Appartiene al tema Altimetria, che circ154_allegato2 cap.1.5.3 esclude
        dal piano per il registro fondiario; compare invece nella legenda del
        piano di base (BP-AV-Legende, fra i simboli, in arancione). Quindi si
        disegna solo in PB-MU. Prima veniva disegnato in entrambi i prodotti."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Punto_quotato")
        if is_gb:
            self.log("   ⏭️ Punto quotato: tema Altimetria, non rappresentato "
                     "sul piano RF (cap.1.5.3) -> invisibile")
            return self._gen_stile_invisibile("Point")
        apply_rule(root, build_sym('point', [make_simple_marker("circle", 0.5, C_NERO)]),
                   "", "Punto quotato")
        return QgsRuleBasedRenderer(root)

    def _gen_stile_altimetria_linee(self, is_gb):
        """Stile per le curve di livello.

        Come il punto quotato appartengono all'Altimetria, tema che il
        cap.1.5.3 esclude dal piano RF: si disegnano solo in PB-MU. La', il
        Weisung §2.2.10 prescrive spessore 0.15 mm (0.25 per le curve
        principali, che il modello non distingue) e Marrone CMYK(45,73,100,0),
        cioe' (140,69,0). Prima erano 0.10 mm e un marrone (153,102,51) senza
        riscontro nella norma, disegnati in entrambi i prodotti."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Curve_livello")
        if is_gb:
            self.log("   ⏭️ Curve di livello: tema Altimetria, non rappresentato "
                     "sul piano RF (cap.1.5.3) -> invisibile")
            return self._gen_stile_invisibile("Line")
        apply_rule(root, build_sym('line', [make_line(C_BP_CURVA_LIVELLO,
                                                      LARGHEZZA_BP_ALTIMETRIA)]),
                   "", "Curva di livello")
        return QgsRuleBasedRenderer(root)

    def _gen_stile_limiti_bosco(self, is_gb):
        """Stile per Limite legale del bosco - tratto 3.5/1.0, spessore 0.3mm (circ154/Circ202)"""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Limite_bosco")
        apply_rule(root, build_sym('line', [make_line(gbc(is_gb, QColor(0, 102, 0)), 0.30, "3.5;1.0")]),
                   "", "Limite legale bosco")
        return QgsRuleBasedRenderer(root)

    def _gen_stile_aree_numerazione(self, is_gb):
        """Stile per Aree di numerazione"""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Aree_numerazione")
        apply_rule(root, build_sym('fill', [make_fill(None, QColor(100, 100, 100), 0.20, "dash")]),
                   "", "Area di numerazione")
        return QgsRuleBasedRenderer(root)

    def _gen_stile_ripartizione_piani(self, is_gb):
        """Stile per Ripartizione dei piani (fogli di mappa). circ154_allegato2
        cap.3.2 pag.13 + cap.3.12 pag.18: genere di linea "margine di piano",
        grigio 30% (C_TRAMA_30), spessore 10mm - un valore deliberatamente
        enorme rispetto a ogni altra linea del piano ("...allo scopo di
        permettere la sovrapposizione con tutte le altre linee", cap.3.12:
        usato SOLO per delimitare i piani isola, quando serve una banda che
        copra visivamente qualunque altra geometria sottostante)."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Ripartizione_piani")
        apply_rule(root, build_sym('fill', [make_fill(None, C_TRAMA_30, 10.0, "solid")]),
                   "", "Foglio di mappa")
        return QgsRuleBasedRenderer(root)

    def _gen_stile_zone_movimento(self, is_gb):
        """Stile per Zone di movimento - CMYK(0,29,90,0) = RGB(255,182,25) in PB-MU, solo tratteggio nero in GB"""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Zone_movimento")
        if is_gb:
            sym = build_sym('fill', [
                make_fill(None, C_NERO, 0.30, "solid"),
                make_hatch(C_NERO, w=0.20, d=3.0, a=45)
            ])
        else:
            sym = build_sym('fill', [
                make_fill(C_SPOSTAMENTO, C_SPOSTAMENTO, 0.30, "solid"),
                make_hatch(C_SPOSTAMENTO, w=0.20, d=3.0, a=45)
            ])
        apply_rule(root, sym, "", "Zona di movimento")
        return QgsRuleBasedRenderer(root)

    def _gen_stile_cap_localita(self, is_gb):
        """Stile per CAP e località"""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("CAP_localita")
        apply_rule(root, build_sym('fill', [make_fill(None, gbc(is_gb, QColor(0, 0, 200)), 0.20, "dash")]),
                   "", "CAP/Località")
        return QgsRuleBasedRenderer(root)

    def _gen_stile_margine_piano(self, is_gb, geom_type_name=""):
        """Stile per Margine del piano (elementi decorativi). Il topic raggruppa
        geometrie diverse (punti come Layout_del_piano/Crocetta_reticolo, linee
        come Linea_coordinate, poligoni come Superficie_disegno): serve un simbolo
        del tipo giusto per ciascuna, altrimenti un QgsLineSymbol su un layer
        punto/poligono non verrebbe disegnato affatto.
        Poligono e linea (il margine/bordo del piano vero e proprio, tema
        "Margine di piano" - vedi anche _gen_stile_ripartizione_piani, stesso
        genere di linea): grigio 30%, spessore 10mm (circ154_allegato2 cap.3.2
        pag.13). Il punto (Crocetta_reticolo, "Croce della rete") resta un
        simbolo diverso e separato, non coperto da questa voce."""
        root = QgsRuleBasedRenderer.Rule(None)
        root.setLabel("Margine_piano")
        gt = (geom_type_name or "").upper()
        if "POLYGON" in gt:
            sym = build_sym('fill', [make_fill(None, C_TRAMA_30, 10.0)])
        elif "POINT" in gt:
            sym = build_sym('point', [make_simple_marker("cross", 1.6, C_NERO, outline_w=0.25)])
        else:
            sym = build_sym('line', [make_line(C_TRAMA_30, 10.0)])
        apply_rule(root, sym, "", "Elemento margine")
        return QgsRuleBasedRenderer(root)

