# Test della rilettura del DXF con GDAL.
#
# I DXF di prova sono minuscoli ma VERI: hanno la tabella LAYER, la sezione
# ENTITIES e l'EOF, e GDAL li apre davvero. Non ci sono finzioni al posto del
# lettore - sarebbe come provare un secondo parere chiedendolo a se stessi.
#
# Eseguire con l'interprete di QGIS (serve osgeo):
#   & "C:\Program Files\QGIS 4.2.0\bin\python-qgis.bat" test_verifica_dxf.py
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tidashboard import verifica_dxf as V

CX, CY = 2718000.0, 1082000.0


def _coppie(*valori):
    return "".join("%s\n%s\n" % (c, v) for c, v in zip(valori[::2], valori[1::2]))


def _tabella_layer(nomi):
    testo = _coppie("0", "SECTION", "2", "TABLES",
                    "0", "TABLE", "2", "LAYER", "70", str(len(nomi)))
    for n in nomi:
        testo += _coppie("0", "LAYER", "2", n, "70", "0", "62", "7",
                         "6", "CONTINUOUS")
    testo += _coppie("0", "ENDTAB", "0", "ENDSEC")
    return testo


def _punto(layer, x=CX, y=CY):
    return _coppie("0", "POINT", "8", layer, "10", "%.3f" % x,
                   "20", "%.3f" % y, "30", "0.0")


def _testo(layer, contenuto="X"):
    return _coppie("0", "TEXT", "8", layer, "10", "%.3f" % CX,
                   "20", "%.3f" % CY, "30", "0.0", "40", "1.0", "1", contenuto)


def _polilinea(layer, punti, flag_vertice="0"):
    testo = _coppie("0", "POLYLINE", "8", layer, "66", "1", "70", "0")
    for x, y in punti:
        testo += _coppie("0", "VERTEX", "8", layer, "10", "%.3f" % x,
                         "20", "%.3f" % y, "30", "0.0", "70", flag_vertice)
    testo += _coppie("0", "SEQEND", "8", layer)
    return testo


def _dxf(cartella, corpo, layer=("01651",), nome="prova.dxf"):
    percorso = os.path.join(cartella, nome)
    testo = _coppie("0", "SECTION", "2", "HEADER",
                    "9", "$ACADVER", "1", "AC1015", "0", "ENDSEC")
    testo += _tabella_layer(layer)
    testo += _coppie("0", "SECTION", "2", "ENTITIES") + corpo
    testo += _coppie("0", "ENDSEC", "0", "EOF")
    with io.open(percorso, "w", encoding="latin-1", newline="\r\n") as f:
        f.write(testo)
    return percorso


class TestConteggioScritte(unittest.TestCase):
    def test_conta_le_entita_per_layer(self):
        p = _dxf(tempfile.mkdtemp(), _punto("01651") + _punto("01651") + _testo("01653"),
                 layer=("01651", "01653"))
        per_layer, per_tipo = V.conta_scritte(p)
        self.assertEqual(dict(per_layer), {"01651": 2, "01653": 1})
        self.assertEqual(dict(per_tipo), {"POINT": 2, "TEXT": 1})

    def test_vertex_e_seqend_non_sono_entita(self):
        """E' la trappola che rendeva il confronto inutilizzabile: contandoli,
        il DXF di Mendrisio dava 1 227 582 contro 468 622, cioe' un allarme
        continuo su un file sano."""
        p = _dxf(tempfile.mkdtemp(),
                 _polilinea("01651", [(CX, CY), (CX + 10, CY), (CX + 10, CY + 10)]))
        per_layer, per_tipo = V.conta_scritte(p)
        self.assertEqual(dict(per_layer), {"01651": 1})
        self.assertEqual(dict(per_tipo), {"POLYLINE": 1})

    def test_un_valore_uguale_a_zero_non_sposta_il_conteggio(self):
        """Lettura a coppie e non riga per riga: il valore del gruppo 70 qui
        e' "0", e riga per riga verrebbe scambiato per l'inizio di una nuova
        entita'. E' un difetto vero, gia' trovato una volta."""
        p = _dxf(tempfile.mkdtemp(), _punto("01651") * 3)
        per_layer, _t = V.conta_scritte(p)
        self.assertEqual(per_layer["01651"], 3)

    def test_legge_i_layer_dichiarati(self):
        p = _dxf(tempfile.mkdtemp(), _punto("01651"),
                 layer=("01651", "01653", "TI_NUMERO_OS"))
        self.assertEqual(set(V.layer_dichiarati(p)),
                         {"01651", "01653", "TI_NUMERO_OS"})


class TestRiletturaGdal(unittest.TestCase):
    def test_un_dxf_sano_non_perde_niente(self):
        p = _dxf(tempfile.mkdtemp(),
                 _punto("01651") + _testo("01651")
                 + _polilinea("01651", [(CX, CY), (CX + 5, CY + 5)]))
        esito = V.verifica(p)
        self.assertTrue(esito.leggibile, esito.problemi)
        self.assertEqual(esito.scritte, 3)
        self.assertEqual(esito.lette, esito.scritte)
        self.assertEqual(esito.scarti, [])
        self.assertTrue(esito.ok, esito.problemi)

    def test_una_polilinea_vuota_viene_scartata_e_si_vede(self):
        """IL CASO PER CUI ESISTE QUESTO CONTROLLO: un'entita' che noi
        scriviamo e un lettore indipendente butta. Misurato: GDAL scarta la
        POLYLINE senza vertici, quella senza SEQEND, la REGION e i tipi che non
        conosce."""
        p = _dxf(tempfile.mkdtemp(),
                 _punto("01651")
                 + _coppie("0", "POLYLINE", "8", "01651", "66", "1", "70", "0")
                 + _coppie("0", "SEQEND", "8", "01651"))
        esito = V.verifica(p)
        self.assertEqual(esito.scritte, 2)
        self.assertEqual(esito.lette, 1, "GDAL deve scartare la polilinea vuota")
        self.assertFalse(esito.ok)
        self.assertTrue(any("scartate" in x for x in esito.problemi), esito.problemi)

    def test_un_tipo_di_entita_sconosciuto_viene_scartato(self):
        p = _dxf(tempfile.mkdtemp(),
                 _punto("01651")
                 + _coppie("0", "PIPPO", "8", "01651", "10", "1.0", "20", "2.0"))
        esito = V.verifica(p)
        self.assertEqual((esito.scritte, esito.lette), (2, 1))
        self.assertFalse(esito.ok)

    def test_il_flag_70_1_sui_vertici_GDAL_lo_legge(self):
        """Questo NON lo prende: e' il difetto che ci aveva morso, ma li' a
        scartare la polilinea era ezdxf. I due lettori non si sostituiscono a
        vicenda, e il commento del modulo lo dice."""
        p = _dxf(tempfile.mkdtemp(),
                 _punto("01651")
                 + _polilinea("01651", [(CX, CY), (CX + 5, CY + 5)],
                              flag_vertice="1"))
        esito = V.verifica(p)
        self.assertEqual(esito.lette, esito.scritte)

    def test_i_messaggi_di_gdal_vengono_raccolti(self):
        """Senza raccoglierli finirebbero su stderr, cioe' in nessun posto che
        l'utente guardi. Sulla POLYLINE senza SEQEND GDAL dice riga e file."""
        p = _dxf(tempfile.mkdtemp(),
                 _punto("01651")
                 + _coppie("0", "POLYLINE", "8", "01651", "66", "1", "70", "0")
                 + _coppie("0", "VERTEX", "8", "01651", "10", "%.3f" % CX,
                           "20", "%.3f" % CY, "30", "0.0", "70", "0"))
        esito = V.verifica(p)
        self.assertTrue(esito.messaggi_gdal,
                        "GDAL segnala l'errore: va riportato, non buttato")

    def test_entita_su_un_layer_non_dichiarato(self):
        """Si disegna lo stesso, ma con colore e spessore decisi da chi apre il
        file: e' il modo silenzioso di perdere la conformita'."""
        p = _dxf(tempfile.mkdtemp(), _punto("01651") + _punto("MAI_DICHIARATO"),
                 layer=("01651",))
        esito = V.verifica(p)
        self.assertIn("MAI_DICHIARATO", esito.non_dichiarati)
        self.assertFalse(esito.ok)

    def test_layer_dichiarati_e_vuoti_non_sono_un_errore(self):
        """Alcuni layer sono dichiarati apposta e restano spenti: nel DXF vero
        sono 22."""
        p = _dxf(tempfile.mkdtemp(), _punto("01651"),
                 layer=("01651", "01653", "TI_NUMERO_OS"))
        esito = V.verifica(p)
        self.assertEqual(set(esito.vuoti), {"01653", "TI_NUMERO_OS"})
        self.assertTrue(esito.ok, esito.problemi)

    def test_coordinate_fuori_da_mn95(self):
        """Non e' uno spostamento: e' un altro sistema di riferimento, oppure
        un oggetto rimasto a coordinate zero."""
        p = _dxf(tempfile.mkdtemp(), _punto("01651") + _punto("01651", 0.0, 0.0))
        esito = V.verifica(p)
        self.assertFalse(esito.ok)
        self.assertTrue(any("MN95" in x for x in esito.problemi), esito.problemi)

    def test_estensione_riportata(self):
        p = _dxf(tempfile.mkdtemp(),
                 _punto("01651") + _punto("01651", CX + 100, CY + 50))
        esito = V.verifica(p)
        self.assertAlmostEqual(esito.estensione[0], CX, places=2)
        self.assertAlmostEqual(esito.estensione[2], CX + 100, places=2)

    def test_file_che_non_esiste(self):
        esito = V.verifica(os.path.join(tempfile.mkdtemp(), "manca.dxf"))
        self.assertFalse(esito.ok)
        self.assertFalse(esito.leggibile)

    def test_file_che_non_e_un_dxf(self):
        cartella = tempfile.mkdtemp()
        percorso = os.path.join(cartella, "finto.dxf")
        with io.open(percorso, "w", encoding="latin-1") as f:
            f.write("questo non e' un DXF\n")
        esito = V.verifica(percorso)
        self.assertFalse(esito.ok)

    def test_l_opzione_globale_di_gdal_viene_rimessa_a_posto(self):
        """DXF_INLINE_BLOCKS e' una configurazione di processo: lasciarla
        cambiata modificherebbe il driver DXF per tutto QGIS."""
        from osgeo import gdal
        gdal.SetConfigOption("DXF_INLINE_BLOCKS", "TRUE")
        p = _dxf(tempfile.mkdtemp(), _punto("01651"))
        V.verifica(p)
        self.assertEqual(gdal.GetConfigOption("DXF_INLINE_BLOCKS", None), "TRUE")
        gdal.SetConfigOption("DXF_INLINE_BLOCKS", None)


class TestRighe(unittest.TestCase):
    def test_il_riepilogo_dice_l_esito(self):
        p = _dxf(tempfile.mkdtemp(), _punto("01651"))
        righe = V.righe_di_esito(V.verifica(p))
        self.assertTrue(any("Nessuno scarto" in r for r in righe), righe)

    def test_il_riepilogo_elenca_gli_scarti(self):
        p = _dxf(tempfile.mkdtemp(),
                 _coppie("0", "POLYLINE", "8", "01651", "66", "1", "70", "0")
                 + _coppie("0", "SEQEND", "8", "01651"))
        righe = V.righe_di_esito(V.verifica(p))
        self.assertTrue(any("01651" in r and "❌" in r for r in righe), righe)

    def test_senza_gdal_il_modulo_lo_dice_invece_di_esplodere(self):
        per_layer, estensione, errore, messaggi = V.conta_lette(
            "x.dxf", gdal=None, ogr=None)
        # Qui GDAL c'e' davvero, quindi l'errore sara' sul file, non sull'import:
        # basta che non sollevi.
        self.assertIsInstance(errore, str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
