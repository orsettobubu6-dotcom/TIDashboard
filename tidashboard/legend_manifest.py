# TIDashboard - dati della misurazione ufficiale svizzera in QGIS
# Copyright (C) 2026 Gabriele Peverelli
#
# Questo programma e' software libero: lo si puo' ridistribuire e modificare
# secondo i termini della GNU General Public License pubblicata dalla Free
# Software Foundation, versione 2 o (a scelta) una successiva. Il testo si
# trova nel file LICENSE distribuito insieme al programma.

# Ponte QGIS -> DXF per la legenda: estrae le regole visibili dal renderer di
# ogni layer stilizzato (renderer.legendSymbolItems(), lo stesso metodo che
# QGIS usa per popolare il pannello Legenda - ispirato al pattern trovato in
# MappiaEarth/mappia_publisher, DirectoryWriter.writeLegendJson) e le scrive
# in un manifest testuale che il generatore DXF Java (Av2geobau.java,
# appendLegendBlock) legge per disegnare una legenda nel piano esportato.
# Formato pipe-delimited (nessuna libreria JSON ne' lato Python ne' lato
# Java): "nome_layer|etichetta_regola|r|g|b" per riga.
#
# Il colore scritto e' quello REALE del simbolo QGIS (symbol.color()) - un
# riquadro colorato come riferimento rapido nella legenda DXF, non una copia
# esatta del marker/hatch (troppo complesso da riprodurre 1:1 in un blocco
# DXF senza duplicare in Java tutta la logica di stile per ogni simbolo).
#
# "Ponte", non magia: si aggiorna in automatico rispetto allo stile QGIS
# (rilegge sempre il renderer live), ma NON rispetto al generatore DXF - i
# due programmi restano separati. Il flusso e': ristilizza il progetto
# (rigenera questo manifest) -> rilancia l'export DXF (legge il manifest piu'
# recente). Se il manifest manca, appendLegendBlock non disegna nulla
# (feature opzionale, non blocca l'export).

def write_legend_manifest(zorder_layers, out_path):
    """zorder_layers: lista di (layer, t_low) come costruita in
    load_and_style_layers. Scrive out_path (un file di testo) con una riga
    per voce di legenda; ritorna il numero di righe scritte."""
    lines = []
    for layer, _t_low in zorder_layers:
        renderer = layer.renderer()
        if renderer is None:
            continue
        table_label = layer.name().replace("|", "/").replace("\n", " ").strip()
        for legend_node in renderer.legendSymbolItems():
            symbol = legend_node.symbol()
            if symbol is None:
                continue  # niente colore proprio (es. intestazioni di gruppo)
            label = (legend_node.label() or "").replace("|", "/").replace("\n", " ").strip()
            if not label:
                continue
            # symbol.color() ritorna il colore del PRIMO symbol layer (indice
            # 0) - per i marker "con maschera" (make_true_font_marker_with_mask)
            # quello e' il livello mask BIANCO sottostante, non il glifo vero
            # (secondo livello, sopra): verificato a runtime, dava sempre
            # (255,255,255) per Punto_di_confine/PFP/PFA/PCGiurisdizionale.
            # L'ULTIMO symbol layer e' quello disegnato sopra a tutti gli
            # altri (il colore effettivamente visibile), quindi e' quello
            # giusto da usare come colore rappresentativo della voce.
            if symbol.symbolLayerCount() > 0:
                color = symbol.symbolLayer(symbol.symbolLayerCount() - 1).color()
            else:
                color = symbol.color()
            lines.append(f"{table_label}|{label}|{color.red()}|{color.green()}|{color.blue()}")

    # ISO-8859-1, NON utf-8: il lettore Java (Av2geobau.readAllLinesIso) apre il
    # manifest in ISO-8859-1, come tutto il resto del DXF. Scriverlo in utf-8
    # produceva mojibake su ogni carattere accentato ("Località" -> "LocalitÃ ")
    # - bug reale riprodotto sul file generato. errors="replace" per i rari
    # caratteri fuori latin-1 (il DXF stesso non potrebbe comunque scriverli).
    with open(out_path, "w", encoding="ISO-8859-1", errors="replace") as f:
        f.write("\n".join(lines))
    return len(lines)
