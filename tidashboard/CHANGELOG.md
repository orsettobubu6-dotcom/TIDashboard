# Diario delle versioni

## 1.2.1 — 21 agosto 2026 — sperimentale

### Il pacchetto pubblicato si può verificare davvero

L'archivio era già costruito per essere riproducibile — date e permessi delle
voci fissati apposta — ma il controllo, fatto per la prima volta sulla Release
1.2.0, **non tornava**: l'impronta pubblicata dalla CI (`27d92656…`) e quella
di una ricostruzione su Windows (`6c594f1c…`) erano diverse.

I due archivi differivano su 15 file, tutti più grandi in locale di esattamente
un byte per riga — `LICENSE` +339 byte su 339 righe: contenuto identico, fine
riga diversi. Con `core.autocrlf=true` Windows scrive CRLF in copia di lavoro e
il runner Linux scrive LF. La compressione, invece, è deterministica.

Ora un `.gitattributes` dichiara `eol=lf` per tutto il testo e marca
esplicitamente i binari: ogni checkout, su qualunque sistema, produce gli
stessi byte. **Da questa versione l'impronta accanto alla Release è
verificabile ricostruendo dallo stesso tag**; quella della 1.2.0 non lo era, e
il README lo dice.

### Il limite del fattore di proporzionalità (cap. 1.5.2)

Il limite inferiore applicato alle scale ridotte si ricavava dalla scrittura
più piccola del cap. 5, che la costante dichiarava di 1.5 mm citando il numero
di edificio: è la stessa lettura errata del cap. 5.5 corretta nella 1.2.0, dove
la tabella prescrive **1.8**. Il limite valeva quindi 1.2/1.5 = 0.80 invece di
1.2/1.8 = **0.67**.

Sulle quattro scale ridotte si disegnava il 20% più grande di quanto la ragione
stessa del limite richiedesse — cioè ci si allontanava dalla proporzione del
cap. 1.5.2 più del necessario. A 1:5000 il numero di fondo passa da 2.00 a
1.67 mm, la linea di confine da 0.32 a 0.27.

### Il contenuto del piano (cap. 1.5.3) è ora verificato

Tre test chiedono al plugin, tema per tema, che cosa finisce sul foglio: i
quattro esclusi dal capitolo (Altezza, Aree di numerazione, Ripartizione del
piano, TSRipartizione), i dodici elencati fra i rappresentati, e gli oggetti in
progetto, che il cartiglio dichiara non rappresentati.

Il secondo è l'altra metà del controllo: un'esclusione troppo larga
toglierebbe dal piano un tema prescritto, e guardando solo la lista degli
esclusi non se ne accorgerebbe nessuno.

## 1.2.0 — 19 agosto 2026 — sperimentale

### Dati ufficiali scaricabili dal plugin

- Nuova voce «⬇️ Cantone...» accanto al campo dell'ITF: sceglie il comune da
  **data.geo.ti.ch** e scarica l'archivio ufficiale, lo estrae e compila da solo
  il percorso. L'elenco dei 130 comuni (e comunanze) arriva dal portale a ogni
  apertura, con la data di aggiornamento di ciascuno: è quella l'informazione
  che serve per decidere se riscaricare.
- **L'impronta si verifica.** Ogni archivio porta l'MD5 calcolato dal Cantone;
  dopo l'estrazione viene ricalcolato e confrontato. Un ITF troncato da una
  connessione caduta è altrimenti indistinguibile da uno buono finché ili2gpkg
  non fallisce a metà, parlando d'altro.
### I simboli uscivano al 75% della misura prescritta

Confronto dei capitoli 2 e 5 dell'istruzione contro il font CADASTRA in
dotazione, glifo per glifo. Ne sono usciti due difetti veri.

**I simboli per i punti erano tutti troppo piccoli di un quarto.** La tabella
che converte la grandezza voluta nella dimensione del font era stata misurata
con `QFontMetricsF` «a corpo 1000 pt», ma Qt disegna i punti a 96 dpi contro i
72 della definizione tipografica: quell'em misurava 1333 pixel e non 1000, e
ogni frazione risultava 4/3 troppo grande. Siccome la dimensione effettiva si
ottiene *dividendo* per la frazione, ogni simbolo usciva al 75%.

Misurato disegnando i simboli a 600 dpi e contando l'inchiostro: da −19.6% a
−25.9% su 24 tasti, mentre un cerchio di dimensione dichiarata usciva giusto
allo 0.5%. Dopo la correzione lo scarto massimo è +2.8%. I valori ora si
leggono dal file del font (bounding box diviso unitsPerEm) invece che a
schermo. Il percorso SVG, usato per le trame di vigna, canneto e torbiera, non
aveva il difetto: là la misura non passa dai punti tipografici.

**Due grandezze di scrittura erano sbagliate** (cap. 5.5 e 5.6): il numero di
edificio stava a 1.5 mm invece di 1.8 — 7 672 iscrizioni sul solo comune di
Mendrisio — e il nome degli oggetti singoli a 2.2 invece di 2.5. Il 2.2
appartiene al cap. 5.9, `elemento_condotta`: le due tabelle stanno sulla stessa
pagina e in una trascrizione a colonne il valore era migrato da una all'altra.

Entrambi i difetti sono ora presidiati da test che **disegnano** il simbolo e
lo misurano, invece di confrontare una costante con un'altra costante: la
tabella sbagliata era perfettamente coerente con se stessa.

### Il modello dei dati, controllato a ogni passo

Il modello sbagliato entra da ogni porta — un ITF ricevuto per posta, un
GeoPackage importato mesi fa da qualcun altro, un secondo ITF scelto a mano per
la sola conversione DXF — e un controllo che sta in una porta sola non è un
controllo. Ora la definizione sta in `modello.py` e la chiamano tutti i passi:

- **scelta del file**: la spia accanto al campo diventa rossa e il pulsante si
  spegne, con il motivo nel tooltip. Prima lo si scopriva dopo minuti di
  `ili2gpkg`, con un errore che parlava di classi mancanti invece che di
  modello sbagliato;
- **inventario**: il modello è scritto sotto il campo, sempre — anche quando è
  quello giusto. È la premessa di tutto il resto;
- **importazione** e **conversione DXF**: riletto un istante prima di avviare
  Java, perché il file può essere cambiato da quando lo si è scelto;
- **caricamento del GeoPackage**: letto da `T_ILI2DB_MODEL`, dove `ili2gpkg` lo
  registra. Qui avvisa e prosegue, invece di bloccare: caricare i layer è
  proprio l'operazione che permette di guardare cosa è arrivato.

Un modello **diverso** ferma il lavoro; un modello **non dichiarato**
(intestazione insolita) si limita ad avvisare: il primo è un fatto letto nel
file, il secondo un'incertezza nostra, e bloccare su un dubbio toglierebbe
all'utente una decisione che è sua. Quando il modello trovato è quello federale
di geodienste.ch il messaggio lo dice, e indica il pulsante da cui scaricare
l'equivalente cantonale.

### Il DXF viene riletto da GDAL prima di dirlo fatto

Il controllo strutturale che c'era legge il file con il nostro stesso codice:
se sbagliamo a scrivere e sbagliamo allo stesso modo a rileggere, passa. Ora
dopo la conversione il DXF viene riletto da **GDAL**, che è già dentro QGIS ed
è un'implementazione completamente diversa. L'invariante: ogni entità scritta
deve tornare una feature, sullo stesso layer.

Misurato sul DXF di Mendrisio (209 MB): **468 622 scritte, 468 622 rilette,
scarto zero** su tutti e 90 i layer, in 9 secondi. Vengono segnalati anche i
layer non dichiarati nella tabella LAYER (colore e spessore li deciderebbe chi
apre il file), le coordinate fuori dai limiti di MN95, e i messaggi che GDAL
scrive per conto suo — che prima finivano su `stderr`, cioè in nessun posto.

Cosa prende e cosa no è **misurato**, costruendo un DXF apposta per ciascun
difetto: scarta i tipi di entità sconosciuti, la `REGION`, la `POLYLINE` senza
vertici e quella senza `SEQEND`; legge invece il flag `70=1` sui vertici (che
era ezdxf a scartare), `MLINE`, il testo senza altezza e l'hatch senza
contorno. I due lettori non si sostituiscono a vicenda.

### Scala di stampa

- La scala del layout del piano di base non è più fissata a 1:5000 nel codice:
  la decide il menu «Scala», come già per la planimetria RF. Prima chi ne
  sceglieva un'altra otteneva comunque un foglio 1:5000, con sopra stampato
  «Scala: 1:5000». Passando a PB-MU il menu si porta su 1:5000 solo se
  l'utente non ha già scelto.

### Correzioni

- Chiudere la finestra mentre una conversione era in corso poteva sollevare
  «wrapped C/C++ object of type JavaWorker has been deleted».

## 1.1.1 — 7 agosto 2026 — sperimentale

Prima versione preparata per la pubblicazione. Rinominata da «Cadastra
Dashboard» a **TIDashboard**.

### Conformità alla norma

- Fattore di proporzionalità del cap. 1.5.2, con scala di riferimento propria per
  ciascun prodotto: 1:1000 per il piano RF, 1:5000 per il piano di base.
- Esclusi dal piano i temi che il cap. 1.5.3 non rappresenta: altimetria, punto
  quotato, aree di numerazione, ripartizione dei piani, grado di tolleranza.
- Trame di roccia e pietraia affiancate senza spaziatura, come prescrive la
  «Distanza: 0» del cap. 4.
- Colori del piano di base allineati ai CMYK del Weisung, compreso il colore
  proprio dell'edificio a 1:10000.
- Verificati contro il testo delle norme: le otto scale ammesse, i tre grigi
  delle trame, le dodici grandezze delle scritture del cap. 5, i quattro passi
  delle trame a punti.

### Planimetrie

- Reticolo di coordinate con passi tondi, croci più visibili e coordinate
  verticali sui bordi laterali.
- Cartiglio con le sette iscrizioni obbligatorie, comune e data letti dai dati,
  barra di scala con caposaldo tondo, freccia nord agganciata alla rotazione.
- Dicitura «Riproduzione senza valore legale» in rosso.
- Anteprima dell'ingombro del foglio sul canvas.

### Interfaccia

- Riorganizzata in tre schede con avanzamento, convalida dei percorsi, console
  filtrabile e memoria delle impostazioni.
- Traduttore DXF e modello INTERLIS in dotazione, non più selezionabili.

### Correzioni di rilievo

- Il centro della planimetria finiva a 150 km dai dati quando il GeoPackage
  dichiarava un'estensione segnaposto.
- Il foglio stampava anche i layer spenti nell'albero, fra cui gli
  identificatori dei punti di confine che il cap. 5.10 non rappresenta.
- La console interpretava come HTML il testo proveniente dai dati.
- Il modello INTERLIS veniva scaricato via HTTP in chiaro.
