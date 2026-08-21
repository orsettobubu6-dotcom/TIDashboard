# TIDashboard - dati della misurazione ufficiale svizzera in QGIS
# Copyright (C) 2026 Gabriele Peverelli
#
# Questo programma e' software libero: lo si puo' ridistribuire e modificare
# secondo i termini della GNU General Public License pubblicata dalla Free
# Software Foundation, versione 2 o (a scelta) una successiva. Il testo si
# trova nel file LICENSE distribuito insieme al programma.

# Il progetto stilizzato, reso leggibile da QGIS Server: una cartella che si
# copia sul server e basta.
#
# QGIS Server non esegue questo plugin. Apre un file. Tutto cio' che il plugin
# fa a runtime - caricare i font in RAM, risolvere gli SVG dentro la propria
# cartella, puntare al GeoPackage dove sta sul PC - non esiste piu' dall'altra
# parte, e sbaglia in silenzio: un GetMap risponde 200 e restituisce una mappa
# con i simboli sbagliati o senza simboli affatto.
#
# TRE PERCORSI, NON UNO. Il difetto piu' noto e' il datasource assoluto
# (C:\Users\...\comune.gpkg). Ma i percorsi che escono dal PC sono tre, e il
# secondo non si vede finche' non si guarda dentro il file scritto. MISURATO,
# scrivendo un progetto in un'altra cartella con Paths/Absolute=false:
#
#   datasource -> ./comune.gpkg|layername=...                        RELATIVO, ok
#   simbolo    -> ../../../../../../../Progetti/COGO/tidashboard/
#                 symbols/normal/Symbol_1_Fels.svg                   RISALE AL PLUGIN
#
# Il datasource diventa relativo da solo perche' lo si e' spostato; l'SVG no,
# perche' nessuno ha detto al simbolo che il file adesso sta altrove. Copiare
# la cartella symbols/ accanto al .qgz - che sembra la cosa da fare - non
# cambia nulla: niente punta alla copia. I percorsi dei simboli vanno riscritti
# uno per uno (rimappa_svg), come si fa col datasource.
#
# Il terzo percorso non e' un percorso e non si puo' riscrivere: i font. Sei
# file .ttf caricati con QFontDatabase.addApplicationFont(), che vive nel
# processo. Vanno INSTALLATI sulla macchina server (vedi LEGGIMI.txt scritto
# nella cartella di consegna). Nessuna riga di questo modulo puo' evitarlo: si
# limita a copiarli e a dirlo.
#
# CHI NON VA IN WMS SI DEDUCE, NON SI ELENCA. La tentazione e' una lista di
# nomi di tabella ("le *Prog fuori"). Una lista scritta a mano si scolla dal
# codice - e' successo alla lista dei moduli attesi in crea_zip_plugin.py, che
# ne controllava 11 su 17 - e qui si scollerebbe da una decisione che il plugin
# HA GIA' PRESO: _get_renderer_for_table assegna lo stile invisibile a tutto
# cio' che il cap. 1.5.3 non rappresenta, scrivendone il motivo nel registro.
# Quella decisione si legge dal risultato (non_rappresentato), quindi le *Prog,
# le Tenuta_a_giorno, l'altimetria, le aree di numerazione e la ripartizione
# del piano restano fuori dal WMS senza che nessuno le nomini qui.
#
# CON UNA DISTINZIONE CHE COSTA CARA SE SI PERDE: "simbolo invisibile" non vuol
# dire "non rappresentato". Le tabelle Pos* sono i punti di ancoraggio delle
# SCRITTE - il simbolo e' invisibile apposta e cio' che si vede e' l'etichetta.
# PosNumero_di_edificio ne porta 7 672 sul solo comune di Mendrisio. Un
# predicato che guardasse solo il simbolo le toglierebbe dal WMS insieme a
# meta' delle iscrizioni del piano.
#
# LA SESSIONE NON SI TOCCA. consegna() rimette a posto tutto quello che ha
# cambiato - datasource, percorsi SVG, flag dei layer, CRS, titolo, nome del
# file, voci WMS - in un finally. Non e' pignoleria: i flag WMS non li legge
# solo il server. Private toglie il layer dall'albero, Identifiable spegne lo
# strumento "informazioni" del desktop. Lasciarli addosso alla sessione
# significherebbe che dopo una consegna il geometra clicca su una copertura del
# suolo e non ottiene piu' nulla, senza spiegazione. Chi vuole comunque un
# progetto sempre pubblicabile ha adegua_progetto() e adegua_layer_per_wms()
# come funzioni pubbliche, e sceglie lui.
#
# E POI SI GUARDA IL FILE SCRITTO. verifica_consegna() non ricontrolla gli
# oggetti in memoria - quelli li abbiamo appena impostati noi, e riguardarli
# direbbe solo che il codice fa quello che fa. Apre il .qgz, che e' uno zip,
# legge il .qgs dentro e verifica sul TESTO che non sia rimasto un percorso
# assoluto, che ogni file nominato esista davvero nella cartella e che le
# capabilities WMS ci siano. E' lo stesso mestiere di verifica_dxf.py: un
# secondo parere su quello che abbiamo scritto.

import os
import re
import shutil
import zipfile

# qgis.core serve a tutto il modulo TRANNE verifica_consegna(), che legge un
# file e basta: cosi' il controllo dell'artefatto puo' girare anche dove QGIS
# non c'e' (il job veloce della CI, o il server prima di pubblicare).
try:
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsMapLayer,
        QgsRectangle,
        QgsRenderContext,
    )
    QGIS_PRESENTE = True
except ImportError:  # pragma: no cover - dipende dall'ambiente, non dal codice
    QGIS_PRESENTE = False

try:
    from .ordinamento import _raw_table_name
except ImportError:
    from ordinamento import _raw_table_name

CRS_MU = "EPSG:2056"
CRS_WEB = "EPSG:3857"

# L'etichetta che _gen_stile_invisibile mette alla regola radice. E' il
# contratto fra stili.py e chi vuole sapere se un tema e' rappresentato: si
# guarda quella, non i colori del simbolo (lo stile invisibile usa un pennello
# "no", che non dipinge nulla a prescindere dal colore - dedurlo dall'alfa ha
# gia' fatto dichiarare difettosi cinque temi che il codice trattava bene).
ETICHETTA_INVISIBILE = "Invisibile"

# Su quali layer ha senso un GetFeatureInfo. Questa SI' e' una lista, ed e'
# una scelta di prodotto, non la ripetizione di qualcosa che il codice sa gia':
# la norma non dice cosa debba rispondere a un clic. Tre voci, i suffissi della
# tabella GeoPackage. Il resto risponde vuoto: un clic che attraversa 120
# tabelle restituisce un elenco che nessuno legge.
IDENTIFICABILI = ("bene_immobile", "posfondo", "punto_di_confine")

FONT_DA_COPIARE = (
    "Cadastra-Regular.ttf",
    "Cadastra-Bold.ttf",
    "Cadastra-Italic.ttf",
    "Cadastra-BoldItalic.ttf",
    "CadastraSymbol-Regular.ttf",
    "CadastraSymbol-Mask.ttf",
)

ABSTRACT_PREDEFINITO = (
    "Misurazione ufficiale, modello MD01MUTI7MN95. Rappresentazione secondo le "
    "istruzioni federali (circolare 154 allegato 2). Riproduzione senza valore "
    "legale.")

# Le voci di progetto che QGIS Server legge, con il tipo con cui vanno scritte.
# WMSExtent E' UNA LISTA DI QUATTRO VALORI, non una stringa con le virgole:
# QgsServerProjectUtils::wmsExtent fa readListEntry e scarta tutto cio' che non
# ha esattamente quattro elementi - una stringa "x,y,x,y" viene letta come una
# lista di uno e ignorata in silenzio.
_VOCI_WMS = (
    ("WMSServiceCapabilities", "/", "bool"),
    ("WMSServiceTitle", "/", "str"),
    ("WMSServiceAbstract", "/", "str"),
    ("WMSAddWktGeometry", "/", "bool"),
    ("WMSUseLayerIDs", "/", "bool"),
    ("WMSCrsList", "/", "list"),
    ("WMSExtent", "/", "list"),
    ("Paths", "Absolute", "bool"),
)


# --- CHI VA IN WMS E COME ------------------------------------------------

def e_invisibile(renderer):
    """Il plugin ha classificato questo tema come NON rappresentato?

    Vero solo per lo stile che _gen_stile_invisibile produce, riconosciuto
    dall'etichetta della sua regola radice."""
    if renderer is None:
        return False
    radice = getattr(renderer, "rootRule", None)
    if radice is None:
        return False
    try:
        return radice().label() == ETICHETTA_INVISIBILE
    except (AttributeError, RuntimeError):
        return False


def porta_iscrizioni(layer):
    """Il layer non disegna un simbolo ma scrive un'iscrizione del piano.

    E' il caso delle tabelle Pos*: simbolo invisibile per costruzione,
    etichetta accesa. Senza questa domanda finirebbero fuori dal WMS insieme
    ai temi davvero esclusi."""
    try:
        return bool(layer.labelsEnabled() and layer.labeling() is not None)
    except AttributeError:
        return False


def non_rappresentato(layer):
    """Il layer non fa parte del contenuto del piano (cap. 1.5.3).

    Dedotto da quello che il plugin ha gia' deciso quando ha applicato gli
    stili, non da un elenco di nomi tenuto qui."""
    return e_invisibile(layer.renderer()) and not porta_iscrizioni(layer)


def senza_geometria(layer):
    """Tabelle caricate solo per fare da sorgente ai join (Fondo,
    Nome_del_luogo, Oggetto_condotta...). Non hanno niente da disegnare e in
    un GetCapabilities sono solo rumore.

    isSpatial() e non un confronto con QgsWkbTypes.NullGeometry: gli enum di
    geometria stanno migrando da QgsWkbTypes a Qgis, e un confronto con un
    alias deprecato e' il tipo di riga che funziona su una versione e cade
    sull'altra - come e' appena successo con QVariant fra il QGIS di Windows e
    quello della CI."""
    try:
        return not layer.isSpatial()
    except AttributeError:
        return False


def e_privato(layer):
    """Fuori dal WMS: QGIS Server non pubblica i layer con il flag Private."""
    return senza_geometria(layer) or non_rappresentato(layer)


def e_identificabile(layer):
    """Risponde a GetFeatureInfo."""
    if e_privato(layer):
        return False
    nome = (_raw_table_name(layer) or "").lower()
    return any(nome.endswith(s) for s in IDENTIFICABILI)


def short_name(layer):
    """Il nome con cui il layer compare nel WMS.

    E' il nome RAW della tabella GeoPackage, non layer.name(): quello e' il
    titolo "carino" del pannello, cambia con la lingua e con le scelte di
    presentazione, e un client che ci si aggancia si rompe alla prima
    rinominata. Stessa distinzione che ha gia' morso i join (~123 layer su
    128, vedi ordinamento._raw_table_name).

    NON SI TRONCA. Un nome troncato puo' collidere con un altro, e due layer
    con lo stesso nome WMS sono un GetMap ambiguo - un guasto vero, mentre un
    nome lungo non lo e'. Le tabelle di ili2db sono gia' accorciate da ili2db
    stesso (aree_di_numerzone_..., ripartizin_d_pani_...): il caso non si
    presenta."""
    grezzo = _raw_table_name(layer) or layer.name()
    # Il nome deve essere un identificatore XML: lettera iniziale, poi lettere,
    # cifre, punto, trattino, sottolineatura.
    pulito = re.sub(r"[^A-Za-z0-9._-]", "_", grezzo)
    if not pulito or not pulito[0].isalpha():
        pulito = "l_" + pulito
    return pulito


def _leggi_short_name(layer):
    sp = layer.serverProperties() if hasattr(layer, "serverProperties") else None
    if sp is not None and hasattr(sp, "shortName"):
        return sp.shortName()
    return layer.shortName() if hasattr(layer, "shortName") else ""


def _scrivi_short_name(layer, nome):
    # QGIS 4 ha spostato queste proprieta' su serverProperties(); il metodo
    # piatto esiste ancora come scorciatoia deprecata. Si usa il primo che c'e',
    # invece di dare per scontato quale sia sopravvissuto: se un giorno il
    # piatto sparisse, un hasattr sbagliato lascerebbe i layer senza short name
    # e il WMS li esporrebbe con l'id di sessione.
    sp = layer.serverProperties() if hasattr(layer, "serverProperties") else None
    if sp is not None and hasattr(sp, "setShortName"):
        sp.setShortName(nome)
        return True
    if hasattr(layer, "setShortName"):
        layer.setShortName(nome)
        return True
    return False


def adegua_layer_per_wms(layer):
    """Short name OGC, GetFeatureInfo solo dove serve, temi non rappresentati
    fuori dal servizio.

    Ritorna lo stato precedente, da passare a ripristina_layer()."""
    stato = {"layer": layer, "flags": layer.flags(),
             "short": _leggi_short_name(layer)}
    _scrivi_short_name(layer, short_name(layer))
    privato = int(QgsMapLayer.LayerFlag.Private)
    identificabile = int(QgsMapLayer.LayerFlag.Identifiable)
    # Si lavora sull'INTERO e si ricostruisce il tipo alla fine: in PyQt6
    # l'operatore ~ su un membro di enum ritorna un int, e da li' in poi tutta
    # l'espressione degrada a int - setFlags lo rifiuta con un TypeError.
    valore = int(layer.flags())
    if e_privato(layer):
        valore = (valore | privato) & ~identificabile
    else:
        valore = valore & ~privato
        valore = (valore | identificabile) if e_identificabile(layer) \
            else (valore & ~identificabile)
    layer.setFlags(QgsMapLayer.LayerFlags(valore))
    return stato


def ripristina_layer(stati):
    for stato in stati:
        stato["layer"].setFlags(stato["flags"])
        _scrivi_short_name(stato["layer"], stato["short"])


def estensione_pubblicata(project):
    """L'estensione dei soli layer che finiscono nel WMS. Vuota se non ce ne
    sono con geometria: e' il caso di un progetto non ancora importato."""
    unione = QgsRectangle()
    unione.setNull()
    for layer in project.mapLayers().values():
        if e_privato(layer) or senza_geometria(layer):
            continue
        est = layer.extent()
        if est is None or est.isNull() or est.isEmpty():
            continue
        unione.combineExtentWith(est)
    return unione


# --- METADATI DI PROGETTO ------------------------------------------------

def _leggi_voce(project, scope, chiave, tipo):
    if tipo == "bool":
        valore, presente = project.readBoolEntry(scope, chiave)
    elif tipo == "list":
        valore, presente = project.readListEntry(scope, chiave)
    else:
        valore, presente = project.readEntry(scope, chiave)
    return (valore, presente)


def _scrivi_voce(project, scope, chiave, tipo, valore):
    if tipo == "bool":
        project.writeEntryBool(scope, chiave, valore)
    else:
        project.writeEntry(scope, chiave, valore)


def stato_progetto(project):
    """Tutto cio' che adegua_progetto() cambia, com'era prima."""
    voci = []
    for scope, chiave, tipo in _VOCI_WMS:
        valore, presente = _leggi_voce(project, scope, chiave, tipo)
        voci.append((scope, chiave, tipo, valore, presente))
    return {"voci": voci, "crs": project.crs(), "titolo": project.title(),
            "file": project.fileName(),
            "home": project.presetHomePath()
            if hasattr(project, "presetHomePath") else ""}


def ripristina_progetto(project, stato):
    for scope, chiave, tipo, valore, presente in stato["voci"]:
        if presente:
            _scrivi_voce(project, scope, chiave, tipo, valore)
        else:
            project.removeEntry(scope, chiave)
    project.setCrs(stato["crs"])
    project.setTitle(stato["titolo"])
    # Sempre, anche quando era vuoto. E' il caso NORMALE: il plugin non salva
    # mai un progetto, quindi fileName() e' "" quasi sempre, e un "ripristina
    # solo se c'era" lascerebbe la sessione appoggiata al .qgz appena scritto -
    # cioe' proprio il guasto che questo finally esiste per evitare. Il
    # successivo "Progetto -> Salva" del geometra sovrascriverebbe la consegna.
    project.setFileName(stato["file"])
    if hasattr(project, "setPresetHomePath"):
        project.setPresetHomePath(stato["home"])


def adegua_progetto(project, titolo="", abstract=ABSTRACT_PREDEFINITO,
                    estensione=None):
    """Le voci che QGIS Server legge. Senza WMSServiceCapabilities il
    GetCapabilities esce quasi vuoto e un client non carica nulla."""
    project.setCrs(QgsCoordinateReferenceSystem(CRS_MU))
    if titolo:
        project.setTitle(titolo)
    project.writeEntryBool("WMSServiceCapabilities", "/", True)
    project.writeEntry("WMSServiceTitle", "/", titolo or "Misurazione ufficiale")
    project.writeEntry("WMSServiceAbstract", "/", abstract)
    project.writeEntryBool("WMSAddWktGeometry", "/", True)
    # Nomi stabili invece degli id di sessione: un client che salva un permalink
    # deve ritrovare lo stesso layer dopo un nuovo import.
    project.writeEntryBool("WMSUseLayerIDs", "/", False)
    project.writeEntry("WMSCrsList", "/", [CRS_MU, CRS_WEB])
    # I dati restano in LV95: il 3857 e' solo per i client che non sanno altro,
    # e lo riproietta il server.
    project.writeEntryBool("Paths", "Absolute", False)
    if estensione is not None and not estensione.isNull() \
            and not estensione.isEmpty():
        project.writeEntry("WMSExtent", "/", [
            "%.3f" % estensione.xMinimum(), "%.3f" % estensione.yMinimum(),
            "%.3f" % estensione.xMaximum(), "%.3f" % estensione.yMaximum()])


# --- I PERCORSI ----------------------------------------------------------

def _strati_di(simbolo):
    """Ogni strato del simbolo, compresi quelli annidati: le trame a punti
    (vigna, canneto, torbiera) tengono il marcatore SVG in un sotto-simbolo, e
    saltarlo lascerebbe indietro proprio i simboli piu' fragili."""
    for i in range(simbolo.symbolLayerCount()):
        strato = simbolo.symbolLayer(i)
        yield strato
        sotto = strato.subSymbol()
        if sotto is not None:
            yield from _strati_di(sotto)


def _svg_di(strato):
    """(percorso, come_si_scrive) per uno strato che usa un file SVG, oppure
    (None, None). Due famiglie con nomi di metodo diversi: marcatore SVG e
    riempimento SVG."""
    for leggi, scrivi in (("path", "setPath"), ("svgFilePath", "setSvgFilePath")):
        if hasattr(strato, leggi) and hasattr(strato, scrivi):
            valore = getattr(strato, leggi)()
            if valore and str(valore).lower().endswith(".svg"):
                return (str(valore), scrivi)
    return (None, None)


def strati_svg(project):
    """Tutti gli strati di simbolo che nominano un file SVG."""
    trovati = []
    contesto = QgsRenderContext()
    for layer in project.mapLayers().values():
        renderer = layer.renderer() if hasattr(layer, "renderer") else None
        if renderer is None:
            continue
        try:
            simboli = renderer.symbols(contesto)
        except (AttributeError, RuntimeError):
            continue
        for simbolo in simboli:
            for strato in _strati_di(simbolo):
                percorso, scrivi = _svg_di(strato)
                if percorso:
                    trovati.append((strato, percorso, scrivi))
    return trovati


def rimappa_svg(project, origine, destinazione):
    """Fa puntare i simboli alla copia degli SVG nella cartella di consegna.

    Senza questo, salvare il progetto altrove scrive un percorso RELATIVO che
    risale fino alla cartella del plugin - misurato:
    "../../../../../../../Progetti/COGO/tidashboard/symbols/normal/
    Symbol_1_Fels.svg". Sul server quel percorso non esiste e il simbolo non
    si disegna, senza che il GetMap segnali nulla.

    Ritorna la lista per ripristina_svg(); gli SVG che non stanno sotto
    'origine' (per esempio quelli della libreria di QGIS) non si toccano - li
    segnala verifica_consegna(), che li vede nel file scritto."""
    orig = os.path.normcase(os.path.normpath(str(origine)))
    toccati = []
    for strato, percorso, scrivi in strati_svg(project):
        normalizzato = os.path.normcase(os.path.normpath(percorso))
        if not normalizzato.startswith(orig + os.sep):
            continue
        relativo = os.path.relpath(percorso, str(origine))
        nuovo = os.path.join(str(destinazione), relativo)
        getattr(strato, scrivi)(nuovo)
        toccati.append((strato, percorso, scrivi))
    return toccati


def ripristina_svg(toccati):
    for strato, percorso, scrivi in toccati:
        getattr(strato, scrivi)(percorso)


def rimappa_gpkg(project, gpkg_prima, gpkg_dopo):
    """Riscrive il datasource dei layer OGR che puntano a gpkg_prima."""
    prima = os.path.normcase(os.path.normpath(str(gpkg_prima)))
    toccati = []
    for layer in project.mapLayers().values():
        src = layer.source()
        base = src.split("|", 1)[0]
        if os.path.normcase(os.path.normpath(base)) != prima:
            continue
        resto = src[len(base):]
        provider = layer.providerType() or "ogr"
        # loadDefaultStyleFlag resta al suo valore predefinito (falso): con il
        # vero, QGIS ricaricherebbe lo stile dal file e la consegna uscirebbe
        # con i colori di serie invece che con la simbologia della circolare.
        layer.setDataSource(str(gpkg_dopo) + resto, layer.name(), provider)
        toccati.append((layer, src, provider))
    return toccati


def ripristina_gpkg(toccati):
    for layer, src, provider in toccati:
        layer.setDataSource(src, layer.name(), provider)


# --- LA CARTELLA DI CONSEGNA ---------------------------------------------

def _copia_dotazione(plugin_dir, dest):
    """Font e SVG: QGIS Server non gira il plugin e non vede tidashboard/."""
    font_dst = os.path.join(dest, "fonts")
    os.makedirs(font_dst, exist_ok=True)
    n_font = 0
    for nome in FONT_DA_COPIARE:
        src = os.path.join(plugin_dir, "fonts", nome)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(font_dst, nome))
            n_font += 1
    svg_src = os.path.join(plugin_dir, "symbols")
    svg_dst = os.path.join(dest, "symbols")
    n_svg = 0
    if os.path.isdir(svg_src):
        if os.path.isdir(svg_dst):
            shutil.rmtree(svg_dst)
        shutil.copytree(svg_src, svg_dst)
        for radice, _cartelle, file in os.walk(svg_dst):
            n_svg += len([f for f in file if f.lower().endswith(".svg")])
    return n_font, n_svg


def _scrivi_leggimi(dest, titolo, n_font):
    testo = """Consegna per QGIS Server
========================

%s

Questa cartella si copia INTERA sul server, con la stessa struttura. Non si
installa TIDashboard su QGIS Server: il server non esegue i plugin, legge
solo il file .qgz.

I FONT VANNO INSTALLATI (%d file in fonts/)
-------------------------------------------
E' l'unico passo che il plugin non puo' fare al posto vostro. QGIS Server
non carica i .ttf che trova accanto al progetto: li cerca fra i font di
sistema. Una volta sola, sul server:

    sudo cp fonts/*.ttf /usr/local/share/fonts/cadastra/
    sudo fc-cache -f
    fc-list | grep -i cadastra          # deve elencarli

Saltando questo passo il WMS risponde lo stesso, con un font di ricambio
scelto da Qt senza dirlo: i punti di confine e i numeri escono con la forma
sbagliata, e non c'e' nessun errore da nessuna parte. La prova e' visiva -
un GetMap "200 OK" non dice niente sul font.

Percorsi
--------
Il .qgz, il .gpkg e la cartella symbols/ stanno insieme e si riferiscono
l'uno all'altro in modo relativo. Spostandone uno solo, la mappa esce
vuota o senza simboli.

Pubblicazione
-------------
Puntare QGIS Server (o QWC2, o Lizmap) al file .qgz di questa cartella.
CRS nativo EPSG:2056; e' pubblicato anche EPSG:3857, riproiettato dal
server, per i client web che non sanno altro.

Il piano per il registro fondiario resta un prodotto di STAMPA. Quello che
il WMS mostra e' una riproduzione senza valore legale.
""" % (titolo or "", n_font)
    with open(os.path.join(dest, "LEGGIMI.txt"), "w", encoding="utf-8") as f:
        f.write(testo)


def consegna(cartella, project, gpkg_path, plugin_dir, titolo="",
             abstract=ABSTRACT_PREDEFINITO):
    """Scrive la cartella di consegna e ritorna cosa contiene.

    LA SESSIONE RESTA COM'ERA. Datasource, percorsi dei simboli, flag dei
    layer, CRS, titolo, nome del file e voci WMS vengono rimessi a posto nel
    finally: chi ha lanciato la consegna continua a lavorare sul GeoPackage
    originale, e il passo dopo (DXF, planimetria) scrive dove scriveva prima.

    Nessuna chiamata all'interfaccia qui dentro - cosi' si prova senza una
    finestra - ma VA CHIAMATA DAL THREAD PRINCIPALE. Il pezzo che dura e' la
    copia del GeoPackage; tutto il resto tocca il progetto QGIS (datasource,
    flag dei layer, percorsi dei simboli), e gli oggetti del progetto non si
    maneggiano da un thread secondario. Meglio qualche secondo di finestra
    ferma che un blocco raro e inspiegabile dentro QGIS."""
    dest = os.path.abspath(str(cartella))
    os.makedirs(dest, exist_ok=True)
    if not os.path.isfile(str(gpkg_path)):
        raise RuntimeError("GeoPackage non trovato: %s" % gpkg_path)
    gpkg_dst = os.path.join(dest, os.path.basename(str(gpkg_path)))
    if os.path.normcase(os.path.normpath(str(gpkg_path))) != \
            os.path.normcase(os.path.normpath(gpkg_dst)):
        shutil.copy2(str(gpkg_path), gpkg_dst)

    n_font, n_svg = _copia_dotazione(plugin_dir, dest)
    _scrivi_leggimi(dest, titolo, n_font)

    qgz = os.path.join(dest, os.path.basename(dest) + ".qgz")
    prima = stato_progetto(project)
    toccati_gpkg = []
    toccati_svg = []
    stati_layer = []
    try:
        toccati_gpkg = rimappa_gpkg(project, gpkg_path, gpkg_dst)
        toccati_svg = rimappa_svg(project, os.path.join(plugin_dir, "symbols"),
                                  os.path.join(dest, "symbols"))
        stati_layer = [adegua_layer_per_wms(lay)
                       for lay in project.mapLayers().values()]
        adegua_progetto(project, titolo, abstract,
                        estensione_pubblicata(project))
        if hasattr(project, "setPresetHomePath"):
            project.setPresetHomePath(dest)
        if not project.write(qgz):
            raise RuntimeError("QGIS ha rifiutato la scrittura di %s" % qgz)
    finally:
        ripristina_layer(stati_layer)
        ripristina_svg(toccati_svg)
        ripristina_gpkg(toccati_gpkg)
        ripristina_progetto(project, prima)

    return {"qgz": qgz, "gpkg": gpkg_dst, "n_font": n_font, "n_svg": n_svg,
            "n_layer": len(stati_layer),
            "n_privati": sum(1 for s in stati_layer if e_privato(s["layer"]))}


# --- IL SECONDO PARERE: SI GUARDA IL FILE SCRITTO ------------------------

_RE_DATASOURCE = re.compile(r"<datasource>(.*?)</datasource>", re.DOTALL)
# datasource e provider, nell'ordine in cui QGIS li scrive dentro <maplayer>.
_RE_LAYER = re.compile(
    r"<datasource>(.*?)</datasource>.*?<provider[^>]*>(.*?)</provider>",
    re.DOTALL)
PROVIDER_DI_FILE = ("ogr", "gdal")
_RE_SVG = re.compile(r'value="([^"]*\.svg)"', re.IGNORECASE)
_RE_FONT = re.compile(r'(?:fontFamily|name="font" type="QString" value)="([^"]+)"')
_RE_PRIVATO = re.compile(r"<Private>(\d)</Private>")


def _e_assoluto(percorso):
    """Assoluto secondo QUALUNQUE dei due sistemi, non secondo quello su cui
    gira il controllo: un "C:\\..." non e' assoluto per os.path su Linux, ed e'
    esattamente il percorso che si vuole scoprire."""
    p = percorso.strip()
    if not p:
        return False
    if p.startswith(("/", "\\\\")):   # radice unix, oppure condivisione di rete
        return True
    return bool(re.match(r"^[A-Za-z]:[\\/]", p))


def leggi_qgs(percorso_qgz):
    """Il testo XML dentro un .qgz (che e' uno zip), oppure il .qgs cosi'
    com'e'."""
    if zipfile.is_zipfile(percorso_qgz):
        with zipfile.ZipFile(percorso_qgz) as z:
            nomi = [n for n in z.namelist() if n.lower().endswith(".qgs")]
            if not nomi:
                raise RuntimeError("nessun .qgs dentro %s" % percorso_qgz)
            return z.read(nomi[0]).decode("utf-8", "replace")
    with open(percorso_qgz, encoding="utf-8", errors="replace") as f:
        return f.read()


def verifica_consegna(cartella):
    """Apre il progetto scritto e controlla che sia davvero portabile.

    Ritorna (rilievi, dati). 'rilievi' vuoto significa che non e' rimasto un
    percorso assoluto, che ogni file nominato dal progetto esiste dentro la
    cartella e che le capabilities WMS ci sono. Non guarda gli oggetti in
    memoria: quelli li abbiamo appena impostati noi."""
    cartella = os.path.abspath(str(cartella))
    qgz = [os.path.join(cartella, f) for f in sorted(os.listdir(cartella))
           if f.lower().endswith((".qgz", ".qgs"))]
    if not qgz:
        return (["nessun progetto (.qgz) nella cartella %s" % cartella],
                {"qgz": None})
    xml = leggi_qgs(qgz[0])
    rilievi = []

    def controlla(percorsi, che_cosa):
        mancanti = 0
        for p in percorsi:
            base = p.split("|", 1)[0].strip()
            if not base:
                continue
            if _e_assoluto(base):
                rilievi.append("%s con percorso assoluto: %s" % (che_cosa, base))
                continue
            intero = os.path.normpath(os.path.join(cartella, base))
            # RELATIVO NON VUOL DIRE PORTATILE, e questo controllo lo mancava
            # finche' non ho provato a romperlo: un simbolo lasciato senza
            # rimappatura viene scritto come "../../../../Progetti/COGO/
            # tidashboard/symbols/...", che e' un percorso relativo regolare e
            # sul PC di chi consegna esiste pure - os.path.isfile diceva di si'
            # e il rilievo non compariva. Sul server quella cartella non c'e'.
            # Cio' che conta e' che il percorso RESTI DENTRO la cartella che si
            # copia, non che risolva qui.
            if os.path.normcase(intero) != os.path.normcase(cartella) and \
                    not os.path.normcase(intero).startswith(
                        os.path.normcase(cartella) + os.sep):
                rilievi.append("%s che esce dalla cartella di consegna: %s"
                               % (che_cosa, base))
                continue
            if not os.path.isfile(intero):
                rilievi.append("%s nominato dal progetto ma assente dalla "
                               "cartella: %s" % (che_cosa, base))
                mancanti += 1
        return mancanti

    # NON OGNI datasource E' UN PERCORSO. Il primo controllo li trattava tutti
    # come file e segnalava "assente dalla cartella" per un layer temporaneo,
    # la cui sorgente e' "Point?crs=EPSG:2056&field=...". Chi decide e' il
    # PROVIDER, che sta accanto nel progetto:
    #   ogr, gdal      -> e' un file, e deve stare dentro la cartella;
    #   memory         -> non e' un file e non esiste fuori da questa sessione:
    #                     sul server quel layer sarebbe vuoto, e va detto;
    #   wms, wfs, ...   -> vive sulla rete, sul server va benissimo.
    coppie = _RE_LAYER.findall(xml)
    datasource = [d for d, _p in coppie]
    controlla([d for d, p in coppie if p in PROVIDER_DI_FILE], "dato")
    for _d, p in coppie:
        if p == "memory":
            rilievi.append("layer temporaneo nel progetto: i suoi dati non "
                           "esistono fuori da questa sessione e sul server "
                           "sarebbe vuoto")
            break
    svg = sorted(set(_RE_SVG.findall(xml)))
    controlla(svg, "simbolo SVG")

    if "<Private>" not in xml:
        rilievi.append("nessun flag Private nel progetto: i temi che il "
                       "cap. 1.5.3 non rappresenta finirebbero nel WMS")
    if "WMSServiceCapabilities" not in xml:
        rilievi.append("manca WMSServiceCapabilities: il GetCapabilities esce "
                       "quasi vuoto e il client non carica i layer")
    if CRS_MU not in xml:
        rilievi.append("il progetto non nomina %s" % CRS_MU)

    famiglie = sorted({f for f in _RE_FONT.findall(xml) if f})
    cartella_font = os.path.join(cartella, "fonts")
    ttf = sorted(os.listdir(cartella_font)) if os.path.isdir(cartella_font) else []
    for nome in FONT_DA_COPIARE:
        if nome not in ttf:
            rilievi.append("font non consegnato: %s" % nome)

    dati = {"qgz": qgz[0], "n_datasource": len(datasource), "n_svg": len(svg),
            "n_privati": sum(1 for v in _RE_PRIVATO.findall(xml) if v == "1"),
            "font_usati": famiglie, "ttf_consegnati": len(ttf)}
    return (rilievi, dati)
