"""Test per la logica di stile del plugin (non per l'interfaccia utente).

Copre le funzioni pure (genere_in, _zorder_priority) e due regressioni reali
trovate e corrette in questa sessione:
- apply_rule: un filtro vuoto deve produrre una regola ELSE (isElse=True),
  altrimenti il simbolo di fallback si disegna sopra ogni feature gia'
  gestita da un'altra regola (bug confermato con un render reale).
- _gen_stile_punto_di_confine: le regole giurisdizionali (che referenziano
  il campo "cippo_giurisdizionale") non devono comparire nel filtro quando
  il layer passato non ha quel campo (es. Punto_di_confine, a differenza
  di PCGiurisdizionale) - altrimenti QgsExpression genera un errore di
  valutazione e la regola non scatta mai (bug confermato con un render
  reale: il punto ricadeva sempre sul fallback "Punto generico").

Richiede l'ambiente Python di QGIS (importa qgis.core): va eseguito con
python-qgis.bat, non con un interprete Python generico, es.:
    "C:\\Program Files\\QGIS 4.2.0\\bin\\python-qgis.bat" test_style_logic.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qgis.core import QgsApplication, QgsVectorLayer, QgsUnitTypes

QgsApplication.setPrefixPath(os.environ.get("QGIS_PREFIX_PATH", ""), True)
_qgs = QgsApplication([], False)
_qgs.initQgis()

import tidashboard as cd


class TestGenereIn(unittest.TestCase):
    def test_singolo_valore_default_field(self):
        self.assertEqual(
            cd.genere_in(['vigna']),
            "(\"genere\" = 'vigna' OR \"genere\" LIKE '%.vigna')"
        )

    def test_piu_valori_campo_custom(self):
        expr = cd.genere_in(['tubo', 'palo_picchetto'], field='segno')
        self.assertEqual(
            expr,
            "(\"segno\" = 'tubo' OR \"segno\" LIKE '%.tubo' "
            "OR \"segno\" = 'palo_picchetto' OR \"segno\" LIKE '%.palo_picchetto')"
        )

    def test_match_esatto_e_suffisso_annidato(self):
        # Il dominio Materiale e' gerarchico: "campanile" reale in ili2db
        # puo' essere esportato come "altro.campanile" - l'espressione deve
        # accettare sia il valore esatto sia il suffisso puntato.
        from qgis.core import QgsExpression, QgsExpressionContext, QgsExpressionContextUtils
        expr_str = cd.genere_in(['campanile'], field='segno')
        for value, expected in (('campanile', True), ('altro.campanile', True), ('bullone', False)):
            fields = QgsVectorLayer("Point?field=segno:string", "t", "memory").fields()
            from qgis.core import QgsFeature
            feat = QgsFeature(fields)
            feat.setAttribute("segno", value)
            ctx = QgsExpressionContext()
            ctx.setFeature(feat)
            exp = QgsExpression(expr_str)
            self.assertEqual(bool(exp.evaluate(ctx)), expected, msg=f"value={value!r}")


class TestZOrderPriority(unittest.TestCase):
    def test_la_croce_della_rete_e_prima_di_tutto(self):
        """Nella versione in vigore del cap.1.5.4 (stato 1.2.2014) la croce
        della rete e' la PRIMA riga della tabella; nella versione marzo 2007
        era l'ultima. Prima non era nemmeno elencata e finiva nel ripiego,
        cioe' disegnata quasi in fondo."""
        self.assertEqual(cd._zorder_priority("margine_del_piano_crocetta_reticolo"), 0)
        self.assertEqual(cd._zorder_priority("confini_comunali_pcgiurisdizionale"), 1)

    def test_i_segni_di_superficie_degli_oggetti_singoli_sono_penultimi(self):
        """La modifica dichiarata dalla circolare federale MO 2014/01: i segni
        convenzionali di superficie degli "objets divers" spostati in
        penultima posizione, cioe' sotto la ripartizione dei piani e sopra la
        sola copertura del suolo."""
        os_sup = cd._zorder_priority("oggetti_singoli_elemento_con_superficie")
        cs = cd._zorder_priority("copertura_dl_solo_superficiecs")
        ripartizione = cd._zorder_priority("ripartizin_d_pani_geometria_piano")
        os_linee = cd._zorder_priority("oggetti_singoli_elemento_lineare")
        self.assertLess(ripartizione, os_sup, "la ripartizione dei piani va sopra")
        self.assertLess(os_sup, cs, "la copertura del suolo resta l'ultima")
        self.assertLess(os_linee, ripartizione,
                        "le linee degli oggetti singoli restano nel loro blocco, in alto")

    def test_nessuna_voce_ne_intercetta_un_altra_per_sottostringa(self):
        """_zorder_priority sceglie la prima voce CONTENUTA nel nome tabella:
        due voci in cui una e' sottostringa dell'altra si ruberebbero il
        posto a seconda dell'ordine."""
        seq = cd.GEOS_ZORDER_SEQUENCE
        for i, voce in enumerate(seq):
            for j, altra in enumerate(seq):
                if i < j and voce in altra:
                    self.fail("'%s' (indice %d) intercetta '%s' (indice %d)"
                              % (voce, i, altra, j))

    def test_punto_di_confine_prima_di_bene_immobile(self):
        # Regressione concettuale: i punti di confine devono restare in
        # primo piano rispetto al confine di proprieta' (indice piu' basso
        # = disegnato sopra, vedi setCustomLayerOrder/_zorder_priority).
        p_confine = cd._zorder_priority("beni_immobili_punto_di_confine")
        p_bene_immobile = cd._zorder_priority("beni_immobili_bene_immobile")
        self.assertLess(p_confine, p_bene_immobile)

    def test_fallback_su_tabella_sconosciuta(self):
        base = len(cd.GEOS_ZORDER_SEQUENCE) + len(cd.Z_ORDER_TIERS)
        self.assertEqual(cd._zorder_priority("tabella_totalmente_sconosciuta_xyz"), base)

    def test_fallback_tier_punto_singolo(self):
        base = len(cd.GEOS_ZORDER_SEQUENCE)
        self.assertEqual(cd._zorder_priority("qualcosa_punto_singolo_xyz"), base + 0)


class TestApplyRuleIsElse(unittest.TestCase):
    """Regressione: apply_rule con filt="" deve produrre isElse=True."""

    def test_filtro_vuoto_diventa_else(self):
        from qgis.core import QgsRuleBasedRenderer
        root = QgsRuleBasedRenderer.Rule(None)
        cd.apply_rule(root, None, "", "Fallback")
        r = root.children()[0]
        self.assertTrue(r.isElse())

    def test_filtro_non_vuoto_non_diventa_else(self):
        from qgis.core import QgsRuleBasedRenderer
        root = QgsRuleBasedRenderer.Rule(None)
        cd.apply_rule(root, None, '"segno" = \'termine_cippo\'', "Specifica")
        r = root.children()[0]
        self.assertFalse(r.isElse())


class TestPuntoDiConfineFieldGuard(unittest.TestCase):
    """Regressione: niente riferimenti a un campo assente dal layer."""

    def test_layer_senza_campo_giurisdizionale(self):
        layer = QgsVectorLayer("Point?field=segno:string", "punto_di_confine", "memory")
        renderer = cd.TIDashboardDialog._gen_stile_punto_di_confine(
            cd.TIDashboardDialog.__new__(cd.TIDashboardDialog), is_gb=True, layer=layer)
        root = renderer.rootRule()
        labels = [c.label() for c in root.children()]
        # Le regole giurisdizionali (P/Q/R/N) non devono comparire affatto.
        self.assertNotIn("Termine giurisdizionale rilevante", labels)
        for child in root.children():
            self.assertNotIn("cippo_giurisdizionale", child.filterExpression())

    def test_layer_con_campo_giurisdizionale(self):
        layer = QgsVectorLayer(
            "Point?field=segno:string&field=cippo_giurisdizionale:string",
            "pcgiurisdizionale", "memory")
        renderer = cd.TIDashboardDialog._gen_stile_punto_di_confine(
            cd.TIDashboardDialog.__new__(cd.TIDashboardDialog), is_gb=True, layer=layer)
        root = renderer.rootRule()
        labels = [c.label() for c in root.children()]
        self.assertIn("Termine giurisdizionale rilevante", labels)
        termine_rule = next(c for c in root.children() if c.label() == "Termine")
        self.assertIn("cippo_giurisdizionale", termine_rule.filterExpression())


class _Stili(cd.StiliMixin):
    """Gli stili stanno tutti in un mixin, quindi si possono provare senza
    costruire la finestra. Un TIDashboardDialog creato con __new__ non ha la
    coda di righe della console, e _get_renderer_for_table logga: assegnargli
    un log finto non basta, perche' su un QDialog mai inizializzato anche il
    solo hasattr solleva RuntimeError."""

    def log(self, *a, **k):
        pass


def _dlg():
    return _Stili()


def _renderer(class_name, t_low, geom="Point", layer=None, mode="gb"):
    return _Stili()._get_renderer_for_table(class_name, t_low, mode, geom, layer)


class TestOrientamentoPuntoDiConfine(unittest.TestCase):
    """L'orientamento del simbolo sta in SimboloPunto_di_confine, che non ha
    geometria: arriva qui come campo unito. Sui dati reali di Chiasso 5637
    punti su 67919 ne portano uno non nullo, e prima erano tutti dritti."""

    def test_senza_il_campo_nessuna_rotazione(self):
        layer = QgsVectorLayer("Point?field=segno:string", "pdc", "memory")
        r = _dlg()._gen_stile_punto_di_confine(True, layer)
        for regola in r.rootRule().children():
            sym = regola.symbol()
            if sym is not None:
                self.assertFalse(sym.dataDefinedAngle().isActive())

    def test_col_campo_tutte_le_regole_ruotano(self):
        layer = QgsVectorLayer(
            "Point?field=segno:string&field=%s:double" % cd.CAMPO_ORI_SIMBOLO,
            "pdc", "memory")
        r = _dlg()._gen_stile_punto_di_confine(True, layer)
        figlie = [c for c in r.rootRule().children() if c.symbol() is not None]
        self.assertTrue(figlie)
        for regola in figlie:
            prop = regola.symbol().dataDefinedAngle()
            self.assertTrue(prop.isActive(), regola.label())
            # gon -> gradi, senza offset: convenzione gia' verificata per
            # SimboloSuperficieCS (setDataDefinedAngle ruota in senso orario
            # da un glifo gia' orientato a nord, come "Ori").
            self.assertIn("0.9", prop.expressionString())
            self.assertIn(cd.CAMPO_ORI_SIMBOLO, prop.expressionString())


class TestTabelleSimbolo(unittest.TestCase):
    """Le undici tabelle Simbolo* del modello non sono un gruppo omogeneo:
    ognuna deve avere una destinazione motivata, non un fallback unico."""

    def test_simbolo_su_superficie_cs(self):
        r = _renderer("SimboloSuperficieCS", "copertura_dl_solo_simbolosuperficiecs")
        self.assertEqual(r.rootRule().label(), "SimboloSuperficieCS")

    def test_la_variante_in_progetto_resta_fuori_dal_piano(self):
        """SimboloSuperficieCSProg finisce nel ramo "oggetti in progetto",
        che il cap.1.5.3 esclude dal contenuto del piano: e' corretto che non
        arrivi affatto al ramo dei simboli."""
        r = _renderer("SimboloSuperficieCSProg", "copertura_dl_solo_simbolosuperficiecsprog")
        self.assertEqual(r.rootRule().label(), "Invisibile")

    def test_layout_del_piano_non_va_sul_foglio(self):
        """Genere_simbolo = (freccia_nord, altro): e' la freccia nord di
        impaginazione. Il cartiglio ne disegna gia' una, agganciata alla
        rotazione della mappa."""
        r = _renderer("SimboloLayout_del_piano", "margine_del_piano_simbololayout_del_piano")
        self.assertEqual(r.rootRule().label(), "Invisibile")

    def test_punto_fisso_ausiliario_non_va_sul_piano_rf(self):
        """Il modello lo dice sul padre: "Non sono rappresentati nel piano
        per il registro fondiario"."""
        r = _renderer("SimboloPto_fisso_ausil", "punti_fissctgria3_simbolopto_fisso_ausil")
        self.assertEqual(r.rootRule().label(), "Invisibile")

    def test_tabelle_di_solo_orientamento(self):
        """Senza geometria non c'e' nulla da disegnare: il loro Ori viene
        usato sul padre."""
        for t in ("beni_immobili_simbolopunto_di_confine",
                  "confini_comunali_simbolopcgiurisdizionale",
                  "punti_fissctgria1_simbolopfp1"):
            r = _renderer("SimboloX", t, geom="Point")
            self.assertEqual(r.rootRule().label(), "Invisibile", t)


class TestSimboloSuOggettoSingolo(unittest.TestCase):
    """Sui dati reali di Chiasso i 102 simboli su elemento lineare stanno
    tutti su acque correnti (101 ruscello, 1 acqua sotterranea canalizzata):
    sono frecce di direzione della corrente, e prima erano invisibili."""

    def test_il_genere_si_cerca_a_due_salti(self):
        layer = QgsVectorLayer(
            "Point?field=ori:double&field=el_genere_di_linea:string"
            "&field=el_os_genere:string", "sim", "memory")
        self.assertEqual(
            _Stili._campo_genere_del_padre(layer), "el_os_genere")

    def test_genere_di_linea_non_viene_scambiato_per_il_genere(self):
        """Elemento_lineare ha "Genere_di_linea" (facciata_chiusa,
        parte_interrata, parte_sporgente), che e' un'altra cosa: un controllo
        ingenuo sul suffisso "genere" lo prenderebbe."""
        layer = QgsVectorLayer(
            "Point?field=ori:double&field=el_genere_di_linea:string", "sim", "memory")
        self.assertIsNone(_Stili._campo_genere_del_padre(layer))

    def test_freccia_della_corrente_orientata(self):
        layer = QgsVectorLayer(
            "Point?field=ori:double&field=el_os_genere:string", "sim", "memory")
        r = _renderer("SimboloElemento_lineare",
                      "oggetti_singoli_simboloelemento_lineare", layer=layer)
        figlie = r.rootRule().children()
        self.assertEqual([c.label() for c in figlie], ["Direzione della corrente"])
        prop = figlie[0].symbol().dataDefinedAngle()
        self.assertTrue(prop.isActive())
        self.assertIn("ruscello", figlie[0].filterExpression())

    def test_senza_il_genere_non_si_disegna_una_freccia_a_caso(self):
        layer = QgsVectorLayer("Point?field=ori:double", "sim", "memory")
        r = _renderer("SimboloElemento_lineare",
                      "oggetti_singoli_simboloelemento_lineare", layer=layer)
        self.assertEqual(r.rootRule().label(), "Invisibile")


class TestFindLabelField(unittest.TestCase):
    """_find_label_field: campo diretto, campo rinominato da un join
    ("{tabella_padre}_{campo}"), case-insensitivity, nessun match."""

    def test_campo_diretto_case_insensitive(self):
        layer = QgsVectorLayer("Point?field=Numero:string", "t", "memory")
        self.assertEqual(
            cd.TIDashboardDialog._find_label_field(layer, ("Numero",)), "Numero")

    def test_campo_rinominato_da_join_suffisso(self):
        # setup_relations_and_joins rinomina i campi ereditati "{padre}_{campo}"
        # dopo il join (es. "entrata_edificio_numero_casa").
        layer = QgsVectorLayer(
            "Point?field=entrata_edificio_numero_casa:string", "t", "memory")
        self.assertEqual(
            cd.TIDashboardDialog._find_label_field(layer, ("Numero_casa",)),
            "entrata_edificio_numero_casa")

    def test_primo_candidato_prioritario(self):
        layer = QgsVectorLayer(
            "Point?field=nome:string&field=numero:string", "t", "memory")
        self.assertEqual(
            cd.TIDashboardDialog._find_label_field(layer, ("Numero", "Nome")), "numero")

    def test_nessun_campo_trovato(self):
        layer = QgsVectorLayer("Point?field=altro:string", "t", "memory")
        self.assertIsNone(cd.TIDashboardDialog._find_label_field(layer, ("Numero",)))


class _FakeTextEdit:
    """Sostituisce QTextEdit (self.txt_log) senza servire una QDialog completa:
    _apply_labels_to_layer/_apply_pos_text_attrs chiamano solo self.log().

    log() non usa piu' append() ma il cursore + insertPlainText, perche'
    append() interpretava il testo come HTML e in console finiscono anche
    stringhe che vengono dai dati: il finto widget imita quel giro."""
    def __init__(self):
        self.lines = []

    def textCursor(self):
        return _FakeCursor(self)

    def setTextCursor(self, _cursore):
        pass

    def ensureCursorVisible(self):
        pass

    def clear(self):
        self.lines = []


class _FakeCursor:
    """Il cursore reale ora porta anche il formato del carattere: log()
    colora le righe secondo la gravita'."""
    def __init__(self, testo):
        self._testo = testo

    def movePosition(self, _dove):
        pass

    def setCharFormat(self, _formato):
        pass

    def insertText(self, msg):
        self._testo.lines.append(msg.rstrip("\n"))


class _FakeSpunta:
    """Sostituisce le due spunte/etichette che log() consulta."""
    def isChecked(self):
        return False

    def setText(self, _testo):
        pass


def make_dialog_stub():
    d = cd.TIDashboardDialog.__new__(cd.TIDashboardDialog)
    d.txt_log = _FakeTextEdit()
    # log() ora tiene lo storico delle righe (per il filtro "solo avvisi ed
    # errori") e aggiorna il conteggio: lo stub deve fornire entrambi.
    d._righe_log = []
    d.chk_solo_problemi = _FakeSpunta()
    d.lbl_conteggio_log = _FakeSpunta()
    return d


class TestApplyLabelsToLayer(unittest.TestCase):
    """_apply_labels_to_layer: dispatch su TEXT_LABEL_RULES/punto_quotato,
    stile (grassetto/corsivo/dimensione) e gestione del campo mancante."""

    def test_punto_quotato_usa_espressione_z(self):
        layer = QgsVectorLayer("Point", "t", "memory")
        d = make_dialog_stub()
        d._apply_labels_to_layer(layer, "altimetria_punto_quotato", "Punto_quotato", is_gb=True)
        settings = layer.labeling().settings()
        self.assertEqual(settings.fieldName, "round($z, 2)")
        self.assertTrue(settings.isExpression)
        self.assertTrue(layer.labelsEnabled())

    def test_posfondo_grassetto_non_corsivo(self):
        # TEXT_LABEL_RULES: ("posfondo", ("Numero",), True, False, 2.5)
        layer = QgsVectorLayer("Point?field=numero:string", "t", "memory")
        d = make_dialog_stub()
        d._apply_labels_to_layer(layer, "beni_immobili_posfondo", "PosFondo", is_gb=True)
        settings = layer.labeling().settings()
        self.assertEqual(settings.fieldName, "numero")
        self.assertFalse(settings.isExpression)
        font = settings.format().font()
        self.assertTrue(font.bold())
        self.assertFalse(font.italic())
        # Dal passaggio alle grandezze normative (circ154_allegato2 cap.5.8:
        # numero_immobile 2.5mm di ALTEZZA MAIUSCOLA) la dimensione non e' piu'
        # in punti ma in millimetri di font, ricavata dall'altezza maiuscola
        # tramite _CAP_HEIGHT_RATIO.
        self.assertEqual(settings.format().sizeUnit(), QgsUnitTypes.RenderMillimeters)
        self.assertAlmostEqual(settings.format().size() * cd._CAP_HEIGHT_RATIO, 2.5, places=6)

    def test_posnumero_os_corsivo_non_grassetto(self):
        # TEXT_LABEL_RULES: ("posnumero_os", ("Numero",), False, True, 8)
        layer = QgsVectorLayer("Point?field=numero:string", "t", "memory")
        d = make_dialog_stub()
        d._apply_labels_to_layer(layer, "oggetti_singoli_posnumero_os", "PosNumero_OS", is_gb=True)
        font = layer.labeling().settings().format().font()
        self.assertFalse(font.bold())
        self.assertTrue(font.italic())

    def test_campo_mancante_logga_avviso_senza_eccezioni(self):
        # Nessuno dei campi candidati ("Numero") presente: deve loggare un
        # avviso e uscire, non lanciare un'eccezione ne' abilitare etichette.
        layer = QgsVectorLayer("Point?field=altro:string", "t", "memory")
        d = make_dialog_stub()
        d._apply_labels_to_layer(layer, "beni_immobili_posfondo", "PosFondo", is_gb=True)
        self.assertTrue(any("⚠️" in line for line in d.txt_log.lines))
        self.assertIsNone(layer.labeling())

    def test_posnome_localizzazione_usa_substr_indici(self):
        # Unico caso con Indice_iniziale/Indice_finale (sottostringa di Testo).
        layer = QgsVectorLayer(
            "Point?field=testo:string&field=indice_iniziale:int&field=indice_finale:int",
            "t", "memory")
        d = make_dialog_stub()
        d._apply_labels_to_layer(
            layer, "indirizzi_posnome_localizzazione", "PosNome_localizzazione", is_gb=True)
        settings = layer.labeling().settings()
        self.assertTrue(settings.isExpression)
        self.assertIn("substr(\"testo\"", settings.fieldName)
        self.assertIn("indice_iniziale", settings.fieldName)
        self.assertIn("indice_finale", settings.fieldName)

    def test_posnome_localizzazione_senza_indici_usa_campo_diretto(self):
        # Senza i campi indice sul layer, deve ricadere sul campo intero.
        layer = QgsVectorLayer("Point?field=testo:string", "t", "memory")
        d = make_dialog_stub()
        d._apply_labels_to_layer(
            layer, "indirizzi_posnome_localizzazione", "PosNome_localizzazione", is_gb=True)
        settings = layer.labeling().settings()
        self.assertFalse(settings.isExpression)
        self.assertEqual(settings.fieldName, "testo")

    def test_nessuna_regola_corrispondente_non_lancia_eccezioni(self):
        layer = QgsVectorLayer("Point?field=altro:string", "t", "memory")
        d = make_dialog_stub()
        d._apply_labels_to_layer(layer, "tabella_sconosciuta_xyz", "Sconosciuta", is_gb=True)
        self.assertIsNone(layer.labeling())


class TestExtractLv95Coords(unittest.TestCase):
    """_extract_lv95_coords: euristica per i messaggi di errore dell'analisi
    duplicati - accetta solo coppie di float ADIACENTI sulla stessa riga,
    nell'ordine (E, N), con E in [2480000, 2840000] e N in [1070000, 1310000].
    Funzione pura (staticmethod), testabile senza layer QGIS."""

    def _extract(self, line):
        return cd.TIDashboardDialog._extract_lv95_coords(line)

    def test_coppia_valida_stessa_riga(self):
        line = "OBJE 46560 2600123.456 1123456.789 500.0"
        self.assertEqual(self._extract(line), (2600123.456, 1123456.789))

    def test_coppia_valida_non_all_inizio(self):
        # Testo/valori prima della coppia coordinata: la prima coppia
        # adiacente che rispetta i range vince.
        line = "OBJE 40497 500.5 2555000.0 1200000.0 42.0"
        self.assertEqual(self._extract(line), (2555000.0, 1200000.0))

    def test_n_ordine_invertito_non_accettato(self):
        # (N, E) invece di (E, N): nessuna coppia adiacente rispetta i range.
        line = "OBJE 1 1123456.789 2600123.456"
        self.assertIsNone(self._extract(line))

    def test_fuori_range_nazionale(self):
        # LV03-style o fuori Svizzera: rifiutati dai range stretti.
        self.assertIsNone(self._extract("OBJE 1 600123.456 223456.789"))
        self.assertIsNone(self._extract("OBJE 1 2900000.0 1400000.0"))

    def test_valori_isolati_non_adiacenti(self):
        # E e N presenti ma non come coppia adiacente (es. quota in mezzo):
        # la vecchia euristica li avrebbe accettati.
        line = "OBJE 1 2600123.456 500.0 1123456.789"
        self.assertIsNone(self._extract(line))

    def test_nessun_float(self):
        self.assertIsNone(self._extract("OBJE 46560"))
        self.assertIsNone(self._extract(""))


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2)
    _qgs.exitQgis()
    sys.exit(0 if result.result.wasSuccessful() else 1)
