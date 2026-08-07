# TIDashboard - dati della misurazione ufficiale svizzera in QGIS
# Copyright (C) 2026 Gabriele Peverelli
#
# Questo programma e' software libero: lo si puo' ridistribuire e modificare
# secondo i termini della GNU General Public License pubblicata dalla Free
# Software Foundation, versione 2 o (a scelta) una successiva. Il testo si
# trova nel file LICENSE distribuito insieme al programma.

# Colori ufficiali della rappresentazione, estratti da tidashboard.py.
#
# Valori esatti presi dalle istruzioni federali (Weisung-GB-it.pdf per il piano
# per il registro fondiario, Weisung-BP-AV-it.pdf per il piano di base): i
# commenti riportano il CMYK di origine, che e' la forma in cui la norma li
# definisce. Non vanno "aggiustati a occhio": ogni scostamento e' uno
# scostamento dalla norma.
from qgis.PyQt.QtGui import QColor


# ==================================================================================================================
# 1. COLORI UFFICIALI ESATTI (da Weisung-GB-it.pdf e Weisung-BP-AV-it.pdf)
# ==================================================================================================================

# === COLORI PIANO REGISTRO FONDIARIO (GB) ===
# Edifici
C_EDIFICIO = QColor(255, 191, 191)        # CMYK(0,25,25,0) - Rosa edificio
# Acque
C_ACQUA = QColor(179, 230, 255)           # CMYK(30,10,0,0) - Blu acqua
# Vegetazione
C_BOSCO = QColor(156, 255, 152)           # CMYK(39,0,39,0) - Verde bosco fitto
C_PASCOLO_BOSC = QColor(191, 255, 189)    # CMYK(25,0,45,0) - Verde pascolo boscato
C_FASCIA_BOSC = QColor(102, 255, 97)      # CMYK(60,0,69,0) - Verde fascia boscata
# Trame grigie
C_TRAMA_50 = QColor(130, 130, 130)        # CMYK(0,0,0,50) - Grigio 50% per trame
C_TRAMA_30 = QColor(178, 178, 178)        # CMYK(0,0,0,30) - Grigio 30% per edificio
C_TRAMA_10 = QColor(225, 225, 225)        # CMYK(0,0,0,11) - Grigio 10% per edificio sotterraneo
# Colori base
C_NERO = QColor(0, 0, 0)
C_BIANCO = QColor(255, 255, 255)
# Trame speciali (colori esatti da specifiche)
C_VIGNA_TRAMA = QColor(51, 168, 0)        # CMYK(80,34,100,0) - Verde vigna
C_TORB_TRAMA = QColor(77, 102, 255)       # CMYK(70,60,0,0) - Blu torbiera
C_CANN_TRAMA = QColor(77, 102, 255)       # CMYK(70,60,0,0) - Blu canneto
C_GHIACCIAIO = QColor(6, 72, 177)         # CMYK(98,72,31,0) - Blu ghiacciaio
C_GIARDINO = QColor(77, 153, 0)           # CMYK(70,40,100,0) - Verde giardino
# Spostamento di terreno
C_SPOSTAMENTO = QColor(255, 182, 25)      # CMYK(0,29,90,0) - Giallo/arancio

# === COLORI PIANO DI BASE (PB-MU) ===
# Contorno dell'edificio nel PB-MU. Valore preso dal Weisung-BP-AV §2.3.2:
# "Contorno rosa (34,78,100,0)", che convertito da' (168,56,0). Prima era
# (161,51,0), scelto senza il CMYK di riferimento.
C_BP_EDIFICIO_CONTORNO = QColor(168, 56, 0)      # CMYK(34,78,100,0) - contorno edificio (PB-MU)

# Il PB-MU cambia colore all'edificio alla scala 1:10000: riempimento E
# contorno diventano un rosa acceso (Weisung-BP-AV §2.3.2), mentre a 1:2500 e
# 1:5000 valgono C_EDIFICIO + C_BP_EDIFICIO_CONTORNO.
C_BP_EDIFICIO_10000 = QColor(240, 71, 135)       # CMYK(6,72,47,0) - edificio a 1:10000
C_BP_ACQUA_BORDO = QColor(77, 102, 255)          # Blu scuro acque (PB-MU)
C_BP_CONFINE = QColor(181, 0, 0)                 # Rosso confini giurisdizionali (PB-MU)

# Curve di livello nel PB-MU (Weisung-BP-AV §2.2.10). Prima si usava un
# (153,102,51) senza riscontro nella norma.
C_BP_CURVA_LIVELLO = QColor(140, 69, 0)          # CMYK(45,73,100,0)
