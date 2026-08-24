# Diario delle versioni

## 1.2.8 — 25 agosto 2026 — sperimentale

Quattro difetti segnalati da una valutazione esterna del codice, verificati
uno per uno prima di toccare qualcosa.

### Il ramo che avvisa dei font mancanti alzava un'eccezione

`simbologia._load_font_file` usava `QgsMessageLog` senza importarlo. Quel
ramo esiste **apposta** per non fallire in silenzio quando un font manca o è
corrotto — il difetto più caro di questo progetto — e sollevava
`NameError` esattamente lì. Nessuna prova ci passava, perché nessuna provava
a caricare un font inesistente. Ora c'è.

### Le coordinate incollate da un PDF venivano rifiutate

Lo spazio unificatore (U+00A0) e quello stretto (U+202F) — la norma
tipografica nei PDF e nelle pagine web — stavano nella classe dei separatori
delle **migliaia**, quindi sparivano prima che la coppia venisse divisa:
`2718000 1082000` diventava un numero solo, e il messaggio invitava a
«separare i due numeri con uno spazio», cioè proprio quello che si era appena
fatto.

Lo stesso carattere non può stare in tutt'e due i ruoli. Ora è separatore, e
le migliaia scritte con lo spazio si ricompongono dopo — un gruppo di
migliaia ha esattamente tre cifre, quindi non si indovina. Undici forme di
scrittura provate: apostrofi, virgole, lettere degli assi, decimali.

### Una data in formato svizzero faceva saltare la lettura

Il filtro sulle date delle tabelle di attualizzazione era `len(v) == 10`, e
`12.03.2024` ha esattamente dieci caratteri: passava, e lo `split("-")`
successivo sollevava `ValueError`. Ora si verifica il formato.

### Il LICENSE non era controllato

Nel pacchetto c'era, ma solo perché sta nella cartella: nessuno lo
verificava, mentre la GPL-2.0 ne pretende la distribuzione. Ora è fra i file
attesi dal pacchettizzatore. Sistemata anche una frase troncata in
`CREDITI.md`.

## 1.2.7 — 21 agosto 2026 — sperimentale

### Ogni nome della nomenclatura si scriveva due volte

Il riscontro fra regola di etichetta e tabella è per sottostringa, e
`nomenclatura_posnome_di_localita` **contiene** `nome_di_localita`: venivano
etichettati tutti e due i layer, il punto di iscrizione **e** il poligono che
delimita l'area denominata. Misurato sul comune di prova:

| classe | poligoni | punti | iscrizioni sul foglio | dovute |
|---|---|---|---|---|
| `nome_di_localita` | 10 | 12 | 22 | 12 |
| `nome_locale` | 648 | 760 | 1408 | 760 |

**658 scritte di troppo** su un comune solo. E non se ne perdeva una per
collisione: la distanza fra le due copie dello stesso nome ha mediana 52.6 m
per le località e 40.4 m per i nomi locali — a 1:1000 sono 40–50 mm di carta,
cioè due scritte lontane e ben leggibili che dicono la stessa cosa.

Quella giusta è sul punto: il modello dice che `PosNome_X` è «l'iscrizione del
Nome», e porta `Ori`/`HAli`/`VAli`, cioè dove e come il geometra ha deciso di
scriverlo. Il poligono è l'estensione dell'area denominata, e il suo centro lo
sceglie QGIS.

### Il WMS dichiarava di coprire tutta la Svizzera

Trovato alla prima prova contro un QGIS Server vero. L'estensione pubblicata si
leggeva da `layer.extent()`, che su un GeoPackage viene da `gpkg_contents` — e
ili2gpkg ci scrive i limiti dell'intero sistema di riferimento:

```
dichiarata  2480000 1070000 2850000 1310000   370 x 240 km
calcolata   2714971 1077802 2722453 1086633   7.5 x 8.8 km
```

Un geoportale si sarebbe aperto su una mappa vuota, con il comune ridotto a un
punto. Ora l'estensione si calcola dalle geometrie: 0.1–0.2 s per layer.

> **Nota per chi pubblica su un server.** La prova locale ha confermato che
> senza i font Cadastra installati sulla macchina il servizio risponde
> regolarmente e disegna i simboli dei punti come **lettere dell'alfabeto**.
> Nessun errore, nessun avviso, stessa dimensione del file. Ed è emerso che
> **QGIS Server su Windows non serve a questo scopo**: impone una piattaforma
> grafica che sul sistema non vede alcun font.

## 1.2.6 — 21 agosto 2026 — sperimentale

### Nomi di località in maiuscolo (raccomandazione cap. 5.7)

Nuova spunta nella scheda *Planimetria*, **spenta di default**. Le istruzioni
federali dicono:

> «Raccomandazione: I nomi di località corrispondenti a delle borgate sono da
> indicare preferibilmente con lettere maiuscole.»

«Preferibilmente», non «devono»: accenderla di serie cambierebbe l'aspetto di
tutte le planimetrie già prodotte per una cosa che la norma non pretende.
L'effetto è immediato sui layer già caricati — una scelta di resa grafica non
può costare una reimportazione, che su un file di produzione sono minuti.

**Il dato non viene toccato.** Nel GeoPackage i nomi sono in minuscolo (zero su
dieci maiuscoli, verificato sul comune di prova) e il maiuscolo si applica al
disegno. Cambiare i nomi sarebbe riscrivere una consegna ufficiale per una
questione di resa grafica.

**Il limite, dichiarato.** La norma parla di località «corrispondenti a delle
borgate». Il modello un posto per dirlo ce l'ha — `Tipo: OPTIONAL TEXT*30;
!! assegnato dal cantone` — ma nella consegna ticinese è vuoto su tutte le
località del comune di prova. Un campo facoltativo che il Cantone non compila
non è un criterio, quindi la regola vale per l'intera classe
`Nome_di_localita`: su Mendrisio quelle dieci sono esattamente le borgate,
altrove potrebbe non essere così. Diventerà esatta il giorno in cui `Tipo`
verrà valorizzato.

## 1.2.5 — 21 agosto 2026 — sperimentale

### Il pulsante «Consegna per QGIS Server»

Scheda *Importazione*, sotto «Crea layout PB-MU». Chiede una cartella e ci
scrive dentro tutto quello che serve a un server per disegnare il piano:
progetto, dati, font, simboli e un `LEGGIMI.txt` con l'unico passo che il
plugin non può fare al posto di chi consegna — installare i font sulla
macchina. È spento finché non c'è un'importazione riuscita, con il motivo nel
tooltip invece che nascosto.

**Il progetto della sessione non viene adeguato all'importazione**, che era la
proposta da cui siamo partiti. I flag WMS non li legge solo il server:
`Private` toglie il layer dall'albero e `Identifiable` spegne lo strumento
«informazioni» del desktop. Applicarli a fine importazione vorrebbe dire che da
quel momento un clic su una copertura del suolo non risponde più, senza
spiegazione. Si adegua al momento della consegna, e si rimette tutto a posto.

A consegna finita la cartella viene riaperta e **controllata**: nessun percorso
assoluto, ogni file citato dal progetto dentro la cartella, capabilities WMS
presenti. Il controllo guarda il file scritto, non gli oggetti in memoria.

### Due difetti trovati provando il percorso intero

Una prova che passa dal metodo della finestra, invece di chiamare la funzione
direttamente, ha mostrato quello che le prove del modulo non potevano vedere:

- il controllo trattava **ogni** `datasource` come un percorso di file, e per
  un layer temporaneo (sorgente `Point?crs=EPSG:2056&field=…`) diceva «assente
  dalla cartella». Non manca nessun file: quel layer non ha file. Ora decide il
  provider — `ogr`/`gdal` è un file e deve stare dentro la cartella, `memory`
  non esiste fuori dalla sessione e viene detto per quello che è, `wms` e simili
  vivono sulla rete e sul server vanno bene;
- il promemoria sui font compariva solo nel messaggio di successo, cioè spariva
  proprio quando la consegna aveva già qualcosa che non andava.

## 1.2.4 — 21 agosto 2026 — sperimentale

### Il sistema che ha prodotto l'archivio

Terza causa, e ultima. Dopo aver fissato i fine riga (1.2.1) e l'ordine delle
voci (1.2.3), i due archivi della 1.2.3 erano ancora diversi: stessi file,
stesso ordine, stessi byte compressi, e **un byte diverso nella directory
centrale di ognuna delle 174 voci** — `\x14\x03` contro `\x14\x00`.

È il campo che lo ZIP si annota da solo: il sistema che l'ha prodotto.
`zipfile` scrive 0 (MS-DOS) su Windows e 3 (Unix) altrove. Ora è fissato a 3 —
non a 0, perché i permessi che scriviamo sono permessi Unix e hanno senso solo
se l'archivio dichiara di venire da un sistema Unix; con 0 quei bit c'erano ma
nessuno li avrebbe letti.

**Questa volta la promessa è stata misurata prima di scriverla.** Fissato il
campo, la ricostruzione su Windows del contenuto della 1.2.3 ha prodotto
`e992cab9…`, cioè esattamente l'archivio che la CI aveva costruito su Linux:
byte per byte, senza sapere in anticipo il risultato. La verifica dell'archivio
controlla ora anche questo campo, oltre all'ordine.

> **Correzione al diario della 1.2.3.** Quella voce diceva che la verifica vale
> «dalla 1.2.3 in poi». Vale **dalla 1.2.4**: la 1.2.3 aveva tolto la seconda
> causa su tre. È la seconda volta di fila che una causa risolta è stata
> scambiata per il problema risolto; per le versioni precedenti il confronto
> non torna, e non è segno di manomissione.

## 1.2.3 — 21 agosto 2026 — sperimentale

### L'ordine delle voci nell'archivio

Il controllo promesso dal README — scaricare il pacchetto della Release,
ricostruirlo dallo stesso tag e confrontare le impronte — **non tornava**, e
questa volta la causa non erano i fine riga.

I due archivi della 1.2.2, quello pubblicato dalla CI e quello ricostruito su
Windows, avevano: gli stessi 174 file, gli stessi contenuti, le stesse date e
gli stessi permessi, perfino le **stesse dimensioni compresse voce per voce**.
Era diverso solo l'**ordine**. `os.walk` visita le sottocartelle nell'ordine che
gli dà il filesystem, e quell'ordine non è lo stesso su NTFS e su ext4: su
Linux `models/` veniva prima di `fonts/`, qui `av2geobau/` prima di tutto.
Ordinare i file *dentro* ciascuna cartella, come si faceva, non basta.

Ora le voci si raccolgono tutte, si ordinano per nome e poi si scrivono; e la
verifica dell'archivio controlla che siano in ordine alfabetico, così il
difetto non può rientrare in silenzio. Provato costruendo con l'ordine di
visita **rovesciato**: stessa impronta, byte per byte.

> **Correzione al diario della 1.2.1.** Quella voce dichiarava che «da questa
> versione l'impronta accanto alla Release è verificabile ricostruendo dallo
> stesso tag». Era falso: la correzione dei fine riga aveva tolto una causa su
> tre. Verificato ricostruendo dal tag `v1.2.1` — stessi file, stessi
> contenuti, ordine diverso, impronta diversa.
>
> E anche questa voce ha dichiarato troppo presto (vedi 1.2.4): restava il
> campo «sistema che ha prodotto l'archivio». **La verifica vale dalla 1.2.4.**

## 1.2.2 — 21 agosto 2026 — sperimentale

### Si installa da GitHub senza sbagliare pacchetto

Scaricare con *Code → Download ZIP* dava
`ModuleNotFoundError: No module named 'TIDashboard-main/tidashboard'`, e non è
aggiustabile da questo lato: GitHub mette sempre una cartella `<nome>-<ramo>`
in cima, QGIS usa il nome della cartella come nome di modulo Python, e un
trattino non è un nome valido. Nessuna disposizione dei file nel repository può
farlo funzionare.

Il repository pubblica ora un **catalogo `plugins.xml`**: un indirizzo da
incollare una volta sola in QGIS (*Estensioni → Impostazioni → Aggiungi*), dopo
il quale il plugin si installa e si aggiorna come qualunque altra estensione.
Il catalogo è generato da `metadata.txt` a ogni costruzione del pacchetto —
scritto a mano si scollerebbe dalla versione al primo rilascio — e il suo
indirizzo di scarico punta al **tag**, non a «latest»: se la Release di quella
versione non esiste ancora, il download fallisce invece di servire di nascosto
un pacchetto diverso da quello dichiarato.

Un difetto trovato leggendo il codice che consuma il catalogo
(`pyplugin_installer/installer_data.py`): QGIS ricava l'**identificativo** del
plugin da `file_name` prendendo tutto ciò che sta prima del primo punto, e
quell'identificativo deve coincidere con il nome della cartella installata. Con
`tidashboard_1.2.1.zip` sarebbe uscito `tidashboard_1`: il plugin sarebbe
comparso come una cosa diversa da quella installata, sarebbe rimasto «non
installato» anche dopo l'installazione e nessun aggiornamento sarebbe mai stato
proposto, senza un errore da nessuna parte. Ora la costruzione si ferma se
l'identificativo non torna.

Le Release portano anche una copia a nome fisso, `tidashboard.zip`, così il
README può indirizzare un collegamento che non scade a ogni pubblicazione.

### Il progetto stilizzato si può consegnare a QGIS Server

Modulo nuovo `pubblica_progetto.py`, sul modello di `legend_manifest.py`: un
ponte verso un altro programma, non una funzione dell'interfaccia. Scrive una
cartella (`.qgz` + `.gpkg` + `fonts/` + `symbols/` + `LEGGIMI.txt`) che si copia
su un server e basta. **Non è ancora collegato a un pulsante**: per ora è una
libreria, con le sue prove.

I percorsi che escono dal PC sono due, non uno. Il datasource diventa relativo
da solo quando il progetto si sposta; il percorso del simbolo no — misurato,
resta un `../../../…` che risale alla cartella del plugin, che sul server non
esiste. Copiare `symbols/` accanto al `.qgz` non cambia nulla, perché nulla
punta alla copia: i simboli vanno riscritti uno per uno. Il terzo, i font,
non è un percorso e non si può riscrivere: vanno installati sulla macchina, e
`LEGGIMI.txt` dice come.

Chi resta fuori dal servizio non è un elenco di nomi ma si deduce dalla
decisione che il plugin ha già preso applicando gli stili, così i temi che il
cap. 1.5.3 non rappresenta restano fuori senza essere nominati due volte — con
la distinzione che le tabelle `Pos*` hanno il simbolo invisibile *apposta* e
portano le iscrizioni, quindi restano dentro.

La sessione non viene toccata: `Private` toglie il layer dall'albero e
`Identifiable` spegne lo strumento «informazioni» anche sul desktop, quindi
tutto ciò che la consegna cambia viene rimesso a posto. E il risultato si
controlla sul **file scritto**, non sugli oggetti in memoria.

### Il pacchetto controllava 11 moduli su 17

La lista dei file attesi nell'archivio era scritta a mano e si era scollata:
sei moduli non erano controllati, tutti nati dopo che la lista era stata
scritta. Se uno fosse sparito, lo script avrebbe detto `PACCHETTO VALIDO`
mentre il plugin moriva al caricamento. Ora i moduli attesi si leggono dagli
`import` di `tidashboard.py`.

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
stessi byte.

> **Questa voce dichiarava troppo** (corretto nella 1.2.3): diceva che da
> questa versione l'impronta era verificabile ricostruendo dallo stesso tag.
> I fine riga erano una causa su due — restava l'ordine delle voci
> nell'archivio, che dipendeva dal filesystem. La verifica vale dalla 1.2.3.

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
