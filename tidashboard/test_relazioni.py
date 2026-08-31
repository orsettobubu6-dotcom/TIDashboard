# Prove delle relazioni e dei join.
#
# DUE GRUPPI. Il primo non importa QGIS: legge chiavi esterne da GeoPackage
# costruiti qui con sqlite3, e gira nel lavoro di CI da dieci secondi. Il
# secondo costruisce layer VERI con OGR e ha bisogno di QGIS.
#
# La guardia sul secondo gruppo e' RUMOROSA di proposito. Uno skip silenzioso
# nel lavoro dove QGIS c'e' vorrebbe dire una suite verde che non ha provato
# niente - il modo migliore per credere coperto cio' che non lo e'. Se
# TIDASHBOARD_QGIS_ATTESO e' impostato (lo imposta la CI nel contenitore
# QGIS) e l'import fallisce, la prova FALLISCE invece di saltare.
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tidashboard import relazioni as R

QGIS_ATTESO = bool(os.environ.get("TIDASHBOARD_QGIS_ATTESO"))
try:
    from osgeo import ogr
    from qgis.core import QgsApplication, QgsProject, QgsVectorLayer
    C_E_QGIS = True
    PERCHE_NO = ""
except ImportError as errore:
    C_E_QGIS = False
    PERCHE_NO = str(errore)


def _gpkg_vuoto(cartella, nome="prova.gpkg"):
    """Un file sqlite col nome di un GeoPackage. Per il gruppo puro basta:
    chiavi_esterne legge sqlite_master, non i metadati OGC."""
    return os.path.join(cartella, nome)


def _metadati_ili2db(percorso, righe, nome_tabella="T_ILI2DB_COLUMN_PROP"):
    """La tabella di metadati di ili2db, col nome MAIUSCOLO che ha davvero."""
    con = sqlite3.connect(percorso)
    con.execute("CREATE TABLE %s (tablename TEXT, columnname TEXT, "
                "tag TEXT, setting TEXT)" % nome_tabella)
    con.executemany("INSERT INTO %s VALUES (?, ?, 'ch.ehi.ili2db.foreignKey', ?)"
                    % nome_tabella, righe)
    con.commit()
    con.close()


class LetturaDelleChiavi(unittest.TestCase):
    """Il gruppo che non ha bisogno di QGIS."""

    def setUp(self):
        self.cartella = tempfile.mkdtemp()
        self.percorso = _gpkg_vuoto(self.cartella)

    def test_vincoli_veri(self):
        """--createFk: le chiavi stanno nei vincoli, le legge PRAGMA."""
        con = sqlite3.connect(self.percorso)
        con.execute("CREATE TABLE punti_di_confine (T_Id INTEGER PRIMARY KEY)")
        con.execute("CREATE TABLE posizione (T_Id INTEGER PRIMARY KEY, "
                    "pdc INTEGER REFERENCES punti_di_confine(T_Id))")
        con.commit()
        con.close()

        chiavi = R.chiavi_esterne(self.percorso)

        self.assertEqual(len(chiavi), 1)
        self.assertEqual(chiavi[0], R.Chiave("posizione", "pdc", "punti_di_confine", "T_Id"))

    def test_ripiego_sui_metadati_maiuscoli(self):
        """DIFETTO VERO. Senza --createFk le chiavi stanno solo nei metadati
        di ili2db, e quella tabella si chiama T_ILI2DB_COLUMN_PROP in
        MAIUSCOLO. In SQLite il confronto su sqlite_master.name distingue le
        maiuscole: cercandola in minuscolo il ripiego non si attivava mai e
        non veniva creato NESSUN join."""
        con = sqlite3.connect(self.percorso)
        con.execute("CREATE TABLE edifici (T_Id INTEGER PRIMARY KEY)")
        con.execute("CREATE TABLE indirizzi (T_Id INTEGER PRIMARY KEY, edificio INTEGER)")
        con.commit()
        con.close()
        _metadati_ili2db(self.percorso, [("indirizzi", "edificio", "edifici")])

        # Controllo di realta': la tabella e' davvero MAIUSCOLA. Senza questo
        # la prova passerebbe anche con un file che non riproduce il difetto.
        con = sqlite3.connect(self.percorso)
        nomi = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        con.close()
        self.assertIn("T_ILI2DB_COLUMN_PROP", nomi)
        self.assertNotIn("t_ili2db_column_prop", nomi)

        chiavi = R.chiavi_esterne(self.percorso)

        self.assertEqual(chiavi, [R.Chiave("indirizzi", "edificio", "edifici", "T_Id")])

    def test_il_vincolo_vero_batte_i_metadati(self):
        """La stessa colonna dichiarata in tutti e due i posti va contata una
        volta sola, e vince il vincolo vero - che porta la colonna del padre
        giusta invece del "T_Id" supposto dal ripiego."""
        con = sqlite3.connect(self.percorso)
        con.execute("CREATE TABLE padre (chiave INTEGER PRIMARY KEY)")
        con.execute("CREATE TABLE figlio (T_Id INTEGER PRIMARY KEY, "
                    "rif INTEGER REFERENCES padre(chiave))")
        con.commit()
        con.close()
        _metadati_ili2db(self.percorso, [("figlio", "rif", "padre")])

        chiavi = R.chiavi_esterne(self.percorso)

        self.assertEqual(len(chiavi), 1)
        self.assertEqual(chiavi[0].colonna_padre, "chiave")

    def test_apostrofo_nel_nome_della_tabella(self):
        """PRAGMA non accetta il binding '?' sui nomi di tabella, quindi il
        nome viene quotato a mano. Un apostrofo nel nome chiuderebbe la
        stringa: senza il raddoppio la lettura muore con un errore di
        sintassi e il GeoPackage sembra illeggibile."""
        con = sqlite3.connect(self.percorso)
        con.execute('CREATE TABLE "l\'edificio" (T_Id INTEGER PRIMARY KEY)')
        con.commit()
        con.close()

        self.assertEqual(R.chiavi_esterne(self.percorso), [])

    def test_nessun_metadato_lo_dice(self):
        con = sqlite3.connect(self.percorso)
        con.execute("CREATE TABLE sola (T_Id INTEGER PRIMARY KEY)")
        con.commit()
        con.close()

        righe = []
        self.assertEqual(R.chiavi_esterne(self.percorso, righe.append), [])
        self.assertTrue(any("t_ili2db_column_prop non presente" in r for r in righe),
                        "il registro non dice perche' non c'e' nessuna chiave")

    def test_le_tabelle_di_servizio_non_contano(self):
        con = sqlite3.connect(self.percorso)
        con.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
        con.execute("CREATE TABLE vero (T_Id INTEGER PRIMARY KEY)")
        con.commit()
        con.close()

        righe = []
        R.chiavi_esterne(self.percorso, righe.append)
        self.assertTrue(any("Tabelle nel DB: 1" in r for r in righe), righe)

    def test_file_rotto_non_e_un_file_senza_relazioni(self):
        """Un GeoPackage illeggibile deve ALZARE. Restituire [] lo farebbe
        passare per un file senza chiavi esterne, e il caricamento
        proseguirebbe senza un join e senza una parola."""
        with open(self.percorso, "wb") as f:
            f.write(b"questo non e' un database" * 40)

        with self.assertRaises(sqlite3.DatabaseError):
            R.chiavi_esterne(self.percorso)

    def test_file_assente_non_ne_crea_uno_vuoto(self):
        """sqlite3.connect su un percorso inesistente CREA un database vuoto:
        la lettura riuscirebbe con zero chiavi, lasciando in giro un file
        finto al posto del GeoPackage. Deve alzare, e non deve creare niente."""
        mancante = os.path.join(self.cartella, "non_c_e.gpkg")

        with self.assertRaises(sqlite3.Error):
            R.chiavi_esterne(mancante)
        self.assertFalse(os.path.exists(mancante), "ha creato un GeoPackage finto")


@unittest.skipUnless(C_E_QGIS, "QGIS non disponibile: %s" % PERCHE_NO)
class ApplicazioneAiLayer(unittest.TestCase):
    """Il gruppo che ha bisogno di QGIS e di layer veri.

    Layer VERI scritti con OGR, non layer di memoria: il nome RAW della
    tabella si legge dalla URI di origine ("...gpkg|layername=xxx"), che un
    layer di memoria non ha. Provarlo in memoria proverebbe un'altra cosa.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = None
        if QgsApplication.instance() is None:
            cls.app = QgsApplication([], False)
            cls.app.initQgis()

    def setUp(self):
        self.cartella = tempfile.mkdtemp()
        self.percorso = os.path.join(self.cartella, "dati.gpkg")

        driver = ogr.GetDriverByName("GPKG")
        fonte = driver.CreateDataSource(self.percorso)

        padre = fonte.CreateLayer("punti_di_confine", geom_type=ogr.wkbPoint)
        padre.CreateField(ogr.FieldDefn("T_Id", ogr.OFTInteger))
        for identificativo in (1, 2):
            f = ogr.Feature(padre.GetLayerDefn())
            f.SetField("T_Id", identificativo)
            geometria = ogr.CreateGeometryFromWkt("POINT(2712000 1115000)")
            f.SetGeometry(geometria)
            padre.CreateFeature(f)

        # Senza geometria, come le cinque tabelle Simbolo* del modello.
        figlio = fonte.CreateLayer("simbolopunto_di_confine", geom_type=ogr.wkbNone)
        figlio.CreateField(ogr.FieldDefn("T_Id", ogr.OFTInteger))
        figlio.CreateField(ogr.FieldDefn("pdc", ogr.OFTInteger))
        figlio.CreateField(ogr.FieldDefn("ori", ogr.OFTReal))
        for identificativo, rif, ori in ((10, 1, 33.5), (11, 2, 0.0)):
            f = ogr.Feature(figlio.GetLayerDefn())
            f.SetField("T_Id", identificativo)
            f.SetField("pdc", rif)
            f.SetField("ori", ori)
            figlio.CreateFeature(f)

        # Una figlia NORMALE, con geometria, sullo stesso padre: serve a
        # mostrare che il join diretto viene saltato solo per le tabelle
        # Simbolo* senza geometria e non per tutti.
        normale = fonte.CreateLayer("posizione_numero", geom_type=ogr.wkbPoint)
        normale.CreateField(ogr.FieldDefn("T_Id", ogr.OFTInteger))
        normale.CreateField(ogr.FieldDefn("pdc", ogr.OFTInteger))
        f = ogr.Feature(normale.GetLayerDefn())
        f.SetField("T_Id", 20)
        f.SetField("pdc", 1)
        f.SetGeometry(ogr.CreateGeometryFromWkt("POINT(2712001 1115001)"))
        normale.CreateFeature(f)
        fonte = None

        _metadati_ili2db(self.percorso,
                         [("simbolopunto_di_confine", "pdc", "punti_di_confine"),
                          ("posizione_numero", "pdc", "punti_di_confine")])

        self.padre = QgsVectorLayer(
            "%s|layername=punti_di_confine" % self.percorso, "Punti di confine", "ogr")
        self.figlio = QgsVectorLayer(
            "%s|layername=simbolopunto_di_confine" % self.percorso,
            "Simbolo punto di confine", "ogr")
        self.normale = QgsVectorLayer(
            "%s|layername=posizione_numero" % self.percorso, "Numeri", "ogr")
        self.layers = [self.padre, self.figlio, self.normale]
        self.assertTrue(all(lay.isValid() for lay in self.layers))

        # I layer stanno nel progetto perche' QgsRelation risolve gli ID
        # attraverso di esso: una relazione fra layer non registrati non e'
        # valida, e la prova misurerebbe quello invece del collegamento.
        self.progetto = QgsProject.instance()
        self.progetto.addMapLayers(self.layers)

    def tearDown(self):
        self.progetto.relationManager().clear()
        self.progetto.removeAllMapLayers()

    def test_i_layer_rinominati_si_collegano_lo_stesso(self):
        """DIFETTO VERO (niente etichette su beni immobili e indirizzi). Al
        momento di collegare, i layer sono gia' stati rinominati coi nomi
        leggibili in italiano; le chiavi esterne portano invece i nomi RAW
        delle tabelle. Indicizzando per layer.name() il confronto falliva in
        silenzio per circa 123 join su 128."""
        self.assertNotEqual(self.padre.name(), "punti_di_confine")

        relazioni, join, orientamenti = R.collega_layer(
            self.percorso, self.layers, self.progetto)

        # Due relazioni, ma UN solo join diretto: quello verso la tabella
        # Simbolo* senza geometria si salta apposta.
        self.assertEqual((relazioni, join), (2, 1))
        self.assertEqual(orientamenti, 1)

    def test_il_join_porta_davvero_i_campi(self):
        """Il conto dei join dice solo che addJoin() ha risposto di si'. La
        cosa che serve e' che i campi del padre compaiano sul figlio."""
        R.collega_layer(self.percorso, self.layers, self.progetto)

        campi = [c.name().lower() for c in self.normale.fields()]
        self.assertTrue(any(c.startswith("punti_di_confine_") for c in campi), campi)

    def test_niente_join_diretto_sulla_tabella_senza_geometria(self):
        """DIFETTO VERO, misurato su una consegna vera: ZERO orientamenti su
        undici chiavi Simbolo*. Il join diretto e quello dell'orientamento
        fanno un anello fra gli stessi due layer e QGIS rifiuta il secondo.
        Il diretto qui non serviva a niente - porta i campi del padre su una
        tabella che non ha geometria e non viene mai disegnata - quindi si
        salta, e l'anello non si forma."""
        R.collega_layer(self.percorso, self.layers, self.progetto)

        campi = [c.name().lower() for c in self.figlio.fields()]
        self.assertFalse(any(c.startswith("punti_di_confine_") for c in campi),
                         "il join diretto rifa' l'anello: %s" % campi)

    def test_orientamento_del_simbolo_sul_padre(self):
        """Il join che va nel verso opposto a tutti gli altri: "ori" sta sulla
        tabella senza geometria, ma serve al layer che la geometria ce l'ha.
        Il campo deve arrivare sul padre col nome fisso che cercano gli stili,
        e portare il valore giusto riga per riga."""
        R.collega_layer(self.percorso, self.layers, self.progetto)

        self.assertGreaterEqual(self.padre.fields().indexFromName(R.CAMPO_ORI_SIMBOLO), 0,
                                [c.name() for c in self.padre.fields()])
        valori = {f["T_Id"]: f[R.CAMPO_ORI_SIMBOLO] for f in self.padre.getFeatures()}
        self.assertAlmostEqual(valori[1], 33.5)

    def test_senza_layer_non_tocca_il_progetto(self):
        self.assertEqual(R.collega_layer(self.percorso, [], self.progetto), (0, 0, 0))
        self.assertEqual(len(self.progetto.relationManager().relations()), 0)

    def test_gpkg_rotto_non_ferma_il_caricamento(self):
        """Il file illeggibile alza, ma chi carica un progetto deve
        proseguire: una riga di registro e zero collegamenti."""
        rotto = os.path.join(self.cartella, "rotto.gpkg")
        with open(rotto, "wb") as f:
            f.write(b"niente affatto un database" * 40)

        righe = []
        esito = R.collega_layer(rotto, self.layers, self.progetto,
                                lambda t, _l=None: righe.append(t))

        self.assertEqual(esito, (0, 0, 0))
        self.assertTrue(any("Errore lettura FK" in r for r in righe), righe)


if __name__ == "__main__":
    if QGIS_ATTESO and not C_E_QGIS:
        sys.stderr.write("QGIS era atteso ma non si importa: %s\n" % PERCHE_NO)
        raise SystemExit(1)
    sys.stderr.write("gruppo QGIS: %s\n" % ("eseguito" if C_E_QGIS else "SALTATO"))
    unittest.main(verbosity=2)
