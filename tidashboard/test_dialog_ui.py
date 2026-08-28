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
                       QgsGeometry, QgsPointXY, QgsRectangle, Qgis,
                       QgsVectorFileWriter)
from qgis.PyQt.QtCore import QDate, Qt
from qgis.PyQt.QtWidgets import QMessageBox, QPushButton

# True: servono i widget veri, non la modalita' senza interfaccia.
_qgs = QgsApplication([], True)
_qgs.initQgis()

from tidashboard.tidashboard import TIDashboardDialog
from tidashboard import planimetria as P
# Il MODULO, non solo la classe: serve per sostituire temporaneamente le
# finestre di dialogo che una prova non puo' aprire davvero.
from tidashboard import tidashboard as cd

CX, CY = 2718000.0, 1082000.0
ITF_VERO = r"C:\Users\gabri\Downloads\5254010100\5254010100.itf"
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


def _layer(nome="beni_immobili_bene_immobile"):
    """Un layer di prova con il nome di una tabella VERA.

    Il nome non e' un dettaglio: planimetria.centro_planimetria centra il
    foglio solo sui layer di centramento (bene_immobile, punto_di_confine), e
    con un layer chiamato "prova" non troverebbe nessun centro. E' anche la
    situazione realistica - un piano si centra sui fondi, non su un layer
    qualunque che capita di avere aperto."""
    lyr = QgsVectorLayer("Polygon?crs=EPSG:2056", nome, "memory")
    f = QgsFeature(lyr.fields())
    f.setGeometry(QgsGeometry.fromPolygonXY([[
        QgsPointXY(CX - 50, CY - 50), QgsPointXY(CX + 50, CY - 50),
        QgsPointXY(CX + 50, CY + 50), QgsPointXY(CX - 50, CY + 50),
        QgsPointXY(CX - 50, CY - 50)]]))
    lyr.dataProvider().addFeatures([f])
    lyr.updateExtents()
    return lyr


class _IfaceFinto(object):
    """Un iface con un canvas VERO ma non collegato a QGIS: basta a provare
    tutto quello che la dialog fa sulla mappa, senza aprire l'applicazione."""

    def __init__(self):
        from qgis.gui import QgsMapCanvas
        from qgis.core import QgsCoordinateReferenceSystem
        self._canvas = QgsMapCanvas()
        self._canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:2056"))
        self._canvas.setExtent(QgsRectangle(CX - 300, CY - 300, CX + 300, CY + 300))

    def mapCanvas(self):
        return self._canvas


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


class TestCentroDaFondo(unittest.TestCase):
    """Il centro agganciato a un fondo restava per sempre, e l'unico segno era
    un messaggio che spariva alla ricerca successiva: si spostava la mappa, si
    premeva CREA PLANIMETRIA e usciva un foglio da tutt'altra parte."""

    @staticmethod
    def _fondo(x=2716000.0, y=1081000.0, dx=50.0, dy=50.0):
        from tidashboard.cerca_fondo import FondoTrovato
        return FondoTrovato(numero="99", sezione="03",
                            extent=(x, y, x + dx, y + dy),
                            centro=(x + dx / 2, y + dy / 2),
                            origine_geometria="geometria")

    def _con_fondo(self, dlg, f):
        dlg._risultati_fondo = [f]
        dlg.lista_fondi.addItem(f.etichetta)
        dlg.lista_fondi.setCurrentRow(0)

    def test_l_avviso_e_permanente_e_il_pulsante_compare(self):
        dlg = TIDashboardDialog()
        self.assertFalse(dlg.lbl_centro_fissato.isVisible())
        self.assertFalse(dlg.btn_sgancia_centro.isVisible())
        self._con_fondo(dlg, self._fondo())
        dlg.centra_planimetria_sul_fondo()
        self.assertIn("agganciato", dlg.lbl_centro_fissato.text())
        self.assertIn("99", dlg.lbl_centro_fissato.text())
        self.assertIsNotNone(dlg._centro_da_fondo)

    def test_sganciare_riporta_il_foglio_sulla_vista(self):
        dlg = TIDashboardDialog()
        self._con_fondo(dlg, self._fondo())
        dlg.centra_planimetria_sul_fondo()
        dlg.sgancia_centro()
        self.assertIsNone(dlg._centro_da_fondo)
        self.assertEqual(dlg.lbl_centro_fissato.text(), "")

    def test_il_centro_del_foglio_e_quello_del_fondo(self):
        dlg = TIDashboardDialog()
        self._con_fondo(dlg, self._fondo(2716000.0, 1081000.0, 100.0, 200.0))
        dlg.centra_planimetria_sul_fondo()
        c = dlg._centro_planimetria()
        self.assertAlmostEqual(c.x(), 2716050.0)
        self.assertAlmostEqual(c.y(), 1081100.0)


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
        self.assertIn("0.67", testo)
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
        self.assertIn("0.18 mm", testo)
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


class TestLocalitaMaiuscolo(unittest.TestCase):
    """Il maiuscolo sui nomi di località (raccomandazione cap. 5.7).

    Il capitolo dice «preferibilmente», non «devono»: la spunta è spenta di
    default, e accenderla non deve costare una nuova importazione."""

    def _layer_localita(self, campo="nome"):
        layer = QgsVectorLayer(
            "Point?crs=EPSG:2056&field=%s:string" % campo,
            "nomenclatura_posnome_di_localita", "memory")
        impostazioni = cd.QgsPalLayerSettings()
        impostazioni.fieldName = campo
        impostazioni.enabled = True
        layer.setLabeling(cd.QgsVectorLayerSimpleLabeling(impostazioni))
        layer.setLabelsEnabled(True)
        return layer

    def test_spenta_di_default(self):
        dlg = TIDashboardDialog()
        self.assertFalse(dlg.chk_localita_maiuscolo.isChecked())
        self.assertIn("5.7", dlg.chk_localita_maiuscolo.text())

    def test_il_tooltip_cita_la_norma_e_il_suo_limite(self):
        dlg = TIDashboardDialog()
        t = dlg.chk_localita_maiuscolo.toolTip()
        self.assertIn("borgate", t)
        self.assertIn("non viene modificato", t,
                      "deve dire che il dato non si tocca")

    def test_accendere_cambia_i_layer_gia_caricati(self):
        """Senza questo la spunta varrebbe solo alla prossima importazione,
        che su un file di produzione sono minuti."""
        dlg = TIDashboardDialog()
        layer = self._layer_localita()
        dlg.loaded_layers = [layer]
        dlg.chk_localita_maiuscolo.setChecked(True)
        imp = layer.labeling().settings()
        self.assertTrue(imp.isExpression)
        self.assertEqual(imp.fieldName, 'upper("nome")')

    def test_spegnere_riporta_al_campo(self):
        dlg = TIDashboardDialog()
        layer = self._layer_localita()
        dlg.loaded_layers = [layer]
        dlg.chk_localita_maiuscolo.setChecked(True)
        dlg.chk_localita_maiuscolo.setChecked(False)
        imp = layer.labeling().settings()
        self.assertFalse(imp.isExpression)
        self.assertEqual(imp.fieldName, "nome")

    def test_accendere_due_volte_non_annida_upper(self):
        """upper("upper(...)") non e' ne' un campo ne' un'espressione valida:
        l'etichetta uscirebbe vuota, e in mappa si vedrebbe solo che i nomi
        di localita' sono spariti."""
        dlg = TIDashboardDialog()
        layer = self._layer_localita()
        dlg.loaded_layers = [layer]
        dlg.chk_localita_maiuscolo.setChecked(True)
        dlg._aggiorna_maiuscolo_localita()      # come una seconda accensione
        self.assertEqual(layer.labeling().settings().fieldName, 'upper("nome")')

    def test_non_tocca_gli_altri_nomi_della_nomenclatura(self):
        """La norma parla di localita'. Nome locale e nome del luogo restano
        come sono - il primo sono 648 microtoponimi sul comune di prova."""
        dlg = TIDashboardDialog()
        altro = self._layer_localita()
        altro.setName("nomenclatura_posnome_locale")
        # il nome della tabella si legge dalla source, non dal nome del layer:
        # un layer di memoria non ha "layername=", quindi vale il nome.
        dlg.loaded_layers = [altro]
        dlg.chk_localita_maiuscolo.setChecked(True)
        self.assertFalse(altro.labeling().settings().isExpression)

    def test_il_campo_puo_venire_dal_join(self):
        """Sulla tabella Pos* il testo arriva dal join e si chiama
        "<tabella_padre>_nome": l'espressione deve citare QUEL campo."""
        dlg = TIDashboardDialog()
        layer = self._layer_localita(campo="nomenclatura_nome_di_localita_nome")
        dlg.loaded_layers = [layer]
        dlg.chk_localita_maiuscolo.setChecked(True)
        self.assertEqual(layer.labeling().settings().fieldName,
                         'upper("nomenclatura_nome_di_localita_nome")')


class TestDxfNonSovrascriveLOriginale(unittest.TestCase):
    """av2geobau apre il DXF con un FileOutputStream, che TRONCA il file di
    destinazione: se il campo DXF puntasse all'ITF, la conversione
    cancellerebbe il dato di consegna del Cantone e poi fallirebbe, perche'
    non avrebbe piu' niente da leggere. Ne' il jar ne' il plugin lo
    impedivano."""

    def _dlg(self, itf, dxf):
        dlg = TIDashboardDialog()
        dlg.txt_geobau_itf.setText(itf)
        dlg.txt_geobau_dxf.setText(dxf)
        return dlg

    def test_dxf_uguale_all_itf_viene_rifiutato(self):
        cartella = tempfile.mkdtemp()
        itf = os.path.join(cartella, "consegna.itf")
        with open(itf, "wb") as f:
            f.write(b"SCNT\r\nMTID INTERLIS1\r\nMODL MD01MUTI7MN95\r\n")
        prima = os.path.getsize(itf)
        dlg = self._dlg(itf, itf)
        chiamate = []
        vecchio = cd.QMessageBox.critical
        cd.QMessageBox.critical = staticmethod(
            lambda *a, **k: chiamate.append(a[2] if len(a) > 2 else ""))
        try:
            dlg.run_geobau()
        finally:
            cd.QMessageBox.critical = vecchio
        self.assertTrue(chiamate, "non ha avvisato")
        self.assertIn("sovrascriverebbe", chiamate[0])
        self.assertEqual(os.path.getsize(itf), prima,
                         "il file di partenza e' stato toccato")

    def test_lo_stesso_file_scritto_in_due_modi(self):
        """Lo stesso file scritto con un percorso relativo e uno assoluto e'
        sempre lo stesso file: il confronto va fatto sui percorsi RISOLTI,
        non sul testo che l'utente ha digitato."""
        cartella = tempfile.mkdtemp()
        itf = os.path.join(cartella, "consegna.itf")
        with open(itf, "wb") as f:
            f.write(b"SCNT\r\n")
        storto = os.path.join(cartella, "sotto", "..", "consegna.itf")
        os.makedirs(os.path.join(cartella, "sotto"), exist_ok=True)
        dlg = self._dlg(itf, storto)
        chiamate = []
        vecchio = cd.QMessageBox.critical
        cd.QMessageBox.critical = staticmethod(lambda *a, **k: chiamate.append(1))
        try:
            dlg.run_geobau()
        finally:
            cd.QMessageBox.critical = vecchio
        self.assertTrue(chiamate, "il percorso equivalente non e' stato visto")


class TestPulsanteConsegna(unittest.TestCase):
    """La consegna per QGIS Server: c'e' sempre, e si accende quando c'e'
    qualcosa da consegnare."""

    def test_spento_finche_non_ci_sono_layer(self):
        dlg = TIDashboardDialog()
        self.assertFalse(dlg.btn_consegna.isHidden())
        self.assertFalse(dlg.btn_consegna.isEnabled())
        self.assertIn("importazione riuscita", dlg.btn_consegna.toolTip())

    def test_si_accende_dopo_l_importazione(self):
        dlg = TIDashboardDialog()
        dlg.loaded_layers = [object()]
        dlg._aggiorna_pulsante_consegna()
        self.assertTrue(dlg.btn_consegna.isEnabled())

    def test_il_tooltip_dice_la_cosa_che_ci_si_dimentica(self):
        """Che il server non esegue il plugin e che i font vanno installati
        la'. E' l'unico passo che il plugin non puo' fare al posto di chi
        consegna, ed e' quello che fallisce in silenzio."""
        dlg = TIDashboardDialog()
        dlg.loaded_layers = [object()]
        dlg._aggiorna_pulsante_consegna()
        suggerimento = dlg.btn_consegna.toolTip()
        self.assertIn("NON esegue questo plugin", suggerimento)
        self.assertIn("font", suggerimento)

    def test_senza_geopackage_avvisa_e_non_chiede_la_cartella(self):
        """Se il GeoPackage non c'e', chiedere dove salvare sarebbe una
        domanda inutile fatta prima di scoprire che non si puo' fare niente."""
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText(r"C:\non\esiste\comune.gpkg")
        chiamate = []
        vecchia_cartella = cd.QFileDialog.getExistingDirectory
        cd.QFileDialog.getExistingDirectory = staticmethod(
            lambda *a, **k: chiamate.append("cartella") or "")
        prima = len(_avvisi)
        try:
            dlg.consegna_qgis_server()
        finally:
            cd.QFileDialog.getExistingDirectory = vecchia_cartella
        self.assertEqual(chiamate, [], "ha chiesto la cartella per niente")
        self.assertGreater(len(_avvisi), prima, "non ha avvisato di nulla")

    def test_annullando_la_cartella_non_succede_niente(self):
        dlg = TIDashboardDialog()
        gpkg = os.path.join(tempfile.mkdtemp(), "comune.gpkg")
        with open(gpkg, "wb"):
            pass
        dlg.txt_gpkg.setText(gpkg)
        chiamate = []
        vecchia_cartella = cd.QFileDialog.getExistingDirectory
        vecchia_consegna = cd._pubblica.consegna
        cd.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: "")
        cd._pubblica.consegna = lambda *a, **k: chiamate.append("consegna")
        try:
            dlg.consegna_qgis_server()
        finally:
            cd.QFileDialog.getExistingDirectory = vecchia_cartella
            cd._pubblica.consegna = vecchia_consegna
        self.assertEqual(chiamate, [])

    def test_la_consegna_intera_scrive_una_cartella_che_supera_il_controllo(self):
        """Il percorso buono, dal pulsante alla cartella scritta.

        Le prove del modulo chiamano consegna() direttamente; questa passa dal
        metodo della finestra, cioe' dal punto in cui si sbaglia a passare il
        GeoPackage o la cartella del plugin."""
        base = tempfile.mkdtemp()
        gpkg = os.path.join(base, "comune.gpkg")
        memoria = QgsVectorLayer(
            "Point?crs=EPSG:2056&field=numero:string",
            "beni_immobili_punto_di_confine", "memory")
        opzioni = QgsVectorFileWriter.SaveVectorOptions()
        opzioni.driverName = "GPKG"
        opzioni.layerName = "beni_immobili_punto_di_confine"
        QgsVectorFileWriter.writeAsVectorFormatV3(
            memoria, gpkg, QgsProject.instance().transformContext(), opzioni)
        layer = QgsVectorLayer(
            "%s|layername=beni_immobili_punto_di_confine" % gpkg, "punti", "ogr")
        self.assertTrue(layer.isValid())
        progetto = QgsProject.instance()
        progetto.addMapLayer(layer)

        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText(gpkg)
        dlg.loaded_layers = [layer]
        dlg._aggiorna_pulsante_consegna()
        dest = os.path.join(base, "consegna")
        vecchia_cartella = cd.QFileDialog.getExistingDirectory
        vecchia_info = cd.QMessageBox.information
        vecchio_avviso = cd.QMessageBox.warning
        # Si raccolgono ENTRAMBI i messaggi: quale dei due esca dipende dai
        # rilievi, e i rilievi dipendono da cosa hanno lasciato nel progetto
        # condiviso le altre prove. Cio' che deve valere in tutt'e due i casi
        # e' che all'utente sia stato detto qualcosa, e che ci sia dentro il
        # promemoria sui font.
        detto = []
        raccogli = staticmethod(
            lambda *a, **k: detto.append(a[2] if len(a) > 2 else ""))
        cd.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: dest)
        cd.QMessageBox.information = raccogli
        cd.QMessageBox.warning = raccogli
        try:
            dlg.consegna_qgis_server()
            # La sorgente si legge PRIMA di togliere il layer dal progetto:
            # removeMapLayer distrugge l'oggetto C++, e leggerlo dopo solleva
            # "wrapped C/C++ object has been deleted".
            sorgente_dopo = layer.source()
        finally:
            cd.QFileDialog.getExistingDirectory = vecchia_cartella
            cd.QMessageBox.information = vecchia_info
            cd.QMessageBox.warning = vecchio_avviso
            progetto.removeMapLayer(layer.id())

        for atteso in ("comune.gpkg", "consegna.qgz", "fonts", "symbols",
                       "LEGGIMI.txt"):
            self.assertIn(atteso, os.listdir(dest))
        from tidashboard import pubblica_progetto as PP
        rilievi, _dati = PP.verifica_consegna(dest)
        # NON si pretende zero rilievi: QgsProject.instance() e' uno solo per
        # tutta la suite e porta i layer temporanei lasciati dalle altre prove.
        # Il controllo li segnala, e ha ragione - un layer temporaneo sul
        # server sarebbe vuoto. Qui interessa che non ci sia niente di storto
        # in cio' che questa consegna ha scritto.
        nostri = [r for r in rilievi if "layer temporaneo" not in r]
        self.assertEqual(nostri, [])
        self.assertTrue(detto, "non ha detto all'utente che era pronta")
        self.assertIn("font", detto[0],
                      "il promemoria sui font e' l'unica cosa che il plugin "
                      "non puo' fare al posto di chi consegna")
        # E la sessione e' rimasta con il suo GeoPackage, non con la copia.
        self.assertTrue(sorgente_dopo.startswith(gpkg), sorgente_dopo)

    def test_la_clessidra_non_resta_addosso_a_qgis_se_qualcosa_va_storto(self):
        """setOverrideCursor senza restore lascia QGIS con la clessidra fino
        al riavvio: e' il genere di guasto che non si collega piu' alla sua
        causa."""
        from qgis.PyQt.QtWidgets import QApplication
        dlg = TIDashboardDialog()
        gpkg = os.path.join(tempfile.mkdtemp(), "comune.gpkg")
        with open(gpkg, "wb"):
            pass
        dlg.txt_gpkg.setText(gpkg)
        vecchia_cartella = cd.QFileDialog.getExistingDirectory
        vecchia_consegna = cd._pubblica.consegna
        vecchio_errore = cd.QMessageBox.critical

        def esplode(*a, **k):
            raise RuntimeError("disco pieno")

        cd.QFileDialog.getExistingDirectory = staticmethod(
            lambda *a, **k: tempfile.mkdtemp())
        cd._pubblica.consegna = esplode
        cd.QMessageBox.critical = staticmethod(lambda *a, **k: None)
        try:
            dlg.consegna_qgis_server()
        finally:
            cd.QFileDialog.getExistingDirectory = vecchia_cartella
            cd._pubblica.consegna = vecchia_consegna
            cd.QMessageBox.critical = vecchio_errore
        self.assertIsNone(QApplication.overrideCursor(),
                          "QGIS resterebbe con la clessidra addosso")


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


class TestWorkerDistrutto(unittest.TestCase):
    """Regressione segnalata da un utente: chiudendo la finestra dopo un
    lavoro finito usciva «RuntimeError: wrapped C/C++ object of type
    JavaWorker has been deleted». Da quando il worker si distrugge da solo
    (finished → deleteLater) l'attributo Python resta appeso a un oggetto C++
    già cancellato, e interrogarlo solleva - proprio in chiusura, dove un
    errore dà più fastidio."""

    def test_riconosce_un_oggetto_gia_distrutto(self):
        from tidashboard.tidashboard import _vivo, JavaWorker
        from PyQt6 import sip
        w = JavaWorker(["x"], "prova")
        self.assertTrue(_vivo(w))
        sip.delete(w)
        self.assertFalse(_vivo(w), "un guscio senza C++ non è vivo")

    def test_none_non_e_vivo(self):
        from tidashboard.tidashboard import _vivo
        self.assertFalse(_vivo(None))

    def test_la_chiusura_non_solleva_con_il_worker_distrutto(self):
        from tidashboard.tidashboard import JavaWorker
        from PyQt6 import sip
        from qgis.PyQt.QtGui import QCloseEvent
        dlg = TIDashboardDialog()
        dlg.worker = JavaWorker(["x"], "prova")
        sip.delete(dlg.worker)
        dlg.closeEvent(QCloseEvent())      # prima: RuntimeError


class TestConteggioEntitaDXF(unittest.TestCase):
    """Regressione: il DXF è fatto di COPPIE codice/valore, e leggere ogni riga
    per conto suo si rompe al primo VALORE uguale a "0" — cosa che capita di
    continuo, perché ogni VERTEX 2d finisce con 70/0 e ogni HATCH con 98/0."""

    def _dxf(self, righe):
        percorso = os.path.join(tempfile.mkdtemp(), "prova.dxf")
        with open(percorso, "w", encoding="latin-1") as f:
            f.write("\n".join(righe) + "\n")
        return percorso

    def test_i_vertici_non_si_mangiano_l_entita_successiva(self):
        righe = ["  2", "ENTITIES"]
        for _ in range(3):
            # un VERTEX come lo scrive il nostro writer: finisce con 70 -> 0
            righe += ["  0", "VERTEX", "  8", "01611", " 10", "2717000.0",
                      " 20", "1082000.0", " 70", "0"]
        righe += ["  0", "SEQEND", "  8", "01611", "  0", "ENDSEC"]
        stats = TIDashboardDialog._count_dxf_entities_stream(
            TIDashboardDialog.__new__(TIDashboardDialog), self._dxf(righe))
        self.assertEqual(stats.get("VERTEX"), 3, "i vertici vanno contati tutti")
        self.assertEqual(stats.get("SEQEND"), 1)
        self.assertEqual(stats["_total"], 4)

    def test_il_campionamento_dei_layer_non_prende_numeri(self):
        righe = ["  2", "ENTITIES",
                 "  0", "TEXT", "  8", "TI_NUMERO_PUNTO_DI_CONFINE",
                 " 40", "0.9", " 73", "0",
                 "  0", "ENDSEC"]
        stats = TIDashboardDialog._count_dxf_entities_stream(
            TIDashboardDialog.__new__(TIDashboardDialog), self._dxf(righe))
        self.assertEqual(stats["_layers_sample"], ["TI_NUMERO_PUNTO_DI_CONFINE"])


class TestInventarioSenzaSchianti(unittest.TestCase):
    """Regressione: il conteggio dell'ITF gira in un QThread, e tenerne il
    riferimento in un attributo solo lo perdeva al secondo file. PyQt
    distruggeva l'oggetto C++ mentre girava e Qt chiamava abort(): QGIS si
    chiudeva. Bastava trascinare due .itf insieme, perché dropEvent scrive nel
    campo due volte di fila."""

    def _due_file(self):
        cartella = tempfile.mkdtemp()
        percorsi = []
        for nome in ("uno.itf", "due.itf"):
            p = os.path.join(cartella, nome)
            with open(p, "w") as f:
                f.write("MODL non importa, basta che il file esista\n")
            percorsi.append(p)
        return percorsi

    def _threads(self, dlg):
        """I thread vivi appesi alla finestra. Non c'e' piu' una lista da
        interrogare: il padre Qt E' il registro, e questo lo dimostra."""
        from tidashboard.tidashboard import InventarioWorker
        return dlg.findChildren(InventarioWorker)

    def test_scrivere_il_percorso_non_lancia_una_lettura_per_carattere(self):
        # Il campo cambia a ogni tasto. Con l'attesa, finche' si scrive non
        # parte niente: e' il ritardo che toglie l'occasione allo schianto,
        # invece di gestirne le conseguenze.
        a, _b = self._due_file()
        dlg = TIDashboardDialog()
        for i in range(1, len(a) + 1):
            dlg.txt_itf.setText(a[:i])
        self.assertEqual(self._threads(dlg), [], "non doveva partire niente")
        self.assertTrue(dlg._timer_inventario.isActive(), "l'attesa doveva essere in corso")

    def test_due_file_trascinati_insieme_fanno_una_lettura_sola(self):
        # dropEvent scrive nel campo due volte di fila: e' l'innesco che
        # faceva chiudere QGIS. Ora le due modifiche si fondono, e quella che
        # vale e' l'ultima.
        a, b = self._due_file()
        dlg = TIDashboardDialog()
        dlg.txt_itf.setText(a)
        dlg.txt_itf.setText(b)
        self.assertEqual(self._threads(dlg), [])
        dlg._esegui_inventario()                    # come se l'attesa fosse scaduta
        vivi = self._threads(dlg)
        self.assertEqual(len(vivi), 1)
        self.assertEqual(dlg._inventario_atteso, b, "doveva valere l'ultimo file")
        vivi[0].wait(10000)

    @unittest.skipUnless(os.path.isfile(ITF_VERO), "ITF di prova non presente")
    def test_il_thread_e_di_qt_non_di_python(self):
        # Il nocciolo della correzione: nessun riferimento Python al thread, e
        # deve restare vivo lo stesso perche' il padre e' la finestra. Senza
        # padre, buttare il riferimento uccide il processo (codice 127).
        dlg = TIDashboardDialog()
        dlg.txt_itf.setText(ITF_VERO)
        dlg._esegui_inventario()
        vivi = self._threads(dlg)
        self.assertEqual(len(vivi), 1)
        self.assertTrue(vivi[0].isRunning())
        self.assertIs(vivi[0].parent(), dlg)
        import gc
        gc.collect()                                 # niente riferimenti nostri
        ancora = self._threads(dlg)
        self.assertEqual(len(ancora), 1, "il thread e' sparito col garbage collector")
        ancora[0].wait(30000)

    def test_lo_stesso_file_non_fa_ripartire_il_conteggio(self):
        a, _b = self._due_file()
        dlg = TIDashboardDialog()
        dlg.txt_itf.setText(a)
        dlg._esegui_inventario()
        for w in self._threads(dlg):
            w.wait(10000)
        dlg.txt_itf.setText(a + " ")          # .strip() lo rende lo stesso file
        dlg._esegui_inventario()
        self.assertEqual(dlg._inventario_atteso, a)

    def test_un_file_illeggibile_non_rompe_niente(self):
        a, _b = self._due_file()
        dlg = TIDashboardDialog()
        dlg._inventario_atteso = a          # è il file che stiamo aspettando
        dlg._mostra_inventario(a, None, None, "")     # errore con messaggio vuoto
        self.assertIn("non leggibile", dlg.lbl_inventario.text())


class TestErroriValidazioneSullaMappa(unittest.TestCase):
    """La scheda «Errori nei dati» dice COSA non va, il layer dice DOVE.

    Le righe usate qui sono quelle vere, prodotte da ili2gpkg importando
    5254010100.itf: due violazioni di unicità su Punto_di_confine e otto
    avvertenze «arc is straight», che la coordinata ce l'hanno già dentro."""

    RIGA_UNICITA = ("Error: line 1183065: MD01MUTI7MN95.Beni_immobili.Punto_di_confine: "
                    "tid 46560: Unique constraint "
                    "MD01MUTI7MN95.Beni_immobili.Punto_di_confine.Constraint2 is "
                    "violated! Values TI63201, 140602 already exist in Object: 40497")
    RIGA_ARCO = "Warning: arc is straight at (2719339.225, 1081435.757, NaN)"

    def _dialogo(self):
        dlg = TIDashboardDialog()
        dlg._import_unique_errors = []
        dlg._punti_validazione = []
        return dlg

    def test_l_avvertenza_con_coordinata_finisce_sulla_mappa(self):
        dlg = self._dialogo()
        dlg._on_import_log_line(self.RIGA_ARCO)
        self.assertEqual(len(dlg._punti_validazione), 1)
        p = dlg._punti_validazione[0]
        self.assertEqual(p["livello"], "avviso")
        self.assertAlmostEqual(p["x"], 2719339.225, places=3)
        self.assertAlmostEqual(p["y"], 1081435.757, places=3)

    def test_la_violazione_di_unicita_non_si_conta_due_volte(self):
        # Ha la sua strada (le coordinate si leggono nell'ITF): non deve
        # entrare anche dalla porta dei messaggi con coordinata.
        dlg = self._dialogo()
        dlg._on_import_log_line(self.RIGA_UNICITA)
        self.assertEqual(len(dlg._import_unique_errors), 1)
        self.assertEqual(dlg._punti_validazione, [])

    def test_le_righe_informative_non_sporcano_la_mappa(self):
        dlg = self._dialogo()
        dlg._on_import_log_line("Info: compiling MD01MUTI7MN95.ili")
        dlg._on_import_log_line("Info: 2719339.225 1081435.757 letta")
        self.assertEqual(dlg._punti_validazione, [])

    def test_il_layer_nasce_solo_se_c_e_qualcosa_da_mostrare(self):
        dlg = self._dialogo()
        self.assertIsNone(dlg.crea_layer_errori_validazione())

    def test_la_stessa_segnalazione_ripetuta_fa_un_punto_solo(self):
        # Sul comune di prova le otto avvertenze «arc is straight» stanno su
        # due posizioni sole, ripetute quattro volte ciascuna: impilare punti
        # identici rende ambiguo il clic sulla mappa e non aggiunge nulla.
        dlg = self._dialogo()
        for _ in range(4):
            dlg._on_import_log_line(self.RIGA_ARCO)
        self.assertEqual(len(dlg._punti_validazione), 4)
        layer = dlg.crea_layer_errori_validazione()
        self.assertEqual(layer.featureCount(), 1)
        QgsProject.instance().removeMapLayer(layer.id())

    def test_il_layer_ha_un_punto_per_problema_e_gli_attributi_giusti(self):
        dlg = self._dialogo()
        dlg._on_import_log_line(self.RIGA_ARCO)
        dlg._punti_validazione.append({
            "livello": "errore", "tipo": "vincolo di unicità",
            "messaggio": "Constraint2: valori duplicati TI63201, 140602",
            "x": 2720017.525, "y": 1080964.798, "tid": "46560", "riga": 1183065})
        layer = dlg.crea_layer_errori_validazione()
        self.assertIsNotNone(layer)
        self.assertTrue(layer.isValid())
        self.assertEqual(layer.featureCount(), 2)
        self.assertEqual(layer.crs().authid(), "EPSG:2056")
        livelli = sorted(f["livello"] for f in layer.getFeatures())
        self.assertEqual(livelli, ["avviso", "errore"])
        errore = [f for f in layer.getFeatures() if f["livello"] == "errore"][0]
        self.assertEqual(errore["tid"], "46560")
        self.assertEqual(errore["riga"], 1183065)
        self.assertAlmostEqual(errore.geometry().asPoint().x(), 2720017.525, places=3)
        QgsProject.instance().removeMapLayer(layer.id())


class _EventoFinto:
    """Il minimo che StrumentoSpostaFoglio chiede a un evento del canvas:
    quale tasto e in che punto del terreno. Basta per provare la logica del
    trascinamento senza sintetizzare eventi Qt veri."""

    def __init__(self, x, y, tasto=Qt.MouseButton.LeftButton):
        self._p = QgsPointXY(x, y)
        self._t = tasto

    def mapPoint(self):
        return self._p

    def button(self):
        return self._t


class TestTrascinamentoDelFoglio(unittest.TestCase):
    """Il foglio si afferra dall'interno e si porta dove serve. Prima si
    spostava la MAPPA finché il centro della vista non capitava al punto
    giusto: un movimento al contrario."""

    def _strumento(self):
        from qgis.gui import QgsMapCanvas
        from tidashboard.tidashboard import StrumentoSpostaFoglio
        dlg = TIDashboardDialog()
        canvas = QgsMapCanvas()
        canvas.setExtent(QgsRectangle(CX - 500, CY - 500, CX + 500, CY + 500))
        # Il canvas va tenuto in vita: e' il padre C++ dello strumento, e se lo
        # si lascia morire alla fine di questo metodo il wrapper Python dello
        # strumento resta appeso a un oggetto distrutto.
        dlg._canvas_di_prova = canvas
        dlg._centro_da_fondo = QgsPointXY(CX, CY)
        return dlg, StrumentoSpostaFoglio(canvas, dlg)

    def test_afferrando_da_dentro_il_foglio_segue_il_puntatore(self):
        dlg, tool = self._strumento()
        # click 10 m a destra del centro, poi trascino di 30 m verso est
        tool.canvasPressEvent(_EventoFinto(CX + 10, CY))
        tool.canvasMoveEvent(_EventoFinto(CX + 40, CY))
        self.assertAlmostEqual(dlg._centro_da_fondo.x(), CX + 30, places=6)
        self.assertAlmostEqual(dlg._centro_da_fondo.y(), CY, places=6)

    def test_il_foglio_non_salta_sotto_il_puntatore(self):
        # Afferrando da un angolo, il centro NON deve schizzare sul punto
        # cliccato: si tiene lo scarto fra click e centro.
        dlg, tool = self._strumento()
        tool.canvasPressEvent(_EventoFinto(CX + 30, CY + 20))
        self.assertAlmostEqual(dlg._centro_da_fondo.x(), CX, places=6)
        tool.canvasMoveEvent(_EventoFinto(CX + 30, CY + 20))
        self.assertAlmostEqual(dlg._centro_da_fondo.x(), CX, places=6)
        self.assertAlmostEqual(dlg._centro_da_fondo.y(), CY, places=6)

    def test_fuori_dal_rettangolo_non_si_afferra_niente(self):
        # Il tasto sinistro fuori dal foglio resta libero per la navigazione.
        dlg, tool = self._strumento()
        tool.canvasPressEvent(_EventoFinto(CX + 100000, CY))
        tool.canvasMoveEvent(_EventoFinto(CX + 100030, CY))
        self.assertAlmostEqual(dlg._centro_da_fondo.x(), CX, places=6)

    def test_il_tasto_destro_non_trascina(self):
        dlg, tool = self._strumento()
        tool.canvasPressEvent(_EventoFinto(CX, CY, Qt.MouseButton.RightButton))
        tool.canvasMoveEvent(_EventoFinto(CX + 50, CY))
        self.assertAlmostEqual(dlg._centro_da_fondo.x(), CX, places=6)

    def test_al_rilascio_la_posizione_resta(self):
        dlg, tool = self._strumento()
        tool.canvasPressEvent(_EventoFinto(CX, CY))
        tool.canvasReleaseEvent(_EventoFinto(CX + 25, CY - 15))
        self.assertAlmostEqual(dlg._centro_da_fondo.x(), CX + 25, places=6)
        self.assertAlmostEqual(dlg._centro_da_fondo.y(), CY - 15, places=6)
        # e un movimento successivo senza premere non sposta piu' niente
        tool.canvasMoveEvent(_EventoFinto(CX + 900, CY))
        self.assertAlmostEqual(dlg._centro_da_fondo.x(), CX + 25, places=6)


class TestScalaDiStampa(unittest.TestCase):
    """La scala di stampa la sceglie l'utente: quella della vista non c'entra,
    e nemmeno il prodotto puo' scavalcarla.

    Il difetto: create_layout_bp aveva 1:5000 scritto nel codice in due punti
    (setScale e il titolo) e non guardava affatto il menu "Scala". Chi
    sceglieva 1:1000 riceveva un foglio 1:5000."""

    def _dialog_bp(self):
        dlg = TIDashboardDialog()
        dlg.combo_product.setCurrentIndex(
            dlg.combo_product.findData("bp"))
        return dlg

    def test_il_layout_pb_usa_la_scala_scelta_non_1_5000(self):
        from qgis.core import QgsLayoutItemMap
        dlg = self._dialog_bp()
        dlg.combo_scala.setCurrentText("1:1000")
        dlg.loaded_layers = [_layer()]
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
        dlg.create_layout_bp()
        layout = QgsProject.instance().layoutManager().layoutByName(
            "Basisplan_PB-MU_1-1000")
        self.assertIsNotNone(layout, "il layout non e' stato registrato")
        mappe = [i for i in layout.items() if isinstance(i, QgsLayoutItemMap)]
        self.assertEqual(len(mappe), 1)
        self.assertAlmostEqual(mappe[0].scale(), 1000.0, places=3)
        testi = [i.text() for i in layout.items() if hasattr(i, "text")]
        self.assertTrue(any("Scala: 1:1000" in t for t in testi),
                        "il titolo non dichiara la scala usata: %s" % testi)
        QgsProject.instance().layoutManager().removeLayout(layout)

    def test_passando_a_pb_mu_la_scala_parte_da_1_5000(self):
        dlg = TIDashboardDialog()
        # La dialog ricorda la scala fra una sessione e l'altra (QgsSettings):
        # si riparte da uno stato noto, com'e' alla primissima apertura.
        dlg.combo_scala.setCurrentText("1:1000")
        dlg._scala_scelta_a_mano = False
        dlg.combo_product.setCurrentIndex(dlg.combo_product.findData("bp"))
        self.assertEqual(dlg.combo_scala.currentText(), "1:5000")

    def test_una_scala_ripristinata_vale_come_scelta(self):
        """Il ripristino delle impostazioni non deve poter essere scavalcato
        dal cambio di prodotto: la scala salvata e' pur sempre una scelta,
        fatta in una sessione precedente."""
        from qgis.core import QgsSettings
        from tidashboard.tidashboard import NOME_PLUGIN
        chiave = "%s/scala" % NOME_PLUGIN
        impostazioni = QgsSettings()
        prima = impostazioni.value(chiave, None)
        impostazioni.setValue(chiave, "1:250")
        try:
            dlg = TIDashboardDialog()
            dlg._scala_scelta_a_mano = False
            dlg._ripristina_impostazioni()
            self.assertEqual(dlg.combo_scala.currentText(), "1:250")
            self.assertTrue(dlg._scala_scelta_a_mano)
            dlg.combo_product.setCurrentIndex(dlg.combo_product.findData("bp"))
            self.assertEqual(dlg.combo_scala.currentText(), "1:250")
        finally:
            if prima is None:
                impostazioni.remove(chiave)
            else:
                impostazioni.setValue(chiave, prima)

    def test_una_scala_scelta_a_mano_non_viene_sovrascritta(self):
        dlg = TIDashboardDialog()
        dlg.combo_scala.setCurrentText("1:500")
        dlg._scala_scelta_dall_utente()      # cio' che fa il segnale activated
        dlg.combo_product.setCurrentIndex(dlg.combo_product.findData("bp"))
        self.assertEqual(dlg.combo_scala.currentText(), "1:500")


class TestScalaFoglioIndipendenteDallaVista(unittest.TestCase):
    """Il foglio esce alla scala scelta qualunque sia lo zoom della mappa."""

    def test_la_scala_del_foglio_e_quella_scelta(self):
        from qgis.core import QgsLayoutItemMap
        prog = QgsProject.instance()
        lyr = _layer()
        prog.addMapLayer(lyr)
        for scala in P.SCALE_UFFICIALI_MU:
            layout = P.crea_planimetria(
                prog, [lyr], QgsPointXY(CX, CY), scala,
                formato="A4 orizzontale", comune="Prova",
                nome="scala_%d" % scala, log=lambda *a, **k: None)
            mappa = [i for i in layout.items()
                     if isinstance(i, QgsLayoutItemMap)][0]
            self.assertAlmostEqual(mappa.scale(), float(scala), places=3)
            # e l'estensione e' quella che quella scala impone sul foglio
            larghezza_mm, _h = P.area_mappa("A4 orizzontale")
            self.assertAlmostEqual(mappa.extent().width(),
                                   larghezza_mm / 1000.0 * scala, places=3)
            prog.layoutManager().removeLayout(layout)
        prog.removeMapLayer(lyr.id())


class TestFinestraScaricaMU(unittest.TestCase):
    """La finestra di scaricamento dal portale cantonale. L'elenco arriva da un
    finto worker: qui si prova l'interfaccia, non la rete (per la rete e il
    formato della pagina c'e' test_scarica_mu.py)."""

    def _finestra(self, comuni=None):
        from tidashboard.tidashboard import DialogScaricaMU
        from tidashboard import scarica_mu as S
        # avvia_indice=False: niente chiamata al portale nei test.
        f = DialogScaricaMU(None, tempfile.mkdtemp(), avvia_indice=False)
        if comuni is None:
            comuni = [S.ComuneMU("5304000101.zip", "Bosco Gurin", "30.07.2026",
                                 "904.63 KB"),
                      S.ComuneMU("5254010100.zip", "Mendrisio", "14.08.2026",
                                 "11.21 MB")]
        f._indice_pronto(comuni, "")
        return f

    def test_l_elenco_si_riempie_e_il_pulsante_parte_spento(self):
        f = self._finestra()
        self.assertEqual(f.elenco.count(), 2)
        self.assertFalse(f.btn_scarica.isEnabled(),
                         "senza un comune scelto non c'e' niente da scaricare")
        f.elenco.setCurrentRow(0)
        self.assertTrue(f.btn_scarica.isEnabled())

    def test_il_filtro_cerca_per_nome_e_per_numero(self):
        f = self._finestra()
        f.txt_filtro.setText("mendri")
        self.assertEqual(f.elenco.count(), 1)
        f.txt_filtro.setText("5304")
        self.assertEqual(f.elenco.count(), 1)
        self.assertIn("Bosco Gurin", f.elenco.item(0).text())
        f.txt_filtro.setText("")
        self.assertEqual(f.elenco.count(), 2)

    def test_il_portale_muto_lo_dice_e_lascia_l_indirizzo(self):
        """Se il portale non risponde la finestra non deve restare a fissare
        una lista vuota senza spiegazioni."""
        from tidashboard import scarica_mu as S
        f = self._finestra(comuni=None)
        f._indice_pronto(None, "timed out")
        self.assertIn("timed out", f.lbl_stato.text())
        self.assertIn(S.URL_INDICE, f.lbl_stato.text())
        self.assertFalse(f.btn_scarica.isEnabled())

    def test_una_cartella_che_non_esiste_ferma_lo_scaricamento(self):
        f = self._finestra()
        f.elenco.setCurrentRow(0)
        f.txt_cartella.setText(r"C:\questa\non\esiste")
        prima = len(_avvisi)
        f._scarica()
        self.assertGreater(len(_avvisi), prima)
        self.assertIsNone(f._scarico, "non deve partire nessun thread")

    def test_il_modello_sbagliato_viene_segnalato(self):
        """Il caso che rende utile il controllo: un ITF nel modello federale
        (geodienste.ch) scarica benissimo e poi non si importa."""
        from tidashboard import scarica_mu as S
        cartella = tempfile.mkdtemp()
        percorso = os.path.join(cartella, "x.itf")
        with open(percorso, "wb") as fh:
            fh.write(b"SCNT\r\nMTID INTERLIS1\r\nMODL MD01MUCH24MN95I\r\n")
        f = self._finestra()
        prima = len(_avvisi)
        f._scarico_finito(percorso, "")
        self.assertGreater(len(_avvisi), prima)
        self.assertIn("MD01MUCH24MN95I", _avvisi[-1])
        self.assertEqual(f.percorso_itf, percorso,
                         "il file c'e' ed e' integro: si tiene, con l'avviso")

    def test_il_modello_giusto_non_disturba(self):
        from tidashboard import scarica_mu as S
        cartella = tempfile.mkdtemp()
        percorso = os.path.join(cartella, "y.itf")
        with open(percorso, "wb") as fh:
            fh.write(b"SCNT\r\nMTID INTERLIS1\r\nMODL %s\r\n"
                     % S.MODELLO_ATTESO.encode())
        f = self._finestra()
        prima = len(_avvisi)
        f._scarico_finito(percorso, "")
        self.assertEqual(len(_avvisi), prima)
        self.assertEqual(f.percorso_itf, percorso)


class TestCentroPerCoordinate(unittest.TestCase):
    """Il campo delle coordinate: riconoscimento, riscontro e centraggio.

    Qui la trasformazione WGS84 e' quella VERA di QGIS - il modulo puro si
    prova senza (test_coordinate.py), ma il collegamento alla proiezione e'
    proprio la parte che quel test non puo' vedere.
    """

    def test_il_pulsante_resta_spento_finche_non_si_capisce(self):
        dlg = TIDashboardDialog()
        self.assertFalse(dlg.btn_coordinate.isEnabled())
        dlg.txt_coordinate.setText("2718")
        self.assertFalse(dlg.btn_coordinate.isEnabled())
        dlg.txt_coordinate.setText("2718000 1082000")
        self.assertTrue(dlg.btn_coordinate.isEnabled())

    def test_il_riscontro_dice_cosa_ha_capito(self):
        """Tre sistemi riconosciuti dall'ordine di grandezza: senza un
        riscontro l'utente scoprirebbe solo dopo di aver incollato delle MN03
        dove pensava di mettere delle MN95."""
        dlg = TIDashboardDialog()
        dlg.txt_coordinate.setText("2718000 1082000")
        self.assertIn("MN95", dlg.lbl_coordinate.text())
        dlg.txt_coordinate.setText("718000 82000")
        self.assertIn("MN03", dlg.lbl_coordinate.text())

    def test_i_gon_vengono_rifiutati_spiegando_perche(self):
        dlg = TIDashboardDialog()
        dlg.txt_coordinate.setText("137.5 gon")
        self.assertFalse(dlg.btn_coordinate.isEnabled())
        self.assertIn("angolare", dlg.lbl_coordinate.text())

    def test_il_campo_vuoto_non_dice_niente(self):
        dlg = TIDashboardDialog()
        dlg.txt_coordinate.setText("2718000 1082000")
        dlg.txt_coordinate.setText("")
        self.assertEqual(dlg.lbl_coordinate.text(), "")
        self.assertFalse(dlg.btn_coordinate.isEnabled())

    def test_centrare_aggancia_il_foglio(self):
        dlg = TIDashboardDialog()
        dlg._iface = None
        dlg.txt_coordinate.setText("2718000 1082000")
        dlg.centra_su_coordinate()
        self.assertIsNotNone(dlg._centro_da_fondo)
        self.assertAlmostEqual(dlg._centro_da_fondo.x(), 2718000.0, places=3)
        self.assertAlmostEqual(dlg._centro_da_fondo.y(), 1082000.0, places=3)

    def test_centrare_scioglie_il_fondo_agganciato(self):
        """Il rettangolo si colora in base al fondo agganciato: tenerlo dopo
        aver spostato il centro altrove direbbe una cosa falsa."""
        dlg = TIDashboardDialog()
        dlg._iface = None
        dlg._fondo_ancorato = object()
        dlg.txt_coordinate.setText("2718000 1082000")
        dlg.centra_su_coordinate()
        self.assertIsNone(dlg._fondo_ancorato)

    def test_coordinate_illeggibili_non_spostano_niente(self):
        dlg = TIDashboardDialog()
        dlg._iface = None
        dlg._centro_da_fondo = None
        dlg.txt_coordinate.setText("Mendrisio")
        prima = len(_avvisi)
        dlg.centra_su_coordinate()
        self.assertIsNone(dlg._centro_da_fondo)
        self.assertGreater(len(_avvisi), prima)

    def test_il_wgs84_passa_dalla_proiezione_di_qgis(self):
        """45.87 N, 8.98 E e' il Mendrisiotto: la trasformazione vera deve
        riportarlo dentro i limiti di MN95, non da qualche altra parte."""
        dlg = TIDashboardDialog()
        punto = dlg._trasforma_wgs84(8.98, 45.87)
        self.assertIsNotNone(punto, "la proiezione EPSG:4326 -> 2056 deve esserci")
        est, nord = punto
        self.assertTrue(2480000.0 <= est <= 2840000.0, "E fuori MN95: %.1f" % est)
        self.assertTrue(1070000.0 <= nord <= 1300000.0, "N fuori MN95: %.1f" % nord)
        # Mendrisio sta nell'angolo sud del cantone: si controlla che la
        # conversione cada davvero li' e non a caso dentro i limiti.
        self.assertAlmostEqual(est, 2718000.0, delta=8000.0)
        self.assertAlmostEqual(nord, 1082000.0, delta=8000.0)

    def test_dal_campo_al_centro_passando_per_i_gradi(self):
        dlg = TIDashboardDialog()
        dlg._iface = None
        dlg.txt_coordinate.setText("45.87 8.98")
        self.assertIn("WGS84", dlg.lbl_coordinate.text())
        dlg.centra_su_coordinate()
        self.assertIsNotNone(dlg._centro_da_fondo)
        self.assertAlmostEqual(dlg._centro_da_fondo.x(), 2718000.0, delta=8000.0)


class TestRisultatiSullaMappa(unittest.TestCase):
    """I risultati della ricerca evidenziati tutti insieme sul canvas.

    Serve al caso "lo stesso numero esiste in piu' sezioni": l'elenco dice
    QUALI sono, la mappa dice DOVE stanno l'uno rispetto all'altro.
    """

    class _FondoFinto:
        def __init__(self, numero, x, y, contorno=None, senza_geometria=False):
            self.numero = numero
            self.sezione = "01"
            self.etichetta = numero
            self.contorno = contorno
            self.centro = None if senza_geometria else (x, y)
            self.extent = (None if senza_geometria
                           else (x - 50, y - 50, x + 50, y + 50))

    def _dialog_con_canvas(self):
        dlg = TIDashboardDialog()
        dlg._iface = _IfaceFinto()
        return dlg

    def test_una_banda_per_ogni_risultato(self):
        dlg = self._dialog_con_canvas()
        fondi = [self._FondoFinto("452", CX, CY),
                 self._FondoFinto("452", CX + 500, CY + 500),
                 self._FondoFinto("452", CX - 400, CY)]
        dlg._evidenzia_risultati(fondi)
        self.assertEqual(len(dlg._bande_risultati), 3)

    def test_una_nuova_ricerca_spegne_la_precedente(self):
        """Lasciare accesi i risultati di prima accanto a quelli nuovi e' un
        modo sicuro di far guardare il fondo sbagliato."""
        dlg = self._dialog_con_canvas()
        dlg._evidenzia_risultati([self._FondoFinto("452", CX, CY),
                                  self._FondoFinto("452", CX + 100, CY)])
        self.assertEqual(len(dlg._bande_risultati), 2)
        dlg._evidenzia_risultati([self._FondoFinto("99", CX, CY)])
        self.assertEqual(len(dlg._bande_risultati), 1)
        dlg._evidenzia_risultati([])
        self.assertEqual(len(dlg._bande_risultati), 0)

    def test_un_fondo_senza_geometria_non_si_inventa(self):
        """Esiste nei dati ma non si sa dove sia: meglio non disegnarlo che
        metterlo in un posto qualunque."""
        dlg = self._dialog_con_canvas()
        fondi = [self._FondoFinto("452", CX, CY),
                 self._FondoFinto("453", 0, 0, senza_geometria=True)]
        dlg._evidenzia_risultati(fondi)
        self.assertEqual(len(dlg._bande_risultati), 1)

    def test_il_contorno_vero_batte_il_rettangolo(self):
        from qgis.core import QgsPointXY
        dlg = self._dialog_con_canvas()
        contorno = [QgsPointXY(CX, CY), QgsPointXY(CX + 30, CY),
                    QgsPointXY(CX + 30, CY + 10), QgsPointXY(CX, CY)]
        geom = dlg._geometria_del_fondo(
            self._FondoFinto("452", CX, CY, contorno=contorno))
        self.assertEqual(len(geom.asPolygon()[0]), 4,
                         "con il contorno si disegna il fondo, non il suo riquadro")

    def test_un_fondo_ridotto_a_un_punto_resta_visibile(self):
        """Ripiego su PosFondo: l'estensione e' larga zero e la banda
        sarebbe invisibile."""
        dlg = self._dialog_con_canvas()
        f = self._FondoFinto("452", CX, CY)
        f.extent = (CX, CY, CX, CY)
        geom = dlg._geometria_del_fondo(f)
        self.assertGreater(geom.boundingBox().width(), 0.0)

    def test_il_selezionato_si_colora_diversamente(self):
        dlg = self._dialog_con_canvas()
        dlg._risultati_fondo = [self._FondoFinto("452", CX, CY),
                                self._FondoFinto("452", CX + 500, CY)]
        for f in dlg._risultati_fondo:
            dlg.lista_fondi.addItem(f.etichetta)
        dlg._evidenzia_risultati(dlg._risultati_fondo)
        dlg.lista_fondi.setCurrentRow(1)
        colori = [b.strokeColor().name() for b in dlg._bande_risultati]
        self.assertEqual(colori[1], dlg.C_RISULTATO_SCELTO.name())
        self.assertEqual(colori[0], dlg.C_RISULTATO.name())

    def test_la_corrispondenza_salta_i_fondi_senza_posizione(self):
        """Le bande sono meno dei risultati quando qualcuno non ha geometria:
        accoppiarle per indice colorerebbe il fondo sbagliato."""
        dlg = self._dialog_con_canvas()
        dlg._risultati_fondo = [
            self._FondoFinto("452", 0, 0, senza_geometria=True),
            self._FondoFinto("452", CX, CY),
        ]
        for f in dlg._risultati_fondo:
            dlg.lista_fondi.addItem(f.etichetta)
        dlg._evidenzia_risultati(dlg._risultati_fondo)
        dlg.lista_fondi.setCurrentRow(1)
        self.assertEqual(len(dlg._bande_risultati), 1)
        self.assertEqual(dlg._bande_risultati[0].strokeColor().name(),
                         dlg.C_RISULTATO_SCELTO.name(),
                         "l'unica banda e' del secondo fondo, che e' quello scelto")

    def test_con_un_risultato_solo_la_vista_non_si_muove(self):
        """Con un risultato ci sono gia' i due comandi espliciti: spostare la
        vista senza che l'utente l'abbia chiesto sarebbe una sorpresa."""
        dlg = self._dialog_con_canvas()
        prima = dlg._iface.mapCanvas().extent()
        dlg._inquadra_tutti_i_risultati([self._FondoFinto("452", CX, CY)])
        self.assertEqual(dlg._iface.mapCanvas().extent(), prima)

    def test_con_piu_risultati_la_vista_li_contiene_tutti(self):
        dlg = self._dialog_con_canvas()
        fondi = [self._FondoFinto("452", CX, CY),
                 self._FondoFinto("452", CX + 2000, CY + 1500)]
        dlg._inquadra_tutti_i_risultati(fondi)
        vista = dlg._iface.mapCanvas().extent()
        for f in fondi:
            self.assertTrue(vista.contains(QgsRectangle(*f.extent)),
                            "il risultato %s resta fuori dalla vista" % f.numero)

    def test_chiudere_la_finestra_spegne_le_bande(self):
        """Restano sul canvas di QGIS finche' qualcuno non le spegne, e chiusa
        la finestra non c'e' piu' nessuno che possa farlo."""
        from qgis.PyQt.QtGui import QCloseEvent
        dlg = self._dialog_con_canvas()
        dlg._evidenzia_risultati([self._FondoFinto("452", CX, CY)])
        self.assertEqual(len(dlg._bande_risultati), 1)
        dlg.closeEvent(QCloseEvent())
        self.assertEqual(dlg._bande_risultati, [])


class TestManigliaSulCanvas(unittest.TestCase):
    """I tre gesti dello strumento: sposta, ruota, doppio clic.

    Il trascinamento c'era gia'; qui si provano la maniglia di rotazione e lo
    zoom, e soprattutto che i tre gesti non si rubino il posto a vicenda.
    """

    def _strumento(self, formato="A4 verticale", scala=1000, gon=0.0):
        from tidashboard.tidashboard import StrumentoSpostaFoglio
        iface = _IfaceFinto()
        dlg = TIDashboardDialog(iface=iface)
        dlg.combo_formato.setCurrentText(formato)
        dlg.combo_scala.setCurrentText("1:%d" % scala)
        dlg.spin_rotazione.setValue(gon)
        dlg._centro_da_fondo = QgsPointXY(CX, CY)
        canvas = iface.mapCanvas()
        # Una vista larga abbastanza da contenere il foglio: la presa della
        # maniglia si misura in pixel, quindi dipende dallo zoom.
        canvas.setExtent(QgsRectangle(CX - 400, CY - 400, CX + 400, CY + 400))
        canvas.resize(600, 600)
        return dlg, StrumentoSpostaFoglio(canvas, dlg), canvas

    def test_la_maniglia_si_afferra_e_ruota(self):
        dlg, tool, _c = self._strumento()
        maniglia = P.maniglia_rotazione(
            QgsPointXY(CX, CY), 1000, "A4 verticale", 0.0)
        tool.canvasPressEvent(_EventoFinto(maniglia.x(), maniglia.y()))
        # trascinata a ovest = un quarto di giro antiorario = 100 gon
        tool.canvasMoveEvent(_EventoFinto(CX - 200, CY))
        self.assertAlmostEqual(dlg.spin_rotazione.value(), 100.0, delta=0.2)

    def test_la_rotazione_finisce_nella_casella_e_non_altrove(self):
        """La casella resta l'unica fonte: cosi' il valore si legge in gon
        mentre si trascina e l'anteprima si aggiorna da sola."""
        dlg, tool, _c = self._strumento()
        maniglia = P.maniglia_rotazione(
            QgsPointXY(CX, CY), 1000, "A4 verticale", 0.0)
        tool.canvasPressEvent(_EventoFinto(maniglia.x(), maniglia.y()))
        tool.canvasReleaseEvent(_EventoFinto(CX, CY - 200))
        self.assertAlmostEqual(dlg.spin_rotazione.value(), 200.0, delta=0.2)

    def test_la_maniglia_ha_la_precedenza_sul_trascinamento(self):
        """Sta sul bordo, quindi cade DENTRO l'impronta: se si controllasse
        prima il rettangolo non si riuscirebbe mai ad afferrarla."""
        dlg, tool, _c = self._strumento()
        prima = dlg.spin_rotazione.value()
        maniglia = P.maniglia_rotazione(
            QgsPointXY(CX, CY), 1000, "A4 verticale", 0.0)
        tool.canvasPressEvent(_EventoFinto(maniglia.x(), maniglia.y()))
        tool.canvasMoveEvent(_EventoFinto(CX - 200, CY))
        self.assertNotAlmostEqual(dlg.spin_rotazione.value(), prima, places=1)
        self.assertAlmostEqual(dlg._centro_da_fondo.x(), CX, places=6,
                               msg="ruotando il centro non si deve muovere")

    def test_dentro_il_foglio_ma_lontano_dalla_maniglia_si_sposta(self):
        dlg, tool, _c = self._strumento()
        prima = dlg.spin_rotazione.value()
        tool.canvasPressEvent(_EventoFinto(CX, CY))
        tool.canvasMoveEvent(_EventoFinto(CX + 30, CY + 10))
        self.assertAlmostEqual(dlg._centro_da_fondo.x(), CX + 30, places=6)
        self.assertAlmostEqual(dlg.spin_rotazione.value(), prima, places=6,
                               msg="spostando la rotazione non deve cambiare")

    def test_fuori_dal_foglio_non_succede_niente(self):
        dlg, tool, _c = self._strumento()
        tool.canvasPressEvent(_EventoFinto(CX + 100000, CY))
        tool.canvasMoveEvent(_EventoFinto(CX + 100030, CY))
        self.assertAlmostEqual(dlg._centro_da_fondo.x(), CX, places=6)

    def test_il_doppio_clic_inquadra_il_foglio(self):
        dlg, tool, canvas = self._strumento()
        canvas.setExtent(QgsRectangle(CX - 5000, CY - 5000, CX + 5000, CY + 5000))
        tool.canvasDoubleClickEvent(_EventoFinto(CX, CY))
        vista = canvas.extent()
        impronta = QgsGeometry.fromPolygonXY([P.impronta_foglio(
            QgsPointXY(CX, CY), 1000, "A4 verticale", 0.0)]).boundingBox()
        self.assertTrue(vista.contains(impronta), "il foglio deve starci tutto")
        self.assertLess(vista.width(), 5000.0, "e la vista deve essersi stretta")

    def test_il_doppio_clic_non_sposta_il_foglio(self):
        """Muove la VISTA, non il foglio: sono due cose diverse e confonderle
        sposterebbe cio' che si stampa mentre si voleva solo guardarlo."""
        dlg, tool, _c = self._strumento()
        tool.canvasDoubleClickEvent(_EventoFinto(CX, CY))
        self.assertAlmostEqual(dlg._centro_da_fondo.x(), CX, places=6)
        self.assertAlmostEqual(dlg._centro_da_fondo.y(), CY, places=6)

    def test_il_doppio_clic_fuori_dal_foglio_non_fa_niente(self):
        dlg, tool, canvas = self._strumento()
        prima = canvas.extent()
        tool.canvasDoubleClickEvent(_EventoFinto(CX + 100000, CY))
        self.assertEqual(canvas.extent(), prima)

    def test_ruotare_col_puntatore_sul_centro_non_fa_saltare_niente(self):
        """Sul centro un angolo non esiste: deve restare com'era, non
        azzerarsi."""
        dlg, tool, _c = self._strumento(gon=137.5)
        maniglia = P.maniglia_rotazione(
            QgsPointXY(CX, CY), 1000, "A4 verticale", 137.5)
        tool.canvasPressEvent(_EventoFinto(maniglia.x(), maniglia.y()))
        tool.canvasMoveEvent(_EventoFinto(CX, CY))
        self.assertAlmostEqual(dlg.spin_rotazione.value(), 137.5, places=1)


class TestCartellaDiLavoro(unittest.TestCase):
    def test_propone_la_cartella_dell_itf_in_uso(self):
        dlg = TIDashboardDialog()
        cartella = tempfile.mkdtemp()
        dlg.txt_itf.setText(os.path.join(cartella, "5254010100.itf"))
        self.assertEqual(dlg._cartella_di_lavoro(), cartella)

    def test_senza_niente_in_mano_non_torna_vuoto(self):
        dlg = TIDashboardDialog()
        dlg.txt_itf.setText("")
        dlg.txt_gpkg.setText("")
        self.assertTrue(os.path.isdir(dlg._cartella_di_lavoro()))


class TestImportazioneMultiComune(unittest.TestCase):
    """L'archivio a piu' comuni.

    La prova che conta e' che importare il secondo comune NON distrugga il
    primo. Era esattamente il comportamento di prima - run_import cancellava
    il GeoPackage a ogni giro - e non lo copriva nessuna prova: la riga piu'
    distruttiva del plugin passava sotto silenzio."""

    TESTA = b"SCNT\r\nINTERLIS Export\r\n////\r\nMTID INTERLIS1\r\nMODL MD01MUTI7MN95\r\n"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.avviati = []
        self._worker_vero = cd.JavaWorker
        prova = self

        class WorkerFinto(object):
            """Registra il comando e non lancia niente: qui si prova la
            DECISIONE, non ili2gpkg."""

            def __init__(self, cmd, tipo, parent=None):
                prova.avviati.append((tipo, list(cmd)))
                self.finished = self.log_signal = self.finished_signal = self

            def connect(self, *a, **k):
                pass

            def start(self):
                pass

            def isRunning(self):
                return False

            def deleteLater(self):
                pass

        cd.JavaWorker = WorkerFinto

    def tearDown(self):
        cd.JavaWorker = self._worker_vero

    def _itf(self, *comuni):
        """Un ITF col modello giusto e la tabella Comune dichiarata."""
        if not comuni:
            comuni = (("Lavertezzo", "5112", "422"),)
        corpo = b"TOPI Beni_immobili\r\nTABL Comune\r\n"
        for i, (nome, bfs, nr) in enumerate(comuni, 1):
            corpo += ("OBJE %d %s %s %s\r\n" % (i, nome, bfs, nr)).encode("latin-1")
        corpo += b"ETAB\r\nETOP\r\nENDE\r\n"
        percorso = os.path.join(tempfile.mkdtemp(), "c.itf")
        with open(percorso, "wb") as f:
            f.write(self.TESTA + corpo)
        return percorso

    def _archivio(self, *dataset):
        """Un GeoPackage con quel tanto di ili2gpkg che serve a decidere."""
        percorso = os.path.join(self.tmp, "archivio.gpkg")
        con = sqlite3.connect(percorso)
        con.execute("CREATE TABLE T_ILI2DB_MODEL (modelName TEXT)")
        con.execute("INSERT INTO T_ILI2DB_MODEL VALUES ('MD01MUTI7MN95')")
        con.execute("CREATE TABLE T_ILI2DB_DATASET (T_Id INTEGER, datasetname TEXT)")
        for i, n in enumerate(dataset, 1):
            con.execute("INSERT INTO T_ILI2DB_DATASET VALUES (?, ?)", (i, n))
        con.execute("CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT)")
        con.execute("CREATE TABLE mu_fondo (T_Id INTEGER, T_datasetname TEXT)")
        con.execute("INSERT INTO gpkg_contents VALUES ('mu_fondo', 'features')")
        con.execute("INSERT INTO mu_fondo VALUES (1, '611')")
        con.commit()
        con.close()
        return percorso

    def _dialog(self, itf, gpkg):
        dlg = TIDashboardDialog()
        jar = os.path.join(self.tmp, "ili2gpkg.jar")
        with open(jar, "wb") as f:
            f.write(b"x")
        dlg.txt_jar.setText(jar)
        dlg.txt_itf.setText(itf)
        dlg.txt_gpkg.setText(gpkg)
        dlg.find_java = lambda: "java"      # qui non si cerca Java
        return dlg

    def test_il_secondo_comune_NON_distrugge_il_primo(self):
        """LA REGRESSIONE. Prima il GeoPackage veniva cancellato a ogni
        importazione: il comune 611 gia' dentro spariva senza che nessuno lo
        dicesse - la conferma parlava di "sovrascrittura", non di "perdi i
        comuni gia' importati"."""
        g = self._archivio("611")
        prima = os.path.getsize(g)
        self._dialog(self._itf(), g).run_import()
        # LE DUE COSE INSIEME, e non una sola: il codice vecchio poteva
        # lasciare l'archivio intatto - bastava rispondere "no" alla conferma
        # di sovrascrittura - ma allora non importava niente. Chiedere solo
        # che il file sopravviva sarebbe passato anche prima.
        self.assertTrue(os.path.isfile(g), "l'archivio e' stato cancellato")
        self.assertEqual(os.path.getsize(g), prima)
        self.assertEqual([t for t, _c in self.avviati], ["dataimport"],
                         "l'archivio e' salvo ma non ha importato niente")
        con = sqlite3.connect(g)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM mu_fondo").fetchone()[0], 1)
        con.close()

    def test_un_comune_nuovo_si_aggiunge_col_suo_dataset(self):
        g = self._archivio("611")
        self._dialog(self._itf(), g).run_import()
        (tipo, cmd), = self.avviati
        self.assertEqual(tipo, "dataimport")
        self.assertIn("--import", cmd)
        self.assertEqual(cmd[cmd.index("--dataset") + 1], "422")

    def test_la_fase_dello_schema_si_salta_su_un_archivio_che_c_e(self):
        """Rifare --schemaimport non e' inutile, e' distruttivo: ricrea le
        tabelle."""
        g = self._archivio("611")
        self._dialog(self._itf(), g).run_import()
        self.assertEqual([t for t, _c in self.avviati], ["dataimport"])

    def test_un_archivio_nuovo_crea_lo_schema_con_la_colonna_dataset(self):
        """Senza --createDatasetCol l'archivio nasce gia' incapace di tenere
        separati i comuni, e non se ne accorge nessuno finche' non se ne
        importa un secondo."""
        g = os.path.join(self.tmp, "mai_esistito.gpkg")
        self._dialog(self._itf(), g).run_import()
        (tipo, cmd), = self.avviati
        self.assertEqual(tipo, "schemaimport")
        self.assertIn("--createDatasetCol", cmd)
        self.assertIn("--schemaimport", cmd)

    def test_un_comune_gia_presente_si_riaggiorna(self):
        g = self._archivio("422", "611")
        self._dialog(self._itf(), g).run_import()
        (_tipo, cmd), = self.avviati
        self.assertIn("--replace", cmd)
        self.assertNotIn("--import", cmd)

    def test_un_ITF_con_due_comuni_avvisa_e_non_avvia_niente(self):
        """Passando, i due comuni finirebbero sotto un nome solo e il DXF
        dell'uno conterrebbe l'altro."""
        g = self._archivio("611")
        itf = self._itf(("Lavertezzo", "5112", "422"), ("Coldrerio", "5251", "611"))
        prima = len(_avvisi)
        self._dialog(itf, g).run_import()
        self.assertEqual(self.avviati, [], "non deve partire nessun processo")
        self.assertGreater(len(_avvisi), prima)
        self.assertIn("2 comuni", _avvisi[-1])

    def test_un_archivio_senza_la_colonna_dataset_si_rifiuta(self):
        """Un GeoPackage fatto dal plugin vecchio: aggiungendoci un comune, le
        righe gia' dentro resterebbero senza proprietario."""
        g = os.path.join(self.tmp, "vecchio.gpkg")
        con = sqlite3.connect(g)
        con.execute("CREATE TABLE T_ILI2DB_MODEL (modelName TEXT)")
        con.execute("INSERT INTO T_ILI2DB_MODEL VALUES ('MD01MUTI7MN95')")
        con.execute("CREATE TABLE T_ILI2DB_DATASET (T_Id INTEGER, datasetname TEXT)")
        con.execute("INSERT INTO T_ILI2DB_DATASET VALUES (1, '611')")
        con.execute("CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT)")
        con.execute("CREATE TABLE mu_fondo (T_Id INTEGER)")   # senza T_datasetname
        con.execute("INSERT INTO gpkg_contents VALUES ('mu_fondo', 'features')")
        con.commit()
        con.close()
        prima = len(_avvisi)
        self._dialog(self._itf(), g).run_import()
        self.assertEqual(self.avviati, [])
        self.assertGreater(len(_avvisi), prima)
        self.assertIn("T_datasetname", _avvisi[-1])


class TestManifestLegenda(unittest.TestCase):
    """Il manifest che il lato Java legge per disegnare la legenda nel DXF.

    Lo cerca ACCANTO ALL'ITF CHE RICEVE (Av2geobau.doConversion). Prima si
    scriveva solo alla fine dello stile, accanto all'ITF del campo di
    IMPORTAZIONE: sono due campi indipendenti, e con l'archivio a piu' comuni
    quasi mai lo stesso file. Il DXF usciva senza legenda, senza un errore e
    senza niente da leggere nel registro."""

    def setUp(self):
        self._worker_vero = cd.JavaWorker
        prova = self

        class WorkerFinto(object):
            def __init__(self, cmd, tipo, parent=None):
                prova.lanciato = list(cmd)
                self.finished = self.log_signal = self.finished_signal = self

            def connect(self, *a, **k):
                pass

            def start(self):
                pass

            def isRunning(self):
                return False

            def deleteLater(self):
                pass

        cd.JavaWorker = WorkerFinto
        self.lanciato = None

    def tearDown(self):
        cd.JavaWorker = self._worker_vero

    def _layer_stilizzato(self):
        lyr = QgsVectorLayer("Point?crs=EPSG:2056", "confini", "memory")
        QgsProject.instance().addMapLayer(lyr)
        return [(lyr, "beni_immobili_punto_di_confine")]

    def test_il_manifest_finisce_accanto_all_ITF_CHE_SI_CONVERTE(self):
        """LA REGRESSIONE: due cartelle diverse, come con piu' comuni."""
        cartella_import = tempfile.mkdtemp()
        cartella_dxf = tempfile.mkdtemp()
        itf_dxf = os.path.join(cartella_dxf, "altro_comune.itf")
        with open(itf_dxf, "wb") as f:
            f.write(b"SCNT\r\nMTID INTERLIS1\r\nMODL MD01MUTI7MN95\r\n")

        dlg = TIDashboardDialog()
        dlg._zorder_layers = self._layer_stilizzato()
        dlg.txt_itf.setText(os.path.join(cartella_import, "importato.itf"))
        dlg.chk_itf_diverso.setChecked(True)
        dlg.txt_geobau_itf.setText(itf_dxf)
        dlg.txt_geobau_dxf.setText(os.path.join(cartella_dxf, "uscita.dxf"))
        dlg.txt_jar.setText(itf_dxf)          # un file qualunque che esista
        dlg.find_java = lambda: "java"
        dlg.run_geobau()

        # Il nome scritto per esteso, non dlg.NOME_MANIFEST: cosi' la prova
        # misura il COMPORTAMENTO e non l'esistenza di una costante nuova, e
        # contro il codice di prima fallisce per il motivo giusto.
        atteso = os.path.join(cartella_dxf, "legenda_manifest.txt")
        self.assertTrue(os.path.isfile(atteso),
                        "il manifest non e' accanto all'ITF che si converte")

    def test_senza_stile_lo_dice_invece_di_tacere(self):
        """Nessuna legenda applicata: il DXF uscira' senza legenda, e va detto
        - prima spariva in silenzio."""
        cartella = tempfile.mkdtemp()
        itf = os.path.join(cartella, "c.itf")
        with open(itf, "wb") as f:
            f.write(b"SCNT\r\nMTID INTERLIS1\r\nMODL MD01MUTI7MN95\r\n")
        dlg = TIDashboardDialog()
        dlg._zorder_layers = []
        dlg.chk_itf_diverso.setChecked(True)
        dlg.txt_geobau_itf.setText(itf)
        dlg.txt_geobau_dxf.setText(os.path.join(cartella, "u.dxf"))
        dlg.txt_jar.setText(itf)
        dlg.find_java = lambda: "java"
        dlg.run_geobau()
        self.assertFalse(os.path.isfile(os.path.join(cartella, dlg.NOME_MANIFEST)))
        testo = dlg.txt_log.toPlainText()
        self.assertIn("senza legenda", testo)

    def test_la_stessa_cartella_non_si_scrive_due_volte(self):
        dlg = TIDashboardDialog()
        dlg._zorder_layers = self._layer_stilizzato()
        cartella = tempfile.mkdtemp()
        scritte = dlg._scrivi_manifest_legenda(
            [cartella, os.path.join(cartella, "."), cartella])
        self.assertEqual(scritte, 1)

    def test_una_cartella_che_non_esiste_non_ferma_le_altre(self):
        dlg = TIDashboardDialog()
        dlg._zorder_layers = self._layer_stilizzato()
        buona = tempfile.mkdtemp()
        scritte = dlg._scrivi_manifest_legenda(
            [os.path.join(tempfile.mkdtemp(), "mai", "esistita"), None, buona])
        self.assertEqual(scritte, 1)
        self.assertTrue(os.path.isfile(os.path.join(buona, dlg.NOME_MANIFEST)))


class TestSvuotaArchivio(unittest.TestCase):
    """Buttare l'archivio per ricominciare.

    Esiste perche' la cancellazione automatica e' stata TOLTA - era un difetto
    con piu' comuni - e con essa era sparito l'unico modo di ripartire da
    zero. Ma le due cose sono diverse: quella di prima avveniva mentre
    l'utente credeva di importare.

    Su una funzione che cancella, le prove che contano sono quelle in cui NON
    deve cancellare."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.g = os.path.join(self.tmp, "archivio.gpkg")
        self.risposte = []
        self._warning_vero = QMessageBox.warning
        prova = self

        def finta(*a, **k):
            _avvisi.append(a[2] if len(a) > 2 else "")
            return prova.risposte.pop(0) if prova.risposte else cd._MB_NO

        QMessageBox.warning = staticmethod(finta)

    def tearDown(self):
        QMessageBox.warning = self._warning_vero

    def _archivio(self, *dataset):
        con = sqlite3.connect(self.g)
        con.execute("CREATE TABLE T_ILI2DB_MODEL (modelName TEXT)")
        con.execute("INSERT INTO T_ILI2DB_MODEL VALUES ('MD01MUTI7MN95')")
        con.execute("CREATE TABLE T_ILI2DB_DATASET (T_Id INTEGER, datasetname TEXT)")
        for i, n in enumerate(dataset, 1):
            con.execute("INSERT INTO T_ILI2DB_DATASET VALUES (?, ?)", (i, n))
        con.commit()
        con.close()
        cd._archivio.registra(self.g, cd._archivio.Comune("422", "Lavertezzo"),
                              "a.itf")
        return self.g

    def _dialog(self, percorso=None):
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText(percorso if percorso is not None else self.g)
        return dlg

    def test_rispondendo_NO_il_file_resta(self):
        self._archivio("422", "611")
        self.risposte = [cd._MB_NO]
        self._dialog().svuota_archivio()
        self.assertTrue(os.path.isfile(self.g))

    def test_rispondendo_SI_il_file_sparisce(self):
        self._archivio("422", "611")
        self.risposte = [cd._MB_SI]
        self._dialog().svuota_archivio()
        self.assertFalse(os.path.isfile(self.g))

    def test_la_conferma_NOMINA_i_comuni(self):
        """La conferma di prima diceva "il file esistente sara' sovrascritto"
        senza mai dire quanti comuni ci fossero dentro: vera, e inutile."""
        self._archivio("422", "611")
        self.risposte = [cd._MB_NO]
        del _avvisi[:]
        self._dialog().svuota_archivio()
        testo = _avvisi[-1]
        self.assertIn("2 comuni", testo)
        self.assertIn("Lavertezzo", testo)
        self.assertIn("comune 611", testo, "il non registrato va nominato lo stesso")

    def test_un_file_che_non_e_nostro_non_si_tocca_NEMMENO_dicendo_SI(self):
        """Un percorso sbagliato nel campo non deve distruggere il lavoro di
        qualcun altro: qui la domanda non si pone proprio."""
        altrui = os.path.join(self.tmp, "relazione.gpkg")
        with open(altrui, "wb") as f:
            f.write(b"documento importante di qualcun altro")
        self.risposte = [cd._MB_SI, cd._MB_SI]
        self._dialog(altrui).svuota_archivio()
        self.assertTrue(os.path.isfile(altrui))
        self.assertEqual(open(altrui, "rb").read(),
                         b"documento importante di qualcun altro")

    def test_un_GeoPackage_di_un_altro_programma_non_si_tocca(self):
        estraneo = os.path.join(self.tmp, "altro.gpkg")
        con = sqlite3.connect(estraneo)
        con.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
        con.commit()
        con.close()
        self.risposte = [cd._MB_SI, cd._MB_SI]
        self._dialog(estraneo).svuota_archivio()
        self.assertTrue(os.path.isfile(estraneo))

    def _archivio_vero(self):
        """Un GeoPackage VERO - scritto da OGR, quindi apribile da QGIS - con
        dentro anche le tabelle che lo rendono un nostro archivio."""
        memoria = QgsVectorLayer("Point?crs=EPSG:2056&field=n:string", "punti",
                                 "memory")
        dp = memoria.dataProvider()
        f = QgsFeature(memoria.fields())
        f.setAttribute(0, "x")
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(CX, CY)))
        dp.addFeature(f)
        memoria.updateExtents()
        opzioni = QgsVectorFileWriter.SaveVectorOptions()
        opzioni.driverName = "GPKG"
        opzioni.layerName = "punti"
        QgsVectorFileWriter.writeAsVectorFormatV3(
            memoria, self.g, QgsProject.instance().transformContext(), opzioni)
        con = sqlite3.connect(self.g)
        con.execute("CREATE TABLE T_ILI2DB_MODEL (modelName TEXT)")
        con.execute("INSERT INTO T_ILI2DB_MODEL VALUES ('MD01MUTI7MN95')")
        con.execute("CREATE TABLE T_ILI2DB_DATASET (T_Id INTEGER, datasetname TEXT)")
        con.execute("INSERT INTO T_ILI2DB_DATASET VALUES (1, '422')")
        con.commit()
        con.close()

    def test_i_layer_APERTI_SUL_FILE_si_chiudono_prima(self):
        """Su Windows un GeoPackage con dei layer aperti sopra e' BLOCCATO, e
        la cancellazione fallisce con un errore di permessi che sembra un
        problema di diritti e non lo e'.

        Il layer qui e' VERO e legge davvero dal file: con un layer di memoria
        la prova passerebbe comunque, perche' loaded_layers viene azzerato in
        ogni caso, e non direbbe niente sull'aggancio per sorgente."""
        self._archivio_vero()
        lyr = QgsVectorLayer("%s|layername=punti" % self.g, "punti", "ogr")
        self.assertTrue(lyr.isValid(), "serve un layer vero per questa prova")
        QgsProject.instance().addMapLayer(lyr)
        identificativo = lyr.id()
        dlg = self._dialog()
        dlg.loaded_layers = [lyr]
        self.assertEqual(dlg._chiudi_layer_dell_archivio(self.g), 1,
                         "non ha riconosciuto il layer aperto sul file")
        self.assertIsNone(QgsProject.instance().mapLayer(identificativo))
        self.assertEqual(dlg.loaded_layers, [])

    def test_un_layer_di_UN_ALTRO_file_non_si_chiude(self):
        """Chiudere i layer di un altro progetto sarebbe un danno collaterale
        silenzioso."""
        self._archivio("422")
        altro = QgsVectorLayer("Point?crs=EPSG:2056", "altro", "memory")
        QgsProject.instance().addMapLayer(altro)
        identificativo = altro.id()
        self.assertEqual(self._dialog()._chiudi_layer_dell_archivio(self.g), 0)
        self.assertIsNotNone(QgsProject.instance().mapLayer(identificativo))
        QgsProject.instance().removeMapLayer(identificativo)

    def test_il_pulsante_dice_quanti_ne_butterebbe(self):
        self._archivio("422", "611")
        dlg = self._dialog()
        dlg._aggiorna_pulsante_svuota()
        self.assertTrue(dlg.btn_svuota.isEnabled())
        self.assertIn("2 comuni", dlg.btn_svuota.text())

    def test_il_pulsante_e_spento_se_non_c_e_niente_da_buttare(self):
        """Un pulsante distruttivo sempre acceso invita a premerlo per vedere
        cosa fa."""
        dlg = self._dialog(os.path.join(self.tmp, "mai_esistito.gpkg"))
        dlg._aggiorna_pulsante_svuota()
        self.assertFalse(dlg.btn_svuota.isEnabled())
        self.assertNotIn("comuni", dlg.btn_svuota.text())


class TestCodaCartella(unittest.TestCase):
    """L'importazione di una cartella intera, nella finestra.

    Il pezzo delicato non e' il piano - quello si prova in test_archivio - ma
    la CODA: che i comandi partano uno per volta, che lo schema si faccia solo
    al primo, che un comune andato male non fermi gli altri, e che i layer si
    carichino una volta sola alla fine."""

    TESTA = b"SCNT\r\nMTID INTERLIS1\r\nMODL MD01MUTI7MN95\r\n"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cartella = os.path.join(self.tmp, "consegne")
        os.makedirs(self.cartella)
        self.avviati = []
        self.caricato = []
        self._worker_vero = cd.JavaWorker
        prova = self

        class WorkerFinto(object):
            def __init__(self, cmd, tipo, parent=None):
                prova.avviati.append((tipo, list(cmd)))
                self.finished = self.log_signal = self.finished_signal = self

            def connect(self, *a, **k):
                pass

            def start(self):
                pass

            def isRunning(self):
                return False

            def deleteLater(self):
                pass

        cd.JavaWorker = WorkerFinto

    def tearDown(self):
        cd.JavaWorker = self._worker_vero

    def _itf(self, nome, nome_comune, numero):
        percorso = os.path.join(self.cartella, nome)
        corpo = (b"TOPI Beni_immobili\r\nTABL Comune\r\n"
                 + ("OBJE 1 %s 5000 %s\r\n" % (nome_comune, numero)).encode("latin-1")
                 + b"ETAB\r\nETOP\r\nENDE\r\n")
        with open(percorso, "wb") as f:
            f.write(self.TESTA + corpo)
        return percorso

    def _dialog(self):
        dlg = TIDashboardDialog()
        jar = os.path.join(self.tmp, "ili2gpkg.jar")
        with open(jar, "wb") as f:
            f.write(b"x")
        dlg.txt_jar.setText(jar)
        dlg.txt_gpkg.setText(os.path.join(self.tmp, "archivio.gpkg"))
        dlg.find_java = lambda: "java"
        prova = self
        dlg.load_and_style_layers = lambda: prova.caricato.append(True)
        dlg._validate_gpkg_with_gdal = lambda *a, **k: None
        return dlg

    def _avvia(self, dlg):
        """Costruisce la coda senza passare dalla finestra di scelta cartella."""
        lavori = cd._archivio.pianifica_cartella(
            dlg.txt_gpkg.text().strip(), self.cartella,
            modello_atteso=cd._modello.MODELLO_ATTESO)
        dlg._coda_import = [l for l in lavori if l.da_fare]
        dlg._fatti_in_coda = 0
        dlg._falliti_in_coda = []
        dlg._avvia_prossimo_della_coda()

    def _gira(self, dlg, *esiti):
        """Fa girare la coda fino in fondo, come farebbero i worker veri.

        Il worker finto non emette il segnale di fine, quindi la catena la si
        percorre a mano: dopo uno schemaimport tocca a on_schema_finished, che
        avvia i dati; dopo un dataimport tocca a on_data_finished, che passa al
        comune successivo. 'esiti' sono i codici di ritorno dei DATI, uno per
        comune, nell'ordine."""
        esiti = list(esiti)
        for _ in range(200):
            if not self.avviati:
                return
            tipo, _cmd = self.avviati[-1]
            if tipo == "schemaimport":
                dlg.on_schema_finished(0, "schemaimport")
                continue
            codice = esiti.pop(0) if esiti else 0
            prima = len(self.avviati)
            dlg.on_data_finished(codice, "dataimport")
            if len(self.avviati) == prima:
                return                    # la coda e' finita

    def test_lo_schema_si_fa_solo_al_primo(self):
        """Rifarlo a ogni file cancellerebbe i comuni gia' entrati: di cento
        comuni ne resterebbe uno."""
        self._itf("a.itf", "Lavertezzo", "422")
        self._itf("b.itf", "Coldrerio", "611")
        self._itf("c.itf", "Arzo", "606")
        dlg = self._dialog()
        self._avvia(dlg)
        self._gira(dlg)
        tipi = [t for t, _c in self.avviati]
        self.assertEqual(tipi.count("schemaimport"), 1, tipi)
        self.assertEqual(tipi.count("dataimport"), 3, tipi)

    def test_ogni_comune_ha_il_suo_dataset(self):
        self._itf("a.itf", "Lavertezzo", "422")
        self._itf("b.itf", "Coldrerio", "611")
        dlg = self._dialog()
        self._avvia(dlg)
        self._gira(dlg)
        dataset = [c[c.index("--dataset") + 1]
                   for t, c in self.avviati if t == "dataimport"]
        self.assertEqual(dataset, ["422", "611"])

    def test_i_layer_si_caricano_UNA_VOLTA_alla_fine(self):
        """Caricarli dopo ogni comune vorrebbe dire rifare lo stile cento
        volte, e mostrare un archivio a meta'."""
        self._itf("a.itf", "Lavertezzo", "422")
        self._itf("b.itf", "Coldrerio", "611")
        dlg = self._dialog()
        self._avvia(dlg)
        dlg.on_schema_finished(0, "schemaimport")
        dlg.on_data_finished(0, "dataimport")
        self.assertEqual(self.caricato, [], "caricati a meta' coda")
        dlg.on_data_finished(0, "dataimport")
        self.assertEqual(len(self.caricato), 1)

    def test_un_comune_andato_male_non_ferma_gli_altri(self):
        """Su cento consegne, fermarsi al primo file storto vorrebbe dire
        rifare tutto il giro dopo averlo tolto."""
        self._itf("a.itf", "Lavertezzo", "422")
        self._itf("b.itf", "Coldrerio", "611")
        self._itf("c.itf", "Arzo", "606")
        dlg = self._dialog()
        self._avvia(dlg)
        self._gira(dlg, 1, 0, 0)                   # il primo fallisce
        self.assertEqual(len(dlg._falliti_in_coda), 1)
        self.assertIn("a.itf", dlg._falliti_in_coda[0])
        self.assertEqual([t for t, _c in self.avviati].count("dataimport"), 3)
        self.assertEqual(len(self.caricato), 1,
                         "gli altri due sono entrati: la legenda va applicata")

    def test_se_falliscono_TUTTI_non_si_stilizza_niente(self):
        self._itf("a.itf", "Lavertezzo", "422")
        self._itf("b.itf", "Coldrerio", "611")
        dlg = self._dialog()
        self._avvia(dlg)
        self._gira(dlg, 1, 1)
        self.assertEqual(self.caricato, [])

    def test_i_comuni_gia_dentro_non_entrano_in_coda(self):
        """La ripresa: e' il motivo per cui un giro da venti minuti
        interrotto non va rifatto da capo."""
        self._itf("a.itf", "Lavertezzo", "422")
        self._itf("b.itf", "Coldrerio", "611")
        g = os.path.join(self.tmp, "archivio.gpkg")
        con = sqlite3.connect(g)
        con.execute("CREATE TABLE T_ILI2DB_MODEL (modelName TEXT)")
        con.execute("INSERT INTO T_ILI2DB_MODEL VALUES ('MD01MUTI7MN95')")
        con.execute("CREATE TABLE T_ILI2DB_DATASET (T_Id INTEGER, datasetname TEXT)")
        con.execute("INSERT INTO T_ILI2DB_DATASET VALUES (1, '422')")
        con.execute("CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT)")
        con.execute("CREATE TABLE mu_fondo (T_Id INTEGER, T_datasetname TEXT)")
        con.execute("INSERT INTO gpkg_contents VALUES ('mu_fondo','features')")
        con.commit()
        con.close()
        dlg = self._dialog()
        self._avvia(dlg)
        dataset = [c[c.index("--dataset") + 1]
                   for t, c in self.avviati if t == "dataimport"]
        self.assertEqual(dataset, ["611"], "ha rifatto un comune gia' dentro")

    def test_un_importazione_singola_non_eredita_la_coda(self):
        """I contatori di un giro precedente farebbero parlare il riassunto
        finale di comuni che non c'entrano."""
        dlg = self._dialog()
        dlg._avviati_in_coda = 7
        dlg._fatti_in_coda = 7
        dlg._falliti_in_coda = ["vecchio.itf"]
        dlg.txt_itf.setText(self._itf("solo.itf", "Lavertezzo", "422"))
        dlg.run_import()
        self.assertEqual(dlg._avviati_in_coda, 1)
        self.assertEqual(dlg._fatti_in_coda, 0)
        self.assertEqual(dlg._falliti_in_coda, [])


class TestBarraArchivio(unittest.TestCase):
    """La barra in cima: quale archivio, quanti comuni, quale attivo.

    La tendina del comune stava dentro la planimetria con l'aria di un campo
    dell'intestazione, mentre da quando l'archivio tiene piu' comuni decide
    che cosa si VEDE. Spostarla sopra le schede e' stato possibile senza
    toccare i venti punti che la leggono, perche' leggono tutti
    currentText() e nessuno sa dove il widget stia."""

    def _archivio(self, *dataset):
        percorso = os.path.join(tempfile.mkdtemp(), "archivio.gpkg")
        con = sqlite3.connect(percorso)
        con.execute("CREATE TABLE T_ILI2DB_MODEL (modelName TEXT)")
        con.execute("INSERT INTO T_ILI2DB_MODEL VALUES ('MD01MUTI7MN95')")
        con.execute("CREATE TABLE T_ILI2DB_DATASET (T_Id INTEGER, datasetname TEXT)")
        con.execute("CREATE TABLE tidashboard_comuni "
                    "(numero TEXT PRIMARY KEY, nome TEXT, bfs TEXT, itf TEXT,"
                    " importato TEXT)")
        nomi = {"422": "Lavertezzo", "611": "Coldrerio", "606": "Arzo"}
        for i, n in enumerate(dataset, 1):
            con.execute("INSERT INTO T_ILI2DB_DATASET VALUES (?, ?)", (i, n))
            con.execute("INSERT INTO tidashboard_comuni VALUES (?,?,?,?,?)",
                        (n, nomi.get(n, "comune " + n), "0", "x.itf", "oggi"))
        con.commit()
        con.close()
        return percorso

    def test_la_tendina_sta_FUORI_dalle_schede(self):
        """E' il punto dell'intervento: un comando che cambia quello che si
        vede non puo' stare dentro una scheda."""
        dlg = TIDashboardDialog()
        genitore = dlg.combo_comune
        dentro_una_scheda = False
        while genitore is not None:
            if genitore is dlg.schede:
                dentro_una_scheda = True
                break
            genitore = genitore.parent()
        self.assertFalse(dentro_una_scheda,
                         "la tendina e' ancora dentro le schede")

    def test_senza_archivio_la_barra_non_si_vede(self):
        """Una barra che dice "nessun comune" occuperebbe spazio per non dire
        niente."""
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText(os.path.join(tempfile.mkdtemp(), "mai.gpkg"))
        self.assertFalse(dlg.barra_archivio.isVisibleTo(dlg))

    def test_un_file_che_non_e_un_archivio_non_accende_la_barra(self):
        percorso = os.path.join(tempfile.mkdtemp(), "altro.gpkg")
        with open(percorso, "wb") as f:
            f.write(b"non e' un database")
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText(percorso)
        self.assertFalse(dlg.barra_archivio.isVisibleTo(dlg))

    def test_la_barra_dice_il_NOME_DEL_FILE_non_il_percorso(self):
        """Il campo di testo mostra il centro di un percorso lungo, che e' la
        parte che non serve: il nome sta in fondo e non si vede."""
        g = self._archivio("422", "611")
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText(g)
        testo = dlg.lbl_archivio.text()
        self.assertIn("archivio.gpkg", testo)
        self.assertNotIn(os.path.dirname(g), testo)
        self.assertEqual(dlg.lbl_archivio.toolTip(), g)

    def test_la_barra_conta_i_comuni(self):
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText(self._archivio("422", "611", "606"))
        self.assertTrue(dlg.barra_archivio.isVisibleTo(dlg))
        self.assertIn("3 comuni", dlg.lbl_archivio.text())

    def test_un_comune_solo_si_dice_al_singolare(self):
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText(self._archivio("422"))
        self.assertIn("1 comune", dlg.lbl_archivio.text())
        self.assertNotIn("1 comuni", dlg.lbl_archivio.text())

    def test_il_contatore_dice_quale_dei_quanti(self):
        g = self._archivio("422", "611")
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText(g)
        dlg.combo_comune.clear()
        dlg.combo_comune.addItems(["Lavertezzo", "Coldrerio"])
        dlg.combo_comune.setCurrentText("Coldrerio")
        dlg._aggiorna_barra_archivio()
        self.assertIn("2 di 2", dlg.lbl_quale_comune.text())
        dlg.combo_comune.setCurrentText("Lavertezzo")
        dlg._aggiorna_barra_archivio()
        self.assertIn("1 di 2", dlg.lbl_quale_comune.text())

    def test_il_contatore_conta_sulla_TENDINA_non_sul_registro(self):
        """Sono due elenchi diversi: il registro ordina per numero di comune,
        la tendina per come i nomi compaiono nelle tabelle. Contando sul
        registro mentre l'occhio legge la tendina, accanto al PRIMO nome
        dell'elenco poteva comparire "2 di 2"."""
        g = self._archivio("422", "611")          # registro: Lavertezzo, Coldrerio
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText(g)
        dlg.combo_comune.clear()
        dlg.combo_comune.addItems(["Coldrerio", "Lavertezzo"])   # ordine opposto
        dlg.combo_comune.setCurrentText("Coldrerio")
        dlg._aggiorna_barra_archivio()
        self.assertIn("1 di 2", dlg.lbl_quale_comune.text(),
                      "ha contato sul registro invece che sulla tendina")

    def test_se_i_due_elenchi_non_combaciano_il_contatore_tace(self):
        """Confronterebbe cose diverse: meglio niente di un numero che non si
        sa a che cosa si riferisce."""
        g = self._archivio("422", "611", "606")
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText(g)
        dlg.combo_comune.clear()
        dlg.combo_comune.addItems(["Lavertezzo", "Coldrerio"])   # due su tre
        dlg.combo_comune.setCurrentText("Coldrerio")
        dlg._aggiorna_barra_archivio()
        self.assertEqual(dlg.lbl_quale_comune.text(), "")
        self.assertIn("3 comuni", dlg.lbl_archivio.text(),
                      "l'archivio ne ha comunque tre, e va detto")

    def test_con_un_comune_solo_il_contatore_tace(self):
        """Sarebbe un contatore che conta fino a uno."""
        g = self._archivio("422")
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText(g)
        dlg.combo_comune.clear()
        dlg.combo_comune.addItems(["Lavertezzo"])
        dlg._aggiorna_barra_archivio()
        self.assertEqual(dlg.lbl_quale_comune.text(), "")

    def test_la_planimetria_dice_a_chi_sara_intestato_il_piano(self):
        """Togliendo la tendina di li' senza lasciare niente, il punto in cui
        si decide l'intestazione sarebbe diventato muto."""
        g = self._archivio("422", "611")
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText(g)
        dlg.combo_comune.clear()
        dlg.combo_comune.addItems(["Lavertezzo", "Coldrerio"])
        dlg.combo_comune.setCurrentText("Coldrerio")
        dlg._aggiorna_barra_archivio()
        eco = dlg.lbl_comune_piano.text()
        self.assertIn("Coldrerio", eco)
        self.assertIn("intestato", eco)
        self.assertIn("uno dei 2", eco)

    def test_senza_comune_l_eco_lo_dice_e_dice_dove_sceglierlo(self):
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText(os.path.join(tempfile.mkdtemp(), "mai.gpkg"))
        self.assertIn("barra in cima", dlg.lbl_comune_piano.text())

    def test_la_tendina_resta_scrivibile(self):
        """Una consegna puo' non portare nessuna delle due fonti del nome, e
        li' e' meglio poterlo scrivere che restare bloccati."""
        dlg = TIDashboardDialog()
        self.assertTrue(dlg.combo_comune.isEditable())
        dlg.combo_comune.setCurrentText("Comune scritto a mano")
        self.assertEqual(dlg.combo_comune.currentText(), "Comune scritto a mano")


class TestComuneAttivo(unittest.TestCase):
    """La catena intera: scelgo un comune nella tendina, e la data del
    cartiglio e i dati dei layer seguono quello.

    Sono i due difetti misurati sull'archivio vero di Lavertezzo e Coldrerio:
    il piano di Coldrerio dichiarava "stato al 17.06.2026" (la data di
    Lavertezzo) mentre i suoi dati erano fermi al 20.05.2026, e il foglio si
    centrava sull'unione dei due comuni - 10 101 x 37 213 m invece di
    1 549 x 902 m, che nessuna delle otto scale di norma poteva contenere."""

    def _archivio(self, quanti=2):
        percorso = os.path.join(tempfile.mkdtemp(), "archivio.gpkg")
        con = sqlite3.connect(percorso)
        con.execute("CREATE TABLE confini_comunali_comune "
                    "(nome TEXT, T_datasetname TEXT)")
        con.execute("CREATE TABLE beni_immobili_tenuta_a_giorno "
                    "(in_vigore TEXT, T_datasetname TEXT)")
        con.execute("CREATE TABLE tidashboard_comuni "
                    "(numero TEXT PRIMARY KEY, nome TEXT, bfs TEXT, itf TEXT,"
                    " importato TEXT)")
        righe = [("422", "Lavertezzo", "2026-06-17"),
                 ("611", "Coldrerio", "2026-05-20")][:quanti]
        for numero, nome, data in righe:
            con.execute("INSERT INTO confini_comunali_comune VALUES (?, ?)",
                        (nome, numero))
            con.execute("INSERT INTO beni_immobili_tenuta_a_giorno VALUES (?, ?)",
                        (data, numero))
            con.execute("INSERT INTO tidashboard_comuni VALUES (?,?,?,?,?)",
                        (numero, nome, "0000", "x.itf", "2026-08-27"))
        con.commit()
        con.close()
        return percorso

    def _layer(self):
        lyr = QgsVectorLayer(
            "Point?crs=EPSG:2056&field=T_datasetname:string", "punti", "memory")
        dp = lyr.dataProvider()
        for ds, x in (("422", 2700000.0), ("611", 2720000.0)):
            f = QgsFeature(lyr.fields())
            f.setAttribute(0, ds)
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, 1100000.0)))
            dp.addFeature(f)
        lyr.updateExtents()
        return lyr

    def _dialog(self, gpkg):
        dlg = TIDashboardDialog()
        dlg.txt_gpkg.setText(gpkg)
        dlg.txt_itf.setText("")          # se no la data verrebbe dal file ITF
        return dlg

    def test_con_piu_comuni_la_data_dell_ITF_si_ignora(self):
        """IL DIFETTO CHE HANNO PRESO SOLO QGIS APERTO E DUE COMUNI VERI.

        Il campo ITF e' uno solo, i comuni sono molti: la sua data di modifica
        finiva in cartiglio per TUTTI. Nella sessione vera il campo era rimasto
        pieno dalle impostazioni precedenti, e i due comuni dichiaravano
        entrambi "stato al 20.08.2026" - la data di un file scaricato mesi
        dopo, che non apparteneva a nessuno dei due.

        Le prove di prima non potevano prenderlo: svuotavano il campo apposta,
        per arrivare al ramo che stavano provando."""
        g = self._archivio()
        itf = os.path.join(tempfile.mkdtemp(), "vecchio.itf")
        with open(itf, "wb") as f:
            f.write(b"SCNT\r\nMTID INTERLIS1\r\nMODL MD01MUTI7MN95\r\n")
        dlg = self._dialog(g)
        dlg.txt_itf.setText(itf)          # com'era nella sessione vera
        dlg.combo_comune.setCurrentText("Coldrerio")
        dlg.aggiorna_comuni_da_dati()
        self.assertEqual(dlg._data_dai_dati, "20.05.2026")
        self.assertEqual(dlg._origine_data, "ultima mutazione nei dati")

    def test_con_UN_comune_la_data_dell_ITF_vale_ancora(self):
        """Non e' stata tolta: con un archivio a comune solo l'ITF e' quello,
        e la sua data di estrazione resta la fonte migliore."""
        g = self._archivio(quanti=1)
        itf = os.path.join(tempfile.mkdtemp(), "solo.itf")
        with open(itf, "wb") as f:
            f.write(b"SCNT\r\nMTID INTERLIS1\r\nMODL MD01MUTI7MN95\r\n")
        dlg = self._dialog(g)
        dlg.txt_itf.setText(itf)
        dlg.aggiorna_comuni_da_dati()
        self.assertEqual(dlg._origine_data, "estrazione ITF")

    def test_cambiare_comune_dalla_TENDINA_aggiorna_anche_la_data(self):
        """Visto solo aprendo la finestra: cambiando comune la mappa si
        filtrava, ma il cartiglio continuava a portare la data del comune di
        prima. La tendina era agganciata al filtro dei dati e NON alla
        rilettura della data - lo stesso difetto appena corretto, rientrato da
        un'altra porta.

        Qui non si chiama aggiorna_comuni_da_dati a mano: si tocca solo la
        tendina, come fa chi usa il plugin."""
        g = self._archivio()
        dlg = self._dialog(g)
        dlg.aggiorna_comuni_da_dati()
        dlg.combo_comune.setCurrentText("Coldrerio")
        self.assertEqual(dlg._data_dai_dati, "20.05.2026")
        dlg.combo_comune.setCurrentText("Lavertezzo")
        self.assertEqual(dlg._data_dai_dati, "17.06.2026",
                         "la data e' rimasta su Coldrerio")

    def test_la_data_segue_il_comune_scelto(self):
        g = self._archivio()
        dlg = self._dialog(g)
        dlg.aggiorna_comuni_da_dati()
        dlg.combo_comune.setCurrentText("Coldrerio")
        dlg.aggiorna_comuni_da_dati()
        self.assertEqual(dlg._numero_comune_attivo(), "611")
        self.assertEqual(dlg._data_dai_dati, "20.05.2026",
                         "il piano di Coldrerio dichiara la data di Lavertezzo")
        dlg.combo_comune.setCurrentText("Lavertezzo")
        dlg.aggiorna_comuni_da_dati()
        self.assertEqual(dlg._data_dai_dati, "17.06.2026")

    def test_i_layer_si_riducono_al_comune_scelto(self):
        g = self._archivio()
        dlg = self._dialog(g)
        lyr = self._layer()
        dlg.loaded_layers = [lyr]
        dlg.aggiorna_comuni_da_dati()
        dlg.combo_comune.setCurrentText("Coldrerio")
        dlg._al_cambio_di_comune()
        self.assertEqual(lyr.featureCount(), 1)
        self.assertAlmostEqual(lyr.extent().xMinimum(), 2720000.0, delta=1.0)

    def test_con_UN_comune_solo_non_cambia_niente(self):
        """Il caso di gran lunga piu' frequente: nessun filtro, comportamento
        identico a prima del multi-comune."""
        g = self._archivio(quanti=1)
        dlg = self._dialog(g)
        lyr = self._layer()
        dlg.loaded_layers = [lyr]
        dlg.aggiorna_comuni_da_dati()
        self.assertIsNone(dlg._numero_comune_attivo())
        dlg._al_cambio_di_comune()
        self.assertEqual(lyr.featureCount(), 2, "non doveva filtrare niente")
        self.assertEqual(lyr.subsetString(), "")

    def test_un_archivio_senza_registro_non_rompe_niente(self):
        """Un GeoPackage importato fuori dal plugin non ha la tabella del
        registro: si deve tornare al comportamento di prima, non fallire."""
        percorso = _gpkg_con_comuni(comuni=("Giubiasco",))
        dlg = self._dialog(percorso)
        dlg.loaded_layers = [self._layer()]
        dlg.aggiorna_comuni_da_dati()
        self.assertIsNone(dlg._numero_comune_attivo())
        dlg._al_cambio_di_comune()          # non deve alzare


class TestModelloAOgniPasso(unittest.TestCase):
    """Il modello dei dati va controllato in tutti i passi, non solo allo
    scaricamento: un ITF ricevuto per posta e un GeoPackage importato altrove
    entrano dalle altre porte."""

    TESTA = (b"SCNT\r\nINTERLIS Export\r\n////\r\nMTID INTERLIS1\r\nMODL %s\r\n")

    def _itf(self, nome_modello=b"MD01MUTI7MN95"):
        percorso = os.path.join(tempfile.mkdtemp(), "prova.itf")
        with open(percorso, "wb") as f:
            f.write(self.TESTA % nome_modello)
        return percorso

    def _dialog_pronta(self, itf):
        """Una dialog con tutti i campi a posto tranne, eventualmente, il
        modello: cosi' il pulsante si spegne per quel motivo e non per altri."""
        dlg = TIDashboardDialog()
        cartella = tempfile.mkdtemp()
        jar = os.path.join(cartella, "ili2gpkg.jar")
        with open(jar, "wb") as f:
            f.write(b"x")
        dlg.txt_jar.setText(jar)
        dlg.txt_itf.setText(itf)
        dlg.txt_gpkg.setText(os.path.join(cartella, "uscita.gpkg"))
        return dlg

    def test_il_modello_giusto_lascia_acceso_il_pulsante(self):
        dlg = self._dialog_pronta(self._itf())
        self.assertTrue(dlg.btn_import.isEnabled(),
                        "con tutto a posto l'importazione deve poter partire")

    def test_il_modello_federale_spegne_l_importazione(self):
        dlg = self._dialog_pronta(self._itf(b"MD01MUCH24MN95I"))
        self.assertFalse(dlg.btn_import.isEnabled())
        self.assertIn("MD01MUCH24MN95I", dlg.lbl_esito_import.text())
        spie = {le: et for le, _s, et, _sc in dlg._campi_percorso}
        self.assertEqual(spie[dlg.txt_itf].text(), "✖")
        self.assertIn("MD01MUTI7MN95", spie[dlg.txt_itf].toolTip())

    def test_anche_l_itf_della_conversione_dxf(self):
        """La conversione puo' lavorare su un ITF diverso da quello importato:
        e' il caso in cui il modello sbagliato passerebbe inosservato."""
        dlg = self._dialog_pronta(self._itf())
        dlg.chk_itf_diverso.setChecked(True)
        dlg.txt_geobau_itf.setText(self._itf(b"MD01MUCH24MN95I"))
        dlg.txt_geobau_dxf.setText(os.path.join(tempfile.mkdtemp(), "u.dxf"))
        self.assertFalse(dlg.btn_geobau.isEnabled())
        self.assertIn("MD01MUCH24MN95I", dlg.lbl_esito_dxf.text())

    def test_un_modello_illeggibile_avvisa_ma_non_blocca(self):
        percorso = os.path.join(tempfile.mkdtemp(), "strano.itf")
        with open(percorso, "wb") as f:
            f.write(b"SCNT\r\nMTID INTERLIS1\r\n")
        dlg = self._dialog_pronta(percorso)
        self.assertTrue(dlg.btn_import.isEnabled(),
                        "un dubbio non deve togliere una decisione all'utente")

    def test_l_importazione_si_ferma_prima_di_avviare_java(self):
        """Ultimo controllo: il file puo' essere cambiato da quando lo si e'
        scelto, e un pulsante acceso non e' una garanzia."""
        buono = self._itf()
        dlg = self._dialog_pronta(buono)
        # il file cambia sotto i piedi, senza passare dall'interfaccia
        with open(buono, "wb") as f:
            f.write(self.TESTA % b"MD01MUCH24MN95I")
        prima = len(_avvisi)
        dlg.run_import()
        self.assertGreater(len(_avvisi), prima)
        self.assertIsNone(getattr(dlg, "_last_itf_path", None),
                          "non deve nemmeno arrivare a preparare l'importazione")

    def test_la_memoria_rilegge_quando_il_file_cambia(self):
        dlg = TIDashboardDialog()
        percorso = self._itf()
        self.assertEqual(dlg._modello_di(percorso)[0], "ok")
        import time
        time.sleep(1.1)              # la memoria e' per (percorso, dimensione, data)
        with open(percorso, "wb") as f:
            f.write(self.TESTA % b"MD01MUCH24MN95I")
        self.assertEqual(dlg._modello_di(percorso)[0], "diverso")

    def test_il_geopackage_di_un_altro_modello_viene_segnalato(self):
        import sqlite3
        cartella = tempfile.mkdtemp()
        percorso = os.path.join(cartella, "altro.gpkg")
        con = sqlite3.connect(percorso)
        con.execute("CREATE TABLE T_ILI2DB_MODEL (filename TEXT, iliversion TEXT, "
                    "modelName TEXT, content TEXT, importDate INTEGER)")
        con.execute("INSERT INTO T_ILI2DB_MODEL VALUES "
                    "('x.ili','1.0','MD01MUCH24MN95I','',0)")
        con.commit()
        con.close()
        dlg = TIDashboardDialog()
        esito, trovato = dlg._modello_di(percorso, e_gpkg=True)
        self.assertEqual(esito, "diverso")
        self.assertEqual(trovato, "MD01MUCH24MN95I")


if __name__ == "__main__":
    risultato = unittest.main(exit=False, verbosity=2)
    _qgs.exitQgis()
    sys.exit(0 if risultato.result.wasSuccessful() else 1)
