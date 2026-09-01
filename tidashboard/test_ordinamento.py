# Prove dei nomi leggibili e del raggruppamento dell'albero dei layer.
#
# ordinamento.py non importa QGIS in testa - e non deve: relazioni.py dipende
# da lui e gira nel lavoro di CI da dieci secondi. Il gruppo che costruisce
# davvero un albero di layer ha bisogno di QGIS e si guarda da se', con la
# guardia rumorosa: se QGIS e' atteso e non si importa, la prova FALLISCE
# invece di saltare.
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tidashboard import ordinamento as O

QGIS_ATTESO = bool(os.environ.get("TIDASHBOARD_QGIS_ATTESO"))
try:
    from qgis.core import QgsApplication, QgsProject, QgsVectorLayer
    C_E_QGIS = True
    PERCHE_NO = ""
except ImportError as errore:
    C_E_QGIS = False
    PERCHE_NO = str(errore)


class NomiLeggibili(unittest.TestCase):

    def test_underscore_diventa_spazio(self):
        self.assertEqual(O.nome_leggibile("Punto_di_confine", "x"), "Punto di confine")

    def test_le_sigle_concatenate_hanno_un_nome_scritto(self):
        """"SuperficieCS" con il solo underscore->spazio resterebbe
        "SuperficieCS": e' il caso per cui esiste la tabella dei nomi."""
        self.assertEqual(O.nome_leggibile("SuperficieCS", "x"),
                         "Superficie (copertura del suolo)")

    def test_le_tabelle_pos_sono_etichette(self):
        """Una tabella "PosXxx" e' il punto di iscrizione di un'etichetta, non
        l'oggetto: chiamarla come l'oggetto ne farebbe due voci uguali nel
        pannello."""
        self.assertEqual(O.nome_leggibile("PosNome_del_luogo", "x"),
                         "Nome del luogo (etichetta)")

    def test_una_sigla_dentro_un_pos(self):
        self.assertEqual(O.nome_leggibile("PosSuperficieCS", "x"),
                         "Superficie (copertura del suolo) (etichetta)")

    def test_le_sigle_dei_punti_fissi_restano_sigle(self):
        """PFP1/2/3 e PFA1/2 NON stanno nella tabella dei nomi, apposta: i
        nomi ufficiali sono le sigle stesse. Prima uscivano parafrasati in
        "Punto fisso di poligonazione (cat. 1)", che l'utente non voleva."""
        for sigla in ("PFP1", "PFP2", "PFP3", "PFA1", "PFA2"):
            with self.subTest(sigla=sigla):
                self.assertEqual(O.nome_leggibile(sigla, "x"), sigla)

    def test_pos_ma_non_un_prefisso(self):
        """"Posizione" comincia per "Pos" ma la quarta lettera e' minuscola:
        non e' una tabella di etichette, e non va decapitata in "izione"."""
        self.assertEqual(O.nome_leggibile("Posizione", "x"), "Posizione")

    def test_senza_classe_ili_si_ripulisce_la_tabella(self):
        """Raro, ma il nome grezzo non va lasciato com'e'."""
        self.assertEqual(O.nome_leggibile("", "beni_immobili_punto_di_confine"),
                         "Beni immobili punto di confine")

    def test_senza_classe_ili_e_senza_niente(self):
        self.assertEqual(O.nome_leggibile(None, "x_y"), "X y")


@unittest.skipUnless(C_E_QGIS, "QGIS non disponibile: %s" % PERCHE_NO)
class AlberoRaggruppato(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if QgsApplication.instance() is None:
            cls.app = QgsApplication([], False)
            cls.app.initQgis()

    def setUp(self):
        self.progetto = QgsProject.instance()

    def tearDown(self):
        self.progetto.removeAllMapLayers()
        radice = self.progetto.layerTreeRoot()
        for figlio in list(radice.children()):
            radice.removeChildNode(figlio)

    def _layer(self, nome, geometria="Point"):
        layer = QgsVectorLayer("%s?crs=EPSG:2056" % geometria, nome, "memory")
        self.assertTrue(layer.isValid())
        self.progetto.addMapLayer(layer)
        return layer

    def _gruppi(self):
        from qgis.core import QgsLayerTreeGroup
        return [n.name() for n in self.progetto.layerTreeRoot().children()
                if isinstance(n, QgsLayerTreeGroup)]

    def test_i_layer_finiscono_nei_gruppi_della_circolare(self):
        confine = self._layer("beni_immobili_punto_di_confine")
        titolo = O._rf_group_for_table("beni_immobili_punto_di_confine")

        spostati = O.raggruppa_albero([(confine, "beni_immobili_punto_di_confine")],
                                      [], self.progetto)

        self.assertEqual(spostati, 1)
        self.assertIn(titolo, self._gruppi())

    def test_le_tabelle_attributo_hanno_il_loro_gruppo(self):
        attributo = self._layer("simbolo", geometria="None")

        O.raggruppa_albero([], [attributo], self.progetto)

        self.assertIn("99 Tabelle attributo (join)", self._gruppi())

    def test_i_gruppi_vuoti_spariscono(self):
        """Dodici gruppi sempre presenti, quasi tutti vuoti, sarebbero un
        elenco da scorrere per niente: in un comune senza condotte quel
        gruppo non deve comparire."""
        confine = self._layer("beni_immobili_punto_di_confine")

        O.raggruppa_albero([(confine, "beni_immobili_punto_di_confine")],
                           [], self.progetto)

        self.assertEqual(len(self._gruppi()), 1, self._gruppi())

    def test_rilanciare_non_duplica_i_gruppi(self):
        """Ricaricare la legenda su un progetto gia' aperto: senza la
        pulizia iniziale i gruppi si accumulerebbero a ogni giro."""
        confine = self._layer("beni_immobili_punto_di_confine")
        coppie = [(confine, "beni_immobili_punto_di_confine")]

        O.raggruppa_albero(coppie, [], self.progetto)
        primo = self._gruppi()
        O.raggruppa_albero(coppie, [], self.progetto)

        self.assertEqual(self._gruppi(), primo)

    def test_rilanciare_non_perde_i_layer(self):
        """La pulizia stacca i nodi dai gruppi vecchi: se lo facesse male, il
        layer sparirebbe dal progetto insieme al gruppo."""
        confine = self._layer("beni_immobili_punto_di_confine")
        coppie = [(confine, "beni_immobili_punto_di_confine")]

        O.raggruppa_albero(coppie, [], self.progetto)
        O.raggruppa_albero(coppie, [], self.progetto)

        self.assertIn(confine.id(), self.progetto.mapLayers())
        self.assertIsNotNone(self.progetto.layerTreeRoot().findLayer(confine.id()))

    def test_un_layer_fuori_dall_albero_non_ferma_gli_altri(self):
        dentro = self._layer("beni_immobili_punto_di_confine")
        fuori = QgsVectorLayer("Point?crs=EPSG:2056", "orfano", "memory")

        spostati = O.raggruppa_albero(
            [(fuori, "boh"), (dentro, "beni_immobili_punto_di_confine")],
            [], self.progetto)

        self.assertEqual(spostati, 1)

    def test_il_conto_finisce_nel_registro(self):
        confine = self._layer("beni_immobili_punto_di_confine")
        righe = []

        O.raggruppa_albero([(confine, "beni_immobili_punto_di_confine")], [],
                           self.progetto, righe.append)

        self.assertTrue(any("Albero raggruppato: 1 layer" in r for r in righe), righe)


if __name__ == "__main__":
    if QGIS_ATTESO and not C_E_QGIS:
        sys.stderr.write("QGIS era atteso ma non si importa: %s\n" % PERCHE_NO)
        raise SystemExit(1)
    sys.stderr.write("gruppo QGIS: %s\n" % ("eseguito" if C_E_QGIS else "SALTATO"))
    unittest.main(verbosity=2)
