# Test della lettura delle coordinate scritte a mano.
#
# Niente QGIS: la trasformazione WGS84 e' iniettata. Cosi' si prova la parte
# che puo' davvero sbagliare - il riconoscimento del sistema dall'ordine di
# grandezza - senza dipendere da una proiezione.
#
# Eseguire con un Python qualunque:  python test_coordinate.py
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tidashboard import coordinate as C

# Mendrisio, centro dei dati di prova.
EST, NORD = 2718000.0, 1082000.0


def _finta_proiezione(lon, lat):
    """Basta che sia riconoscibile: qui non si prova la proiezione di QGIS."""
    return (2600000.0 + (lon - 7.44) * 70000.0,
            1200000.0 + (lat - 46.95) * 111000.0)


class TestMN95(unittest.TestCase):
    def test_forma_normale(self):
        c = C.analizza("2718000 1082000")
        self.assertEqual(c.sistema, "MN95")
        self.assertAlmostEqual(c.est, EST)
        self.assertAlmostEqual(c.nord, NORD)
        self.assertFalse(c.approssimata)

    def test_separatori_ammessi(self):
        for testo in ("2718000,1082000", "2718000; 1082000", "2718000/1082000",
                      "2718000    1082000"):
            self.assertIsNotNone(C.analizza(testo), testo)

    def test_apostrofi_delle_migliaia(self):
        """In Svizzera i numeri si scrivono cosi': 2'718'000."""
        c = C.analizza("2'718'000 1'082'000")
        self.assertIsNotNone(c)
        self.assertAlmostEqual(c.est, EST)

    def test_lettere_degli_assi(self):
        for testo in ("E 2718000 N 1082000", "E2718000 N1082000",
                      "Y=2718000 X=1082000"):
            c = C.analizza(testo)
            self.assertIsNotNone(c, testo)
            self.assertAlmostEqual(c.est, EST, msg=testo)

    def test_invertite_si_raddrizzano(self):
        """Il tedesco scrive Nord/Est e l'italiano Est/Nord: in MN95 i due
        intervalli non si sovrappongono, quindi l'ordine si deduce."""
        c = C.analizza("1082000 2718000")
        self.assertAlmostEqual(c.est, EST)
        self.assertAlmostEqual(c.nord, NORD)

    def test_decimali(self):
        c = C.analizza("2718000.25 1082000.75")
        self.assertAlmostEqual(c.est, 2718000.25)
        self.assertAlmostEqual(c.nord, 1082000.75)


class TestMN03(unittest.TestCase):
    def test_le_vecchie_coordinate_si_riconoscono(self):
        """MN03 e' ancora in giro su piani e documenti piu' vecchi."""
        c = C.analizza("718000 82000")
        self.assertEqual(c.sistema, "MN03")
        self.assertAlmostEqual(c.est, EST)
        self.assertAlmostEqual(c.nord, NORD)

    def test_la_conversione_si_dichiara_approssimata(self):
        """Somma di due offset, non la griglia CHENyx06: fino a un metro di
        differenza. Tacerlo sarebbe far passare per esatta una stima."""
        c = C.analizza("718000 82000")
        self.assertTrue(c.approssimata)
        self.assertIn("un metro", C.spiega(c))

    def test_non_si_confonde_con_mn95(self):
        mn95 = C.analizza("2718000 1082000")
        mn03 = C.analizza("718000 82000")
        self.assertEqual(mn95.sistema, "MN95")
        self.assertEqual(mn03.sistema, "MN03")
        self.assertAlmostEqual(mn95.est, mn03.est)


class TestWGS84(unittest.TestCase):
    def test_gradi_decimali(self):
        c = C.analizza("45.87, 8.98", trasforma_wgs84=_finta_proiezione)
        self.assertIsNotNone(c)
        self.assertEqual(c.sistema, "WGS84")

    def test_ordine_lat_lon_o_lon_lat(self):
        """I telefoni danno "lat, lon"; le mappe a volte il contrario."""
        a = C.analizza("45.87 8.98", trasforma_wgs84=_finta_proiezione)
        b = C.analizza("8.98 45.87", trasforma_wgs84=_finta_proiezione)
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertAlmostEqual(a.est, b.est, places=6)

    def test_senza_proiezione_non_si_inventa_niente(self):
        """Fuori da QGIS non c'e' modo di proiettare: meglio None che due
        numeri inventati."""
        self.assertIsNone(C.analizza("45.87, 8.98"))


class TestRifiuti(unittest.TestCase):
    def test_fuori_dalla_svizzera(self):
        # ATTENZIONE alla scelta dei valori: "500000 200000" sembra fuori ma
        # letto come MN03 vale E 2500000 N 1200000, cioe' dalle parti di
        # Yverdon - dentro. Servono numeri che non cadano in Svizzera in
        # NESSUNA delle tre letture.
        self.assertIsNone(C.analizza("3000000 500000"))
        self.assertIsNone(C.analizza("0 0"))
        self.assertIsNone(C.analizza("-100 -200"))

    def test_un_numero_solo(self):
        self.assertIsNone(C.analizza("2718000"))

    def test_testo_vuoto(self):
        for t in ("", "   ", None):
            self.assertIsNone(C.analizza(t))

    def test_non_numeri(self):
        self.assertIsNone(C.analizza("Mendrisio, Arzo"))

    def test_i_gon_non_sono_coordinate(self):
        """E' la richiesta da cui e' nato il modulo, e la risposta e' no: il
        gon e' angolare, nel piano serve per la rotazione del foglio."""
        self.assertIsNone(C.analizza("137.5 gon"))
        motivo = C.motivo_del_rifiuto("137.5 gon")
        self.assertIn("angolare", motivo)
        self.assertIn("rotazione", motivo)

    def test_il_rifiuto_dice_cosa_sistemare(self):
        self.assertIn("due numeri", C.motivo_del_rifiuto("2718000"))
        self.assertIn("Fuori dalla Svizzera", C.motivo_del_rifiuto("0 0"))
        self.assertEqual(C.motivo_del_rifiuto(""), "")


class TestSpiega(unittest.TestCase):
    def test_dice_il_sistema_riconosciuto(self):
        self.assertIn("MN95", C.spiega(C.analizza("2718000 1082000")))
        self.assertIn("MN03", C.spiega(C.analizza("718000 82000")))
        self.assertIn("WGS84", C.spiega(
            C.analizza("45.87 8.98", trasforma_wgs84=_finta_proiezione)))

    def test_niente_da_dire_su_niente(self):
        self.assertEqual(C.spiega(None), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
