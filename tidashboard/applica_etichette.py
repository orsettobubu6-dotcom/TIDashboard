# TIDashboard - dati della misurazione ufficiale svizzera in QGIS
# Copyright (C) 2026 Gabriele Peverelli
#
# Questo programma e' software libero: lo si puo' ridistribuire e modificare
# secondo i termini della GNU General Public License pubblicata dalla Free
# Software Foundation, versione 2 o (a scelta) una successiva. Il testo si
# trova nel file LICENSE distribuito insieme al programma.

# Le etichette APPLICATE ai layer di QGIS.
#
# DUE MODULI E NON UNO, e la divisione conta. etichette.py tiene le REGOLE -
# TEXT_LABEL_RULES, i nomi dei campi candidati, le parole chiave delle tabelle
# Pos*, le altezze del cap. 5.7 - e non importa QGIS: quelle regole vengono
# dalla norma, si leggono senza un programma di cartografia e si provano senza
# costruire un layer. Qui c'e' l'altra meta': prendere quelle regole e
# costruirci sopra un QgsPalLayerSettings.
#
# Mettere tutto insieme avrebbe fatto perdere a etichette.py l'unica cosa che
# lo rende interessante, cioe' essere leggibile e provabile da solo.
#
# PERCHE' NON DENTRO LA FINESTRA, dove stavano. Questi quattro pezzi non
# toccavano un solo widget: l'unico legame con la classe erano le chiamate a
# self.log e una lettura di spunta. Il registro entra come parametro con un
# valore di riposo che non fa nulla, e la spunta entra come booleano - cosi'
# le regole del cap. 5.7 si provano senza aprire una finestra, che era il
# motivo per cui non erano mai state provate direttamente.
#
# IL PROGETTO ENTRA ANCH'ESSO come parametro. Una riga sola ne aveva bisogno -
# spegnere il nodo dell'albero per i layer che nascono invisibili - e prendeva
# QgsProject.instance(), cioe' il progetto aperto, che in una prova non e'
# quello che si vuole toccare.
from qgis.core import (
    Qgis,
    QgsPalLayerSettings,
    QgsProject,
    QgsProperty,
    QgsTextFormat,
    QgsUnitTypes,
    QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtGui import QColor, QFont

try:
    from .etichette import (
        _LABEL_DISABLED_BY_DEFAULT,
        _LABEL_LAYER_OFF_BY_DEFAULT,
        _LABEL_PRIORITY,
        _LABEL_PRIORITY_DEFAULT,
        _POS_LEFT_BOTTOM_KEYWORDS,
        _POS_STILE_KEYWORDS,
        KEYWORD_LOCALITA,
        TESTO_SOLO_SU_POS,
        TEXT_LABEL_RULES,
        e_tabella_pos,
        iscrizione_localita,
    )
    from .simbologia import (
        CADASTRA_TEXT_FAMILY,
        _ensure_cadastra_text_font_loaded,
        _font_size_for_cap,
        gbc,
    )
except ImportError:                     # eseguito fuori dal pacchetto
    from etichette import (
        _LABEL_DISABLED_BY_DEFAULT,
        _LABEL_LAYER_OFF_BY_DEFAULT,
        _LABEL_PRIORITY,
        _LABEL_PRIORITY_DEFAULT,
        _POS_LEFT_BOTTOM_KEYWORDS,
        _POS_STILE_KEYWORDS,
        KEYWORD_LOCALITA,
        TESTO_SOLO_SU_POS,
        TEXT_LABEL_RULES,
        e_tabella_pos,
        iscrizione_localita,
    )
    from simbologia import (
        CADASTRA_TEXT_FAMILY,
        _ensure_cadastra_text_font_loaded,
        _font_size_for_cap,
        gbc,
    )


def _zitto(_testo, _livello=None):
    """Il registro quando nessuno lo passa. Serve a poter chiamare queste
    funzioni da una prova senza costruire una finestra."""


def campo_di_etichetta(layer, candidati):
    """Il primo campo fra i candidati presente sul layer, o None.

    Le tabelle "PosX" del modello non contengono quasi mai il testo: vive
    sulla tabella padre "X" e diventa un campo del layer solo dopo il join,
    rinominato "{tabella_padre}_{campo}". Si cerca quindi anche un campo che
    FINISCA per "_<candidato>"."""
    presenti = {f.name().lower(): f.name() for f in layer.fields()}
    for c in candidati:
        if c.lower() in presenti:
            return presenti[c.lower()]
    for c in candidati:
        coda = ("_" + c).lower()
        for minuscolo, originale in presenti.items():
            if minuscolo.endswith(coda):
                return originale
    return None


def rilega_campo_nelle_regole(regola, vecchio, nuovo):
    """Sostituisce, in tutto l'albero di regole, ogni riferimento a 'vecchio'
    nell'espressione di filtro con 'nuovo'. Ritorna quante sostituzioni.

    Serve ai renderer costruiti su un campo (es. "Genere") che esiste solo
    sulla tabella padre e compare sul layer solo dopo il join."""
    quante = 0
    rif_vecchio, rif_nuovo = '"%s"' % vecchio, '"%s"' % nuovo
    if vecchio != nuovo:
        espressione = regola.filterExpression()
        if rif_vecchio in espressione:
            regola.setFilterExpression(espressione.replace(rif_vecchio, rif_nuovo))
            quante += 1
    for figlio in regola.children():
        quante += rilega_campo_nelle_regole(figlio, vecchio, nuovo)
    return quante


def applica_attributi_pos(layer, impostazioni, chiave, dimensione_base):
    """Collega Ori/HAli/VAli/Dimensione/Stile (tabelle Pos* di
    MD01MUTI7MN95.ili) alle proprieta' data-defined di QGIS, applicando come
    valore di riposo esplicito il "non_definito" che il modello dichiara per
    quell'attributo quando manca nei dati, invece di lasciare un valore
    implicito di QGIS.

    - Ori: azimut in GON orario da Nord (0=Nord, 100=Est, coerente con
      "E_Azimut ... Azimut 100 = E" del modello). QGIS vuole gradi orari da
      Est (0=Est): gradi_qgis = (Ori_gon - 100) * 0.9 - segno opposto alla
      stessa formula usata per il DXF in av2geobau_ti/Mapper.java, che
      converte lo stesso Ori in gradi ANTIorari da Est.
    - HAli/VAli: le proprieta' data-defined accettano LETTERALMENTE gli stessi
      valori del dominio ILI (Left/Center/Right, Bottom/Base/Half/Cap/Top) -
      nessuna conversione, solo il valore di riposo giusto per tabella.
    - Dimensione (piccolo/medio/grande): il plugin ha gia' una dimensione
      fissa in mm per ogni voce di TEXT_LABEL_RULES, che e' il caso "medio".
      Il +-25% per piccolo/grande e' un'approssimazione: il valore esatto non
      e' specificato ne' nel modello ne' in av2geobau, che Dimensione non la
      mappa affatto.
    - Stile "spaziato": spaziatura fra le lettere allargata, concetto assente
      in DXF; ampiezza approssimata in proporzione al corpo.

    Tutte queste proprieta' hanno senso solo col posizionamento SOPRA AL
    PUNTO, non con la ricerca automatica anti-sovrapposizione che QGIS usa per
    difetto: si imposta quindi sempre OverPoint, come il posizionamento fisso
    di un TEXT del DXF."""
    campi = layer.fields()
    applicati = []
    sinistra_basso = chiave in _POS_LEFT_BOTTOM_KEYWORDS
    hali = "Left" if sinistra_basso else "Center"
    vali = "Bottom" if sinistra_basso else "Half"
    dd = impostazioni.dataDefinedProperties()

    if campi.lookupField("ori") >= 0:
        dd.setProperty(QgsPalLayerSettings.Property.LabelRotation,
                       QgsProperty.fromExpression(
                           '(coalesce("ori", 100) - 100) * 0.9'))
        applicati.append("Ori")
    if campi.lookupField("hali") >= 0:
        dd.setProperty(QgsPalLayerSettings.Property.Hali,
                       QgsProperty.fromExpression(
                           "coalesce(\"hali\", '%s')" % hali))
        applicati.append("HAli")
    if campi.lookupField("vali") >= 0:
        dd.setProperty(QgsPalLayerSettings.Property.Vali,
                       QgsProperty.fromExpression(
                           "coalesce(\"vali\", '%s')" % vali))
        applicati.append("VAli")
    if not sinistra_basso and campi.lookupField("dimensione") >= 0:
        dd.setProperty(QgsPalLayerSettings.Property.Size,
                       QgsProperty.fromExpression(
                           'CASE "dimensione" '
                           "WHEN 'piccolo' THEN %s "
                           "WHEN 'grande' THEN %s "
                           'ELSE %s END'
                           % (dimensione_base * 0.8, dimensione_base * 1.25,
                              dimensione_base)))
        applicati.append("Dimensione")
    if chiave in _POS_STILE_KEYWORDS and campi.lookupField("stile") >= 0:
        dd.setProperty(QgsPalLayerSettings.Property.FontLetterSpacing,
                       QgsProperty.fromExpression(
                           "CASE WHEN \"stile\" = 'spaziato' THEN %s ELSE 0 END"
                           % (dimensione_base * 0.3)))
        applicati.append("Stile")

    # PRIORITA' E OSTACOLI. Il motore di etichettatura sa gia' nascondere una
    # scritta che non ci sta; quello che non sa, senza che glielo si dica, e'
    # QUALE delle due deve cedere - senza priorita' tratta tutti i layer alla
    # pari e decide con l'ordine di disegno. La scala sta in _LABEL_PRIORITY
    # ed e' la stessa dell'esportazione DXF (AntiCollisioneEtichette.java),
    # cosi' anteprima e disegno consegnato non si contraddicono.
    impostazioni.priority = _LABEL_PRIORITY.get(chiave, _LABEL_PRIORITY_DEFAULT)
    # La scritta e' anche ostacolo per le altre, con peso pari alla sua
    # priorita': un numero di fondo non va coperto da un numero di punto.
    ostacoli = impostazioni.obstacleSettings()
    ostacoli.setIsObstacle(True)
    ostacoli.setFactor(0.5 + 0.1 * impostazioni.priority)
    impostazioni.setObstacleSettings(ostacoli)

    if applicati:
        impostazioni.placement = Qgis.LabelPlacement.OverPoint
    return applicati


def applica_etichette(layer, t_low, nome_classe, e_gb=False, maiuscolo=False,
                      log=None, progetto=None):
    """Applica le etichette a un layer testuale (cap. 5 Weisung-GB-it).

    'maiuscolo' e' la scelta dell'utente per i nomi di localita' (cap. 5.7);
    'log' riceve (testo, livello) e per difetto non fa nulla; 'progetto' serve
    solo a spegnere il nodo dell'albero dei layer che nascono invisibili."""
    log = log or _zitto
    progetto = progetto if progetto is not None else QgsProject.instance()
    _ensure_cadastra_text_font_loaded()

    # Punto quotato: la quota e' la componente Z della geometria (CoordA), non
    # un attributo separato -> etichetta su espressione $z.
    if "punto_quotato" in t_low:
        impostazioni = QgsPalLayerSettings()
        impostazioni.fieldName = "round($z, 2)"
        impostazioni.isExpression = True
        formato = QgsTextFormat()
        formato.setColor(gbc(e_gb, QColor(102, 51, 0)))
        formato.setFont(QFont(CADASTRA_TEXT_FAMILY))
        # Estensione cantonale senza grandezza federale: allineata a 1.8 mm
        # come le altre etichette-numero.
        formato.setSize(_font_size_for_cap(1.8))
        formato.setSizeUnit(QgsUnitTypes.RenderMillimeters)
        impostazioni.setFormat(formato)
        impostazioni.enabled = True
        applicati = applica_attributi_pos(layer, impostazioni, "punto_quotato", 1.8)
        layer.setLabeling(QgsVectorLayerSimpleLabeling(impostazioni))
        layer.setLabelsEnabled(True)
        nota = " (%s da Pos*)" % "+".join(applicati) if applicati else ""
        log("     ✅ Etichetta Punto_quotato su $z%s" % nota)
        return True

    for chiave, candidati, grassetto, corsivo, dimensione in TEXT_LABEL_RULES:
        if chiave not in t_low:
            continue

        # LA SCRITTA VA SUL PUNTO DI ISCRIZIONE, non sull'oggetto che nomina:
        # vedi TESTO_SOLO_SU_POS. Senza questo controllo il nome finiva sul
        # foglio due volte - 658 iscrizioni di troppo sul solo comune di
        # prova, a mediana 40-50 mm di carta l'una dall'altra.
        if chiave in TESTO_SOLO_SU_POS and not e_tabella_pos(t_low):
            log("     ⏭️ %s: l'iscrizione sta sulla tabella Pos*, qui sarebbe "
                "la seconda copia dello stesso nome" % nome_classe)
            return False

        campo = campo_di_etichetta(layer, candidati)
        if not campo:
            log("     ⚠️ Nessun campo tra %s trovato per '%s' (join mancante o "
                "non riuscito?)" % (candidati, chiave), Qgis.Warning)
            return False

        impostazioni = QgsPalLayerSettings()
        # PosNome_localizzazione: Indice_iniziale/Indice_finale delimitano una
        # sottostringa di Testo da mostrare (per difetto 1..ultimo carattere,
        # cioe' tutto), secondo MD01MUTI7MN95.ili.
        if chiave == "posnome_localizzazione" \
                and layer.fields().lookupField("indice_iniziale") >= 0:
            impostazioni.fieldName = (
                'substr("%s", coalesce("indice_iniziale", 1), '
                'coalesce("indice_finale", length("%s")) - '
                'coalesce("indice_iniziale", 1) + 1)' % (campo, campo))
            impostazioni.isExpression = True
        elif chiave == KEYWORD_LOCALITA:
            impostazioni.fieldName, impostazioni.isExpression = \
                iscrizione_localita(campo, maiuscolo)
        else:
            impostazioni.fieldName = campo

        formato = QgsTextFormat()
        carattere = QFont(CADASTRA_TEXT_FAMILY)
        carattere.setBold(grassetto)
        carattere.setItalic(corsivo)
        formato.setFont(carattere)
        # 'dimensione' e' l'altezza della MAIUSCOLA in mm richiesta dalla
        # norma: va convertita nel corpo del carattere e resa in millimetri di
        # stampa (a 1:1000 coincide col valore normativo). In punti
        # tipografici il rapporto fra le classi di scrittura non sarebbe
        # quello prescritto.
        formato.setSize(_font_size_for_cap(dimensione))
        formato.setSizeUnit(QgsUnitTypes.RenderMillimeters)
        impostazioni.setFormat(formato)
        impostazioni.enabled = True
        applicati = applica_attributi_pos(layer, impostazioni, chiave, dimensione)
        layer.setLabeling(QgsVectorLayerSimpleLabeling(impostazioni))
        spenta = any(k in t_low for k in _LABEL_DISABLED_BY_DEFAULT)
        layer.setLabelsEnabled(not spenta)

        stile = "grassetto" if grassetto else ("corsivo" if corsivo else "normale")
        nota = " + %s da Pos*" % "+".join(applicati) if applicati else ""
        coda = " (etichetta creata ma spenta di default)" if spenta else ""
        log("     ✅ Etichetta '%s' su campo '%s' (Cadastra %s %smm%s)%s"
            % (chiave, campo, stile, dimensione, nota, coda))

        if any(k in t_low for k in _LABEL_LAYER_OFF_BY_DEFAULT):
            nodo = progetto.layerTreeRoot().findLayer(layer.id())
            if nodo:
                nodo.setItemVisibilityChecked(False)
                log("     ✅ Layer spento di default (etichetta pronta, da "
                    "riaccendere manualmente)")
            else:
                log("     ⚠️ Nodo albero non trovato per %s: layer resta acceso"
                    % layer.name(), Qgis.Warning)
        return True

    log("     ⚠️ Nessuna regola di etichettatura corrispondente")
    return False
