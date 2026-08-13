# TIDashboard - dati della misurazione ufficiale svizzera in QGIS
# Copyright (C) 2026 Gabriele Peverelli
#
# Questo programma e' software libero: lo si puo' ridistribuire e modificare
# secondo i termini della GNU General Public License pubblicata dalla Free
# Software Foundation, versione 2 o (a scelta) una successiva. Il testo si
# trova nel file LICENSE distribuito insieme al programma.

# Cosa c'e' dentro un ITF, prima di importarlo.
#
# Per sapere cosa contiene una consegna finora bisognava importarla: su un file
# di produzione sono minuti, e l'importazione puo' fermarsi a meta' lasciando un
# GeoPackage vuoto - proprio quando avresti piu' bisogno di sapere cosa c'era
# dentro. GDAL ha il driver "Interlis 1" compilato dentro QGIS e legge l'ITF
# direttamente: sul comune di prova, 733 527 oggetti in 128 classi contati in
# 2.5 secondi.
#
# LIMITE, misurato: senza il modello COMPILATO (.imd, che si genera con ili2c)
# il driver da' nomi di campo di ripiego (Field01, Field02...) e non riconosce
# le geometrie. Per il conteggio non serve - i nomi delle CLASSI ci sono - ma
# non si provi a leggere gli attributi da qui.

import os

# Le classi che il plugin si aspetta di trovare in una consegna della
# misurazione ufficiale: se una manca del tutto, il piano che ne esce sara'
# incompleto e vale la pena dirlo subito invece che a importazione finita.
# I nomi sono quelli che il driver espone: "Topic__Classe".
CLASSI_ATTESE = (
    ("Beni_immobili__Fondo", "fondi"),
    ("Beni_immobili__Bene_immobile_Geometria", "geometrie dei beni immobili"),
    ("Beni_immobili__Punto_di_confine", "punti di confine"),
    ("Copertura_del_suolo__SuperficieCS", "superfici di copertura del suolo"),
)


def leggi_inventario(percorso):
    """(classi, totale) di un ITF: 'classi' e' una lista (nome, quanti)
    ordinata per numero decrescente, senza le classi vuote.

    Solleva RuntimeError se il file non si apre: il chiamante decide se
    e' un problema o solo un file non ancora scelto."""
    if not percorso or not os.path.isfile(percorso):
        raise RuntimeError("file non trovato")
    try:
        from osgeo import gdal
    except ImportError:
        raise RuntimeError("binding GDAL (osgeo) non disponibili")
    # Il driver segnala con un warning ogni classe senza definizione di
    # modello: su questo file sono decine di righe che non aggiungono nulla
    # a un conteggio, e finirebbero nel log dell'utente.
    gdal.PushErrorHandler("CPLQuietErrorHandler")
    try:
        ds = gdal.OpenEx(percorso, gdal.OF_VECTOR)
    finally:
        gdal.PopErrorHandler()
    if ds is None:
        raise RuntimeError("non riconosciuto come INTERLIS 1")
    classi = []
    for i in range(ds.GetLayerCount()):
        lay = ds.GetLayer(i)
        quanti = lay.GetFeatureCount()
        if quanti:
            classi.append((lay.GetName(), quanti))
    classi.sort(key=lambda c: (-c[1], c[0]))
    return classi, sum(q for _n, q in classi)


def mancanti(classi):
    """Le classi attese che nel file non ci sono (o sono vuote), con la loro
    descrizione in chiaro."""
    presenti = {nome for nome, _q in classi}
    return [descrizione for nome, descrizione in CLASSI_ATTESE
            if nome not in presenti]


def riassunto(classi, totale, quante_in_testa=3):
    """Una riga sola per l'interfaccia: quanto c'e' e cosa pesa di piu'."""
    if not classi:
        return "il file non contiene oggetti"
    testa = ", ".join("%s %s" % ("{:,}".format(q).replace(",", "'"),
                                 nome.split("__")[-1])
                      for nome, q in classi[:quante_in_testa])
    return ("%s oggetti in %d classi — %s"
            % ("{:,}".format(totale).replace(",", "'"), len(classi), testa))
