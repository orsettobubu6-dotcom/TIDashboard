# TIDashboard - dati della misurazione ufficiale svizzera in QGIS
# Copyright (C) 2026 Gabriele Peverelli
#
# Questo programma e' software libero: lo si puo' ridistribuire e modificare
# secondo i termini della GNU General Public License pubblicata dalla Free
# Software Foundation, versione 2 o (a scelta) una successiva. Il testo si
# trova nel file LICENSE distribuito insieme al programma.

import os
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QFileDialog,
    QTextEdit, QLabel, QGroupBox, QMessageBox, QAction, QCheckBox, QGridLayout,
    QComboBox, QDoubleSpinBox, QDateEdit, QTabWidget, QProgressBar, QWidget,
    QSlider, QTableWidget, QTableWidgetItem, QAbstractItemView, QListWidget,
    QListWidgetItem, QApplication
)
from qgis.PyQt.QtCore import (QThread, pyqtSignal, QPointF, QRectF, QDate,
                              QTimer, Qt)
from qgis.PyQt.QtGui import (QIcon, QColor, QFont, QTextCursor, QPalette,
                             QTextCharFormat, QCursor)
from qgis.gui import QgsMapTool
# NB: le classi di simbologia (QgsSimpleFillSymbolLayer, QgsFontMarkerSymbolLayer,
# QgsFillSymbol, ...) non compaiono piu' qui: sono passate a simbologia.py e a
# stili.py insieme al codice che le usa.
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsMessageLog, Qgis, QgsDataSourceUri, QgsFeature,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsRelation,
    QgsVectorLayerJoinInfo,
    QgsPrintLayout, QgsLayoutItemLabel, QgsLayoutItemScaleBar, QgsLayoutItemMap,
    QgsLayoutExporter, QgsLayerTreeGroup, QgsRectangle,
    QgsPalLayerSettings, QgsTextFormat, QgsVectorLayerSimpleLabeling, QgsProperty,
    QgsUnitTypes, QgsGeometry, QgsWkbTypes, QgsSettings, QgsPointXY,
    QgsMapLayerLegendUtils
)
# NB: niente import di iface da qgis.utils a livello di modulo: renderebbe il
# modulo non importabile fuori da QGIS (es. test headless) e dipendente da un
# singleton globale. L'iface viene passato dal plugin al costruttore della
# dialog (parametro opzionale iface=None, salvato come self._iface).

try:
    from . import planimetria as _planimetria
    from . import cerca_fondo as _cerca_fondo
    from . import dati_comune as _dati_comune
    from . import inventario as _inventario
    from . import scarica_mu as _scarica_mu
    from . import modello as _modello
    from . import verifica_dxf as _verifica_dxf
    from . import java_env as _java_env
    from . import coordinate as _coordinate
    from . import pubblica_progetto as _pubblica
    from . import simbologia as _simbologia
    from .stili import StiliMixin
    from .legend_manifest import write_legend_manifest
    from .colori import *          # noqa: F401,F403 - costanti C_*
    from .etichette import *       # noqa: F401,F403 - regole di etichettatura
    from .ordinamento import *     # noqa: F401,F403 - ordine z e gruppi
    from .simbologia import *      # noqa: F401,F403 - costruttori di simboli
    from .etichette import (KEYWORD_LOCALITA, TESTO_SOLO_SU_POS,
                            _LABEL_DISABLED_BY_DEFAULT,
                            _LABEL_LAYER_OFF_BY_DEFAULT,
                            _LABEL_PRIORITY, _LABEL_PRIORITY_DEFAULT,
                            _POS_LEFT_BOTTOM_KEYWORDS, _POS_STILE_KEYWORDS,
                            campo_di_iscrizione, e_tabella_pos,
                            iscrizione_localita)
    from .ordinamento import (CAMPO_ORI_SIMBOLO, PREFISSO_SIMBOLO,
                              _raw_table_name, _rf_group_debug_info,
                              _rf_group_for_table, _zorder_debug_info,
                              _zorder_priority)
    from .simbologia import (_CAP_HEIGHT_RATIO, _ensure_cadastra_text_font_loaded,
                             _font_marker_offset, _font_size_for_cap,
                             _svg_symbol_path)
except ImportError:
    # test_style_logic.py importa questo modulo come top-level (non come
    # pacchetto), quindi l'import relativo fallisce li' - fallback assoluto.
    import planimetria as _planimetria
    import cerca_fondo as _cerca_fondo
    import dati_comune as _dati_comune
    import inventario as _inventario
    import scarica_mu as _scarica_mu
    import modello as _modello
    import verifica_dxf as _verifica_dxf
    import java_env as _java_env
    import coordinate as _coordinate
    import pubblica_progetto as _pubblica
    import simbologia as _simbologia
    from stili import StiliMixin
    from legend_manifest import write_legend_manifest
    from colori import *           # noqa: F401,F403
    from etichette import *        # noqa: F401,F403
    from ordinamento import *      # noqa: F401,F403
    from simbologia import *       # noqa: F401,F403
    from etichette import (KEYWORD_LOCALITA, TESTO_SOLO_SU_POS,
                           _LABEL_DISABLED_BY_DEFAULT,
                           _LABEL_LAYER_OFF_BY_DEFAULT,
                           _LABEL_PRIORITY, _LABEL_PRIORITY_DEFAULT,
                           _POS_LEFT_BOTTOM_KEYWORDS, _POS_STILE_KEYWORDS,
                           campo_di_iscrizione, e_tabella_pos,
                           iscrizione_localita)
    from ordinamento import (CAMPO_ORI_SIMBOLO, PREFISSO_SIMBOLO,
                             _raw_table_name, _rf_group_debug_info,
                             _rf_group_for_table, _zorder_debug_info,
                             _zorder_priority)
    from simbologia import (_CAP_HEIGHT_RATIO, _ensure_cadastra_text_font_loaded,
                            _font_marker_offset, _font_size_for_cap,
                            _svg_symbol_path)

# NB: gli import con * qui sopra non sono pigrizia - RI-ESPORTANO i nomi
# spostati nei nuovi moduli, cosi' chi importa questo modulo (i test, il resto
# del plugin) continua a trovarli dove li ha sempre trovati. Senza,
# spacchettare il file avrebbe rotto ogni riferimento esterno.

# Cartella con il set ufficiale di simboli Cadastra Symbol SVG 2024 (e la
# variante "mask" per l'alone bianco), fornita dall'utente e copiata dentro
# il plugin per non dipendere da un percorso specifico della macchina. Sostituisce
# il font "CadastraSymbol"/"CadastraSymbol Mask": niente piu' dipendenza da
# un font installato in QGIS con nome famiglia esatto, ne' da assunzioni sulla
# mappatura tasto->glifo del font (che non e' verificabile senza aprirlo).
# PyQt6 (QGIS 4): gli enum delle classi Qt vanno referenziati nella forma
# annidata Classe.EnumType.Valore. La forma piatta (_MB_SI) solleva
# AttributeError - e le finestre di conferma che la usavano fallivano invece
# di chiedere conferma.
_MB_SI = QMessageBox.StandardButton.Yes
_MB_NO = QMessageBox.StandardButton.No

SYMBOLS_DIR = _simbologia.SYMBOLS_DIR

# av2geobau_ti.jar: fork di av2geobau (https://github.com/claeis/av2geobau)
# con Av2geobau.java/Mapper.java estesi per leggere MD01MUTI7MN95 direttamente
# (nessuna finta "TRANSLATION OF" verso il modello tedesco, che fallirebbe per
# le divergenze strutturali reali - vedi Materiale/Genere_CS/Genere_OS
# gerarchici). Il jar richiede la sua cartella "libs" accanto a se' (i
# riferimenti nel MANIFEST.MF sono relativi alla posizione del jar).
AV2GEOBAU_JAR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "av2geobau", "av2geobau_ti.jar")

# Nome ufficiale del plugin, quello con cui viene pubblicato.
NOME_PLUGIN = "TIDashboard"

# Modello INTERLIS in dotazione. TIDashboard e' scritto per QUESTO modello: i
# nomi di tabella, gli enumerati e le regole di simbologia sono i suoi. Un .ili
# diverso (o una revisione diversa) produrrebbe silenziosamente un risultato
# sbagliato, percio' non si sceglie - come per il traduttore DXF.
MODELLO_ILI = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "models", "MD01MUTI7MN95.ili")


def _versione_dichiarata():
    """La versione LETTA da metadata.txt, non ricopiata a mano.

    Il titolo della finestra annunciava "v2.0" mentre metadata.txt diceva
    1.1.1: due numeri diversi per lo stesso plugin. Leggendola da li' non
    possono piu' divergere."""
    percorso = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.txt")
    try:
        with open(percorso, encoding="utf-8") as f:
            for riga in f:
                if riga.startswith("version="):
                    return riga.split("=", 1)[1].strip()
    except OSError:
        pass
    return "?"





def _looks_like_gpkg(path):
    """Verifica che un file sia davvero (con ogni probabilita') un GeoPackage
    prima di sovrascriverlo/cancellarlo: richiede SIA l'estensione ".gpkg"
    (case-insensitive) SIA l'header magico SQLite ("SQLite format 3\\0") nei
    primi 100 byte del file - un GeoPackage e' per definizione un database
    SQLite (GPKG 1.0, Requirement 1). Helper puro (nessuna dipendenza da QGIS),
    pensato per essere testabile fuori da QGIS. Usato in run_import: un
    percorso sbagliato digitato nel campo "Output GPKG" (es. un file .gpkg
    mancante creato da un altro programma, o un file rinominato) non deve
    essere cancellato al posto di un vecchio output del plugin."""
    try:
        p = Path(path)
        if p.suffix.lower() != ".gpkg":
            return False
        with open(p, "rb") as f:
            header = f.read(100)
        return header.startswith(b"SQLite format 3\x00")
    except OSError:
        return False


# ==================================================================================================================
class JavaWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int, str)

    def __init__(self, command, task_type, parent=None):
        # Il PADRE Qt e' quello che impedisce a PyQt di distruggere il thread
        # quando l'attributo che lo teneva viene riassegnato al lavoro
        # successivo: senza, Qt chiama abort() su un thread in corso e QGIS si
        # chiude. Stessa correzione gia' fatta su InventarioWorker.
        super().__init__(parent)
        self.command = command
        self.task_type = task_type
        # Riferimento al Popen in corso, per poterlo terminare da fuori il
        # thread (vedi cancel() / closeEvent della dialog).
        self._proc = None
        # cancel() puo' arrivare PRIMA che run() abbia fatto Popen: chiudendo
        # la finestra subito dopo l'avvio, _proc e' ancora None e il processo
        # java resterebbe in giro. Il flag lo fa terminare appena esiste.
        self._annullato = False

    def run(self):
        try:
            # CREATE_NO_WINDOW su Windows: senza questo flag ogni lancio di
            # java apre una finestra console nera sopra QGIS (stesso flag gia'
            # usato da _probe_java_version). Fuori Windows il flag non esiste:
            # si passa 0 (nessun flag).
            self._proc = subprocess.Popen(
                self.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace', bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            if self._annullato:
                self._proc.terminate()
            with self._proc as process:
                for line in process.stdout:
                    if line:
                        self.log_signal.emit(line.strip())
            self.finished_signal.emit(process.returncode, self.task_type)
        except Exception as e:
            self.log_signal.emit(f"❌ ERRORE CRITICO: {str(e)}")
            self.finished_signal.emit(-1, self.task_type)

    def cancel(self):
        """Termina il processo Java in corso, se ancora attivo (chiamato dalla
        dialog alla chiusura della finestra). terminate() chiude lo stdout del
        processo: il ciclo di lettura in run() finisce da solo e il thread
        termina regolarmente (poi il chiamante fa wait() per sincronizzarsi)."""
        self._annullato = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.terminate()

# ==================================================================================================================
# 4. DASHBOARD UI
# ==================================================================================================================
# Stile dei pulsanti di avvio. Il colore di fondo e' il segnaposto %s; il ramo
# :disabled serve perche' i pulsanti ora si spengono da soli finche' i campi
# non sono a posto, e uno stile a colore fisso non lo farebbe vedere.
_STILE_PULSANTE = (
    "QPushButton { background-color: %s; color: white; font-weight: bold; "
    "padding: 10px; border-radius: 4px; }"
    "QPushButton:disabled { background-color: #757575; color: #E0E0E0; }"
)


def _vivo(oggetto):
    """L'oggetto Qt esiste ancora, o e' solo un guscio Python?

    Con parent Qt e deleteLater il C++ puo' sparire mentre l'attributo Python
    che lo teneva resta: da quel momento QUALSIASI chiamata su quel guscio
    solleva RuntimeError. sip.isdeleted lo dice senza toccarlo; se sip non e'
    disponibile si ripiega su una chiamata innocua dentro un try."""
    if oggetto is None:
        return False
    # In PyQt6 sip sta sotto il pacchetto (PyQt6.sip), non piu' al primo
    # livello: cercarlo solo come "sip" fallisce in silenzio e si finirebbe
    # sempre sul ripiego.
    for modulo in ("PyQt6.sip", "PyQt5.sip", "sip"):
        try:
            sip = __import__(modulo, fromlist=["isdeleted"])
            return not sip.isdeleted(oggetto)
        except (ImportError, AttributeError):
            continue
    try:
        oggetto.objectName()
        return True
    except RuntimeError:
        return False


class InventarioWorker(QThread):
    """Conta cosa c'e' nell'ITF senza bloccare la finestra.

    Misurato sul comune di prova: 2.5 secondi per 733 527 oggetti. Poco per
    un'attesa, troppo per farlo nel thread dell'interfaccia mentre l'utente
    sta ancora scegliendo i file - la finestra resterebbe ferma proprio
    mentre ci si clicca dentro."""

    fatto = pyqtSignal(object, object, str)      # classi, totale, errore

    def __init__(self, percorso, parent=None):
        # Il PADRE non e' un dettaglio: con un padre Qt la proprieta'
        # dell'oggetto passa a Qt, e perdere il riferimento Python non lo
        # distrugge piu'. Senza, PyQt lo raccoglie mentre gira e il processo
        # muore con codice 127 (verificato). E' quello che rende inutile
        # tenersi una lista di thread vivi.
        super().__init__(parent)
        self._percorso = percorso

    def run(self):
        try:
            classi, totale = _inventario.leggi_inventario(self._percorso)
        except Exception as e:                   # anche gli errori GDAL nativi
            self.fatto.emit(None, None, str(e))
            return
        self.fatto.emit(classi, totale, "")


class VerificaDxfWorker(QThread):
    """Rilegge il DXF appena prodotto con GDAL, in un thread.

    Misurato sul DXF di Mendrisio, 209 MB: 13 secondi. Poco rispetto ai minuti
    della conversione, troppo per farlo nel thread dell'interfaccia - la
    finestra resterebbe ferma proprio mentre mostra l'esito."""

    fatto = pyqtSignal(object, str)             # esito, errore

    def __init__(self, percorso, parent=None):
        super().__init__(parent)
        self._percorso = percorso

    def run(self):
        try:
            self.fatto.emit(_verifica_dxf.verifica(self._percorso), "")
        except Exception as e:                  # anche gli errori nativi di GDAL
            self.fatto.emit(None, str(e))


class IndiceMuWorker(QThread):
    """Legge l'elenco dei comuni dal portale cantonale.

    Sta su un thread perche' e' una chiamata di rete: su una linea lenta, o con
    il portale giu', la finestra resterebbe congelata fino al timeout (30 s)."""

    fatto = pyqtSignal(object, str)              # elenco, errore

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            self.fatto.emit(_scarica_mu.scarica_indice(), "")
        except Exception as e:
            self.fatto.emit(None, str(e))


class ScaricaMuWorker(QThread):
    """Scarica l'archivio di un comune, lo estrae e ne verifica l'impronta."""

    avanzamento = pyqtSignal(int, int)           # byte fatti, byte totali
    fatto = pyqtSignal(str, str)                 # percorso itf, errore

    def __init__(self, comune, cartella, parent=None):
        super().__init__(parent)
        self._comune = comune
        self._cartella = cartella
        self._annullato = False

    def annulla(self):
        self._annullato = True

    def run(self):
        percorso_zip = None
        try:
            percorso_zip = _scarica_mu.scarica_archivio(
                self._comune, self._cartella,
                progresso=lambda f, t: self.avanzamento.emit(f, t),
                annullato=lambda: self._annullato)
            itf = _scarica_mu.estrai_itf(percorso_zip, self._cartella)
        except _scarica_mu.InterruttoDallUtente:
            self.fatto.emit("", "")              # annullato: nessun errore da mostrare
            return
        except Exception as e:
            self.fatto.emit("", str(e))
            return
        finally:
            # L'archivio ha gia' dato quel che doveva: tenerlo raddoppia lo
            # spazio occupato (Bellinzona: 31 MB di zip per 130 MB di ITF).
            if percorso_zip and os.path.exists(percorso_zip):
                try:
                    os.remove(percorso_zip)
                except OSError:
                    pass
        self.fatto.emit(itf, "")


class DialogScaricaMU(QDialog):
    """Scelta del comune e scaricamento dell'ITF dal portale cantonale.

    L'elenco arriva dal portale a ogni apertura invece di stare scritto qui:
    le date di aggiornamento cambiano di continuo (meta' dei comuni entro il
    mese) ed e' proprio quella l'informazione che serve per decidere se
    riscaricare. Un elenco fisso nel codice direbbe solo i nomi, che si sanno
    gia'."""

    def __init__(self, parent=None, cartella=None, avvia_indice=True):
        super().__init__(parent)
        self.setWindowTitle("Scarica dati MU dal Cantone")
        self.resize(560, 520)
        self.percorso_itf = ""
        self._comuni = []
        self._indice = None
        self._scarico = None
        # I thread NON hanno per padre questa finestra ma quella che la apre:
        # devono poterle sopravvivere. Chiudere mentre la rete e' ancora in
        # corso distruggerebbe il padre di un QThread vivo, che e' il modo
        # classico di far morire il processo. Con il padre piu' in alto, Qt
        # scollega da solo i segnali diretti a questa finestra quando sparisce.
        self._padrone = parent if parent is not None else self

        colonna = QVBoxLayout()
        intro = QLabel(
            "Misurazione ufficiale del Cantone Ticino, modello cantonale "
            "<b>%s</b>.<br>Fonte: <a href=\"%s\">data.geo.ti.ch</a> — "
            "<a href=\"%s\">condizioni di utilizzo</a>."
            % (_scarica_mu.MODELLO_ATTESO, _scarica_mu.URL_INDICE,
               _scarica_mu.URL_CONDIZIONI))
        intro.setOpenExternalLinks(True)
        intro.setWordWrap(True)
        colonna.addWidget(intro)

        self.txt_filtro = QLineEdit()
        self.txt_filtro.setPlaceholderText("Filtra per nome o numero...")
        self.txt_filtro.textChanged.connect(self._filtra)
        colonna.addWidget(self.txt_filtro)

        self.elenco = QListWidget()
        self.elenco.itemSelectionChanged.connect(self._aggiorna_pulsanti)
        self.elenco.itemDoubleClicked.connect(self._scarica)
        colonna.addWidget(self.elenco, 1)

        riga_cartella = QHBoxLayout()
        riga_cartella.addWidget(QLabel("Salva in:"))
        self.txt_cartella = QLineEdit(cartella or "")
        riga_cartella.addWidget(self.txt_cartella)
        btn_sfoglia = QPushButton("Sfoglia...")
        btn_sfoglia.clicked.connect(self._scegli_cartella)
        riga_cartella.addWidget(btn_sfoglia)
        colonna.addLayout(riga_cartella)

        self.barra = QProgressBar()
        self.barra.setVisible(False)
        colonna.addWidget(self.barra)

        self.lbl_stato = QLabel("Leggo l'elenco dei comuni...")
        self.lbl_stato.setWordWrap(True)
        colonna.addWidget(self.lbl_stato)

        riga_pulsanti = QHBoxLayout()
        riga_pulsanti.addStretch()
        self.btn_scarica = QPushButton("Scarica")
        self.btn_scarica.setEnabled(False)
        self.btn_scarica.clicked.connect(self._scarica)
        riga_pulsanti.addWidget(self.btn_scarica)
        self.btn_chiudi = QPushButton("Chiudi")
        self.btn_chiudi.clicked.connect(self.reject)
        riga_pulsanti.addWidget(self.btn_chiudi)
        colonna.addLayout(riga_pulsanti)
        self.setLayout(colonna)

        if avvia_indice:
            self._indice = IndiceMuWorker(self._padrone)
            self._indice.fatto.connect(self._indice_pronto)
            self._indice.finished.connect(self._indice.deleteLater)
            self._indice.start()

    # --- elenco --------------------------------------------------------------
    def _indice_pronto(self, comuni, errore):
        if errore or not comuni:
            self.lbl_stato.setText(
                "Non riesco a leggere l'elenco dal portale: %s\n"
                "Puoi scaricare a mano da %s"
                % (errore or "nessun comune trovato", _scarica_mu.URL_INDICE))
            return
        self._comuni = comuni
        self.lbl_stato.setText("%d comuni disponibili. Scegline uno."
                               % len(comuni))
        self._filtra()

    def _filtra(self):
        cercato = self.txt_filtro.text().strip().lower()
        self.elenco.clear()
        for c in self._comuni:
            if cercato and cercato not in c.nome.lower() and cercato not in c.codice:
                continue
            voce = QListWidgetItem("%s  —  %s  —  %s"
                                   % (c.nome, c.data, c.dimensione))
            voce.setData(Qt.ItemDataRole.UserRole, c)
            voce.setToolTip("%s\naggiornato il %s\n%s"
                            % (c.archivio, c.data, c.url))
            self.elenco.addItem(voce)
        self._aggiorna_pulsanti()

    def _comune_scelto(self):
        voce = self.elenco.currentItem()
        return voce.data(Qt.ItemDataRole.UserRole) if voce else None

    def _aggiorna_pulsanti(self):
        in_corso = _vivo(self._scarico) and self._scarico.isRunning()
        self.btn_scarica.setEnabled(bool(self._comune_scelto()) and not in_corso)

    def _scegli_cartella(self):
        cartella = QFileDialog.getExistingDirectory(
            self, "Dove salvare l'ITF", self.txt_cartella.text().strip())
        if cartella:
            self.txt_cartella.setText(cartella)

    # --- scaricamento --------------------------------------------------------
    def _scarica(self):
        comune = self._comune_scelto()
        if comune is None:
            return
        cartella = self.txt_cartella.text().strip()
        if not os.path.isdir(cartella):
            QMessageBox.warning(self, "Scarica dati MU",
                                "La cartella di destinazione non esiste:\n%s"
                                % (cartella or "(vuota)"))
            return
        self.barra.setVisible(True)
        self.barra.setValue(0)
        self.lbl_stato.setText("Scarico %s (%s)..." % (comune.nome, comune.dimensione))
        self._scarico = ScaricaMuWorker(comune, cartella, self._padrone)
        self._scarico.avanzamento.connect(self._avanza)
        self._scarico.fatto.connect(self._scarico_finito)
        self._scarico.finished.connect(self._scarico.deleteLater)
        self._scarico.start()
        self._aggiorna_pulsanti()
        self.btn_chiudi.setText("Annulla")

    def _avanza(self, fatti, totali):
        if totali > 0:
            self.barra.setRange(0, totali)
            self.barra.setValue(fatti)
            self.barra.setFormat("%.1f di %.1f MB (%%p%%)"
                                 % (fatti / 1048576.0, totali / 1048576.0))
        else:
            # Senza Content-Length non c'e' una percentuale da mostrare: una
            # barra indeterminata dice "sto lavorando" senza mentire.
            self.barra.setRange(0, 0)
            self.barra.setFormat("%.1f MB" % (fatti / 1048576.0))

    def _scarico_finito(self, percorso, errore):
        self.barra.setVisible(False)
        self.btn_chiudi.setText("Chiudi")
        self._aggiorna_pulsanti()
        if errore:
            self.lbl_stato.setText("Non riuscito: %s" % errore)
            QMessageBox.warning(self, "Scarica dati MU", errore)
            return
        if not percorso:
            self.lbl_stato.setText("Annullato.")
            return
        esito, trovato = _modello.controlla_itf(percorso)
        messaggio = _modello.spiega(esito, trovato, "l'archivio scaricato")
        if messaggio:
            # Non e' un errore fatale - il file c'e' ed e' integro - ma la
            # catena a valle e' tarata su un modello solo, e scoprirlo qui
            # costa un avviso, scoprirlo dopo costa un'importazione fallita.
            QMessageBox.warning(self, "Scarica dati MU", messaggio)
        self.percorso_itf = percorso
        self.accept()

    def reject(self):
        if _vivo(self._scarico) and self._scarico.isRunning():
            self._scarico.annulla()
            self._scarico.wait(5000)
            return                          # il primo Annulla ferma, non chiude
        super().reject()

    def closeEvent(self, evento):
        """Chiudere con la X non deve lasciare un download a scrivere su un
        file di cui nessuno guarda piu' l'esito."""
        if _vivo(self._scarico) and self._scarico.isRunning():
            self._scarico.annulla()
            self._scarico.wait(5000)
        super().closeEvent(evento)


class StrumentoSpostaFoglio(QgsMapTool):
    """Prende il rettangolo del foglio e lo porta dove serve, o lo gira.

    Prima il foglio si inquadrava indirettamente: si spostava la MAPPA finche'
    il centro della vista non capitava dove serviva, e il rettangolo seguiva.
    Funziona, ma e' un movimento al contrario - si muove tutto per posizionare
    una cosa - e alle scale piccole basta un pixel di troppo per perdere
    l'inquadratura. Qui si afferra direttamente il rettangolo.

    TRE GESTI, e ciascuno risponde solo dove ha senso:
      - dentro il rettangolo, trascina: sposta il centro;
      - sulla MANIGLIA (meta' del lato superiore), trascina: ruota;
      - doppio clic dentro: la vista si porta sul foglio.

    Fuori dal rettangolo il tasto sinistro resta libero per la navigazione
    normale, cosi' lo strumento acceso non sequestra il canvas.
    """

    # Raggio di presa della maniglia, in PIXEL: la tolleranza deve essere
    # quella del dito sullo schermo, non una distanza sul terreno - a 1:10000
    # dieci metri sono un pixel, a 1:200 mezzo schermo.
    PRESA_PX = 14

    def __init__(self, canvas, dialogo):
        super().__init__(canvas)
        self._dialogo = dialogo
        self._scarto = None                  # click meno centro, per non far saltare il foglio
        self._ruotando = False
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

    def _centro_corrente(self):
        canvas = self.canvas()
        return (getattr(self._dialogo, "_centro_da_fondo", None)
                or canvas.extent().center())

    def _parametri(self):
        return self._dialogo._parametri_planimetria()

    def _impronta(self, centro):
        formato, scala, rotazione, _c, _d = self._parametri()
        return QgsGeometry.fromPolygonXY(
            [_planimetria.impronta_foglio(centro, scala, formato, rotazione)])

    def _maniglia(self, centro):
        formato, scala, rotazione, _c, _d = self._parametri()
        return _planimetria.maniglia_rotazione(centro, scala, formato, rotazione)

    def _sulla_maniglia(self, punto, centro):
        """La presa si misura in pixel e si converte in unita' di mappa: e'
        la tolleranza del dito, non una distanza sul terreno."""
        try:
            per_pixel = self.canvas().mapUnitsPerPixel()
        except Exception:
            return False
        maniglia = self._maniglia(centro)
        return (punto.distance(maniglia) <= self.PRESA_PX * per_pixel)

    def canvasPressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        punto = e.mapPoint()
        centro = self._centro_corrente()
        # La maniglia si prova PRIMA del rettangolo: sta sul bordo, e con un
        # foglio grande cade dentro l'impronta - controllando il rettangolo
        # per primo non si riuscirebbe mai ad afferrarla.
        if self._sulla_maniglia(punto, centro):
            self._ruotando = True
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return
        if not self._impronta(centro).contains(QgsGeometry.fromPointXY(punto)):
            return                            # fuori dal foglio: non e' roba nostra
        # Si tiene lo scarto fra dove hai cliccato e il centro: senza, al primo
        # movimento il foglio salterebbe centrandosi sotto il puntatore.
        self._scarto = (punto.x() - centro.x(), punto.y() - centro.y())
        self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def canvasMoveEvent(self, e):
        punto = e.mapPoint()
        if self._ruotando:
            self._dialogo.ruota_foglio_verso(punto, self._centro_corrente())
            return
        if self._scarto is None:
            return
        self._dialogo.sposta_foglio_a(
            QgsPointXY(punto.x() - self._scarto[0], punto.y() - self._scarto[1]))

    def canvasReleaseEvent(self, e):
        punto = e.mapPoint()
        if self._ruotando:
            self._ruotando = False
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            self._dialogo.ruota_foglio_verso(punto, self._centro_corrente(),
                                             definitivo=True)
            return
        if self._scarto is None:
            return
        nuovo = QgsPointXY(punto.x() - self._scarto[0], punto.y() - self._scarto[1])
        self._scarto = None
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        self._dialogo.sposta_foglio_a(nuovo, definitivo=True)

    def canvasDoubleClickEvent(self, e):
        """Doppio clic dentro il foglio: la vista si porta sull'impronta.

        Serve a controllare cosa verra' stampato senza cercare a mano lo zoom
        giusto. Non tocca il CENTRO del foglio: sposta la vista, non il
        foglio."""
        if e.button() != Qt.MouseButton.LeftButton:
            return
        centro = self._centro_corrente()
        impronta = self._impronta(centro)
        if not impronta.contains(QgsGeometry.fromPointXY(e.mapPoint())):
            return
        riquadro = impronta.boundingBox()
        riquadro.grow(max(riquadro.width(), riquadro.height()) * 0.05)
        self.canvas().setExtent(riquadro)
        self.canvas().refresh()

    def deactivate(self):
        self._scarto = None
        self._ruotando = False
        super().deactivate()


class TIDashboardDialog(StiliMixin, QDialog):
    def __init__(self, parent=None, iface=None):
        super().__init__(parent)
        self.setWindowTitle("%s %s" % (NOME_PLUGIN, _versione_dichiarata()))
        self.resize(900, 900)
        # iface di QGIS passato dal plugin (niente import globale da qgis.utils):
        # opzionale perche' i test istanziano la dialog con __new__ senza
        # __init__ - ogni uso deve quindi passare da getattr(self, "_iface", None).
        self._iface = iface
        self.worker = None
        self.loaded_layers = []
        self.product_mode = "gb"  # 'gb' o 'bp'
        self.plugin_dir = Path(__file__).parent
        self._java_path_cache = None  # vedi find_java(): None = mai cercato, "" = cercato e non trovato
        self._banda_ingombro = None
        # Righe di console conservate per intero: il filtro nasconde, non
        # butta via. Deve esistere PRIMA di init_ui, che gia' logga.
        self._righe_log = []
        self.init_ui()
        # L'ingombro e' centrato sulla vista corrente: deve seguire pan e zoom,
        # altrimenti resta indietro e mostra un'area che non e' piu' quella
        # che verrebbe stampata.
        if self._iface and self._iface.mapCanvas():
            self._iface.mapCanvas().extentsChanged.connect(self._aggiorna_ingombro)

    def init_ui(self):
        # Elenco dei campi-percorso da convalidare, riempito da
        # create_file_row: (QLineEdit, e_di_salvataggio, etichetta_stato, scheda)
        self._campi_percorso = []
        layout = QVBoxLayout()

        prod_layout = QHBoxLayout()
        prod_layout.addWidget(QLabel("Prodotto:"))
        self.combo_product = QComboBox()
        self.combo_product.addItem("Piano per il registro fondiario (GB)", "gb")
        self.combo_product.addItem("Piano di base (PB-MU)", "bp")
        self.combo_product.currentIndexChanged.connect(self.on_product_changed)
        prod_layout.addWidget(self.combo_product)
        prod_layout.addStretch()
        layout.addLayout(prod_layout)

        # Le tre fasi stanno su SCHEDE, non piu' impilate in una colonna sola:
        # in colonna, su uno schermo da portatile, la console si riduceva a due
        # righe e la sezione planimetria finiva sotto il bordo della finestra
        # (nessuna QScrollArea). Le schede danno a ogni fase l'altezza piena e
        # lasciano la console sempre visibile sotto.
        self.schede = QTabWidget()

        # --- 0. Ambiente --------------------------------------------------
        # Prima di questa scheda l'utente doveva indovinare da solo che serve
        # Java, che ili2gpkg e' un jar da procurarsi altrove, e in che ordine
        # fare le cose: se Java mancava se ne accorgeva a meta' importazione,
        # da un errore di processo. Qui si vede tutto prima di cominciare.
        # ili2gpkg sta QUI e non nella scheda 1 perche' e' configurazione -
        # si sceglie una volta e resta - non un dato del singolo lavoro.
        group_amb = QGroupBox("0. Ambiente (si configura una volta sola)")
        layout_amb = QVBoxLayout()

        self.txt_jar = QLineEdit()
        self.txt_jar.setPlaceholderText("Seleziona ili2gpkg-x.x.jar...")
        layout_amb.addLayout(self.create_file_row(
            "ili2gpkg JAR:", self.txt_jar, "JAR files (*.jar)", False, "import"))

        self._spie_ambiente = {}
        for chiave, etichetta in (("java", "Java"),
                                  ("ili2gpkg", "ili2gpkg"),
                                  ("av2geobau", "Traduttore DXF"),
                                  ("modello", "Modello INTERLIS")):
            layout_amb.addLayout(self._riga_ambiente(chiave, etichetta))

        self.btn_verifica = QPushButton("🔍 VERIFICA AMBIENTE")
        self.btn_verifica.setStyleSheet(_STILE_PULSANTE % "#455A64")
        self.btn_verifica.clicked.connect(self.verifica_ambiente)
        layout_amb.addWidget(self.btn_verifica)

        # Solo indirizzi di cui si conosce con certezza la destinazione: un
        # link inventato manda l'utente a cercare altrove il problema. I due
        # operativi sono stati indicati dall'utente e verificati:
        #  - interlis.ch/downloads/ili2db offre davvero ili2gpkg (insieme a
        #    ili2pg e ili2fgdb): e' la pagina ufficiale, non un mirror;
        #  - data.geo.ti.ch con questo parametro e' la misurazione ufficiale
        #    ticinese, scaricabile "in interlis 1 per i dati della misurazione
        #    ufficiale" - cioe' proprio l'ITF che serve qui. Il "7_mn95" nel
        #    parametro corrisponde al modello MD01MUTI7MN95 in dotazione.
        aiuto = QLabel(
            'Dove si trovano le cose:<br>'
            '• <b>File ITF</b> — è la consegna della misurazione ufficiale, non '
            'si produce con questo plugin. Per il Ticino: '
            '<a href="https://data.geo.ti.ch/?p=ti_mu_version1_7_mn95">'
            'data.geo.ti.ch</a> (scegliere <i>INTERLIS 1</i>, il formato dei '
            'dati della misurazione ufficiale).<br>'
            '• <b>ili2gpkg</b> — '
            '<a href="https://www.interlis.ch/downloads/ili2db">'
            'interlis.ch/downloads/ili2db</a> (nella pagina, la voce '
            '<i>ili2gpkg</i>: le altre due sono per PostgreSQL e FileGDB).<br>'
            '• <b>Java</b> — serve la versione 8 o superiore, si installa a parte; '
            'il plugin lo cerca da solo in PATH, JAVA_HOME e nelle cartelle dei '
            'principali fornitori.<br>'
            '• <b>Misurazione ufficiale svizzera</b> — '
            '<a href="https://www.cadastre.ch">cadastre.ch</a>')
        aiuto.setWordWrap(True)
        aiuto.setOpenExternalLinks(True)
        aiuto.setStyleSheet("color: #757575;")
        layout_amb.addWidget(aiuto)

        layout_amb.addStretch()
        group_amb.setLayout(layout_amb)
        self.pagina_ambiente = self._in_scheda(group_amb)
        self.schede.addTab(self.pagina_ambiente, "0. Ambiente")

        group_import = QGroupBox("1. Importazione Dati (ITF -> GeoPackage)")
        layout_import = QVBoxLayout()

        self.txt_itf = QLineEdit()
        self.txt_itf.setPlaceholderText("Seleziona il file dati .itf...")
        riga_itf = self.create_file_row("File ITF in:", self.txt_itf,
                                        "ITF files (*.itf)", False, "import")
        # Il dato ufficiale si scarica da qui, non a mano dal browser: il
        # portale cantonale pubblica un archivio per comune, e prenderlo dal
        # plugin evita sia di sbagliare comune sia di finire per errore sul
        # modello federale di geodienste.ch, che e' un modello diverso.
        self._btn_scarica_mu = QPushButton("⬇️ Cantone...")
        self._btn_scarica_mu.setToolTip(
            "Scarica l'ITF ufficiale di un comune da data.geo.ti.ch\n"
            "(modello cantonale %s)" % _scarica_mu.MODELLO_ATTESO)
        self._btn_scarica_mu.clicked.connect(self.scarica_itf_dal_cantone)
        riga_itf.addWidget(self._btn_scarica_mu)
        layout_import.addLayout(riga_itf)

        # Cosa c'e' dentro, prima di importare. Finora per saperlo bisognava
        # lanciare l'importazione - minuti - e se si fermava a meta' restavi
        # senza risposta proprio quando serviva.
        self.lbl_inventario = QLabel()
        self.lbl_inventario.setWordWrap(True)
        self.lbl_inventario.setStyleSheet("color: #9E9E9E;")
        self.lbl_inventario.setVisible(False)
        layout_import.addWidget(self.lbl_inventario)

        # Modello INTERLIS in dotazione: vedi MODELLO_ILI. Stessa scelta del
        # traduttore DXF - visibile, cosi' si sa su quale modello si sta
        # lavorando, ma non sostituibile.
        self.txt_ili = QLineEdit()
        self.txt_ili.setReadOnly(True)
        self.txt_ili.setText(MODELLO_ILI)
        self.txt_ili.setToolTip("Modello in dotazione al plugin, non sostituibile")
        layout_import.addLayout(
            self._riga_in_dotazione("Modello .ili:", self.txt_ili, "stato_ili"))

        self.txt_gpkg = QLineEdit()
        self.txt_gpkg.setPlaceholderText("Definisci output GeoPackage...")
        layout_import.addLayout(self.create_file_row("Output GPKG:", self.txt_gpkg, "GeoPackage (*.gpkg)", True, "import"))

        group_adv = QGroupBox("Opzioni Tolleranza Errori (Per dati sporchi)")
        group_adv.setCheckable(True)
        group_adv.setChecked(True)
        layout_adv = QGridLayout()
        # Etichette in italiano, flag di ili2gpkg nel tooltip: i nomi grezzi
        # ("--skipPolygonBuilding") dicono qualcosa solo a chi conosce gia'
        # ili2gpkg, e queste opzioni cambiano cosa finisce nel GeoPackage.
        self.chk_disable_val = self._casella_tolleranza(
            "Non validare i dati", "--disableValidation",
            "Salta del tutto il controllo di conformita' al modello. "
            "Ultima risorsa: passa anche cio' che e' sbagliato.")
        self.chk_skip_geom = self._casella_tolleranza(
            "Ignora errori di geometria", "--skipGeometryErrors",
            "Le geometrie non valide non bloccano l'importazione: gli oggetti "
            "interessati vengono saltati.")
        self.chk_skip_ref = self._casella_tolleranza(
            "Ignora riferimenti mancanti", "--skipReferenceErrors",
            "Accetta i rimandi a oggetti assenti (relazioni interrotte).")
        self.chk_skip_poly = self._casella_tolleranza(
            "Non costruire i poligoni", "--skipPolygonBuilding",
            "Non ricompone le superfici dai contorni: restano solo le linee. "
            "Utile quando i contorni non chiudono.")
        self.chk_sql_null = self._casella_tolleranza(
            "Ammetti valori nulli", "--sqlEnableNull",
            "Le colonne obbligatorie diventano facoltative nel GeoPackage.")
        self.chk_sql_text = self._casella_tolleranza(
            "Tutte le colonne come testo", "--sqlColsAsText",
            "Nessuna conversione di tipo: numeri e date restano testo.")
        layout_adv.addWidget(self.chk_disable_val, 0, 0)
        layout_adv.addWidget(self.chk_skip_geom, 0, 1)
        layout_adv.addWidget(self.chk_skip_ref, 1, 0)
        layout_adv.addWidget(self.chk_skip_poly, 1, 1)
        layout_adv.addWidget(self.chk_sql_null, 2, 0)
        layout_adv.addWidget(self.chk_sql_text, 2, 1)
        group_adv.setLayout(layout_adv)
        self.group_adv = group_adv
        layout_import.addWidget(group_adv)

        self.btn_import = QPushButton("▶ ELABORA IMPORTAZIONE INTERLIS")
        # Le regole vanno scritte con il selettore QPushButton e non come
        # dichiarazioni nude: senza il ramo :disabled il pulsante restava
        # verde acceso anche da spento, quindi sembrava premibile.
        self.btn_import.setStyleSheet(_STILE_PULSANTE % "#2E7D32")
        self.btn_import.clicked.connect(self.run_import)
        layout_import.addWidget(self.btn_import)
        self.lbl_esito_import = QLabel()
        self.lbl_esito_import.setStyleSheet("color: %s;" % self._rosso_avviso())
        layout_import.addWidget(self.lbl_esito_import)

        # Sempre presente, non piu' setVisible: comparendo e sparendo al
        # cambio di prodotto faceva saltare tutto il resto della scheda, e
        # sparire un comando non spiega perche' non e' disponibile. Ora resta
        # al suo posto, spento, con il motivo nel tooltip.
        self.btn_layout = QPushButton("📐 CREA LAYOUT PB-MU")
        self.btn_layout.setStyleSheet(_STILE_PULSANTE % "#1565C0")
        self.btn_layout.clicked.connect(self.create_layout_bp)
        layout_import.addWidget(self.btn_layout)
        self._aggiorna_pulsante_layout()

        # "Consegna", non "WebGIS": quello che esce di qui e' una cartella da
        # copiare su un server, non un sito. Il tooltip dice la cosa che ci si
        # dimentica sempre - che il server non esegue questo plugin.
        self.btn_consegna = QPushButton("🌐 CONSEGNA PER QGIS SERVER")
        self.btn_consegna.setStyleSheet(_STILE_PULSANTE % "#00695C")
        self.btn_consegna.clicked.connect(self.consegna_qgis_server)
        layout_import.addWidget(self.btn_consegna)
        self._aggiorna_pulsante_consegna()

        layout_import.addStretch()
        group_import.setLayout(layout_import)
        self.pagina_import = self._in_scheda(group_import)
        self.schede.addTab(self.pagina_import, "1. Importazione")

        group_geobau = QGroupBox("2. Conversione DXF (av2geobau)")
        layout_geobau = QVBoxLayout()
        # Il traduttore DXF e' quello IN DOTAZIONE al plugin: e' una versione
        # nostra, allineata al modello ticinese, e usarne un'altra produrrebbe
        # un DXF che non rispetta le convenzioni implementate qui. Il campo
        # resta VISIBILE, cosi' si vede qual e' il motore in uso, ma non si
        # sceglie: niente "Sfoglia...", sola lettura.
        self.txt_geobau_jar = QLineEdit()
        self.txt_geobau_jar.setReadOnly(True)
        self.txt_geobau_jar.setText(AV2GEOBAU_JAR)
        self.txt_geobau_jar.setToolTip(
            "Traduttore in dotazione al plugin, non sostituibile")
        layout_geobau.addLayout(
            self._riga_in_dotazione("Traduttore DXF:", self.txt_geobau_jar, "stato_jar"))
        # L'ITF era chiesto DUE volte, qui e nella scheda 1, gia' sincronizzati
        # fra loro: chi guardava vedeva due campi identici e non sapeva se
        # andassero compilati entrambi. Ora questo rispecchia quello
        # dell'importazione ed e' bloccato; si sblocca solo con la spunta, per
        # il caso reale ma raro di un DXF da un ITF diverso da quello importato.
        self.txt_geobau_itf = QLineEdit()
        self.txt_geobau_itf.setPlaceholderText("Come nella scheda \"1. Importazione\"")
        self.txt_geobau_itf.setReadOnly(True)
        riga_itf = self.create_file_row("File ITF in:", self.txt_geobau_itf,
                                        "ITF files (*.itf)", False, "dxf")
        layout_geobau.addLayout(riga_itf)
        self.chk_itf_diverso = QCheckBox(
            "Convertire un file ITF diverso da quello importato")
        self.chk_itf_diverso.toggled.connect(self._sblocca_itf_dxf)
        layout_geobau.addWidget(self.chk_itf_diverso)
        # Il pulsante "Sfoglia..." della riga e' l'ultimo widget aggiunto:
        # senza la spunta non ha nulla da fare.
        self._btn_sfoglia_itf_dxf = riga_itf.itemAt(riga_itf.count() - 1).widget()
        self._btn_sfoglia_itf_dxf.setEnabled(False)
        self.txt_geobau_dxf = QLineEdit()
        self.txt_geobau_dxf.setPlaceholderText("Salva il DXF come...")
        layout_geobau.addLayout(self.create_file_row("Output DXF:", self.txt_geobau_dxf, "DXF (*.dxf)", True, "dxf"))
        self.btn_geobau = QPushButton("▶ ESPORTAZIONE DXF")
        self.btn_geobau.setStyleSheet(_STILE_PULSANTE % "#1565C0")
        self.btn_geobau.clicked.connect(self.run_geobau)
        layout_geobau.addWidget(self.btn_geobau)
        self.lbl_esito_dxf = QLabel()
        self.lbl_esito_dxf.setStyleSheet("color: %s;" % self._rosso_avviso())
        layout_geobau.addWidget(self.lbl_esito_dxf)
        layout_geobau.addStretch()
        group_geobau.setLayout(layout_geobau)
        self.pagina_dxf = self._in_scheda(group_geobau)
        self.schede.addTab(self.pagina_dxf, "2. Conversione DXF")

        # --- 3. Planimetria -------------------------------------------------
        group_plan = QGroupBox("3. Planimetria (estratto stampabile)")
        layout_plan = QVBoxLayout()
        riga_plan = QHBoxLayout()

        riga_plan.addWidget(QLabel("Formato:"))
        self.combo_formato = QComboBox()
        self.combo_formato.addItems([n for n, _w, _h in _planimetria.FORMATI])
        riga_plan.addWidget(self.combo_formato)

        riga_plan.addWidget(QLabel("Scala:"))
        self.combo_scala = QComboBox()
        # Solo le scale del cap.1.5.1: l'elenco e' chiuso, quindi un menu a
        # tendina invece di un campo libero rende impossibile sbagliarla.
        self.combo_scala.addItems(["1:%d" % s for s in _planimetria.SCALE_UFFICIALI_MU])
        self.combo_scala.setCurrentText("1:1000")
        # activated, non currentIndexChanged: il primo scatta SOLO quando a
        # cambiare la voce e' l'utente. Serve a distinguere una scala scelta da
        # una scala di partenza, cosi' il cambio di prodotto puo' proporre la
        # scala di riferimento senza mai sovrascrivere una decisione presa.
        self.combo_scala.activated.connect(self._scala_scelta_dall_utente)
        riga_plan.addWidget(self.combo_scala)

        riga_plan.addWidget(QLabel("Rotazione (gon):"))
        self.spin_rotazione = QDoubleSpinBox()
        self.spin_rotazione.setRange(0.0, 400.0)
        self.spin_rotazione.setDecimals(1)
        self.spin_rotazione.setSingleStep(10.0)
        self.spin_rotazione.setToolTip("Rotazione della mappa attorno al centro del foglio, "
                                       "in gon (100 gon = 90 gradi)")
        riga_plan.addWidget(self.spin_rotazione)
        # I gradi accanto al valore: i gon sono l'unita' della misurazione
        # ufficiale, ma il riscontro visivo che tutti hanno e' in gradi.
        self.lbl_gradi = QLabel()
        self.lbl_gradi.setStyleSheet("color: #9E9E9E;")
        riga_plan.addWidget(self.lbl_gradi)
        layout_plan.addLayout(riga_plan)

        # Cursore e scatti rapidi: con il solo spin a passo 10 arrivare a 300
        # gon voleva dire trenta clic. Cursore e spin restano sincronizzati nei
        # due sensi; il cursore lavora in DECIMI di gon perche' QSlider e'
        # intero e lo spin ha un decimale.
        riga_rot = QHBoxLayout()
        self.slider_rotazione = QSlider(Qt.Orientation.Horizontal)
        self.slider_rotazione.setRange(0, 4000)
        self.slider_rotazione.setSingleStep(10)
        self.slider_rotazione.setPageStep(250)
        riga_rot.addWidget(self.slider_rotazione, 1)
        for gon in (0, 100, 200, 300):
            b = QPushButton("%d" % gon)
            b.setMaximumWidth(40)
            b.setToolTip("%d gon = %g°" % (gon, _planimetria.gon_a_gradi(gon)))
            b.clicked.connect(lambda _c=False, g=gon: self.spin_rotazione.setValue(float(g)))
            riga_rot.addWidget(b)
        layout_plan.addLayout(riga_rot)

        self.slider_rotazione.valueChanged.connect(
            lambda v: self.spin_rotazione.setValue(v / 10.0))
        self.spin_rotazione.valueChanged.connect(self._sync_rotazione)
        self._sync_rotazione(self.spin_rotazione.value())

        riga_plan2 = QHBoxLayout()
        riga_plan2.addWidget(QLabel("Comune:"))
        # Il comune si LEGGE dai dati INTERLIS (vedi dati_comune.py), non si
        # digita: e' un'iscrizione obbligatoria e il modello lo contiene gia'.
        # La casella resta scrivibile perche' una consegna puo' non portare
        # nessuna delle due fonti, e in quel caso e' meglio poterlo scrivere
        # che restare bloccati.
        self.combo_comune = QComboBox()
        self.combo_comune.setEditable(True)
        self.combo_comune.lineEdit().setPlaceholderText(
            "Letto dai dati INTERLIS dopo l'importazione")
        self.combo_comune.setToolTip(
            "Nomi trovati nei dati: Layout_del_piano.Nome_comune e "
            "Confini_comunali.Comune.Nome")
        riga_plan2.addWidget(self.combo_comune, 1)

        # "Stato al" e' la DATA DI VALIDITA' dei dati (iscrizione obbligatoria,
        # cap.1.5.7), non la data di stampa: un estratto prodotto oggi da dati
        # consegnati a marzo deve dichiarare marzo. Prima veniva scritta
        # d'ufficio la data odierna, cioe' un'attestazione falsa di attualita'.
        # Il valore iniziale resta oggi perche' e' il caso piu' frequente
        # (estratto da dati appena importati), ma ora e' modificabile.
        riga_plan2.addWidget(QLabel("Stato al:"))
        self.data_validita = QDateEdit()
        self.data_validita.setDisplayFormat("dd.MM.yyyy")
        self.data_validita.setCalendarPopup(True)
        self.data_validita.setDate(QDate.currentDate())
        self.data_validita.setToolTip(
            "Data riportata nel cartiglio (cap.1.5.7), non quella di stampa. "
            "Viene proposta la data di estrazione dell'ITF; se l'ITF non è "
            "disponibile, la mutazione più recente presente nei dati.")
        riga_plan2.addWidget(self.data_validita)
        layout_plan.addLayout(riga_plan2)

        # Da dove viene la data. "Stato al" e' un'iscrizione obbligatoria
        # (cap.1.5.7) e nessuna delle due fonti disponibili e' una data del
        # contenuto INTERLIS: l'ITF non ne porta nessuna e il timestamp del
        # file e' un dato del file system. Finora la fonte finiva solo in
        # console al momento dell'importazione, quindi chi apriva questa scheda
        # dopo vedeva una data e basta, senza sapere quanto fidarsene.
        self.lbl_origine_data = QLabel()
        self.lbl_origine_data.setWordWrap(True)
        layout_plan.addWidget(self.lbl_origine_data)
        self.data_validita.dateChanged.connect(self._aggiorna_origine_data)
        self._aggiorna_origine_data()

        # --- Cerca fondo ---------------------------------------------------
        # Trovare un fondo scorrendo la mappa e' impraticabile: un comune ne
        # ha migliaia. La ricerca sta qui, nella scheda della planimetria,
        # perche' e' li' che serve - si cerca un fondo per centrarci il foglio.
        gruppo_cerca = QGroupBox("Cerca fondo")
        layout_cerca = QVBoxLayout()

        riga_cerca = QHBoxLayout()
        riga_cerca.addWidget(QLabel("Numero:"))
        self.txt_fondo = QLineEdit()
        self.txt_fondo.setPlaceholderText("es. 452  oppure  452-01")
        self.txt_fondo.setToolTip(
            "Numero del fondo. Si può scrivere anche numero e sezione insieme "
            "(452-01, 452 / 01): la sezione viene riconosciuta da sola.")
        self.txt_fondo.returnPressed.connect(self.cerca_fondo)
        riga_cerca.addWidget(self.txt_fondo, 1)

        riga_cerca.addWidget(QLabel("Sezione:"))
        self.combo_sezione = QComboBox()
        self.combo_sezione.setToolTip(
            "Le sezioni presenti nei dati. «Tutte» lascia decidere dopo, "
            "guardando i risultati.")
        self.combo_sezione.setMinimumWidth(80)
        riga_cerca.addWidget(self.combo_sezione)

        riga_cerca.addWidget(QLabel("EGRID:"))
        self.txt_egrid = QLineEdit()
        self.txt_egrid.setPlaceholderText("facoltativo")
        self.txt_egrid.setMaximumWidth(140)
        self.txt_egrid.returnPressed.connect(self.cerca_fondo)
        riga_cerca.addWidget(self.txt_egrid)
        layout_cerca.addLayout(riga_cerca)

        riga_cerca2 = QHBoxLayout()
        self.chk_solo_in_vigore = QCheckBox("Solo fondi in vigore")
        self.chk_solo_in_vigore.setChecked(True)
        self.chk_solo_in_vigore.setToolTip(
            "Togliendo la spunta si includono anche i fondi contestati. "
            "Gli oggetti in progetto restano sempre esclusi: non sono fondi "
            "esistenti e il piano non li rappresenta (cap. 1.5.3).")
        riga_cerca2.addWidget(self.chk_solo_in_vigore)
        self.btn_cerca_fondo = QPushButton("🔎 CERCA")
        self.btn_cerca_fondo.clicked.connect(self.cerca_fondo)
        riga_cerca2.addWidget(self.btn_cerca_fondo)
        layout_cerca.addLayout(riga_cerca2)

        # Centro per coordinate: chi ha gia' il punto non deve passare da un
        # fondo. Riconosce MN95, le vecchie MN03 e i gradi WGS84 dall'ordine
        # di grandezza - vedi coordinate.analizza.
        riga_coord = QHBoxLayout()
        riga_coord.addWidget(QLabel("Coordinate:"))
        self.txt_coordinate = QLineEdit()
        self.txt_coordinate.setPlaceholderText(
            "es. 2718000 1082000  ·  718000 82000 (MN03)  ·  45.87 8.98 (WGS84)")
        self.txt_coordinate.setToolTip(
            "Due numeri separati da virgola o spazio. Il sistema si riconosce "
            "dall'ordine di grandezza: non c'e' niente da dichiarare.\n"
            "I GON non si accettano: sono un'unita' angolare e nel piano "
            "servono per la rotazione del foglio, non per una posizione.")
        self.txt_coordinate.returnPressed.connect(self.centra_su_coordinate)
        self.txt_coordinate.textChanged.connect(self._anteprima_coordinate)
        riga_coord.addWidget(self.txt_coordinate)
        self.btn_coordinate = QPushButton("🎯 Centra qui")
        self.btn_coordinate.setEnabled(False)
        self.btn_coordinate.clicked.connect(self.centra_su_coordinate)
        riga_coord.addWidget(self.btn_coordinate)
        layout_cerca.addLayout(riga_coord)

        self.lbl_coordinate = QLabel()
        self.lbl_coordinate.setWordWrap(True)
        self.lbl_coordinate.setStyleSheet("color: #9E9E9E;")
        layout_cerca.addWidget(self.lbl_coordinate)

        self.lbl_esito_fondo = QLabel()
        self.lbl_esito_fondo.setWordWrap(True)
        layout_cerca.addWidget(self.lbl_esito_fondo)

        # Elenco e non selezione automatica: con piu' sezioni lo stesso numero
        # esiste piu' volte, e portare l'utente sul primo risultato vorrebbe
        # dire mostrargli il fondo sbagliato senza dirglielo.
        self.lista_fondi = QListWidget()
        self.lista_fondi.setMaximumHeight(110)
        self.lista_fondi.itemDoubleClicked.connect(lambda _i: self.zoom_sul_fondo())
        self.lista_fondi.currentRowChanged.connect(self._aggiorna_comandi_fondo)
        layout_cerca.addWidget(self.lista_fondi)

        riga_azioni = QHBoxLayout()
        self.btn_zoom_fondo = QPushButton("🔍 Zoom sulla mappa")
        self.btn_zoom_fondo.clicked.connect(self.zoom_sul_fondo)
        riga_azioni.addWidget(self.btn_zoom_fondo)
        self.btn_centra_fondo = QPushButton("🎯 Usa come centro della planimetria")
        self.btn_centra_fondo.clicked.connect(self.centra_planimetria_sul_fondo)
        riga_azioni.addWidget(self.btn_centra_fondo)
        layout_cerca.addLayout(riga_azioni)

        # Avviso permanente + sblocco. Il centro agganciato a un fondo resta
        # tale finché non lo si toglie: senza qualcosa che lo dica in modo
        # stabile, si sposta la mappa, si preme CREA PLANIMETRIA e si ottiene
        # un foglio da tutt'altra parte.
        riga_centro = QHBoxLayout()
        self.lbl_centro_fissato = QLabel()
        self.lbl_centro_fissato.setWordWrap(True)
        self.lbl_centro_fissato.setVisible(False)
        riga_centro.addWidget(self.lbl_centro_fissato, 1)
        self.btn_sgancia_centro = QPushButton("Sgancia")
        self.btn_sgancia_centro.setToolTip(
            "Il foglio torna a centrarsi sulla vista corrente della mappa")
        self.btn_sgancia_centro.setMaximumWidth(90)
        self.btn_sgancia_centro.clicked.connect(self.sgancia_centro)
        self.btn_sgancia_centro.setVisible(False)
        riga_centro.addWidget(self.btn_sgancia_centro)
        layout_cerca.addLayout(riga_centro)

        gruppo_cerca.setLayout(layout_cerca)
        layout_plan.addWidget(gruppo_cerca)
        self._risultati_fondo = []
        self._centro_da_fondo = None
        self._fondo_ancorato = None
        self._aggiorna_comandi_fondo()

        # Anteprima dell'ingombro: senza, formato, scala e rotazione si
        # scelgono alla cieca e il risultato si vede solo a layout creato.
        self.chk_ingombro = QCheckBox("Mostra sulla mappa l'ingombro del foglio")
        self.chk_ingombro.setToolTip(
            "Disegna sul canvas il rettangolo di terreno che finira' sul foglio, "
            "seguendo formato, scala, rotazione e centro della vista")
        self.chk_ingombro.toggled.connect(self._aggiorna_ingombro)
        layout_plan.addWidget(self.chk_ingombro)

        # Trascinare il foglio invece di spostare la mappa. Il verso naturale
        # e' questo: si muove la cosa da posizionare, non tutto il resto.
        self.chk_trascina = QCheckBox("Sposta il foglio trascinandolo sulla mappa")
        self.chk_trascina.setToolTip(
            "Afferra il rettangolo dall'interno e portalo dove serve. Il colore "
            "dice se il fondo agganciato ci sta ancora: verde dentro, arancione "
            "a filo di cornice, rosso fuori.")
        self.chk_trascina.toggled.connect(self._attiva_trascinamento)
        layout_plan.addWidget(self.chk_trascina)
        for controllo in (self.combo_formato, self.combo_scala):
            controllo.currentIndexChanged.connect(self._aggiorna_ingombro)
        self.spin_rotazione.valueChanged.connect(self._aggiorna_ingombro)

        # Fattore di proporzionalita' (cap.1.5.2). Il limite di leggibilita'
        # morde su 4 delle 8 scale ufficiali del piano RF, e fino a stamattina
        # lo scostamento era scritto solo nel README: chi sceglieva 1:5000 non
        # aveva modo di sapere che i segni uscivano quattro volte piu' grandi
        # della lettera della norma. Ora si vede qui e finisce nel cartiglio.
        self.chk_lettera_norma = QCheckBox(
            "Fattore alla lettera della norma (cap. 1.5.2)")
        self.chk_lettera_norma.setToolTip(
            "Applica il fattore esatto riferimento/scala, senza il limite di "
            "leggibilità. Dà la proporzione prescritta, ma alle scale piccole "
            "le scritture scendono sotto la soglia di stampa e spariscono.")
        self.chk_lettera_norma.toggled.connect(self._aggiorna_nota_fattore)
        layout_plan.addWidget(self.chk_lettera_norma)

        # Raccomandazione del cap. 5.7, non obbligo: spenta di default.
        self.chk_localita_maiuscolo = QCheckBox(
            "Nomi di località in maiuscolo (raccomandazione cap. 5.7)")
        self.chk_localita_maiuscolo.setToolTip(
            "«I nomi di località corrispondenti a delle borgate sono da "
            "indicare preferibilmente con lettere maiuscole.»\n"
            "Il modello non dice quali località siano borgate: la regola vale "
            "per tutta la classe Nome_di_località.\nIl dato non viene "
            "modificato — il maiuscolo è solo nel disegno.")
        self.chk_localita_maiuscolo.toggled.connect(
            self._aggiorna_maiuscolo_localita)
        layout_plan.addWidget(self.chk_localita_maiuscolo)

        self.lbl_fattore = QLabel()
        self.lbl_fattore.setWordWrap(True)
        layout_plan.addWidget(self.lbl_fattore)
        self.combo_scala.currentIndexChanged.connect(self._aggiorna_nota_fattore)
        self._aggiorna_nota_fattore()

        self.btn_planimetria = QPushButton("\U0001F4D0 CREA PLANIMETRIA")
        self.btn_planimetria.setStyleSheet(_STILE_PULSANTE % "#00695C")
        self.btn_planimetria.clicked.connect(self.run_planimetria)
        layout_plan.addWidget(self.btn_planimetria)

        self.btn_planimetria_pdf = QPushButton("\U0001F4C4 ESPORTA PLANIMETRIA IN PDF")
        self.btn_planimetria_pdf.clicked.connect(self.run_planimetria_pdf)
        layout_plan.addWidget(self.btn_planimetria_pdf)

        layout_plan.addStretch()
        group_plan.setLayout(layout_plan)
        self.pagina_plan = self._in_scheda(group_plan)
        self.schede.addTab(self.pagina_plan, "3. Planimetria")

        # Scheda degli errori nei dati: l'analisi delle violazioni di vincolo
        # esisteva gia' ma finiva in console, dove un elenco di venti conflitti
        # e' un muro di testo. In tabella diventa una lista di cose da
        # sistemare. Resta disabilitata finche' non ci sono errori.
        group_err = QGroupBox("Violazioni di vincolo trovate nell'ITF")
        layout_err = QVBoxLayout()
        nota_err = QLabel(
            "Sono errori dei dati sorgente: vanno corretti da chi gestisce "
            "l'ITF, non da qui. L'importazione li riporta tali e quali.")
        nota_err.setWordWrap(True)
        nota_err.setTextFormat(Qt.TextFormat.PlainText)
        layout_err.addWidget(nota_err)
        self.tab_errori = QTableWidget(0, 6)
        self.tab_errori.setHorizontalHeaderLabels(
            ["Tabella", "Vincolo", "Valori duplicati", "tid in conflitto",
             "Riga ITF", "Diagnosi"])
        self.tab_errori.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.tab_errori.setAlternatingRowColors(True)
        layout_err.addWidget(self.tab_errori)
        group_err.setLayout(layout_err)
        self.pagina_errori = self._in_scheda(group_err)
        self.schede.addTab(self.pagina_errori, "Errori nei dati")
        self.schede.setTabEnabled(self.schede.indexOf(self.pagina_errori), False)

        # Percorso di lavoro sopra le schede. Le spunte sui titoli dicono cosa
        # e' fatto, ma non cosa MANCA per finire: qui ogni passo dichiara il
        # motivo per cui e' fermo, ed e' cliccabile - porta alla sua scheda e
        # mette il fuoco sul campo che lo blocca.
        self._passi_fatti = set()
        self.lbl_percorso = QLabel()
        self.lbl_percorso.setWordWrap(True)
        self.lbl_percorso.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_percorso.linkActivated.connect(self._vai_al_passo)
        self.lbl_percorso.setStyleSheet(
            "padding: 4px; border: 1px solid palette(mid); border-radius: 3px;")
        layout.addWidget(self.lbl_percorso)

        layout.addWidget(self.schede)

        # Sincronizza ITF/DXF del gruppo 2 con i campi del gruppo 1 (stesso
        # dataset), senza sovrascrivere un valore che l'utente ha gia'
        # inserito a mano direttamente nel gruppo 2.
        # Catena dei nomi automatici: ITF -> GeoPackage -> DXF. Va collegata in
        # quest'ordine, cosi' scegliendo l'ITF si popolano gli altri due.
        self.txt_itf.textChanged.connect(self._avvia_inventario)
        self.txt_itf.textChanged.connect(self._sync_gpkg_da_itf)
        self.txt_itf.textChanged.connect(self._sync_geobau_itf)
        self.txt_gpkg.textChanged.connect(self._sync_geobau_dxf)
        # Cambiando il GeoPackage cambia anche il comune da proporre.
        self.txt_gpkg.textChanged.connect(self.aggiorna_comuni_da_dati)
        self.txt_gpkg.textChanged.connect(self.aggiorna_sezioni_da_dati)

        # Avanzamento: durante ili2gpkg su un comune intero non si muoveva
        # nulla per minuti, solo qualche riga di console. La barra e'
        # INDETERMINATA (setRange(0, 0)) perche' ne' ili2gpkg ne' av2geobau
        # riportano una percentuale: dichiarare un avanzamento numerico
        # sarebbe inventarselo. Fase e tempo trascorso sono invece reali.
        self.riga_avanzamento = QHBoxLayout()
        self.lbl_fase = QLabel()
        self.lbl_tempo = QLabel()
        self.lbl_tempo.setStyleSheet("font-family: Consolas, monospace;")
        self.barra_avanzamento = QProgressBar()
        self.barra_avanzamento.setRange(0, 0)
        self.barra_avanzamento.setTextVisible(False)
        self.barra_avanzamento.setMaximumHeight(8)
        self.riga_avanzamento.addWidget(self.lbl_fase)
        self.riga_avanzamento.addWidget(self.barra_avanzamento, 1)
        self.riga_avanzamento.addWidget(self.lbl_tempo)
        layout.addLayout(self.riga_avanzamento)
        self._timer_lavoro = QTimer(self)
        self._timer_lavoro.setInterval(1000)
        self._timer_lavoro.timeout.connect(self._tic_lavoro)
        self._inizio_lavoro_ts = None
        self._mostra_avanzamento(False)

        # Esito dell'importazione. Prima l'unico riscontro era la console che
        # scorreva: per sapere se era andata bene bisognava risalire centinaia
        # di righe. Resta nascosto finche' non c'e' un esito da mostrare.
        self.riquadro_esito = QGroupBox("Esito dell'ultima importazione")
        layout_esito = QVBoxLayout()
        self.lbl_esito = QLabel()
        # PlainText esplicito: nel testo finiscono nomi di tabella che vengono
        # dai dati, e QLabel di suo interpreta il rich text (stessa ragione per
        # cui la console non usa append()).
        self.lbl_esito.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_esito.setWordWrap(True)
        layout_esito.addWidget(self.lbl_esito)
        self.riquadro_esito.setLayout(layout_esito)
        self.riquadro_esito.setVisible(False)
        layout.addWidget(self.riquadro_esito)

        # Barra della console: filtro e strumenti. Dopo un'importazione con
        # dati sporchi la console e' lunga migliaia di righe e gli avvisi ci si
        # perdono dentro; e per segnalare un problema a qualcun altro serviva
        # selezionare tutto a mano.
        riga_console = QHBoxLayout()
        riga_console.addWidget(QLabel("Console di Esecuzione:"))
        self.chk_solo_problemi = QCheckBox("Solo avvisi ed errori")
        self.chk_solo_problemi.toggled.connect(self._ridisegna_console)
        riga_console.addWidget(self.chk_solo_problemi)
        self.lbl_conteggio_log = QLabel()
        self.lbl_conteggio_log.setStyleSheet("color: #9E9E9E;")
        riga_console.addWidget(self.lbl_conteggio_log)
        riga_console.addStretch()
        for testo, azione in (("Copia", self._copia_log),
                              ("Salva…", self._salva_log),
                              ("Pulisci", self._pulisci_log)):
            b = QPushButton(testo)
            b.setMaximumWidth(70)
            b.clicked.connect(azione)
            riga_console.addWidget(b)
        layout.addLayout(riga_console)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        # Colori presi dal tema, non fissi: la console era sempre nera con
        # testo verde, quindi in QGIS chiaro restava un riquadro nero in mezzo
        # a un'interfaccia chiara, e il verde acceso era faticoso da leggere a
        # lungo. Il carattere a spaziatura fissa resta: serve, le colonne dei
        # log di ili2gpkg si leggono solo cosi'.
        fondo, testo = ("#1e1e1e", "#d4d4d4") if self._tema_scuro() else ("#fafafa", "#202020")
        self.txt_log.setStyleSheet(
            "background-color: %s; color: %s; font-family: Consolas, monospace; "
            "font-size: 11px;" % (fondo, testo))
        layout.addWidget(self.txt_log)

        self.setLayout(layout)

        # Trascinamento dei file sulla finestra. Le QLineEdit accettano i
        # rilasci PER CONTO LORO e ci scriverebbero dentro il testo dell'url
        # ("file:///C:/..."), che non e' un percorso valido: vanno zittite,
        # cosi' l'evento arriva al dialogo e lo smista sul campo giusto in
        # base all'estensione, indipendentemente da dove e' stato lasciato.
        self.setAcceptDrops(True)
        for campo in (self.txt_jar, self.txt_itf, self.txt_gpkg,
                      self.txt_geobau_itf, self.txt_geobau_dxf):
            campo.setAcceptDrops(False)

        # Il comune fa parte del percorso di lavoro: se resta vuoto la
        # planimetria e' bloccata, e la riga sopra le schede deve dirlo subito.
        self.combo_comune.currentTextChanged.connect(self._aggiorna_percorso)
        self._convalida_percorsi()
        self._aggiorna_conteggio_log()
        self._ripristina_impostazioni()
        # _ripristina_impostazioni ha appena riempito i campi: la convalida va
        # rifatta, altrimenti il percorso resta quello del dialogo vuoto.
        self._convalida_percorsi()

        # La verifica si esegue SEMPRE all'apertura, non solo al primo avvio:
        # e' l'unica cosa che popola la cache di Java, e senza quella il
        # percorso di lavoro direbbe "manca: java" a chi Java ce l'ha
        # benissimo - solo perche' nessuno era ancora andato a cercarlo.
        # Costa una scansione dei candidati, una volta per finestra.
        self.verifica_ambiente()

        # PRIMO AVVIO: senza un ili2gpkg salvato non si puo' fare nulla, e la
        # scheda giusta da guardare e' quella dell'ambiente. Ci si apre sopra,
        # invece di lasciare l'utente sulla scheda dell'importazione con un
        # pulsante spento e nessuna spiegazione.
        if not self.txt_jar.text().strip():
            self.schede.setCurrentIndex(self.schede.indexOf(self.pagina_ambiente))

    def _in_scheda(self, widget):
        """Impacchetta un QGroupBox in una scheda con un po' di margine."""
        pagina = QWidget()
        contenitore = QVBoxLayout()
        contenitore.setContentsMargins(6, 8, 6, 6)
        contenitore.addWidget(widget)
        pagina.setLayout(contenitore)
        return pagina

    def on_product_changed(self, index):
        self.product_mode = self.combo_product.currentData()
        self._aggiorna_pulsante_layout()
        # La scala di stampa parte da quella di riferimento del prodotto (1:1000
        # per il piano RF, 1:5000 per il piano di base): e' la scala a cui il
        # prodotto e' pensato, ed e' il valore che il PB-MU aveva fisso nel
        # codice. Ma se l'utente ne ha scelta una A MANO non si tocca: la scala
        # di stampa la decide lui, e cambiare prodotto non e' un modo per
        # revocargliela.
        if not getattr(self, "_scala_scelta_a_mano", False):
            riferimento = _planimetria.SCALA_RIFERIMENTO.get(self.product_mode)
            if riferimento in _planimetria.SCALE_UFFICIALI_MU:
                self.combo_scala.setCurrentText("1:%d" % riferimento)
        # Il fattore dipende dal prodotto: la scala di riferimento e' 1:1000 per
        # il piano RF e 1:5000 per il piano di base, quindi cambiando prodotto
        # cambia anche quanto il limite di leggibilita' morde.
        self._aggiorna_nota_fattore()
        self.log(f"🔄 Prodotto selezionato: {self.combo_product.currentText()}")

    def _aggiorna_origine_data(self):
        """Dichiara accanto al campo da dove viene la data di "Stato al".

        Nessuna delle due fonti e' una data del contenuto INTERLIS, e le due
        sbagliano in modo DIVERSO: il timestamp dell'ITF puo' essere piu'
        recente della consegna (se il file e' stato ricopiato male), mentre
        l'ultima mutazione presente nei dati e' per costruzione un limite
        inferiore. Dirlo e' l'unico modo perche' chi firma il foglio sappia
        cosa sta attestando; la data resta modificabile e la modifica a mano
        viene riconosciuta, perche' e' la sola fonte che qualcuno abbia
        davvero verificato."""
        if not hasattr(self, "lbl_origine_data"):
            return
        dai_dati = getattr(self, "_data_dai_dati", "")
        origine = getattr(self, "_origine_data", "")
        corrente = self.data_validita.date().toString("dd.MM.yyyy")
        if dai_dati and corrente == dai_dati and origine == "estrazione ITF":
            colore = "#E65100"
            testo = ("Fonte: <b>data di modifica del file ITF</b>. È un dato del "
                     "file system, non del contenuto: l'ITF non contiene alcuna "
                     "data. Cambia se il file viene ricopiato con strumenti che "
                     "non conservano il timestamp.")
        elif dai_dati and corrente == dai_dati:
            colore = "#E65100"
            testo = ("Fonte: <b>mutazione più recente presente nei dati</b> "
                     "(Tenuta_a_giorno). È un limite inferiore: un comune senza "
                     "mutazioni recenti dà una data più vecchia del suo stato "
                     "reale.")
        elif dai_dati:
            colore = "#2E7D32"
            testo = ("Fonte: <b>indicata a mano</b> (dai dati risultava %s)."
                     % dai_dati)
        else:
            colore = "#B71C1C"
            testo = ("<b>Nessuna fonte nei dati</b>: né un ITF né le tabelle di "
                     "attualizzazione. La data qui sopra non è ricavata dai "
                     "dati e va indicata a mano.")
        self.lbl_origine_data.setText(
            "<span style='color:%s'>%s</span>" % (colore, testo))

    def _aggiorna_nota_fattore(self):
        """Scrive sotto la casella quale fattore del cap.1.5.2 verra' applicato
        alla scala scelta, e avvisa quando si discosta dalla norma o quando la
        lettera della norma rende il foglio non stampabile."""
        if not hasattr(self, "lbl_fattore"):
            return
        try:
            scala = int(self.combo_scala.currentText().split(":")[1])
        except (ValueError, IndexError, AttributeError):
            self.lbl_fattore.setText("")
            return
        lettera = self.chk_lettera_norma.isChecked()
        prodotto = self.product_mode
        fattore = _planimetria.fattore_proporzionale(scala, prodotto, lettera)
        riferimento = _planimetria.SCALA_RIFERIMENTO.get(prodotto, 1000)
        altezza, illeggibile = _planimetria.fattore_illeggibile(fattore)
        nota = _planimetria.nota_fattore(scala, prodotto, lettera)
        testo = ("Fattore cap.1.5.2: <b>x%.2f</b> (riferimento 1:%d, "
                 "scrittura minima %.2f mm)" % (fattore, riferimento, altezza))
        if illeggibile:
            colore, coda = "#B71C1C", ("<br>Sotto la soglia di stampa di %.2f mm: "
                                       "le scritture più piccole non si vedranno."
                                       % _planimetria.CAP_HEIGHT_MINIMA_STAMPA)
        elif nota:
            colore, coda = "#E65100", "<br>" + nota + ". Sarà scritto nel cartiglio."
        else:
            colore, coda = "#2E7D32", "<br>Proporzione esatta della norma."
        self.lbl_fattore.setText("<span style='color:%s'>%s%s</span>"
                                 % (colore, testo, coda))

    def _scala_scelta_dall_utente(self, _indice=None):
        """L'utente ha scelto la scala di stampa: da qui in poi comanda lei."""
        self._scala_scelta_a_mano = True

    def _aggiorna_pulsante_layout(self):
        """Il layout del piano di base ha senso solo in modalita' PB-MU."""
        attivo = self.product_mode == "bp"
        self.btn_layout.setEnabled(attivo)
        self.btn_layout.setToolTip(
            "" if attivo else
            "Disponibile solo con il prodotto \"Piano di base (PB-MU)\"")

    def _maiuscolo_localita(self):
        """La spunta e' accesa? Falso se la spunta non c'e' proprio.

        try/except E NON getattr con valore di riposo, che e' quello che avevo
        scritto e che NON funziona: su una finestra costruita con __new__ -
        come fanno le prove, per non alzare una GUI vera - PyQt rifiuta
        qualunque accesso ad attributo con RuntimeError ("super-class
        __init__() was never called"), e il valore di riposo di getattr copre
        AttributeError, non RuntimeError. La riga alzava un'eccezione proprio
        nel caso che diceva di gestire."""
        try:
            spunta = self.chk_localita_maiuscolo
        except (AttributeError, RuntimeError):
            return False
        return bool(spunta is not None and spunta.isChecked())

    def _aggiorna_maiuscolo_localita(self, _acceso=None):
        """Accende o spegne il maiuscolo sui layer GIA' caricati.

        Senza questo la spunta varrebbe solo alla prossima importazione, che su
        un file di produzione sono minuti: una scelta di resa grafica non puo'
        costare un reimport. Si riscrive solo l'espressione dell'etichetta, il
        resto del formato non si tocca."""
        maiuscolo = self._maiuscolo_localita()
        toccati = 0
        for layer in getattr(self, "loaded_layers", None) or []:
            if not _vivo(layer) or KEYWORD_LOCALITA not in \
                    _raw_table_name(layer).lower():
                continue
            etichettatura = layer.labeling()
            if etichettatura is None:
                continue
            impostazioni = etichettatura.settings()
            # Si riparte SEMPRE dal campo di base: senza, accendendo due volte
            # si otterrebbe upper("upper(...)"), che non e' un campo ne' una
            # espressione valida e lascerebbe l'etichetta vuota.
            campo = campo_di_iscrizione(impostazioni.fieldName,
                                        impostazioni.isExpression)
            impostazioni.fieldName, impostazioni.isExpression = \
                iscrizione_localita(campo, maiuscolo)
            layer.setLabeling(QgsVectorLayerSimpleLabeling(impostazioni))
            layer.triggerRepaint()
            toccati += 1
        if toccati:
            self.log("   🔠 Nomi di località %s su %d layer (cap. 5.7)"
                     % ("in MAIUSCOLO" if maiuscolo else "come nel dato",
                        toccati))
        _iface = getattr(self, "_iface", None)
        if _iface and _iface.mapCanvas():
            _iface.mapCanvas().refresh()

    def _aggiorna_pulsante_consegna(self):
        """Si consegna quello che c'e': senza layer caricati non c'e' niente.

        Spento con il motivo nel tooltip invece che nascosto - un comando che
        sparisce non spiega perche' non e' disponibile."""
        pulsante = getattr(self, "btn_consegna", None)
        if pulsante is None:
            return
        attivo = bool(getattr(self, "loaded_layers", None))
        pulsante.setEnabled(attivo)
        pulsante.setToolTip(
            "Scrive una cartella (progetto + dati + font + simboli) da copiare "
            "su QGIS Server.\nIl server NON esegue questo plugin: legge solo il "
            "progetto, e i font vanno installati sulla macchina."
            if attivo else
            "Disponibile dopo un'importazione riuscita: non c'e' ancora niente "
            "da consegnare.")

    def create_file_row(self, label_text, line_edit, filter_str, is_save, scheda=None):
        row = QHBoxLayout()
        btn = QPushButton("Sfoglia...")
        if is_save:
            btn.clicked.connect(lambda: self.browse_save_file(line_edit, filter_str))
        else:
            btn.clicked.connect(lambda: self.browse_open_file(line_edit, filter_str))
        lbl = QLabel(label_text)
        lbl.setMinimumWidth(110)
        row.addWidget(lbl)
        row.addWidget(line_edit)
        # Stato del campo, aggiornato a ogni battuta: prima un percorso
        # sbagliato si scopriva solo dalla console, dopo che Java era gia'
        # partito e fallito.
        stato = QLabel()
        stato.setMinimumWidth(16)
        row.addWidget(stato)
        row.addWidget(btn)
        if scheda:
            self._campi_percorso.append((line_edit, is_save, stato, scheda))
            line_edit.textChanged.connect(self._convalida_percorsi)
        return row

    def _segna_scheda_fatta(self, pagina, titolo):
        """Antepone una spunta al titolo della scheda portata a termine.

        Le tre schede sono una sequenza, ma niente lo diceva: chi apriva il
        plugin non sapeva a che punto fosse. NON si passa in automatico alla
        scheda successiva: dopo l'importazione i passi possibili sono due
        (DXF o planimetria) e sceglierne uno sarebbe indovinare - il riquadro
        di esito li nomina entrambi."""
        indice = self.schede.indexOf(pagina)
        if indice >= 0 and not self.schede.tabText(indice).startswith("✔"):
            self.schede.setTabText(indice, "✔ " + titolo)

    def _mostra_esito_importazione(self, n_layer, saltate, comuni):
        """Riepilogo leggibile a fine importazione, con il passo successivo.

        'saltate' = lista di (tabella, motivo)."""
        righe = ["✅ %d layer caricati e stilizzati" % n_layer]
        if comuni:
            righe.append("🏛️ Comune dai dati: %s" % ", ".join(comuni))
        else:
            righe.append("⚠️ Comune non trovato nei dati: per la planimetria "
                         "va indicato a mano")
        if saltate:
            elenco = ", ".join(t for t, _m in saltate[:6])
            if len(saltate) > 6:
                elenco += " e altre %d" % (len(saltate) - 6)
            righe.append("⚠️ %d tabelle saltate: %s" % (len(saltate), elenco))
        n_errori = len(getattr(self, "_import_unique_errors", []) or [])
        if n_errori:
            righe.append("❌ %d violazioni di vincolo nell'ITF: vedi la scheda "
                         "\"Errori nei dati\"" % n_errori)
        avvisi = sum(1 for _m, l in self._righe_log if l == "avviso")
        errori = sum(1 for _m, l in self._righe_log if l == "errore")
        if avvisi or errori:
            righe.append("In console: %d avvisi, %d errori (spunta \"Solo avvisi "
                         "ed errori\" per isolarli)" % (avvisi, errori))
        righe.append("→ Passo successivo: scheda \"2. Conversione DXF\" "
                     "oppure \"3. Planimetria\"")
        self.lbl_esito.setText("\n".join(righe))
        self.riquadro_esito.setVisible(True)

    def _riempi_tabella_errori(self, righe):
        """Popola la scheda degli errori. 'righe' = lista di dizionari con le
        chiavi tabella/vincolo/valori/tid/riga/diagnosi."""
        self.tab_errori.setRowCount(len(righe))
        for i, r in enumerate(righe):
            for j, chiave in enumerate(("tabella", "vincolo", "valori", "tid",
                                        "riga", "diagnosi")):
                voce = QTableWidgetItem(str(r.get(chiave, "")))
                voce.setFlags(voce.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.tab_errori.setItem(i, j, voce)
        self.tab_errori.resizeColumnsToContents()
        indice = self.schede.indexOf(self.pagina_errori)
        self.schede.setTabEnabled(indice, bool(righe))
        self.schede.setTabText(indice, "Errori nei dati (%d)" % len(righe)
                               if righe else "Errori nei dati")

    # --- MEMORIA DELLE IMPOSTAZIONI -----------------------------------------
    # Chi lavora sullo stesso comune per giorni ricompilava tutto a ogni
    # avvio. Si salva quello che vale la pena ritrovare, NON la data di
    # validita' (che deve ripartire da oggi) ne' l'anteprima dell'ingombro
    # (che e' un aiuto momentaneo, non una preferenza).
    def _controlli_da_ricordare(self):
        """(chiave, widget) dei controlli con memoria. Il tipo di widget
        decide come leggerli e riscriverli."""
        return [
            ("prodotto", self.combo_product),
            ("ili2gpkg_jar", self.txt_jar),
            ("itf", self.txt_itf),
            ("gpkg", self.txt_gpkg),
            ("geobau_itf", self.txt_geobau_itf),
            ("geobau_dxf", self.txt_geobau_dxf),
            ("formato", self.combo_formato),
            ("scala", self.combo_scala),
            ("rotazione", self.spin_rotazione),
            ("comune", self.combo_comune),
            ("tolleranze_attive", self.group_adv),
            ("disable_validation", self.chk_disable_val),
            ("skip_geometry", self.chk_skip_geom),
            ("skip_reference", self.chk_skip_ref),
            ("skip_polygon", self.chk_skip_poly),
            ("sql_null", self.chk_sql_null),
            ("sql_text", self.chk_sql_text),
            ("solo_problemi", self.chk_solo_problemi),
            ("lettera_norma", self.chk_lettera_norma),
        ]

    def _ripristina_impostazioni(self):
        impostazioni = QgsSettings()
        for chiave, widget in self._controlli_da_ricordare():
            valore = impostazioni.value("%s/%s" % (NOME_PLUGIN, chiave), None)
            if valore is None:
                continue
            try:
                if isinstance(widget, QLineEdit):
                    widget.setText(str(valore))
                elif isinstance(widget, QComboBox):
                    # I percorsi cambiano, gli elenchi no: se la voce salvata
                    # non c'e' piu' si lascia la predefinita invece di
                    # inventarne una.
                    if widget.isEditable():
                        widget.setCurrentText(str(valore))
                    elif widget.findText(str(valore)) >= 0:
                        widget.setCurrentText(str(valore))
                elif isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(valore))
                elif isinstance(widget, (QCheckBox, QGroupBox)):
                    widget.setChecked(str(valore).lower() in ("true", "1"))
            except (TypeError, ValueError):
                continue    # un valore corrotto non deve impedire l'avvio
            if chiave == "scala":
                # Una scala ripristinata resta una scala scelta dall'utente,
                # solo in una sessione precedente: cambiare prodotto non deve
                # riportarla alla scala di riferimento. Senza questa riga
                # l'ordine dell'elenco qui sopra (prodotto prima di scala)
                # sarebbe l'unica cosa a salvarla.
                self._scala_scelta_a_mano = True
        self._convalida_percorsi()

    def _salva_impostazioni(self):
        impostazioni = QgsSettings()
        for chiave, widget in self._controlli_da_ricordare():
            if isinstance(widget, QLineEdit):
                valore = widget.text()
            elif isinstance(widget, QComboBox):
                valore = widget.currentText()
            elif isinstance(widget, QDoubleSpinBox):
                valore = widget.value()
            elif isinstance(widget, (QCheckBox, QGroupBox)):
                valore = widget.isChecked()
            else:
                continue
            impostazioni.setValue("%s/%s" % (NOME_PLUGIN, chiave), valore)

    def _tema_scuro(self):
        """Vero se QGIS sta girando con un tema scuro. Si guarda la luminosita'
        del colore di sfondo invece del nome del tema: i temi sono
        personalizzabili e i nomi cambiano fra le versioni.

        La tavolozza si chiede all'APPLICAZIONE, non a self: il tema e' una
        proprieta' dell'applicazione, e self.palette() richiede che l'oggetto
        C++ sottostante sia gia' costruito - cosa non vera quando la dialog
        viene istanziata con __new__ (i test lo fanno per esercitare i metodi
        di stile senza costruire l'interfaccia)."""
        from qgis.PyQt.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            return False
        return app.palette().color(QPalette.ColorRole.Window).lightness() < 128

    def _rosso_avviso(self):
        """Rosso leggibile sul fondo corrente: #B71C1C e' quasi invisibile su
        sfondo scuro."""
        return "#EF9A9A" if self._tema_scuro() else "#B71C1C"

    def _verde_ok(self):
        """Verde leggibile sul fondo corrente (vedi _rosso_avviso)."""
        return "#A5D6A7" if self._tema_scuro() else "#2E7D32"

    def _sync_rotazione(self, valore):
        """Allinea cursore ed etichetta dei gradi allo spin. blockSignals sul
        cursore evita il rimbalzo cursore -> spin -> cursore, che con
        l'arrotondamento ai decimi bloccava il trascinamento."""
        self.lbl_gradi.setText("= %.1f°" % _planimetria.gon_a_gradi(valore))
        atteso = int(round(valore * 10))
        if self.slider_rotazione.value() != atteso:
            self.slider_rotazione.blockSignals(True)
            self.slider_rotazione.setValue(atteso)
            self.slider_rotazione.blockSignals(False)

    def _casella_tolleranza(self, testo, flag, spiegazione):
        """Casella per un'opzione di tolleranza: etichetta in italiano, con il
        flag di ili2gpkg e la spiegazione nel tooltip. Il flag resta visibile
        perche' chi lo conosce deve poterlo riconoscere, e perche' compare tal
        quale nella riga di comando stampata in console."""
        casella = QCheckBox(testo)
        casella.setToolTip("%s\n\n%s" % (spiegazione, flag))
        return casella

    def _riga_in_dotazione(self, etichetta, campo, nome_stato):
        """Riga per una risorsa IN DOTAZIONE (traduttore DXF, modello .ili):
        percorso visibile ma in sola lettura, spia di presenza, nessun pulsante
        'Sfoglia...'. Al suo posto un'etichetta che dice perche' non c'e' nulla
        da scegliere."""
        riga = QHBoxLayout()
        lbl = QLabel(etichetta)
        lbl.setMinimumWidth(110)
        riga.addWidget(lbl)
        riga.addWidget(campo)
        spia = QLabel()
        spia.setMinimumWidth(16)
        riga.addWidget(spia)
        setattr(self, nome_stato, spia)
        nota = QLabel("in dotazione")
        nota.setStyleSheet("color: #9E9E9E; font-style: italic;")
        riga.addWidget(nota)
        return riga

    # --- PERCORSO DI LAVORO -------------------------------------------------
    # (chiave, titolo, pagina, campo su cui mettere il fuoco quando manca)
    def _passi_percorso(self):
        return (
            ("ambiente", "Ambiente", self.pagina_ambiente, self.txt_jar),
            ("import", "Importazione", self.pagina_import, self.txt_itf),
            ("dxf", "DXF", self.pagina_dxf, self.txt_geobau_dxf),
            ("plan", "Planimetria", self.pagina_plan, self.combo_comune),
            ("pdf", "PDF", self.pagina_plan, None),
        )

    def _stato_passi(self):
        """(fatto, motivo_se_bloccato) per ogni passo. Un passo puo' essere
        fatto, fermo per un motivo dichiarato, o semplicemente non ancora
        cominciato: sono tre stati diversi e vanno distinti."""
        amb = self._controlla_ambiente(ricerca_java=False)
        # ok è False (assente) o None (non ancora verificato): sono cose
        # diverse e non vanno confuse in un unico "manca". Dire "manca: java"
        # a chi Java ce l'ha, solo perché nessuno l'ha ancora cercato, manda
        # a installare qualcosa che c'è già.
        mancano_amb = [k for k, (ok, _t) in amb.items() if ok is False]
        da_verificare = [k for k, (ok, _t) in amb.items() if ok is None]
        stato = {}
        if mancano_amb:
            stato["ambiente"] = (False, "manca: " + ", ".join(sorted(mancano_amb)))
        elif da_verificare:
            stato["ambiente"] = (False, "da verificare: " + ", ".join(sorted(da_verificare)))
        else:
            stato["ambiente"] = (True, "")
        stato["import"] = ("import" in self._passi_fatti, "")
        if not stato["import"][0] and not self.txt_itf.text().strip():
            stato["import"] = (False, "manca: file ITF")
        stato["dxf"] = ("dxf" in self._passi_fatti, "")
        comune = self.combo_comune.currentText().strip()
        if "plan" in self._passi_fatti:
            stato["plan"] = (True, "")
        elif not comune:
            # Il comune e' un'iscrizione obbligatoria del cartiglio (cap.1.5.7)
            # e si legge dai dati: se manca, di solito manca l'importazione.
            stato["plan"] = (False, "manca: comune")
        else:
            stato["plan"] = (False, "")
        stato["pdf"] = ("pdf" in self._passi_fatti, "")
        return stato

    def _aggiorna_percorso(self):
        if not hasattr(self, "lbl_percorso"):
            return
        stato = self._stato_passi()
        pezzi = []
        for chiave, titolo, _pagina, _campo in self._passi_percorso():
            fatto, motivo = stato.get(chiave, (False, ""))
            if fatto:
                colore, coda = self._verde_ok(), " ✔"
            elif motivo:
                colore, coda = "#E65100", " (%s)" % motivo
            else:
                colore, coda = "#9E9E9E", ""
            pezzi.append(
                "<a href='%s' style='color:%s; text-decoration:none;'>%s%s</a>"
                % (chiave, colore, titolo, coda))
        self.lbl_percorso.setText(
            "<span style='color:#9E9E9E;'> → </span>".join(pezzi))

    def _vai_al_passo(self, chiave):
        """Porta alla scheda del passo e, se e' fermo per un campo, mette il
        fuoco proprio su quello: dire "manca il comune" senza portarci
        costringe a cercarlo."""
        for k, _titolo, pagina, campo in self._passi_percorso():
            if k != chiave:
                continue
            indice = self.schede.indexOf(pagina)
            if indice >= 0:
                self.schede.setCurrentIndex(indice)
            fatto, motivo = self._stato_passi().get(chiave, (False, ""))
            if campo is not None and not fatto and motivo:
                campo.setFocus()
                self._lampeggia(campo)
            return

    def _lampeggia(self, widget):
        """Bordo rosso temporaneo sul campo che blocca il passo. Il tempo di
        ripristino e' l'unico modo per non lasciare il campo rosso per sempre
        una volta corretto."""
        precedente = widget.styleSheet()
        widget.setStyleSheet(precedente + "; border: 2px solid %s;"
                             % self._rosso_avviso())
        QTimer.singleShot(1500, lambda: widget.setStyleSheet(precedente))

    def _segna_passo(self, chiave):
        self._passi_fatti.add(chiave)
        self._aggiorna_percorso()

    # --- AMBIENTE -----------------------------------------------------------
    def _riga_ambiente(self, chiave, etichetta):
        """Riga a semaforo della scheda Ambiente: spia, nome, esito esteso."""
        riga = QHBoxLayout()
        spia = QLabel("•")
        spia.setMinimumWidth(16)
        spia.setStyleSheet("color: #9E9E9E; font-weight: bold;")
        riga.addWidget(spia)
        nome = QLabel(etichetta)
        nome.setMinimumWidth(130)
        riga.addWidget(nome)
        esito = QLabel("da verificare")
        esito.setStyleSheet("color: #9E9E9E;")
        esito.setWordWrap(True)
        riga.addWidget(esito, 1)
        self._spie_ambiente[chiave] = (spia, esito)
        return riga

    def _controlla_ambiente(self, ricerca_java=True):
        """Stato dei quattro requisiti: {chiave: (ok, testo)}.

        'ricerca_java' a False evita la scansione dei percorsi Java, che
        esegue 'java -version' su ogni candidato: va bene al primo avvio e
        quando si preme il pulsante, non a ogni battuta di tasto."""
        stato = {}
        if ricerca_java:
            java = self.find_java()
            stato["java"] = (bool(java), java if java else
                             "non trovato: installa Java 8 o superiore, "
                             "oppure indica JAVA_HOME")
        else:
            cache = getattr(self, "_java_path_cache", None)
            if cache is None:
                stato["java"] = (None, "non ancora verificato")
            else:
                stato["java"] = (bool(cache), cache or "non trovato")

        jar = self.txt_jar.text().strip()
        if not jar:
            stato["ili2gpkg"] = (False, "non indicato: scegli il file ili2gpkg-x.x.jar")
        elif not os.path.isfile(jar):
            stato["ili2gpkg"] = (False, "il file indicato non esiste: %s" % jar)
        else:
            stato["ili2gpkg"] = (True, jar)

        for chiave, percorso, cosa in (
                ("av2geobau", AV2GEOBAU_JAR, "il traduttore DXF"),
                ("modello", MODELLO_ILI, "il modello INTERLIS")):
            if os.path.isfile(percorso):
                stato[chiave] = (True, "in dotazione: %s" % os.path.basename(percorso))
            else:
                stato[chiave] = (False, "%s in dotazione manca: installazione "
                                        "incompleta del plugin" % cosa)
        return stato

    def _mostra_ambiente(self, stato):
        for chiave, (ok, testo) in stato.items():
            coppia = self._spie_ambiente.get(chiave)
            if coppia is None:
                continue
            spia, esito = coppia
            if ok is None:
                simbolo, colore = "•", "#9E9E9E"
            elif ok:
                simbolo, colore = "✔", self._verde_ok()
            else:
                simbolo, colore = "✖", self._rosso_avviso()
            spia.setText(simbolo)
            spia.setStyleSheet("color: %s; font-weight: bold;" % colore)
            esito.setText(testo)
            esito.setStyleSheet("color: %s;" % ("#9E9E9E" if ok is None else colore))

    def verifica_ambiente(self):
        """Rilancia i controlli da capo, buttando via la cache di Java: e' il
        senso del pulsante, altrimenti dopo aver installato Java direbbe
        ancora di no."""
        self._java_path_cache = None
        self.log("\n🔍 Verifica dell'ambiente...")
        stato = self._controlla_ambiente(ricerca_java=True)
        self._mostra_ambiente(stato)
        for chiave, (ok, testo) in sorted(stato.items()):
            self.log("   %s %-16s %s" % ("✅" if ok else "❌", chiave, testo),
                     Qgis.Info if ok else Qgis.Warning)
        mancanti = [k for k, (ok, _t) in stato.items() if not ok]
        if mancanti:
            self.log("   ⚠️ Manca: %s. Le fasi che ne dipendono restano spente."
                     % ", ".join(mancanti), Qgis.Warning)
        else:
            self.log("   ✅ Ambiente completo: si puo' importare.")
        self._aggiorna_percorso()
        return stato

    # --- CONVALIDA DEI PERCORSI ---------------------------------------------
    def _stato_percorso(self, testo, is_save):
        """(simbolo, colore, motivo) per un campo-percorso. Il campo vuoto non
        e' un errore: e' semplicemente non ancora compilato."""
        testo = (testo or "").strip()
        if not testo:
            return "•", "#9E9E9E", "da compilare"
        if is_save:
            # Per un file da scrivere conta che esista la CARTELLA: il file
            # stesso non c'e' ancora, ed e' normale.
            cartella = os.path.dirname(testo) or "."
            if not os.path.isdir(cartella):
                return "✖", self._rosso_avviso(), "la cartella di destinazione non esiste"
            return "✔", self._verde_ok(), ""
        if not os.path.isfile(testo):
            return "✖", self._rosso_avviso(), "il file non esiste"
        return "✔", self._verde_ok(), ""

    # --- IL MODELLO, A OGNI PASSO -------------------------------------------
    # Il modello sbagliato entra da ogni porta: un ITF ricevuto per posta, un
    # GeoPackage importato mesi fa da qualcun altro, un secondo ITF scelto a
    # mano per la sola conversione DXF. Il controllo sta quindi dove si sceglie
    # il file (spia sempre accesa) e di nuovo prima di ogni operazione lunga,
    # non in un punto solo.
    def _modello_di(self, percorso, e_gpkg=False):
        """(esito, modello) con memoria: _convalida_percorsi gira a ogni
        battuta sulla tastiera, e rileggere il file a ogni tasto sarebbe
        sprecato. La memoria e' per (percorso, dimensione, data): un file
        riscritto viene riletto."""
        percorso = (percorso or "").strip()
        if not percorso or not os.path.isfile(percorso):
            return _modello.NON_LEGGIBILE, ""
        try:
            stato = os.stat(percorso)
            chiave = (percorso, stato.st_size, int(stato.st_mtime))
        except OSError:
            return _modello.NON_LEGGIBILE, ""
        memoria = getattr(self, "_memoria_modello", None)
        if memoria is None:
            memoria = self._memoria_modello = {}
        if chiave not in memoria:
            memoria[chiave] = (_modello.controlla_gpkg(percorso) if e_gpkg
                               else _modello.controlla_itf(percorso))
        return memoria[chiave]

    def _campi_con_modello(self):
        """I campi che puntano a un ITF, cioe' quelli che dichiarano un
        modello. Sono due perche' la conversione DXF puo' lavorare su un ITF
        diverso da quello importato: e' proprio il caso in cui il modello
        sbagliato passerebbe inosservato."""
        return [c for c in (getattr(self, "txt_itf", None),
                            getattr(self, "txt_geobau_itf", None)) if c is not None]

    def _registra_modello(self, percorso, esito, trovato):
        """Una riga di log sola per file: senza, l'inventario ripeterebbe lo
        stesso avviso a ogni ricalcolo e la console diventerebbe illeggibile."""
        detti = getattr(self, "_modelli_detti", None)
        if detti is None:
            detti = self._modelli_detti = set()
        if percorso in detti:
            return
        detti.add(percorso)
        if esito == _modello.OK:
            self.log("   🧬 Modello dei dati: %s (quello atteso)" % trovato)
        else:
            self.log("   ⚠️ %s" % _modello.spiega(esito, trovato, "il file scelto"),
                     Qgis.Warning)

    def _controlla_modello_prima_di(self, percorso, cosa, e_gpkg=False):
        """Ultimo controllo prima di un'operazione lunga. True = si prosegue.

        Il file puo' essere cambiato da quando lo si e' scelto, e un pulsante
        acceso non e' una garanzia: si rilegge qui, dove costa un istante e
        risparmia minuti."""
        esito, trovato = self._modello_di(percorso, e_gpkg)
        messaggio = _modello.spiega(esito, trovato, cosa)
        if not messaggio:
            return True
        if _modello.e_bloccante(esito):
            QMessageBox.warning(self, "Modello dei dati", messaggio)
            self.log("   ❌ %s" % messaggio, Qgis.Critical)
            return False
        # Incertezza, non certezza: si avvisa e si lascia decidere.
        self.log("   ⚠️ %s" % messaggio, Qgis.Warning)
        return True

    def _convalida_percorsi(self):
        """Aggiorna le spie dei campi e abilita i pulsanti solo quando la
        rispettiva scheda e' completa."""
        if not getattr(self, "_campi_percorso", None):
            return
        mancanti = {"import": [], "dxf": []}
        for line_edit, is_save, etichetta, scheda in self._campi_percorso:
            simbolo, colore, motivo = self._stato_percorso(line_edit.text(), is_save)
            # Un percorso valido non basta: se il file c'e' ma dichiara un
            # altro modello, la spia lo dice subito e il pulsante resta spento.
            # Prima lo si scopriva dopo minuti di ili2gpkg, con un errore che
            # parlava di classi mancanti invece che di modello sbagliato.
            if not motivo and line_edit in self._campi_con_modello():
                esito, trovato = self._modello_di(line_edit.text())
                if _modello.e_bloccante(esito):
                    simbolo, colore = "✖", self._rosso_avviso()
                    motivo = _modello.spiega(esito, trovato, "il file scelto")
            etichetta.setText(simbolo)
            etichetta.setStyleSheet("color: %s; font-weight: bold;" % colore)
            etichetta.setToolTip(motivo)
            if motivo:
                mancanti[scheda].append(motivo)

        # Le risorse in dotazione non si scelgono, ma vanno comunque verificate:
        # se l'installazione e' incompleta il file non c'e' e l'operazione
        # fallirebbe con un errore di Java invece che con un messaggio chiaro.
        for nome_stato, percorso, descrizione, schede in (
                ("stato_jar", AV2GEOBAU_JAR, "il traduttore DXF", ("dxf",)),
                ("stato_ili", MODELLO_ILI, "il modello .ili", ("import", "dxf"))):
            spia = getattr(self, nome_stato, None)
            if spia is None:
                continue
            if os.path.isfile(percorso):
                spia.setText("✔")
                spia.setStyleSheet("color: %s; font-weight: bold;" % self._verde_ok())
                spia.setToolTip("")
            else:
                spia.setText("✖")
                spia.setStyleSheet("color: %s; font-weight: bold;" % self._rosso_avviso())
                motivo = "%s in dotazione non e' installato" % descrizione
                spia.setToolTip(motivo)
                for scheda in schede:
                    mancanti[scheda].append(motivo)

        # Un lavoro in corso ha la precedenza: i pulsanti restano spenti anche
        # se i campi sono a posto. Si guarda un flag e non worker.isRunning()
        # perche' _inizio_lavoro viene chiamato PRIMA che il nuovo JavaWorker
        # sia assegnato a self.worker: interrogando il worker si sarebbe visto
        # quello vecchio (o None) e i pulsanti si sarebbero riaccesi subito.
        occupato = getattr(self, "_lavoro_in_corso", False)
        for scheda, pulsante, etichetta in (
                ("import", self.btn_import, self.lbl_esito_import),
                ("dxf", self.btn_geobau, self.lbl_esito_dxf)):
            problemi = mancanti[scheda]
            pulsante.setEnabled(not problemi and not occupato)
            if problemi:
                etichetta.setText("%d campo/i da sistemare: %s"
                                  % (len(problemi), "; ".join(sorted(set(problemi)))))
            else:
                etichetta.setText("")

        # Anche i comandi della planimetria vanno spenti mentre gira un lavoro:
        # prima restavano attivi e potevano partire con il GeoPackage in
        # scrittura, leggendo layer a meta' importazione.
        for pulsante in (getattr(self, "btn_planimetria", None),
                         getattr(self, "btn_planimetria_pdf", None),
                         getattr(self, "btn_layout", None)):
            if pulsante is None:
                continue
            if pulsante is self.btn_layout:
                pulsante.setEnabled(self.product_mode == "bp" and not occupato)
            else:
                pulsante.setEnabled(not occupato)

        # Le spie della scheda Ambiente e la riga di percorso si aggiornano
        # insieme ai campi. Java NON viene ricercato qui: la scansione esegue
        # 'java -version' sui candidati e non puo' girare a ogni battuta.
        self._mostra_ambiente(self._controlla_ambiente(ricerca_java=False))
        self._aggiorna_percorso()

    # --- AVANZAMENTO --------------------------------------------------------
    def _mostra_avanzamento(self, visibile):
        for w in (self.lbl_fase, self.barra_avanzamento, self.lbl_tempo):
            w.setVisible(visibile)

    def _inizio_lavoro(self, fase):
        import time
        self._lavoro_in_corso = True
        self._inizio_lavoro_ts = time.monotonic()
        self.lbl_fase.setText(fase)
        self.lbl_tempo.setText("00:00")
        self._mostra_avanzamento(True)
        self._timer_lavoro.start()
        self._convalida_percorsi()

    def _fine_lavoro(self):
        self._lavoro_in_corso = False
        self._timer_lavoro.stop()
        self._inizio_lavoro_ts = None
        self._mostra_avanzamento(False)
        self._convalida_percorsi()

    def _tic_lavoro(self):
        import time
        if self._inizio_lavoro_ts is None:
            return
        trascorsi = int(time.monotonic() - self._inizio_lavoro_ts)
        self.lbl_tempo.setText("%02d:%02d" % (trascorsi // 60, trascorsi % 60))

    # --- COMUNE LETTO DAI DATI ----------------------------------------------
    def aggiorna_comuni_da_dati(self):
        """Rilegge i nomi di comune dal GeoPackage e li propone nella casella.

        Il percorso si prende prima dai layer caricati (sono loro a dire da
        quale file vengono davvero) e solo in mancanza dal campo di testo, che
        l'utente puo' aver cambiato dopo l'importazione."""
        percorso = _dati_comune.gpkg_dei_layer(getattr(self, "loaded_layers", None))
        if not percorso:
            percorso = self.txt_gpkg.text().strip()
        # "Stato al" e' la data di ESTRAZIONE dell'ITF, non quella della
        # stampa. L'ITF non la contiene al suo interno, quindi si legge dal
        # timestamp del file. Se l'ITF non e' disponibile (es. si e' aperto
        # solo un GeoPackage) si ripiega sulla mutazione piu' recente presente
        # nei dati, che e' la migliore approssimazione ricavabile.
        data = _dati_comune.data_estrazione_itf(self.txt_itf.text().strip())
        self._origine_data = "estrazione ITF" if data else ""
        if not data:
            data = _dati_comune.leggi_data_validita(percorso)
            self._origine_data = "ultima mutazione nei dati" if data else ""
        if data:
            # _data_dai_dati va assegnata PRIMA di setDate: setDate emette
            # dateChanged, che rilegge l'etichetta della fonte; con il vecchio
            # ordine l'etichetta si sarebbe calcolata sul valore precedente e
            # avrebbe dichiarato "modificata a mano" una data appena letta.
            self._data_dai_dati = data
            giorno, mese, anno = (int(x) for x in data.split("."))
            self.data_validita.setDate(QDate(anno, mese, giorno))
        else:
            self._data_dai_dati = ""
        self._aggiorna_origine_data()
        nomi = _dati_comune.leggi_comuni(percorso)
        if not nomi:
            return []
        scelto = self.combo_comune.currentText().strip()
        self.combo_comune.clear()
        self.combo_comune.addItems(nomi)
        # Se l'utente aveva gia' scelto un nome ancora presente, lo si rispetta.
        self.combo_comune.setCurrentText(scelto if scelto in nomi else nomi[0])
        return nomi

    # --- TRASCINAMENTO DEL FOGLIO -------------------------------------------
    def _colore_ingombro(self, stato):
        """Il colore del rettangolo dice se il fondo agganciato ci sta ancora.

        Il riscontro va dato SUL CANVAS, dove sta l'occhio di chi trascina: una
        scritta nella finestra di dialogo, che spesso copre solo mezza mappa,
        si legge dopo. Verde dentro, arancione a filo di cornice, rosso fuori;
        il verde acqua di sempre quando non c'e' nessun fondo agganciato e la
        domanda non ha senso."""
        return {"dentro": QColor(46, 125, 50),
                "stretto": QColor(230, 145, 0),
                "fuori": QColor(198, 40, 40)}.get(stato, QColor(0, 105, 92))

    def _stato_fondo_nel_foglio(self, centro):
        """"dentro"/"stretto"/"fuori" per il fondo agganciato, o None."""
        fondo = getattr(self, "_fondo_ancorato", None)
        punti = getattr(fondo, "contorno", None) if fondo else None
        if not punti:
            return None
        formato, scala, rotazione, _c, _d = self._parametri_planimetria()
        return _planimetria.stato_capienza(punti, centro, scala, formato, rotazione)

    # --- CENTRO PER COORDINATE ----------------------------------------------
    def _trasforma_wgs84(self, lon, lat):
        """(lon, lat) in gradi -> (E, N) in MN95, con la proiezione di QGIS.

        Ritorna None se la trasformazione non e' disponibile: meglio dire
        "non ho capito" che centrare il foglio su due numeri inventati."""
        try:
            sorgente = QgsCoordinateReferenceSystem("EPSG:4326")
            destinazione = QgsCoordinateReferenceSystem(_planimetria.CRS_MU)
            if not (sorgente.isValid() and destinazione.isValid()):
                return None
            tr = QgsCoordinateTransform(sorgente, destinazione,
                                        QgsProject.instance())
            punto = tr.transform(QgsPointXY(lon, lat))
            return punto.x(), punto.y()
        except Exception:
            return None

    def _leggi_coordinate(self):
        return _coordinate.analizza(self.txt_coordinate.text(),
                                    trasforma_wgs84=self._trasforma_wgs84)

    def _anteprima_coordinate(self, *_args):
        """Dice a ogni battuta cosa si e' capito, prima di premere qualcosa.

        Il campo accetta tre sistemi e li riconosce dall'ordine di grandezza:
        senza un riscontro, l'utente scoprirebbe solo dopo di aver incollato
        delle MN03 dove pensava di mettere delle MN95."""
        testo = self.txt_coordinate.text().strip()
        coord = self._leggi_coordinate() if testo else None
        self.btn_coordinate.setEnabled(coord is not None)
        if not testo:
            self.lbl_coordinate.setText("")
            return
        if coord is None:
            self.lbl_coordinate.setText(_coordinate.motivo_del_rifiuto(testo))
            self.lbl_coordinate.setStyleSheet("color: %s;" % self._rosso_avviso())
            return
        self.lbl_coordinate.setText(_coordinate.spiega(coord))
        self.lbl_coordinate.setStyleSheet(
            "color: %s;" % ("#E65100" if coord.approssimata else "#9E9E9E"))

    def centra_su_coordinate(self):
        """Porta il foglio sul punto scritto nel campo.

        Usa lo stesso aggancio del centro fissato su un fondo: da li' in poi
        la vista puo' muoversi quanto vuole, il foglio resta dove l'hai
        messo."""
        coord = self._leggi_coordinate()
        if coord is None:
            testo = self.txt_coordinate.text().strip()
            if testo:
                QMessageBox.warning(self, "Coordinate",
                                    _coordinate.motivo_del_rifiuto(testo))
            return
        # Il fondo agganciato lascia il posto: il centro ora e' un punto
        # scelto a mano, e continuare a colorare il rettangolo in base a un
        # fondo che non c'entra piu' direbbe una cosa falsa.
        self._fondo_ancorato = None
        self.sposta_foglio_a(QgsPointXY(coord.est, coord.nord), definitivo=True)
        self._aggiorna_centro_fissato("coordinate inserite a mano")
        self.log("\n🎯 CENTRO PER COORDINATE")
        self.log("   ✅ %s" % _coordinate.spiega(coord),
                 Qgis.Warning if coord.approssimata else Qgis.Info)
        _iface = getattr(self, "_iface", None)
        if _iface and _iface.mapCanvas():
            canvas = _iface.mapCanvas()
            estensione = canvas.extent()
            mezzo_x, mezzo_y = estensione.width() / 2.0, estensione.height() / 2.0
            canvas.setExtent(QgsRectangle(coord.est - mezzo_x, coord.nord - mezzo_y,
                                          coord.est + mezzo_x, coord.nord + mezzo_y))
            canvas.refresh()

    def sposta_foglio_a(self, centro, definitivo=False):
        """Mette il centro del foglio dove lo si e' trascinato.

        Usa lo stesso aggancio del centro fissato su un fondo: da li' in poi la
        vista puo' muoversi quanto vuole, il foglio resta dove l'hai messo."""
        self._centro_da_fondo = QgsPointXY(centro)
        self._aggiorna_ingombro()
        if not definitivo:
            return
        self._fondo_ancorato = getattr(self, "_fondo_ancorato", None)
        stato = self._stato_fondo_nel_foglio(centro)
        etichetta = getattr(self, "_etichetta_centro", None)
        if stato is None:
            self._aggiorna_centro_fissato("posizione scelta a mano")
        else:
            self._aggiorna_centro_fissato(etichetta)
        nota = {"dentro": "", "stretto": " — il fondo arriva a filo di cornice",
                "fuori": " — ATTENZIONE: il fondo esce dal foglio"}.get(stato, "")
        self.log("   🖐️ Foglio spostato a E%.1f N%.1f%s"
                 % (centro.x(), centro.y(), nota),
                 Qgis.Warning if stato == "fuori" else Qgis.Info)

    def ruota_foglio_verso(self, punto, centro, definitivo=False):
        """Gira il foglio finche' la maniglia non guarda 'punto'.

        Scrive nella casella della rotazione invece di tenersi un valore
        suo: la casella resta l'unica fonte, il valore e' leggibile in gon
        mentre si trascina, e l'anteprima si aggiorna da sola perche' e' gia'
        agganciata al cambiamento di quella casella."""
        gon = _planimetria.rotazione_verso(centro, punto)
        if gon is None:
            return          # puntatore sul centro: li' un angolo non esiste
        self.spin_rotazione.setValue(round(gon, 1))
        if definitivo:
            self.log("   🔄 Foglio ruotato a %.1f gon (%.1f°)"
                     % (gon, _planimetria.gon_a_gradi(gon)))

    def _attiva_trascinamento(self, attivo):
        """Accende o spegne lo strumento di trascinamento sul canvas."""
        iface = getattr(self, "_iface", None)
        canvas = iface.mapCanvas() if iface else None
        if canvas is None:
            return
        if attivo:
            if not self.chk_ingombro.isChecked():
                self.chk_ingombro.setChecked(True)   # senza rettangolo non c'e' cosa afferrare
            self._strumento_precedente = canvas.mapTool()
            self._strumento_foglio = StrumentoSpostaFoglio(canvas, self)
            canvas.setMapTool(self._strumento_foglio)
            self.log("   🖐️ Trascina il rettangolo per inquadrare il foglio "
                     "(il colore dice se il fondo ci sta)")
            return
        strumento = getattr(self, "_strumento_foglio", None)
        if strumento is not None and canvas.mapTool() is strumento:
            canvas.unsetMapTool(strumento)
            precedente = getattr(self, "_strumento_precedente", None)
            if precedente is not None:
                canvas.setMapTool(precedente)
        self._strumento_foglio = None
        # Spenta la presa, via anche la maniglia: promette un gesto che da
        # quel momento non funziona piu'.
        self._aggiorna_ingombro()

    # --- ANTEPRIMA DELL'INGOMBRO DEL FOGLIO ---------------------------------
    def _aggiorna_ingombro(self, *_args):
        """Disegna (o cancella) sul canvas il rettangolo di terreno che finira'
        sul foglio. La geometria arriva da planimetria.impronta_foglio, la
        stessa usata per costruire il layout, cosi' anteprima e risultato non
        possono divergere."""
        iface = getattr(self, "_iface", None)
        canvas = iface.mapCanvas() if iface else None
        if canvas is None:
            return
        banda = getattr(self, "_banda_ingombro", None)
        if not self.chk_ingombro.isChecked():
            if banda is not None:
                banda.reset(QgsWkbTypes.PolygonGeometry)
            return
        if banda is None:
            from qgis.gui import QgsRubberBand
            banda = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
            banda.setWidth(2)
            self._banda_ingombro = banda
        formato, scala, rotazione, _comune, _data = self._parametri_planimetria()
        # Il centro fissato su un fondo ha la precedenza sulla vista: altrimenti
        # l'anteprima mostrerebbe un ingombro diverso da quello che verrebbe
        # stampato, che e' esattamente cio' che l'anteprima deve escludere.
        centro = getattr(self, "_centro_da_fondo", None) or canvas.extent().center()
        punti = _planimetria.impronta_foglio(centro, scala, formato, rotazione)
        banda.setToGeometry(QgsGeometry.fromPolygonXY([punti]), None)
        colore = self._colore_ingombro(self._stato_fondo_nel_foglio(centro))
        banda.setStrokeColor(colore)
        banda.setColor(QColor(colore.red(), colore.green(), colore.blue(), 60))
        self._disegna_maniglia(canvas, centro, scala, formato, rotazione, colore)

    def _disegna_maniglia(self, canvas, centro, scala, formato, rotazione, colore):
        """Il pallino per cui si afferra il foglio per ruotarlo.

        Si disegna SOLO con lo strumento di trascinamento acceso: una
        maniglia che non risponde al mouse e' peggio di nessuna maniglia -
        promette un gesto che non funziona."""
        maniglia = getattr(self, "_banda_maniglia", None)
        attivo = getattr(self, "_strumento_foglio", None) is not None
        if not attivo:
            if maniglia is not None:
                maniglia.reset(QgsWkbTypes.PointGeometry)
            return
        if maniglia is None:
            from qgis.gui import QgsRubberBand
            maniglia = QgsRubberBand(canvas, QgsWkbTypes.PointGeometry)
            maniglia.setIcon(QgsRubberBand.ICON_CIRCLE)
            maniglia.setIconSize(11)
            maniglia.setWidth(2)
            self._banda_maniglia = maniglia
        punto = _planimetria.maniglia_rotazione(centro, scala, formato, rotazione)
        maniglia.setToGeometry(QgsGeometry.fromPointXY(punto), None)
        maniglia.setStrokeColor(colore)
        maniglia.setColor(QColor(255, 255, 255, 220))

    def browse_open_file(self, line_edit, filter_str):
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona File", "", filter_str)
        if path:
            line_edit.setText(path)

    def browse_save_file(self, line_edit, filter_str):
        path, _ = QFileDialog.getSaveFileName(self, "Salva File", "", filter_str)
        if path:
            line_edit.setText(path)

    def _cartella_di_lavoro(self):
        """Dove proporre di salvare: accanto ai file con cui si sta gia'
        lavorando, non in una cartella qualunque."""
        for campo in (getattr(self, "txt_itf", None), getattr(self, "txt_gpkg", None)):
            testo = campo.text().strip() if campo else ""
            if testo:
                cartella = os.path.dirname(testo)
                if os.path.isdir(cartella):
                    return cartella
        scaricati = os.path.join(os.path.expanduser("~"), "Downloads")
        return scaricati if os.path.isdir(scaricati) else os.path.expanduser("~")

    def scarica_itf_dal_cantone(self):
        """Apre la scelta del comune e, se lo scaricamento riesce, compila da
        solo il campo dell'ITF: fine dello scaricamento e inizio del lavoro
        sono la stessa cosa, e farli scrivere a mano sarebbe l'unico modo di
        sbagliarli."""
        finestra = DialogScaricaMU(self, self._cartella_di_lavoro())
        if finestra.exec() != QDialog.DialogCode.Accepted:
            return
        percorso = finestra.percorso_itf
        if not percorso:
            return
        self.txt_itf.setText(percorso)
        self.log("\n⬇️ DATI MU DAL CANTONE")
        self.log("   ✅ %s (%.1f MB), impronta MD5 verificata"
                 % (percorso, os.path.getsize(percorso) / 1048576.0),
                 Qgis.Success)
        self.log("   ℹ️ Fonte: %s — %s"
                 % (_scarica_mu.URL_INDICE, "condizioni: " + _scarica_mu.URL_CONDIZIONI))

    def _livello_riga(self, msg, level):
        """Classifica una riga come 'errore', 'avviso' o 'normale'.

        Il parametro 'level' e' la fonte piu' attendibile, ma buona parte delle
        chiamate non lo passa e affida la gravita' al solo emoji iniziale:
        si guardano entrambi, altrimenti il filtro 'solo avvisi ed errori'
        lascerebbe fuori proprio le righe scritte senza livello esplicito."""
        if level == Qgis.Critical or "❌" in msg:
            return "errore"
        if level == Qgis.Warning or "⚠️" in msg:
            return "avviso"
        return "normale"

    def _colore_livello(self, livello):
        if livello == "errore":
            return QColor(self._rosso_avviso())
        if livello == "avviso":
            return QColor("#FFB74D" if self._tema_scuro() else "#E65100")
        return QColor("#d4d4d4" if self._tema_scuro() else "#202020")

    def _scrivi_riga(self, msg, livello):
        """Scrive una riga colorata secondo la gravita'.

        insertText e NON append(): append interpreta il testo come HTML
        (verificato: "<b>x</b>" viene mostrato in grassetto, senza i tag).
        Nella console finiscono anche stringhe che vengono dai DATI - nomi di
        file e messaggi di ili2gpkg che riportano i valori dell'ITF - quindi
        un ITF confezionato ad arte poteva scrivere in console un falso
        "✅ Importazione completata", o far caricare risorse locali con un
        <img src>. Il colore lo decidiamo noi dal livello, il testo resta
        letterale."""
        cursore = self.txt_log.textCursor()
        cursore.movePosition(QTextCursor.MoveOperation.End)
        formato = QTextCharFormat()
        formato.setForeground(self._colore_livello(livello))
        cursore.setCharFormat(formato)
        cursore.insertText(msg + "\n")
        self.txt_log.setTextCursor(cursore)
        self.txt_log.ensureCursorVisible()

    def log(self, msg, level=Qgis.Info):
        livello = self._livello_riga(msg, level)
        # Le righe si conservano tutte: il filtro nasconde, non butta via.
        self._righe_log.append((msg, livello))
        if not (self.chk_solo_problemi.isChecked() and livello == "normale"):
            self._scrivi_riga(msg, livello)
        self._aggiorna_conteggio_log()
        QgsMessageLog.logMessage(msg, NOME_PLUGIN, level)

    def _ridisegna_console(self):
        """Riscrive la console applicando il filtro corrente."""
        solo_problemi = self.chk_solo_problemi.isChecked()
        self.txt_log.clear()
        for msg, livello in self._righe_log:
            if solo_problemi and livello == "normale":
                continue
            self._scrivi_riga(msg, livello)
        self._aggiorna_conteggio_log()

    def _aggiorna_conteggio_log(self):
        avvisi = sum(1 for _m, l in self._righe_log if l == "avviso")
        errori = sum(1 for _m, l in self._righe_log if l == "errore")
        self.lbl_conteggio_log.setText(
            "" if not (avvisi or errori) else "%d avvisi, %d errori" % (avvisi, errori))

    def _copia_log(self):
        from qgis.PyQt.QtWidgets import QApplication
        QApplication.clipboard().setText("\n".join(m for m, _l in self._righe_log))

    def _salva_log(self):
        percorso, _ = QFileDialog.getSaveFileName(
            self, "Salva il registro", "tidashboard_log.txt", "Testo (*.txt)")
        if not percorso:
            return
        try:
            with open(percorso, "w", encoding="utf-8") as f:
                f.write("\n".join(m for m, _l in self._righe_log))
        except OSError as e:
            QMessageBox.warning(self, "Salvataggio", "Impossibile scrivere il file:\n%s" % e)

    def _pulisci_log(self):
        self._righe_log = []
        self.txt_log.clear()
        self._aggiorna_conteggio_log()

    def closeEvent(self, event):
        """Se un worker Java e' ancora in esecuzione, chiedi conferma prima di
        chiudere la finestra: il processo figlio (ili2gpkg/av2geobau) NON
        morirebbe insieme alla dialog e continuerebbe a scrivere sul
        GPKG/DXF in background, con l'utente convinto che fosse stato
        interrotto. Su conferma, il processo viene terminato (worker.cancel)
        e si attende al massimo 3 secondi che il thread finisca."""
        worker = getattr(self, "worker", None)  # getattr: i test usano __new__ senza __init__
        # Il wrapper Python puo' sopravvivere all'oggetto C++: da quando il
        # worker si distrugge da solo a lavoro finito (finished -> deleteLater)
        # self.worker resta appeso a un oggetto gia' cancellato, e interrogarlo
        # solleva RuntimeError proprio nella chiusura della finestra - dove un
        # errore e' piu' fastidioso che altrove. Segnalato da un utente:
        # "RuntimeError: wrapped C/C++ object of type JavaWorker has been
        # deleted" in closeEvent.
        if not _vivo(worker):
            worker = None
        if worker is not None and worker.isRunning():
            reply = QMessageBox.warning(
                self, "Processo in esecuzione",
                "Un'operazione e' ancora in corso. Chiudendo la finestra "
                "verra' interrotta.\nChiudere comunque?",
                _MB_SI | _MB_NO, _MB_NO)
            if reply != _MB_SI:
                event.ignore()
                return
            self.log("⏹️ Interruzione richiesta dall'utente (chiusura finestra)...")
            worker.cancel()
            worker.wait(3000)
        # Le impostazioni si salvano alla chiusura, non a ogni battuta:
        # cosi' una sessione interrotta a meta' non lascia in memoria percorsi
        # scritti per sbaglio.
        self._salva_impostazioni()
        # L'ingombro e' disegnato sul canvas di QGIS, non dentro questa
        # finestra: chiudendola resterebbe li' senza piu' nessuno che lo
        # aggiorni.
        banda = getattr(self, "_banda_ingombro", None)
        if banda is not None:
            banda.reset(QgsWkbTypes.PolygonGeometry)
        maniglia = getattr(self, "_banda_maniglia", None)
        if maniglia is not None:
            maniglia.reset(QgsWkbTypes.PointGeometry)
        # Stesso motivo per i risultati della ricerca: restano accesi sulla
        # mappa di QGIS finche' qualcuno non li spegne, e chiusa la finestra
        # non c'e' piu' nessuno che possa farlo.
        self._pulisci_bande_risultati()
        super().closeEvent(event)

    def find_java(self):
        """Trova un java funzionante sulla macchina, senza assumere una
        versione specifica installata.

        La ricerca vera sta in java_env.trova_java: scansione dei dischi,
        esecuzione di 'java -version' e scelta della versione piu' alta fra
        quelle che partono davvero (un file java puo' esistere ed essere uno
        stub rotto o di un'architettura sbagliata). Qui restano le due cose
        che appartengono alla finestra: la CACHE sull'istanza - per non
        rifare la scansione a ogni conversione della stessa sessione - e i
        MESSAGGI nella console.

        Il jar av2geobau_ti.jar e' compilato con --release 8, quindi
        qualunque JRE 8+ va bene; preferire il piu' recente resta la scelta
        piu' sicura."""
        if self._java_path_cache is not None:
            return self._java_path_cache or None  # "" cachato = "cercato, non trovato"

        esito = _java_env.trova_java(
            log=lambda msg: self.log(msg, Qgis.Warning))
        if esito.percorso:
            self.log("   ☕ Java trovato e verificato funzionante: %s "
                     "(versione %d.%d, %d candidati esaminati)"
                     % (esito.percorso, esito.versione[0], esito.versione[1],
                        esito.n_candidati))
        elif esito.candidati:
            self.log("   ⚠️ %d eseguibili java trovati ma nessuno risulta "
                     "funzionante (eseguibile rotto o incompatibile?)"
                     % esito.n_candidati, Qgis.Warning)

        self._java_path_cache = esito.percorso or ""
        return esito.percorso

    def get_ili_class(self, gpkg_path, table_name):
        """Legge la classe ILI dai metadati di ili2db."""
        try:
            with sqlite3.connect(str(gpkg_path)) as conn:
                cursor = conn.cursor()
                # Le colonne reali sono "IliName"/"SqlName" (verificato sul GeoPackage),
                # non "class_name"/"sql_name".
                cursor.execute("SELECT IliName FROM t_ili2db_classname WHERE SqlName = ?", (table_name,))
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            self.log(f"  ⚠️ Errore lettura metadati ILI per {table_name}: {str(e)}", Qgis.Warning)
            return None

    def _nice_layer_name(self, class_name, table):
        """Nome leggibile per il pannello Layers di QGIS, al posto del nome
        tabella grezzo del GeoPackage (es. "beni_immobili_punto_di_confine",
        "punti_fissctgria3_simbolopfp3" - l'identificativo SQL generato da
        ili2db, spesso troncato/concatenato in modi poco intuitivi e mai
        pensato per essere letto da un utente).
        'class_name' e' il nome della classe ILI vera e propria (letto dai
        metadati t_ili2db_classname, es. "Punto_di_confine", "SuperficieCS",
        "PosNome_del_luogo") - gia' molto piu' chiaro con un semplice
        underscore->spazio, tranne per le sigle tecniche concatenate senza
        underscore (SuperficieCS, PCGiurisdizionale, DPSSP, PFP1/2/3, PFA1/2),
        per cui uso _NICE_CLASS_NAMES. Le tabelle "PosXxx" (punto di
        iscrizione di un'etichetta testuale, non l'oggetto vero e proprio -
        vedi TEXT_LABEL_RULES) diventano "Xxx (etichetta)".
        Se la classe ILI non e' stata risolta (raro, gia' loggato come
        warning altrove), ripulisce almeno il nome tabella grezzo invece di
        lasciarlo cosi' com'e'."""
        if not class_name:
            return table.replace("_", " ").strip().capitalize()
        if class_name in self._NICE_CLASS_NAMES:
            return self._NICE_CLASS_NAMES[class_name]
        base, suffix = class_name, ""
        if base.startswith("Pos") and len(base) > 3 and base[3].isupper():
            base = base[3:]
            suffix = " (etichetta)"
        if base in self._NICE_CLASS_NAMES:
            return self._NICE_CLASS_NAMES[base] + suffix
        return base.replace("_", " ") + suffix

    # Sigle/nomi di classe ILI concatenati senza underscore, illeggibili con
    # il semplice underscore->spazio usato da _nice_layer_name per tutti gli
    # altri (es. "Punto_di_confine" -> "Punto di confine" gia' va bene cosi').
    # PFP1/2/3 e PFA1/2 non compaiono qui apposta: senza underscore, ricadono
    # gia' correttamente sul percorso generico (base.replace("_"," ")) che le
    # lascia invariate ("PFP1" invece della precedente "Punto fisso di
    # poligonazione (cat. 1)" - richiesta esplicita dell'utente, i nomi
    # ufficiali sono le sigle stesse, non una parafrasi).
    _NICE_CLASS_NAMES = {
        "SuperficieCS": "Superficie (copertura del suolo)",
        "SuperficieCSProg": "Superficie (copertura del suolo, progetto)",
        "PCGiurisdizionale": "Punto di confine giurisdizionale",
        "DPSSP": "DPSSP (diritto per sé stante e permanente)",
        "CAP_localita": "CAP località",
    }

    def _check_geometry_validity(self, layer, table):
        """Conta le geometrie non valide (auto-intersezioni, anelli
        degeneri, ecc.) in un layer appena caricato, verificate con il motore
        geometrico di QGIS -
        lo stesso motore geometrico usato "sotto" da GDAL/OGR (il provider
        "ogr" con cui ogni layer di questo plugin viene aperto e' letto
        proprio tramite GDAL). Una geometria non valida non blocca il
        caricamento QGIS, ma puo' rompere in modo silenzioso passi molto
        piu' a valle - un poligono HATCH nel DXF costruito da un anello
        auto-intersecante, un calcolo di area/z-order sbagliato - dove la
        causa reale e' molto piu' difficile da individuare che qui, subito
        dopo l'import."""
        if not layer.isSpatial():
            return 0
        n_invalid = 0
        n_checked = 0
        examples = []
        for f in layer.getFeatures():
            geom = f.geometry()
            if geom is None or geom.isEmpty():
                continue
            n_checked += 1
            if not geom.isGeosValid():
                n_invalid += 1
                if len(examples) < 3:
                    examples.append(f.id())
        if n_invalid:
            self.log(f"   ⚠️ {n_invalid}/{n_checked} geometrie non valide in {table} "
                      f"- feature id esempio: {examples}", Qgis.Warning)
        return n_invalid

    def _validate_gpkg_with_gdal(self, gpkg_path):
        """Verifica il GeoPackage appena importato usando i binding Python
        di GDAL/OGR direttamente (osgeo.ogr, non tramite QgsVectorLayer):
        stesso principio di _validate_dxf per l'export, applicato qui
        all'import - ili2gpkg puo' uscire con codice 0 anche per un
        GeoPackage vuoto o strutturalmente incompleto (es. schema creato ma
        nessun dato importato per un ITF malformato/tronco)."""
        try:
            from osgeo import ogr, gdal
        except ImportError:
            self.log("   ⚠️ Binding Python di GDAL (osgeo) non disponibili in questo QGIS: verifica saltata.", Qgis.Warning)
            return True
        # Niente la mutazione globale delle eccezioni OGR (DontUse...): mutava
        # lo stato GDAL GLOBALE di tutta l'applicazione QGIS (non solo di
        # questa chiamata), cambiando il comportamento di ogni altro
        # plugin/codice che usa i binding dopo di noi. Per non inondare il log con l'errore ATTESO su un file
        # eventualmente corrotto si isola invece un error handler "quiet"
        # attorno alla sola ogr.Open, e il risultato si controlla per None
        # (con un except RuntimeError di sicurezza, nel caso le eccezioni
        # GDAL fossero state attivate globalmente da altri).
        gdal.PushErrorHandler("CPLQuietErrorHandler")
        try:
            ds = ogr.Open(str(gpkg_path))
        except RuntimeError:
            ds = None
        finally:
            gdal.PopErrorHandler()
        if ds is None:
            self.log(f"   ❌ GDAL non riesce ad aprire il GeoPackage: {gpkg_path}", Qgis.Critical)
            return False

        n_layers = ds.GetLayerCount()
        self.log(f"   📊 GDAL: {n_layers} tabelle nel GeoPackage")
        if n_layers == 0:
            self.log("   ❌ GeoPackage senza tabelle: import probabilmente fallito.", Qgis.Critical)
            ds = None
            return False

        total_features = 0
        empty_geom_layers = []
        n_geom_layers = 0
        for i in range(n_layers):
            lyr = ds.GetLayerByIndex(i)
            n = lyr.GetFeatureCount()
            total_features += n
            if lyr.GetGeomType() != ogr.wkbNone:
                n_geom_layers += 1
                if n == 0:
                    empty_geom_layers.append(lyr.GetName())

        self.log(f"   📊 GDAL: {n_geom_layers} tabelle con geometria, {total_features} feature totali")
        if empty_geom_layers:
            sample = ", ".join(empty_geom_layers[:10])
            more = ", ..." if len(empty_geom_layers) > 10 else ""
            self.log(f"   ℹ️ {len(empty_geom_layers)} tabelle con geometria ma 0 feature "
                      f"(normale per temi assenti in questo comune): {sample}{more}")
        ds = None
        return True

    # Pattern degli errori di vincolo di unicita' ili2db (es. due
    # Punto_di_confine con lo stesso IdentAN+Identificatore ma coordinate
    # diverse - dati sorgente difettosi, non un bug del plugin). Esempio
    # reale: "Error: line 1183131: MD01MUTI7MN95.Beni_immobili.
    # Punto_di_confine: tid 46560: Unique constraint MD01MUTI7MN95.
    # Beni_immobili.Punto_di_confine.Constraint2 is violated! Values
    # TI63201, 140602 already exist in Object: 40497"
    _ILI2GPKG_UNIQUE_RE = re.compile(
        r"^Error: line (\d+): ([\w.]+): tid (\d+): "
        r"Unique constraint ([\w.]+) is violated! "
        r"Values (.+) already exist in Object: (\d+)$"
    )

    # I messaggi che la validazione emette con le coordinate gia' dentro, e che
    # finora restavano semplici righe di log: "Warning: arc is straight at
    # (2719339.225, 1081435.757, NaN)". Sono geolocalizzati all'origine, e non
    # c'e' bisogno di andarli a cercare nell'ITF come per i vincoli di unicita'.
    _ILI2GPKG_LIVELLO_RE = re.compile(r"^(Error|Warning): (.+)$")

    # Quanto si aspetta, dopo l'ultima modifica del campo, prima di leggere il
    # file. Il campo cambia a ogni carattere digitato e dropEvent ci scrive
    # due volte quando i file trascinati sono due: senza attesa partirebbe una
    # lettura per ognuna, e sono 2.4 secondi di disco l'una. Aspettare toglie
    # l'occasione invece di gestirne le conseguenze.
    ATTESA_INVENTARIO_MS = 400

    def _avvia_inventario(self, *_args):
        """Programma la lettura dell'ITF, senza farla subito."""
        if not hasattr(self, "_timer_inventario"):
            self._timer_inventario = QTimer(self)
            self._timer_inventario.setSingleShot(True)
            self._timer_inventario.timeout.connect(self._esegui_inventario)
        # start() su un timer gia' avviato lo fa ripartire da capo: e' proprio
        # il comportamento voluto, l'ultima modifica azzera l'attesa.
        self._timer_inventario.start(self.ATTESA_INVENTARIO_MS)

    def _esegui_inventario(self):
        """Conta cosa c'e' nell'ITF, in un thread a parte."""
        percorso = self.txt_itf.text().strip()
        if not percorso or not os.path.isfile(percorso):
            self.lbl_inventario.setVisible(False)
            self._inventario_atteso = None
            return
        if percorso == getattr(self, "_inventario_atteso", None):
            return          # stesso file: o e' gia' in corso, o e' gia' scritto
        self._inventario_atteso = percorso
        self.lbl_inventario.setText("Leggo cosa c'è nel file…")
        self.lbl_inventario.setVisible(True)
        # parent=self: da li' in poi il thread e' di Qt e non serve tenerne un
        # riferimento Python. deleteLater lo fa sparire quando ha finito,
        # senza liste da potare e senza il rischio di potare quello sbagliato.
        worker = InventarioWorker(percorso, parent=self)
        worker.fatto.connect(lambda c, t, e, p=percorso: self._mostra_inventario(p, c, t, e))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _mostra_inventario(self, percorso, classi, totale, errore):
        """Scrive l'esito sotto il campo, se e' ancora quello che serve."""
        if getattr(self, "_inventario_atteso", None) != percorso:
            return                      # nel frattempo il file e' cambiato
        # Il fallimento si riconosce da 'classi' assente, non dal messaggio:
        # un'eccezione con str() vuoto passerebbe il controllo sul messaggio e
        # farebbe arrivare None dentro mancanti(), cioe' un TypeError dentro
        # uno slot - dove non si vede.
        if classi is None:
            # Non e' un errore dell'utente: l'importazione puo' andare
            # benissimo anche se questa lettura rapida non riesce.
            self.lbl_inventario.setText("Contenuto non leggibile in anteprima (%s)" % errore)
            return
        testo = _inventario.riassunto(classi, totale)
        assenti = _inventario.mancanti(classi)
        if assenti:
            testo += ("<br><span style='color:#E65100'>Mancano: %s</span>"
                      % ", ".join(assenti))
        # Il modello si dice SEMPRE, anche quando e' quello giusto: e' la
        # premessa di tutto quello che il plugin fa dopo, e vederla scritta
        # costa una riga mentre scoprirla sbagliata costa un'importazione.
        esito, trovato = _modello.controlla_itf(percorso)
        if esito == _modello.OK:
            testo += ("<br><span style='color:%s'>Modello %s ✔</span>"
                      % (self._verde_ok(), trovato))
        else:
            testo += ("<br><span style='color:%s'>%s</span>"
                      % (self._rosso_avviso(),
                         _modello.spiega(esito, trovato, "questo ITF")))
        self.lbl_inventario.setText(testo)
        self._registra_modello(percorso, esito, trovato)
        self.log("   📦 %s" % _inventario.riassunto(classi, totale, quante_in_testa=5))
        if assenti:
            self.log("   ⚠️ Nella consegna non ci sono: %s" % ", ".join(assenti),
                     Qgis.Warning)

    def _on_import_log_line(self, line):
        """Wrapper del log_signal del JavaWorker durante l'import: logga
        come sempre, ma intercetta e memorizza anche gli errori di vincolo
        di unicita' riconosciuti, per l'analisi automatica in caso di
        fallimento (vedi _analyze_import_errors), e ogni altro messaggio di
        validazione che porti con se' una coordinata."""
        self.log(line)
        livello = self._ILI2GPKG_LIVELLO_RE.match(line.strip())
        if livello and not self._ILI2GPKG_UNIQUE_RE.match(line.strip()):
            coord = self._extract_lv95_coords(line)
            if coord:
                if not hasattr(self, "_punti_validazione"):
                    self._punti_validazione = []
                self._punti_validazione.append({
                    "livello": "errore" if livello.group(1) == "Error" else "avviso",
                    "tipo": "validazione",
                    "messaggio": livello.group(2).strip(),
                    "x": coord[0], "y": coord[1], "tid": "", "riga": 0,
                })
        m = self._ILI2GPKG_UNIQUE_RE.match(line.strip())
        if m:
            self._import_unique_errors.append({
                "line": int(m.group(1)),
                "class_path": m.group(2),
                "tid": m.group(3),
                "constraint": m.group(4),
                "values": m.group(5),
                "existing_tid": m.group(6),
            })

    def _find_itf_table_block(self, itf_path, around_line, max_scan=3_000_000):
        """Trova inizio (riga 'TABL <Classe>') e fine (riga 'ETAB') del
        blocco tabella ITF che contiene 'around_line' (1-indexed). Legge il
        file una sola volta in streaming, senza caricarlo in memoria - un
        ITF di produzione puo' superare il milione di righe. Se il file
        supera 'max_scan' righe la scansione si ferma: il troncamento viene
        segnalato nel log, perche' un risultato mancante in quel caso NON
        significa "blocco non presente" ma solo "non cercato oltre"."""
        start_line = None
        start_name = None
        end_line = None
        with open(itf_path, "r", encoding="utf-8", errors="replace") as f:
            for i, raw in enumerate(f, start=1):
                if i > max_scan:
                    self.log(f"      ⚠️ Analisi ITF troncata a {max_scan:,} righe "
                              f"(limite di scansione): il blocco tabella cercato, se sta "
                              f"oltre questo punto, non e' stato letto.", Qgis.Warning)
                    break
                if raw.startswith("TABL"):
                    start_line = i
                    start_name = raw.strip()
                if i >= around_line and raw.startswith("ETAB"):
                    end_line = i
                    break
        return start_line, start_name, end_line

    @staticmethod
    def _extract_objects_by_tid(itf_path, start_line, end_line, tids):
        """Estrae le righe OBJE grezze per gli 'tid' cercati, limitandosi
        all'intervallo [start_line, end_line] (un solo blocco TABL...ETAB,
        non l'intero file)."""
        wanted = set(tids)
        found = {}
        with open(itf_path, "r", encoding="utf-8", errors="replace") as f:
            for i, raw in enumerate(f, start=1):
                if i < start_line:
                    continue
                if i > end_line or len(found) == len(wanted):
                    break
                if raw.startswith("OBJE"):
                    parts = raw.split()
                    if len(parts) >= 2 and parts[1] in wanted:
                        found[parts[1]] = raw.strip()
        return found

    @staticmethod
    def _extract_lv95_coords(obje_line):
        """Euristica indipendente dalla classe ILI - resta un'euristica,
        pensata SOLO per arricchire i messaggi di errore dell'analisi
        duplicati (coordinate indicative nei log), non per ricostruire
        geometrie vere: cerca nella riga OBJE una COPPIA di numeri con la
        virgola che compaiano consecutivamente sulla STESSA riga e cadano,
        nell'ordine, nei range LV95 svizzeri E [2'480'000, 2'840'000] e
        N [1'070'000, 1'310'000] (estremi nazionali con margine). La versione
        precedente prendeva i primi due numeri "plausibili" dovunque nella
        riga, con range piu' larghi e SENZA richiedere l'adiacenza: falsi
        positivi su quote/attributi numerici erano facili (es. una quota
        1234567.89 seguita da un valore 2450000.0). Piu' affidabile che
        assumere la posizione esatta del campo Geometria, che varia da
        classe a classe."""
        nums = re.findall(r"-?\d+\.\d+", obje_line)
        for i in range(len(nums) - 1):
            e, n = float(nums[i]), float(nums[i + 1])
            if 2_480_000 <= e <= 2_840_000 and 1_070_000 <= n <= 1_310_000:
                return e, n
        return None

    def crea_layer_errori_validazione(self):
        """Mette sulla mappa i problemi trovati dalla validazione.

        La scheda "Errori nei dati" dice COSA non va; questo layer dice DOVE, e
        sono due domande diverse. Con due punti di confine che hanno lo stesso
        identificativo, sapere che distano 8 metri o 8 chilometri cambia cosa
        si va a controllare sul terreno - e per arrivarci finora bisognava
        copiare le coordinate dal log e incollarle a mano.

        I punti arrivano da due strade: le violazioni di unicita', per cui le
        coordinate si vanno a leggere nell'ITF (vedi _analyze_import_errors), e
        i messaggi che la coordinata ce l'hanno gia' dentro, come "arc is
        straight at (...)". Ritorna il layer, o None se non c'e' niente da
        mostrare."""
        punti = getattr(self, "_punti_validazione", None)
        if not punti:
            return None
        layer = QgsVectorLayer(
            "Point?crs=EPSG:2056&field=livello:string(10)&field=tipo:string(40)"
            "&field=messaggio:string(400)&field=tid:string(20)&field=riga:integer",
            "Errori di validazione", "memory")
        # Lo stesso difetto viene segnalato piu' volte: sul comune di prova le
        # otto avvertenze "arc is straight" stanno su DUE posizioni sole,
        # ripetute quattro volte ciascuna (una per anello che passa di li').
        # Impilare quattro punti identici non aggiunge niente e rende il clic
        # sulla mappa ambiguo, quindi restano quelli distinti.
        visti = set()
        distinti = []
        for p in punti:
            chiave = (p["livello"], p["tipo"], p["messaggio"],
                      round(p["x"], 3), round(p["y"], 3))
            if chiave in visti:
                continue
            visti.add(chiave)
            distinti.append(p)
        if len(distinti) < len(punti):
            self.log("   ℹ️ %d segnalazioni ripetute sulla stessa posizione accorpate"
                     % (len(punti) - len(distinti)))
        punti = distinti
        feature_list = []
        for p in punti:
            f = QgsFeature(layer.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(p["x"], p["y"])))
            f.setAttributes([p["livello"], p["tipo"], p["messaggio"],
                             str(p.get("tid") or ""), int(p.get("riga") or 0)])
            feature_list.append(f)
        layer.dataProvider().addFeatures(feature_list)
        layer.updateExtents()
        self._stile_errori_validazione(layer)
        QgsProject.instance().addMapLayer(layer)
        n_err = sum(1 for p in punti if p["livello"] == "errore")
        self.log("   🗺️ Layer «Errori di validazione»: %d punti (%d errori, %d avvisi). "
                 "Clic destro sul layer → Zoom sul layer per vederli."
                 % (len(punti), n_err, len(punti) - n_err))
        return layer

    def _stile_errori_validazione(self, layer):
        """Rosso gli errori, arancione gli avvisi, e l'etichetta col messaggio:
        un puntino senza scritta costringe comunque ad aprire la tabella."""
        from qgis.core import QgsMarkerSymbol, QgsRuleBasedRenderer
        radice = QgsRuleBasedRenderer.Rule(None)
        for livello, colore in (("errore", "198,40,40"), ("avviso", "230,145,0")):
            simbolo = QgsMarkerSymbol.createSimple({
                "name": "circle", "color": colore + ",180",
                "outline_color": "255,255,255", "outline_width": "0.4", "size": "4"})
            regola = QgsRuleBasedRenderer.Rule(simbolo, filterExp='"livello" = \'%s\'' % livello,
                                               label=livello)
            radice.appendChild(regola)
        layer.setRenderer(QgsRuleBasedRenderer(radice))

    def _analyze_import_errors(self, itf_path):
        """Analizza gli errori di vincolo di unicita' catturati durante
        l'import (vedi _on_import_log_line) e propone un riepilogo leggibile
        invece di lasciare solo il log Java grezzo: per ogni conflitto,
        cerca le due righe OBJE coinvolte nell'ITF originale e - quando
        possibile - le coordinate e la distanza tra i due punti, per capire
        subito se e' un vero doppione (stesso punto, due tid) o una
        collisione di numerazione (punti diversi, stesso identificativo)."""
        errors = self._import_unique_errors
        if not errors:
            self.log("   ℹ️ Nessun errore di vincolo di unicità riconosciuto nel log sopra: "
                      "controlla i messaggi \"Error:\" per il dettaglio.", Qgis.Warning)
            return

        self.log(f"\n🔬 Analisi automatica: {len(errors)} violazione/i di vincolo di unicità")
        # Le stesse informazioni vanno anche nella scheda "Errori nei dati":
        # in console un elenco di venti conflitti e' un muro di testo, in
        # tabella e' una lista di cose da sistemare. Il log resta perche' porta
        # il dettaglio esteso (coordinate, distanza) che in tabella non sta.
        righe_tabella = []
        for err in errors:
            table = err["class_path"].split(".")[-1]
            riga = {
                "tabella": table,
                "vincolo": err["constraint"].split(".")[-1],
                "valori": err["values"],
                "tid": "%s ↔ %s" % (err["tid"], err["existing_tid"]),
                "riga": err["line"],
                "diagnosi": "",
            }
            righe_tabella.append(riga)
            self.log(f"\n   📋 Tabella: {table}  |  Vincolo: {err['constraint'].split('.')[-1]}")
            self.log(f"      Valori duplicati: {err['values']}")
            self.log(f"      Oggetto nuovo (tid {err['tid']}, riga ITF {err['line']}) "
                      f"in conflitto con oggetto già importato (tid {err['existing_tid']})")
            try:
                start, start_name, end = self._find_itf_table_block(itf_path, err["line"])
                if not start or not end:
                    self.log("      ⚠️ Non trovo i confini del blocco tabella nell'ITF per il dettaglio.", Qgis.Warning)
                    riga["diagnosi"] = "blocco tabella non individuato nell'ITF"
                    continue
                objs = self._extract_objects_by_tid(itf_path, start, end, [err["tid"], err["existing_tid"]])
                coord_a = self._extract_lv95_coords(objs[err["tid"]]) if err["tid"] in objs else None
                coord_b = self._extract_lv95_coords(objs[err["existing_tid"]]) if err["existing_tid"] in objs else None
                if coord_a and coord_b:
                    dist = ((coord_a[0] - coord_b[0]) ** 2 + (coord_a[1] - coord_b[1]) ** 2) ** 0.5
                    # Gli stessi due punti finiscono anche sulla mappa: la
                    # tabella dice COSA non va, il layer dice DOVE.
                    for tid, (x, y) in ((err["tid"], coord_a), (err["existing_tid"], coord_b)):
                        self._punti_validazione.append({
                            "livello": "errore", "tipo": "vincolo di unicità",
                            "messaggio": "%s: valori duplicati %s"
                                         % (err["constraint"].split(".")[-1], err["values"]),
                            "x": x, "y": y, "tid": tid, "riga": err["line"],
                        })
                    self.log(f"      Coordinate: A=({coord_a[0]:.1f}, {coord_a[1]:.1f})  "
                              f"B=({coord_b[0]:.1f}, {coord_b[1]:.1f})  →  distanza {dist:.0f} m")
                    if dist < 1.0:
                        riga["diagnosi"] = "doppione: stesso punto, distanza %.1f m" % dist
                        self.log("      → Stesso punto fisico registrato due volte (probabile doppione da rimuovere).")
                    else:
                        riga["diagnosi"] = ("collisione di numerazione: punti diversi, "
                                            "distanza %.0f m" % dist)
                        self.log("      → Punti fisicamente DIVERSI: collisione di numerazione "
                                  "(due punti distinti con lo stesso identificativo), non un doppione.")
                else:
                    riga["diagnosi"] = "coordinate non estratte (formato riga inatteso)"
                    self.log("      ℹ️ Coordinate non estratte automaticamente (formato riga inatteso).")
            except OSError as e:
                riga["diagnosi"] = "lettura ITF fallita"
                self.log(f"      ⚠️ Lettura ITF fallita durante l'analisi: {e}", Qgis.Warning)

        self._riempi_tabella_errori(righe_tabella)
        self.crea_layer_errori_validazione()
        self.log("\n   💡 Non è un problema risolvibile qui: i dati sorgente vanno corretti da chi "
                  "gestisce l'ITF (assegna un identificativo diverso a uno dei due punti). "
                  "Per procedere comunque con l'import (i duplicati restano nel GeoPackage così come sono), "
                  "attiva \"Disabilita validazione\" nei parametri avanzati e rilancia. "
                  "L'elenco completo è nella scheda \"Errori nei dati\".")

    def run_import(self):
        # Guardia contro il doppio avvio: un secondo worker in parallelo
        # scriverebbe sullo stesso GPKG del primo, corrompendolo.
        if _vivo(getattr(self, "worker", None)) and self.worker.isRunning():
            QMessageBox.warning(self, "Operazione in corso",
                                "Un processo e' gia' in esecuzione: attendi che termini "
                                "(o chiudi la finestra per interromperlo).")
            self.log("⚠️ Avvio rifiutato: un processo e' gia' in esecuzione.", Qgis.Warning)
            return

        jar_path = Path(self.txt_jar.text().strip())
        itf_path = Path(self.txt_itf.text().strip())
        gpkg_path = Path(self.txt_gpkg.text().strip())
        # Il modello si prende dalla costante, non dal campo: il campo lo
        # mostra soltanto (vedi MODELLO_ILI).
        ili_path = Path(MODELLO_ILI)
        if not ili_path.is_file():
            QMessageBox.warning(self, "Modello mancante",
                                "Il modello INTERLIS in dotazione non e' presente "
                                "nell'installazione del plugin:\n%s\n\n"
                                "Reinstalla %s." % (ili_path, NOME_PLUGIN))
            self.log("   ❌ Modello in dotazione mancante: %s" % ili_path, Qgis.Critical)
            return
        # Il modello DEI DATI, che e' un'altra cosa dal .ili in dotazione: qui
        # si controlla che l'ITF sia davvero ticinese. La spia del campo lo dice
        # gia', ma il file puo' essere cambiato da allora e un'importazione dura
        # minuti - riletto qui, costa un istante.
        if not self._controlla_modello_prima_di(str(itf_path), "l'ITF da importare"):
            return
        self._last_itf_path = itf_path
        self._import_unique_errors = []
        # Azzerato a ogni importazione, se no i punti della volta prima
        # resterebbero sulla mappa a indicare errori gia' corretti.
        self._punti_validazione = []

        self.log("=" * 60)
        self.log("🚀 AVVIO IMPORTAZIONE")
        self.log("=" * 60)
        self.log(f"📁 JAR: {jar_path}")
        self.log(f"📄 ITF: {itf_path}")
        self.log(f"📋 Modello ILI: {ili_path}")
        self.log(f"💾 Output GPKG: {gpkg_path}")

        if not all([jar_path.name, itf_path.name, gpkg_path.name, ili_path.name]):
            QMessageBox.warning(self, "Dati Mancanti", "Compila tutti i campi.")
            self.log("❌ Campi mancanti!")
            return

        java_exe = self.find_java()
        if not java_exe:
            QMessageBox.critical(self, "Errore", "Java non trovato.")
            self.log("❌ Java non trovato nel sistema!")
            return
        self.log(f"☕ Java trovato: {java_exe}")

        if gpkg_path.exists():
            # Prima di cancellare un file esistente, DUE salvaguardie (il
            # vecchio GPKG veniva sovrascritto senza alcuna conferma ne'
            # verifica del contenuto):
            # (a) deve essere DAVVERO un GeoPackage/SQLite (estensione +
            #     header magico, vedi _looks_like_gpkg): un percorso
            #     sbagliato digitato nel campo output non deve distruggere
            #     un file che non e' un precedente output del plugin.
            if not _looks_like_gpkg(gpkg_path):
                self.log(f"❌ Il file esistente non e' un GeoPackage valido "
                          f"(estensione .gpkg e/o header SQLite mancanti): {gpkg_path}. "
                          "Cancellazione rifiutata - import annullato.", Qgis.Critical)
                return
            # (b) conferma esplicita dell'utente (default "No": la scelta
            #     distruttiva deve essere deliberata).
            reply = QMessageBox.warning(
                self, "Sovrascrittura GeoPackage",
                f"Il file GeoPackage esistente sara' sovrascritto:\n{gpkg_path}\n\n"
                "Continuare?",
                _MB_SI | _MB_NO, _MB_NO)
            if reply != _MB_SI:
                self.log("⏹️ Import annullato dall'utente (file esistente non sovrascritto).")
                return
            try:
                gpkg_path.unlink()
                self.log(f"🗑️ Rimosso vecchio GPKG: {gpkg_path.name}")
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Impossibile cancellare il GPKG.\n{e}")
                self.log(f"❌ Errore cancellazione GPKG: {str(e)}")
                return

        model_name = ili_path.stem
        model_dir = ili_path.parent
        self.log(f"📋 Nome modello: {model_name}")
        self.log(f"📂 Cartella modello: {model_dir}")

        tol_params = []
        if self.group_adv.isChecked():
            if self.chk_sql_null.isChecked(): tol_params.append("--sqlEnableNull")
            if self.chk_sql_text.isChecked(): tol_params.append("--sqlColsAsText")
            if self.chk_skip_poly.isChecked(): tol_params.append("--skipPolygonBuilding")
            if self.chk_skip_ref.isChecked(): tol_params.append("--skipReferenceErrors")
            if self.chk_skip_geom.isChecked(): tol_params.append("--skipGeometryErrors")
            if self.chk_disable_val.isChecked(): tol_params.append("--disableValidation")
        self.log(f"⚙️ Parametri tolleranza: {tol_params if tol_params else 'Nessuno'}")

        base_cmd = [java_exe, "-jar", str(jar_path), "--dbfile", str(gpkg_path),
                    "--modeldir", str(model_dir), "--models", model_name,
                    "--defaultSrsCode", "2056", "--nameByTopic"]

        # --createMetaInfo: crea t_ili2db_column_prop, da cui ricaviamo le relazioni
        # padre/figlio (es. PosFondo -> Fondo) per etichette e join, senza dover
        # imporre vincoli FK reali (--createFk) che rifiuterebbero l'import in
        # presenza di riferimenti mancanti/dati tolleranti errori.
        cmd_schema = base_cmd + ["--schemaimport", "--createMetaInfo"] + tol_params
        self.log("\n⚙️ FASE 1: Creazione schema database...")
        self.log(f"   Comando: {' '.join(cmd_schema)}")
        self.btn_import.setEnabled(False)
        self.btn_geobau.setEnabled(False)
        self._inizio_lavoro("Fase 1: creazione schema")

        self.worker = JavaWorker(cmd_schema, "schemaimport", parent=self)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.log_signal.connect(self._on_import_log_line)
        self.worker.finished_signal.connect(self.on_schema_finished)
        self.worker.start()

        # Il file .itf va messo per ULTIMO: l'usage di ili2gpkg e'
        # "[Options] [file.xtf]" e con tol_params non vuoto (es.
        # --disableValidation) mettere il file prima delle opzioni fa
        # fallire il parsing della CLI ("invalid placed argument").
        self._pending_import_cmd = base_cmd + ["--import"] + tol_params + [str(itf_path)]

    def on_schema_finished(self, returncode, task_type):
        self.log(f"\n📊 Risultato FASE 1: Codice ritorno = {returncode}")
        if returncode == 0 and task_type == "schemaimport":
            self.log("✅ Schema creato con successo!")
            self.log("\n📥 FASE 2: Importazione dati dal file ITF...")
            self.log(f"   Comando: {' '.join(self._pending_import_cmd)}")
            self._inizio_lavoro("Fase 2: importazione dati")
            self.worker = JavaWorker(self._pending_import_cmd, "dataimport", parent=self)
            self.worker.finished.connect(self.worker.deleteLater)
            self.worker.log_signal.connect(self._on_import_log_line)
            self.worker.finished_signal.connect(self.on_data_finished)
            self.worker.start()
        else:
            self.log(f"❌ Creazione schema fallita (Codice: {returncode}).", Qgis.Critical)
            self._fine_lavoro()
            self.btn_import.setEnabled(True)
            self.btn_geobau.setEnabled(True)

    def on_data_finished(self, returncode, task_type):
        self.log(f"\n📊 Risultato FASE 2: Codice ritorno = {returncode}")
        self.btn_import.setEnabled(True)
        self.btn_geobau.setEnabled(True)
        if returncode == 0:
            self.log("✅ Importazione dati completata!")
            self.log("\n🔎 Verifica GeoPackage (GDAL)...")
            self._validate_gpkg_with_gdal(self.txt_gpkg.text().strip())
            self.log("\n" + "=" * 60)
            self.log("🎨 AVVIO APPLICAZIONE LEGENDA")
            self.log("=" * 60)
            self.lbl_fase.setText("Fase 3: legenda e stili")
            self.load_and_style_layers()
        else:
            self.log(f"❌ Importazione dati fallita (Codice: {returncode}).", Qgis.Critical)
            if self._import_unique_errors:
                self._analyze_import_errors(self._last_itf_path)
        self._fine_lavoro()

    def load_and_style_layers(self):
        """Carica i layer dal GeoPackage con approccio robusto per QGIS 4.0."""
        gpkg_path = Path(self.txt_gpkg.text().strip())
        self.log(f"\n📂 GeoPackage: {gpkg_path}")

        if not gpkg_path.exists():
            self.log(f"❌ File GeoPackage non trovato: {gpkg_path}", Qgis.Critical)
            return

        # Il modello anche qui, che e' il passo in cui puo' arrivare un
        # GeoPackage importato altrove: ili2gpkg lo registra in T_ILI2DB_MODEL,
        # e da li' si legge senza dover riaprire l'ITF (che potrebbe non esserci
        # nemmeno piu').
        #
        # QUI SI AVVISA E SI PROSEGUE, mentre sull'ITF si blocca. Non e' una
        # svista: importare e convertire sono operazioni lunghe che non possono
        # riuscire con il modello sbagliato, e fermarle risparmia minuti;
        # caricare dei layer e' invece la cosa che permette all'utente di
        # GUARDARE cosa gli e' arrivato. Rifiutarsi di mostrarglielo non lo
        # aiuterebbe - gli stili non troveranno le tabelle attese, e l'avviso
        # dice perche' invece di lasciarlo davanti a un progetto vuoto.
        esito_mod, trovato_mod = self._modello_di(str(gpkg_path), e_gpkg=True)
        if esito_mod == _modello.OK:
            self.log("   🧬 Modello del GeoPackage: %s (quello atteso)" % trovato_mod)
        else:
            self.log("   ⚠️ %s" % _modello.spiega(esito_mod, trovato_mod,
                                                  "il GeoPackage"), Qgis.Warning)
            if _modello.e_bloccante(esito_mod):
                QMessageBox.warning(self, "Modello dei dati",
                                    _modello.spiega(esito_mod, trovato_mod,
                                                    "il GeoPackage"))

        # Rimuovi i layer caricati da un'esecuzione precedente in questa stessa
        # sessione QGIS. Senza questo, i layer vecchi restano nel progetto ma
        # fuori dalla nuova lista di ordine di disegno (zorder_layers): QGIS
        # aggiunge in automatico ogni layer assente dall'ordine personalizzato
        # IN CODA (= primo piano), coprendo i layer nuovi correttamente
        # ordinati - indipendentemente dal tema. E' questo, non un errore
        # nella tabella di priorita', a spiegare "punti di confine sotto le
        # linee di confine/copertura del suolo/oggetti singoli" quando il
        # plugin viene rilanciato piu' volte senza riavviare QGIS.
        stale_layers = getattr(self, "loaded_layers", None)
        if stale_layers:
            stale_ids = [lyr.id() for lyr in stale_layers
                         if lyr and QgsProject.instance().mapLayer(lyr.id())]
            if stale_ids:
                QgsProject.instance().removeMapLayers(stale_ids)
                self.log(f"🧹 Rimossi {len(stale_ids)} layer da un'esecuzione precedente")
        self.loaded_layers = []

        # Diagnostica simboli: tutti i simboli per punti di confine, PFP/PFA,
        # oggetti puntiformi e le trame a punti (Vigna/Canneto/Torbiera) usano
        # ora il set ufficiale Cadastra Symbol SVG 2024 (cartelle symbols/normal
        # e symbols/mask dentro il plugin), non piu' il font "CadastraSymbol":
        # verifichiamo solo che le cartelle esistano e contengano gli SVG attesi,
        # altrimenti i simboli non trovati ricadono silenziosamente su un
        # cerchio generico (vedi _svg_symbol_path).
        n_normal = len([f for f in os.listdir(os.path.join(SYMBOLS_DIR, "normal"))
                        if f.lower().endswith(".svg")]) if os.path.isdir(os.path.join(SYMBOLS_DIR, "normal")) else 0
        n_mask = len([f for f in os.listdir(os.path.join(SYMBOLS_DIR, "mask"))
                      if f.lower().endswith(".svg")]) if os.path.isdir(os.path.join(SYMBOLS_DIR, "mask")) else 0
        if n_normal and n_mask:
            self.log(f"🖼️ Simboli SVG Cadastra trovati: {n_normal} normali, {n_mask} maschera (cartella {SYMBOLS_DIR})")
        else:
            self.log(f"⚠️ ATTENZIONE: cartella simboli SVG mancante o vuota ({SYMBOLS_DIR}). "
                      "I simboli per punti di confine, PFP/PFA, oggetti puntiformi e le trame a "
                      "punti (Vigna/Canneto/Torbiera) ricadranno su un cerchio generico.", Qgis.Warning)

        # 1. Leggi tabelle geometriche e tabelle attributo
        self.log("\n📋 Fase 1: Lettura tabelle geometriche...")
        geom_tables = {}
        attr_tables = []
        try:
            with sqlite3.connect(gpkg_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT table_name, column_name, geometry_type_name FROM gpkg_geometry_columns")
                rows = cursor.fetchall()
                self.log(f"   Trovate {len(rows)} tabelle con geometria")
                for row in rows:
                    geom_tables[row[0]] = (row[1], row[2])
                    self.log(f"   📋 {row[0]} | {row[1]} | {row[2]}")

                # Tabelle SENZA geometria (es. Fondo, Nome_del_luogo, Oggetto_condotta):
                # nel modello ILI il testo di molte etichette (numero di fondo, nomi,
                # ecc.) vive su queste tabelle "padre", non su quelle con geometria
                # che compaiono in gpkg_geometry_columns. Vanno comunque caricate
                # (senza stile/etichetta propri) per poter fare da sorgente ai join.
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                all_tables = [r[0] for r in cursor.fetchall()]
                skip_prefixes = ("gpkg_", "sqlite_", "t_ili2db_", "t_key_object")
                attr_tables = [t for t in all_tables
                               if t not in geom_tables and not t.lower().startswith(skip_prefixes)]
                self.log(f"   Trovate {len(attr_tables)} tabelle attributo (senza geometria)")
        except Exception as e:
            self.log(f"❌ Errore lettura schema GeoPackage: {str(e)}", Qgis.Critical)
            return

        if not geom_tables:
            self.log("⚠️ Nessuna tabella con geometria trovata.", Qgis.Warning)
            return

        # 2. Carica layer con approccio robusto
        self.log("\n🎨 Fase 2: Caricamento layer...")
        self.log(f"   Modalità: {'GB' if self.product_mode == 'gb' else 'PB-MU'}")

        loaded_layers = []
        pending_labels = []  # (layer, t_low, class_name) da etichettare dopo i join (Fase 3)
        pending_genere_rebind = []  # layer i cui filtri su "Genere" vanno ri-agganciati dopo i join
        zorder_layers = []  # (layer, t_low) per l'ordine di disegno finale (Fase 5)
        saltate = []  # (tabella, motivo) - alimenta il riquadro di esito
        crs_2056 = QgsCoordinateReferenceSystem("EPSG:2056")
        mode = self.product_mode

        for idx, (table, (geom_col, geom_type_name)) in enumerate(geom_tables.items(), 1):
            # Un solo layer problematico (dato inatteso, valore mai visto prima)
            # non deve bloccare tutti gli altri: senza questo try/except
            # un'eccezione qui abortiva l'intero metodo, saltando join/etichette/
            # ordine di disegno anche per i layer gia' processati correttamente.
            try:
                self.log(f"\n{'─' * 60}")
                self.log(f"🗂️ Layer {idx}/{len(geom_tables)}: {table}")
                self.log(f"   Colonna geom: {geom_col} | Tipo: {geom_type_name}")

                # APPROCCIO ROBUSTO: usa percorso diretto invece di QgsDataSourceUri
                layer_uri = f"{gpkg_path}|layername={table}"
                layer = QgsVectorLayer(layer_uri, table, "ogr")

                if not layer.isValid():
                    self.log("   ❌ Layer non valido con formato OGR diretto!", Qgis.Critical)
                    # Prova alternativa con QgsDataSourceUri
                    self.log("   🔄 Tentativo alternativo con QgsDataSourceUri...")
                    uri = QgsDataSourceUri()
                    uri.setDatabase(str(gpkg_path))
                    uri.setDataSource("", table, geom_col)
                    layer = QgsVectorLayer(uri.uri(), table, "ogr")

                    if not layer.isValid():
                        self.log("   ❌ Anche QgsDataSourceUri fallito", Qgis.Critical)
                        saltate.append((table, "layer non valido"))
                        continue

                # Imposta CRS
                if not layer.crs().isValid():
                    layer.setCrs(crs_2056)
                    self.log("   🌐 CRS impostato: EPSG:2056")
                else:
                    self.log(f"   ✅ CRS: {layer.crs().authid()}")

                # Aggiungi al progetto
                QgsProject.instance().addMapLayer(layer)
                loaded_layers.append(layer)
                t_low = table.lower()
                zorder_layers.append((layer, t_low))
                self.log("   ✅ Layer aggiunto al progetto")

                # Vedi _check_geometry_validity: geometrie non valide possono
                # rompere in modo silenzioso passi piu' a valle.
                self._check_geometry_validity(layer, table)

                # Nome leggibile nel pannello Layers - vedi _nice_layer_name.
                # class_name calcolato una sola volta qui e riusato piu'
                # sotto per lo stile, invece di rileggerlo.
                ili_class = self.get_ili_class(gpkg_path, table)
                if ili_class:
                    # Le geometrie secondarie (LINEATTR, es. "Origine_piano_sinottico")
                    # producono un IliName con un riferimento tra parentesi alla classe
                    # base, es. "...Layout_del_piano.Origine_piano_sinottico(...Layout_del_piano)":
                    # va scartato, altrimenti lo split('.') prende l'ultimo segmento del
                    # riferimento tra parentesi invece del vero nome della classe.
                    ili_class_main = ili_class.split('(')[0]
                    class_name = ili_class_main.split('.')[-1] if ili_class_main else ""
                else:
                    class_name = ""
                layer.setName(self._nice_layer_name(class_name, table))

                # Applica stili (logica in cascata a 3 livelli: QML accanto
                # al GPKG -> Gestore Stili di QGIS -> renderer generato).
                # Esisteva un primo livello "QML in styles/gb|bp/ del plugin",
                # rimosso: la cartella styles/ non e' mai esistita nel plugin,
                # quindi il ramo era codice morto (controllo + log su ogni
                # layer senza possibilita' di match).
                self.log(f"\n   🔍 Ricerca stile per: {table}")
                style_applied = False

                # 1. Cartella del GeoPackage
                qml_file_gpkg = gpkg_path.parent / f"{table}.qml"
                self.log(f"   1️⃣ Controllo: {qml_file_gpkg}")
                if qml_file_gpkg.exists():
                    if load_qml_style(layer, qml_file_gpkg, self.log):
                        style_applied = True
                        self.log("   ✅ Stile da cartella GPKG")

                # 2. Gestore Stili di QGIS
                if not style_applied:
                    self.log("   2️⃣ Controllo Gestore Stili")
                    if apply_style_from_manager(layer, table, self.log):
                        style_applied = True
                        self.log("   ✅ Stile da Gestore Stili")

                # 3. Fallback: stile generato automaticamente
                if not style_applied:
                    self.log("   3️⃣ Applicazione stile automatico")
                    # t_low/ili_class/class_name gia' calcolati sopra (per il
                    # nome leggibile del layer, vedi _nice_layer_name): non
                    # vanno ricalcolati, solo loggati qui per diagnostica.
                    if ili_class:
                        ili_class_main = ili_class.split('(')[0]
                        topic = ili_class_main.split('.')[-2] if len(ili_class_main.split('.')) >= 2 else ""
                        self.log(f"   📋 Classe ILI: {ili_class}")
                        self.log(f"   📋 Nome classe: {class_name}")
                        self.log(f"   📋 Topic: {topic}")
                    else:
                        self.log("   ⚠️ Classe ILI non trovata")

                    renderer = self._get_renderer_for_table(class_name, t_low, mode, geom_type_name, layer)

                    if renderer:
                        layer.setRenderer(renderer)
                        self.log("   ✅ Renderer applicato")
                        self._nascondi_legenda_se_invisibile(layer, renderer)

                        if hasattr(renderer, 'rootRule'):
                            root_rule = renderer.rootRule()
                            num_rules = len(root_rule.children()) if root_rule else 0
                            self.log(f"   📊 Regole: {num_rules}")

                        # Diagnostica: elenca i valori distinti di "Genere" realmente
                        # presenti in SuperficieCS, per verificare se bosco/vigna/ecc.
                        # esistono davvero in questo dataset con l'ortografia attesa,
                        # invece di continuare a ipotizzare un bug di rendering.
                        if "superficiecs" in t_low:
                            try:
                                idx = layer.fields().indexFromName("genere")
                                valori = sorted({str(f.attribute(idx)) for f in layer.getFeatures()}) if idx >= 0 else []
                                self.log(f"   🔎 Valori distinti 'Genere' in SuperficieCS: {valori}")
                            except Exception as e:
                                self.log(f"   ⚠️ Diagnostica Genere fallita: {e}", Qgis.Warning)

                        # Diagnostica: come sopra per SuperficieCS, ma per "segno"/
                        # "cippo_giurisdizionale" su Punto_di_confine/PCGiurisdizionale -
                        # se un valore di "segno" non compare tra quelli attesi da
                        # _gen_stile_punto_di_confine (termine_cippo/termine_artificiale/
                        # bullone/campanile/croce_scolpito/croce/scolpito/tubo/
                        # palo_picchetto/non_materializzato, eventualmente come percorso
                        # puntato es. "altro.campanile"), il punto ricade sul fallback
                        # "Punto generico" (cerchio pieno indifferenziato) invece del
                        # glifo E/F/G/H/I atteso dal piano per il registro fondiario.
                        if "punto_di_confine" in t_low or "pcgiurisdizionale" in t_low:
                            try:
                                idx = layer.fields().indexFromName("segno")
                                valori = sorted({str(f.attribute(idx)) for f in layer.getFeatures()}) if idx >= 0 else []
                                self.log(f"   🔎 Valori distinti 'segno' in {table}: {valori}")
                                idx_g = layer.fields().indexFromName("cippo_giurisdizionale")
                                if idx_g >= 0:
                                    valori_g = sorted({str(f.attribute(idx_g)) for f in layer.getFeatures()})
                                    self.log(f"   🔎 Valori distinti 'cippo_giurisdizionale' in {table}: {valori_g}")
                            except Exception as e:
                                self.log(f"   ⚠️ Diagnostica Segno fallita: {e}", Qgis.Warning)

                        # Etichette per layer testuali: rimandate a dopo i join (Fase 3),
                        # perche' il testo da scrivere vive quasi sempre sulla tabella
                        # padre e diventa un campo del layer solo dopo il join.
                        if "punto_quotato" in t_low or any(k in t_low for k, *_ in TEXT_LABEL_RULES):
                            self.log("   📝 Etichette rimandate a dopo i join")
                            pending_labels.append((layer, t_low, class_name))

                        # Elemento_puntiforme/Elemento_lineare/Elemento_con_superficie non
                        # hanno un campo "Genere" proprio: vive sulla tabella padre
                        # Oggetto_singolo (confermato da Sym_MD01MUTI7MN95.gni), disponibile
                        # solo dopo il join. Le regole sono gia' costruite su "Genere":
                        # vanno solo ri-agganciate al campo giusto dopo la Fase 3.
                        # SimboloSuperficieCS e' nella stessa situazione (FK a SuperficieCS,
                        # niente campo Genere proprio - vedi commento ILI subito prima di
                        # "TABLE SimboloSuperficieCS"), ma la sua rotazione (Ori) e' invece
                        # un campo NATIVO della tabella stessa, gia' disponibile prima dei join.
                        if any(k in t_low for k in ["elemento_puntiforme", "elemento_lineare",
                                                     "elemento_con_superficie", "simbolosuperficiecs"]):
                            self.log("   🔗 Filtri su \"Genere\" da ri-agganciare dopo i join")
                            pending_genere_rebind.append(layer)
                    else:
                        self.log("   ⚠️ Nessun renderer specifico", Qgis.Warning)
            except Exception as e:
                self.log(f"   ❌ Errore imprevisto sul layer '{table}': {e}", Qgis.Critical)
                self.log(f"   ⏭️ Layer '{table}' saltato, proseguo con gli altri", Qgis.Warning)
                saltate.append((table, str(e)))
                continue

        # 2bis. Carica le tabelle attributo (senza geometria): niente stile/etichetta
        # proprio, servono solo come sorgente per i join delle etichette (Fase 3bis).
        attr_layers = []  # layer attributo puri (per il gruppo dedicato nell'albero, vedi Fase 4bis)
        if attr_tables:
            self.log("\n📎 Fase 2bis: Caricamento tabelle attributo (per i join)...")
            for table in attr_tables:
                layer_uri = f"{gpkg_path}|layername={table}"
                layer = QgsVectorLayer(layer_uri, table, "ogr")
                if layer.isValid():
                    QgsProject.instance().addMapLayer(layer)
                    loaded_layers.append(layer)
                    attr_layers.append(layer)
                    self.log(f"   ✅ {table}")
                else:
                    self.log(f"   ⚠️ Tabella attributo non valida: {table}", Qgis.Warning)
                    saltate.append((table, "tabella attributo non valida"))

        self.loaded_layers = loaded_layers
        self.log(f"\n{'═' * 60}")
        self.log(f"✅ Caricamento completato: {len(loaded_layers)} layer")
        self.log(f"{'═' * 60}")

        # Il comune per il cartiglio della planimetria si legge ORA dai dati
        # appena importati: e' un'iscrizione obbligatoria (cap.1.5.7) e il
        # modello la contiene, quindi non ha senso farla digitare.
        comuni = self.aggiorna_comuni_da_dati()
        data = getattr(self, "_data_dai_dati", "")
        if data:
            self.log("   📅 \"Stato al\" %s (%s)"
                     % (data, getattr(self, "_origine_data", "?")))
        else:
            self.log("   ⚠️ Nessuna data ricavabile da ITF o dati: "
                     "\"Stato al\" resta quella proposta", Qgis.Warning)
        if comuni:
            self.log("   🏛️ Comune letto dai dati INTERLIS: %s" % ", ".join(comuni))
        else:
            self.log("   ⚠️ Nessun comune nei dati (Layout_del_piano.Nome_comune, "
                     "Comune.Nome): per la planimetria andra' indicato a mano",
                     Qgis.Warning)

        # Riepilogo in chiaro sopra la console: quanto e' entrato, cosa e'
        # rimasto fuori e qual e' il passo successivo.
        self._mostra_esito_importazione(len(loaded_layers), saltate, comuni)
        if loaded_layers:
            self._segna_scheda_fatta(self.pagina_import, "1. Importazione")
            self._segna_passo("import")

        # Relazioni e join
        self.log("\n🔗 Fase 3: Relazioni e join...")
        self.setup_relations_and_joins(gpkg_path, loaded_layers)

        # Etichette (dopo i join, cosi' i campi della tabella padre sono disponibili)
        if pending_labels:
            self.log(f"\n📝 Fase 3bis: Configurazione etichette ({len(pending_labels)} layer)...")
            for layer, t_low, class_name in pending_labels:
                self._apply_labels_to_layer(layer, t_low, class_name, mode == "gb")

        # Ri-aggancio dei filtri su "genere" al campo reale (post-join) per
        # Elemento_puntiforme/Elemento_lineare/Elemento_con_superficie.
        # NB: genere_in() genera i filtri con il nome campo in minuscolo
        # ("genere"), coerente col fatto che ili2db esporta sempre i nomi dei
        # campi minuscoli indipendentemente dalla capitalizzazione nel modello
        # ILI: la ricerca/sostituzione qui deve usare la stessa stringa esatta.
        if pending_genere_rebind:
            self.log(f"\n🔗 Fase 3ter: Ri-aggancio campo \"genere\" ({len(pending_genere_rebind)} layer)...")
            for layer in pending_genere_rebind:
                field = self._find_label_field(layer, ["genere"])
                if not field:
                    self.log(f"   ⚠️ Campo genere (diretto o da join) non trovato per {layer.name()}", Qgis.Warning)
                    continue
                renderer = layer.renderer()
                if renderer is None or not hasattr(renderer, 'rootRule'):
                    continue
                n = self._rebind_field_in_rules(renderer.rootRule(), "genere", field)
                layer.triggerRepaint()
                self.log(f"   ✅ {layer.name()}: \"genere\" -> \"{field}\" ({n} regole)")

        # Edificio_sotterraneo/Serbatoio: generi di Elemento_con_superficie
        # (Oggetti_singoli), ma da trattare come Copertura del suolo per
        # ordine di disegno e raggruppamento in legenda (richiesta esplicita
        # dell'utente). QGIS non supporta un ordine di disegno per singola
        # feature/genere ALL'INTERNO di un solo layer (setCustomLayerOrder
        # opera per intero layer): l'unico modo e' isolare questi generi in
        # un layer fisicamente separato, lasciando l'originale con tutti gli
        # ALTRI generi della stessa tabella (muro_di_sostegno, arginatura, ecc.).
        #
        # DUE BUG REALI EVITATI QUI (trovati con test isolati contro un
        # GeoPackage vero prima di questa modifica):
        # 1. QgsVectorLayer.setSubsetString() passa il WHERE al provider OGR
        #    grezzo, che NON conosce i campi aggiunti da un JOIN di QGIS -
        #    serve una SUBQUERY SQL che ricostruisce il join a mano sulla
        #    tabella fisica, usando la relazione gia' creata in Fase 3.
        # 2. Un layer con un QgsVectorLayerJoinInfo GIA' attivo (come
        #    l'originale, dopo Fase 3) fallisce silenziosamente
        #    (featureCount()==-1, "unable to open database file") su
        #    QUALSIASI setSubsetString successivo, anche rimuovendo il join
        #    prima. Unico modo che funziona: filtrare su DUE OGGETTI
        #    QgsVectorLayer completamente nuovi (mai toccati da alcun join),
        #    poi ri-agganciare il join a entrambi solo DOPO il subsetString.
        for i, (old_layer, t_low) in enumerate(zorder_layers):
            if "elemento_con_superficie" in t_low and "oggetti_singoli" in t_low:
                self.log("\n🏚️ Fase 3quater: Isolamento Edificio sotterraneo/Serbatoio...")
                relations = QgsProject.instance().relationManager().referencingRelations(old_layer)
                if not relations:
                    self.log(f"   ⚠️ Nessuna relazione (Fase 3) trovata per {old_layer.name()}: split saltato", Qgis.Warning)
                    break
                relation = relations[0]
                pairs = relation.fieldPairs()
                if not pairs:
                    self.log(f"   ⚠️ Relazione senza coppie di campi per {old_layer.name()}: split saltato", Qgis.Warning)
                    break
                child_col, parent_col = next(iter(pairs.items()))
                parent_layer = relation.referencedLayer()
                parent_table = _raw_table_name(parent_layer)
                parent_genere_field = self._find_label_field(parent_layer, ["genere"])
                if not parent_genere_field:
                    self.log(f"   ⚠️ Campo genere non trovato su {parent_layer.name()}: split saltato", Qgis.Warning)
                    break
                values_sql = ", ".join(f"'{v}'" for v in EDIFICIO_SOTTERRANEO_GENERI)
                subquery = (f'"{child_col}" IN (SELECT "{parent_col}" FROM {parent_table} '
                            f'WHERE "{parent_genere_field}" IN ({values_sql}))')

                raw_table = _raw_table_name(old_layer)
                uri = old_layer.source()
                sott = QgsVectorLayer(uri, f"{old_layer.name()} (sotterraneo)", "ogr")
                rest = QgsVectorLayer(uri, old_layer.name(), "ogr")
                if not sott.isValid() or not rest.isValid():
                    self.log(f"   ⚠️ Impossibile ricaricare {raw_table} da zero: split saltato", Qgis.Warning)
                    break
                if not sott.setSubsetString(subquery):
                    self.log(f"   ⚠️ setSubsetString fallito sul layer isolato: split saltato", Qgis.Warning)
                    break
                if not rest.setSubsetString(f'NOT ({subquery})'):
                    self.log(f"   ⚠️ setSubsetString fallito sul layer rimanente: split annullato", Qgis.Warning)
                    break

                sott.setCrs(old_layer.crs())
                rest.setCrs(old_layer.crs())
                if old_layer.renderer() is not None:
                    sott.setRenderer(old_layer.renderer().clone())
                    rest.setRenderer(old_layer.renderer().clone())
                if old_layer.labeling() is not None:
                    sott.setLabeling(old_layer.labeling().clone())
                    sott.setLabelsEnabled(old_layer.labelsEnabled())
                    rest.setLabeling(old_layer.labeling().clone())
                    rest.setLabelsEnabled(old_layer.labelsEnabled())

                for target in (sott, rest):
                    ji = QgsVectorLayerJoinInfo()
                    ji.setJoinLayer(parent_layer)
                    ji.setJoinFieldName(parent_col)
                    ji.setTargetFieldName(child_col)
                    ji.setUsingMemoryCache(True)
                    ji.setPrefix(f"{parent_table}_")
                    if not target.addJoin(ji):
                        self.log(f"   ⚠️ Ri-aggancio join fallito su {target.name()}", Qgis.Warning)

                QgsProject.instance().removeMapLayer(old_layer.id())
                loaded_layers.remove(old_layer)
                zorder_layers.pop(i)
                QgsProject.instance().addMapLayer(rest)
                QgsProject.instance().addMapLayer(sott)
                loaded_layers.append(rest)
                loaded_layers.append(sott)
                zorder_layers.append((rest, t_low))
                zorder_layers.append((sott, "copertura_dl_solo_superficiecs"))
                self.log(f"   ✅ {sott.name()}: isolato ({sott.featureCount()} feature), "
                         f"classificato come Copertura del suolo")
                self.log(f"   ✅ {rest.name()}: resta Oggetti singoli "
                         f"({rest.featureCount()} feature rimanenti)")
                break

        # Ordine di disegno (z-order): senza questo i layer si sovrappongono
        # nell'ordine casuale di dichiarazione nel GeoPackage, non secondo la
        # gerarchia cartografica del piano (punti fissi/di confine devono restare
        # sempre in primo piano, le coperture del suolo sempre sullo sfondo).
        if zorder_layers:
            self.log(f"\n📐 Fase 4: Ordine di disegno ({len(zorder_layers)} layer)...")
            # NB: QgsLayerTree.setCustomLayerOrder() passa la lista COSI' COM'E'
            # (senza invertirla) a QgsMapSettings.setLayers() - verificato nel
            # sorgente C++ (nessun reverse tra customLayerOrder() e
            # mCanvas->setLayers()) e con un render headless reale (QGIS 4.2.0):
            # il PRIMO elemento e' il layer in primo piano, l'ultimo lo sfondo.
            # Un precedente .reverse() qui (basato su un'assunzione mai
            # verificata contro il comportamento reale) mandava i punti di
            # confine/fissi sullo sfondo invece che in primo piano: rimosso.
            # Log dettagliato PRIMA di ordinare: una riga per layer con
            # priorita' calcolata e il pattern/motivo esatto del match, cosi'
            # un dubbio su "perche' X e' sopra/sotto Y" si risolve leggendo
            # il log invece di dover essere investigato da capo ogni volta
            # (vedi _zorder_debug_info).
            for lyr, t_low in sorted(zorder_layers, key=lambda p: _zorder_priority(p[1])):
                prio, reason = _zorder_debug_info(t_low)
                self.log(f"      [{prio:3d}] {lyr.name()}  ({reason})")
            ordered = [lyr for lyr, _ in sorted(zorder_layers, key=lambda p: _zorder_priority(p[1]))]
            root = QgsProject.instance().layerTreeRoot()
            root.setHasCustomLayerOrder(True)
            root.setCustomLayerOrder(ordered)
            self.log("   ✅ Ordine applicato (punti di confine/fissi in primo piano, coperture sullo sfondo)")

        # Raggruppamento dell'albero layer (pannello Layers): puramente
        # visuale, non tocca l'ordine di disegno appena impostato sopra.
        if zorder_layers or attr_layers:
            self.log("\n📁 Fase 4bis: Raggruppamento albero layer...")
            for lyr, t_low in zorder_layers:
                group, reason = _rf_group_debug_info(t_low)
                self.log(f"      {lyr.name()}  ->  \"{group}\"  ({reason})")
            self._reorganize_layer_tree(zorder_layers, attr_layers)

        # Conformita' cartografica: dimensioni simboli/etichette corrette a
        # qualunque scala di zoom (non solo 1:1000) + punti di confine
        # tralasciati oltre 1:5000 come da piano ufficiale.
        if zorder_layers:
            self.log("\n📏 Fase 4ter: Conformità cartografica (§1.5.2/1.5.4)...")
            self._apply_carto_conformity(zorder_layers)

        # Ponte QGIS -> DXF per la legenda (vedi legend_manifest.py): scritto
        # SEMPRE alla fine dello stile, cosi' il generatore DXF (Java) trova
        # sempre il manifest piu' recente al prossimo export - non e' un
        # collegamento live tra i due programmi, va rigenerato rilanciando lo
        # stile e poi l'export, in quest'ordine.
        if zorder_layers:
            self.log("\n🗒️ Fase 4quater: Manifest legenda per il DXF...")
            # Il lato Java cerca il manifest ACCANTO AL FILE ITF che sta
            # convertendo (Av2geobau.doConversion), non accanto al GeoPackage:
            # scriverlo solo nella cartella del GPKG lo rendeva invisibile
            # all'export ogni volta che ITF e GPKG stanno in cartelle diverse
            # (sono 2 campi indipendenti nella dialog) - la legenda spariva
            # senza alcun errore. Si scrive quindi in ENTRAMBE le cartelle
            # quando differiscono (il file e' di pochi KB).
            try:
                dest_dirs = [gpkg_path.parent]
                itf_txt = self.txt_itf.text().strip()
                if itf_txt:
                    itf_dir = Path(itf_txt).parent
                    if itf_dir != gpkg_path.parent:
                        dest_dirs.append(itf_dir)
                for dest_dir in dest_dirs:
                    manifest_path = dest_dir / "legenda_manifest.txt"
                    n_voci = write_legend_manifest(zorder_layers, manifest_path)
                    self.log(f"   ✅ {n_voci} voci scritte in {manifest_path}")
            except Exception as e:
                self.log(f"   ⚠️ Errore scrittura manifest legenda: {str(e)}", Qgis.Warning)

        # Layout PB-MU
        if self.product_mode == "bp" and loaded_layers:
            self.log("\n📐 Fase 5: Layout PB-MU...")
            self.create_layout_bp()

        # Aggiorna canvas. getattr perche' i test istanziano la dialog con
        # __new__ (senza __init__): self._iface potrebbe non esistere affatto.
        _iface = getattr(self, "_iface", None)
        if _iface and _iface.mapCanvas():
            _iface.mapCanvas().refresh()
            self.log("\n🖼️ Canvas aggiornato")

        # Adesso c'e' qualcosa da consegnare. NON si adegua il progetto qui:
        # i flag WMS non li legge solo il server - Private toglie il layer
        # dall'albero e Identifiable spegne lo strumento "informazioni" del
        # desktop - e applicarli a fine importazione vorrebbe dire che da quel
        # momento un clic su una copertura del suolo non risponde piu', senza
        # spiegazione. Si adegua quando si consegna, e si rimette a posto.
        self._aggiorna_pulsante_consegna()

    def _reorganize_layer_tree(self, geom_layers, attr_layers):
        """Raggruppa il pannello Layers secondo i 12 livelli di RF_LAYER_GROUPS
        (circ154 cap. 1.5.4), invece di lasciare un elenco piatto di
        decine/centinaia di tabelle con nomi tecnici. Puramente organizzativo:
        NON tocca l'ordine di disegno (gia' impostato da setCustomLayerOrder
        in Fase 4) ne' stili/etichette - sposta solo i nodi nell'albero.
        'geom_layers': lista di (layer, t_low) come zorder_layers.
        'attr_layers': layer attributo puri (senza geometria, solo per i join).
        Rilanciabile: rimuove i gruppi RF di un run precedente prima di
        ricrearli, cosi' ricaricare la legenda su un progetto gia' aperto
        non li duplica."""
        root = QgsProject.instance().layerTreeRoot()

        # Rimuovi eventuali gruppi RF di un run precedente (stesso progetto,
        # legenda ricaricata): stacca prima i layer nel nodo radice, cosi'
        # restano nel progetto anche se il gruppo viene rimosso.
        prefixes = tuple(f"{title.split()[0]} " for title, _ in RF_LAYER_GROUPS) + ("90 ", "99 ")
        for child in list(root.children()):
            if isinstance(child, QgsLayerTreeGroup) and child.name().startswith(prefixes):
                for sub in list(child.findLayers()):
                    root.insertChildNode(0, sub.clone())
                    child.removeChildNode(sub)
                root.removeChildNode(child)

        group_nodes = {}
        for title, _pats in RF_LAYER_GROUPS:
            group_nodes[title] = root.addGroup(title)
        other_group = root.addGroup("90 Altri layer geometrici")
        attr_group = root.addGroup("99 Tabelle attributo (join)")

        moved = 0
        for lyr, t_low in geom_layers:
            node = root.findLayer(lyr.id())
            if node is None:
                continue
            title = _rf_group_for_table(t_low)
            target = group_nodes.get(title, other_group) if title else other_group
            target.insertChildNode(-1, node.clone())
            parent = node.parent()
            if parent is not None:
                parent.removeChildNode(node)
            moved += 1

        for lyr in attr_layers:
            node = root.findLayer(lyr.id())
            if node is None:
                continue
            attr_group.insertChildNode(-1, node.clone())
            parent = node.parent()
            if parent is not None:
                parent.removeChildNode(node)
            moved += 1

        # Rimuovi i gruppi rimasti vuoti (nessun layer di questo dataset
        # rientrava in quella categoria - es. nessuna condotta nel comune).
        for g in list(group_nodes.values()) + [other_group, attr_group]:
            if len(g.children()) == 0:
                root.removeChildNode(g)

        self.log(f"   ✅ Albero raggruppato: {moved} layer in {len(RF_LAYER_GROUPS) + 2} categorie possibili")

    def _nascondi_legenda_se_invisibile(self, layer, renderer):
        """Toglie dalla legenda le voci dei layer con simbolo invisibile.

        Sono i punti di iscrizione delle etichette (le tabelle Pos* di
        copertura del suolo, oggetti singoli e altri temi) e le tabelle che il
        piano non rappresenta: il loro simbolo e' un marcatore da 0.01 mm
        trasparente, ma QGIS in legenda lo disegna comunque come un punto nero,
        e cosi' l'albero dei layer si riempie di decine di pallini che non
        corrispondono a nulla di visibile sulla mappa.

        Il riconoscimento passa dall'etichetta della regola radice, che
        _gen_stile_invisibile imposta a "Invisibile": e' l'unico marcatore che
        distingue quel renderer dagli altri rule-based."""
        try:
            radice = renderer.rootRule() if hasattr(renderer, "rootRule") else None
            if radice is None or radice.label() != "Invisibile":
                return False
            nodo = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
            if nodo is None:
                return False
            # Ordine vuoto = nessuna voce di legenda per questo layer.
            QgsMapLayerLegendUtils.setLegendNodeOrder(nodo, [])
            nodo.setCustomProperty("legend/node-order-updated", True)
            return True
        except Exception as e:
            self.log("   ⚠️ Legenda non nascosta per %s: %s" % (layer.name(), e),
                     Qgis.Warning)
            return False

    # --- CONFORMITA' CARTOGRAFICA (§1.5.4) ---
    # NOTA: esisteva anche un fattore di scala §1.5.2 (size_mm * 1000/@map_scale
    # via proprieta' data-defined su simboli ed etichette), rimosso dopo un
    # riscontro reale dell'utente: testi/simboli invisibili a qualunque scala
    # diversa da 1:1000 (le dimensioni collassano sotto la soglia leggibile a
    # scale piu' "zoomate fuori"), e marker a font disallineati (il loro
    # offset di ancoraggio, _font_marker_offset, non veniva ri-scalato in
    # sincrono). La visibilita' scala-dipendente sotto (§1.5.4, indipendente
    # dalla dimensione) resta invece valida.
    def _apply_scale_dependent_visibility(self, layer, t_low):
        """§1.5.4: i punti di confine (non le altre geometrie) restano
        visibili solo a scale piu' dettagliate di 1:CONFINE_POINTS_MIN_SCALE -
        oltre, il piano ufficiale li tralascia."""
        t = (t_low or layer.name()).lower()
        is_confine_pt = (
            ("punto_di_confine" in t or "pcgiurisdizionale" in t)
            and "pospunto" not in t and "_pos" not in t and not t.startswith("pos")
        )
        if "tenuta_a_giorno" in t or t.endswith("prog"):
            return False
        if not is_confine_pt:
            return False
        try:
            layer.setScaleBasedVisibility(True)
            layer.setMinimumScale(float(CONFINE_POINTS_MIN_SCALE))
            layer.setMaximumScale(0.0)
            return True
        except Exception as e:
            self.log(f"   ⚠️ Impossibile impostare la visibilita' scala-dipendente "
                      f"su {layer.name()}: {e}", Qgis.Warning)
            return False

    def _apply_carto_conformity(self, zorder_layers):
        """Applica la visibilita' scala-dipendente dei punti di confine (§1.5.4)
        a tutti i layer geometrici stilizzati."""
        n_visibility = 0
        for layer, t_low in zorder_layers:
            if self._apply_scale_dependent_visibility(layer, t_low):
                n_visibility += 1
        self.log(f"   ✅ Visibilita' scala-dipendente §1.5.4 (punti di confine "
                  f"oltre 1:{CONFINE_POINTS_MIN_SCALE}): {n_visibility} layer")

    # --- ETICHETTE ---
    @staticmethod
    def _find_label_field(layer, candidates):
        """Trova il primo campo tra i candidati sul layer. Le tabelle "PosX" del
        modello ILI non contengono quasi mai il testo direttamente: vive sulla
        tabella padre "X" e diventa un campo del layer solo dopo il join
        (rinominato "{tabella_padre}_{campo}" da setup_relations_and_joins).
        Cerchiamo quindi anche un campo che termini con "_<candidato>"."""
        existing = {f.name().lower(): f.name() for f in layer.fields()}
        for cand in candidates:
            if cand.lower() in existing:
                return existing[cand.lower()]
        for cand in candidates:
            suffix = ("_" + cand).lower()
            for lname, orig in existing.items():
                if lname.endswith(suffix):
                    return orig
        return None

    @staticmethod
    def _rebind_field_in_rules(rule, old_field, new_field):
        """Sostituisce, in tutto l'albero di regole a partire da 'rule', ogni
        riferimento a "old_field" nell'espressione di filtro con "new_field".
        Usato per i renderer costruiti su un campo (es. "Genere") che esiste solo
        sulla tabella padre e diventa disponibile sul layer solo dopo il join."""
        count = 0
        old_ref, new_ref = f'"{old_field}"', f'"{new_field}"'
        if old_field != new_field:
            expr = rule.filterExpression()
            if old_ref in expr:
                rule.setFilterExpression(expr.replace(old_ref, new_ref))
                count += 1
        for child in rule.children():
            count += TIDashboardDialog._rebind_field_in_rules(child, old_field, new_field)
        return count

    def _apply_pos_text_attrs(self, layer, settings, keyword, base_size):
        """Collega Ori/HAli/VAli/Dimensione/Stile (tabelle Pos* di
        MD01MUTI7MN95.ili) alle proprieta' data-defined di QGIS, applicando
        come default esplicito il valore "non_definito" dichiarato dal
        modello per quell'attributo quando e' assente nei dati, invece di
        lasciarlo a un default QGIS implicito.

        - Ori: azimut in GON orario da Nord (0=Nord, 100=Est, coerente con
          "E_Azimut ... Azimut 100 = E" del modello). QGIS vuole gradi orari
          da Est (0=Est): gradi_qgis = (Ori_gon - 100) * 0.9 (segno opposto
          alla stessa formula usata per il DXF in av2geobau_ti/Mapper.java,
          che converte lo stesso Ori in gradi ANTIorari da Est).
        - HAli/VAli: le proprieta' data-defined QgsPalLayerSettings.Hali/Vali
          accettano LETTERALMENTE gli stessi valori del dominio ILI
          (Left/Center/Right, Bottom/Base/Half/Cap/Top) - nessuna conversione,
          solo il default giusto per tabella (Left/Bottom per le etichette-
          numero di punto PFP/PFA/Segnale/Punto_quotato, Center/Half per
          tutte le altre, secondo _POS_LEFT_BOTTOM_KEYWORDS).
        - Dimensione (piccolo/medio/grande): il plugin ha gia' una dimensione
          fissa in pt per ogni voce di TEXT_LABEL_RULES, che rappresenta il
          caso "medio" (default dichiarato ovunque). +-25% per piccolo/grande
          e' un'approssimazione (il valore pt esatto non e' specificato ne'
          nel modello ne' in av2geobau, che non mappa affatto Dimensione).
        - Stile (normale/spaziato): "spaziato" = testo con spaziatura lettere
          allargata, via la proprieta' data-defined FontLetterSpacing
          (assente il concetto in DXF/av2geobau); ampiezza approssimata
          proporzionale alla dimensione del carattere.

        Tutte le proprieta' hanno senso solo con placement "sopra al punto"
        anziche' la ricerca automatica anti-sovrapposizione di QGIS
        (AroundPoint, il default): viene quindi sempre impostato OverPoint,
        analogo al posizionamento fisso di un TEXT DXF.
        """
        fields = layer.fields()
        applied = []
        left_bottom = keyword in _POS_LEFT_BOTTOM_KEYWORDS
        hali_default = "Left" if left_bottom else "Center"
        vali_default = "Bottom" if left_bottom else "Half"
        dd = settings.dataDefinedProperties()

        if fields.lookupField("ori") >= 0:
            dd.setProperty(QgsPalLayerSettings.Property.LabelRotation,
                            QgsProperty.fromExpression('(coalesce("ori", 100) - 100) * 0.9'))
            applied.append("Ori")
        if fields.lookupField("hali") >= 0:
            dd.setProperty(QgsPalLayerSettings.Property.Hali,
                            QgsProperty.fromExpression(f"coalesce(\"hali\", '{hali_default}')"))
            applied.append("HAli")
        if fields.lookupField("vali") >= 0:
            dd.setProperty(QgsPalLayerSettings.Property.Vali,
                            QgsProperty.fromExpression(f"coalesce(\"vali\", '{vali_default}')"))
            applied.append("VAli")
        if not left_bottom and fields.lookupField("dimensione") >= 0:
            dd.setProperty(QgsPalLayerSettings.Property.Size, QgsProperty.fromExpression(
                f'CASE "dimensione" '
                f"WHEN 'piccolo' THEN {base_size * 0.8} "
                f"WHEN 'grande' THEN {base_size * 1.25} "
                f'ELSE {base_size} END'
            ))
            applied.append("Dimensione")
        if keyword in _POS_STILE_KEYWORDS and fields.lookupField("stile") >= 0:
            dd.setProperty(QgsPalLayerSettings.Property.FontLetterSpacing, QgsProperty.fromExpression(
                f"CASE WHEN \"stile\" = 'spaziato' THEN {base_size * 0.3} ELSE 0 END"
            ))
            applied.append("Stile")

        # Priorita' e comportamento in caso di sovrapposizione. Il motore di
        # etichettatura di QGIS sa gia' nascondere una scritta che non ci sta;
        # quello che non sa, senza che glielo si dica, e' QUALE delle due deve
        # cedere: senza priorita' tratta tutti i layer alla pari e decide
        # l'ordine di disegno. La scala sta in _LABEL_PRIORITY, ed e' la stessa
        # usata dall'esportazione DXF (AntiCollisioneEtichette.java), cosi'
        # anteprima e disegno consegnato non si contraddicono.
        settings.priority = _LABEL_PRIORITY.get(keyword, _LABEL_PRIORITY_DEFAULT)
        # La scritta e' anche ostacolo per le altre, con peso pari alla sua
        # priorita': un numero di fondo non va coperto da un numero di punto.
        ostacoli = settings.obstacleSettings()
        ostacoli.setIsObstacle(True)
        ostacoli.setFactor(0.5 + 0.1 * settings.priority)
        settings.setObstacleSettings(ostacoli)

        if applied:
            settings.placement = Qgis.LabelPlacement.OverPoint
        return applied

    def _apply_labels_to_layer(self, layer, t_low, class_name, is_gb=False):
        """Applica etichette ai layer testuali (cap. 5 Weisung-GB-it.pdf)."""
        _ensure_cadastra_text_font_loaded()
        # Punto quotato: la quota e' la componente Z della geometria (CoordA),
        # non un attributo separato -> etichetta basata su espressione $z.
        if "punto_quotato" in t_low:
            settings = QgsPalLayerSettings()
            settings.fieldName = "round($z, 2)"
            settings.isExpression = True
            text_format = QgsTextFormat()
            text_format.setColor(gbc(is_gb, QColor(102, 51, 0)))
            text_format.setFont(QFont(CADASTRA_TEXT_FAMILY))
            # Punto quotato: estensione cantonale senza grandezza federale,
            # allineato a 1.8mm come le altre etichette-numero.
            text_format.setSize(_font_size_for_cap(1.8))
            text_format.setSizeUnit(QgsUnitTypes.RenderMillimeters)
            settings.setFormat(text_format)
            settings.enabled = True
            applied = self._apply_pos_text_attrs(layer, settings, "punto_quotato", 1.8)
            layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
            layer.setLabelsEnabled(True)
            note = f" ({'+'.join(applied)} da Pos*)" if applied else ""
            self.log(f"     ✅ Etichetta Punto_quotato su $z{note}")
            return

        for keyword, candidates, bold, italic, size in TEXT_LABEL_RULES:
            if keyword not in t_low:
                continue

            # La scritta va sul PUNTO DI ISCRIZIONE, non sull'oggetto che
            # nomina: vedi TESTO_SOLO_SU_POS. Senza questo controllo il nome
            # finiva sul foglio due volte - 658 iscrizioni di troppo sul solo
            # comune di prova, a mediana 40-50 mm di carta l'una dall'altra.
            if keyword in TESTO_SOLO_SU_POS and not e_tabella_pos(t_low):
                self.log("     ⏭️ %s: l'iscrizione sta sulla tabella Pos*, "
                         "qui sarebbe la seconda copia dello stesso nome"
                         % class_name)
                return

            field_name = self._find_label_field(layer, candidates)
            if not field_name:
                self.log(f"     ⚠️ Nessun campo tra {candidates} trovato per '{keyword}' "
                          f"(join mancante o non riuscito?)", Qgis.Warning)
                return

            settings = QgsPalLayerSettings()
            # PosNome_localizzazione: Indice_iniziale/Indice_finale delimitano
            # una sottostringa di Testo da mostrare (default 1..ultimo
            # carattere = tutto il testo), secondo MD01MUTI7MN95.ili.
            if keyword == "posnome_localizzazione" and layer.fields().lookupField("indice_iniziale") >= 0:
                settings.fieldName = (
                    f'substr("{field_name}", coalesce("indice_iniziale", 1), '
                    f'coalesce("indice_finale", length("{field_name}")) - coalesce("indice_iniziale", 1) + 1)'
                )
                settings.isExpression = True
            elif keyword == KEYWORD_LOCALITA:
                settings.fieldName, settings.isExpression = \
                    iscrizione_localita(field_name, self._maiuscolo_localita())
            else:
                settings.fieldName = field_name
            text_format = QgsTextFormat()
            font = QFont(CADASTRA_TEXT_FAMILY)
            font.setBold(bold)
            font.setItalic(italic)
            text_format.setFont(font)
            # 'size' e' l'altezza della MAIUSCOLA in mm richiesta dalla norma:
            # va convertita nella dimensione del font e resa in millimetri di
            # stampa (a 1:1000 coincide col valore normativo). In punti
            # tipografici, come prima, il rapporto fra le classi di scrittura
            # non sarebbe quello prescritto.
            text_format.setSize(_font_size_for_cap(size))
            text_format.setSizeUnit(QgsUnitTypes.RenderMillimeters)
            settings.setFormat(text_format)
            settings.enabled = True
            applied = self._apply_pos_text_attrs(layer, settings, keyword, size)
            layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
            label_off = any(k in t_low for k in _LABEL_DISABLED_BY_DEFAULT)
            layer.setLabelsEnabled(not label_off)
            style = "grassetto" if bold else ("corsivo" if italic else "normale")
            note = f" + {'+'.join(applied)} da Pos*" if applied else ""
            off_note = " (etichetta creata ma spenta di default)" if label_off else ""
            self.log(f"     ✅ Etichetta '{keyword}' su campo '{field_name}' (Cadastra {style} {size}mm{note}){off_note}")

            if any(k in t_low for k in _LABEL_LAYER_OFF_BY_DEFAULT):
                node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
                if node:
                    node.setItemVisibilityChecked(False)
                    self.log(f"     ✅ Layer spento di default (etichetta pronta, da riaccendere manualmente)")
                else:
                    self.log(f"     ⚠️ Nodo albero non trovato per {layer.name()}: layer resta acceso", Qgis.Warning)
            return

        self.log("     ⚠️ Nessuna regola di etichettatura corrispondente")

    # --- RELAZIONI E JOIN ---
    def setup_relations_and_joins(self, gpkg_path, loaded_layers):
        """Crea relazioni e join tra i layer."""
        if not loaded_layers:
            self.log("   ⚠️ Nessun layer caricato, skip relazioni")
            return

        self.log(f"   📊 Layer caricati: {len(loaded_layers)}")
        # BUG REALE (segnalato dall'utente: testi/etichette assenti su beni
        # immobili e indirizzi degli edifici): le chiavi esterne lette da
        # sqlite_master/t_ili2db_column_prop usano i nomi RAW delle tabelle
        # del GeoPackage, ma qui sotto veniva indicizzato per layer.name() -
        # gia' rinominato al nome "nice" in italiano (vedi _nice_layer_name,
        # applicato in Fase 2, PRIMA di questa Fase 3) per la maggior parte
        # dei layer. Il lookup falliva quindi silenziosamente (continue senza
        # log) per ~123 join su 128 in un caso reale, lasciando i layer Pos*
        # senza il campo testo della tabella padre e di conseguenza senza
        # etichetta. Il nome di tabella RAW e' invece recuperabile in modo
        # affidabile dalla source URI del layer OGR ("...gpkg|layername=xxx"),
        # indipendente da come e' stato rinominato il layer.
        layer_dict = {_raw_table_name(layer): layer for layer in loaded_layers}
        fk_list = []
        seen = set()

        try:
            conn = sqlite3.connect(str(gpkg_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]
            self.log(f"   📋 Tabelle nel DB: {len(tables)}")

            # 1. Vincoli FK reali (presenti solo se lo schema e' stato creato con --createFk)
            # PRAGMA non supporta il binding '?' sui nomi tabella (solo sui valori),
            # quindi l'identificatore va quotato a mano: raddoppiare gli apici interni
            # e' la forma di escaping SQL standard per una stringa letterale.
            for table in tables:
                cursor.execute("PRAGMA foreign_key_list('%s')" % table.replace("'", "''"))
                rows = cursor.fetchall()
                for row in rows:
                    child_col, parent_table, parent_col = row[3], row[2], row[4] if row[4] else "rowid"
                    key = (table, child_col)
                    if key not in seen:
                        fk_list.append((table, child_col, parent_table, parent_col))
                        seen.add(key)

            # 2. Fallback: metadati ili2db (t_ili2db_column_prop, tag ch.ehi.ili2db.foreignKey).
            # Popolata con --createMetaInfo anche SENZA --createFk: e' il modo con cui ili2db
            # permette di ricostruire le relazioni quando lo schema non ha vincoli FK reali
            # (che rifiuterebbero l'import di dati con riferimenti mancanti/tolleranti errori).
            # I nomi delle tabelle di metadati ili2db sono in MAIUSCOLO
            # (es. "T_ILI2DB_COLUMN_PROP", verificato sul GeoPackage): il confronto
            # diretto su sqlite_master.name e' case-sensitive in SQLite, quindi
            # serve un confronto case-insensitive esplicito.
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND lower(name)='t_ili2db_column_prop'")
            if cursor.fetchone():
                cursor.execute(
                    "SELECT tablename, columnname, setting FROM t_ili2db_column_prop "
                    "WHERE tag = 'ch.ehi.ili2db.foreignKey'")
                for table, child_col, parent_table in cursor.fetchall():
                    key = (table, child_col)
                    if key not in seen:
                        fk_list.append((table, child_col, parent_table, "T_Id"))
                        seen.add(key)
            else:
                self.log("   ℹ️ t_ili2db_column_prop non presente (schemaimport senza --createMetaInfo)")

            conn.close()
            self.log(f"   🔗 Chiavi esterne trovate: {len(fk_list)}")
        except Exception as e:
            self.log(f"   ❌ Errore lettura FK: {str(e)}", Qgis.Warning)
            return

        relations_created = 0
        joins_created = 0

        for child_table, child_col, parent_table, parent_col in fk_list:
            child_layer = layer_dict.get(child_table)
            parent_layer = layer_dict.get(parent_table)

            if not child_layer or not parent_layer:
                continue

            child_fields = [f.name() for f in child_layer.fields()]
            parent_fields = [f.name() for f in parent_layer.fields()]

            if child_col not in child_fields or parent_col not in parent_fields:
                continue

            relation = QgsRelation()
            relation.setId(f"{child_table}_{parent_table}")
            relation.setName(f"{child_table} → {parent_table}")
            relation.setReferencingLayer(child_layer.id())
            relation.setReferencedLayer(parent_layer.id())
            relation.addFieldPair(child_col, parent_col)

            if relation.isValid():
                QgsProject.instance().relationManager().addRelation(relation)
                relations_created += 1
                self.log(f"   ✅ Relazione: {child_table}.{child_col} → {parent_table}.{parent_col}")

            join_info = QgsVectorLayerJoinInfo()
            # NB: QgsVectorLayerJoinInfo e' un binding SIP: l'assegnazione diretta di
            # attributo (join_info.joinLayerId = ...) NON richiama il setter C++, crea
            # solo un attributo Python "ombra" che addJoin() ignora completamente,
            # lasciando il join configurato con valori vuoti/default (fallimento silenzioso).
            # Vanno usati i metodi setter espliciti. setJoinLayer() (puntatore diretto)
            # e' preferito a setJoinLayerId() per evitare qualsiasi dipendenza dalla
            # risoluzione dell'ID tramite QgsProject al momento dell'uso del join.
            join_info.setJoinLayer(parent_layer)
            join_info.setJoinFieldName(parent_col)
            join_info.setTargetFieldName(child_col)
            join_info.setUsingMemoryCache(True)
            join_info.setPrefix(f"{parent_table}_")
            if child_layer.addJoin(join_info):
                joins_created += 1
                new_fields = [f.name() for f in child_layer.fields()
                              if f.name().lower().startswith(f"{parent_table}_".lower())]
                if not new_fields:
                    all_fields = [f.name() for f in child_layer.fields()]
                    self.log(f"   ⚠️ Join OK ma nessun campo con prefisso '{parent_table}_' su "
                              f"{child_table} (campi attuali: {all_fields})", Qgis.Warning)
            else:
                self.log(f"   ⚠️ Join fallito: {child_table}.{child_col} → {parent_table}.{parent_col}", Qgis.Warning)

        self.log(f"   📊 Relazioni create: {relations_created}")
        self.log(f"   📊 Join creati: {joins_created}")
        self._join_orientamento_simboli(fk_list, layer_dict)

    def _join_orientamento_simboli(self, fk_list, layer_dict):
        """Porta l'orientamento del simbolo dalle tabelle "Simbolo*" SENZA
        geometria sul layer del padre, con un join nel verso opposto a tutti
        gli altri.

        Cinque delle undici tabelle Simbolo* del modello - SimboloPunto_di_
        confine, SimboloPCGiurisdizionale, SimboloPFP1/2/3 - non hanno alcuna
        geometria: portano solo "Ori", cioe' l'orientamento con cui va disegnato
        il simbolo del punto a cui si riferiscono, e la relazione e' 1-c (IDENT
        sul riferimento), quindi al piu' una riga per padre. Non sono
        disegnabili di per se': l'unico modo di usarle e' portare "Ori" sul
        padre, che la geometria ce l'ha. Tutti gli altri join di questo metodo
        vanno figlio -> padre; questo e' l'unico che va padre <- figlio.

        Sui dati reali di Chiasso: 5637 punti di confine su 67919 portano un
        orientamento non nullo, e finora venivano disegnati tutti dritti.

        Il prefisso e' fisso (PREFISSO_SIMBOLO) e non derivato dal nome della
        tabella: gli stili cercano "simbolo_ori", che e' uguale per tutti i
        temi, invece di dover ricostruire nomi come
        "beni_immobili_simbolopunto_di_confine_ori"."""
        fatti = 0
        for child_table, child_col, parent_table, parent_col in fk_list:
            nome = child_table.lower()
            if "simbolo" not in nome:
                continue
            child_layer = layer_dict.get(child_table)
            parent_layer = layer_dict.get(parent_table)
            if not child_layer or not parent_layer:
                continue
            # Solo le tabelle SENZA geometria: quelle che ce l'hanno si
            # disegnano da se' e il loro "Ori" lo usa il loro stesso stile.
            if child_layer.geometryType() != QgsWkbTypes.NullGeometry:
                continue
            if child_layer.fields().indexFromName("ori") < 0:
                continue
            if parent_layer.fields().indexFromName(CAMPO_ORI_SIMBOLO) >= 0:
                continue
            join = QgsVectorLayerJoinInfo()
            join.setJoinLayer(child_layer)
            join.setJoinFieldName(child_col)      # la FK del figlio...
            join.setTargetFieldName(parent_col)   # ...contro la chiave del padre
            join.setUsingMemoryCache(True)
            join.setPrefix(PREFISSO_SIMBOLO)
            join.setJoinFieldNamesSubset(["ori"])
            if parent_layer.addJoin(join):
                fatti += 1
                self.log("   🧭 Orientamento simbolo: %s.ori → %s.%s"
                         % (child_table, parent_table, CAMPO_ORI_SIMBOLO))
            else:
                self.log("   ⚠️ Join orientamento fallito: %s → %s"
                         % (child_table, parent_table), Qgis.Warning)
        if fatti:
            self.log("   📊 Orientamenti di simbolo collegati: %d" % fatti)

    def consegna_qgis_server(self):
        """Scrive la cartella da copiare su QGIS Server e la ricontrolla.

        NEL THREAD DELL'INTERFACCIA, non in un QThread come le altre attese
        lunghe. Il pezzo che dura e' la copia del GeoPackage, ma il resto tocca
        il progetto QGIS - datasource, flag dei layer, percorsi dei simboli - e
        gli oggetti del progetto non si maneggiano da un thread secondario.
        Meglio una finestra ferma per qualche secondo, con la clessidra, che un
        blocco raro e inspiegabile dentro QGIS."""
        gpkg = self.txt_gpkg.text().strip()
        if not os.path.isfile(gpkg):
            QMessageBox.warning(self, "Consegna per QGIS Server",
                                "GeoPackage non trovato:\n%s" % (gpkg or "(vuoto)"))
            return

        cartella = QFileDialog.getExistingDirectory(
            self, "Cartella di consegna (vuota o nuova)",
            os.path.dirname(gpkg))
        if not cartella:
            return
        # La consegna riscrive symbols/ e il progetto: su una cartella che
        # contiene gia' altro si sovrascrive senza che l'utente lo sappia.
        if os.path.isdir(cartella) and os.listdir(cartella):
            if QMessageBox.question(
                    self, "Consegna per QGIS Server",
                    "La cartella non è vuota:\n%s\n\nI file con lo stesso nome "
                    "verranno sovrascritti. Procedere?" % cartella,
                    _MB_SI | _MB_NO, _MB_NO) != _MB_SI:
                return

        nome = os.path.splitext(os.path.basename(gpkg))[0]
        self.log("\n🌐 Consegna per QGIS Server → %s" % cartella)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            esito = _pubblica.consegna(
                cartella, QgsProject.instance(), gpkg,
                os.path.dirname(os.path.abspath(__file__)), titolo=nome)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.log("   ❌ Consegna non riuscita: %s" % e, Qgis.Critical)
            QMessageBox.critical(self, "Consegna per QGIS Server",
                                 "Consegna non riuscita:\n%s" % e)
            return
        finally:
            # restoreOverrideCursor anche sul percorso di errore, altrimenti
            # QGIS resta con la clessidra addosso fino al riavvio.
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

        self.log("   ✅ %s" % os.path.basename(esito["qgz"]))
        self.log("   📦 %d layer, di cui %d fuori dal servizio (cap. 1.5.3); "
                 "%d font, %d simboli"
                 % (esito["n_layer"], esito["n_privati"], esito["n_font"],
                    esito["n_svg"]))

        # E POI SI GUARDA IL FILE SCRITTO, non gli oggetti appena impostati.
        rilievi, _dati = _pubblica.verifica_consegna(cartella)
        for r in rilievi:
            self.log("   ⚠️ %s" % r, Qgis.Warning)

        # IL PROMEMORIA SUI FONT VA IN ENTRAMBI I MESSAGGI. Prima stava solo in
        # quello di successo, cioe' spariva proprio quando la consegna aveva
        # gia' qualcosa che non andava - il momento in cui una dimenticanza in
        # piu' costa di piu'. Ed e' l'unico passo che il plugin non puo' fare
        # al posto di chi consegna: senza i font installati il server risponde
        # lo stesso, con un carattere di ricambio scelto da Qt in silenzio.
        promemoria = ("\n\nI font Cadastra vanno INSTALLATI sul server: QGIS "
                      "Server non carica i .ttf che trova accanto al progetto. "
                      "Le istruzioni sono in LEGGIMI.txt dentro la cartella.")
        if rilievi:
            QMessageBox.warning(
                self, "Consegna per QGIS Server",
                "Cartella scritta, ma il controllo ha trovato %d problemi:\n\n%s"
                "\n\nIl dettaglio è nel registro.%s"
                % (len(rilievi), "\n".join(rilievi[:5]), promemoria))
        else:
            QMessageBox.information(
                self, "Consegna per QGIS Server",
                "Cartella pronta:\n%s\n\nControllata: nessun percorso assoluto, "
                "ogni file citato dal progetto è dentro la cartella.%s"
                % (cartella, promemoria))

    def create_layout_bp(self):
        """Crea un layout per il piano di base (PB-MU): mappa a tutto foglio
        (meno i margini per titolo e barra di scala), titolo e barra di scala
        collegata alla mappa.

        LA SCALA E' QUELLA SCELTA nel menu "Scala", non piu' 1:5000 fisso nel
        codice. Il valore 1:5000 era la scala tipica del piano di base ed era
        scritto in due punti - setScale e il titolo - senza che nulla lo legasse
        al menu: chi sceglieva 1:1000 otteneva comunque un foglio 1:5000, con
        sopra stampato "Scala: 1:5000", cioe' un foglio coerente con se stesso e
        con nient'altro. Ora 1:5000 resta il PUNTO DI PARTENZA (on_product_changed
        lo preseleziona passando a PB-MU) ma e' una proposta, non un vincolo.

        La versione ancora precedente creava un layout con la sola etichetta e
        una barra di scala non collegata a nessuna mappa (niente
        QgsLayoutItemMap nel layout, quindi il PDF esportato non mostrava
        alcuna mappa)."""
        if not self.loaded_layers:
            self.log("   ⚠️ Nessun layer caricato, skip layout")
            return

        _formato, scala, _rot, _com, _data = self._parametri_planimetria()
        self.log("   📐 Creazione layout PB-MU (scala 1:%d)..." % scala)
        project = QgsProject.instance()
        # QgsPrintLayout, non QgsLayout: solo il primo ha setName e puo' essere
        # registrato nel gestore dei layout. Con QgsLayout questo metodo
        # sollevava AttributeError su QGIS 4, quindi il pulsante non produceva
        # alcun layout.
        layout = QgsPrintLayout(project)
        layout.initializeDefaults()
        # Il nome porta la scala: ora che non e' piu' fissa, due layout a scale
        # diverse sono due fogli diversi. Con il nome unico "Basisplan_PB-MU" il
        # secondo si sarebbe scontrato con il primo nel gestore dei layout.
        layout.setName("Basisplan_PB-MU_1-%d" % scala)

        page = layout.pageCollection().page(0)
        page_w = page.sizeWithUnits().width()
        page_h = page.sizeWithUnits().height()

        # Mappa: occupa il foglio meno un margine alto (per il titolo, ~30mm)
        # e uno basso (per la barra di scala, ~20mm). Aggiunta PRIMA degli
        # altri elementi, cosi' titolo e barra di scala le restano sopra
        # nell'ordine di disegno del layout.
        map_item = QgsLayoutItemMap(layout)
        # Aggiunto al layout PRIMA di dimensionarlo e, soprattutto, con un CRS
        # esplicito: senza CRS QGIS non sa legare le unita' della mappa ai
        # millimetri del foglio e setScale() azzera l'estensione (misurato:
        # 0x0 m), producendo un foglio vuoto. Vedi la stessa nota in
        # planimetria.crea_planimetria.
        layout.addLayoutItem(map_item)
        map_item.setCrs(QgsCoordinateReferenceSystem("EPSG:2056"))
        map_item.attemptSetSceneRect(QRectF(5, 30, page_w - 10, page_h - 55))
        # Estensione: unione degli extent di tutti i layer caricati (i layer
        # del plugin sono tutti in EPSG:2056, vedi load_and_style_layers -
        # nessuna riproiezione necessaria). Se un layer e' vuoto/non
        # spaziale il suo extent viene saltato.
        extent = QgsRectangle()
        extent.setMinimal()
        n_ext = 0
        for lyr in self.loaded_layers:
            if lyr and lyr.isSpatial():
                ext = lyr.extent()
                if ext and not ext.isEmpty():
                    extent.combineExtentWith(ext)
                    n_ext += 1
        if not extent.isEmpty():
            map_item.setExtent(extent)          # centra la mappa sull'unione
            # setExtent PRIMA di setScale: l'estensione fissa il centro, la
            # scala poi ridimensiona attorno a quel centro senza spostarlo.
            map_item.setScale(float(scala))
            self.log(f"   🗺️ Mappa: extent da {n_ext} layer, scala 1:{scala}")
        else:
            self.log("   ⚠️ Nessun extent valido dai layer caricati: la mappa "
                      "resta con l'estensione di default del layout.", Qgis.Warning)

        _ensure_cadastra_text_font_loaded()
        title_label = QgsLayoutItemLabel(layout)
        title_label.setText(f"Piano di base della misurazione ufficiale\nScala: 1:{scala}\nData: {datetime.now().strftime('%d.%m.%Y')}\nLegenda: www.cadastre.ch/legende")
        title_label.setFont(QFont(CADASTRA_TEXT_FAMILY, 10))
        title_label.adjustSizeToText()
        layout.addLayoutItem(title_label)
        # attemptSetSceneRect, non setItemPosition/setItemSize: quei due metodi
        # non esistono piu' nell'API dei layout di QGIS 4 e sollevavano
        # AttributeError, interrompendo la creazione del layout a meta'.
        title_label.attemptSetSceneRect(QRectF(10, 5, page_w - 20, 22))

        scalebar = QgsLayoutItemScaleBar(layout)
        scalebar.setStyle("Line Ticks Up")
        scalebar.setUnitLabel("m")
        layout.addLayoutItem(scalebar)
        scalebar.attemptSetSceneRect(QRectF(10, page_h - 22, 60, 10))
        # Collega la barra di scala alla mappa (senza linked map la barra non
        # sa a quale scala riferirsi e resta vuota/indicativa).
        scalebar.setLinkedMap(map_item)
        scalebar.applyDefaultSize()
        scalebar.update()

        # Un layout con lo stesso nome c'e' gia' quando si rigenera lo stesso
        # foglio: si sostituisce, altrimenti addLayout fallisce in silenzio e
        # resta appeso quello vecchio, che e' il modo peggiore di scoprirlo.
        gestore = project.layoutManager()
        vecchio = gestore.layoutByName(layout.name())
        if vecchio is not None:
            gestore.removeLayout(vecchio)
        gestore.addLayout(layout)
        self.log("   ✅ Layout creato: %s" % layout.name())

        reply = QMessageBox.question(self, "Esporta PDF", "Layout creato. Vuoi esportarlo in PDF/A?", _MB_SI | _MB_NO)
        if reply == _MB_SI:
            save_path, _ = QFileDialog.getSaveFileName(self, "Salva PDF", "", "PDF (*.pdf)")
            if save_path:
                try:
                    exporter = QgsLayoutExporter(layout)
                    settings = QgsLayoutExporter.PdfExportSettings()
                    settings.forceVectorOutput = True
                    result = exporter.exportToPdf(save_path, settings)
                    if result == QgsLayoutExporter.Success:
                        self.log(f"   ✅ PDF esportato: {save_path}")
                    else:
                        self.log(f"   ❌ Esportazione PDF fallita (codice {result}).", Qgis.Critical)
                except Exception as e:
                    self.log(f"   ❌ Errore PDF: {str(e)}", Qgis.Critical)

    def _parametri_planimetria(self):
        """Legge i controlli della sezione Planimetria. Ritorna
        (formato, scala, rotazione_gon, comune, data_validita)."""
        formato = self.combo_formato.currentText()
        scala = int(self.combo_scala.currentText().split(":")[1])
        return (formato, scala, self.spin_rotazione.value(),
                self.combo_comune.currentText().strip(),
                self.data_validita.date().toString("dd.MM.yyyy"))

    # --- CERCA FONDO --------------------------------------------------------
    def _gpkg_corrente(self):
        """Il GeoPackage su cui cercare: prima quello dei layer caricati (sono
        loro a dire da quale file vengono davvero), poi il campo di testo."""
        percorso = _dati_comune.gpkg_dei_layer(getattr(self, "loaded_layers", None))
        return percorso or self.txt_gpkg.text().strip()

    def aggiorna_sezioni_da_dati(self):
        """Riempie la casella delle sezioni leggendo i valori distinti di
        IdentAN. Un comune senza sezioni lascia la sola voce «Tutte»."""
        if not hasattr(self, "combo_sezione"):
            return
        # La rilettura e' agganciata al campo del GeoPackage, che cambia a ogni
        # BATTUTA DI TASTO: senza questa guardia ogni carattere digitato
        # lanciava un DISTINCT su tutta la tabella dei fondi (11 000 righe sui
        # dati di Mendrisio), e il log si riempiva di righe uguali.
        percorso = self._gpkg_corrente()
        if percorso == getattr(self, "_gpkg_sezioni", "__mai__"):
            return
        self._gpkg_sezioni = percorso

        scelta = self.combo_sezione.currentText()
        sezioni = _cerca_fondo.sezioni_disponibili(percorso)
        self.combo_sezione.clear()
        self.combo_sezione.addItem("Tutte", None)
        for codice, nome in sezioni:
            # Il NOME accanto al codice: "03 — Arzo" si sceglie, "03" no.
            # Viene da Nome_di_localita e in Ticino e' l'ex comune diventato
            # sezione; puo' mancare, e allora resta il solo codice.
            self.combo_sezione.addItem(
                "%s — %s" % (codice, nome) if nome else codice, codice)
        indice = self.combo_sezione.findText(scelta)
        if indice >= 0:
            self.combo_sezione.setCurrentIndex(indice)
        if sezioni:
            self.log("   🔢 Sezioni nei dati (%d): %s"
                     % (len(sezioni), ", ".join(
                         "%s %s" % (c, n) if n else c for c, n in sezioni)))

    def cerca_fondo(self):
        percorso = self._gpkg_corrente()
        self.lista_fondi.clear()
        self._risultati_fondo = []
        self._evidenzia_risultati([])
        self._aggiorna_comandi_fondo()
        if not percorso:
            self._esito_fondo("Nessun GeoPackage: importa i dati o indica il "
                              "file nella scheda 1.", errore=True)
            return

        numero = self.txt_fondo.text().strip()
        egrid = self.txt_egrid.text().strip()
        if not numero and not egrid:
            self._esito_fondo("Indica il numero del fondo (o un EGRID).",
                              errore=True)
            return

        # Il comune del CARTIGLIO filtra la ricerca solo se corrisponde a un
        # comune presente nei dati. Quella casella e' modificabile e serve
        # all'iscrizione del foglio: un nome scritto a mano che i dati non
        # conoscono azzerava la ricerca in silenzio, e il messaggio "nessun
        # fondo trovato" mandava a controllare numero e sezione, che erano
        # giusti.
        comune = self.combo_comune.currentText().strip() or None
        if comune:
            noti = [n.lower() for n in
                    _dati_comune.leggi_comuni(percorso) or []]
            if noti and comune.lower() not in noti:
                self.log("   ℹ️ «%s» non è fra i comuni dei dati (%s): la "
                         "ricerca non lo usa come filtro."
                         % (comune, ", ".join(noti)))
                comune = None

        risultati = _cerca_fondo.cerca(
            percorso, numero=numero or None, egrid=egrid or None,
            sezione=self.combo_sezione.currentData(), comune=comune,
            solo_in_vigore=self.chk_solo_in_vigore.isChecked())
        self._risultati_fondo = risultati

        if not risultati:
            # Anche il "niente trovato" deve spegnere l'evidenziazione
            # precedente: lasciare accesi i risultati di una ricerca vecchia
            # accanto a un messaggio di ricerca fallita e' un modo sicuro di
            # far guardare il fondo sbagliato.
            self._evidenzia_risultati([])
            self._esito_fondo("Nessun fondo trovato. Controlla numero, sezione "
                              "e comune; se il fondo è contestato, togli la "
                              "spunta «Solo fondi in vigore».", errore=True)
            return

        for f in risultati:
            voce = QListWidgetItem(f.etichetta)
            if f.extent is None:
                voce.setToolTip("Fondo senza geometria: non si può centrare "
                                "il foglio su di esso.")
            self.lista_fondi.addItem(voce)

        if len(risultati) == 1:
            # Un solo risultato: si può selezionare, non c'è ambiguità.
            self.lista_fondi.setCurrentRow(0)
            self._esito_fondo("1 fondo trovato.")
        else:
            # PIU' RISULTATI: nessuna selezione automatica. Lo stesso numero
            # esiste in ogni sezione, quindi scegliere per conto dell'utente
            # vuol dire portarlo sul fondo sbagliato senza dirglielo.
            sezioni = sorted({f.sezione for f in risultati if f.sezione})
            self._esito_fondo(
                "%d fondi con questo numero%s: scegli quale, la sezione "
                "distingue." % (len(risultati),
                                " (sezioni %s)" % ", ".join(sezioni) if sezioni else ""),
                avviso=True)
        if len(risultati) >= _cerca_fondo.LIMITE_RISULTATI:
            self.log("   ℹ️ Elenco troncato a %d risultati: restringi con "
                     "sezione o comune." % _cerca_fondo.LIMITE_RISULTATI)
        self._evidenzia_risultati(risultati)
        self._inquadra_tutti_i_risultati(risultati)
        senza_posizione = [f for f in risultati if f.extent is None]
        if senza_posizione:
            self.log("   ℹ️ %d dei %d risultati non hanno geometria: sulla "
                     "mappa non compaiono." % (len(senza_posizione), len(risultati)))
        self._aggiorna_comandi_fondo()

    def _esito_fondo(self, testo, errore=False, avviso=False):
        colore = (self._rosso_avviso() if errore
                  else "#E65100" if avviso else self._verde_ok())
        self.lbl_esito_fondo.setText("<span style='color:%s'>%s</span>"
                                     % (colore, testo))

    def _fondo_scelto(self):
        riga = self.lista_fondi.currentRow()
        if 0 <= riga < len(self._risultati_fondo):
            return self._risultati_fondo[riga]
        return None

    # --- RISULTATI EVIDENZIATI SULLA MAPPA ----------------------------------
    # Colori: il fondo scelto si stacca dagli altri. Senza distinzione, con
    # dodici risultati accesi tutti uguali non si capisce quale sia quello che
    # si sta guardando nell'elenco.
    C_RISULTATO = QColor(0, 105, 92)          # verde acqua, come l'ingombro
    C_RISULTATO_SCELTO = QColor(230, 145, 0)  # arancione

    def _pulisci_bande_risultati(self):
        """Toglie dal canvas le bande della ricerca precedente.

        Sono QgsRubberBand e NON un layer: un layer dei risultati comparirebbe
        nell'albero e, peggio, sarebbe un altro oggetto da ricordarsi di
        escludere dal foglio stampato. Le bande vivono solo sul canvas e non
        possono finire in una planimetria."""
        for banda in getattr(self, "_bande_risultati", []) or []:
            try:
                banda.reset(QgsWkbTypes.PolygonGeometry)
                scena = banda.scene()
                if scena is not None:
                    scena.removeItem(banda)
            except RuntimeError:
                pass          # il canvas se n'e' gia' andato
        self._bande_risultati = []

    def _geometria_del_fondo(self, f):
        """Il contorno vero se c'e', altrimenti il rettangolo dell'estensione.

        Il contorno arriva dal WKB (vedi cerca_fondo._contorno) e puo'
        mancare: geometria troncata, oppure il fondo e' stato localizzato dal
        solo PosFondo, che e' un punto. In quel caso un rettangolo dice
        comunque DOVE, che e' quello che serve qui."""
        punti = getattr(f, "contorno", None)
        if punti:
            return QgsGeometry.fromPolygonXY([list(punti)])
        if f.extent is None:
            return None
        est = QgsRectangle(f.extent[0], f.extent[1], f.extent[2], f.extent[3])
        if est.width() <= 0 or est.height() <= 0:
            # Ripiego su un punto solo: un quadratino di 10 m, altrimenti la
            # banda sarebbe invisibile.
            c = est.center()
            est = QgsRectangle(c.x() - 5, c.y() - 5, c.x() + 5, c.y() + 5)
        return QgsGeometry.fromRect(est)

    def _evidenzia_risultati(self, fondi):
        """Accende sul canvas tutti i fondi trovati, insieme.

        E' la risposta al caso "lo stesso numero esiste in piu' sezioni":
        l'elenco dice QUALI sono, la mappa dice DOVE stanno l'uno rispetto
        all'altro - che e' l'informazione che manca quando i nomi delle
        sezioni non si conoscono a memoria."""
        self._pulisci_bande_risultati()
        iface = getattr(self, "_iface", None)
        canvas = iface.mapCanvas() if iface else None
        if canvas is None or not fondi:
            return
        from qgis.gui import QgsRubberBand
        for f in fondi:
            geom = self._geometria_del_fondo(f)
            if geom is None:
                continue      # fondo senza posizione: non si inventa dove sta
            banda = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
            banda.setToGeometry(geom, None)
            banda.setWidth(2)
            self._bande_risultati.append(banda)
        self._colora_bande_risultati()

    def _colora_bande_risultati(self):
        """Il fondo selezionato nell'elenco si accende sulla mappa.

        E' quello che rende utile l'evidenziazione con piu' risultati: si
        scorre l'elenco e si vede quale si illumina, senza doverli aprire uno
        per uno."""
        scelto = self.lista_fondi.currentRow() if hasattr(self, "lista_fondi") else -1
        # Le bande seguono l'ordine dei risultati, ma i fondi senza posizione
        # non ne hanno una: si rifa' la corrispondenza saltandoli.
        con_posizione = [i for i, f in enumerate(getattr(self, "_risultati_fondo", []))
                         if self._geometria_del_fondo(f) is not None]
        # getattr: init_ui chiama i comandi del fondo prima che sia mai stata
        # fatta una ricerca, e i test costruiscono la dialog con __new__.
        for banda, indice in zip(getattr(self, "_bande_risultati", []),
                                 con_posizione):
            colore = (self.C_RISULTATO_SCELTO if indice == scelto
                      else self.C_RISULTATO)
            try:
                banda.setStrokeColor(colore)
                banda.setColor(QColor(colore.red(), colore.green(),
                                      colore.blue(), 50))
                banda.setWidth(3 if indice == scelto else 2)
            except RuntimeError:
                pass

    def _inquadra_tutti_i_risultati(self, fondi):
        """Porta la vista su tutti i risultati insieme.

        Solo con PIU' di un risultato: con uno solo l'utente ha gia' i due
        comandi espliciti (zoom, usa come centro) e spostargli la vista senza
        che l'abbia chiesto sarebbe una sorpresa.

        NON tocca il centro del foglio: se e' agganciato a un fondo o a delle
        coordinate resta dov'e' (vedi _centro_planimetria)."""
        iface = getattr(self, "_iface", None)
        canvas = iface.mapCanvas() if iface else None
        if canvas is None or len(fondi) < 2:
            return
        unione = QgsRectangle()
        unione.setMinimal()
        for f in fondi:
            if f.extent is None:
                continue
            unione.combineExtentWith(
                QgsRectangle(f.extent[0], f.extent[1], f.extent[2], f.extent[3]))
        if unione.isEmpty():
            return
        margine = max(unione.width(), unione.height()) * 0.10 or 20.0
        unione.grow(margine)
        canvas.setExtent(unione)
        canvas.refresh()

    def _aggiorna_comandi_fondo(self, _riga=None):
        """I due comandi restano spenti finché non c'è una scelta con una
        posizione: premerli senza selezione non saprebbe dove andare."""
        self._colora_bande_risultati()
        f = self._fondo_scelto()
        attivo = f is not None and f.extent is not None
        for pulsante in (getattr(self, "btn_zoom_fondo", None),
                         getattr(self, "btn_centra_fondo", None)):
            if pulsante is not None:
                pulsante.setEnabled(attivo)
                pulsante.setToolTip("" if attivo else
                                    "Scegli un fondo dall'elenco (con geometria)")

    def _rettangolo_fondo(self, f, margine=0.10):
        """Estensione del fondo con un margine attorno, così non tocca i bordi
        della vista. Un fondo ridotto a un punto (ripiego su PosFondo) non ha
        larghezza: gli si dà un intorno fisso, altrimenti lo zoom sarebbe
        indefinito."""
        xmin, ymin, xmax, ymax = f.extent
        dx, dy = (xmax - xmin), (ymax - ymin)
        if dx <= 0 and dy <= 0:
            dx = dy = 50.0
        m = max(dx, dy) * margine
        return QgsRectangle(xmin - m, ymin - m, xmax + m, ymax + m)

    def zoom_sul_fondo(self):
        f = self._fondo_scelto()
        if f is None or f.extent is None:
            return
        _iface = getattr(self, "_iface", None)
        if not (_iface and _iface.mapCanvas()):
            self._esito_fondo("Mappa di QGIS non disponibile.", errore=True)
            return
        _iface.mapCanvas().setExtent(self._rettangolo_fondo(f))
        _iface.mapCanvas().refresh()
        self.log("   🔍 Zoom sul fondo %s, sezione %s (%s)"
                 % (f.numero, f.sezione or "—", f.origine_geometria))

    def centra_planimetria_sul_fondo(self):
        """Fissa il centro del foglio sul fondo scelto. Il centro resta quello
        finché non si cerca un altro fondo: senza, bastava muovere la mappa
        per perdere l'inquadratura appena trovata."""
        f = self._fondo_scelto()
        if f is None or f.centro is None:
            return
        self._centro_da_fondo = QgsPointXY(f.centro[0], f.centro[1])
        # Il fondo resta agganciato anche dopo: serve al trascinamento, che
        # deve poter dire se spostando il foglio il fondo ne esce.
        self._fondo_ancorato = f
        etichetta = "fondo %s%s" % (f.numero,
                                    " sez. %s" % f.sezione if f.sezione else "")
        self._esito_fondo("Centro della planimetria fissato sul %s." % etichetta)
        self.log("   🎯 Centro planimetria: %s a E%.1f N%.1f (%s)"
                 % (etichetta, f.centro[0], f.centro[1], f.origine_geometria))
        self._avvisa_capienza(f)
        self._aggiorna_centro_fissato(etichetta)
        self._aggiorna_ingombro()

    def _rotazione_che_salva_la_scala(self, f, scala, formato):
        """Il formato e la rotazione che salvano la scala per un fondo
        trovato. Scarta il guscio del risultato di ricerca e chiama
        planimetria.rotazione_che_salva_la_scala, che ragiona di geometria e
        non deve sapere cos'e' un FondoTrovato."""
        punti = getattr(f, "contorno", None)
        if not punti or f.centro is None:
            return None, None
        return _planimetria.rotazione_che_salva_la_scala(
            punti, QgsPointXY(f.centro[0], f.centro[1]), scala, formato)

    def _avvisa_capienza(self, f):
        """Centrare non basta: la scala resta quella scelta prima, e un fondo
        piu' grande del foglio viene tagliato. Sui dati di Mendrisio, su A4
        verticale, non ci sta il 25% dei fondi a 1:500.

        L'avviso dice cosa FARE, non solo che c'è un problema. Prima proponeva
        solo di rimpicciolire la scala sullo stesso formato: per il 14.5% dei
        fondi è una perdita di dettaglio evitabile, perché alla scala voluta ci
        starebbero su un altro foglio. Passare da 1:500 a 1:1000 dimezza il
        dettaglio di un piano che non aveva bisogno di perderlo."""
        if f.extent is None:
            return
        dx, dy = f.extent[2] - f.extent[0], f.extent[3] - f.extent[1]
        formato, scala, rotazione, _c, _d = self._parametri_planimetria()

        # Due controlli distinti: se ci sta ma a filo di cornice è un'altra
        # cosa dal non starci, e va detta in un altro modo.
        edx, edy = _planimetria.estensione_ruotata(dx, dy, rotazione)
        larghezza, altezza = _planimetria.area_mappa(formato)
        if edx <= larghezza / 1000.0 * scala and edy <= altezza / 1000.0 * scala:
            stretto, _, _ = _planimetria.miglior_foglio(
                dx, dy, scala, formato, rotazione_gon=rotazione)
            if stretto != formato:
                self.log("   ℹ️ Il fondo (%.0f × %.0f m) ci sta a 1:%d su %s ma "
                         "arriva a meno di %.0f mm dalla cornice: sul foglio "
                         "stampato sembrerà tagliato."
                         % (dx, dy, scala, formato, _planimetria.MARGINE_CORTESIA))
            return

        proposta, nuova_scala, motivo = _planimetria.miglior_foglio(
            dx, dy, scala, formato, rotazione_gon=rotazione)
        if motivo == "formato":
            rimedio = ("Alla stessa scala ci sta su %s: basta cambiare formato."
                       % proposta)
        else:
            # Prima di rinunciare alla scala si prova a GIRARE il foglio: un
            # fondo lungo e stretto in diagonale ha un rettangolo circoscritto
            # molto più grande di sé, e alla scala voluta ci starebbe storto.
            # Serve la geometria vera, non l'extent: se la ricerca non l'ha
            # (WKB troncato, o ripiego su PosFondo) si resta al consiglio di
            # prima, che è comunque corretto.
            foglio_giro, giro = self._rotazione_che_salva_la_scala(f, scala, formato)
            if giro is not None:
                rimedio = ("Alla stessa scala ci sta ruotando il foglio di "
                           "%.0f gon%s." % (giro, "" if foglio_giro == formato
                                            else " su %s" % foglio_giro))
            elif motivo == "scala":
                rimedio = ("Serve 1:%d%s."
                           % (nuova_scala,
                              " su %s" % proposta if proposta != formato else ""))
            else:
                rimedio = "Non ci sta in nessun formato e in nessuna scala ufficiale."
        self.log("   ⚠️ Il fondo misura %.0f × %.0f m e a 1:%d su %s non ci "
                 "sta: verrà tagliato. %s" % (dx, dy, scala, formato, rimedio),
                 Qgis.Warning)

    def _aggiorna_centro_fissato(self, etichetta=None):
        """Avviso PERMANENTE finché il centro è agganciato a un fondo.

        Prima era un messaggio che spariva alla ricerca successiva: si poteva
        spostare la mappa, premere CREA PLANIMETRIA e ottenere un foglio
        altrove, senza nulla che lo spiegasse."""
        if not hasattr(self, "lbl_centro_fissato"):
            return
        fissato = getattr(self, "_centro_da_fondo", None) is not None
        if fissato and etichetta:
            self._etichetta_centro = etichetta
        testo = ("<span style='color:#E65100'>Centro del foglio agganciato al "
                 "%s: la vista della mappa non lo sposta.</span>"
                 % getattr(self, "_etichetta_centro", "fondo scelto")) if fissato else ""
        self.lbl_centro_fissato.setText(testo)
        self.lbl_centro_fissato.setVisible(bool(testo))
        if hasattr(self, "btn_sgancia_centro"):
            self.btn_sgancia_centro.setVisible(fissato)

    def sgancia_centro(self):
        """Torna a centrare sulla vista corrente."""
        self._centro_da_fondo = None
        self._fondo_ancorato = None
        self._aggiorna_centro_fissato()
        self._esito_fondo("Centro sganciato: il foglio segue di nuovo la vista "
                          "della mappa.")
        self.log("   🎯 Centro planimetria: torna a seguire la vista")
        self._aggiorna_ingombro()

    def _centro_planimetria(self):
        """Centro del foglio. La regola di precedenza sta in
        planimetria.centro_planimetria; qui restano le due cose che
        appartengono alla finestra: il fondo agganciato con "Cerca fondo" e
        il canvas di QGIS."""
        _iface = getattr(self, "_iface", None)
        canvas = _iface.mapCanvas() if _iface else None
        return _planimetria.centro_planimetria(
            self.loaded_layers,
            centro_fissato=getattr(self, "_centro_da_fondo", None),
            centro_vista=canvas.extent().center() if canvas else None)

    def run_planimetria(self):
        """Crea il layout della planimetria e lo apre nel compositore."""
        centro = self._centro_planimetria()
        if centro is None:
            QMessageBox.warning(self, "Planimetria",
                                "Nessuna mappa inquadrata e nessun layer caricato: "
                                "non so su cosa centrare il foglio.")
            return
        formato, scala, rotazione, comune, data_validita = self._parametri_planimetria()
        # Il comune e' una delle nove iscrizioni obbligatorie del cap.1.5.7:
        # senza, il cartiglio stampava "Comune di —" e la planimetria usciva
        # non conforme senza che nulla lo segnalasse.
        if not comune:
            # Ultimo tentativo di leggerlo dai dati prima di disturbare
            # l'utente: puo' essere che i layer siano stati caricati da un
            # progetto salvato, senza passare dall'importazione.
            trovati = self.aggiorna_comuni_da_dati()
            if trovati:
                comune = self.combo_comune.currentText().strip()
                self.log("   ℹ️ Comune letto dai dati INTERLIS: %s" % comune)
        if not comune:
            QMessageBox.warning(self, "Planimetria",
                                "Comune non trovato nei dati INTERLIS "
                                "(Layout_del_piano.Nome_comune, Comune.Nome): "
                                "indicalo a mano, e' un'iscrizione obbligatoria "
                                "del cartiglio (cap.1.5.7).")
            self.combo_comune.setFocus()
            return
        self.log("\n\U0001F4D0 PLANIMETRIA")
        try:
            layout = _planimetria.crea_planimetria(
                QgsProject.instance(), self.loaded_layers, centro, scala,
                formato=formato, rotazione_gon=rotazione, comune=comune,
                data_validita=data_validita, prodotto=self.product_mode,
                lettera_norma=self.chk_lettera_norma.isChecked(),
                log=self.log)
        except ValueError as e:
            QMessageBox.warning(self, "Planimetria", str(e))
            self.log("   \u274C %s" % e, Qgis.Warning)
            return
        self._ultima_planimetria = layout
        self._segna_scheda_fatta(self.pagina_plan, "3. Planimetria")
        self._segna_passo("plan")
        self.log("   \u2705 Centrata su %.3f, %.3f" % (centro.x(), centro.y()))
        _iface = getattr(self, "_iface", None)
        if _iface:
            try:
                _iface.openLayoutDesigner(layout)
            except Exception:
                self.log("   \u2139\uFE0F Layout creato: aprilo da Progetto > Gestore dei layout di stampa")

    def run_planimetria_pdf(self):
        """Esporta in PDF l'ultima planimetria creata."""
        layout = getattr(self, "_ultima_planimetria", None)
        # Se l'utente ha eliminato il layout dal gestore, il riferimento Python
        # resta appeso a un oggetto C++ distrutto e qualunque accesso solleva
        # RuntimeError: si verifica leggendone il nome prima di usarlo.
        if layout is not None:
            try:
                layout.name()
            except RuntimeError:
                layout = None
                self._ultima_planimetria = None
        if layout is None:
            QMessageBox.information(self, "Planimetria",
                                    "Crea prima una planimetria con 'CREA PLANIMETRIA'.")
            return
        percorso, _ = QFileDialog.getSaveFileName(self, "Salva planimetria",
                                                  "planimetria.pdf", "PDF (*.pdf)")
        if not percorso:
            return
        ok, msg = _planimetria.esporta_pdf(layout, percorso)
        if ok:
            self.log("   \u2705 PDF esportato: %s" % msg, Qgis.Success)
            self._segna_passo("pdf")
            QMessageBox.information(self, "Planimetria", "PDF esportato:\n%s" % msg)
        else:
            self.log("   \u274C Export PDF fallito: %s" % msg, Qgis.Critical)
            QMessageBox.critical(self, "Planimetria", "Export fallito: %s" % msg)

    def _sblocca_itf_dxf(self, sbloccato):
        """La spunta "ITF diverso" apre il campo della scheda DXF. Togliendola
        si torna a rispecchiare l'ITF dell'importazione, cosi' non resta un
        valore vecchio che nessuno si ricorda di aver scritto."""
        self.txt_geobau_itf.setReadOnly(not sbloccato)
        self._btn_sfoglia_itf_dxf.setEnabled(sbloccato)
        self.txt_geobau_itf.setPlaceholderText(
            "Seleziona il file dati .itf..." if sbloccato
            else "Come nella scheda \"1. Importazione\"")
        if not sbloccato:
            self._sync_geobau_itf(self.txt_itf.text())

    def _sync_geobau_itf(self, text):
        """Tiene allineato il campo ITF della scheda DXF con quello
        dell'importazione. Con la spunta "ITF diverso" attiva non tocca
        nulla: li' il valore lo decide l'utente."""
        if getattr(self, "chk_itf_diverso", None) is not None \
                and self.chk_itf_diverso.isChecked():
            return
        self.txt_geobau_itf.setText(text)
        self._geobau_itf_auto = text

    def _sync_gpkg_da_itf(self, text):
        """Propone il GeoPackage di uscita accanto all'ITF, con lo stesso nome.

        Chiude la catena dei nomi automatici: ITF -> GeoPackage -> DXF. Il
        secondo anello c'era gia' (_sync_geobau_dxf), il primo no, quindi il
        percorso di uscita andava scritto o cercato a mano ogni volta pur
        essendo, nella pratica, sempre lo stesso nome nella stessa cartella.

        Stesso patto degli altri campi automatici: se il valore attuale non e'
        quello proposto da noi, l'utente l'ha scelto e non si tocca."""
        attuale = self.txt_gpkg.text()
        if attuale and attuale != getattr(self, "_gpkg_auto", None):
            return
        text = (text or "").strip()
        proposto = ""
        if text:
            itf = Path(text)
            if itf.name:
                proposto = str(itf.with_suffix(".gpkg"))
        self.txt_gpkg.setText(proposto)
        self._gpkg_auto = proposto

    # --- TRASCINAMENTO ------------------------------------------------------
    def dragEnterEvent(self, evento):
        """Accetta il trascinamento solo se c'e' almeno un file che sappiamo
        dove mettere: accettare tutto e poi ignorare in silenzio farebbe
        sembrare il rilascio riuscito."""
        if evento.mimeData().hasUrls() and self._percorsi_utili(evento.mimeData()):
            evento.acceptProposedAction()

    dragMoveEvent = dragEnterEvent

    @staticmethod
    def _percorsi_utili(mime):
        buoni = []
        for url in mime.urls():
            percorso = url.toLocalFile()
            if not percorso:
                continue          # url remota: non e' un file da aprire
            # normpath: su Windows toLocalFile() restituisce le barre IN
            # AVANTI ("C:/Users/..."), che unite a un nome con os.path.join
            # danno un percorso misto ("C:/Users/dati\file.itf"). Windows lo
            # accetta, ma resta brutto nel campo e - peggio - non coincide
            # con il valore che ci siamo annotati come "proposto da noi",
            # quindi il nome automatico smetterebbe di aggiornarsi.
            percorso = os.path.normpath(percorso)
            if os.path.isdir(percorso):
                buoni.append(percorso)
            elif os.path.splitext(percorso)[1].lower() in (".itf", ".jar", ".gpkg"):
                buoni.append(percorso)
        return buoni

    def dropEvent(self, evento):
        """Smista i file trascinati sul campo giusto in base all'estensione.

        Una cartella significa due cose diverse a seconda di cosa contiene, e
        va detto quale delle due si e' fatta: se dentro c'e' UN SOLO .itf lo
        si prende, se ce ne sono tanti non si indovina, se non ce ne sono la
        cartella diventa la destinazione dell'uscita."""
        for percorso in self._percorsi_utili(evento.mimeData()):
            if os.path.isdir(percorso):
                self._rilascia_cartella(percorso)
                continue
            estensione = os.path.splitext(percorso)[1].lower()
            if estensione == ".itf":
                self.txt_itf.setText(percorso)
                self.log("   📥 ITF: %s" % percorso)
            elif estensione == ".jar":
                self.txt_jar.setText(percorso)
                self.log("   📥 ili2gpkg: %s" % percorso)
                self.verifica_ambiente()
            elif estensione == ".gpkg":
                self.txt_gpkg.setText(percorso)
                self._gpkg_auto = None    # scelto a mano: non piu' automatico
                self.log("   📥 GeoPackage: %s" % percorso)
        evento.acceptProposedAction()

    def _rilascia_cartella(self, cartella):
        itf = sorted(f for f in os.listdir(cartella)
                     if f.lower().endswith(".itf")
                     and os.path.isfile(os.path.join(cartella, f)))
        if len(itf) == 1:
            percorso = os.path.join(cartella, itf[0])
            self.txt_itf.setText(percorso)
            self.log("   📥 Unico ITF nella cartella: %s" % percorso)
            return
        if len(itf) > 1:
            self.log("   ⚠️ Nella cartella ci sono %d file ITF (%s): "
                     "trascina quello giusto, non la cartella."
                     % (len(itf), ", ".join(itf[:4])
                        + (", …" if len(itf) > 4 else "")), Qgis.Warning)
            return
        # Nessun ITF: la cartella vale come destinazione dell'uscita.
        base = Path(self.txt_itf.text().strip()).stem if self.txt_itf.text().strip() else ""
        if not base:
            self.log("   ⚠️ Cartella senza file ITF e nessun ITF indicato: "
                     "non so che nome dare all'uscita.", Qgis.Warning)
            return
        proposto = str(Path(cartella) / (base + ".gpkg"))
        self.txt_gpkg.setText(proposto)
        self._gpkg_auto = proposto
        self.log("   📥 Cartella di destinazione: %s" % proposto)

    def _sync_geobau_dxf(self, text):
        """Come _sync_geobau_itf, per il campo DXF: propone stesso nome/
        cartella del GeoPackage di output, con estensione .dxf."""
        current = self.txt_geobau_dxf.text()
        if current and current != getattr(self, '_geobau_dxf_auto', None):
            return
        text = text.strip()
        dxf_text = ""
        if text:
            gpkg_path = Path(text)
            if gpkg_path.name:
                dxf_text = str(gpkg_path.with_suffix('.dxf'))
        self.txt_geobau_dxf.setText(dxf_text)
        self._geobau_dxf_auto = dxf_text

    def run_geobau(self):
        """Esegue la conversione DXF con av2geobau (fork av2geobau_ti: legge
        MD01MUTI7MN95 direttamente, senza la finta "TRANSLATION OF" verso il
        modello tedesco usata dal jar ufficiale per gli altri modelli - vedi
        commento su AV2GEOBAU_JAR). Traduttore e modello .ili sono entrambi
        quelli in dotazione (MODELLO_ILI serve a risolvere --modeldir)."""
        # Guardia contro il doppio avvio (vedi run_import).
        if _vivo(getattr(self, "worker", None)) and self.worker.isRunning():
            QMessageBox.warning(self, "Operazione in corso",
                                "Un processo e' gia' in esecuzione: attendi che termini "
                                "(o chiudi la finestra per interromperlo).")
            self.log("⚠️ Avvio rifiutato: un processo e' gia' in esecuzione.", Qgis.Warning)
            return

        # Il traduttore si prende dalla costante, non dal campo di testo: il
        # campo e' li' per mostrare quale motore gira, non per sceglierlo.
        jar_path = Path(AV2GEOBAU_JAR)
        ili_path = Path(MODELLO_ILI)
        for percorso, cosa in ((jar_path, "Il traduttore DXF"),
                               (ili_path, "Il modello INTERLIS")):
            if not percorso.is_file():
                QMessageBox.warning(self, "Risorsa mancante",
                                    "%s in dotazione non e' presente "
                                    "nell'installazione del plugin:\n%s\n\n"
                                    "Reinstalla %s." % (cosa, percorso, NOME_PLUGIN))
                self.log("   ❌ Risorsa in dotazione mancante: %s" % percorso, Qgis.Critical)
                return
        itf_path = Path(self.txt_geobau_itf.text().strip())
        dxf_path = Path(self.txt_geobau_dxf.text().strip())

        self.log("\n⚙️ AVVIO av2geobau")
        self.log(f"   JAR: {jar_path}")
        self.log(f"   ITF: {itf_path}")
        self.log(f"   DXF: {dxf_path}")
        self.log(f"   Modello ILI: {ili_path}")

        if not all([jar_path.name, itf_path.name, dxf_path.name, ili_path.name]):
            QMessageBox.warning(self, "Dati Mancanti",
                                 "Compila tutti i campi di av2geobau (JAR, ITF, DXF e il modello .ili "
                                 "nel gruppo 1, necessario per risolvere --modeldir).")
            self.log("   ❌ Campi mancanti!")
            return

        # IL FILE DA SCRIVERE NON PUO' ESSERE UNO DI QUELLI DA LEGGERE.
        # av2geobau apre il DXF con un FileOutputStream, che TRONCA il file di
        # destinazione: se il campo DXF puntasse all'ITF - un percorso
        # incollato male, una scelta sbagliata nel dialogo - la conversione
        # cancellerebbe il file di partenza e poi fallirebbe, perche' non ha
        # piu' niente da leggere. Il dato di consegna del Cantone sparirebbe
        # per un errore di battitura, e non c'e' modo di recuperarlo dal
        # programma. Ne' il jar ne' il plugin lo impedivano.
        #
        # Si confrontano i percorsi RISOLTI: "..\\dati\\a.itf" e
        # "C:\\dati\\a.itf" sono lo stesso file scritti in due modi.
        letti = {"l'ITF da convertire": itf_path,
                 "il modello INTERLIS": ili_path,
                 "il traduttore av2geobau": jar_path}
        for cosa, percorso in letti.items():
            try:
                stesso = (os.path.normcase(os.path.abspath(str(dxf_path)))
                          == os.path.normcase(os.path.abspath(str(percorso))))
            except (OSError, ValueError):
                continue
            if stesso:
                QMessageBox.critical(
                    self, "Conversione DXF",
                    "Il file DXF da scrivere è lo stesso file di %s:\n%s\n\n"
                    "La conversione lo sovrascriverebbe e perderesti "
                    "l'originale. Scegli un altro nome per il DXF."
                    % (cosa, dxf_path))
                self.log("   ❌ DXF e %s sono lo stesso file: conversione "
                         "annullata per non sovrascrivere l'originale" % cosa,
                         Qgis.Critical)
                return

        # La conversione DXF puo' lavorare su un ITF diverso da quello
        # importato (la spunta "ITF diverso"): e' il caso in cui un modello
        # sbagliato passerebbe piu' facilmente inosservato, perche' quel file
        # non e' mai passato dall'importazione.
        if not self._controlla_modello_prima_di(str(itf_path), "l'ITF da convertire"):
            return

        java_exe = self.find_java()
        if not java_exe:
            QMessageBox.critical(self, "Errore", "Java non trovato.")
            self.log("   ❌ Java non trovato!")
            return

        # --modeldir: prima la cartella del modello in dotazione, poi i modelli
        # dentro il jar, poi il repository ufficiale IN HTTPS.
        #
        # Due modifiche di sicurezza rispetto a prima:
        #  - il repository era "http://models.interlis.ch/", in CHIARO. La
        #    definizione del modello governa l'interpretazione dei dati
        #    catastali, e su HTTP chiunque sia in mezzo alla connessione puo'
        #    sostituirla. Verificato che il sito risponde in HTTPS (200) e che
        #    da solo NON reindirizza da http a https: senza questa modifica il
        #    traffico restava davvero in chiaro.
        #  - tolto il placeholder %ITF_DIR, che faceva prevalere un .ili posato
        #    accanto al file di dati: il modello lo sceglieva chi fornisce
        #    l'ITF, non noi.
        #
        # Per i dati ticinesi (MD01MUTI7MN95) la rete non serve comunque: il
        # modello in dotazione e' INTERLIS 1 senza IMPORTS, quindi
        # autosufficiente - verificato convertendo un ITF reale con il solo
        # modeldir locale. Il ripiego di rete resta per i modelli federali
        # (MD01MUCH24MN95I, DM01AVCH24LV95D...), che non sono in dotazione.
        model_dir = ili_path.parent
        ilidirs = os.pathsep.join([str(model_dir), "%JAR_DIR/ilimodels",
                                   "https://models.interlis.ch/"])
        cmd = [java_exe, "-jar", str(jar_path), "--modeldir", ilidirs, str(itf_path), str(dxf_path)]
        self.log(f"   Comando: {' '.join(cmd)}")

        self.btn_import.setEnabled(False)
        self.btn_geobau.setEnabled(False)
        self._inizio_lavoro("Traduzione av2geobau")
        self.worker = JavaWorker(cmd, "av2geobau", parent=self)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.log_signal.connect(self.log)
        self.worker.finished_signal.connect(self.on_geobau_finished)
        self.worker.start()

    def on_geobau_finished(self, returncode, task_type):
        self.log(f"\n📊 Risultato av2geobau: Codice ritorno = {returncode}")
        self._fine_lavoro()
        self.btn_import.setEnabled(True)
        self.btn_geobau.setEnabled(True)
        if returncode == 0:
            # Il codice di ritorno del processo Java da solo non basta: il jar
            # puo' uscire con successo (0) anche quando il file prodotto e'
            # strutturalmente incompleto/vuoto - un controllo minimo qui
            # (dimensione, EOF, conteggio entita') avrebbe segnalato subito
            # problemi come "Error in APPID Table" scoperti solo aprendo il
            # file in AutoCAD, senza dover aspettare quel passaggio manuale.
            # Percio' la verifica viene PRIMA di dichiarare fatto: dirlo e poi
            # scoprire che il file e' vuoto lascia una spunta verde su un
            # passo non riuscito, ed e' peggio che non dire niente.
            dxf_path = self.txt_geobau_dxf.text().strip()
            valido = True
            if dxf_path:
                self.log("\n🔎 Verifica struttura DXF...")
                valido = self._validate_dxf(dxf_path)
            if valido:
                # Il primo controllo legge il file con il NOSTRO codice: se
                # sbagliamo a scrivere e sbagliamo allo stesso modo a rileggere,
                # passa. Il secondo lo fa rileggere a GDAL, che e'
                # un'implementazione diversa - ed e' quello che decide se il
                # passo e' completo. Dirlo fatto e poi scoprire che meta' del
                # disegno non si rilegge sarebbe una spunta verde su un passo
                # non riuscito.
                self._avvia_rilettura_gdal(dxf_path)
            else:
                self.log("❌ Il convertitore ha finito senza errori ma il DXF "
                         "non ha superato la verifica: il passo NON è completo.",
                         Qgis.Critical)
        else:
            self.log("❌ Esportazione DXF fallita.", Qgis.Critical)

    def _count_dxf_entities_stream(self, dxf_path, max_layers_sample=12):
        """Conta i tipi di entita' (group 0) nella sezione ENTITIES leggendo
        il file riga per riga, senza caricarlo tutto in memoria (i DXF di un
        piano cadastrale reale arrivano facilmente a decine di MB)."""
        stats = {}
        total = 0
        layers = []
        layer_seen = set()
        in_entities = False
        expect_type = False
        expect_layer = False
        # Il DXF e' fatto di COPPIE: una riga col codice, una col valore. Non
        # tenerne il conto e guardare ogni riga per conto suo sembra funzionare
        # finche' non capita un VALORE uguale a "0" - e capita di continuo: ogni
        # VERTEX 2d finisce con 70/0, ogni HATCH con 98/0. Quel valore veniva
        # scambiato per il codice di una nuova entita', la riga dopo (il vero
        # codice) veniva mangiata come se fosse un tipo, e il conteggio non si
        # risincronizzava piu': tre VERTEX e un SEQEND risultavano una entita'
        # sola. Ora le righe si leggono a due a due, come sono scritte.
        try:
            with open(dxf_path, "r", encoding="latin-1", errors="replace") as f:
                for raw in f:
                    codice = raw.strip()
                    valore_raw = f.readline()
                    if not valore_raw:
                        break
                    valore = valore_raw.strip()
                    if not in_entities:
                        if valore == "ENTITIES":
                            in_entities = True
                        continue
                    if codice == "0" and valore == "ENDSEC":
                        break
                    if codice == "0":
                        stats[valore] = stats.get(valore, 0) + 1
                        total += 1
                    elif codice == "8":
                        if valore and valore not in layer_seen and len(layer_seen) < max_layers_sample:
                            layer_seen.add(valore)
                            layers.append(valore)
        except OSError as e:
            return {"_error": str(e), "_total": 0, "_layers_sample": []}
        stats["_total"] = total
        stats["_layers_sample"] = layers
        return stats

    def _avvia_rilettura_gdal(self, dxf_path):
        """Fa rileggere il DXF a GDAL e rimanda a dopo il verdetto sul passo."""
        if not dxf_path:
            return
        self.log("\n🔁 Rilettura con GDAL (secondo parere, motore diverso dal "
                 "nostro)...")
        worker = VerificaDxfWorker(dxf_path, parent=self)
        worker.fatto.connect(self._rilettura_gdal_finita)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _rilettura_gdal_finita(self, esito, errore):
        if errore or esito is None:
            # Un guasto della verifica non e' un guasto del DXF: si dice cosa
            # non ha funzionato e si lascia buono il file, invece di bocciarlo
            # per colpa nostra.
            self.log("   ⚠️ Rilettura non riuscita: %s" % (errore or "esito assente"),
                     Qgis.Warning)
            self.log("✅ Esportazione DXF completata (senza il secondo parere).",
                     Qgis.Success)
            self._segna_scheda_fatta(self.pagina_dxf, "2. Conversione DXF")
            self._segna_passo("dxf")
            return
        for riga in _verifica_dxf.righe_di_esito(esito):
            self.log(riga, Qgis.Critical if riga.strip().startswith("❌") else Qgis.Info)

        # PRECISIONE ITF -> DXF: l'unico controllo che confronta l'uscita con
        # l'INGRESSO, e non il DXF con se stesso. Serve a DIMOSTRARE che la
        # conversione non ha toccato le coordinate, invece di affermarlo.
        # Costa mezzo secondo su un comune intero, quindi resta nel thread
        # dell'interfaccia insieme al resto del riassunto.
        itf_convertito = self.txt_geobau_itf.text().strip()
        if os.path.isfile(itf_convertito):
            try:
                dev = _verifica_dxf.deviazione_coordinate(itf_convertito,
                                                          str(dxf_path))
            except Exception as e:              # un ITF illeggibile non e' un
                self.log("   ⚠️ Deviazione delle coordinate non misurata: %s"
                         % e, Qgis.Warning)     # motivo per bocciare il DXF
            else:
                livello = Qgis.Critical if dev["oltre_tolleranza"] else Qgis.Info
                for riga in _verifica_dxf.righe_deviazione(dev):
                    self.log("   📏 %s" % riga, livello)
                if dev["oltre_tolleranza"]:
                    esito.problemi.append(
                        "le coordinate del DXF non coincidono con quelle "
                        "dell'ITF: scarto massimo %.4f m in X, %.4f m in Y"
                        % (dev["max_x"], dev["max_y"]))

        if esito.ok:
            self.log("✅ Esportazione DXF completata e riletta!", Qgis.Success)
            self._segna_scheda_fatta(self.pagina_dxf, "2. Conversione DXF")
            self._segna_passo("dxf")
        else:
            self.log("❌ Il DXF non supera la rilettura: il passo NON è completo.",
                     Qgis.Critical)
            QMessageBox.warning(self, "Verifica DXF",
                                "Il DXF è stato prodotto ma rileggendolo con "
                                "GDAL non torna:\n\n%s"
                                % "\n".join(esito.problemi))

    def _validate_dxf(self, dxf_path):
        """Controlli strutturali minimi su un DXF appena esportato: esiste,
        non e' vuoto, ha SECTION/EOF, contiene almeno un'entita' geometrica.
        Non ripara nulla (i problemi noti - LTYPE a lunghezza 0, $HANDSEED
        placeholder - sono gia' risolti alla fonte nel writer Java): serve
        solo a far emergere subito un file strutturalmente incompleto,
        invece di scoprirlo solo aprendolo in AutoCAD."""
        path = Path(dxf_path)
        if not path.is_file():
            self.log(f"   ❌ DXF non creato: {path}", Qgis.Critical)
            return False
        size = path.stat().st_size
        self.log(f"   📏 Dimensione DXF: {size} byte")
        if size < 200:
            self.log("   ❌ DXF sospettosamente piccolo (probabile file vuoto/corrotto).", Qgis.Critical)
            return False

        head_lines = []
        tail_lines = []
        try:
            with open(path, "r", encoding="latin-1", errors="replace") as f:
                for i, line in enumerate(f):
                    if i >= 80:
                        break
                    head_lines.append(line.rstrip("\n"))
                f.seek(max(0, size - 8000))
                tail_lines = f.read().splitlines()[-40:]
        except OSError as e:
            self.log(f"   ⚠️ Lettura DXF fallita: {e}", Qgis.Warning)
            return False

        if not any(l.strip() == "SECTION" for l in head_lines):
            self.log("   ⚠️ Nessuna SECTION trovata in testa al DXF (formato inatteso).", Qgis.Warning)

        has_eof = any(l.strip() == "EOF" for l in tail_lines) or any(l.strip() == "EOF" for l in head_lines)
        if has_eof:
            self.log("   ✅ EOF presente")
        else:
            self.log("   ⚠️ EOF assente in coda al DXF (file troncato?).", Qgis.Warning)

        stats = self._count_dxf_entities_stream(path)
        if "_error" in stats:
            self.log(f"   ⚠️ Analisi entità fallita: {stats['_error']}", Qgis.Warning)
            return True
        total = stats.pop("_total", 0)
        layers_sample = stats.pop("_layers_sample", [])
        self.log(f"   📊 Entità in ENTITIES: {total}")
        if total <= 0:
            self.log("   ❌ Nessuna entità geometrica trovata nel DXF.", Qgis.Critical)
            return False
        top = sorted(stats.items(), key=lambda kv: -kv[1])[:8]
        self.log("   📊 Tipi principali: " + ", ".join(f"{k}={v}" for k, v in top))
        if layers_sample:
            self.log("   📋 Layer (campione): " + ", ".join(layers_sample))
        return True

# ==================================================================================================================
# 5. ENTRY POINT PLUGIN QGIS
# ==================================================================================================================
class TIDashboardPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = Path(__file__).parent
        self.actions = []
        self.menu_name = "&TIDashboard"
        self.toolbar = self.iface.addToolBar("TIDashboard")
        self.toolbar.setObjectName("TIDashboard")
        self.dialog = None

    def initGui(self):
        icon_path = self.plugin_dir / "icon.png"
        icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
        action = QAction(icon, "TIDashboard", self.iface.mainWindow())
        action.triggered.connect(self.run)
        self.iface.addPluginToMenu(self.menu_name, action)
        self.toolbar.addAction(action)
        self.actions.append(action)

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.menu_name, action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    def run(self):
        if self.dialog is None:
            self.dialog = TIDashboardDialog(self.iface.mainWindow(), iface=self.iface)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
