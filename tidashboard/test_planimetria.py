# Test del generatore di planimetrie. Eseguire con l'interprete di QGIS:
#   & "C:\Program Files\QGIS 4.2.0\bin\python-qgis.bat" test_planimetria.py
#
# Copre le criticita' trovate e corrette, cosi' non possono rientrare in
# silenzio: sovrapposizioni nel cartiglio, coordinate della griglia tagliate
# dal bordo, nomi che si sovrascrivono, stabilita' del centro di rotazione.
import math
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


class TestScalaCheContiene(unittest.TestCase):
    """Centrare il foglio su un fondo non basta: la scala resta quella scelta
    prima, e un fondo piu' grande del foglio viene tagliato. Misurato sui dati
    di Mendrisio: su A4 verticale non ci sta il 25% dei fondi a 1:500 e il
    7.7% a 1:1000."""

    def test_sceglie_la_scala_piu_dettagliata_che_basta(self):
        larghezza, altezza = P.area_mappa("A4 verticale")
        # un oggetto che riempie esattamente il foglio a 1:500
        dx, dy = larghezza / 1000.0 * 500, altezza / 1000.0 * 500
        self.assertEqual(P.scala_che_contiene(dx, dy, "A4 verticale"), 500)

    def test_un_metro_in_piu_fa_salire_di_scala(self):
        larghezza, altezza = P.area_mappa("A4 verticale")
        dx, dy = larghezza / 1000.0 * 500 + 1, altezza / 1000.0 * 500
        self.assertEqual(P.scala_che_contiene(dx, dy, "A4 verticale"), 1000)

    def test_il_formato_conta(self):
        """Lo stesso oggetto, largo e basso, ci sta in orizzontale e non in
        verticale."""
        larghezza, _ = P.area_mappa("A4 orizzontale")
        dx, dy = larghezza / 1000.0 * 500, 10.0
        self.assertEqual(P.scala_che_contiene(dx, dy, "A4 orizzontale"), 500)
        self.assertGreater(P.scala_che_contiene(dx, dy, "A4 verticale"), 500)

    def test_oltre_ogni_scala_ufficiale(self):
        """Non si inventa una scala fuori elenco: si dice che non ci sta."""
        self.assertIsNone(P.scala_che_contiene(50000, 50000, "A4 verticale"))

    def test_il_fondo_piu_grande_di_mendrisio(self):
        """2174 x 1316 m, misurato sui dati reali. Su A4 VERTICALE non ci sta
        in nessuna scala ufficiale - a 1:10000 il foglio copre 1820 m di
        larghezza e ne servono 2174 - mentre in ORIZZONTALE ci sta, perche'
        li' la larghezza vale 2690 m. E' il caso che mostra perche' il
        formato va nel conto e non basta guardare la scala."""
        self.assertIsNone(P.scala_che_contiene(2174, 1316, "A4 verticale"))
        self.assertEqual(P.scala_che_contiene(2174, 1316, "A4 orizzontale"), 10000)


class TestNoveIscrizioni(unittest.TestCase):
    """Il cap.1.5.7 nella versione IN VIGORE (stato 1.2.2014) elenca NOVE
    iscrizioni obbligatorie; la versione marzo 2007, su cui era stato costruito
    il cartiglio, ne elencava sette. Mancavano i due cenni."""

    @staticmethod
    def _testi(lay):
        return "\n".join(i.text() for i in lay.items()
                         if i.__class__.__name__ == "QgsLayoutItemLabel")

    def test_ci_sono_tutte_e_nove(self):
        lay = P.crea_planimetria(QgsProject.instance(), [_layer()],
                                 QgsPointXY(CX, CY), 1000, comune="Giubiasco",
                                 data_validita="01.03.2024", nome="Nove")
        testo = self._testi(lay)
        for atteso in ("Piano per il registro fondiario",   # 1
                       "Giubiasco",                          # 2
                       "Scala 1:1000",                       # 4
                       "01.03.2024",                         # 6 data di validita'
                       "in progetto",                        # 7 cenno
                       "spostamenti permanenti",             # 8 cenno
                       "cadastre.ch/legende"):               # 9
            self.assertIn(atteso, testo, atteso)
        # 3 la direzione del nord e 5 il riferimento alla rete delle coordinate
        # non sono testi: sono la freccia e il reticolo, verificati altrove.
        self.assertTrue([i for i in lay.items()
                         if i.__class__.__name__ == "QgsLayoutItemPicture"])
        self.assertTrue(_mappa(lay).grid().enabled())

    def test_il_cenno_sugli_spostamenti_dice_il_vero(self):
        """Senza zone di movimento fra i layer, scrivere "sono rappresentati"
        sarebbe una dichiarazione falsa sul foglio."""
        self.assertEqual(P.cenno_spostamenti([]), P.CENNO_MOVIMENTO_NO)
        self.assertEqual(P.cenno_spostamenti([_layer()]), P.CENNO_MOVIMENTO_NO)
        zone = _layer()
        zone.setName("zone_di_movimento_movimento")
        self.assertEqual(P.cenno_spostamenti([zone]), P.CENNO_MOVIMENTO_SI)

    def test_il_cartiglio_contiene_tutte_le_righe(self):
        """Le due iscrizioni in piu' non devono uscire dal riquadro: e' il
        motivo per cui H_CARTIGLIO e' passato da 32 a 40 mm."""
        lay = P.crea_planimetria(QgsProject.instance(), [_layer()],
                                 QgsPointXY(CX, CY), 1000, comune="Giubiasco",
                                 nome="NoveIngombro")
        limite = lay.pageCollection().page(0).pageSize().height() - P.MARGINE
        for i in lay.items():
            if i.__class__.__name__ != "QgsLayoutItemLabel":
                continue
            self.assertLessEqual(i.pos().y() + i.rect().height(), limite + 0.01,
                                 i.text()[:40])


class TestDichiarazioneFattore(unittest.TestCase):
    """Il limite di leggibilita' e' uno scostamento voluto dalla lettera del
    cap.1.5.2, ma finche' restava scritto solo nel README chi riceveva il
    foglio non poteva saperlo. Ora va dichiarato nel cartiglio."""

    def test_dove_morde_il_limite(self):
        """Non e' un caso raro: 4 delle 8 scale RF e 1 delle 8 PB."""
        limitate_gb = [s for s in P.SCALE_UFFICIALI_MU
                       if P.nota_fattore(s, "gb")]
        limitate_bp = [s for s in P.SCALE_UFFICIALI_MU
                       if P.nota_fattore(s, "bp")]
        self.assertEqual(limitate_gb, [2000, 2500, 5000, 10000])
        self.assertEqual(limitate_bp, [10000])

    def test_niente_nota_quando_il_fattore_e_quello_della_norma(self):
        for scala in (200, 250, 500, 1000):
            self.assertEqual(P.nota_fattore(scala, "gb"), "",
                             "1:%d non ha scostamenti da dichiarare" % scala)

    def test_la_nota_finisce_nel_cartiglio(self):
        lay = P.crea_planimetria(QgsProject.instance(), [_layer()],
                                 QgsPointXY(CX, CY), 5000, comune="Giubiasco",
                                 nome="Fatt5000")
        testi = [i.text() for i in lay.items()
                 if i.__class__.__name__ == "QgsLayoutItemLabel"]
        riga = [t for t in testi if "Scala 1:5000" in t]
        self.assertTrue(riga, "manca la riga della scala nel cartiglio")
        self.assertIn("×0.80", riga[0])
        self.assertIn("×0.20", riga[0])
        self.assertIn("anziché", riga[0],
                      "il cartiglio va stampato con gli accenti veri")

    def test_senza_scostamento_la_riga_resta_pulita(self):
        lay = P.crea_planimetria(QgsProject.instance(), [_layer()],
                                 QgsPointXY(CX, CY), 1000, comune="Giubiasco",
                                 nome="Fatt1000")
        testi = [i.text() for i in lay.items()
                 if i.__class__.__name__ == "QgsLayoutItemLabel"]
        riga = [t for t in testi if "Scala 1:1000" in t][0]
        self.assertNotIn("cap. 1.5.2", riga)

    def test_la_nota_non_sfonda_il_cartiglio(self):
        """La nota sta sulla riga della scala proprio per non aggiungere una
        quarta riga: se qualcuno la spostasse su una riga sua, il blocco
        uscirebbe dai 32 mm del riquadro."""
        lay = P.crea_planimetria(QgsProject.instance(), [_layer()],
                                 QgsPointXY(CX, CY), 10000, comune="Giubiasco",
                                 nome="FattIngombro")
        for i in lay.items():
            if i.__class__.__name__ != "QgsLayoutItemLabel":
                continue
            if "Scala 1:10000" not in i.text():
                continue
            # L'invariante non e' il numero di righe del blocco - da quando il
            # cap.1.5.7 in vigore ne impone nove sono cinque - ma che la nota
            # sul fattore stia SULLA STESSA RIGA della scala, senza aggiungerne
            # una propria.
            riga_scala = [r for r in i.text().split("\n") if r.startswith("Scala")][0]
            self.assertIn("cap. 1.5.2", riga_scala)
            fondo = i.pos().y() + i.rect().height()
            limite = lay.pageCollection().page(0).pageSize().height() - P.MARGINE
            self.assertLessEqual(fondo, limite + 0.01)

    def test_lettera_norma_toglie_il_limite(self):
        self.assertAlmostEqual(P.fattore_proporzionale(10000, "gb"), 0.8)
        self.assertAlmostEqual(
            P.fattore_proporzionale(10000, "gb", lettera_norma=True), 0.1)
        self.assertEqual(P.nota_fattore(10000, "gb", lettera_norma=True), "")

    def test_lettera_norma_avvisa_che_non_si_stampa(self):
        altezza, illeggibile = P.fattore_illeggibile(
            P.fattore_proporzionale(10000, "gb", lettera_norma=True))
        self.assertAlmostEqual(altezza, 0.15)
        self.assertTrue(illeggibile)
        # col limite attivo invece resta stampabile
        _, illeggibile = P.fattore_illeggibile(
            P.fattore_proporzionale(10000, "gb"))
        self.assertFalse(illeggibile)


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


class TestMigliorFoglio(unittest.TestCase):
    """La scelta del foglio non e' piu' binaria: se alla scala voluta l'oggetto
    ci sta su un altro formato, cambiare formato costa meno che dimezzare il
    dettaglio."""

    def test_se_va_gia_bene_non_cambia_niente(self):
        formato, scala, motivo = P.miglior_foglio(20.0, 30.0, 500, "A4 verticale")
        self.assertEqual((formato, scala, motivo), ("A4 verticale", 500, ""))

    def test_preferisce_girare_il_foglio_invece_di_perdere_scala(self):
        # Largo quanto l'A4 orizzontale e basso: verticale non lo contiene.
        larghezza, _ = P.area_utile("A4 orizzontale", P.MARGINE_CORTESIA)
        dx = larghezza / 1000.0 * 500 - 1.0
        formato, scala, motivo = P.miglior_foglio(dx, 10.0, 500, "A4 verticale")
        self.assertEqual(scala, 500, "la scala non doveva cambiare")
        self.assertEqual(motivo, "formato")
        self.assertEqual(formato, "A4 orizzontale")

    def test_quando_serve_davvero_rimpicciolisce(self):
        formato, scala, motivo = P.miglior_foglio(1500.0, 1500.0, 500, "A4 verticale")
        self.assertEqual(motivo, "scala")
        self.assertGreater(scala, 500)
        self.assertIsNotNone(formato)

    def test_oltre_ogni_formato_e_ogni_scala(self):
        formato, scala, motivo = P.miglior_foglio(90000.0, 90000.0, 500, "A4 verticale")
        self.assertIsNone(formato)
        self.assertIsNone(scala)
        self.assertEqual(motivo, "impossibile")

    def test_il_margine_di_cortesia_esclude_chi_tocca_la_cornice(self):
        # Esattamente della misura dell'area di mappa: ci "sta", ma incollato.
        larghezza, altezza = P.area_mappa("A4 verticale")
        dx, dy = larghezza / 1000.0 * 500, altezza / 1000.0 * 500
        self.assertEqual(P.scala_che_contiene(dx, dy, "A4 verticale"), 500)
        formato, _, motivo = P.miglior_foglio(dx, dy, 500, "A4 verticale")
        self.assertNotEqual(motivo, "", "a filo di cornice non e' 'va bene'")


class TestEstensioneRuotata(unittest.TestCase):
    def test_senza_rotazione_non_tocca_niente(self):
        self.assertEqual(P.estensione_ruotata(30.0, 10.0, 0.0), (30.0, 10.0))

    def test_a_cento_gon_i_due_lati_si_scambiano(self):
        dx, dy = P.estensione_ruotata(30.0, 10.0, 100.0)
        self.assertAlmostEqual(dx, 10.0, places=6)
        self.assertAlmostEqual(dy, 30.0, places=6)

    def test_in_diagonale_i_due_lati_si_pareggiano(self):
        # A 50 gon (45 gradi) un rettangolo 3:1 non diventa piu' largo - anzi,
        # 30x10 vale 28.28 - ma diventa QUADRATO: il lato corto passa da 10 a
        # 28.28, ed e' quello che fa uscire il fondo dalla cornice.
        dx, dy = P.estensione_ruotata(30.0, 10.0, 50.0)
        self.assertAlmostEqual(dx, dy, places=6)
        self.assertGreater(dy, 10.0)


class TestRettangoloMinimo(unittest.TestCase):
    def test_rettangolo_allineato_resta_com_e(self):
        dx, dy, _rot = P.rettangolo_minimo([(0, 0), (40, 0), (40, 10), (0, 10)])
        self.assertAlmostEqual(max(dx, dy), 40.0, places=6)
        self.assertAlmostEqual(min(dx, dy), 10.0, places=6)

    def test_in_diagonale_trova_il_lato_corto(self):
        # Lo stesso rettangolo 40x10 girato di 45 gradi: l'extent allineato
        # agli assi misura 35x35, il rettangolo minimo deve tornare 40x10.
        import math as _m
        a = _m.radians(45.0)
        punti = [(x * _m.cos(a) - y * _m.sin(a), x * _m.sin(a) + y * _m.cos(a))
                 for x, y in ((0, 0), (40, 0), (40, 10), (0, 10))]
        dx, dy, rot = P.rettangolo_minimo(punti)
        self.assertAlmostEqual(max(dx, dy), 40.0, places=5)
        self.assertAlmostEqual(min(dx, dy), 10.0, places=5)
        self.assertTrue(0.0 <= rot < 400.0)
        xs = [p[0] for p in punti]
        self.assertGreater(max(xs) - min(xs), 34.0, "l'extent allineato e' molto piu' largo")

    def test_punti_degeneri_non_esplodono(self):
        self.assertEqual(P.rettangolo_minimo([(5, 5), (5, 5)])[:2], (0.0, 0.0))


class TestOrdineDiDisegnoSulFoglio(unittest.TestCase):
    """Regressione da un PDF reale: sul canvas la gerarchia del cap. 1.5.4 era
    giusta, sul FOGLIO no. La planimetria riceveva i layer nell'ordine di
    CARICAMENTO e li passava così a setLayers(), che disegna il primo in cima:
    le linee di confine finivano sopra i punti di confine."""

    def _due_layer(self, prj):
        sotto, sopra = _layer(), _layer()
        sotto.setName("copertura")      # va disegnato in fondo
        sopra.setName("punti")          # va disegnato in cima
        prj.addMapLayer(sotto)
        prj.addMapLayer(sopra)
        return sotto, sopra

    def test_il_foglio_segue_l_ordine_del_progetto_non_quello_di_caricamento(self):
        prj = QgsProject.instance()
        prj.removeAllMapLayers()
        sotto, sopra = self._due_layer(prj)
        # il progetto dichiara: prima i punti (in cima), poi la copertura
        prj.layerTreeRoot().setHasCustomLayerOrder(True)
        prj.layerTreeRoot().setCustomLayerOrder([sopra, sotto])
        # ...e la planimetria li riceve nell'ordine SBAGLIATO, come fa il plugin
        lay = P.crea_planimetria(prj, [sotto, sopra], QgsPointXY(CX, CY), 1000,
                                 nome="OrdineFoglio")
        nomi = [l.name() for l in _mappa(lay).layers()]
        self.assertEqual(nomi[0].split()[0], "punti",
                         "in cima al foglio deve esserci il layer che il progetto mette per primo")

    def test_senza_ordine_personalizzato_si_rispetta_quello_ricevuto(self):
        prj = QgsProject.instance()
        prj.removeAllMapLayers()
        sotto, sopra = self._due_layer(prj)
        prj.layerTreeRoot().setHasCustomLayerOrder(False)
        lay = P.crea_planimetria(prj, [sopra, sotto], QgsPointXY(CX, CY), 1000,
                                 nome="OrdineRicevuto")
        nomi = [l.name() for l in _mappa(lay).layers()]
        self.assertEqual(nomi[0].split()[0], "punti")

    def test_un_layer_fuori_dall_ordine_finisce_in_coda(self):
        prj = QgsProject.instance()
        prj.removeAllMapLayers()
        sotto, sopra = self._due_layer(prj)
        estraneo = _layer()
        estraneo.setName("estraneo")
        prj.addMapLayer(estraneo)
        prj.layerTreeRoot().setHasCustomLayerOrder(True)
        prj.layerTreeRoot().setCustomLayerOrder([sopra, sotto])
        ordinati = P.ordina_come_il_progetto(prj, [estraneo, sotto, sopra])
        self.assertEqual([l.name() for l in ordinati], ["punti", "copertura", "estraneo"])


class TestStatoCapienza(unittest.TestCase):
    """Mentre si trascina il foglio la domanda non è quale scala serve, ma se
    il fondo agganciato è ancora tutto dentro."""

    def _quadrato(self, cx, cy, lato):
        m = lato / 2.0
        return [(cx - m, cy - m), (cx + m, cy - m), (cx + m, cy + m), (cx - m, cy + m)]

    def test_al_centro_e_dentro(self):
        punti = self._quadrato(CX, CY, 20.0)
        self.assertEqual(
            P.stato_capienza(punti, QgsPointXY(CX, CY), 500, "A4 verticale"), "dentro")

    def test_spostando_il_foglio_il_fondo_ne_esce(self):
        punti = self._quadrato(CX, CY, 20.0)
        # il foglio a 1:500 su A4 verticale copre ~91 x 114 m: 200 m di
        # spostamento lo porta sicuramente via
        lontano = QgsPointXY(CX + 200.0, CY)
        self.assertEqual(P.stato_capienza(punti, lontano, 500, "A4 verticale"), "fuori")

    def test_a_filo_di_cornice_e_stretto_non_dentro(self):
        larghezza, _ = P.area_mappa("A4 verticale")
        # largo quanto l'area di mappa: ci sta, ma tocca la cornice
        punti = self._quadrato(CX, CY, larghezza / 1000.0 * 500 - 0.5)
        self.assertEqual(
            P.stato_capienza(punti, QgsPointXY(CX, CY), 500, "A4 verticale"), "stretto")

    def test_la_rotazione_del_foglio_conta(self):
        # Striscia lunga e stretta orizzontale: su A4 verticale a 1:500 il
        # foglio è largo ~91 m e alto ~114, quindi dritta non ci sta e girata
        # sì. 100 m e non 110: a 110 il gioco che resta è 2.25 m per lato, meno
        # dei 2.5 del margine di cortesia, e la risposta giusta sarebbe
        # "stretto" - il che proverebbe un'altra cosa.
        lunghezza = 100.0
        punti = [(CX - lunghezza / 2, CY - 3), (CX + lunghezza / 2, CY - 3),
                 (CX + lunghezza / 2, CY + 3), (CX - lunghezza / 2, CY + 3)]
        centro = QgsPointXY(CX, CY)
        self.assertEqual(P.stato_capienza(punti, centro, 500, "A4 verticale"), "fuori")
        self.assertEqual(
            P.stato_capienza(punti, centro, 500, "A4 verticale", rotazione_gon=100.0),
            "dentro")

    def test_senza_geometria_non_si_pronuncia(self):
        self.assertIsNone(P.stato_capienza([], QgsPointXY(CX, CY), 500))
        self.assertIsNone(P.stato_capienza([(0, 0)], None, 500))


class TestRotazioneCheContiene(unittest.TestCase):
    """La rotazione proposta deve funzionare davvero: si verifica sull'impronta
    vera del foglio, non sull'angolo del rettangolo minimo. Il segno della
    rotazione e' il dettaglio che si sbaglia in silenzio."""

    def _fondo_storto(self, lunghezza, larghezza, gradi):
        a = math.radians(gradi)
        return [(CX + x * math.cos(a) - y * math.sin(a),
                 CY + x * math.sin(a) + y * math.cos(a))
                for x, y in ((-lunghezza / 2, -larghezza / 2),
                             (lunghezza / 2, -larghezza / 2),
                             (lunghezza / 2, larghezza / 2),
                             (-lunghezza / 2, larghezza / 2))]

    def test_fondo_storto_ci_sta_girando_il_foglio(self):
        # Lungo quanto il lato lungo dell'A4 verticale a 1:500 e stretto: dritto
        # non ci sta (l'ingombro in diagonale supera il lato corto), storto si'.
        _larghezza, altezza = P.area_utile("A4 verticale", P.MARGINE_CORTESIA)
        lunghezza = altezza / 1000.0 * 500 - 2.0
        punti = self._fondo_storto(lunghezza, 8.0, 40.0)
        xs = [p[0] for p in punti]
        ys = [p[1] for p in punti]
        dritto = P.miglior_foglio(max(xs) - min(xs), max(ys) - min(ys), 500,
                                  "A4 verticale")
        self.assertNotEqual(dritto[2], "", "dritto non doveva starci")
        giro = P.rotazione_che_contiene(punti, QgsPointXY(CX, CY), 500, "A4 verticale")
        self.assertIsNotNone(giro, "girando il foglio ci deve stare")
        # e la rotazione proposta deve contenerlo per davvero
        impronta = QgsGeometry.fromPolygonXY(
            [P.impronta_foglio(QgsPointXY(CX, CY), 500, "A4 verticale", giro)])
        for x, y in punti:
            self.assertTrue(impronta.contains(QgsGeometry.fromPointXY(QgsPointXY(x, y))),
                            "vertice fuori dal foglio ruotato di %.1f gon" % giro)

    def test_fondo_troppo_grande_non_si_salva_girando(self):
        punti = self._fondo_storto(5000.0, 4000.0, 30.0)
        self.assertIsNone(
            P.rotazione_che_contiene(punti, QgsPointXY(CX, CY), 500, "A4 verticale"))

    def test_senza_geometria_non_propone_niente(self):
        self.assertIsNone(P.rotazione_che_contiene([], QgsPointXY(CX, CY), 500))
        self.assertIsNone(P.rotazione_che_contiene([(0, 0)], None, 500))


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2)
    _qgs.exitQgis()
    sys.exit(0 if result.result.wasSuccessful() else 1)
