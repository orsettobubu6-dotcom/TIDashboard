# Test dell'inventario rapido dell'ITF. Eseguire con l'interprete di QGIS:
#   & "C:\Program Files\QGIS 4.2.0\bin\python-qgis.bat" test_inventario.py
#
# Serve GDAL con il driver "Interlis 1", che QGIS ha compilato dentro. I test
# che leggono un ITF vero si saltano da soli se il file di prova non c'e':
# stanno qui perche' su un formato che non controlliamo noi un caso sintetico
# proverebbe solo che il nostro parser legge il nostro parser.
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tidashboard import inventario as I

ITF_VERO = r"C:\Users\gabri\Downloads\5254010100\5254010100.itf"


class TestRiassunto(unittest.TestCase):
    def test_file_senza_oggetti(self):
        self.assertEqual(I.riassunto([], 0), "il file non contiene oggetti")

    def test_conta_e_mette_in_testa_le_classi_piu_grosse(self):
        classi = [("Copertura_del_suolo__SuperficieCS_Geometria", 181493),
                  ("Beni_immobili__Bene_immobile_Geometria", 87571),
                  ("Beni_immobili__Punto_di_confine", 75298)]
        testo = I.riassunto(classi, 344362)
        self.assertIn("344'362 oggetti in 3 classi", testo)
        # il nome del topic non serve nella riga breve, la classe si'
        self.assertIn("SuperficieCS_Geometria", testo)
        self.assertNotIn("Copertura_del_suolo__", testo)

    def test_gli_apostrofi_sono_quelli_svizzeri(self):
        self.assertIn("1'000", I.riassunto([("X__Y", 1000)], 1000))


class TestClassiMancanti(unittest.TestCase):
    def test_consegna_completa_non_segnala_niente(self):
        classi = [(nome, 1) for nome, _d in I.CLASSI_ATTESE]
        self.assertEqual(I.mancanti(classi), [])

    def test_segnala_quelle_che_non_ci_sono(self):
        classi = [("Beni_immobili__Fondo", 10)]
        assenti = I.mancanti(classi)
        self.assertIn("punti di confine", assenti)
        self.assertNotIn("fondi", assenti)

    def test_una_classe_vuota_conta_come_mancante(self):
        # leggi_inventario scarta le classi a zero: se il topic c'e' ma non ha
        # oggetti, per chi importa e' come se non ci fosse.
        self.assertEqual(len(I.mancanti([])), len(I.CLASSI_ATTESE))


class TestLetturaFile(unittest.TestCase):
    def test_percorso_inesistente(self):
        with self.assertRaises(RuntimeError):
            I.leggi_inventario(os.path.join(tempfile.mkdtemp(), "non_c_e.itf"))

    def test_percorso_vuoto(self):
        with self.assertRaises(RuntimeError):
            I.leggi_inventario("")

    def test_file_che_non_e_un_itf(self):
        percorso = os.path.join(tempfile.mkdtemp(), "finto.itf")
        with open(percorso, "w") as f:
            f.write("questo non e' un file INTERLIS\n")
        with self.assertRaises(RuntimeError):
            I.leggi_inventario(percorso)

    @unittest.skipUnless(os.path.isfile(ITF_VERO), "ITF di prova non presente")
    def test_sul_file_vero(self):
        classi, totale = I.leggi_inventario(ITF_VERO)
        self.assertGreater(totale, 100000)
        self.assertGreater(len(classi), 50)
        # ordinato per numero decrescente
        self.assertEqual([q for _n, q in classi], sorted([q for _n, q in classi], reverse=True))
        # nessuna classe vuota nell'elenco
        self.assertTrue(all(q > 0 for _n, q in classi))
        nomi = dict(classi)
        self.assertIn("Beni_immobili__Punto_di_confine", nomi)
        # lo stesso numero che il DXF esporta come punti di confine
        self.assertGreater(nomi["Beni_immobili__Punto_di_confine"], 75000)
        self.assertEqual(I.mancanti(classi), [],
                         "la consegna di prova ha tutte le classi attese")


if __name__ == "__main__":
    risultato = unittest.main(exit=False, verbosity=2)
    sys.exit(0 if risultato.result.wasSuccessful() else 1)
