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


def _blob(xmin, ymin, xmax, ymax, con_envelope=True, punto=False, anello=None):
    """Blob GeoPackage come quelli veri: intestazione "GP", versione 0, flag
    big endian, SRS 2056, poi l'envelope xy. Con con_envelope=False si
    ottiene il caso - ammesso dal formato - in cui l'envelope manca.

    'anello' scrive un POLYGON COMPLETO con quei vertici, per provare la
    lettura del contorno; senza, il WKB resta troncato al tipo, che e' il caso
    in cui si ha il solo envelope."""
    flag = 0x02 if con_envelope else 0x00
    testa = b"GP" + bytes([0, flag]) + struct.pack(">i", 2056)
    if con_envelope:
        testa += struct.pack(">4d", xmin, xmax, ymin, ymax)
    if punto:
        # WKB di un POINT big endian: serve a provare il ripiego quando
        # l'envelope non c'e'.
        return testa + b"\x00" + struct.pack(">I", 1) + struct.pack(">2d", xmin, ymin)
    if anello:
        corpo = b"\x00" + struct.pack(">I", 3) + struct.pack(">I", 1)
        corpo += struct.pack(">I", len(anello))
        for x, y in anello:
            corpo += struct.pack(">2d", x, y)
        return testa + corpo
    return testa + b"\x00" + struct.pack(">I", 3)      # tipo POLYGON, tronco


def _gpkg(fondi, parti=(), posfondo=(), comuni=(("Mendrisio", 5254, 632),),
          con_prog=False, localita=()):
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
    # Nome_di_localita: da qui viene il NOME della sezione. La chiave del
    # modello e' (IdentAN, Numero), quindi piu' localita' per area sono
    # ammesse.
    con.execute("CREATE TABLE nomenclatura_nome_di_localita "
                "(T_Id INTEGER, nome TEXT, tipo TEXT, identan TEXT, numero TEXT)")
    for i, (identan, numero, nome) in enumerate(localita):
        con.execute("INSERT INTO nomenclatura_nome_di_localita VALUES (?,?,?,?,?)",
                    (i + 1, nome, None, identan, numero))
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


class TestNomeDellaSezione(unittest.TestCase):
    """Le sezioni hanno un NOME: in Ticino sono gli ex comuni aggregati.
    Area_di_numerazione non lo porta - ha solo Ct, NumeroAN e IncartoTecnico
    - ma Nome_di_localita si', legato dallo stesso IdentAN. Su Mendrisio:
    TI63203 -> Arzo, TI63209 -> Ligornetto."""

    def _dati(self, localita):
        return _gpkg(
            fondi=[(1, "TI63203", "99", None, "in_vigore", "bene_immobile"),
                   (2, "TI63209", "99", None, "in_vigore", "bene_immobile")],
            localita=localita)

    def test_il_nome_arriva_nel_risultato_e_nell_etichetta(self):
        g = self._dati([("TI63203", "201", "Arzo"), ("TI63209", "1", "Ligornetto")])
        r = {f.sezione: f for f in C.cerca(g, numero="99")}
        self.assertEqual(r["03"].sezione_nome, "Arzo")
        self.assertEqual(r["09"].sezione_nome, "Ligornetto")
        self.assertIn("sezione 03 Arzo", r["03"].etichetta)

    def test_il_comune_non_si_ripete_se_e_gia_il_nome_della_sezione(self):
        """La sezione principale di un comune aggregato porta il nome del
        comune: "sezione 01 Mendrisio · Mendrisio" e' solo rumore."""
        g = _gpkg(fondi=[(1, "TI63201", "9", None, "in_vigore", "bene_immobile"),
                         (2, "TI63203", "9", None, "in_vigore", "bene_immobile")],
                  localita=[("TI63201", "101", "Mendrisio"),
                            ("TI63203", "201", "Arzo")])
        e = {f.sezione: f.etichetta for f in C.cerca(g, numero="9")}
        self.assertEqual(e["01"].count("Mendrisio"), 1)
        self.assertIn("Arzo · Mendrisio", e["03"])

    def test_il_nome_compare_nell_elenco_delle_sezioni(self):
        g = self._dati([("TI63203", "201", "Arzo"), ("TI63209", "1", "Ligornetto")])
        self.assertEqual(C.sezioni_disponibili(g),
                         [("03", "Arzo"), ("09", "Ligornetto")])

    def test_senza_localita_resta_il_solo_codice(self):
        g = self._dati([])
        self.assertEqual(C.sezioni_disponibili(g), [("03", None), ("09", None)])
        self.assertIsNone(C.cerca(g, numero="99")[0].sezione_nome)

    def test_piu_nomi_per_la_stessa_area_non_ne_scelgono_uno(self):
        """Il modello ammette piu' localita' per area (IDENT IdentAN, Numero):
        mostrarne una a caso attribuirebbe alla sezione un nome non suo."""
        g = self._dati([("TI63203", "201", "Arzo"), ("TI63203", "202", "Meride"),
                        ("TI63209", "1", "Ligornetto")])
        sezioni = dict(C.sezioni_disponibili(g))
        self.assertIsNone(sezioni["03"])
        self.assertEqual(sezioni["09"], "Ligornetto")

    def test_il_nome_e_chiavato_sull_identan_intero(self):
        """Non su due cifre ritagliate: IdentAN e' Ct + NumeroAN con NumeroAN
        TEXT*10, e nei dati reali esistono anche "CH0100000001"."""
        g = _gpkg(fondi=[(1, "TI63203", "5", None, "in_vigore", "bene_immobile")],
                  localita=[("TI63203", "201", "Arzo"),
                            ("CH0100000003", "1", "Svizzera")])
        f = C.cerca(g, numero="5")[0]
        self.assertEqual(f.sezione_nome, "Arzo")


class TestPiuDiDieciSezioni(unittest.TestCase):
    """Le sezioni non sono al massimo dieci: SS ha due cifre, quindi fino a
    99, e il codice non deve avere alcun limite cablato."""

    def test_venti_sezioni(self):
        fondi = [(i, "TI632%02d" % i, "7", None, "in_vigore", "bene_immobile")
                 for i in range(1, 21)]
        g = _gpkg(fondi=fondi)
        self.assertEqual(len(C.sezioni_disponibili(g)), 20)
        self.assertEqual(len(C.cerca(g, numero="7")), 20)

    def test_sezione_oltre_la_decima_si_cerca(self):
        fondi = [(i, "TI632%02d" % i, "7", None, "in_vigore", "bene_immobile")
                 for i in range(1, 21)]
        g = _gpkg(fondi=fondi)
        self.assertEqual([f.identan for f in C.cerca(g, numero="7", sezione="17")],
                         ["TI63217"])
        self.assertEqual([f.identan for f in C.cerca(g, numero="7-17")],
                         ["TI63217"])


class TestSezioniDisponibili(unittest.TestCase):
    def test_elenco_ordinato_e_senza_ripetizioni(self):
        g = _gpkg(fondi=[(1, "TI63203", "1", None, "in_vigore", "bene_immobile"),
                         (2, "TI63201", "2", None, "in_vigore", "bene_immobile"),
                         (3, "TI63203", "3", None, "in_vigore", "bene_immobile")])
        self.assertEqual(C.sezioni_disponibili(g), [("01", None), ("03", None)])


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


class TestContorno(unittest.TestCase):
    """L'envelope basta per sapere se un fondo ci sta nel foglio, non per
    sapere se ci starebbe girandolo: per quello servono i vertici veri."""

    ANELLO = [(2717000.0, 1082000.0), (2717100.0, 1082000.0),
              (2717100.0, 1082050.0), (2717000.0, 1082050.0),
              (2717000.0, 1082000.0)]

    def test_legge_l_anello_esterno(self):
        blob = _blob(2717000.0, 1082000.0, 2717100.0, 1082050.0, anello=self.ANELLO)
        self.assertEqual(C._contorno(blob), [(x, y) for x, y in self.ANELLO])

    def test_wkb_troncato_non_esplode(self):
        # Caso reale: l'envelope c'e', la geometria no. Si deve restare senza
        # contorno, non sollevare.
        self.assertEqual(C._contorno(_blob(0, 0, 10, 10)), [])

    def test_un_punto_non_e_un_contorno(self):
        self.assertEqual(C._contorno(_blob(5, 5, 5, 5, punto=True)), [])

    def test_blob_vuoto_o_non_gpkg(self):
        self.assertEqual(C._contorno(None), [])
        self.assertEqual(C._contorno(b"XX"), [])

    def test_arriva_fino_al_risultato_della_ricerca(self):
        p = _gpkg(fondi=[(1, "TI63201", "452", None, "in_vigore", "bene_immobile")],
                  parti=[(1, 2717000.0, 1082000.0, 2717100.0, 1082050.0)])
        # riscrivo la geometria della parte con un poligono completo
        con = sqlite3.connect(p)
        con.execute("UPDATE beni_immobili_bene_immobile SET geometria = ?",
                    (_blob(2717000.0, 1082000.0, 2717100.0, 1082050.0,
                           anello=self.ANELLO),))
        con.commit(); con.close()
        trovati = C.cerca(p, numero="452")
        self.assertEqual(len(trovati), 1)
        self.assertEqual(len(trovati[0].contorno), 5)
        self.assertIn((2717100.0, 1082050.0), trovati[0].contorno)

    def test_senza_geometria_il_contorno_resta_vuoto(self):
        # Ripiego su PosFondo: c'e' il centro, non c'e' il perimetro.
        p = _gpkg(fondi=[(1, "TI63201", "452", None, "in_vigore", "bene_immobile")],
                  posfondo=[(1, 2717050.0, 1082025.0)])
        trovati = C.cerca(p, numero="452")
        self.assertEqual(trovati[0].contorno, [])


class TestBlobCorrotto(unittest.TestCase):
    """Un blob WKB rotto non deve far cadere il programma.

    n_anelli e n_punti sono numeri LETTI DAL FILE: in un blob corrotto o
    troncato valgono qualunque cosa fino a 4 miliardi. La stringa di formato
    veniva composta prima di guardare quanti byte restassero, quindi struct
    provava ad allocare per quel numero di punti - e il risultato non era un
    errore di lettura ma un MemoryError, cioe' un guasto che sembra del
    programma invece che del dato."""

    def _poligono_che_promette_troppo(self, punti_dichiarati):
        import struct
        # WKB little-endian: tipo 3 (Polygon), 1 anello, N punti dichiarati,
        # e poi NIENTE.
        return (struct.pack("<BI", 1, 3) + struct.pack("<I", 1)
                + struct.pack("<I", punti_dichiarati))

    def test_un_conteggio_assurdo_non_alza_memoryerror(self):
        b = self._poligono_che_promette_troppo(4000000000)
        fuori = []
        C._leggi_anelli(b, 5, "<", fuori)
        self.assertEqual(fuori, [], "non c'era nessun punto da leggere")

    def test_un_blob_troncato_a_meta(self):
        b = self._poligono_che_promette_troppo(3)[:-2]
        fuori = []
        C._leggi_anelli(b, 5, "<", fuori)
        self.assertEqual(fuori, [])

    def test_un_poligono_sano_si_legge_ancora(self):
        """L'altra meta': un controllo troppo stretto scarterebbe le
        geometrie buone, e la ricerca non troverebbe piu' niente."""
        import struct
        b = (struct.pack("<BI", 1, 3) + struct.pack("<I", 1)
             + struct.pack("<I", 2)
             + struct.pack("<dddd", 2718000.0, 1082000.0, 2718100.0, 1082100.0))
        fuori = []
        C._leggi_anelli(b, 5, "<", fuori)
        self.assertEqual(fuori, [(2718000.0, 1082000.0),
                                 (2718100.0, 1082100.0)])



if __name__ == "__main__":
    unittest.main(verbosity=2)
