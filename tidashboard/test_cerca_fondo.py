# Test della ricerca di un fondo. Non serve QGIS: cerca_fondo.py legge il
# GeoPackage come file SQLite, quindi i dati di prova si costruiscono qui.
#   & "C:\Program Files\QGIS 4.2.0\bin\python-qgis.bat" test_cerca_fondo.py
#   (va anche con un Python qualunque)
import os
import sqlite3
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tidashboard import cerca_fondo as C


def _blob(xmin, ymin, xmax, ymax, con_envelope=True, punto=False):
    """Blob GeoPackage come quelli veri: intestazione "GP", versione 0, flag
    big endian, SRS 2056, poi l'envelope xy. Con con_envelope=False si
    ottiene il caso - ammesso dal formato - in cui l'envelope manca."""
    flag = 0x02 if con_envelope else 0x00
    testa = b"GP" + bytes([0, flag]) + struct.pack(">i", 2056)
    if con_envelope:
        testa += struct.pack(">4d", xmin, xmax, ymin, ymax)
    if punto:
        # WKB di un POINT big endian: serve a provare il ripiego quando
        # l'envelope non c'e'.
        return testa + b"\x00" + struct.pack(">I", 1) + struct.pack(">2d", xmin, ymin)
    return testa + b"\x00" + struct.pack(">I", 3)      # tipo POLYGON, tronco


def _gpkg(fondi, parti=(), posfondo=(), comuni=(("Mendrisio", 5254, 632),),
          con_prog=False):
    """GeoPackage minimo con le sole tabelle che servono alla ricerca.

    'fondi'    (T_Id, identan, numero, egrid, validita, genere)
    'parti'    (fondo_id, xmin, ymin, xmax, ymax)
    'posfondo' (fondo_id, x, y)
    """
    percorso = os.path.join(tempfile.mkdtemp(), "dati.gpkg")
    con = sqlite3.connect(percorso)
    con.execute("CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT)")
    con.execute("""CREATE TABLE beni_immobili_fondo (
        T_Id INTEGER, identan TEXT, numero TEXT, egris_egrid TEXT,
        validita TEXT, integralita TEXT, genere TEXT, superficie_totale INTEGER)""")
    for tid, identan, numero, egrid, validita, genere in fondi:
        con.execute("INSERT INTO beni_immobili_fondo VALUES (?,?,?,?,?,?,?,?)",
                    (tid, identan, numero, egrid, validita, "completo", genere, None))
    if con_prog:
        con.execute("""CREATE TABLE beni_immobili_fondoprog (
            T_Id INTEGER, identan TEXT, numero TEXT, egris_egrid TEXT,
            validita TEXT, integralita TEXT, genere TEXT, superficie_totale INTEGER)""")
        con.execute("INSERT INTO beni_immobili_fondoprog VALUES "
                    "(900,'TI63201','777',NULL,'in_vigore','completo','bene_immobile',NULL)")
    con.execute("""CREATE TABLE beni_immobili_bene_immobile (
        T_Id INTEGER, geometria BLOB, superficie INTEGER, bene_immobile_di INTEGER)""")
    for i, (fid, xmin, ymin, xmax, ymax) in enumerate(parti):
        con.execute("INSERT INTO beni_immobili_bene_immobile VALUES (?,?,?,?)",
                    (i + 1, _blob(xmin, ymin, xmax, ymax), 100, fid))
    con.execute("""CREATE TABLE beni_immobili_posfondo (
        T_Id INTEGER, pos BLOB, posfondo_di INTEGER)""")
    for i, (fid, x, y) in enumerate(posfondo):
        con.execute("INSERT INTO beni_immobili_posfondo VALUES (?,?,?)",
                    (i + 1, _blob(x, y, x, y, con_envelope=False, punto=True), fid))
    con.execute("CREATE TABLE confini_comunali_comune (T_Id INTEGER, nome TEXT, noufs INTEGER, nofisc INTEGER)")
    for i, (nome, noufs, nofisc) in enumerate(comuni):
        con.execute("INSERT INTO confini_comunali_comune VALUES (?,?,?,?)",
                    (i + 1, nome, noufs, nofisc))
    con.commit()
    con.close()
    return percorso


class TestScomposizioneIdentAN(unittest.TestCase):
    """IdentAN e' TICCCSS: le ultime due cifre sono la sezione, quelle in
    mezzo il comune."""

    def test_sezione_e_comune(self):
        self.assertEqual(C.sezione_di("TI63203"), "03")
        self.assertEqual(C.comune_di("TI63203"), "632")

    def test_forme_impreviste_non_inventano_nulla(self):
        for brutto in (None, "", "TI", "abc", "TI6320X"):
            self.assertIsNone(C.sezione_di(brutto), brutto)


class TestNormalizzazioneNumero(unittest.TestCase):
    def test_zeri_iniziali_solo_sui_numeri_puri(self):
        self.assertEqual(C.normalizza_numero("0452"), "452")
        self.assertEqual(C.normalizza_numero("452"), "452")

    def test_un_numero_con_lettere_resta_com_e(self):
        """'0A' e 'A' non sono lo stesso fondo: togliere gli zeri qui
        confonderebbe due chiavi diverse."""
        self.assertEqual(C.normalizza_numero("0A"), "0A")
        self.assertEqual(C.normalizza_numero("12b"), "12b")


class TestParserRicerca(unittest.TestCase):
    """Il modo naturale di scrivere un fondo con sezione e' in un campo
    solo."""

    def test_separatori_ammessi(self):
        for testo in ("452-01", "452 / 01", "452/01", "452.01", "452 01"):
            self.assertEqual(C.analizza_ricerca(testo), ("452", "01"), testo)

    def test_sezione_di_una_cifra_viene_completata(self):
        self.assertEqual(C.analizza_ricerca("452-1"), ("452", "01"))

    def test_senza_separatore_la_sezione_resta_ignota(self):
        self.assertEqual(C.analizza_ricerca("452"), ("452", None))

    def test_vuoto(self):
        self.assertEqual(C.analizza_ricerca("  "), (None, None))


class TestDisambiguazione(unittest.TestCase):
    """LA REGOLA CHE CONTA. Lo stesso numero esiste in ogni sezione: sui dati
    reali di Mendrisio il numero 99 sta in tutte e dieci. Cercare "99" non
    deve mai portare sul primo risultato."""

    def setUp(self):
        self.g = _gpkg(
            fondi=[(1, "TI63201", "99", None, "in_vigore", "bene_immobile"),
                   (2, "TI63202", "99", None, "in_vigore", "bene_immobile"),
                   (3, "TI63203", "99", None, "in_vigore", "bene_immobile"),
                   (4, "TI63201", "12", None, "in_vigore", "bene_immobile")],
            parti=[(1, 2716000, 1081000, 2716100, 1081100),
                   (2, 2717000, 1082000, 2717100, 1082100),
                   (3, 2718000, 1083000, 2718100, 1083100),
                   (4, 2719000, 1084000, 2719100, 1084100)])

    def test_numero_ripetuto_restituisce_tutte_le_sezioni(self):
        r = C.cerca(self.g, numero="99")
        self.assertEqual(len(r), 3)
        self.assertEqual(sorted(f.sezione for f in r), ["01", "02", "03"])

    def test_la_sezione_e_visibile_nell_etichetta(self):
        """Se la sezione non si legge, tre righe identiche non si scelgono."""
        for f in C.cerca(self.g, numero="99"):
            self.assertIn("sezione %s" % f.sezione, f.etichetta)

    def test_con_la_sezione_il_risultato_e_uno(self):
        r = C.cerca(self.g, numero="99", sezione="02")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].identan, "TI63202")

    def test_la_sezione_si_puo_scrivere_nel_numero(self):
        r = C.cerca(self.g, numero="99-02")
        self.assertEqual([f.identan for f in r], ["TI63202"])

    def test_la_sezione_esplicita_vince_su_quella_scritta_nel_numero(self):
        r = C.cerca(self.g, numero="99-02", sezione="03")
        self.assertEqual([f.identan for f in r], ["TI63203"])

    def test_ritorna_sempre_una_lista(self):
        self.assertIsInstance(C.cerca(self.g, numero="12"), list)


class TestGeometria(unittest.TestCase):
    def test_estensione_e_centro_dalle_parti(self):
        g = _gpkg(fondi=[(1, "TI63201", "5", None, "in_vigore", "bene_immobile")],
                  parti=[(1, 2716000, 1081000, 2716100, 1081200)])
        f = C.cerca(g, numero="5")[0]
        self.assertEqual(f.extent, (2716000, 1081000, 2716100, 1081200))
        self.assertEqual(f.centro, (2716050, 1081100))
        self.assertEqual(f.origine_geometria, "geometria")

    def test_piu_parti_si_uniscono(self):
        """Superficie_totale esiste nel modello proprio perche' un fondo puo'
        essere fatto di piu' parti: prendere solo la prima darebbe
        un'estensione che non contiene il resto."""
        g = _gpkg(fondi=[(1, "TI63201", "5", None, "in_vigore", "bene_immobile")],
                  parti=[(1, 2716000, 1081000, 2716100, 1081100),
                         (1, 2716500, 1081500, 2716600, 1081600)])
        f = C.cerca(g, numero="5")[0]
        self.assertEqual(f.extent, (2716000, 1081000, 2716600, 1081600))
        self.assertEqual(f.n_parti, 2)

    def test_ripiego_su_posfondo(self):
        """Senza parti si usa il punto di iscrizione del numero, e lo si
        dichiara: non e' la geometria del fondo."""
        g = _gpkg(fondi=[(1, "TI63201", "7", None, "in_vigore", "bene_immobile")],
                  parti=[], posfondo=[(1, 2716333.5, 1081444.5)])
        f = C.cerca(g, numero="7")[0]
        self.assertEqual(f.centro, (2716333.5, 1081444.5))
        self.assertEqual(f.origine_geometria, "posizione del numero")

    def test_senza_geometria_non_si_inventa_un_centro(self):
        g = _gpkg(fondi=[(1, "TI63201", "8", None, "in_vigore", "bene_immobile")])
        f = C.cerca(g, numero="8")[0]
        self.assertIsNone(f.extent)
        self.assertIsNone(f.centro)
        self.assertIn("senza geometria", f.etichetta)


class TestFiltri(unittest.TestCase):
    def setUp(self):
        self.g = _gpkg(
            fondi=[(1, "TI63201", "10", "CH1234567890", "in_vigore", "bene_immobile"),
                   (2, "TI63201", "11", None, "contestato", "bene_immobile"),
                   (3, "TI70001", "10", None, "in_vigore", "bene_immobile")],
            comuni=(("Mendrisio", 5254, 632), ("Chiasso", 5250, 700)),
            con_prog=True)

    def test_fondoprog_escluso_per_difetto(self):
        self.assertEqual(C.cerca(self.g, numero="777"), [])

    def test_contestato_escluso_per_difetto(self):
        self.assertEqual(C.cerca(self.g, numero="11"), [])
        self.assertEqual(len(C.cerca(self.g, numero="11", solo_in_vigore=False)), 1)

    def test_filtro_per_nome_di_comune(self):
        r = C.cerca(self.g, numero="10", comune="Mendrisio")
        self.assertEqual([f.identan for f in r], ["TI63201"])

    def test_filtro_per_numero_di_comune(self):
        r = C.cerca(self.g, numero="10", comune="700")
        self.assertEqual([f.identan for f in r], ["TI70001"])

    def test_il_nome_del_comune_arriva_nel_risultato(self):
        self.assertEqual(C.cerca(self.g, numero="10", comune="Mendrisio")[0].comune,
                         "Mendrisio")

    def test_ricerca_per_egrid(self):
        r = C.cerca(self.g, egrid="ch1234567890")
        self.assertEqual([f.numero for f in r], ["10"])

    def test_zeri_iniziali(self):
        self.assertEqual(len(C.cerca(self.g, numero="0010")), 2)

    def test_senza_criteri_non_si_scarica_tutto(self):
        """Numero ed EGRID sono i criteri di RICERCA; sezione, comune e
        validita' sono filtri, cioe' restringono un risultato e non lo
        cercano. A campi vuoti la ricerca restituiva i primi 50 fondi del
        comune come se li avesse trovati."""
        self.assertEqual(C.cerca(self.g), [])
        self.assertEqual(C.cerca(self.g, sezione="01"), [])
        self.assertEqual(C.cerca(self.g, comune="Mendrisio"), [])
        self.assertEqual(C.cerca(self.g, numero="   "), [])

    def test_limite(self):
        molti = [(i, "TI632%02d" % (i % 90 + 1), "5", None, "in_vigore", "bene_immobile")
                 for i in range(1, 120)]
        g = _gpkg(fondi=molti)
        self.assertEqual(len(C.cerca(g, numero="5")), C.LIMITE_RISULTATI)
        self.assertEqual(len(C.cerca(g, numero="5", limite=7)), 7)


class TestSezioniDisponibili(unittest.TestCase):
    def test_elenco_ordinato_e_senza_ripetizioni(self):
        g = _gpkg(fondi=[(1, "TI63203", "1", None, "in_vigore", "bene_immobile"),
                         (2, "TI63201", "2", None, "in_vigore", "bene_immobile"),
                         (3, "TI63203", "3", None, "in_vigore", "bene_immobile")])
        self.assertEqual(C.sezioni_disponibili(g), ["01", "03"])


class TestFileAssenteOMalformato(unittest.TestCase):
    """La ricerca non deve mai sollevare: e' collegata a un campo di testo."""

    def test_file_inesistente(self):
        self.assertEqual(C.cerca("/percorso/che/non/esiste.gpkg", numero="1"), [])
        self.assertEqual(C.sezioni_disponibili(None), [])

    def test_file_che_non_e_un_gpkg(self):
        p = os.path.join(tempfile.mkdtemp(), "finto.gpkg")
        with open(p, "w") as f:
            f.write("non sono un database")
        self.assertEqual(C.cerca(p, numero="1"), [])

    def test_gpkg_senza_la_tabella_dei_fondi(self):
        p = os.path.join(tempfile.mkdtemp(), "vuoto.gpkg")
        con = sqlite3.connect(p)
        con.execute("CREATE TABLE altro (x INTEGER)")
        con.commit(); con.close()
        self.assertEqual(C.cerca(p, numero="1"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
