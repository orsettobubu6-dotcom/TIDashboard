# TIDashboard - dati della misurazione ufficiale svizzera in QGIS
# Copyright (C) 2026 Gabriele Peverelli
#
# Questo programma e' software libero: lo si puo' ridistribuire e modificare
# secondo i termini della GNU General Public License pubblicata dalla Free
# Software Foundation, versione 2 o (a scelta) una successiva. Il testo si
# trova nel file LICENSE distribuito insieme al programma.

# Costruzione dei simboli: caricamento di font e SVG, correzioni di dimensione
# e ancoraggio, e le funzioni che assemblano riempimenti, linee e marcatori.
# Estratte da tidashboard.py.
#
# Qui sta il "come si disegna"; il "cosa si disegna" (quale simbolo per quale
# tabella) resta nei generatori di stile.
import os
import tempfile
from pathlib import Path

from qgis.PyQt.QtCore import QPointF
from qgis.PyQt.QtGui import QFont, QFontDatabase
from qgis.PyQt.QtXml import QDomDocument
from qgis.core import (
    Qgis, QgsSimpleFillSymbolLayer, QgsLinePatternFillSymbolLayer,
    QgsPointPatternFillSymbolLayer, QgsSimpleLineSymbolLayer,
    QgsSimpleMarkerSymbolLayer, QgsMarkerLineSymbolLayer,
    QgsSvgMarkerSymbolLayer, QgsFontMarkerSymbolLayer,
    QgsRuleBasedRenderer, QgsFillSymbol, QgsLineSymbol, QgsMarkerSymbol,
    QgsSingleSymbolRenderer, QgsReadWriteContext, QgsStyle,
)

try:
    from .colori import C_NERO, C_BIANCO, C_TRAMA_50
except ImportError:
    from colori import C_NERO, C_BIANCO, C_TRAMA_50

SYMBOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "symbols")
FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
_svg_path_cache = {}


def _svg_symbol_path(tasto, mask=False):
    """Trova il file SVG per un dato tasto alfanumerico Cadastra Symbol (es.
    'H', 'b', '3') in symbols/normal o symbols/mask. Il tasto e' case-sensitive
    (es. 'P' e 'p' sono simboli diversi nel set ufficiale). Ritorna None se il
    file non viene trovato (fallback gestito dal chiamante)."""
    key = (mask, tasto)
    if key in _svg_path_cache:
        return _svg_path_cache[key]
    folder = os.path.join(SYMBOLS_DIR, "mask" if mask else "normal")
    path = None
    if os.path.isdir(folder):
        prefix = f"Symbol_{tasto}_"
        for fname in os.listdir(folder):
            if fname.startswith(prefix) and fname.lower().endswith(".svg"):
                path = os.path.join(folder, fname)
                break
    # I fallimenti (None) NON vanno cachati: se la cartella symbols/ viene
    # ripristinata durante la stessa sessione QGIS (es. reinstallazione del
    # plugin senza riavvio), un None cachato continuerebbe a restituire il
    # fallback generico fino al riavvio di QGIS. Si cachano solo le
    # risoluzioni riuscite; i None verranno semplicemente ricercati di nuovo
    # alla prossima chiamata (una scansione di cartella, costo trascurabile).
    if path is not None:
        _svg_path_cache[key] = path
    return path

# Frazione occupata dal disegno effettivo (ink) rispetto al viewBox 25.51x25.51
# di ciascun simbolo del set Cadastra Symbol SVG 2024, misurata rasterizzando
# ogni SVG con QSvgRenderer/QImage e cercando il bounding box dei pixel non
# trasparenti (script one-off, non incluso nel plugin). Il viewBox e' un
# "riquadro di disegno" condiviso da tutti i 57 simboli, non il contorno del
# glifo: un tasto piccolo come 'I' (non materializzato) occupa solo il 6% del
# riquadro, mentre 'P' (bedeutsamer HGP) ne occupa il 40%. Passare 'size'
# direttamente a QgsSvgMarkerSymbolLayer scala l'intero riquadro, quindi la
# grandezza VISIBILE risultante e' 'size' * frazione: usando le grandezze di
# circ154_allegato2 cap.2 cosi' come sono (pensate come diametro visibile in
# mm, es. G=0.8mm), il segno effettivo diventava sub-pixel e invisibile a
# schermo (0.8mm * 0.1125 = 0.09mm). _svg_effective_size() compensa dividendo
# per la frazione, cosi' il diametro VISIBILE finale corrisponde davvero al
# valore in mm del documento.
_SVG_INK_FRACTION = {
    '1': 0.775, '2': 0.7625, '3': 0.2225, '4': 0.3325, '5': 0.42, '6': 0.3975, '7': 0.7125,
    'A': 0.3525, 'B': 0.42, 'C': 0.2125, 'D': 0.2125, 'E': 0.1775, 'F': 0.1325, 'G': 0.1125,
    'H': 0.2025, 'I': 0.06, 'J': 0.2875, 'K': 0.2875, 'L': 0.2875, 'M': 0.2875, 'N': 0.3975,
    'O': 0.42, 'P': 0.3975, 'Q': 0.3975, 'R': 0.3975, 'S': 0.3975, 'T': 0.3975, 'U': 0.3975,
    'V': 0.3975, 'W': 0.3975, 'X': 0.3975,
    'a': 0.66, 'b': 0.3325, 'c': 0.4275, 'd': 0.4425, 'e': 0.44, 'f': 0.3575, 'g': 0.44,
    'h': 0.44, 'i': 0.44, 'j': 0.4425, 'k': 0.4425, 'l': 0.44, 'm': 0.44, 'n': 0.55,
    'o': 0.4425, 'p': 0.4425, 'q': 0.355, 'r': 0.5525, 's': 0.5525, 't': 0.135, 'u': 0.265,
    'v': 0.2225, 'w': 0.4425, 'x': 0.4425, 'y': 0.4425, 'z': 0.5525,
}
_SVG_INK_FRACTION_DEFAULT = 0.35  # fallback se un tasto non e' in tabella (media approssimativa)

def _svg_effective_size(ch, desired_mm):
    """Converte la grandezza VISIBILE desiderata (in mm, come da
    circ154_allegato2) nel valore di 'size' da passare a
    QgsSvgMarkerSymbolLayer, compensando il padding del viewBox (vedi
    _SVG_INK_FRACTION)."""
    frac = _SVG_INK_FRACTION.get(ch, _SVG_INK_FRACTION_DEFAULT)
    return desired_mm / frac

# Font ufficiale CadastraSymbol (+ variante "Mask" per l'alone), su richiesta
# esplicita dell'utente ("passa al font cadastra con la maschera come da
# direttiva e circolare"), usato SOLO per Punto_di_confine/PCGiurisdizionale,
# PFP/PFA e Segnale/Tavola_cippo condotta (vedi make_true_font_marker_with_mask):
# tutti gli altri simboli puntiformi (Elemento_puntiforme, confine nazionale/
# cantonale su linea, trame vigna/torbiera/canneto) restano sugli SVG sopra,
# non menzionati dalla richiesta. File copiati dentro il plugin (fonts/) per
# non dipendere da un'installazione di sistema: caricati a runtime via
# QFontDatabase.addApplicationFont(), non richiedono che l'utente li installi.
FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
CADASTRA_SYMBOL_FAMILY = "CadastraSymbol"
CADASTRA_SYMBOL_MASK_FAMILY = "CadastraSymbol Mask"
_cadastra_symbol_font_loaded = False

def _load_font_file(path):
    """Carica un singolo file .ttf nel database font dell'applicazione,
    verificando che il file esista e che QFontDatabase.addApplicationFont()
    lo accetti davvero (ritorna -1 su file corrotto/formato non supportato -
    prima il fallimento era silenzioso e i simboli/testi ricadevano su un
    font sostitutivo senza alcun avviso)."""
    if not os.path.exists(path):
        QgsMessageLog.logMessage(
            f"File font non trovato: {path} - i simboli/etichette useranno "
            "un font sostitutivo.", "TIDashboard", Qgis.Warning)
        return
    if QFontDatabase.addApplicationFont(path) == -1:
        QgsMessageLog.logMessage(
            f"Caricamento font fallito: {path} (file corrotto o formato non "
            "supportato) - i simboli/etichette useranno un font sostitutivo.",
            "TIDashboard", Qgis.Warning)

def _ensure_cadastra_symbol_font_loaded():
    """Carica CadastraSymbol-Regular.ttf/CadastraSymbol-Mask.ttf una sola volta
    per sessione QGIS. I nomi famiglia effettivi (CADASTRA_SYMBOL_FAMILY/_MASK_
    FAMILY) sono stati verificati via QFontDatabase.applicationFontFamilies()
    dopo il caricamento, non assunti: CadastraSymbol-Mask.ttf dichiara due
    famiglie ('CadastraSymbol Mask', 'CadastraSymbol'), la prima e' quella
    giusta per non collidere con il font regular."""
    global _cadastra_symbol_font_loaded
    if _cadastra_symbol_font_loaded:
        return
    for fname in ("CadastraSymbol-Regular.ttf", "CadastraSymbol-Mask.ttf"):
        _load_font_file(os.path.join(FONTS_DIR, fname))
    _cadastra_symbol_font_loaded = True

# Font di TESTO "Cadastra" (etichette: nomi, numeri di fondo, ecc. - vedi
# TEXT_LABEL_RULES/_apply_labels_to_layer), DIVERSO dal font di simboli
# CadastraSymbol sopra. Fino a questo fix veniva referenziato con
# QFont("Cadastra", size) assumendo che fosse installato a livello di
# sistema operativo: se non installato (es. su una macchina diversa da
# quella di sviluppo), Qt sostituiva silenziosamente un font qualunque,
# senza alcun errore/avviso - stesso problema gia' risolto per CadastraSymbol,
# qui semplicemente non ancora applicato. I 4 file (Regular/Bold/Italic/
# BoldItalic) dichiarano TUTTI la stessa famiglia "Cadastra" (verificato via
# QFontDatabase.applicationFontFamilies()), con lo stile bold/italic gia'
# incorporato in ciascun file: caricarli tutti e
# quattro nel database font dell'applicazione basta perche' Qt scelga da
# solo il file giusto quando setBold()/setItalic() vengono chiamati su un
# QFont("Cadastra", ...) - non serve referenziare i file per nome altrove.
CADASTRA_TEXT_FAMILY = "Cadastra"
_cadastra_text_font_loaded = False

def _ensure_cadastra_text_font_loaded():
    global _cadastra_text_font_loaded
    if _cadastra_text_font_loaded:
        return
    for fname in ("Cadastra-Regular.ttf", "Cadastra-Bold.ttf",
                  "Cadastra-Italic.ttf", "Cadastra-BoldItalic.ttf"):
        _load_font_file(os.path.join(FONTS_DIR, fname))
    _cadastra_text_font_loaded = True

# Frazione ink/dimensione-nominale per i tasti CadastraSymbol usati da
# Punto_di_confine/PFP/PFA/Segnale condotta, misurata con
# QFontMetricsF.tightBoundingRect() a corpo 1000pt (script one-off, non
# incluso nel plugin) - stesso motivo della tabella _SVG_INK_FRACTION: la
# dimensione nominale passata a QgsFontMarkerSymbolLayer non e' la dimensione
# visibile del glifo. Font Regular e Mask hanno bounding box quasi identici
# per ogni tasto (stesso contorno esterno, la differenza e' il riempimento
# pieno invece che cavo) tranne 'I', dove il glifo Mask e' disegnato
# volutamente piu' grande (fraz. 0.15 contro 0.099 del Regular) - un punto
# non materializzato e' cosi' piccolo che il solo riempimento pieno non
# basterebbe a renderlo leggibile come alone.
_FONT_INK_FRACTION = {
    'A': 0.5972, 'B': 0.7097, 'C': 0.3579, 'D': 0.3579, 'E': 0.2989, 'F': 0.2250,
    'G': 0.1869, 'H': 0.3426, 'I': 0.0994, 'J': 0.4858, 'K': 0.4858, 'L': 0.4858,
    'M': 0.4858, 'N': 0.6727, 'P': 0.6727, 'Q': 0.6727, 'R': 0.6727,
    'l': 0.7474, 'm': 0.7474,
    # Elemento_puntiforme (o/g/i/k/h/p/n/f/u/y/q/a): stessa misurazione,
    # QFontMetricsF.tightBoundingRect a corpo 1000pt. 'u' (Rovina/oggetto
    # archeologico) e' un caso noto: il font Mask non ha il glifo corretto
    # (ripiega su un fallback testuale, verificato via QRawFont.
    # supportsCharacter()==False e via render) - l'alone per 'u' risultera'
    # visibilmente sbagliato (una lettera "u" invece di un alone a L), difetto
    # accettato esplicitamente dall'utente invece di lasciare 'u' sugli SVG.
    'o': 0.7478, 'g': 0.7465, 'i': 0.7471, 'k': 0.7470, 'h': 0.7474, 'p': 0.7481,
    'n': 0.9304, 'f': 0.6038, 'u': 0.4488, 'y': 0.7470, 'q': 0.5978, 'a': 1.1202,
    # make_font_marker_line (Confine_nazionale/Confine_cantonale): stessa misurazione.
    '3': 0.3739, '4': 0.5612,
}
_FONT_INK_FRACTION_MASK_I = 0.1500  # vedi nota sopra: solo 'I' differisce tra Regular e Mask
_FONT_INK_FRACTION_DEFAULT = 0.5

def _font_effective_size(ch, desired_mm, mask=False):
    """Converte la grandezza VISIBILE desiderata (in mm) nel valore di 'size'
    da passare a QgsFontMarkerSymbolLayer, compensando la differenza tra
    dimensione nominale e ink del glifo (vedi _FONT_INK_FRACTION)."""
    if mask and ch == 'I':
        frac = _FONT_INK_FRACTION_MASK_I
    else:
        frac = _FONT_INK_FRACTION.get(ch, _FONT_INK_FRACTION_DEFAULT)
    return desired_mm / frac

# BUG REALE (segnalato dall'utente: "i simboli sono belli ma non sono dove
# devono essere"): il punto di ancoraggio "Center" di QgsFontMarkerSymbolLayer
# NON coincide col centro dell'ink del glifo per il font CadastraSymbol -
# verificato misurando il centroide dei pixel neri renderizzati rispetto al
# punto vero (script one-off: render del glifo su un QImage, ricerca del
# centroide dei pixel non bianchi, confronto col centro noto). L'offset
# orizzontale e' quasi sempre trascurabile (<1.3% della dimensione, tranne
# 'u'/'3'/'4' intorno al 6-8%), ma quello VERTICALE e' rilevante e NON
# costante tra i caratteri (da -6% per 'y' a -80% per 'n'): non e' un singolo
# valore di offset del font (es. baseline vs mezzo dell'em-box), dipende dalla
# posizione verticale di ciascun glifo. Valori come frazione della dimensione
# effettiva passata a QgsFontMarkerSymbolLayer (fx, fy) - l'offset da
# applicare e' quindi (fx*size, fy*size), NON una costante in mm.
_FONT_OFFSET_FRACTION = {
    'A': (0.0056, -0.3614), 'B': (0.0029, -0.3727), 'C': (0.0019, -0.3712),
    'D': (0.0018, -0.3714), 'E': (0.0066, -0.3701), 'F': (0.0068, -0.3713),
    'G': (0.0123, -0.3696), 'H': (0.0096, -0.3707), 'I': (0.0061, -0.3691),
    'J': (0.0089, -0.3721), 'K': (0.0090, -0.3714), 'L': (0.0096, -0.3709),
    'M': (0.0085, -0.3695), 'N': (0.0073, -0.3656), 'P': (0.0064, -0.3669),
    'Q': (0.0069, -0.3665), 'R': (0.0061, -0.3670), 'a': (-0.0029, -0.3450),
    'f': (0.0041, -0.2974), 'g': (0.0050, -0.3158), 'h': (0.0078, -0.2758),
    'i': (0.0069, -0.5111), 'k': (0.0065, -0.1840), 'm': (0.0069, -0.2478),
    'n': (0.0011, -0.7997), 'o': (0.0035, -0.3684), 'p': (0.0123, -0.3723),
    'q': (0.0069, -0.3683), 'u': (0.0655, -0.2830), 'y': (0.0066, -0.0617),
    'l': (0.0078, -0.2330), '3': (0.0757, -0.3712), '4': (0.0790, -0.3686),
}
_FONT_OFFSET_FRACTION_DEFAULT = (0.0, -0.37)  # fallback: la maggioranza dei tasti cade qui

def _font_marker_offset(ch, effective_size):
    fx, fy = _FONT_OFFSET_FRACTION.get(ch, _FONT_OFFSET_FRACTION_DEFAULT)
    return QPointF(fx * effective_size, fy * effective_size)

_CAP_HEIGHT_RATIO = 0.7290

def _font_size_for_cap(cap_mm):
    """Dimensione font (mm) che produce l'altezza maiuscola richiesta (mm)."""
    return cap_mm / _CAP_HEIGHT_RATIO

# ==================================================================================================================
# 2. FUNZIONI HELPER PER COSTRUIRE SIMBOLI
# ==================================================================================================================

def gbc(is_gb, color):
    """Colore da usare per un elemento colorato: nero se GB (piano per il registro
    fondiario, rappresentato esclusivamente in bianco e nero), altrimenti il colore
    ufficiale del Piano di base (PB-MU, a colori)."""
    return C_NERO if is_gb else color

def genere_in(values, field="genere"):
    """Espressione che confronta 'field' con uno o piu' valori foglia di
    un'enumerazione ILI gerarchica (es. Genere_CS, Genere_OS, Materiale).
    ili2db esporta i valori annidati come percorso puntato completo a partire
    dal nodo subito sotto la radice del dominio (es. 'bosco_fitto' -> valore
    reale 'bosco.bosco_fitto', 'vigna' -> 'humus.coltura_intensiva.vigna'),
    non il solo valore foglia usato nei nomi ili - confermato via diagnostica
    su un GeoPackage reale (Fase 2, log 'Valori distinti Genere in SuperficieCS').
    Confrontare con '=' soltanto avrebbe sempre fallito per ogni valore non di
    primo livello. Qui si accetta sia il valore esatto (nodi di primo livello,
    es. 'edificio') sia la corrispondenza come suffisso dopo un punto (nodi
    annidati a qualunque profondita')."""
    parts = []
    for v in values:
        parts.append(f"\"{field}\" = '{v}'")
        parts.append(f"\"{field}\" LIKE '%.{v}'")
    return "(" + " OR ".join(parts) + ")"

def make_fill(color=None, out_c=C_NERO, out_w=0.20, out_s="solid", dash=None):
    """Crea un riempimento semplice con colori esatti. 'dash', se indicato, imposta
    un pattern di tratteggio esatto in mm sul contorno (come make_line), altrimenti
    'out_s' resta il preset QGIS generico ("solid"/"dash"/...)."""
    p = {'outline_width': str(out_w), 'outline_width_unit': 'MM', 'outline_style': out_s}
    p['color'] = f"{color.red()},{color.green()},{color.blue()},255" if color else "0,0,0,0"
    p['outline_color'] = f"{out_c.red()},{out_c.green()},{out_c.blue()},255"
    if dash:
        p['customdash'] = dash
        p['customdash_unit'] = 'MM'
        p['use_custom_dash'] = '1'
    return QgsSimpleFillSymbolLayer.create(p)

def make_outline(c=C_NERO, w=0.20, dash=None):
    """Contorno di un POLIGONO disegnato come vero simbolo di linea.

    Serve perche' QgsSimpleFillSymbolLayer IGNORA 'customdash': impostando un
    pattern esatto sul contorno del riempimento, QGIS disegna comunque il
    preset generico di Qt (misurato: 1.00/0.20 mm invece dei 1.5/0.5 di
    "interrotto1"), e il preset scala con lo spessore del pennino invece di
    essere una misura assoluta in mm. Con un QgsSimpleLineSymbolLayer il
    pattern viene invece rispettato alla lettera.

    'capstyle=flat' e' indispensabile: col cap di default ogni tratto viene
    esteso di mezzo spessore per lato, quindi 1.5/0.5 renderizza 1.70/0.30
    (misurato). Con il cap piatto si ottengono esattamente 1.50/0.50.
    """
    p = {'line_color': f"{c.red()},{c.green()},{c.blue()},255",
         'line_width': str(w), 'line_width_unit': 'MM', 'line_style': 'solid'}
    if dash:
        p['use_custom_dash'] = '1'
        p['customdash'] = dash
        p['customdash_unit'] = 'MM'
        p['capstyle'] = 'flat'
    return QgsSimpleLineSymbolLayer.create(p)

def fill_dash(fill_c, out_c=C_NERO, out_w=0.20, dash=None, extra=None):
    """Symbol layer di un poligono con contorno tratteggiato ESATTO: riempimento
    senza contorno, eventuali trame, e per ultimo il contorno come linea vera
    (vedi make_outline). L'ordine mette il contorno sopra alla trama, come sul
    piano stampato."""
    layers = [make_fill(fill_c, out_c, 0.0, "no")]
    if extra:
        layers.extend(extra)
    layers.append(make_outline(out_c, out_w, dash))
    return layers

def make_hatch(c=C_TRAMA_50, w=0.15, d=1.5, a=45.0):
    """Crea un tratteggio (line pattern fill) con colore esatto."""
    return QgsLinePatternFillSymbolLayer.create({
        'color': f"{c.red()},{c.green()},{c.blue()},255",
        'line_width': str(w), 'distance': str(d),
        'distance_unit': 'MM', 'angle': str(a), 'line_width_unit': 'MM'
    })

def make_point_pattern(c=C_NERO, d=2.0, size=0.3):
    """Crea un pattern a punti.
    NB: QgsPointPatternFillSymbolLayer.create() vuole le chiavi 'distance_x'/
    'distance_y' (verificato via l.properties() in QGIS 4.0.3) - non esiste una
    chiave 'distance' generica. Usarla lascia silenziosamente la spaziatura al
    valore di default del costruttore (15mm x 15mm), ignorando 'd' del tutto:
    bug che rendeva identiche (e sbagliate) tutte le trame a punti del plugin."""
    l = QgsPointPatternFillSymbolLayer.create({
        'distance_x': str(d), 'distance_y': str(d),
        'distance_x_unit': 'MM', 'distance_y_unit': 'MM'
    })
    sub = QgsSimpleMarkerSymbolLayer.create({
        'name': 'circle',
        'color': f"{c.red()},{c.green()},{c.blue()},255",
        'outline_color': '0,0,0,0',
        'size': str(size), 'size_unit': 'MM'
    })
    m = QgsMarkerSymbol()
    m.deleteSymbolLayer(0)
    m.appendSymbolLayer(sub)
    l.setSubSymbol(m)
    return l

def make_font_point_pattern(ch, c=C_TRAMA_50, d=10.0, size=3.0, fn="CadastraSymbol"):
    """Trama a punti con simbolo Cadastra Symbol ripetuto (Vigna=tasto 'b',
    Canneto='c', Torbiera='d'), come prescritto da circ154_allegato2.pdf cap.4
    "Simboli associati a superfici": grandezza e distanza esatte del tasto.
    Colore grigio ~50% (valore indicativo di trama a mezzatinta - il documento
    specifica esplicitamente che "tutte le trame composte di simboli sono
    rappresentate in grigio (valore indicativo ca. 50%) ad eccezione delle
    trame punteggiate (bosco, superficie boscata e pascolo)", che restano nere).
    Usa il set SVG ufficiale (symbols/normal) invece del font: il parametro
    'fn' e' ignorato, mantenuto solo per compatibilita' con le chiamate esistenti.
    NB: le chiavi corrette per QgsPointPatternFillSymbolLayer.create() sono
    'distance_x'/'distance_y' (non 'distance' - vedi make_point_pattern).
    NB2: 'size' e' la grandezza VISIBILE voluta (in mm); viene compensata con
    _svg_effective_size() per il padding del viewBox SVG (vedi _SVG_INK_FRACTION)."""
    l = QgsPointPatternFillSymbolLayer.create({
        'distance_x': str(d), 'distance_y': str(d),
        'distance_x_unit': 'MM', 'distance_y_unit': 'MM'
    })
    sub = QgsMarkerSymbol()
    sub.deleteSymbolLayer(0)
    path = _svg_symbol_path(ch, mask=False)
    if path:
        sub.appendSymbolLayer(QgsSvgMarkerSymbolLayer.create({
            'name': path, 'size': str(_svg_effective_size(ch, size)), 'size_unit': 'MM',
            'fill': f"{c.red()},{c.green()},{c.blue()},255",
            'outline': '0,0,0,0', 'outline_width': '0',
            'horizontal_anchor_point': '1', 'vertical_anchor_point': '1'
        }))
    else:
        sub.appendSymbolLayer(make_simple_marker("circle", size * 0.3, c))
    l.setSubSymbol(sub)
    return l

def make_line(c=C_NERO, w=0.20, dash=None):
    """Crea una linea con spessore esatto in mm."""
    p = {'line_color': f"{c.red()},{c.green()},{c.blue()},255",
         'line_width': str(w), 'line_width_unit': 'MM', 'penstyle': 'solid'}
    if dash:
        p['customdash'] = dash
        p['customdash_unit'] = 'MM'
        p['use_custom_dash'] = '1'
        # cap piatto: senza, ogni tratto si allunga di mezzo spessore per lato
        # (1.5/0.5 renderizzato 1.70/0.30, misurato) - vedi make_outline.
        p['capstyle'] = 'flat'
    return QgsSimpleLineSymbolLayer.create(p)

def make_font_marker_line(ch, interval, c=C_NERO, sz=2.4, fn="CadastraSymbol"):
    """Linea con simbolo Cadastra Symbol ripetuto a intervalli regolari, come
    prescritto per Confine_nazionale (tasto '3') e Confine_cantonale (tasto '4')
    da circ154_allegato2.pdf ("Tasto alfanumerico simbolo CADASTRA"). Usa il
    font ufficiale CadastraSymbol (verificato: Regular e Mask hanno lo stesso
    contorno per '3'/'4' - a differenza di 'b'/'c'/'d' in
    make_font_point_pattern, dove il Mask e' un rettangolo generico non
    corrispondente alla sagoma reale, lasciati quindi sugli SVG). Nessun
    alone qui (a differenza di make_true_font_marker_with_mask): non
    presente nella versione precedente, comportamento invariato. Il
    parametro 'fn' e' ignorato (il font e' sempre CADASTRA_SYMBOL_FAMILY),
    mantenuto solo per compatibilita' con le chiamate esistenti.
    'sz' e' la grandezza VISIBILE voluta (in mm), compensata via
    _font_effective_size(). Include la stessa correzione di ancoraggio di
    make_true_font_marker_with_mask (vedi _FONT_OFFSET_FRACTION) - l'offset
    e' nello spazio locale del marker, quindi ruota correttamente insieme al
    simbolo (setRotateSymbols)."""
    _ensure_cadastra_symbol_font_loaded()
    sub = QgsMarkerSymbol()
    sub.deleteSymbolLayer(0)
    size = _font_effective_size(ch, sz)
    fl = QgsFontMarkerSymbolLayer.create({
        'font': CADASTRA_SYMBOL_FAMILY, 'chr': ch,
        'size': str(size), 'size_unit': 'MM',
        'color': f"{c.red()},{c.green()},{c.blue()},255",
        'horizontal_anchor_point': '1', 'vertical_anchor_point': '1'
    })
    fl.setOffset(_font_marker_offset(ch, size))
    sub.appendSymbolLayer(fl)
    ml = QgsMarkerLineSymbolLayer.create({'interval': str(interval), 'interval_unit': 'MM'})
    ml.setRotateSymbols(True)
    ml.setSubSymbol(sub)
    return ml

def make_true_font_marker_with_mask(ch, sz=2.4, c=C_NERO, mask_color=C_BIANCO, halo_scale=1.25):
    """Marker con alone bianco dietro al simbolo vero (leggibilita' quando il
    punto cade su una linea nera), col font ufficiale CadastraSymbol invece
    degli SVG usati altrove nel file (make_font_marker_line/
    make_font_point_pattern) - su richiesta esplicita dell'utente, per
    Punto_di_confine/PCGiurisdizionale, PFP/PFA, Segnale/Tavola_cippo condotta
    e Elemento_puntiforme. Solo 2 livelli (contro i 3 dell'analoga versione
    SVG rimossa, make_font_marker_with_mask): il
    font CadastraSymbol-Mask fornisce gia' un glifo PIENO alla stessa
    posizione/tasto del Regular (verificato via render: il vuoto al centro
    di 'H' mostra correttamente il bianco sottostante), quindi non serve un
    "tappo" separato per il forellino centrale. 'halo_scale' ingrandisce il
    solo livello Mask oltre alla dimensione del Regular, per un margine
    visibile attorno al bordo esterno (non solo nei vuoti interni del
    glifo) - il font stesso non lo fornisce per la maggior parte dei tasti
    (bounding box Regular/Mask quasi identici, vedi _FONT_INK_FRACTION).
    BUG REALE CORRETTO QUI (segnalato dall'utente: "i simboli sono belli ma
    non sono dove devono essere"): l'ancoraggio 'Center' di
    QgsFontMarkerSymbolLayer non coincide col centro dell'ink per questo
    font - vedi _FONT_OFFSET_FRACTION, applicato via setOffset() su ciascun
    livello in base alla propria dimensione effettiva (mask e regular hanno
    dimensioni diverse, quindi offset assoluti diversi anche se la frazione
    e' la stessa)."""
    _ensure_cadastra_symbol_font_loaded()
    layers = []
    mask_size = _font_effective_size(ch, sz * halo_scale, mask=True)
    mask_layer = QgsFontMarkerSymbolLayer.create({
        'font': CADASTRA_SYMBOL_MASK_FAMILY, 'chr': ch,
        'size': str(mask_size), 'size_unit': 'MM',
        'color': f"{mask_color.red()},{mask_color.green()},{mask_color.blue()},255",
        'horizontal_anchor_point': '1', 'vertical_anchor_point': '1'
    })
    mask_layer.setOffset(_font_marker_offset(ch, mask_size))
    layers.append(mask_layer)

    regular_size = _font_effective_size(ch, sz)
    regular_layer = QgsFontMarkerSymbolLayer.create({
        'font': CADASTRA_SYMBOL_FAMILY, 'chr': ch,
        'size': str(regular_size), 'size_unit': 'MM',
        'color': f"{c.red()},{c.green()},{c.blue()},255",
        'horizontal_anchor_point': '1', 'vertical_anchor_point': '1'
    })
    regular_layer.setOffset(_font_marker_offset(ch, regular_size))
    layers.append(regular_layer)
    return layers

def make_simple_marker(shape="circle", size=1.0, c=C_NERO, outline_w=0):
    """Crea un marcatore semplice. outline_w=0 (default, come finora) = nessun
    contorno: corretto per forme piene ("circle") dove il riempimento basta a
    renderle visibili. Le forme a solo tratto senza area interna (es. "cross",
    un +) vengono disegnate SOLO tramite il contorno: con outline_color
    trasparente (il default precedente, unico per tutte le forme) risultano
    completamente invisibili, non solo prive di bordo - verificato con un
    render isolato. Per queste va passato un outline_w > 0."""
    p = {
        'name': shape,
        'color': f"{c.red()},{c.green()},{c.blue()},255",
        'size': str(size), 'size_unit': 'MM'
    }
    if outline_w > 0:
        p['outline_color'] = f"{c.red()},{c.green()},{c.blue()},255"
        p['outline_width'] = str(outline_w)
        p['outline_width_unit'] = 'MM'
    else:
        p['outline_color'] = '0,0,0,0'
    return QgsSimpleMarkerSymbolLayer.create(p)

def build_sym(geom, layers):
    """Costruisce un QgsSymbol da una lista di SymbolLayer."""
    if geom == 'fill':
        s = QgsFillSymbol()
    elif geom == 'line':
        s = QgsLineSymbol()
    else:
        s = QgsMarkerSymbol()
    s.deleteSymbolLayer(0)
    for l in layers:
        s.appendSymbolLayer(l)
    return s

def apply_rule(root, sym, filt, label):
    """Aggiunge una regola al renderer rule-based.
    BUG CORRETTO QUI: un filtro vuoto ("") in QgsRuleBasedRenderer NON significa
    "regola di fallback/cattura cio' che resta" come assunto in ogni chiamata
    esistente con filt="" (etichettate "generico"/"invisibile") - significa
    "matcha SEMPRE, in aggiunta a qualunque altra regola gia' scattata".
    Verificato con un render reale (non solo isFilterOK/symbolsForFeature, che
    restano ottimisti per motivi di legenda): senza isElse, il simbolo di
    fallback veniva disegnato IN PIU' sopra OGNI feature gia' stilizzata da
    un'altra regola (es. un "Punto generico" sopra un glifo E/F/G/H/I gia'
    corretto), non solo sulle feature realmente non gestite. setIsElse() e' il
    meccanismo ufficiale QGIS per "matcha solo se nessun'altra regola gia'
    scattata": impostarlo automaticamente quando filt=="" corregge tutte le
    chiamate esistenti in un solo punto."""
    r = QgsRuleBasedRenderer.Rule(sym)
    r.setFilterExpression(filt)
    r.setLabel(label)
    if filt == "":
        r.setIsElse(True)
    root.appendChild(r)
    # Ritorna la regola: serve a chi deve poi limitarne l'intervallo di scala
    # (es. il colore dell'edificio nel PB-MU, diverso da 1:10000 in poi).
    return r

def load_qml_style(layer, qml_path, parent_log):
    """Carica uno stile da un file QML."""
    if qml_path.exists():
        parent_log(f"  🔍 Trovato QML: {qml_path.name}")
        res, msg = layer.loadNamedStyle(str(qml_path))
        if res:
            layer.triggerRepaint()
            parent_log(f"  ✅ Stile caricato da {qml_path.name}")
            return True
        else:
            parent_log(f"  ❌ Errore caricamento QML {qml_path.name}: {msg}", Qgis.Warning)
    else:
        parent_log(f"  ⚠️ QML non trovato: {qml_path}")
    return False

def apply_style_from_manager(layer, style_name, parent_log):
    """Cerca e applica uno stile dal Gestore Stili di QGIS."""
    try:
        parent_log(f"  🔍 Ricerca nel Gestore Stili: '{style_name}'")
        style = QgsStyle.defaultStyle()
        if style.findSymbol(style_name):
            parent_log(f"  ✅ Stile trovato nel Gestore Stili: '{style_name}'")
            symbol = style.symbol(style_name)
            if symbol:
                renderer = QgsSingleSymbolRenderer(symbol.clone())
                doc = QDomDocument("qgis")
                root = doc.createElement("qgis")
                root.setAttribute("version", "3.34.0")
                root.setAttribute("styleCategories", "Symbology")
                doc.appendChild(root)
                context = QgsReadWriteContext()
                elem = renderer.save(doc, context)
                root.appendChild(elem)
                with tempfile.NamedTemporaryFile(mode='w', suffix='.qml', delete=False) as tmp_file:
                    tmp_file.write(doc.toString(2))
                    tmp_path = tmp_file.name
                res = load_qml_style(layer, Path(tmp_path), parent_log)
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                return res
        else:
            parent_log(f"  ⚠️ Stile non trovato nel Gestore Stili: '{style_name}'")
    except Exception as e:
        parent_log(f"  ❌ Errore Gestore Stili: {str(e)}", Qgis.Warning)
    return False

# ==================================================================================================================
# 3. WORKER THREAD ASINCRONO
