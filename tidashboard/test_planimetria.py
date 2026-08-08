# Test del generatore di planimetrie. Eseguire con l'interprete di QGIS:
#   & "C:\Program Files\QGIS 4.2.0\bin\python-qgis.bat" test_planimetria.py
#
# Copre le criticita' trovate e corrette, cosi' non possono rientrare in
# silenzio: sovrapposizioni nel cartiglio, coordinate della griglia tagliate
# dal bordo, nomi che si sovrascrivono, stabilita' del centro di rotazione.
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qgis.core import (QgsApplication, QgsProject, QgsVectorLayer, QgsFeature,
                       QgsGeometry, QgsPointXY, QgsSingleSymbolRenderer,
                       QgsFillSymbol)
from qgis.PyQt.QtGui import QFont, QFontMetricsF

_qgs = QgsApplication([], False)
_qgs.initQgis()

from tidashboard import planimetria as P

CX, CY = 2718000.0, 1082000.0


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


def _mappa(layout):
    return [i for i in layout.items()
            if i.__class__.__name__ == "QgsLayoutItemMap"][0]


class TestConversioneGon(unittest.TestCase):
    def test_gon_a_gradi(self):
        for gon, gradi in ((0, 0.0), (50, 45.0), (100, 90.0), (200, 180.0), (400, 0.0)):
            self.assertAlmostEqual(P.gon_a_gradi(gon), gradi, places=9)


class TestScaleUfficiali(unittest.TestCase):
    def test_elenco_da_cap_1_5_1(self):
        self.assertEqual(P.SCALE_UFFICIALI_MU,
                         (200, 250, 500, 1000, 2000, 2500, 5000, 10000))

    def test_scala_fuori_elenco_rifiutata(self):
        with self.assertRaises(ValueError):
            P.crea_planimetria(QgsProject.instance(), [], QgsPointXY(CX, CY), 750)


class TestGeometriaFoglio(unittest.TestCase):
    def test_scala_ed_estensione_per_ogni_formato(self):
        prj = QgsProject.instance()
        lyr = _layer()
        for formato, w, h in P.FORMATI:
            for scala in (200, 1000, 10000):
                lay = P.crea_planimetria(prj, [lyr], QgsPointXY(CX, CY), scala,
                                         formato=formato, nome="T_%s_%d" % (formato, scala))
                m = _mappa(lay)
                self.assertAlmostEqual(m.scale(), scala, delta=0.5)
                # larghezza in metri = larghezza mappa in mm / 1000 * scala
                attesa = (w - 2 * P.MARGINE) / 1000.0 * scala
                self.assertAlmostEqual(m.extent().width(), attesa, delta=0.5)


class TestCentroDiRotazione(unittest.TestCase):
    def test_il_centro_inquadrato_non_si_sposta(self):
        prj = QgsProject.instance()
        lyr = _layer()
        for gon in (0, 25, 50, 100, 200, 399):
            lay = P.crea_planimetria(prj, [lyr], QgsPointXY(CX, CY), 1000,
                                     rotazione_gon=gon, nome="Rot_%s" % gon)
            e = _mappa(lay).extent()
            self.assertAlmostEqual((e.xMinimum() + e.xMaximum()) / 2, CX, places=6)
            self.assertAlmostEqual((e.yMinimum() + e.yMaximum()) / 2, CY, places=6)


class TestImprontaFoglio(unittest.TestCase):
    """L'anteprima sul canvas deve mostrare esattamente il terreno che finira'
    sul foglio: i vertici calcolati si confrontano con quelli che QGIS stessa
    riporta per la mappa del layout, rotazione compresa."""

    def _confronta(self, formato, scala, gon):
        lay = P.crea_planimetria(QgsProject.instance(), [_layer()],
                                 QgsPointXY(CX, CY), scala, formato=formato,
                                 rotazione_gon=gon, comune="Giubiasco",
                                 nome="Imp_%s_%d_%d" % (formato, scala, gon))
        atteso = _mappa(lay).visibleExtentPolygon()
        ottenuto = P.impronta_foglio(QgsPointXY(CX, CY), scala, formato, gon)
        # visibleExtentPolygon puo' partire da un vertice diverso: si
        # confrontano gli insiemi di vertici, ordinati.
        def chiave(p):
            return (round(p.x(), 3), round(p.y(), 3))
        a = sorted({chiave(p) for p in atteso})
        b = sorted({chiave(p) for p in ottenuto})
        self.assertEqual(len(b), 4, "l'impronta deve avere 4 vertici distinti")
        for (ax, ay), (bx, by) in zip(a, b):
            self.assertAlmostEqual(ax, bx, places=2,
                                   msg="%s 1:%d %s gon" % (formato, scala, gon))
            self.assertAlmostEqual(ay, by, places=2)

    def test_coincide_con_la_mappa_del_layout(self):
        for formato, _w, _h in P.FORMATI:
            for scala in (200, 1000, 10000):
                for gon in (0, 25, 50, 100, 150, 300):
                    self._confronta(formato, scala, gon)


class TestLayerSulFoglio(unittest.TestCase):
    """Il foglio prendeva TUTTI i layer caricati, anche quelli che il plugin
    spegne apposta perche' il piano non li rappresenta (identificatori dei
    punti di confine, cap.5.10). Riscontrato su un estratto reale di Chiasso a
    1:500: dieci numeri a dieci cifre stampati sopra il disegno."""

    def test_i_layer_spenti_nell_albero_restano_fuori(self):
        prj = QgsProject.instance()
        acceso, spento = _layer(), _layer()
        acceso.setName("acceso")
        spento.setName("spento")
        prj.addMapLayer(acceso)
        prj.addMapLayer(spento)
        nodo = prj.layerTreeRoot().findLayer(spento.id())
        self.assertIsNotNone(nodo, "il layer deve essere nell'albero")
        nodo.setItemVisibilityChecked(False)
        scelti = P._layers_visibili(prj, [acceso, spento])
        self.assertIn(acceso, scelti)
        self.assertNotIn(spento, scelti)

    def test_senza_albero_si_prendono_tutti(self):
        """Uso da script senza progetto: meglio disegnare tutto che niente."""
        a, b = _layer(), _layer()
        self.assertEqual(len(P._layers_visibili(None, [a, b])), 2)


class TestCartiglio(unittest.TestCase):
    """Il cartiglio aveva tre sovrapposizioni in tutti i formati (barra/
    dettagli, freccia/titolo, rotazione/dettagli): non si vedevano solo
    perche' i testi di prova erano corti."""

    def test_nessuna_sovrapposizione_fra_elementi(self):
        prj = QgsProject.instance()
        lyr = _layer()
        for formato, _w, _h in P.FORMATI:
            lay = P.crea_planimetria(prj, [lyr], QgsPointXY(CX, CY), 10000,
                                     formato=formato, rotazione_gon=50,
                                     comune="Bellinzona-Giubiasco",
                                     nome="Cart_%s" % formato)
            # il riquadro e la pagina contengono tutto per definizione
            esclusi = ("QgsLayoutItemShape", "QgsLayoutItemPage", "QgsLayoutItemMap")
            els = [i for i in lay.items()
                   if i.__class__.__name__.startswith("QgsLayoutItem")
                   and i.__class__.__name__ not in esclusi]
            for i in range(len(els)):
                for j in range(i + 1, len(els)):
                    a = els[i].sceneBoundingRect()
                    b = els[j].sceneBoundingRect()
                    inter = a.intersected(b)
                    self.assertFalse(
                        inter.width() > 0.5 and inter.height() > 0.5,
                        "%s e %s si sovrappongono di %.1f x %.1f mm su %s"
                        % (els[i].__class__.__name__, els[j].__class__.__name__,
                           inter.width(), inter.height(), formato))


class TestMargineGriglia(unittest.TestCase):
    """Con 8 mm di margine le coordinate uscivano tagliate dal bordo del
    foglio ("082000" invece di "1082000")."""

    def test_margine_ospita_una_coordinata(self):
        # La lettera della famiglia ("E "/"N ") fa parte dell'annotazione, e
        # allarga la stringa piu' misurata dal margine.
        fm = QFontMetricsF(QFont("Arial", 6))
        larghezza_mm = fm.horizontalAdvance("N 1082000") * 25.4 / 96.0
        self.assertLess(larghezza_mm + P.DIST_ANNOTAZIONI, P.MARGINE,
                        "il margine non basta all'annotazione di coordinata")


def _dettagli(layout):
    """Il riquadro di testo del cartiglio che porta scala, stato e legenda."""
    return [i for i in layout.items()
            if i.__class__.__name__ == "QgsLayoutItemLabel"
            and "Stato al:" in i.text()][0]


class TestDataDiValidita(unittest.TestCase):
    """'Stato al' e' la data di validita' dei dati (cap.1.5.7), non la data di
    stampa: scriverci d'ufficio l'odierna attesta un'attualita' che i dati
    possono non avere."""

    def test_la_data_passata_finisce_nel_cartiglio(self):
        lay = P.crea_planimetria(QgsProject.instance(), [_layer()],
                                 QgsPointXY(CX, CY), 1000,
                                 data_validita="14.03.2024", nome="Data_esplicita")
        self.assertIn("Stato al: 14.03.2024", _dettagli(lay).text())

    def test_senza_data_ripiega_sull_odierna(self):
        lay = P.crea_planimetria(QgsProject.instance(), [_layer()],
                                 QgsPointXY(CX, CY), 1000, nome="Data_assente")
        self.assertIn("Stato al: %s" % datetime.now().strftime("%d.%m.%Y"),
                      _dettagli(lay).text())


class TestFattoreProporzionalita(unittest.TestCase):
    """Cap.1.5.2: le dimensioni sono definite per l'1:1000 e a scale diverse va
    applicato un fattore. Verificato che il meccanismo QGIS lo realizza davvero:
    marcatore da 3.0 mm reso a 5.9 mm su un foglio 1:500."""

    def test_ingrandimenti_col_fattore_pieno(self):
        for scala, atteso in ((200, 5.0), (250, 4.0), (500, 2.0), (1000, 1.0)):
            self.assertAlmostEqual(P.fattore_proporzionale(scala), atteso, places=6)

    def test_i_due_prodotti_hanno_riferimenti_diversi(self):
        """Il piano RF e' definito all'1:1000, il piano di base all'1:5000
        (Weisung-BP-AV cap.2.2). Usare 1000 per entrambi sbagliava il fattore
        di cinque volte in PB-MU."""
        self.assertEqual(P.SCALA_RIFERIMENTO["gb"], 1000)
        self.assertEqual(P.SCALA_RIFERIMENTO["bp"], 5000)
        # a 1:5000 il piano di base e' alla sua scala di riferimento: fattore 1
        self.assertAlmostEqual(P.fattore_proporzionale(5000, "bp"), 1.0, places=6)
        # ...mentre il piano RF li' e' ridotto al limite di leggibilita'
        self.assertAlmostEqual(P.fattore_proporzionale(5000, "gb"), 0.8, places=6)
        # a 1:1000 vale l'opposto
        self.assertAlmostEqual(P.fattore_proporzionale(1000, "gb"), 1.0, places=6)
        self.assertAlmostEqual(P.fattore_proporzionale(1000, "bp"), 5.0, places=6)

    def test_riduzioni_limitate_dalla_leggibilita(self):
        """Il fattore pieno a 1:10000 varrebbe 0.1: la scrittura piu' piccola
        (1.5 mm) scenderebbe a 0.15 mm, non stampabile."""
        minimo = P.CAP_HEIGHT_MINIMA_STAMPA / P.CAP_HEIGHT_MINIMA_NORMA
        for scala in (2000, 2500, 5000, 10000):
            f = P.fattore_proporzionale(scala)
            self.assertAlmostEqual(f, minimo, places=6)
            self.assertGreaterEqual(f * P.CAP_HEIGHT_MINIMA_NORMA,
                                    P.CAP_HEIGHT_MINIMA_STAMPA)

    def test_i_layer_veri_non_vengono_toccati(self):
        """Il fattore vale per il FOGLIO: sui layer del progetto cambierebbe
        anche il canvas, dove l'utente zooma e i simboli sparirebbero alle
        scale piccole - il difetto per cui un primo tentativo fu tolto."""
        lyr = _layer()
        lyr.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple({})))
        prima = lyr.renderer().referenceScale()
        for scala in P.SCALE_UFFICIALI_MU:
            P.crea_planimetria(QgsProject.instance(), [lyr], QgsPointXY(CX, CY),
                               scala, nome="Rif_%d" % scala)
            self.assertEqual(lyr.renderer().referenceScale(), prima,
                             "la scala di riferimento del layer vero e' cambiata a 1:%d" % scala)

    def test_i_cloni_portano_la_scala_di_riferimento(self):
        prj = QgsProject.instance()
        lyr = _layer()
        lyr.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple({})))
        prj.addMapLayer(lyr, False)
        cloni, ids = P._layers_proporzionati(prj, [lyr], 500)
        self.assertEqual(len(ids), 1, "a 1:500 il foglio deve usare un clone")
        self.assertAlmostEqual(cloni[0].renderer().referenceScale(), 1000.0, places=3)
        # a 1:1000 il fattore e' 1: nessun clone, si usano i layer veri
        cloni, ids = P._layers_proporzionati(prj, [lyr], 1000)
        self.assertEqual(ids, [])
        self.assertIs(cloni[0], lyr)


class TestTitoloProdotto(unittest.TestCase):
    """Il titolo era fisso su "Piano per il registro fondiario" anche in
    modalita' piano di base: l'iscrizione piu' visibile del foglio dichiarava
    un prodotto diverso da quello estratto."""

    def _titolo(self, layout):
        return [i for i in layout.items()
                if i.__class__.__name__ == "QgsLayoutItemLabel"
                and "Piano" in i.text()][0].text()

    def test_ogni_prodotto_ha_il_suo_titolo(self):
        for prodotto, atteso in P.TITOLI_PRODOTTO.items():
            lay = P.crea_planimetria(QgsProject.instance(), [_layer()],
                                     QgsPointXY(CX, CY), 1000, prodotto=prodotto,
                                     comune="Giubiasco", nome="Prod_%s" % prodotto)
            self.assertEqual(self._titolo(lay), atteso)

    def test_prodotto_sconosciuto_rifiutato(self):
        with self.assertRaises(ValueError):
            P.crea_planimetria(QgsProject.instance(), [_layer()],
                               QgsPointXY(CX, CY), 1000, prodotto="xx")


class TestAvvertenzaValoreLegale(unittest.TestCase):
    """Il foglio ha titolo, cartiglio e simbologia di un prodotto ufficiale
    della misurazione: senza dicitura puo' essere scambiato per un estratto
    emesso dall'autorita' competente."""

    def _avvertenza(self, layout):
        for i in layout.items():
            if (i.__class__.__name__ == "QgsLayoutItemLabel"
                    and P.AVVERTENZA_VALORE_LEGALE in i.text()):
                return i
        return None

    def test_presente_in_entrambi_i_prodotti(self):
        for prodotto in P.TITOLI_PRODOTTO:
            lay = P.crea_planimetria(QgsProject.instance(), [_layer()],
                                     QgsPointXY(CX, CY), 1000, prodotto=prodotto,
                                     comune="Giubiasco", nome="Avv_%s" % prodotto)
            self.assertIsNotNone(self._avvertenza(lay),
                                 "manca la dicitura in modalita' %s" % prodotto)

    def test_in_rosso(self):
        lay = P.crea_planimetria(QgsProject.instance(), [_layer()],
                                 QgsPointXY(CX, CY), 1000, comune="Giubiasco",
                                 nome="AvvRosso")
        colore = self._avvertenza(lay).fontColor()
        self.assertEqual((colore.red(), colore.green(), colore.blue()),
                         (P.C_AVVERTENZA.red(), P.C_AVVERTENZA.green(),
                          P.C_AVVERTENZA.blue()))
        self.assertGreater(colore.red(), 150, "il rosso deve essere evidente")
        self.assertLess(max(colore.green(), colore.blue()), 100)


class TestComuneObbligatorio(unittest.TestCase):
    def test_comune_vuoto_avvisa(self):
        righe = []
        P.crea_planimetria(QgsProject.instance(), [_layer()], QgsPointXY(CX, CY),
                           1000, comune="", nome="SenzaComune", log=righe.append)
        self.assertTrue(any("Comune non indicato" in r for r in righe),
                        "il comune mancante e' passato in silenzio")

    def test_comune_indicato_non_avvisa(self):
        righe = []
        P.crea_planimetria(QgsProject.instance(), [_layer()], QgsPointXY(CX, CY),
                           1000, comune="Giubiasco", nome="ConComune", log=righe.append)
        self.assertFalse(any("Comune non indicato" in r for r in righe))


class TestPassoGriglia(unittest.TestCase):
    """Le annotazioni sulla cornice sono coordinate nazionali: con passi non
    tondi (25 m a 1:250, 250 m a 1:2500) uscivano valori come 2717925."""

    def test_solo_passi_tondi_a_ogni_scala_ufficiale(self):
        for scala in P.SCALE_UFFICIALI_MU:
            passo = P.intervallo_griglia(scala)
            self.assertIn(passo, [float(p) for p in P.PASSI_GRIGLIA],
                          "passo %s non tondo a 1:%d" % (passo, scala))

    def test_le_due_scale_che_sbagliavano(self):
        self.assertEqual(P.intervallo_griglia(250), 20.0)     # era 25 m
        self.assertEqual(P.intervallo_griglia(2500), 200.0)   # era 250 m

    def test_spaziatura_sulla_carta_utilizzabile(self):
        for scala in P.SCALE_UFFICIALI_MU:
            mm = P.intervallo_griglia(scala) / float(scala) * 1000.0
            self.assertTrue(60.0 <= mm <= 140.0,
                            "a 1:%d le croci distano %.0f mm" % (scala, mm))

    def test_serie_125_decrescente(self):
        for valore, atteso in ((100.0, 50.0), (50.0, 20.0), (20.0, 10.0),
                               (10.0, 5.0), (5.0, 2.0), (2.0, 1.0), (1.0, 0.5)):
            self.assertAlmostEqual(P._giu_serie_125(valore), atteso, places=9)

    def test_serie_125_non_oltre(self):
        for valore, atteso in ((13.35, 10.0), (66.75, 50.0), (267.0, 200.0),
                               (100.0, 100.0), (5.0, 5.0), (0.267, 0.2)):
            self.assertAlmostEqual(P._serie_125_non_oltre(valore), atteso, places=9)


class TestBarraDiScala(unittest.TestCase):
    """La larghezza veniva imposta a quella della colonna del cartiglio: la
    barra risultava stirata o compressa senza che i suoi capisaldi cambiassero,
    cioe' la lunghezza disegnata non corrispondeva ai metri annotati."""

    def _barra(self, layout):
        return [i for i in layout.items()
                if i.__class__.__name__ == "QgsLayoutItemScaleBar"][0]

    def test_dimensione_naturale_non_forzata(self):
        for scala in P.SCALE_UFFICIALI_MU:
            lay = P.crea_planimetria(QgsProject.instance(), [_layer()],
                                     QgsPointXY(CX, CY), scala,
                                     comune="Giubiasco", nome="Barra_%d" % scala)
            barra = self._barra(lay)
            prima = barra.sizeWithUnits().width()
            barra.resizeToMinimumWidth()
            self.assertAlmostEqual(barra.sizeWithUnits().width(), prima, places=3,
                                   msg="barra deformata a 1:%d" % scala)

    def test_caposaldo_tondo(self):
        """applyDefaultSize proponeva capisaldi come 8 m a 1:500 e 75 m a
        1:5000: su una barra di scala vanno letti a colpo d'occhio."""
        for scala in P.SCALE_UFFICIALI_MU:
            lay = P.crea_planimetria(QgsProject.instance(), [_layer()],
                                     QgsPointXY(CX, CY), scala,
                                     comune="Giubiasco", nome="Capo_%d" % scala)
            ups = self._barra(lay).unitsPerSegment()
            self.assertAlmostEqual(P._serie_125_non_oltre(ups), ups, places=6,
                                   msg="caposaldo %s non tondo a 1:%d" % (ups, scala))

    def test_resta_dentro_il_cartiglio(self):
        for formato, _w, _h in P.FORMATI:
            for scala in P.SCALE_UFFICIALI_MU:
                lay = P.crea_planimetria(QgsProject.instance(), [_layer()],
                                         QgsPointXY(CX, CY), scala, formato=formato,
                                         comune="Giubiasco",
                                         nome="BarraC_%s_%d" % (formato, scala))
                riquadro = [i for i in lay.items()
                            if i.__class__.__name__ == "QgsLayoutItemShape"][0]
                barra = self._barra(lay).sceneBoundingRect()
                self.assertLessEqual(barra.right(),
                                     riquadro.sceneBoundingRect().right() + 0.5,
                                     "barra fuori dal cartiglio a 1:%d su %s"
                                     % (scala, formato))


class TestAnnotazioniGriglia(unittest.TestCase):
    """Ruotando il foglio le linee di griglia tagliano tutti e quattro i lati,
    quindi Est e Nord finiscono sullo stesso bordo: ogni coordinata deve dire
    a quale famiglia appartiene, senza che se ne perda nessuna."""

    def test_ogni_coordinata_porta_la_sua_lettera(self):
        from qgis.core import QgsLayoutItemMapGrid as G
        lay = P.crea_planimetria(QgsProject.instance(), [_layer()],
                                 QgsPointXY(CX, CY), 1000, rotazione_gon=50,
                                 comune="Giubiasco", nome="Annot")
        griglia = _mappa(lay).grid()
        self.assertEqual(griglia.annotationFormat(), G.CustomFormat)
        espressione = griglia.annotationExpression()
        self.assertIn("@grid_axis", espressione)
        self.assertIn("'E '", espressione)
        self.assertIn("'N '", espressione)

    def test_nessun_lato_scarta_annotazioni(self):
        """La variante 'Nord solo ai lati, Est solo sopra e sotto' faceva
        sparire le Est che escono dai lati verticali."""
        from qgis.core import QgsLayoutItemMapGrid as G
        lay = P.crea_planimetria(QgsProject.instance(), [_layer()],
                                 QgsPointXY(CX, CY), 1000, rotazione_gon=50,
                                 comune="Giubiasco", nome="Annot2")
        griglia = _mappa(lay).grid()
        for lato in (G.Left, G.Right, G.Top, G.Bottom):
            self.assertEqual(griglia.annotationDisplay(lato), G.ShowAll)


class TestFrecciaNord(unittest.TestCase):
    """La freccia deve puntare al nord del TERRENO cosi' come appare sul
    foglio, non verso l'alto del foglio: ruotando la mappa il nord si sposta e
    la freccia deve seguirlo.

    La direzione attesa non e' presa dal codice della freccia ma ricavata da
    'impronta_foglio', che a sua volta e' stata verificata contro
    visibleExtentPolygon(). L'impronta manda la direzione locale del foglio
    (dx, dy) sul terreno con una rotazione di +a; il nord del terreno (0, 1)
    finisce quindi sul foglio in (sin a, cos a), cioe' a 'a' gradi in senso
    orario rispetto all'alto del foglio."""

    @staticmethod
    def _freccia(layout):
        for i in layout.items():
            if i.__class__.__name__ == "QgsLayoutItemPicture":
                return i
        return None

    def test_segue_la_rotazione_del_foglio(self):
        for gon in (0, 50, 100, 150, 200, 333):
            lay = P.crea_planimetria(QgsProject.instance(), [_layer()],
                                     QgsPointXY(CX, CY), 1000, rotazione_gon=gon,
                                     comune="Giubiasco", nome="Nord%s" % gon)
            atteso = P.gon_a_gradi(gon) % 360
            reale = self._freccia(lay).pictureRotation() % 360
            scarto = (reale - atteso + 180) % 360 - 180
            self.assertAlmostEqual(scarto, 0.0, places=3,
                                   msg="a %s gon il nord del terreno cade a %.1f gradi "
                                       "dall'alto del foglio ma la freccia punta a %.1f"
                                       % (gon, atteso, reale))

    def test_agganciata_alla_mappa_e_al_nord_reticolato(self):
        """Se il collegamento salta la freccia resta ferma a 0 e il test sopra
        passerebbe comunque per la sola rotazione nulla."""
        lay = P.crea_planimetria(QgsProject.instance(), [_layer()],
                                 QgsPointXY(CX, CY), 1000, rotazione_gon=50,
                                 comune="Giubiasco", nome="NordLink")
        freccia = self._freccia(lay)
        from qgis.core import QgsLayoutItemPicture as Pic
        self.assertIs(freccia.linkedMap(), _mappa(lay))
        self.assertEqual(freccia.northMode(), Pic.GridNorth)


class TestNomiUnivoci(unittest.TestCase):
    def test_estratti_diversi_non_si_sovrascrivono(self):
        prj = QgsProject.instance()
        lyr = _layer()
        a = P.crea_planimetria(prj, [lyr], QgsPointXY(CX, CY), 1000)
        b = P.crea_planimetria(prj, [lyr], QgsPointXY(CX + 5000, CY), 1000)
        self.assertNotEqual(a.name(), b.name())
        nomi = [l.name() for l in prj.layoutManager().layouts()]
        self.assertIn(a.name(), nomi)
        self.assertIn(b.name(), nomi)

    def test_stesso_estratto_sostituisce_invece_di_duplicare(self):
        prj = QgsProject.instance()
        lyr = _layer()
        primo = P.crea_planimetria(prj, [lyr], QgsPointXY(CX, CY), 500)
        # il nome va letto ORA: rigenerando lo stesso estratto il layout
        # precedente viene rimosso e il suo wrapper Python resta appeso a un
        # oggetto C++ distrutto (RuntimeError al primo accesso).
        nome = primo.name()
        P.crea_planimetria(prj, [lyr], QgsPointXY(CX, CY), 500)
        nomi = [l.name() for l in prj.layoutManager().layouts()]
        self.assertEqual(nomi.count(nome), 1)


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2)
    _qgs.exitQgis()
    sys.exit(0 if result.result.wasSuccessful() else 1)
