# Test dell'interfaccia della dialog. Costruisce la finestra vera e ne
# esercita i controlli: i difetti trovati finora (exec_ al posto di exec,
# QMessageBox.Yes non piu' esistente) erano tutti invisibili ai test che
# saltavano la costruzione dei widget.
#
# Eseguire con l'interprete di QGIS:
#   & "C:\Program Files\QGIS 4.2.0\bin\python-qgis.bat" test_dialog_ui.py
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qgis.core import (QgsApplication, QgsProject, QgsVectorLayer, QgsFeature,
                       QgsGeometry, QgsPointXY, QgsRectangle, Qgis)
from qgis.PyQt.QtCore import QDate
from qgis.PyQt.QtWidgets import QMessageBox, QPushButton

# True: servono i widget veri, non la modalita' senza interfaccia.
_qgs = QgsApplication([], True)
_qgs.initQgis()

from tidashboard.tidashboard import TIDashboardDialog
from tidashboard import planimetria as P

CX, CY = 2718000.0, 1082000.0
_avvisi = []
QMessageBox.warning = staticmethod(
    lambda *a, **k: _avvisi.append(a[2] if len(a) > 2 else ""))


def _gpkg_con_comuni(nome_piano=None, comuni=("Giubiasco",)):
    percorso = os.path.join(tempfile.mkdtemp(), "dati.gpkg")
    con = sqlite3.connect(percorso)
    con.execute("CREATE TABLE confini_comunali_comune (nome TEXT)")
    con.executemany("INSERT INTO confini_comunali_comune VALUES (?)",
                    [(c,) for c in comuni])
    if nome_piano:
        con.execute("CREATE TABLE margine_del_piano_layout_del_piano (nome_comune TEXT)")
        con.execute("INSERT INTO margine_del_piano_layout_del_piano VALUES (?)",
                    (nome_piano,))
    con.commit()
    con.close()
    return percorso


def _gpkg_con_tenuta_a_giorno(in_vigore, comuni=("Giubiasco",)):
    """GeoPackage con una tabella di attualizzazione: e' la seconda fonte di
    "Stato al", quella usata quando non c'e' un ITF da cui leggere il
    timestamp."""
    percorso = _gpkg_con_comuni(comuni=comuni)
    con = sqlite3.connect(percorso)
    con.execute("CREATE TABLE confini_comunali_tenuta_a_giorno_comune "
                "(in_vigore TEXT)")
    con.execute("INSERT INTO confini_comunali_tenuta_a_giorno_comune VALUES (?)",
                (in_vigore,))
    con.commit()
    con.close()
    return percorso


def _layer():
    lyr = QgsVectorLayer("Polygon?crs=EPSG:2056", "prova", "memory")
    f = QgsFeature(lyr.fields())
    f.setGeometry(QgsGeometry.fromPolygonXY([[
        QgsPointXY(CX - 50, CY - 50), QgsPointXY(CX + 50, CY - 50),
        QgsPointXY(CX + 50, CY + 50), QgsPointXY(CX - 50, CY + 50),
        QgsPointXY(CX - 50, CY - 50)]]))
    lyr.dataProvider().addFeatures([f])
    lyr.updateExtents()
    return lyr


class TestSchede(unittest.TestCase):
    def test_tre_schede_nell_ordine_del_flusso(self):
        dlg = TIDashboardDialog()
        titoli = [dlg.schede.tabText(i) for i in range(dlg.schede.count())]
        self.assertEqual(titoli, ["0. Ambiente", "1. Importazione",
                                  "2. Conversione DXF", "3. Planimetria",
                                  "Errori nei dati"])

    def test_scheda_errori_spenta_finche_non_ce_ne_sono(self):
        dlg = TIDashboardDialog()
        i = dlg.schede.indexOf(dlg.pagina_errori)
        self.assertFalse(dlg.schede.isTabEnabled(i))


class TestSpunteSulleSchede(unittest.TestCase):
    """Le tre schede sono una sequenza, ma niente diceva a che punto si fosse."""

    def test_la_spunta_compare_e_non_raddoppia(self):
        dlg = TIDashboardDialog()
        # Per indice di PAGINA, non per posizione: l'aggiunta della scheda
        # "0. Ambiente" ha spostato tutte le altre di uno.
        i = dlg.schede.indexOf(dlg.pagina_import)
        self.assertEqual(dlg.schede.tabText(i), "1. Importazione")
        dlg._segna_scheda_fatta(dlg.pagina_import, "1. Importazione")
        self.assertEqual(dlg.schede.tabText(i), "✔ 1. Importazione")
        dlg._segna_scheda_fatta(dlg.pagina_import, "1. Importazione")
        self.assertEqual(dlg.schede.tabText(i), "✔ 1. Importazione")

    def test_non_si_cambia_scheda_da_soli(self):
        """Dopo l'importazione i passi possibili sono due (DXF o planimetria):
        sceglierne uno sarebbe indovinare."""
        dlg = TIDashboardDialog()
        dlg.schede.setCurrentIndex(0)
        dlg._segna_scheda_fatta(dlg.pagina_import, "1. Importazione")
        self.assertEqual(dlg.schede.currentIndex(), 0)


class TestItfDellaSchedaDxf(unittest.TestCase):
    """L'ITF era chiesto due volte, in due campi identici gia' sincronizzati:
    non si capiva se andassero compilati entrambi."""

    def test_rispecchia_l_importazione_ed_e_bloccato(self):
        dlg = TIDashboardDialog()
        self.assertTrue(dlg.txt_geobau_itf.isReadOnly())
        self.assertFalse(dlg._btn_sfoglia_itf_dxf.isEnabled())
        dlg.txt_itf.setText(r"C:\dati\5250010200.itf")
        self.assertEqual(dlg.txt_geobau_itf.text(), r"C:\dati\5250010200.itf")

    def test_la_spunta_sblocca_e_l_importazione_non_sovrascrive(self):
        dlg = TIDashboardDialog()
        dlg.txt_itf.setText(r"C:\dati\primo.itf")
        dlg.chk_itf_diverso.setChecked(True)
        self.assertFalse(dlg.txt_geobau_itf.isReadOnly())
        self.assertTrue(dlg._btn_sfoglia_itf_dxf.isEnabled())
        dlg.txt_geobau_itf.setText(r"C:\altro\diverso.itf")
        dlg.txt_itf.setText(r"C:\dati\secondo.itf")
        self.assertEqual(dlg.txt_geobau_itf.text(), r"C:\altro\diverso.itf")

    def test_togliendo_la_spunta_torna_a_rispecchiare(self):
        """Altrimenti resterebbe un valore vecchio che nessuno ricorda di aver
        scritto, e si convertirebbe l'ITF sbagliato in silenzio."""
        dlg = TIDashboardDialog()
        dlg.chk_itf_diverso.setChecked(True)
        dlg.txt_geobau_itf.setText(r"C:\altro\diverso.itf")
        dlg.txt_itf.setText(r"C:\dati\corrente.itf")
        dlg.chk_itf_diverso.setChecked(False)
        self.assertEqual(dlg.txt_geobau_itf.text(), r"C:\dati\corrente.itf")
        self.assertTrue(dlg.txt_geobau_itf.isReadOnly())


class TestConvalidaPercorsi(unittest.TestCase):
    """Un percorso sbagliato si scopriva solo dalla console, dopo che Java era
    partito e fallito."""

    def test_pulsanti_spenti_a_campi_vuoti(self):
        dlg = TIDashboardDialog()
        dlg.txt_geobau_jar.setText("")     # il jar in dotazione lo precompila
        self.assertFalse(dlg.btn_import.isEnabled())
        self.assertFalse(dlg.btn_geobau.isEnabled())
        self.assertIn("da sistemare", dlg.lbl_esito_import.text())

    def test_file_inesistente_segnalato(self):
        dlg = TIDashboardDialog()
        dlg.txt_jar.setText(os.path.join(tempfile.mkdtemp(), "manca.jar"))
        spie = {le: et for le, _s, et, _sc in dlg._campi_percorso}
        self.assertEqual(spie[dlg.txt_jar].text(), "✖")
        self.assertIn("non esiste", spie[dlg.txt_jar].toolTip())

    def test_campo_di_salvataggio_guarda_la_cartella(self):
        """Il file di output non esiste ancora: e' normale, deve esistere la
        cartella che lo conterra'."""
        dlg = TIDashboardDialog()
        cartella = tempfile.mkdtemp()
        dlg.txt_gpkg.setText(os.path.join(cartella, "nuovo.gpkg"))
        spie = {le: et for le, _s, et, _sc in dlg._campi_percorso}
        self.assertEqual(spie[dlg.txt_gpkg].text(), "✔")
        dlg.txt_gpkg.setText(os.path.join(cartella, "manca", "nuovo.gpkg"))
        self.assertEqual(spie[dlg.txt_gpkg].text(), "✖")

    def test_pulsante_acceso_a_campi_validi(self):
        dlg = TIDashboardDialog()
        esistente = _gpkg_con_comuni()
        for campo in (dlg.txt_jar, dlg.txt_itf, dlg.txt_gpkg):
            campo.setText(esistente)
        self.assertTrue(dlg.btn_import.isEnabled())
        self.assertEqual(dlg.lbl_esito_import.text(), "")


class TestAvanzamento(unittest.TestCase):
    def test_nascosto_a_riposo_e_visibile_durante_il_lavoro(self):
        dlg = TIDashboardDialog()
        self.assertFalse(dlg.barra_avanzamento.isVisible())
        dlg._inizio_lavoro("Fase 1: creazione schema")
        self.assertEqual(dlg.lbl_fase.text(), "Fase 1: creazione schema")
        self.assertEqual(dlg.lbl_tempo.text(), "00:00")
        dlg._fine_lavoro()
        self.assertFalse(dlg.barra_avanzamento.isVisible())

    def test_pulsanti_spenti_durante_il_lavoro(self):
        """_inizio_lavoro viene chiamato PRIMA che il nuovo JavaWorker sia
        assegnato a self.worker: se la convalida interrogasse il worker invece
        del flag, i pulsanti si riaccenderebbero subito."""
        dlg = TIDashboardDialog()
        esistente = _gpkg_con_comuni()
        for campo in (dlg.txt_jar, dlg.txt_itf, dlg.txt_gpkg):
            campo.setText(esistente)
        self.assertTrue(dlg.btn_import.isEnabled())
        dlg._inizio_lavoro("Fase 1")
        self.assertFalse(dlg.btn_import.isEnabled())
        dlg._fine_lavoro()
        self.assertTrue(dlg.btn_import.isEnabled())


class TestComuneDaiDati(unittest.TestCase):
    def test_letto_dal_geopackage_indicato(self):
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText(_gpkg_con_comuni(comuni=("Giubiasco", "Camorino")))
        self.assertEqual(dlg.aggiorna_comuni_da_dati(), ["Giubiasco", "Camorino"])
        self.assertEqual(dlg.combo_comune.currentText(), "Giubiasco")

    def test_nome_per_il_piano_preferito(self):
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText(_gpkg_con_comuni(nome_piano="Bellinzona-Giubiasco",
                                              comuni=("Camorino",)))
        dlg.aggiorna_comuni_da_dati()
        self.assertEqual(dlg.combo_comune.currentText(), "Bellinzona-Giubiasco")

    def test_finisce_nel_cartiglio_senza_digitarlo(self):
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText(_gpkg_con_comuni(comuni=("Giubiasco",)))
        dlg.loaded_layers = [_layer()]
        dlg._iface = None
        QgsProject.instance().addMapLayer(dlg.loaded_layers[0], False)
        dlg.run_planimetria()
        testi = [i.text() for i in dlg._ultima_planimetria.items()
                 if i.__class__.__name__ == "QgsLayoutItemLabel"]
        self.assertIn("Comune di Giubiasco", testi)

    def test_senza_comune_nei_dati_avvisa_e_non_crea(self):
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText("")
        dlg.loaded_layers = [_layer()]
        dlg._iface = None
        del _avvisi[:]
        dlg.run_planimetria()
        self.assertTrue(any("Comune non trovato" in a for a in _avvisi))
        self.assertIsNone(getattr(dlg, "_ultima_planimetria", None))


class TestConsole(unittest.TestCase):
    """QTextEdit.append() interpreta il testo come HTML. In console finiscono
    anche stringhe che vengono dai DATI (percorsi di file, messaggi di
    ili2gpkg che riportano valori dell'ITF), quindi un ITF confezionato ad arte
    poteva scriverci dentro un falso "Importazione completata"."""

    def test_il_markup_non_viene_interpretato(self):
        dlg = TIDashboardDialog()
        riga = '<b>FALSO</b> <span style="color:#00ff00">completata</span>'
        dlg.log(riga)
        self.assertIn(riga, dlg.txt_log.toPlainText())


class TestFiltroConsole(unittest.TestCase):
    def _dialog(self):
        dlg = TIDashboardDialog()
        dlg._pulisci_log()
        dlg.log("riga normale")
        dlg.log("   ⚠️ un avviso")
        dlg.log("   ❌ un errore", Qgis.Critical)
        return dlg

    def test_livelli_riconosciuti_anche_dal_solo_emoji(self):
        """Buona parte delle chiamate non passa 'level' e affida la gravita'
        all'emoji: guardando solo il parametro, il filtro le perderebbe."""
        dlg = self._dialog()
        self.assertEqual([l for _m, l in dlg._righe_log],
                         ["normale", "avviso", "errore"])
        self.assertEqual(dlg.lbl_conteggio_log.text(), "1 avvisi, 1 errori")

    def test_il_filtro_nasconde_ma_non_butta_via(self):
        dlg = self._dialog()
        self.assertEqual(len(dlg.txt_log.toPlainText().strip().split("\n")), 3)
        dlg.chk_solo_problemi.setChecked(True)
        self.assertEqual(len(dlg.txt_log.toPlainText().strip().split("\n")), 2)
        self.assertEqual(len(dlg._righe_log), 3)
        dlg.chk_solo_problemi.setChecked(False)
        self.assertEqual(len(dlg.txt_log.toPlainText().strip().split("\n")), 3)

    def test_pulisci_azzera_anche_lo_storico(self):
        dlg = self._dialog()
        dlg._pulisci_log()
        self.assertEqual(dlg._righe_log, [])
        self.assertEqual(dlg.txt_log.toPlainText(), "")


class TestEsitoImportazione(unittest.TestCase):
    def test_riepilogo_con_saltate_e_passo_successivo(self):
        dlg = TIDashboardDialog()
        self.assertFalse(dlg.riquadro_esito.isVisibleTo(dlg))
        dlg._mostra_esito_importazione(106, [("t_x", "non valida")], ["Giubiasco"])
        testo = dlg.lbl_esito.text()
        self.assertIn("106 layer", testo)
        self.assertIn("Giubiasco", testo)
        self.assertIn("1 tabelle saltate", testo)
        self.assertIn("Passo successivo", testo)
        self.assertTrue(dlg.riquadro_esito.isVisibleTo(dlg))

    def test_senza_comune_lo_dice(self):
        dlg = TIDashboardDialog()
        dlg._mostra_esito_importazione(10, [], [])
        self.assertIn("Comune non trovato", dlg.lbl_esito.text())


class TestTabellaErrori(unittest.TestCase):
    RIGHE = [{"tabella": "Punto_di_confine", "vincolo": "IdentAN",
              "valori": "TI5250 1234", "tid": "17 ↔ 42", "riga": 8891,
              "diagnosi": "doppione: stesso punto, distanza 0.0 m"}]

    def test_scheda_si_accende_e_conta(self):
        dlg = TIDashboardDialog()
        i = dlg.schede.indexOf(dlg.pagina_errori)
        dlg._riempi_tabella_errori(self.RIGHE)
        self.assertTrue(dlg.schede.isTabEnabled(i))
        self.assertEqual(dlg.schede.tabText(i), "Errori nei dati (1)")
        self.assertEqual(dlg.tab_errori.rowCount(), 1)
        self.assertEqual(dlg.tab_errori.item(0, 0).text(), "Punto_di_confine")

    def test_celle_non_modificabili(self):
        """E' un referto sui dati sorgente, non un campo da correggere qui."""
        from qgis.PyQt.QtCore import Qt
        dlg = TIDashboardDialog()
        dlg._riempi_tabella_errori(self.RIGHE)
        self.assertFalse(bool(dlg.tab_errori.item(0, 0).flags()
                              & Qt.ItemFlag.ItemIsEditable))


class TestMemoriaImpostazioni(unittest.TestCase):
    def test_salva_e_ripristina(self):
        dlg = TIDashboardDialog()
        dlg.txt_jar.setText(r"C:\percorso\ili2gpkg.jar")
        dlg.combo_scala.setCurrentText("1:2000")
        dlg.spin_rotazione.setValue(137.5)
        dlg.chk_skip_geom.setChecked(True)
        dlg._salva_impostazioni()

        nuova = TIDashboardDialog()
        self.assertEqual(nuova.txt_jar.text(), r"C:\percorso\ili2gpkg.jar")
        self.assertEqual(nuova.combo_scala.currentText(), "1:2000")
        self.assertAlmostEqual(nuova.spin_rotazione.value(), 137.5, places=3)
        self.assertTrue(nuova.chk_skip_geom.isChecked())

    def test_la_data_di_validita_non_si_ricorda(self):
        """Ripartire dalla data dell'ultima sessione significherebbe
        attestare un'attualita' vecchia di giorni."""
        from qgis.PyQt.QtCore import QDate
        dlg = TIDashboardDialog()
        dlg.data_validita.setDate(QDate(2020, 1, 1))
        dlg._salva_impostazioni()
        self.assertEqual(TIDashboardDialog().data_validita.date(), QDate.currentDate())


class TestRisorseInDotazione(unittest.TestCase):
    """Traduttore DXF e modello .ili non si scelgono: sono quelli distribuiti
    col plugin."""

    def test_campi_in_sola_lettura_e_preimpostati(self):
        from tidashboard.tidashboard import AV2GEOBAU_JAR, MODELLO_ILI
        dlg = TIDashboardDialog()
        self.assertTrue(dlg.txt_geobau_jar.isReadOnly())
        self.assertTrue(dlg.txt_ili.isReadOnly())
        self.assertEqual(dlg.txt_geobau_jar.text(), AV2GEOBAU_JAR)
        self.assertEqual(dlg.txt_ili.text(), MODELLO_ILI)

    def test_presenti_nell_installazione(self):
        from tidashboard.tidashboard import AV2GEOBAU_JAR, MODELLO_ILI
        for percorso in (AV2GEOBAU_JAR, MODELLO_ILI):
            self.assertTrue(os.path.isfile(percorso), "manca %s" % percorso)
        dlg = TIDashboardDialog()
        self.assertEqual(dlg.stato_jar.text(), "✔")
        self.assertEqual(dlg.stato_ili.text(), "✔")


class TestRotazione(unittest.TestCase):
    """Con il solo spin a passo 10, arrivare a 300 gon voleva dire trenta
    clic."""

    def test_cursore_e_spin_si_seguono(self):
        dlg = TIDashboardDialog()
        dlg.spin_rotazione.setValue(137.5)
        self.assertEqual(dlg.slider_rotazione.value(), 1375)
        dlg.slider_rotazione.setValue(2000)
        self.assertAlmostEqual(dlg.spin_rotazione.value(), 200.0, places=3)

    def test_gradi_mostrati_accanto_ai_gon(self):
        dlg = TIDashboardDialog()
        for gon, gradi in ((0, 0.0), (50, 45.0), (100, 90.0), (300, 270.0)):
            dlg.spin_rotazione.setValue(float(gon))
            self.assertEqual(dlg.lbl_gradi.text(), "= %.1f°" % gradi)

    def test_scatti_rapidi(self):
        dlg = TIDashboardDialog()
        scatti = [b for b in dlg.findChildren(QPushButton)
                  if b.text() in ("0", "100", "200", "300")]
        self.assertEqual(len(scatti), 4)
        for b in scatti:
            b.click()
            self.assertAlmostEqual(dlg.spin_rotazione.value(), float(b.text()), places=3)


def _rilascia(dlg, *percorsi):
    """Simula un rilascio vero sulla finestra: costruisce il QDropEvent con
    gli url dei file e lo consegna al dialogo, invece di chiamare a mano il
    gestore. Cosi' il test copre anche l'accettazione del trascinamento."""
    from qgis.PyQt.QtCore import QMimeData, QPointF, QUrl, Qt
    from qgis.PyQt.QtGui import QDragEnterEvent, QDropEvent
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(p) for p in percorsi])
    entrata = QDragEnterEvent(
        QPointF(1, 1).toPoint(), Qt.DropAction.CopyAction, mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    dlg.dragEnterEvent(entrata)
    caduta = QDropEvent(
        QPointF(1, 1), Qt.DropAction.CopyAction, mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    dlg.dropEvent(caduta)
    return entrata.isAccepted()


class TestNomiAutomatici(unittest.TestCase):
    """La catena ITF -> GeoPackage -> DXF aveva solo il secondo anello: il
    percorso di uscita andava scritto a mano pur essendo, in pratica, sempre
    lo stesso nome nella stessa cartella."""

    def test_il_gpkg_segue_l_itf(self):
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText("")
        dlg.txt_itf.setText(os.path.join("C:", os.sep, "dati", "5254010100.itf"))
        self.assertEqual(dlg.txt_gpkg.text(),
                         os.path.join("C:", os.sep, "dati", "5254010100.gpkg"))

    def test_e_il_dxf_segue_il_gpkg(self):
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText("")
        dlg.txt_itf.setText(os.path.join("C:", os.sep, "dati", "5254010100.itf"))
        self.assertEqual(dlg.txt_geobau_dxf.text(),
                         os.path.join("C:", os.sep, "dati", "5254010100.dxf"))

    def test_una_scelta_a_mano_non_viene_sovrascritta(self):
        dlg = TIDashboardDialog()
        mio = os.path.join("C:", os.sep, "altrove", "mio.gpkg")
        dlg.txt_gpkg.setText(mio)
        dlg.txt_itf.setText(os.path.join("C:", os.sep, "dati", "5254010100.itf"))
        self.assertEqual(dlg.txt_gpkg.text(), mio)


class TestTrascinamento(unittest.TestCase):
    def test_itf_e_jar_finiscono_nei_campi_giusti(self):
        dlg = TIDashboardDialog()
        cartella = tempfile.mkdtemp()
        itf = os.path.join(cartella, "5254010100.itf")
        jar = os.path.join(cartella, "ili2gpkg-5.5.2.jar")
        for p in (itf, jar):
            open(p, "w").close()
        self.assertTrue(_rilascia(dlg, itf, jar))
        self.assertEqual(dlg.txt_itf.text(), itf)
        self.assertEqual(dlg.txt_jar.text(), jar)
        # e la catena dei nomi e' scattata anche da qui
        self.assertEqual(dlg.txt_gpkg.text(),
                         os.path.join(cartella, "5254010100.gpkg"))

    def test_un_tipo_che_non_sappiamo_dove_mettere_non_viene_accettato(self):
        """Accettare tutto e poi ignorare in silenzio farebbe sembrare il
        rilascio riuscito."""
        dlg = TIDashboardDialog()
        altro = os.path.join(tempfile.mkdtemp(), "lettera.pdf")
        open(altro, "w").close()
        self.assertFalse(_rilascia(dlg, altro))

    def test_cartella_con_un_solo_itf(self):
        dlg = TIDashboardDialog()
        cartella = tempfile.mkdtemp()
        itf = os.path.join(cartella, "unico.itf")
        open(itf, "w").close()
        _rilascia(dlg, cartella)
        self.assertEqual(dlg.txt_itf.text(), itf)

    def test_cartella_con_piu_itf_non_indovina(self):
        dlg = TIDashboardDialog()
        cartella = tempfile.mkdtemp()
        for nome in ("a.itf", "b.itf"):
            open(os.path.join(cartella, nome), "w").close()
        prima = dlg.txt_itf.text()
        _rilascia(dlg, cartella)
        self.assertEqual(dlg.txt_itf.text(), prima)

    def test_cartella_senza_itf_diventa_la_destinazione(self):
        dlg = TIDashboardDialog()
        origine = tempfile.mkdtemp()
        itf = os.path.join(origine, "5254010100.itf")
        open(itf, "w").close()
        dlg.txt_itf.setText(itf)
        destinazione = tempfile.mkdtemp()
        _rilascia(dlg, destinazione)
        self.assertEqual(dlg.txt_gpkg.text(),
                         os.path.join(destinazione, "5254010100.gpkg"))

    def test_le_caselle_non_intercettano_il_rilascio(self):
        """Se accettassero i rilasci per conto loro ci scriverebbero dentro
        il testo dell'url ("file:///C:/..."), che non e' un percorso."""
        dlg = TIDashboardDialog()
        for campo in (dlg.txt_jar, dlg.txt_itf, dlg.txt_gpkg,
                      dlg.txt_geobau_itf, dlg.txt_geobau_dxf):
            self.assertFalse(campo.acceptDrops())
        self.assertTrue(dlg.acceptDrops())


class TestSchedaAmbiente(unittest.TestCase):
    """Java, ili2gpkg, traduttore e modello: prima si scoprivano mancanti a
    meta' importazione, da un errore di processo."""

    def test_quattro_semafori(self):
        dlg = TIDashboardDialog()
        self.assertEqual(sorted(dlg._spie_ambiente),
                         ["av2geobau", "ili2gpkg", "java", "modello"])

    def test_ili2gpkg_mancante_e_rosso_e_spiegato(self):
        dlg = TIDashboardDialog()
        dlg.txt_jar.setText("")
        stato = dlg._controlla_ambiente(ricerca_java=False)
        ok, testo = stato["ili2gpkg"]
        self.assertFalse(ok)
        self.assertIn("non indicato", testo)
        spia, esito = dlg._spie_ambiente["ili2gpkg"]
        self.assertEqual(spia.text(), "✖")
        self.assertIn("non indicato", esito.text())

    def test_ili2gpkg_valido_e_verde(self):
        dlg = TIDashboardDialog()
        jar = os.path.join(tempfile.mkdtemp(), "ili2gpkg.jar")
        open(jar, "w").close()
        dlg.txt_jar.setText(jar)
        self.assertTrue(dlg._controlla_ambiente(ricerca_java=False)["ili2gpkg"][0])
        self.assertEqual(dlg._spie_ambiente["ili2gpkg"][0].text(), "✔")

    def test_le_risorse_in_dotazione_sono_presenti(self):
        dlg = TIDashboardDialog()
        stato = dlg._controlla_ambiente(ricerca_java=False)
        self.assertTrue(stato["av2geobau"][0], stato["av2geobau"][1])
        self.assertTrue(stato["modello"][0], stato["modello"][1])

    def test_java_viene_cercato_all_apertura(self):
        """Se non lo si cerca all'apertura, il percorso di lavoro dichiara
        "manca: java" a chi Java ce l'ha - solo perche' nessuno era ancora
        andato a guardare."""
        dlg = TIDashboardDialog()
        self.assertIsNotNone(dlg._java_path_cache)
        self.assertIsNotNone(dlg._controlla_ambiente(ricerca_java=False)["java"][0])

    def test_non_verificato_non_e_mancante(self):
        dlg = TIDashboardDialog()
        # Serve isolare il caso: un ili2gpkg davvero assente e' un "manca" e
        # prevarrebbe, nascondendo quello che questo test vuole vedere.
        jar = os.path.join(tempfile.mkdtemp(), "ili2gpkg.jar")
        open(jar, "w").close()
        dlg.txt_jar.setText(jar)
        dlg._java_path_cache = None
        fatto, motivo = dlg._stato_passi()["ambiente"]
        self.assertFalse(fatto)
        self.assertIn("da verificare", motivo)
        self.assertNotIn("manca", motivo)

    def test_senza_cercare_java_non_si_inventa_un_esito(self):
        """La ricerca esegue 'java -version' su ogni candidato: non puo'
        girare a ogni battuta di tasto, e finche' non e' stata fatta lo stato
        e' "non verificato", non "assente"."""
        dlg = TIDashboardDialog()
        dlg._java_path_cache = None
        ok, testo = dlg._controlla_ambiente(ricerca_java=False)["java"]
        self.assertIsNone(ok)
        self.assertIn("non ancora verificato", testo)


class TestPercorsoDiLavoro(unittest.TestCase):
    """Le spunte sui titoli dicono cosa e' fatto, non cosa manca per finire."""

    def test_cinque_passi_nell_ordine(self):
        dlg = TIDashboardDialog()
        self.assertEqual([k for k, _t, _p, _c in dlg._passi_percorso()],
                         ["ambiente", "import", "dxf", "plan", "pdf"])

    def test_la_planimetria_dichiara_che_manca_il_comune(self):
        dlg = TIDashboardDialog()
        dlg.combo_comune.setCurrentText("")
        self.assertEqual(dlg._stato_passi()["plan"], (False, "manca: comune"))
        self.assertIn("manca: comune", dlg.lbl_percorso.text())

    def test_col_comune_il_motivo_sparisce(self):
        dlg = TIDashboardDialog()
        dlg.combo_comune.setCurrentText("Chiasso")
        self.assertEqual(dlg._stato_passi()["plan"], (False, ""))
        self.assertNotIn("manca: comune", dlg.lbl_percorso.text())

    def test_un_passo_fatto_resta_fatto(self):
        dlg = TIDashboardDialog()
        dlg._segna_passo("import")
        self.assertTrue(dlg._stato_passi()["import"][0])
        self.assertIn("Importazione ✔", dlg.lbl_percorso.text())

    def test_ogni_passo_e_cliccabile(self):
        dlg = TIDashboardDialog()
        for chiave, _t, _p, _c in dlg._passi_percorso():
            self.assertIn("href='%s'" % chiave, dlg.lbl_percorso.text())

    def test_il_click_porta_alla_scheda_e_al_campo(self):
        dlg = TIDashboardDialog()
        dlg.combo_comune.setCurrentText("")
        dlg._vai_al_passo("plan")
        self.assertEqual(dlg.schede.currentIndex(),
                         dlg.schede.indexOf(dlg.pagina_plan))
        # focusWidget e non hasFocus: hasFocus vuole una finestra ATTIVA, e i
        # test non mostrano mai il dialogo - sarebbe sempre False, cioe' un
        # test che passa o fallisce per il motivo sbagliato.
        self.assertIs(dlg.focusWidget(), dlg.combo_comune)

    def test_un_passo_gia_fatto_non_mette_il_fuoco_da_nessuna_parte(self):
        """Portare alla scheda si', ma non segnalare in rosso un campo che
        non ha nessun problema."""
        dlg = TIDashboardDialog()
        dlg.combo_comune.setCurrentText("Chiasso")
        dlg._segna_passo("plan")
        dlg.txt_itf.setFocus()
        dlg._vai_al_passo("plan")
        self.assertEqual(dlg.schede.currentIndex(),
                         dlg.schede.indexOf(dlg.pagina_plan))
        self.assertIs(dlg.focusWidget(), dlg.txt_itf)


class TestOrigineData(unittest.TestCase):
    """"Stato al" e' un'iscrizione obbligatoria e nessuna delle due fonti e'
    una data del contenuto INTERLIS. La fonte finiva solo in console al momento
    dell'importazione: chi apriva la scheda dopo vedeva una data e basta."""

    def test_senza_dati_dichiara_che_non_ha_fonti(self):
        dlg = TIDashboardDialog()
        testo = dlg.lbl_origine_data.text()
        self.assertIn("Nessuna fonte", testo)
        self.assertIn("B71C1C", testo, "va segnalato in rosso")

    def test_da_itf_dichiara_il_file_system(self):
        dlg = TIDashboardDialog()
        itf = os.path.join(tempfile.mkdtemp(), "prova.itf")
        with open(itf, "w") as f:
            f.write("MTID\n")
        dlg.txt_itf.setText(itf)
        dlg.txt_gpkg.setText(_gpkg_con_comuni())
        dlg.aggiorna_comuni_da_dati()
        testo = dlg.lbl_origine_data.text()
        self.assertIn("file system", testo)
        self.assertIn("file ITF", testo)

    def test_senza_itf_dichiara_la_mutazione_nei_dati(self):
        dlg = TIDashboardDialog()
        dlg.txt_itf.setText("")
        dlg.txt_gpkg.setText(_gpkg_con_tenuta_a_giorno("2024-03-15"))
        dlg.aggiorna_comuni_da_dati()
        testo = dlg.lbl_origine_data.text()
        self.assertIn("mutazione pi", testo)
        self.assertIn("limite inferiore", testo)

    def test_modificata_a_mano_smette_di_attribuirla_ai_dati(self):
        """Il caso che conta: se l'operatore corregge la data, l'etichetta non
        deve continuare a dichiarare una fonte che non e' piu' quella."""
        dlg = TIDashboardDialog()
        dlg.txt_itf.setText("")
        dlg.txt_gpkg.setText(_gpkg_con_tenuta_a_giorno("2024-03-15"))
        dlg.aggiorna_comuni_da_dati()
        self.assertIn("mutazione pi", dlg.lbl_origine_data.text())
        dlg.data_validita.setDate(QDate(2025, 7, 1))
        testo = dlg.lbl_origine_data.text()
        self.assertIn("a mano", testo)
        self.assertIn("15.03.2024", testo, "va ricordato cosa dicevano i dati")

    def test_rimettendo_la_data_dei_dati_torna_la_fonte(self):
        dlg = TIDashboardDialog()
        dlg.txt_itf.setText("")
        dlg.txt_gpkg.setText(_gpkg_con_tenuta_a_giorno("2024-03-15"))
        dlg.aggiorna_comuni_da_dati()
        dlg.data_validita.setDate(QDate(2025, 7, 1))
        dlg.data_validita.setDate(QDate(2024, 3, 15))
        self.assertIn("mutazione pi", dlg.lbl_origine_data.text())


class TestNotaFattore(unittest.TestCase):
    """Il limite di leggibilita' del cap.1.5.2 morde su 4 delle 8 scale RF, ma
    era scritto solo nel README: chi sceglieva 1:5000 non poteva sapere che i
    segni uscivano quattro volte piu' grandi della lettera della norma."""

    @staticmethod
    def _scegli_scala(dlg, scala):
        for i in range(dlg.combo_scala.count()):
            if dlg.combo_scala.itemText(i).endswith(":%d" % scala):
                dlg.combo_scala.setCurrentIndex(i)
                return True
        return False

    def test_avvisa_quando_il_fattore_e_limitato(self):
        dlg = TIDashboardDialog()
        self.assertTrue(self._scegli_scala(dlg, 5000))
        testo = dlg.lbl_fattore.text()
        self.assertIn("0.80", testo)
        self.assertIn("cartiglio", testo)

    def test_conferma_quando_il_fattore_e_quello_della_norma(self):
        dlg = TIDashboardDialog()
        self.assertTrue(self._scegli_scala(dlg, 1000))
        self.assertIn("esatta", dlg.lbl_fattore.text())

    def test_lettera_norma_avvisa_che_non_si_stampa(self):
        dlg = TIDashboardDialog()
        self.assertTrue(self._scegli_scala(dlg, 10000))
        dlg.chk_lettera_norma.setChecked(True)
        testo = dlg.lbl_fattore.text()
        self.assertIn("0.15 mm", testo)
        self.assertIn("soglia di stampa", testo)

    def test_cambiando_prodotto_cambia_il_riferimento(self):
        """1:5000 e' limitato sul piano RF (riferimento 1:1000) ma e' la scala
        di riferimento stessa del piano di base: la nota deve sparire."""
        dlg = TIDashboardDialog()
        self.assertTrue(self._scegli_scala(dlg, 5000))
        self.assertIn("cartiglio", dlg.lbl_fattore.text())
        dlg.combo_product.setCurrentIndex(1)      # Piano di base
        self.assertIn("esatta", dlg.lbl_fattore.text())


class TestPulsanteLayoutBP(unittest.TestCase):
    """Comparendo e sparendo al cambio di prodotto faceva saltare il resto
    della scheda, e un comando che sparisce non spiega perche' non c'e'."""

    def test_sempre_visibile_e_spento_fuori_da_pb_mu(self):
        dlg = TIDashboardDialog()
        # isHidden e non isVisibleTo: il difetto originale era un
        # setVisible(False) esplicito sul pulsante. isVisibleTo guarda anche
        # gli antenati, e la pagina che lo contiene e' nascosta da QTabWidget
        # ogni volta che la scheda corrente e' un'altra - per esempio al primo
        # avvio, che si apre su "0. Ambiente".
        self.assertFalse(dlg.btn_layout.isHidden())
        self.assertFalse(dlg.btn_layout.isEnabled())
        self.assertIn("PB-MU", dlg.btn_layout.toolTip())
        dlg.combo_product.setCurrentIndex(1)      # Piano di base
        self.assertTrue(dlg.btn_layout.isEnabled())
        self.assertEqual(dlg.btn_layout.toolTip(), "")


class TestComandiDurantelLavoro(unittest.TestCase):
    def test_anche_la_planimetria_si_spegne(self):
        """Restavano attivi e potevano partire con il GeoPackage in scrittura."""
        dlg = TIDashboardDialog()
        dlg.combo_product.setCurrentIndex(1)
        self.assertTrue(dlg.btn_planimetria.isEnabled())
        dlg._inizio_lavoro("Fase 1")
        for pulsante in (dlg.btn_planimetria, dlg.btn_planimetria_pdf, dlg.btn_layout):
            self.assertFalse(pulsante.isEnabled())
        dlg._fine_lavoro()
        for pulsante in (dlg.btn_planimetria, dlg.btn_planimetria_pdf, dlg.btn_layout):
            self.assertTrue(pulsante.isEnabled())


class TestOpzioniTolleranza(unittest.TestCase):
    def test_etichette_in_italiano_col_flag_nel_tooltip(self):
        dlg = TIDashboardDialog()
        coppie = ((dlg.chk_disable_val, "--disableValidation"),
                  (dlg.chk_skip_geom, "--skipGeometryErrors"),
                  (dlg.chk_skip_ref, "--skipReferenceErrors"),
                  (dlg.chk_skip_poly, "--skipPolygonBuilding"),
                  (dlg.chk_sql_null, "--sqlEnableNull"),
                  (dlg.chk_sql_text, "--sqlColsAsText"))
        for casella, flag in coppie:
            self.assertNotIn("--", casella.text(), "etichetta ancora grezza")
            self.assertIn(flag, casella.toolTip())


class TestIngombro(unittest.TestCase):
    AREA_A4V = (210 - 2 * P.MARGINE) * (297 - 2 * P.MARGINE - P.H_CARTIGLIO)

    def _dialog_con_canvas(self):
        from qgis.gui import QgsMapCanvas
        from qgis.core import QgsRectangle, QgsCoordinateReferenceSystem
        canvas = QgsMapCanvas()
        canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:2056"))
        canvas.setExtent(QgsRectangle(CX - 300, CY - 300, CX + 300, CY + 300))

        class FintoIface:
            def mapCanvas(self_):
                return canvas

        dlg = TIDashboardDialog(iface=FintoIface())
        dlg.combo_formato.setCurrentText("A4 verticale")
        dlg.combo_scala.setCurrentText("1:1000")
        return dlg, canvas

    def test_senza_canvas_non_solleva(self):
        """La dialog puo' vivere senza iface (test, uso da script): l'anteprima
        deve semplicemente non fare nulla."""
        dlg = TIDashboardDialog()
        dlg._iface = None
        dlg.chk_ingombro.setChecked(True)
        self.assertIsNone(dlg._aggiorna_ingombro())

    def test_disegna_l_area_del_foglio_alla_scala_scelta(self):
        dlg, _canvas = self._dialog_con_canvas()
        self.assertIsNone(dlg._banda_ingombro)
        dlg.chk_ingombro.setChecked(True)
        self.assertAlmostEqual(dlg._banda_ingombro.asGeometry().area(),
                               self.AREA_A4V, delta=1.0)
        dlg.combo_scala.setCurrentText("1:2000")
        self.assertAlmostEqual(dlg._banda_ingombro.asGeometry().area(),
                               self.AREA_A4V * 4, delta=4.0)

    def test_segue_la_vista(self):
        """L'ingombro e' centrato sulla vista: se non seguisse pan e zoom
        mostrerebbe un'area diversa da quella che verrebbe stampata."""
        dlg, canvas = self._dialog_con_canvas()
        dlg.chk_ingombro.setChecked(True)
        canvas.setExtent(QgsRectangle(CX + 400, CY - 300, CX + 1000, CY + 300))
        centro = dlg._banda_ingombro.asGeometry().centroid().asPoint()
        self.assertAlmostEqual(centro.x(), CX + 700, places=3)

    def test_togliendo_la_spunta_sparisce(self):
        dlg, _canvas = self._dialog_con_canvas()
        dlg.chk_ingombro.setChecked(True)
        dlg.chk_ingombro.setChecked(False)
        self.assertTrue(dlg._banda_ingombro.asGeometry().isEmpty())


if __name__ == "__main__":
    risultato = unittest.main(exit=False, verbosity=2)
    _qgs.exitQgis()
    sys.exit(0 if risultato.result.wasSuccessful() else 1)
