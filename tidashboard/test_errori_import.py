# Prove dell'analisi degli errori di importazione.
#
# Gli ITF di prova sono minuscoli ma VERI nella forma: TABL/OBJE/ETAB come li
# scrive l'esportatore, e le righe di log sono copiate da una consegna vera.
#
# Il grosso non ha bisogno di QGIS: riconoscere una riga, ritrovare il blocco
# nell'ITF, cavarne le coordinate e dire se e' un doppione o una collisione di
# numerazione e' tutto testo. La guardia sul gruppo QGIS e' rumorosa come in
# test_relazioni: se QGIS e' atteso e non si importa, la prova FALLISCE invece
# di saltare.
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tidashboard import errori_import as E

QGIS_ATTESO = bool(os.environ.get("TIDASHBOARD_QGIS_ATTESO"))
try:
    from qgis.core import QgsApplication, QgsProject
    C_E_QGIS = True
    PERCHE_NO = ""
except ImportError as errore:
    C_E_QGIS = False
    PERCHE_NO = str(errore)


# Riga vera, da una consegna vera.
RIGA_UNICITA = ("Error: line 1183131: MD01MUTI7MN95.Beni_immobili.Punto_di_confine: "
                "tid 46560: Unique constraint MD01MUTI7MN95.Beni_immobili."
                "Punto_di_confine.Constraint2 is violated! Values TI63201, 140602 "
                "already exist in Object: 40497")
RIGA_ARCO = "Warning: arc is straight at (2719339.225, 1081435.757, NaN)"


def _itf(cartella, blocchi, nome="prova.itf"):
    """Un ITF con dei blocchi TABL...ETAB. 'blocchi' e' una lista di
    (nome_classe, [(tid, est, nord), ...]).

    Restituisce (percorso, dove), dove 'dove' e' indicizzato per (classe, tid)
    e non per tid soltanto: lo stesso tid puo' comparire in blocchi diversi -
    ed e' proprio il caso che una di queste prove verifica - quindi una chiave
    sul solo tid direbbe silenziosamente l'ultima riga invece di quella
    chiesta.
    """
    righe = ["SCNT", "MODL MD01MUTI7MN95", "TOPI Beni_immobili"]
    dove = {}
    for classe, oggetti in blocchi:
        righe.append("TABL %s" % classe)
        for tid, est, nord in oggetti:
            dove[(classe, tid)] = len(righe) + 1
            righe.append("OBJE %s 1 %.3f %.3f" % (tid, est, nord))
        righe.append("ETAB")
    righe += ["ETOP", "ENDE"]
    percorso = os.path.join(cartella, nome)
    with open(percorso, "w", encoding="latin-1", newline="\r\n") as f:
        f.write("\n".join(righe) + "\n")
    return percorso, dove


class RigheDiLog(unittest.TestCase):

    def test_violazione_di_unicita(self):
        genere, violazione = E.leggi_riga(RIGA_UNICITA)

        self.assertEqual(genere, "unicita")
        self.assertEqual(violazione.riga, 1183131)
        self.assertEqual(violazione.tid, "46560")
        self.assertEqual(violazione.tid_esistente, "40497")
        self.assertEqual(violazione.valori, "TI63201, 140602")
        self.assertTrue(violazione.vincolo.endswith("Constraint2"))

    def test_messaggio_con_la_coordinata_dentro(self):
        genere, punto = E.leggi_riga(RIGA_ARCO)

        self.assertEqual(genere, "punto")
        self.assertEqual(punto["livello"], "avviso")
        self.assertAlmostEqual(punto["x"], 2719339.225)
        self.assertAlmostEqual(punto["y"], 1081435.757)
        self.assertIn("arc is straight", punto["messaggio"])

    def test_un_errore_diventa_livello_errore(self):
        _genere, punto = E.leggi_riga(
            "Error: overlap at (2719339.225, 1081435.757, NaN)")
        self.assertEqual(punto["livello"], "errore")

    def test_la_violazione_di_unicita_non_diventa_anche_un_punto(self):
        """La riga di unicita' porta dei numeri, ma le sue coordinate vere si
        vanno a cercare nell'ITF: contarla due volte metterebbe sulla mappa un
        punto preso da un identificativo qualsiasi della riga."""
        genere, _ = E.leggi_riga(RIGA_UNICITA)
        self.assertEqual(genere, "unicita")

    def test_le_righe_informative_non_contano(self):
        self.assertIsNone(E.leggi_riga("Info: compiling MD01MUTI7MN95.ili"))
        self.assertIsNone(E.leggi_riga("Info: 2719339.225 1081435.757 letta"))

    def test_un_avviso_senza_coordinate_non_e_un_punto(self):
        self.assertIsNone(E.leggi_riga("Warning: something happened"))


class Coordinate(unittest.TestCase):

    def test_coppia_nella_riga_obje(self):
        self.assertEqual(E.coordinate_lv95("OBJE 46560 1 2719339.225 1081435.757"),
                         (2719339.225, 1081435.757))

    def test_serve_l_adiacenza(self):
        """Il difetto della versione precedente: prendeva i primi due numeri
        plausibili dovunque nella riga. Qui una quota sta in mezzo, e la
        coppia vera viene dopo."""
        riga = "OBJE 1 1 2719339.225 999.500 1081435.757"
        self.assertIsNone(E.coordinate_lv95(riga))

    def test_fuori_dalla_svizzera_non_e_una_coordinata(self):
        self.assertIsNone(E.coordinate_lv95("OBJE 1 1 1234567.890 9876543.210"))

    def test_l_ordine_conta(self):
        """Nord prima di Est non e' una coordinata LV95: E e N hanno
        intervalli diversi e non sovrapposti."""
        self.assertIsNone(E.coordinate_lv95("OBJE 1 1 1081435.757 2719339.225"))

    def test_senza_decimali_non_si_riconosce(self):
        self.assertIsNone(E.coordinate_lv95("OBJE 1 1 2719339 1081435"))


class BlocchiNellItf(unittest.TestCase):

    def setUp(self):
        self.cartella = tempfile.mkdtemp()

    def test_trova_il_blocco_che_contiene_la_riga(self):
        percorso, dove = _itf(self.cartella, [
            ("Punto_di_confine", [("1", 2719000.0, 1081000.0)]),
            ("Edificio", [("2", 2719100.0, 1081100.0), ("3", 2719200.0, 1081200.0)]),
        ])

        inizio, nome, fine = E.blocco_tabella(percorso, dove[("Edificio", "3")])

        self.assertIn("Edificio", nome)
        self.assertLess(inizio, dove[("Edificio", "3")])
        self.assertGreater(fine, dove[("Edificio", "3")])
        # Non deve prendere il blocco precedente.
        self.assertGreater(inizio, dove[("Punto_di_confine", "1")])

    def test_il_troncamento_si_dice(self):
        """Un risultato mancante perche' la scansione si e' fermata NON vuol
        dire "blocco assente": senza la riga di registro sarebbero
        indistinguibili."""
        percorso, dove = _itf(self.cartella, [
            ("Punto_di_confine", [("1", 2719000.0, 1081000.0)])])

        righe = []
        _i, _n, fine = E.blocco_tabella(percorso, dove[("Punto_di_confine", "1")],
                                            righe_max=2,
                                            log=righe.append)

        self.assertIsNone(fine)
        self.assertTrue(any("troncata" in r for r in righe), righe)

    def test_oggetti_per_tid_resta_nel_blocco(self):
        """Lo stesso tid esiste in tutti e due i blocchi: deve tornare quello
        del blocco chiesto.

        Si chiedono TUTTI E DUE i blocchi, e il secondo e' quello che conta.
        Chiedendo solo il primo la prova passerebbe anche senza il limite
        inferiore dell'intervallo: la scansione parte dall'inizio del file e
        si ferma appena ha trovato quello che cerca, quindi troverebbe il
        primo per caso. Verificato: guastando quel limite, con la sola prova
        sul primo blocco, la suite restava verde.
        """
        percorso, dove = _itf(self.cartella, [
            ("Punto_di_confine", [("7", 2719000.0, 1081000.0)]),
            ("Edificio", [("7", 2730000.0, 1090000.0)]),
        ])

        for classe, atteso in (("Punto_di_confine", (2719000.0, 1081000.0)),
                               ("Edificio", (2730000.0, 1090000.0))):
            with self.subTest(classe=classe):
                inizio, nome, fine = E.blocco_tabella(percorso, dove[(classe, "7")])
                self.assertIn(classe, nome)

                trovati = E.oggetti_per_tid(percorso, inizio, fine, ["7"])

                self.assertEqual(len(trovati), 1)
                self.assertEqual(E.coordinate_lv95(trovati["7"]), atteso)


class Diagnosi(unittest.TestCase):
    """La cosa che vale: distinguere il doppione dalla collisione."""

    def setUp(self):
        self.cartella = tempfile.mkdtemp()

    def _violazione(self, riga, tid, tid_esistente):
        return E.Violazione(riga=riga, classe="MD01MUTI7MN95.Beni_immobili.Punto_di_confine",
                            tid=tid, vincolo="MD01MUTI7MN95.Beni_immobili."
                                             "Punto_di_confine.Constraint2",
                            valori="TI63201, 140602", tid_esistente=tid_esistente)

    def test_stesso_punto_e_un_doppione(self):
        percorso, dove = _itf(self.cartella, [
            ("Punto_di_confine", [("46560", 2719339.225, 1081435.757),
                                  ("40497", 2719339.445, 1081435.900)])])

        righe, punti = E.analizza([self._violazione(dove[("Punto_di_confine", "46560")],
                                             "46560", "40497")], percorso)

        self.assertEqual(len(righe), 1)
        self.assertIn("doppione", righe[0]["diagnosi"])
        self.assertEqual(len(punti), 2)

    def test_punti_lontani_sono_una_collisione_di_numerazione(self):
        percorso, dove = _itf(self.cartella, [
            ("Punto_di_confine", [("46560", 2719339.225, 1081435.757),
                                  ("40497", 2721339.225, 1083435.757)])])

        righe, _punti = E.analizza([self._violazione(dove[("Punto_di_confine", "46560")],
                                              "46560", "40497")], percorso)

        self.assertIn("collisione", righe[0]["diagnosi"])
        self.assertNotIn("doppione", righe[0]["diagnosi"])

    def test_il_confine_fra_le_due_diagnosi(self):
        """Un metro esatto e' gia' una collisione: il limite e' dichiarato e
        deve restare dove dice la costante, non spostarsi con un arrotondamento."""
        for distanza, atteso in ((0.5, "doppione"), (1.5, "collisione")):
            with self.subTest(distanza=distanza):
                percorso, dove = _itf(self.cartella, [
                    ("Punto_di_confine", [("1", 2719339.225, 1081435.757),
                                          ("2", 2719339.225 + distanza, 1081435.757)])],
                    nome="d%s.itf" % distanza)
                righe, _p = E.analizza(
                    [self._violazione(dove[("Punto_di_confine", "1")], "1", "2")],
                    percorso)
                self.assertIn(atteso, righe[0]["diagnosi"])

    def test_senza_violazioni_lo_dice_e_non_inventa_righe(self):
        registro = []
        righe, punti = E.analizza([], "inesistente.itf", registro.append)

        self.assertEqual((righe, punti), ([], []))
        self.assertTrue(any("Nessun errore di vincolo" in r for r in registro), registro)

    def test_itf_illeggibile_non_ferma_l_analisi(self):
        """La riga in tabella deve esserci lo stesso: senza, l'utente vedrebbe
        una scheda vuota e crederebbe che non ci siano errori."""
        righe, punti = E.analizza(
            [self._violazione(10, "1", "2")],
            os.path.join(self.cartella, "non_c_e.itf"))

        self.assertEqual(len(righe), 1)
        self.assertIn("lettura ITF fallita", righe[0]["diagnosi"])
        self.assertEqual(punti, [])

    def test_coordinate_non_estratte_lo_dice_in_tabella(self):
        percorso = os.path.join(self.cartella, "strano.itf")
        with open(percorso, "w", encoding="latin-1", newline="\r\n") as f:
            f.write("TABL Punto_di_confine\nOBJE 1 senza numeri\n"
                    "OBJE 2 senza numeri\nETAB\n")

        righe, punti = E.analizza([self._violazione(2, "1", "2")], percorso)

        self.assertIn("coordinate non estratte", righe[0]["diagnosi"])
        self.assertEqual(punti, [])

    def test_piu_violazioni_nella_stessa_tabella(self):
        """Il caso comune di una consegna vera: venti conflitti tutti nella
        stessa tabella. Ognuno deve avere la sua riga e la sua diagnosi."""
        oggetti = []
        for i in range(6):
            oggetti.append((str(100 + i), 2719000.0 + i * 10, 1081000.0))
        percorso, dove = _itf(self.cartella, [("Punto_di_confine", oggetti)])

        chiave = lambda t: dove[("Punto_di_confine", t)]
        violazioni = [self._violazione(chiave("100"), "100", "101"),
                      self._violazione(chiave("102"), "102", "103"),
                      self._violazione(chiave("104"), "104", "105")]
        righe, punti = E.analizza(violazioni, percorso)

        self.assertEqual(len(righe), 3)
        self.assertTrue(all("collisione" in r["diagnosi"] for r in righe), righe)
        self.assertEqual(len(punti), 6)

    def test_l_itf_non_si_riscandisce_per_ogni_conflitto(self):
        """Tre conflitti nella STESSA tabella: il blocco si cerca una volta.

        Non e' un dettaglio: un ITF di consegna supera il milione di righe e
        ogni scansione costa secondi: con venti conflitti - il caso normale -
        erano venti letture del file per ritrovare sempre lo stesso blocco.
        La prova conta le chiamate, non i secondi: un tempo misurato qui
        direbbe piu' cose sulla macchina che sul codice.
        """
        oggetti = [(str(100 + i), 2719000.0 + i * 10, 1081000.0) for i in range(6)]
        percorso, dove = _itf(self.cartella, [("Punto_di_confine", oggetti)])
        chiave = lambda t: dove[("Punto_di_confine", t)]
        violazioni = [self._violazione(chiave("100"), "100", "101"),
                      self._violazione(chiave("102"), "102", "103"),
                      self._violazione(chiave("104"), "104", "105")]

        vera = E.blocco_tabella
        chiamate = []

        def contata(*argomenti, **chiavi):
            chiamate.append(argomenti[1])
            return vera(*argomenti, **chiavi)

        E.blocco_tabella = contata
        try:
            righe, _punti = E.analizza(violazioni, percorso)
        finally:
            E.blocco_tabella = vera

        self.assertEqual(len(righe), 3)
        self.assertEqual(len(chiamate), 1,
                         "l'ITF e' stato riscandito %d volte" % len(chiamate))


class PuntiRipetuti(unittest.TestCase):

    def _punto(self, x=2719339.225, y=1081435.757, messaggio="arc is straight"):
        return {"livello": "avviso", "tipo": "validazione", "messaggio": messaggio,
                "x": x, "y": y, "tid": "", "riga": 0}

    def test_lo_stesso_difetto_nella_stessa_posizione_conta_una_volta(self):
        registro = []
        distinti = E.punti_distinti([self._punto() for _ in range(4)], registro.append)

        self.assertEqual(len(distinti), 1)
        self.assertTrue(any("accorpate" in r for r in registro), registro)

    def test_posizioni_diverse_restano_diverse(self):
        punti = [self._punto(), self._punto(x=2719400.0)]
        self.assertEqual(len(E.punti_distinti(punti)), 2)

    def test_messaggi_diversi_nella_stessa_posizione_restano(self):
        """Due difetti diversi nello stesso punto sono due cose da sistemare."""
        punti = [self._punto(), self._punto(messaggio="overlap")]
        self.assertEqual(len(E.punti_distinti(punti)), 2)

    def test_senza_ripetizioni_non_dice_niente(self):
        registro = []
        E.punti_distinti([self._punto()], registro.append)
        self.assertEqual(registro, [])


@unittest.skipUnless(C_E_QGIS, "QGIS non disponibile: %s" % PERCHE_NO)
class LayerSullaMappa(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if QgsApplication.instance() is None:
            cls.app = QgsApplication([], False)
            cls.app.initQgis()

    def setUp(self):
        self.progetto = QgsProject.instance()

    def tearDown(self):
        self.progetto.removeAllMapLayers()

    def _punto(self, livello="errore", x=2719339.225, y=1081435.757):
        return {"livello": livello, "tipo": "validazione", "messaggio": "arc is straight",
                "x": x, "y": y, "tid": "7", "riga": 12}

    def test_senza_punti_niente_layer(self):
        self.assertIsNone(E.crea_layer([], self.progetto))
        self.assertEqual(len(self.progetto.mapLayers()), 0)

    def test_i_punti_arrivano_sulla_mappa_con_i_loro_valori(self):
        layer = E.crea_layer([self._punto()], self.progetto)

        self.assertIsNotNone(layer)
        self.assertEqual(layer.featureCount(), 1)
        elemento = next(layer.getFeatures())
        self.assertEqual(elemento["livello"], "errore")
        self.assertEqual(elemento["tid"], "7")
        self.assertEqual(elemento["riga"], 12)
        punto = elemento.geometry().asPoint()
        self.assertAlmostEqual(punto.x(), 2719339.225, places=3)
        self.assertEqual(layer.crs().authid(), "EPSG:2056")
        self.assertIn(layer.id(), self.progetto.mapLayers())

    def test_le_ripetizioni_non_si_impilano_sulla_mappa(self):
        layer = E.crea_layer([self._punto() for _ in range(4)], self.progetto)
        self.assertEqual(layer.featureCount(), 1)

    def test_errori_e_avvisi_hanno_regole_distinte(self):
        layer = E.crea_layer([self._punto(), self._punto(livello="avviso",
                                                         x=2719400.0)],
                             self.progetto)

        etichette = {r.label() for r in layer.renderer().rootRule().children()}
        self.assertEqual(etichette, {"errore", "avviso"})

    def test_il_conto_nel_registro_dice_errori_e_avvisi(self):
        registro = []
        E.crea_layer([self._punto(), self._punto(livello="avviso", x=2719400.0)],
                     self.progetto, registro.append)

        finale = [r for r in registro if "Errori di validazione" in r]
        self.assertEqual(len(finale), 1)
        self.assertIn("2 punti (1 errori, 1 avvisi)", finale[0])


if __name__ == "__main__":
    if QGIS_ATTESO and not C_E_QGIS:
        sys.stderr.write("QGIS era atteso ma non si importa: %s\n" % PERCHE_NO)
        raise SystemExit(1)
    sys.stderr.write("gruppo QGIS: %s\n" % ("eseguito" if C_E_QGIS else "SALTATO"))
    unittest.main(verbosity=2)
