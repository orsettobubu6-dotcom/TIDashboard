# Test della consegna del progetto per QGIS Server.
#
# I progetti di prova sono piccoli ma VERI: un GeoPackage scritto davvero, un
# simbolo SVG preso dalla cartella del plugin, un progetto scritto su disco e
# poi riaperto e letto. Il controllo sulla consegna non si prova su un oggetto
# in memoria - quello lo abbiamo appena impostato noi, e riguardarlo direbbe
# solo che il codice fa quello che fa: si prova sul file scritto, rompendolo.
#
# LA PROVA CHE CONTA e' TestIlControlloMorde. Un controllo che non ha mai detto
# "no" non e' un controllo: e' successo con la lista dei moduli attesi dello zip
# (diceva PACCHETTO VALIDO anche togliendo un modulo) e non deve succedere qui.
# Ognuno dei quattro guasti li' sotto e' un modo reale in cui una consegna esce
# rotta senza che nulla protesti.
#
# Eseguire con l'interprete di QGIS:
#   & "C:\Program Files\QGIS 4.2.0\bin\python-qgis.bat" test_pubblica_progetto.py
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qgis.core import (
    QgsApplication,
    QgsCoordinateTransformContext,
    QgsFeature,
    QgsFillSymbol,
    QgsGeometry,
    QgsMapLayer,
    QgsMarkerSymbol,
    QgsPalLayerSettings,
    QgsPointXY,
    QgsProject,
    QgsRuleBasedRenderer,
    QgsSingleSymbolRenderer,
    QgsSvgMarkerSymbolLayer,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
)

QgsApplication.setPrefixPath(os.environ.get("QGIS_PREFIX_PATH", ""), True)
_qgs = QgsApplication([], False)
_qgs.initQgis()

import pubblica_progetto as P
from stili import StiliMixin

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
SYMBOLS_DIR = os.path.join(PLUGIN_DIR, "symbols")


def _un_svg():
    cartella = os.path.join(SYMBOLS_DIR, "normal")
    for nome in sorted(os.listdir(cartella)):
        if nome.lower().endswith(".svg"):
            return os.path.join(cartella, nome)
    raise unittest.SkipTest("nessun SVG nella dotazione del plugin")


def _gpkg(percorso, tabella, tipo, punti=()):
    """Una tabella vera dentro un GeoPackage vero.

    I campi si dichiarano nell'URI del layer di memoria, come in tutte le
    altre suite, invece di costruirli con QgsField/QVariant: QVariant e' un
    residuo di Qt5 che PyQt6 sta togliendo, e questa era l'unica riga di tutto
    il plugin che ci si appoggiava. Ha funzionato sul QGIS di Windows e ha
    fatto cadere il job Linux della CI - un'API che il resto del codice evita
    non e' il posto giusto per scoprire una differenza di ambiente."""
    memoria = QgsVectorLayer("%s?crs=EPSG:2056&field=numero:string" % tipo,
                             tabella, "memory")
    if punti:
        elementi = []
        for x, y in punti:
            f = QgsFeature(memoria.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            elementi.append(f)
        memoria.dataProvider().addFeatures(elementi)
        memoria.updateExtents()
    opzioni = QgsVectorFileWriter.SaveVectorOptions()
    opzioni.driverName = "GPKG"
    opzioni.layerName = tabella
    if os.path.exists(percorso):
        opzioni.actionOnExistingFile = \
            QgsVectorFileWriter.CreateOrOverwriteLayer
    QgsVectorFileWriter.writeAsVectorFormatV3(
        memoria, percorso, QgsCoordinateTransformContext(), opzioni)
    return QgsVectorLayer("%s|layername=%s" % (percorso, tabella), tabella, "ogr")


def _invisibile(layer):
    radice = QgsRuleBasedRenderer.Rule(None)
    radice.setLabel(P.ETICHETTA_INVISIBILE)
    layer.setRenderer(QgsRuleBasedRenderer(radice))
    return layer


def _con_etichetta(layer):
    impostazioni = QgsPalLayerSettings()
    impostazioni.fieldName = "numero"
    impostazioni.enabled = True
    layer.setLabeling(QgsVectorLayerSimpleLabeling(impostazioni))
    layer.setLabelsEnabled(True)
    return layer


def progetto_di_prova(con_punti=False):
    """(progetto, gpkg, cartella). Quattro layer che coprono i quattro casi
    che la consegna deve distinguere."""
    base = tempfile.mkdtemp()
    lavoro = os.path.join(base, "lavoro")
    os.makedirs(lavoro)
    gpkg = os.path.join(lavoro, "comune.gpkg")

    confini = _gpkg(gpkg, "beni_immobili_punto_di_confine", "Point",
                    punti=((2718000.0, 1082000.0), (2718500.0, 1082400.0))
                    if con_punti else ())
    simbolo = QgsMarkerSymbol()
    simbolo.changeSymbolLayer(0, QgsSvgMarkerSymbolLayer(_un_svg()))
    confini.setRenderer(QgsSingleSymbolRenderer(simbolo))

    altimetria = _invisibile(_gpkg(gpkg, "altimetria_linea", "LineString"))
    posfondo = _con_etichetta(_invisibile(
        _gpkg(gpkg, "beni_immobili_posfondo", "Point")))
    copertura = _gpkg(gpkg, "copertura_dl_solo_superficiecs", "Polygon")
    copertura.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol()))

    progetto = QgsProject()
    for layer in (confini, altimetria, posfondo, copertura):
        progetto.addMapLayer(layer)
    return progetto, gpkg, base


class TestChiVaInWms(unittest.TestCase):
    """La domanda "questo layer va nel WMS?" si risponde da quello che il
    plugin ha gia' deciso applicando gli stili, non da un elenco di nomi."""

    @classmethod
    def setUpClass(cls):
        cls.progetto, cls.gpkg, cls.base = progetto_di_prova()
        cls.layer = {P._raw_table_name(lay): lay
                     for lay in cls.progetto.mapLayers().values()}

    def test_un_tema_escluso_dal_cap_153_resta_fuori(self):
        self.assertTrue(P.e_privato(self.layer["altimetria_linea"]))

    def test_un_tema_rappresentato_va_nel_wms(self):
        self.assertFalse(P.e_privato(
            self.layer["beni_immobili_punto_di_confine"]))
        self.assertFalse(P.e_privato(
            self.layer["copertura_dl_solo_superficiecs"]))

    def test_le_tabelle_pos_restano_dentro(self):
        """LA DISTINZIONE CHE COSTA CARA. PosFondo ha il simbolo invisibile
        come l'altimetria, ma per un motivo opposto: cio' che si vede e'
        l'etichetta. Un predicato che guardasse solo il simbolo toglierebbe
        dal WMS meta' delle iscrizioni del piano (PosNumero_di_edificio ne
        porta 7 672 sul solo comune di Mendrisio)."""
        posfondo = self.layer["beni_immobili_posfondo"]
        self.assertTrue(P.e_invisibile(posfondo.renderer()),
                        "il presupposto della prova non regge piu'")
        self.assertFalse(P.e_privato(posfondo))

    def test_getfeatureinfo_solo_dove_serve(self):
        self.assertTrue(P.e_identificabile(
            self.layer["beni_immobili_punto_di_confine"]))
        self.assertTrue(P.e_identificabile(self.layer["beni_immobili_posfondo"]))
        self.assertFalse(P.e_identificabile(
            self.layer["copertura_dl_solo_superficiecs"]))

    def test_un_layer_privato_non_e_mai_identificabile(self):
        self.assertFalse(P.e_identificabile(self.layer["altimetria_linea"]))

    def test_una_tabella_senza_geometria_non_va_nel_wms(self):
        """Fondo, Nome_del_luogo, Oggetto_condotta: caricate solo per fare da
        sorgente ai join. In un GetCapabilities sono rumore."""
        tabella = QgsVectorLayer("None?field=numero:string", "fondo", "memory")
        self.assertTrue(P.senza_geometria(tabella))
        self.assertTrue(P.e_privato(tabella))


class TestEstensione(unittest.TestCase):
    """L'estensione dichiarata dal GeoPackage non e' quella dei dati.

    ili2gpkg scrive in gpkg_contents i limiti dell'INTERO sistema di
    riferimento. Misurato sul comune di prova:

        dichiarata  2480000 1070000 2850000 1310000   tutta la Svizzera
        calcolata   2714971 1077802 2722453 1086633   Mendrisio, 7x9 km

    Il WMSExtent che ne usciva diceva al client di inquadrare la Svizzera
    intera, e il geoportale si apriva su una mappa vuota."""

    def _gpkg_che_mente(self):
        """Un GeoPackage con due punti vicini e gpkg_contents falsato, come
        quello vero. Si scrive con QGIS e poi si sovrascrive il metadato.

        IL LAYER INTERMEDIO SI RILASCIA PRIMA della modifica con sqlite3:
        _gpkg() ne restituisce uno con il file gia' aperto da OGR, e scrivere
        sullo stesso file da un'altra connessione mentre quello e' vivo e'
        cercarsi guai - due lettori dello stesso GeoPackage con idee diverse
        su cosa contenga."""
        cartella = tempfile.mkdtemp()
        percorso = os.path.join(cartella, "bugiardo.gpkg")
        intermedio = _gpkg(percorso, "beni_immobili_punto_di_confine", "Point",
                           punti=((2718000.0, 1082000.0), (2718500.0, 1082400.0)))
        del intermedio
        con = sqlite3.connect(percorso)
        con.execute("UPDATE gpkg_contents SET min_x=2480000, min_y=1070000, "
                    "max_x=2850000, max_y=1310000")
        con.commit()
        con.close()
        return QgsVectorLayer(
            "%s|layername=beni_immobili_punto_di_confine" % percorso,
            "punti", "ogr")

    def test_non_si_crede_a_quella_dichiarata(self):
        layer = self._gpkg_che_mente()
        self.assertTrue(layer.isValid())
        dichiarata = layer.extent()
        self.assertGreater(dichiarata.width(), 300000,
                           "il presupposto della prova non regge: il "
                           "GeoPackage non dichiara piu' il falso")
        vera = P.estensione_vera(layer)
        self.assertLess(vera.width(), 1000, vera.toString())
        self.assertAlmostEqual(vera.xMinimum(), 2718000.0, places=1)
        self.assertAlmostEqual(vera.yMaximum(), 1082400.0, places=1)

    def test_un_layer_vuoto_non_sposta_l_estensione(self):
        progetto, _g, _b = progetto_di_prova()
        est = P.estensione_pubblicata(progetto)
        self.assertTrue(est.isNull() or est.isEmpty(),
                        "senza oggetti non c'e' estensione da dichiarare")


class TestCoerenzaConGliStili(unittest.TestCase):
    """e_invisibile() deve riconoscere lo stile che stili.py produce davvero.

    Se un giorno _gen_stile_invisibile cambiasse etichetta, il predicato qui
    smetterebbe di riconoscerlo e ogni tema escluso dal cap. 1.5.3 finirebbe
    nel WMS senza che nulla protesti. Questa prova lega le due parti, invece
    di fidarsi di una stringa copiata."""

    def test_lo_stile_invisibile_di_stili_viene_riconosciuto(self):
        for tipo in ("POINT", "LINESTRING", "POLYGON"):
            renderer = StiliMixin._gen_stile_invisibile(None, tipo)
            self.assertTrue(P.e_invisibile(renderer),
                            "lo stile invisibile per %s non viene riconosciuto"
                            % tipo)

    def test_uno_stile_normale_non_viene_scambiato(self):
        self.assertFalse(P.e_invisibile(
            QgsSingleSymbolRenderer(QgsFillSymbol())))
        self.assertFalse(P.e_invisibile(None))


class TestShortName(unittest.TestCase):
    def test_e_il_nome_della_tabella_non_quello_del_pannello(self):
        progetto, _gpkg_path, _base = progetto_di_prova()
        layer = next(lay for lay in progetto.mapLayers().values()
                     if "punto_di_confine" in P._raw_table_name(lay))
        layer.setName("Punti di confine")
        self.assertEqual(P.short_name(layer), "beni_immobili_punto_di_confine")

    def test_i_caratteri_non_ammessi_diventano_sottolineature(self):
        layer = QgsVectorLayer("Point", "nome con spazi e/barre", "memory")
        self.assertEqual(P.short_name(layer), "nome_con_spazi_e_barre")

    def test_non_puo_iniziare_con_una_cifra(self):
        layer = QgsVectorLayer("Point", "2056_punti", "memory")
        self.assertTrue(P.short_name(layer)[0].isalpha())

    def test_non_si_tronca(self):
        """Un nome troncato puo' collidere con un altro, e due layer con lo
        stesso nome WMS sono un GetMap ambiguo. Un nome lungo non e' un
        guasto; una collisione si'."""
        lungo = "beni_immobili_" + "a" * 80
        layer = QgsVectorLayer("Point", lungo, "memory")
        self.assertEqual(len(P.short_name(layer)), len(lungo))


class TestFlagWms(unittest.TestCase):
    def setUp(self):
        self.progetto, self.gpkg, self.base = progetto_di_prova()
        self.layer = {P._raw_table_name(lay): lay
                      for lay in self.progetto.mapLayers().values()}

    def _flag(self, layer, nome):
        return bool(int(layer.flags()) & int(getattr(QgsMapLayer.LayerFlag, nome)))

    def test_il_tema_escluso_riceve_private(self):
        P.adegua_layer_per_wms(self.layer["altimetria_linea"])
        self.assertTrue(self._flag(self.layer["altimetria_linea"], "Private"))
        self.assertFalse(self._flag(self.layer["altimetria_linea"],
                                    "Identifiable"))

    def test_la_copertura_resta_pubblica_ma_muta(self):
        cs = self.layer["copertura_dl_solo_superficiecs"]
        P.adegua_layer_per_wms(cs)
        self.assertFalse(self._flag(cs, "Private"))
        self.assertFalse(self._flag(cs, "Identifiable"))

    def test_ripristina_rimette_tutto_com_era(self):
        """I flag non li legge solo il server: Private toglie il layer
        dall'albero e Identifiable spegne lo strumento informazioni del
        desktop. Dopo una consegna la sessione deve essere quella di prima."""
        prima = {lay.id(): int(lay.flags())
                 for lay in self.progetto.mapLayers().values()}
        stati = [P.adegua_layer_per_wms(lay)
                 for lay in self.progetto.mapLayers().values()]
        self.assertNotEqual(
            {lay.id(): int(lay.flags())
             for lay in self.progetto.mapLayers().values()}, prima,
            "la prova non dimostra nulla se i flag non erano cambiati")
        P.ripristina_layer(stati)
        self.assertEqual({lay.id(): int(lay.flags())
                          for lay in self.progetto.mapLayers().values()}, prima)


class TestConsegna(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.progetto, cls.gpkg, cls.base = progetto_di_prova(con_punti=True)
        cls.prima = {
            "sorgenti": {lay.id(): lay.source()
                         for lay in cls.progetto.mapLayers().values()},
            "flag": {lay.id(): int(lay.flags())
                     for lay in cls.progetto.mapLayers().values()},
            "svg": [percorso for _s, percorso, _m in P.strati_svg(cls.progetto)],
            "crs": cls.progetto.crs().authid(),
            "titolo": cls.progetto.title(),
            "file": cls.progetto.fileName(),
        }
        cls.dest = os.path.join(cls.base, "consegna_comune")
        cls.esito = P.consegna(cls.dest, cls.progetto, cls.gpkg, PLUGIN_DIR,
                               titolo="Comune di prova")

    def test_la_cartella_contiene_quello_che_serve(self):
        dentro = set(os.listdir(self.dest))
        for atteso in ("comune.gpkg", "consegna_comune.qgz", "fonts",
                       "symbols", "LEGGIMI.txt"):
            self.assertIn(atteso, dentro)
        self.assertEqual(self.esito["n_font"], len(P.FONT_DA_COPIARE))
        self.assertGreater(self.esito["n_svg"], 0)

    def test_il_file_scritto_e_portatile(self):
        rilievi, dati = P.verifica_consegna(self.dest)
        self.assertEqual(rilievi, [])
        self.assertGreater(dati["n_datasource"], 0)
        self.assertEqual(dati["n_privati"], 1)

    def test_i_simboli_puntano_dentro_la_cartella(self):
        """Il difetto che non si vede se non si guarda il file: il datasource
        diventa relativo da solo perche' il file si e' spostato, il percorso
        dell'SVG no - resta un ../../.. che risale alla cartella del plugin,
        che sul server non esiste."""
        xml = P.leggi_qgs(self.esito["qgz"])
        percorsi = sorted(set(P._RE_SVG.findall(xml)))
        self.assertTrue(percorsi, "nessun simbolo SVG nel progetto scritto")
        for percorso in percorsi:
            self.assertFalse(percorso.startswith(".."),
                             "il simbolo risale fuori dalla consegna: %s"
                             % percorso)
            self.assertTrue(os.path.isfile(
                os.path.join(self.dest, percorso.replace("/", os.sep))))

    def test_il_wms_usa_il_nome_della_tabella(self):
        xml = P.leggi_qgs(self.esito["qgz"])
        self.assertIn("<shortname>beni_immobili_punto_di_confine</shortname>",
                      xml.replace("\n", ""))

    def test_l_estensione_e_una_lista_di_quattro_valori(self):
        """QgsServerProjectUtils::wmsExtent fa readListEntry e scarta tutto
        cio' che non ha esattamente quattro elementi: una stringa con le
        virgole verrebbe letta come una lista di uno e ignorata in silenzio."""
        xml = P.leggi_qgs(self.esito["qgz"])
        self.assertIn("WMSExtent", xml)
        pezzo = xml.split("WMSExtent", 1)[1][:400]
        self.assertEqual(pezzo.count("<value>"), 4, pezzo[:200])

    def test_la_sessione_e_tornata_com_era(self):
        """Senza questo, dopo una consegna il progetto della sessione punta
        alla copia: il passo successivo (DXF, planimetria) scriverebbe la'.
        Il caso normale e' proprio quello scomodo - il plugin non salva mai un
        progetto, quindi fileName() e' vuoto, e un "ripristina solo se c'era"
        lascerebbe la sessione agganciata al .qgz appena scritto."""
        self.assertEqual({lay.id(): lay.source()
                          for lay in self.progetto.mapLayers().values()},
                         self.prima["sorgenti"])
        self.assertEqual({lay.id(): int(lay.flags())
                          for lay in self.progetto.mapLayers().values()},
                         self.prima["flag"])
        self.assertEqual([p for _s, p, _m in P.strati_svg(self.progetto)],
                         self.prima["svg"])
        self.assertEqual(self.progetto.crs().authid(), self.prima["crs"])
        self.assertEqual(self.progetto.title(), self.prima["titolo"])
        self.assertEqual(self.progetto.fileName(), self.prima["file"])

    def test_le_voci_wms_non_restano_addosso_alla_sessione(self):
        valore, presente = self.progetto.readBoolEntry(
            "WMSServiceCapabilities", "/")
        self.assertFalse(presente and valore)

    def test_lo_stile_sopravvive_alla_rimappatura_del_dato(self):
        """setDataSource ricrea il provider: con loadDefaultStyleFlag vero la
        consegna uscirebbe con i colori di serie di QGIS invece che con la
        simbologia della circolare, e nessuno se ne accorgerebbe finche' non
        guarda la mappa."""
        confini = next(lay for lay in self.progetto.mapLayers().values()
                       if "punto_di_confine" in P._raw_table_name(lay))
        strati = P.strati_svg(self.progetto)
        self.assertTrue(strati, "il simbolo SVG e' andato perso")
        self.assertIsInstance(confini.renderer(), QgsSingleSymbolRenderer)

    def test_il_leggimi_dice_che_i_font_vanno_installati(self):
        with open(os.path.join(self.dest, "LEGGIMI.txt"),
                  encoding="utf-8") as f:
            testo = f.read()
        self.assertIn("fc-cache", testo)
        self.assertIn("senza valore legale", testo)


class TestIlControlloMorde(unittest.TestCase):
    """Quattro modi reali di consegnare una cartella rotta. Se il controllo
    non li vede, non serve a niente."""

    def _consegna(self):
        progetto, gpkg, base = progetto_di_prova()
        dest = os.path.join(base, "consegna")
        esito = P.consegna(dest, progetto, gpkg, PLUGIN_DIR, titolo="Prova")
        return progetto, dest, esito

    def test_la_consegna_sana_non_produce_rilievi(self):
        _p, dest, _e = self._consegna()
        self.assertEqual(P.verifica_consegna(dest)[0], [])

    def test_un_simbolo_mancante_dalla_cartella(self):
        _p, dest, _e = self._consegna()
        cartella = os.path.join(dest, "symbols", "normal")
        os.remove(os.path.join(cartella, min(
            f for f in os.listdir(cartella) if f.endswith(".svg"))))
        rilievi = P.verifica_consegna(dest)[0]
        self.assertTrue(any("assente dalla cartella" in r for r in rilievi),
                        rilievi)

    def test_un_font_non_consegnato(self):
        _p, dest, _e = self._consegna()
        os.remove(os.path.join(dest, "fonts", "Cadastra-Bold.ttf"))
        rilievi = P.verifica_consegna(dest)[0]
        self.assertTrue(any("Cadastra-Bold.ttf" in r for r in rilievi), rilievi)

    def test_i_simboli_copiati_ma_non_rimappati(self):
        """E' la consegna che sembra fatta bene: la cartella symbols/ c'e',
        i file ci sono, e nessun simbolo li usa.

        SI CHIEDE CHE IL RILIEVO CI SIA, NON COME E' SCRITTO. Un simbolo non
        rimappato viene messo su carta in due forme diverse a seconda di dove
        gira QGIS - misurate tutt'e due:

          Windows  ../../../../../../../Progetti/COGO/tidashboard/symbols/
                   normal/Symbol_1_Fels.svg          relativo, ma esce
          Linux    /src/tidashboard/symbols/normal/Symbol_1_Fels.svg
                                                     assoluto

        Sono lo stesso guasto - un percorso che sul server non esiste - e il
        controllo li prende con due regole diverse. Chiedere la formula esatta
        legava la prova alla piattaforma: passava qui e faceva cadere il job
        Linux della CI, cioe' proprio la piattaforma per cui questo modulo
        esiste."""
        vera = P.rimappa_svg
        P.rimappa_svg = lambda progetto, origine, destinazione: []
        try:
            _p, dest, _e = self._consegna()
        finally:
            P.rimappa_svg = vera
        rilievi = P.verifica_consegna(dest)[0]
        self.assertTrue(
            any(".svg" in r and ("esce dalla cartella" in r
                                 or "percorso assoluto" in r)
                for r in rilievi),
            rilievi)

    def test_un_simbolo_con_percorso_assoluto(self):
        """La forma che il guasto prende su Linux, provata anche da Windows.

        Il progetto si scrive a mano: aspettare la piattaforma che produce
        quella forma vuol dire scoprire il buco in CI, che e' come l'ho
        scoperto la prima volta."""
        cartella = tempfile.mkdtemp()
        os.makedirs(os.path.join(cartella, "fonts"))
        for nome in P.FONT_DA_COPIARE:
            with open(os.path.join(cartella, "fonts", nome), "wb"):
                pass
        with open(os.path.join(cartella, "prova.qgs"), "w",
                  encoding="utf-8") as f:
            f.write('<qgis><Private>1</Private>'
                    '<WMSServiceCapabilities type="bool">true'
                    '</WMSServiceCapabilities><crs>EPSG:2056</crs>'
                    '<Option name="name" type="QString" '
                    'value="/srv/tidashboard/symbols/normal/Symbol_1.svg"/>'
                    "</qgis>")
        rilievi = P.verifica_consegna(cartella)[0]
        atteso = ("simbolo SVG con percorso assoluto: "
                  "/srv/tidashboard/symbols/normal/Symbol_1.svg")
        self.assertEqual([r for r in rilievi if ".svg" in r], [atteso])

    def _cartella_con_progetto(self, corpo):
        cartella = tempfile.mkdtemp()
        os.makedirs(os.path.join(cartella, "fonts"))
        for nome in P.FONT_DA_COPIARE:
            with open(os.path.join(cartella, "fonts", nome), "wb"):
                pass
        with open(os.path.join(cartella, "prova.qgs"), "w",
                  encoding="utf-8") as f:
            f.write("<qgis>%s</qgis>" % corpo)
        return cartella

    def test_un_layer_temporaneo_non_e_un_file_mancante(self):
        """Difetto trovato dalla prova d'insieme sul pulsante: il controllo
        trattava OGNI datasource come un percorso, e per un layer di memoria
        (sorgente "Point?crs=EPSG:2056&field=...") diceva "assente dalla
        cartella". Non manca nessun file: quel layer non ha file. Il guasto
        vero e' un altro, e va detto per quello che e' - sul server quel layer
        sarebbe vuoto."""
        cartella = self._cartella_con_progetto(
            "<maplayer><datasource>Point?crs=EPSG:2056&amp;field=numero:string"
            "</datasource><provider>memory</provider></maplayer>")
        rilievi = P.verifica_consegna(cartella)[0]
        self.assertTrue(any("layer temporaneo" in r for r in rilievi), rilievi)
        self.assertFalse(any("assente dalla cartella" in r for r in rilievi),
                         rilievi)

    def test_un_layer_di_rete_non_si_cerca_su_disco(self):
        """Un WMS di sfondo sul server funziona: non e' un percorso da
        controllare, e segnalarlo sarebbe un allarme falso ripetuto."""
        cartella = self._cartella_con_progetto(
            "<maplayer><datasource>crs=EPSG:2056&amp;format=image/png&amp;"
            "url=https://wms.geo.admin.ch/</datasource>"
            "<provider>wms</provider></maplayer>")
        rilievi = P.verifica_consegna(cartella)[0]
        self.assertFalse(any("dato" in r for r in rilievi), rilievi)

    def test_un_file_ogr_fuori_dalla_cartella_si_segnala_lo_stesso(self):
        """L'altra meta': togliendo il controllo ai non-file non deve
        sparire anche per i file."""
        cartella = self._cartella_con_progetto(
            "<maplayer><datasource>C:\\altrove\\comune.gpkg|layername=x"
            "</datasource><provider>ogr</provider></maplayer>")
        rilievi = P.verifica_consegna(cartella)[0]
        self.assertTrue(any("percorso assoluto" in r for r in rilievi), rilievi)

    def test_i_percorsi_lasciati_assoluti(self):
        vera = P.adegua_progetto

        def senza_relativi(progetto, titolo="", abstract="", estensione=None):
            vera(progetto, titolo, abstract, estensione)
            progetto.writeEntryBool("Paths", "Absolute", True)

        P.adegua_progetto = senza_relativi
        try:
            _p, dest, _e = self._consegna()
        finally:
            P.adegua_progetto = vera
        rilievi = P.verifica_consegna(dest)[0]
        self.assertTrue(any("percorso assoluto" in r for r in rilievi), rilievi)

    def test_una_cartella_senza_progetto(self):
        vuota = tempfile.mkdtemp()
        rilievi, dati = P.verifica_consegna(vuota)
        self.assertTrue(rilievi)
        self.assertIsNone(dati["qgz"])


class TestPercorsiAssoluti(unittest.TestCase):
    """_e_assoluto guarda le due convenzioni, non quella del sistema su cui
    gira: un "C:\\..." non e' assoluto per os.path su Linux, ed e' esattamente
    il percorso che si vuole scoprire (la CI gira su Linux)."""

    def test_windows(self):
        for p in (r"C:\Users\gabri\comune.gpkg", "D:/dati/comune.gpkg",
                  r"\\server\condivisione\comune.gpkg"):
            self.assertTrue(P._e_assoluto(p), p)

    def test_unix(self):
        self.assertTrue(P._e_assoluto("/srv/qgis/comune.gpkg"))

    def test_relativi(self):
        for p in ("./comune.gpkg", "symbols/normal/Symbol_A.svg", "comune.gpkg",
                  "../fuori.gpkg", ""):
            self.assertFalse(P._e_assoluto(p), p)


if __name__ == "__main__":
    unittest.main(verbosity=2)
