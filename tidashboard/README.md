# TIDashboard

Plugin QGIS per i dati della misurazione ufficiale svizzera, modello ticinese
**MD01MUTI7MN95**.

> **Sperimentale.** La conformità alla norma è stata verificata sul testo delle
> istruzioni federali e per misurazione, **non** con un confronto affiancato a un
> estratto ufficiale né con una validazione dell'autorità competente. Le
> planimetrie prodotte riportano la dicitura «Riproduzione senza valore legale».

## Cosa fa

1. **Importa** un file ITF in GeoPackage (via ili2gpkg) e applica la simbologia
   normativa a ~150 layer.
2. **Converte** in DXF (via av2geobau, versione adattata al modello ticinese).
3. **Genera planimetrie** stampabili alle otto scale ufficiali (1:200 … 1:10000),
   con rotazione del foglio in gon, reticolo di coordinate e cartiglio con le
   sette iscrizioni obbligatorie.

Due prodotti: **piano per il registro fondiario** (bianco e nero) e **piano di
base della misurazione ufficiale** (a colori).

## Cosa serve

- **QGIS 4.0** o superiore
- **Java 8** o superiore, installato separatamente — il plugin lo cerca da solo
  in PATH, `JAVA_HOME` e nelle cartelle dei principali fornitori
- **Windows** — è l'unico sistema su cui è stato provato
- Il file **ili2gpkg.jar**, da indicare nella prima scheda

Il modello INTERLIS e il traduttore DXF sono in dotazione e non si scelgono.

## Installazione

Estensioni → Gestisci ed installa estensioni → Installa da ZIP → `tidashboard_1.1.1.zip`.

Poiché è marcato sperimentale, va prima attivata l'opzione *Mostra anche le
estensioni sperimentali* nelle impostazioni del gestore.

## Uso

Le tre schede seguono l'ordine del lavoro. Un segno di spunta sul titolo indica
quelle già completate.

1. **Importazione** — indica ili2gpkg, il file ITF e dove salvare il GeoPackage.
   Il pulsante resta spento finché i percorsi non sono validi.
2. **Conversione DXF** — usa lo stesso ITF dell'importazione.
3. **Planimetria** — formato, scala, rotazione. Comune e data sono letti dai dati.
   La spunta «Mostra sulla mappa l'ingombro del foglio» disegna sul canvas il
   rettangolo che finirà sul foglio.

## Limiti noti

- Provato solo su Windows.
- Il fattore di proporzionalità (cap. 1.5.2) è applicato per intero agli
  ingrandimenti; alle riduzioni si ferma dove la scrittura più piccola
  scenderebbe sotto 1,2 mm. Il limite morde su **4 delle 8 scale ufficiali**
  del piano per il registro fondiario e su una del piano di base:

  | scala | RF: norma → applicato | PB-MU: norma → applicato |
  |---|---|---|
  | 1:2000 | ×0,50 → **×0,80** | ×2,50 → ×2,50 |
  | 1:2500 | ×0,40 → **×0,80** | ×2,00 → ×2,00 |
  | 1:5000 | ×0,20 → **×0,80** | ×1,00 → ×1,00 |
  | 1:10000 | ×0,10 → **×0,80** | ×0,50 → **×0,80** |

  Dove lo scostamento c'è, viene **scritto nel cartiglio** accanto alla scala e
  segnalato nella scheda Planimetria: non è una deviazione silenziosa. La
  spunta *Fattore alla lettera della norma* toglie il limite e dà la
  proporzione esatta, al prezzo che a 1:10000 la scrittura più piccola scende a
  0,15 mm e non si stampa.
- Nel piano di base gli Oggetti singoli usano uno spessore uniforme invece dei
  valori per singolo oggetto del Weisung §2.2.5 (differenze di 0,05 mm).
- Le date di aggiornamento provengono dal timestamp del file ITF, che non è un
  dato contenuto nel file.

## Licenza

**GPL-2.0-or-later** — vedi [LICENSE](LICENSE). È la convenzione dei plugin
QGIS (QGIS stesso è GPLv2+) ed è compatibile con i componenti LGPL 2.1
distribuiti insieme, elencati in `CREDITI.md`.

## Terze parti

Vedi [CREDITI.md](CREDITI.md).
