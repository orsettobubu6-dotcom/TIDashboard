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
from etichette import _LABEL_PRIORITY


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
        seq = cd.ORDINE_PRIORITA
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
        base = len(cd.ORDINE_PRIORITA) + len(cd.Z_ORDER_TIERS)
        self.assertEqual(cd._zorder_priority("tabella_totalmente_sconosciuta_xyz"), base)

    def test_fallback_tier_punto_singolo(self):
        base = len(cd.ORDINE_PRIORITA)
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


class TestPuntiDiAppoggioNonRappresentati(unittest.TestCase):
    """Punto_singolo e Punto_fisso_ausiliario non si disegnano sul piano.

    Prima prendevano un cerchio nero pieno di 0.6 mm - un simbolo inventato,
    perché il catalogo non ne documenta uno. Sul comune di prova erano 33 487
    pallini, e i 22 251 punti singoli della copertura del suolo stanno per
    definizione SULLE linee di copertura: sul foglio sembravano linee che
    passano sopra i punti di confine."""

    def _renderer(self, nome_tabella):
        # make_dialog_stub e' definito piu' in basso nel file: in Python il
        # nome si risolve alla chiamata, non alla definizione della classe.
        layer = QgsVectorLayer("Point?crs=EPSG:2056&field=segno:string", nome_tabella, "memory")
        return make_dialog_stub()._get_renderer_for_table(
            nome_tabella, nome_tabella.lower(), "gb", "POINT", layer)

    def _disegna_qualcosa(self, renderer):
        """True se almeno una regola lascia un segno sulla carta.

        Non basta guardare enabled(): lo stile "invisibile" del plugin e' un
        simbolo REGOLARE con colore a trasparenza zero (vedi
        _gen_stile_invisibile), quindi i suoi livelli risultano abilitati.
        Quello che conta e' se ha colore."""
        for regola in renderer.rootRule().children():
            simbolo = regola.symbol()
            if simbolo is None:
                continue
            for i in range(simbolo.symbolLayerCount()):
                livello = simbolo.symbolLayer(i)
                if not livello.enabled():
                    continue
                if livello.color().alpha() > 0 or livello.strokeColor().alpha() > 0:
                    return True
        return False

    def test_punto_singolo_della_copertura_non_si_vede(self):
        self.assertFalse(self._disegna_qualcosa(
            self._renderer("copertura_dl_solo_punto_singolo")))

    def test_punto_singolo_degli_oggetti_singoli_non_si_vede(self):
        self.assertFalse(self._disegna_qualcosa(
            self._renderer("oggetti_singoli_punto_singolo")))

    def test_punto_fisso_ausiliario_non_si_vede(self):
        self.assertFalse(self._disegna_qualcosa(
            self._renderer("punti_fissctgria3_punto_fisso_ausiliario")))

    def test_il_punto_di_confine_invece_si_vede(self):
        # La controprova: la modifica non deve aver spento anche i punti che
        # il piano DEVE mostrare.
        self.assertTrue(self._disegna_qualcosa(
            self._renderer("beni_immobili_punto_di_confine")))

    def test_il_simbolo_inventato_non_esiste_piu(self):
        # Se torna, torna anche il difetto: era l'unico cerchio nero pieno.
        self.assertFalse(hasattr(cd.TIDashboardDialog, "_gen_stile_punto_generico"))


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

    def _priorita_di(self, tabella, campo="numero:string"):
        layer = QgsVectorLayer("Point?field=%s" % campo, "t", "memory")
        make_dialog_stub()._apply_labels_to_layer(layer, tabella, "X", is_gb=True)
        return layer.labeling().settings()

    def test_priorita_numero_di_fondo_maggiore_del_numero_di_punto(self):
        # In caso di sovrapposizione deve cedere il numero del punto di
        # confine, che il piano RF non rappresenta nemmeno (cap.5.10), non il
        # numero di fondo, che e' l'orientamento di chi legge.
        fondo = self._priorita_di("beni_immobili_posfondo")
        punto = self._priorita_di("beni_immobili_pospunto_di_confine",
                                  campo="identificatore:string")
        self.assertGreater(fondo.priority, punto.priority)

    def test_priorita_giurisdizionale_e_la_massima(self):
        giur = self._priorita_di("confini_comunali_pospcgiurisdizionale",
                                 campo="identificatore:string")
        self.assertEqual(giur.priority, 10)

    def test_ogni_etichetta_e_anche_ostacolo(self):
        # Se una scritta non fa da ostacolo, le altre le si posano sopra e la
        # priorita' non serve a niente.
        settings = self._priorita_di("beni_immobili_posfondo")
        self.assertTrue(settings.obstacleSettings().isObstacle())

    def test_priorita_dichiarate_nel_range_di_qgis(self):
        # QGIS accetta 0..10; un valore fuori scala verrebbe troncato in
        # silenzio e l'ordine dichiarato non sarebbe quello applicato.
        for chiave, valore in _LABEL_PRIORITY.items():
            self.assertTrue(0 <= valore <= 10, "%s = %s" % (chiave, valore))

    def test_ogni_regola_di_etichetta_ha_una_priorita(self):
        # Una regola senza priorita' ricadrebbe sul default 5, cioe' si
        # troverebbe in mezzo alla scala senza che nessuno l'abbia deciso.
        for chiave, _, _, _, _ in cd.TEXT_LABEL_RULES:
            self.assertIn(chiave, _LABEL_PRIORITY, "manca la priorita' di '%s'" % chiave)


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


class TestGrandezzaDeiSimboliDisegnati(unittest.TestCase):
    """Il simbolo che finisce sulla carta misura quello che la norma chiede?

    Non si controlla una costante contro un'altra costante: si DISEGNA il
    simbolo su un'immagine a DPI noto e si conta l'inchiostro. E' l'unico modo
    in cui l'errore che questo test presidia si sarebbe visto - la tabella
    _FONT_INK_FRACTION era coerente con se stessa e sbagliata di 4/3, perche'
    misurata attraverso la conversione punti->pixel di Qt (96 dpi contro i 72
    della definizione tipografica). Ogni simbolo usciva al 75% della misura
    prescritta dal cap. 2 e nessun confronto fra costanti poteva accorgersene.

    Il banco di prova e' tarato sul caso semplice: un cerchio di dimensione
    dichiarata deve misurare quella dimensione. Se sbagliasse li', il resto
    non proverebbe niente."""

    DPI = 600.0
    LATO = 700
    # (tasto, mm prescritti dal cap. 2.2/2.3)
    CASI = (("A", 3.2), ("B", 3.6), ("E", 1.4), ("H", 2.4), ("N", 3.4),
            ("f", 4.5), ("n", 5.0), ("a", 6.0))
    TOLLERANZA = 0.06        # 6%: antialiasing e differenza contorno/inchiostro

    def _ink_mm(self, livelli):
        from qgis.core import QgsMarkerSymbol, QgsRenderContext
        from qgis.PyQt.QtGui import QImage, QPainter, QColor
        from qgis.PyQt.QtCore import QPointF
        sym = QgsMarkerSymbol(livelli)
        img = QImage(self.LATO, self.LATO, QImage.Format.Format_ARGB32)
        punti_per_metro = int(self.DPI / 25.4 * 1000)
        img.setDotsPerMeterX(punti_per_metro)
        img.setDotsPerMeterY(punti_per_metro)
        img.fill(QColor(255, 255, 255))
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        ctx = QgsRenderContext.fromQPainter(p)
        sym.startRender(ctx)
        sym.renderPoint(QPointF(self.LATO / 2.0, self.LATO / 2.0), None, ctx)
        sym.stopRender(ctx)
        p.end()
        xs, ys = [], []
        for y in range(self.LATO):
            for x in range(self.LATO):
                c = img.pixelColor(x, y)
                if c.red() < 200 or c.green() < 200 or c.blue() < 200:
                    xs.append(x)
                    ys.append(y)
        if not xs:
            return None
        k = ctx.scaleFactor()
        return max((max(xs) - min(xs) + 1) / k, (max(ys) - min(ys) + 1) / k)

    def test_il_banco_di_prova_misura_giusto_un_cerchio(self):
        from qgis.core import QgsSimpleMarkerSymbolLayer, QgsUnitTypes
        for mm in (0.8, 3.2):
            l = QgsSimpleMarkerSymbolLayer.create(
                {"name": "circle", "size": str(mm), "color": "0,0,0,255",
                 "outline_style": "no"})
            l.setSizeUnit(QgsUnitTypes.RenderUnit.RenderMillimeters)
            reso = self._ink_mm([l])
            self.assertAlmostEqual(reso / mm, 1.0, delta=self.TOLLERANZA,
                                   msg="il banco sbaglia sul cerchio da %.1f mm "
                                       "(reso %.3f): la misura sui simboli non "
                                       "proverebbe niente" % (mm, reso))

    def test_ogni_simbolo_misura_quello_che_la_norma_chiede(self):
        from simbologia import (make_true_font_marker_with_mask,
                                _ensure_cadastra_text_font_loaded)
        _ensure_cadastra_text_font_loaded()
        for tasto, mm in self.CASI:
            # solo il livello REGOLARE: la maschera e' piu' grande apposta
            # (alone) e misurerebbe il contorno bianco, non il segno.
            livelli = make_true_font_marker_with_mask(tasto, sz=mm)[-1:]
            reso = self._ink_mm(livelli)
            self.assertIsNotNone(reso, "il tasto %r non ha disegnato nulla" % tasto)
            self.assertAlmostEqual(
                reso / mm, 1.0, delta=self.TOLLERANZA,
                msg="tasto %r: la norma chiede %.2f mm, ne misura %.3f (%+.1f%%)"
                    % (tasto, mm, reso, (reso - mm) / mm * 100))


class TestGrandezzeDelCapitolo5(unittest.TestCase):
    """Le grandezze delle scritture contro il testo dell'istruzione.

    Non e' un test tautologico che ricopia il codice: i valori qui sotto sono
    TRASCRITTI DALLE TABELLE del cap.5 (Rappresentazione del piano per il
    registro fondiario, stato 1.2.2014), tema per tema. Due erano sbagliati e
    lo si e' scoperto solo rileggendo il testo:
      - numero_di_edificio stava a 1.5 invece di 1.8 (cap.5.5);
      - nome_oggetto degli Oggetti singoli stava a 2.2 invece di 2.5 (cap.5.6);
        il 2.2 e' di un'altra tabella - cap.5.9, elemento_condotta - e nella
        trascrizione era migrato fra due tabelle della stessa pagina.
    Da qui in avanti uno scivolamento del genere fa fallire un test."""

    # (sottostringa della regola, mm, grassetto, corsivo, capitolo)
    NORMA = (
        ("posnumero_di_edificio",           1.8, False, True,  "5.5 numero_di_edificio"),
        ("posnome_oggetto",                 2.5, False, True,  "5.5 nome_oggetto"),
        ("posnumero_oggetto",               1.8, False, True,  "5.6 numero_oggetto"),
        ("oggetti_singoli_posnome_oggetto", 2.5, False, True,  "5.6 nome_oggetto"),
        ("nome_locale",                     4.5, False, True,  "5.7 nome_locale"),
        ("nome_di_localita",                4.5, True,  False, "5.7 nome_di_localita"),
        ("nome_del_luogo",                  4.5, False, False, "5.7 nome di luogo"),
        ("posfondo",                        2.5, True,  False, "5.8 numero_immobile"),
        ("posnome_localizzazione",          3.0, False, True,  "5.12 nome_localizzazione"),
        ("posnumero_casa",                  1.8, False, False, "5.12 numero_casa"),
        ("posnome_edificio",                1.8, False, False, "5.12 Nome_edificio"),
        ("posnome_localita",                4.5, True,  False, "5.12 Nome_localita"),
    )

    def test_ogni_grandezza_corrisponde_alla_tabella_della_norma(self):
        from etichette import TEXT_LABEL_RULES
        regole = {r[0]: r for r in TEXT_LABEL_RULES}
        for chiave, mm, grassetto, corsivo, capitolo in self.NORMA:
            self.assertIn(chiave, regole, "regola sparita: %s" % chiave)
            _k, _campi, g, c, dim = regole[chiave]
            self.assertAlmostEqual(dim, mm, places=3,
                                   msg="%s: cap.%s prescrive %.1f mm, noi %.1f"
                                       % (chiave, capitolo, mm, dim))
            self.assertEqual((g, c), (grassetto, corsivo),
                             "%s: stile diverso da quello del cap.%s"
                             % (chiave, capitolo))

    def test_il_2_2_delle_condotte_non_e_finito_sugli_oggetti_singoli(self):
        """Il valore 2.2 del cap.5.9 (elemento_condotta) non deve comparire
        sulle scritture di Copertura del suolo o Oggetti singoli: e' li' che
        era migrato."""
        from etichette import TEXT_LABEL_RULES
        for chiave, _campi, _g, _c, dim in TEXT_LABEL_RULES:
            if "nome_oggetto" in chiave:
                self.assertNotAlmostEqual(
                    dim, 2.2, places=3,
                    msg="%s ha la grandezza delle condotte" % chiave)


class TestLineeDellaCoperturaDelSuolo(unittest.TestCase):
    """Le linee perimetrali della Copertura del suolo (cap. 3.3).

    Il capitolo dice tre cose: lo spessore e' 0.20 mm per TUTTO il tema, il
    contorno e' "continuo o interrotto1" a seconda del genere, e l'interrotto1
    (1.5 / 0.5) si usa SOLO qui.

    IL DIFETTO CHE QUESTO TEST PRESIDIA: in un QgsRuleBasedRenderer senza
    regola di ripiego, una feature che non combacia con nessun filtro non
    viene disegnata affatto. "spartitraffico" non aveva alcuna regola e i suoi
    132 poligoni sparivano dal piano di Mendrisio in silenzio - nessun errore,
    nessun avviso, semplicemente non c'erano. Non lo si trova guardando le
    regole che ci sono: lo si trova passando tutto il dominio."""

    # I valori VERI del dominio Genere_CS di MD01MUTI7MN95, con il tipo di
    # linea prescritto dal cap. 3.3.
    DOMINIO = (
        ("edificio", "continuo"),
        ("rivestimento_duro.strada_sentiero.nazionale", "continuo"),
        ("rivestimento_duro.strada_sentiero.cantonale", "continuo"),
        ("rivestimento_duro.strada_sentiero.comunale", "continuo"),
        ("rivestimento_duro.strada_sentiero.altra_strada", "continuo"),
        # sotto-genere con linea propria per circ154_allegato4
        ("rivestimento_duro.strada_sentiero.sentiero", "interrotto1"),
        ("rivestimento_duro.marciapiede", "continuo"),
        ("rivestimento_duro.spartitraffico", "continuo"),
        ("rivestimento_duro.ferrovia", "interrotto1"),
        ("rivestimento_duro.aeroporto", "continuo"),
        ("rivestimento_duro.bacino_idrico.piscina", "continuo"),
        ("rivestimento_duro.bacino_idrico.altro_bacino_idrico", "continuo"),
        ("rivestimento_duro.altro_rivestimento_duro", "interrotto1"),
        ("humus.campo_prato_pascolo", "interrotto1"),
        ("humus.coltura_intensiva.vigna", "interrotto1"),
        ("humus.coltura_intensiva.altra_coltura_intensiva", "interrotto1"),
        ("humus.giardino", "interrotto1"),
        ("humus.torbiera", "interrotto1"),
        ("humus.altro_humus", "interrotto1"),
        ("acque.specchio_acqua", "continuo"),
        ("acque.corso_acqua.fiume", "continuo"),
        ("acque.corso_acqua.torrente", "continuo"),
        ("acque.corso_acqua.canale", "continuo"),
        ("acque.canneti", "interrotto1"),
        ("bosco.bosco_fitto", "interrotto1"),
        ("bosco.pascolo_boscato.pascolo_boscato_fitto", "interrotto1"),
        ("bosco.pascolo_boscato.pascolo_boscato_rado", "interrotto1"),
        ("bosco.altro_bosco", "interrotto1"),
        ("senza_vegetazione.roccia", "interrotto1"),
        ("senza_vegetazione.ghiacciaio_nevaio", "interrotto1"),
        ("senza_vegetazione.pietraia_sabbia", "interrotto1"),
        ("senza_vegetazione.cava_di_ghiaia_discarica", "interrotto1"),
        ("senza_vegetazione.altra_senza_vegetazione", "interrotto1"),
    )

    def _renderer(self):
        layer = QgsVectorLayer(
            "Polygon?crs=EPSG:2056&field=genere:string",
            "copertura_dl_solo_superficiecs", "memory")
        return make_dialog_stub()._get_renderer_for_table(
            "SuperficieCS", "copertura_dl_solo_superficiecs", "gb",
            "POLYGON", layer), layer

    def _contorno(self, sym, prof=0):
        """(spessore, tratteggio) del contorno, scendendo nei sotto-simboli:
        con il bordo tratteggiato il contorno e' una linea vera DENTRO il
        simbolo di riempimento, non la cornice del riempimento."""
        larg = tratto = None
        if sym is None or prof > 4:
            return larg, tratto
        for i in range(sym.symbolLayerCount()):
            sl = sym.symbolLayer(i)
            tipo = sl.layerType()
            if tipo == "SimpleLine":
                if sl.width() and sl.width() > 0 and larg is None:
                    larg = sl.width()
                v = sl.customDashVector()
                if sl.useCustomDashPattern() and v:
                    tratto = ";".join("%.2f" % x for x in v)
                elif tratto is None:
                    tratto = "continuo"
            elif tipo == "SimpleFill":
                if sl.strokeWidth() and sl.strokeWidth() > 0 and larg is None:
                    larg = sl.strokeWidth()
                    tratto = tratto or "continuo"
            sub = getattr(sl, "subSymbol", lambda: None)()
            if sub is not None:
                l2, t2 = self._contorno(sub, prof + 1)
                larg = larg if larg is not None else l2
                tratto = tratto if tratto is not None else t2
        return larg, tratto

    def _regola_per(self, renderer, layer, genere):
        from qgis.core import (QgsFeature, QgsExpression, QgsExpressionContext,
                               QgsExpressionContextUtils)
        f = QgsFeature(layer.fields())
        f.setAttribute("genere", genere)
        ctx = QgsExpressionContext()
        ctx.appendScope(QgsExpressionContextUtils.globalScope())
        ctx.setFeature(f)
        for reg in renderer.rootRule().children():
            espressione = reg.filterExpression()
            if not espressione:
                return reg            # ripiego: prende tutto
            if QgsExpression(espressione).evaluate(ctx):
                return reg
        return None

    def test_ogni_genere_del_dominio_ha_una_regola(self):
        renderer, layer = self._renderer()
        senza = [g for g, _t in self.DOMINIO
                 if self._regola_per(renderer, layer, g) is None]
        self.assertEqual(senza, [],
                         "questi generi non li disegna nessuno: %s" % senza)

    def test_continuo_o_interrotto1_secondo_la_tabella(self):
        renderer, layer = self._renderer()
        for genere, atteso in self.DOMINIO:
            reg = self._regola_per(renderer, layer, genere)
            self.assertIsNotNone(reg, genere)
            _larg, tratto = self._contorno(reg.symbol())
            nostro = "interrotto1" if tratto == "1.50;0.50" else tratto
            self.assertEqual(nostro, atteso,
                             "%s: il cap.3.3 lo vuole %s, la regola %r da' %s"
                             % (genere, atteso, reg.label(), nostro))

    def test_tutto_il_tema_a_020_mm(self):
        """Lo spessore e' unico per tutta la copertura del suolo."""
        renderer, _layer = self._renderer()
        for reg in renderer.rootRule().children():
            larg, _t = self._contorno(reg.symbol())
            self.assertIsNotNone(larg, "regola senza contorno: %s" % reg.label())
            self.assertAlmostEqual(larg, 0.20, places=3,
                                   msg="%s: spessore %.3f invece di 0.20"
                                       % (reg.label(), larg))


class TestLineeDegliOggettiSingoli(unittest.TestCase):
    """Le linee degli Oggetti singoli (cap. 3.4).

    Il capitolo dice tre cose: 0.20 mm per tutti i generi tranne "sentiero"
    che va a 0.30, il genere di linea per ciascun oggetto, e che il tratteggio
    Interrotto1 NON deve essere utilizzato per questo tema - e' riservato alla
    copertura del suolo.

    Il metodo _gen_stile_elemento_lineare dichiara nella propria docstring il
    principio che questo test verifica: nessun genere del dominio puo' restare
    senza regola, perche' in un renderer a regole senza ripiego una feature che
    non combacia non viene disegnata affatto.
    """

    # Il dominio Genere_OS di MD01MUTI7MN95 con il tipo di linea del cap. 3.4.
    # None = genere che il capitolo non elenca (li tratta come simboli di
    # punto, cap. 2.3) o estensione cantonale: deve comunque avere una regola.
    DOMINIO = (
        ("muro.muro", "continuo"),
        ("muro.muro_di_sostegno", "continuo"),
        # Circ202_Allegato2 (2012) porta il muro divisorio a interrotto2,
        # sostituendo l'interrotto del 2007: 1 635 oggetti su Mendrisio.
        ("muro.muro_divisorio", "interrotto2"),
        ("edificio_sotterraneo.edificio_sotterraneo_indipendente", "punteggiato"),
        ("edificio_sotterraneo.parte_sotterranea_di_edificio", "punteggiato"),
        ("altra_parte_di_edificio.scala", "interrotto2"),
        ("altra_parte_di_edificio.altra_parte_costruttiva", "interrotto2"),
        ("acqua_sotterranea_canalizzata", "punteggiato"),
        ("scala_importante", "continuo"),
        ("tunnel_sottopassaggio_galleria", "punteggiato"),
        ("ponte_passerella", "continuo"),
        ("banchina", "continuo"),
        ("fontana", "continuo"),
        ("serbatoio", "punteggiato"),
        ("pilastro", "continuo"),
        ("riparo", "interrotto2"),
        ("silo_torre_gasometro", "continuo"),
        ("ciminiera", "continuo"),
        ("monumento", "continuo"),
        ("palo_antenna", "continuo"),
        ("torre_panoramica", "continuo"),
        ("arginatura", "continuo"),
        ("briglia", "continuo"),
        ("riparo_antivalanghe", "interrotto2"),
        ("zoccolo_massiccio", "continuo"),
        ("rovina_oggetto_archeologico", "continuo"),
        ("debarcadero", "continuo"),
        ("masso_erratico", "continuo"),
        ("fascia_boscata", "interrotto2"),
        ("ruscello", "continuo"),
        ("sentiero", "interrotto2"),
        ("linea_aerea_ad_alta_tensione", "misto1"),
        ("condotta_forzata", "misto1"),
        ("binari_ferrovia", "misto2"),
        ("teleferica", "misto2"),
        ("telecabina_seggiovia", "misto2"),
        ("teleferica_per_il_materiale", "misto2"),
        ("scilift", "misto2"),
        ("traghetto", "misto2"),
        ("grotta_entrata_di_caverna", "continuo"),
        ("asse", "misto2"),
        ("albero_importante", None),
        ("cappella_statua_crocifisso", None),
        ("sorgente", None),
        ("punto_di_riferimento", None),
        ("altro.concimaia", None),
        ("altro.riparo_fonico", None),
        ("altro.serra", None),
        ("altro.accesso_lago", None),
        ("altro.altro", None),
    )

    # I tratteggi della tabella 3.1, in millimetri.
    PATTERN = {
        "punteggiato": "0.50;0.50",
        "interrotto": "2.50;0.70",
        "interrotto1": "1.50;0.50",
        "interrotto2": "1.00;0.70",
        "interrotto3": "4.00;1.00",
        "misto1": "6.50;1.00;1.00;1.00;1.00;1.00",
        "misto2": "10.00;1.00;1.80;1.00",
    }

    def _renderer(self):
        layer = QgsVectorLayer("LineString?crs=EPSG:2056&field=genere:string",
                               "oggetti_singoli_elemento_lineare", "memory")
        return make_dialog_stub()._get_renderer_for_table(
            "Elemento_lineare", "oggetti_singoli_elemento_lineare", "gb",
            "LINE", layer), layer

    def _linea(self, sym, prof=0):
        larg = tratto = None
        if sym is None or prof > 4:
            return larg, tratto
        for i in range(sym.symbolLayerCount()):
            sl = sym.symbolLayer(i)
            if sl.layerType() == "SimpleLine":
                if sl.width() and sl.width() > 0 and larg is None:
                    larg = sl.width()
                v = sl.customDashVector()
                if sl.useCustomDashPattern() and v:
                    tratto = ";".join("%.2f" % x for x in v)
                elif tratto is None:
                    tratto = "continuo"
            sub = getattr(sl, "subSymbol", lambda: None)()
            if sub is not None:
                l2, t2 = self._linea(sub, prof + 1)
                larg = larg if larg is not None else l2
                tratto = tratto if tratto is not None else t2
        return larg, tratto

    def _regole_per(self, renderer, layer, genere):
        from qgis.core import (QgsFeature, QgsExpression, QgsExpressionContext,
                               QgsExpressionContextUtils)
        f = QgsFeature(layer.fields())
        f.setAttribute("genere", genere)
        ctx = QgsExpressionContext()
        ctx.appendScope(QgsExpressionContextUtils.globalScope())
        ctx.setFeature(f)
        prese = []
        for reg in renderer.rootRule().children():
            espressione = reg.filterExpression()
            if not espressione or QgsExpression(espressione).evaluate(ctx):
                prese.append(reg)
        return prese

    def test_ogni_genere_del_dominio_ha_una_regola(self):
        renderer, layer = self._renderer()
        senza = [g for g, _t in self.DOMINIO
                 if not self._regole_per(renderer, layer, g)]
        self.assertEqual(senza, [],
                         "questi generi non li disegna nessuno: %s" % senza)

    def test_nessun_genere_viene_disegnato_due_volte(self):
        """In un renderer a regole NON esclusive ogni regola che combacia
        disegna: due filtri che si sovrappongono raddoppiano il tratto."""
        renderer, layer = self._renderer()
        doppi = {g: [r.label() for r in self._regole_per(renderer, layer, g)]
                 for g, _t in self.DOMINIO
                 if len(self._regole_per(renderer, layer, g)) > 1}
        self.assertEqual(doppi, {}, "generi presi da piu' regole: %s" % doppi)

    def test_il_genere_di_linea_segue_la_tabella(self):
        renderer, layer = self._renderer()
        for genere, atteso in self.DOMINIO:
            if atteso is None:
                continue
            regole = self._regole_per(renderer, layer, genere)
            self.assertTrue(regole, genere)
            _l, tratto = self._linea(regole[0].symbol())
            nostro = "continuo" if tratto == "continuo" else next(
                (k for k, v in self.PATTERN.items() if v == tratto), str(tratto))
            self.assertEqual(nostro, atteso,
                             "%s: il cap.3.4 lo vuole %s, la regola %r da' %s"
                             % (genere, atteso, regole[0].label(), nostro))

    def test_020_ovunque_tranne_il_sentiero(self):
        renderer, layer = self._renderer()
        for genere, _t in self.DOMINIO:
            regole = self._regole_per(renderer, layer, genere)
            self.assertTrue(regole, genere)
            larg, _tr = self._linea(regole[0].symbol())
            atteso = 0.30 if genere == "sentiero" else 0.20
            self.assertAlmostEqual(larg, atteso, places=3,
                                   msg="%s: spessore %s invece di %.2f"
                                       % (genere, larg, atteso))

    def test_l_interrotto1_non_si_usa_in_questo_tema(self):
        """Il cap. 3.4 lo vieta: l'interrotto1 e' della copertura del suolo."""
        renderer, _layer = self._renderer()
        con_interrotto1 = [r.label() for r in renderer.rootRule().children()
                           if self._linea(r.symbol())[1] == self.PATTERN["interrotto1"]]
        self.assertEqual(con_interrotto1, [])


class TestTrameDelCapitolo4(unittest.TestCase):
    """Le trame delle superfici contro la tabella del cap. 4.

    I valori qui sotto sono TRASCRITTI dall'istruzione (stato 1.2.2014), non
    ricopiati dal codice. La tabella dice, per ogni superficie, la grandezza
    di riferimento a 1:1000 e la distanza fra i simboli.

    Il colore: "tutte le trame composte di simboli sono rappresentate in
    grigio (valore indicativo ca. 50%) AD ECCEZIONE delle trame punteggiate
    (bosco, superficie boscata e pascolo)" - che restano nere.
    """

    # (descrizione, dimensione mm, distanza mm)
    NORMA = (
        ("Bosco fitto",           0.3, 2.0),
        ("Altro bosco",           0.3, 4.0),
        ("Pascolo boscato fitto", 0.3, 8.0),
        ("Pascolo boscato rado",  0.3, 16.0),
        ("Vigne",                 3.0, 10.0),
        ("Torbiera",              3.5, 10.0),
        ("Canneto",               3.0, 10.0),
    )

    def test_i_passi_delle_trame_punteggiate(self):
        """2, 4, 8, 16: raddoppiano a ogni classe, dal bosco piu' fitto al
        pascolo piu' rado. Un valore fuori posto inverte la gerarchia visiva
        fra due coperture del suolo diverse."""
        passi = [d for _n, _s, d in self.NORMA[:4]]
        self.assertEqual(passi, [2.0, 4.0, 8.0, 16.0])

    def test_i_colori_delle_trame(self):
        """I grigi sono dati in RGB dalla norma: 130 per le trame a simboli,
        178 per l'edificio, 225 per l'edificio sotterraneo."""
        from colori import C_TRAMA_50, C_TRAMA_30, C_TRAMA_10
        self.assertEqual((C_TRAMA_50.red(), C_TRAMA_50.green(), C_TRAMA_50.blue()),
                         (130, 130, 130))
        self.assertEqual((C_TRAMA_30.red(), C_TRAMA_30.green(), C_TRAMA_30.blue()),
                         (178, 178, 178))
        self.assertEqual((C_TRAMA_10.red(), C_TRAMA_10.green(), C_TRAMA_10.blue()),
                         (225, 225, 225))

    def test_le_trame_punteggiate_restano_nere(self):
        """L'eccezione dichiarata dal cap. 4: bosco, superficie boscata e
        pascolo non vanno in grigio."""
        from colori import C_NERO, C_TRAMA_50
        from simbologia import make_point_pattern
        livello = make_point_pattern(C_NERO, d=2.0, size=0.3)
        sub = livello.subSymbol()
        colore = sub.symbolLayer(0).color()
        self.assertEqual((colore.red(), colore.green(), colore.blue()), (0, 0, 0))
        self.assertNotEqual(colore.name(), C_TRAMA_50.name())

    def test_il_passo_disegnato_e_quello_chiesto(self):
        """MISURATO SUL DISEGNO, non sulle costanti: si riempie un poligono e
        si contano le macchie di inchiostro.

        La taratura sul bosco fitto (passo 2 mm) viene prima: se lo strumento
        sbagliasse li', la misura sulle altre trame non proverebbe niente. E'
        gia' successo due volte scrivendo questo controllo - un primo metodo
        contava i tratti dentro un glifo invece dei simboli, un secondo
        trovava i multipli del passo invece del passo."""
        import math
        from qgis.core import (QgsFillSymbol, QgsRenderContext, QgsGeometry,
                               QgsPointXY)
        from qgis.PyQt.QtGui import QImage, QPainter, QColor
        from colori import C_NERO
        from simbologia import make_point_pattern

        dpi, lato = 300.0, 600
        for passo_voluto in (2.0, 8.0):
            sym = QgsFillSymbol([make_point_pattern(C_NERO, d=passo_voluto, size=0.3)])
            img = QImage(lato, lato, QImage.Format.Format_ARGB32)
            ppm = int(dpi / 25.4 * 1000)
            img.setDotsPerMeterX(ppm)
            img.setDotsPerMeterY(ppm)
            img.fill(QColor(255, 255, 255))
            pittore = QPainter(img)
            ctx = QgsRenderContext.fromQPainter(pittore)
            sym.startRender(ctx)
            poly = QgsGeometry.fromPolygonXY([[
                QgsPointXY(0, 0), QgsPointXY(lato, 0), QgsPointXY(lato, lato),
                QgsPointXY(0, lato), QgsPointXY(0, 0)]])
            sym.renderPolygon(poly.asQPolygonF(), None, None, ctx)
            sym.stopRender(ctx)
            pittore.end()
            scuri = set()
            for y in range(lato):
                for x in range(lato):
                    if img.pixelColor(x, y).red() < 240:
                        scuri.add((x, y))
            centri, visti = [], set()
            for p0 in scuri:
                if p0 in visti:
                    continue
                coda, gruppo = [p0], []
                visti.add(p0)
                while coda:
                    x, y = coda.pop()
                    gruppo.append((x, y))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        q = (x + dx, y + dy)
                        if q in scuri and q not in visti:
                            visti.add(q)
                            coda.append(q)
                centri.append((sum(a for a, _ in gruppo) / len(gruppo),
                               sum(b for _, b in gruppo) / len(gruppo)))
            self.assertGreater(len(centri), 3,
                               "la trama non ha disegnato abbastanza punti")
            vicini = sorted(
                min(math.dist(c1, c2) for j, c2 in enumerate(centri) if i != j)
                for i, c1 in enumerate(centri))
            misurato = vicini[len(vicini) // 2] / ctx.scaleFactor()
            self.assertAlmostEqual(
                misurato / passo_voluto, 1.0, delta=0.05,
                msg="passo chiesto %.1f mm, disegnato %.3f" % (passo_voluto, misurato))


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2)
    _qgs.exitQgis()
    sys.exit(0 if result.result.wasSuccessful() else 1)
