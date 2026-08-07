# Test della lettura del comune dai dati INTERLIS. Non serve QGIS:
#   python test_dati_comune.py
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dati_comune as D


def _gpkg(tabelle):
    """Crea un file sqlite temporaneo con le tabelle indicate.
    'tabelle' = {nome: (colonne, righe)}."""
    percorso = os.path.join(tempfile.mkdtemp(), "prova.gpkg")
    con = sqlite3.connect(percorso)
    for nome, (colonne, righe) in tabelle.items():
        con.execute("CREATE TABLE %s (%s)" % (nome, ", ".join("%s TEXT" % c for c in colonne)))
        con.executemany("INSERT INTO %s VALUES (%s)"
                        % (nome, ", ".join("?" * len(colonne))), righe)
    con.commit()
    con.close()
    return percorso


class TestLetturaComune(unittest.TestCase):
    def test_elenco_comuni_del_perimetro(self):
        p = _gpkg({"confini_comunali_comune": (["nome"], [("Giubiasco",), ("Camorino",)])})
        self.assertEqual(D.leggi_comuni(p), ["Giubiasco", "Camorino"])

    def test_il_nome_per_il_piano_ha_la_precedenza(self):
        """Layout_del_piano.Nome_comune e' il nome pensato per l'intestazione
        del piano: deve arrivare prima dell'elenco dei comuni."""
        p = _gpkg({
            "confini_comunali_comune": (["nome"], [("Camorino",)]),
            "margine_del_piano_layout_del_piano":
                (["nome_comune", "numero_del_piano"], [("Bellinzona-Giubiasco", "12")]),
        })
        self.assertEqual(D.leggi_comuni(p), ["Bellinzona-Giubiasco", "Camorino"])

    def test_nomi_ripetuti_e_vuoti_scartati(self):
        p = _gpkg({"confini_comunali_comune":
                   (["nome"], [("Giubiasco",), ("Giubiasco",), ("",), ("  ",)])})
        self.assertEqual(D.leggi_comuni(p), ["Giubiasco"])

    def test_tabelle_di_servizio_ignorate(self):
        """Le tabelle interne del GeoPackage non vanno lette: gpkg_contents ha
        una colonna 'table_name', non un comune."""
        p = _gpkg({"gpkg_contents": (["nome_comune"], [("non_leggere",)]),
                   "confini_comunali_comune": (["nome"], [("Giubiasco",)])})
        self.assertEqual(D.leggi_comuni(p), ["Giubiasco"])

    def test_nessuna_fonte_non_e_un_errore(self):
        p = _gpkg({"beni_immobili_bene_immobile": (["numero"], [("4471",)])})
        self.assertEqual(D.leggi_comuni(p), [])

    def test_file_assente_o_illeggibile(self):
        self.assertEqual(D.leggi_comuni("C:/non/esiste.gpkg"), [])
        self.assertEqual(D.leggi_comuni(""), [])
        self.assertEqual(D.leggi_comuni(None), [])

    def test_file_non_sqlite(self):
        percorso = os.path.join(tempfile.mkdtemp(), "finto.gpkg")
        with open(percorso, "w") as f:
            f.write("questo non e' un database")
        self.assertEqual(D.leggi_comuni(percorso), [])


class TestDataValidita(unittest.TestCase):
    """"Stato al" e' la data dei DATI, non della stampa: sta nelle tabelle
    Tenuta_a_giorno_* dell'ITF."""

    def test_prende_la_piu_recente_fra_i_temi(self):
        p = _gpkg({
            "confini_comunali_tenuta_a_giorno_comune":
                (["in_vigore"], [("2004-09-07",)]),
            "beni_immobili_tenuta_a_giornobi":
                (["in_vigore"], [("2024-07-31",), ("2019-03-02",)]),
        })
        self.assertEqual(D.leggi_data_validita(p), "31.07.2024")

    def test_in_vigore_ha_la_precedenza_su_data1(self):
        """Il modello dice: "Per gli aggiornamenti futuri, la data da inserire
        e' In_vigore. Data1 ... non viene piu' usato"."""
        p = _gpkg({"x_tenuta_a_giornopfp1":
                   (["in_vigore", "data1"], [("2024-01-15", "1998-01-01")])})
        self.assertEqual(D.leggi_data_validita(p), "15.01.2024")

    def test_senza_tabelle_di_attualizzazione(self):
        p = _gpkg({"beni_immobili_bene_immobile": (["numero"], [("4471",)])})
        self.assertEqual(D.leggi_data_validita(p), "")

    def test_file_assente(self):
        self.assertEqual(D.leggi_data_validita("C:/non/esiste.gpkg"), "")


class TestDataEstrazioneItf(unittest.TestCase):
    """"Stato al" e' la data di estrazione dell'ITF. Il file non la contiene al
    suo interno - l'intestazione porta solo MTID, MODL e il filtro di
    esportazione - quindi si legge dal timestamp."""

    def test_legge_la_data_di_modifica(self):
        import datetime
        percorso = os.path.join(tempfile.mkdtemp(), "consegna.itf")
        with open(percorso, "w") as f:
            f.write("SCNT\nMTID INTERLIS1\n")
        quando = datetime.datetime(2024, 9, 2, 18, 34).timestamp()
        os.utime(percorso, (quando, quando))
        self.assertEqual(D.data_estrazione_itf(percorso), "02.09.2024")

    def test_file_assente_o_vuoto(self):
        self.assertEqual(D.data_estrazione_itf("C:/non/esiste.itf"), "")
        self.assertEqual(D.data_estrazione_itf(""), "")
        self.assertEqual(D.data_estrazione_itf(None), "")


class TestGpkgDeiLayer(unittest.TestCase):
    class _Finto:
        def __init__(self, sorgente):
            self._s = sorgente

        def source(self):
            return self._s

    def test_percorso_estratto_dalla_source(self):
        p = _gpkg({"x": (["a"], [("1",)])})
        layers = [self._Finto("%s|layername=beni_immobili_bene_immobile" % p)]
        self.assertEqual(D.gpkg_dei_layer(layers), p)

    def test_layer_senza_gpkg_o_lista_vuota(self):
        self.assertEqual(D.gpkg_dei_layer([]), "")
        self.assertEqual(D.gpkg_dei_layer(None), "")
        self.assertEqual(D.gpkg_dei_layer([self._Finto("memory?geometry=Point")]), "")


if __name__ == "__main__":
    risultato = unittest.main(exit=False, verbosity=2)
    sys.exit(0 if risultato.result.wasSuccessful() else 1)
