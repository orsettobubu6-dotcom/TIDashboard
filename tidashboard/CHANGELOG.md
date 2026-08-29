# Diario delle versioni

## 1.3.3 — 29 agosto 2026 — sperimentale

Stesso contenuto della 1.3.2, che non è stata pubblicata: la sua CI è caduta su
`ruff`, che segnalava quattro rilievi in codice scritto quel giorno — una
`sorted(set(...))` da riscrivere come comprensione, un prefisso `u""` residuo di
Python 2, un `IOError` che in Python 3 è un alias di `OSError`, e un `open()`
senza gestore di contesto in una prova.

Il tag `v1.3.2` non è stato spostato. Un tag che cambia contenuto è peggio di un
tag fallito: chi l'avesse già scaricato si troverebbe un file diverso con lo
stesso nome, che è esattamente il difetto da cui è partito questo giro di
controlli.

Il resto è nella 1.3.2 qui sotto.

## 1.3.2 — 29 agosto 2026 — non pubblicata (CI rossa su ruff)

Quattro interventi sulla finestra, la consegna WebGIS provata davvero su Linux,
e due controlli che non sapevano di non star controllando.

### La finestra: gli ultimi quattro punti

**Il pulsante che cancella è uscito dalla pila.** Era la terza di tre barre a
tutta larghezza, impilate a 42 pixel e distinte solo dal colore: il gesto che
importa e quello che distrugge si somigliavano ed erano a un centimetro. Ora sta
su una riga sua, dopo un separatore, allineato a destra, alto la metà, col bordo
invece del fondo pieno — il rosso pieno su una barra grande attira il clic
invece di scoraggiarlo. Quanti comuni butterebbe non sta più *dentro* il
pulsante ma nella riga accanto, dove l'occhio passa prima di arrivare al clic.

**Le due uscite hanno una scheda loro** («4. Consegna»). *Crea layout PB-MU* e
*Consegna per QGIS Server* non sono importazioni: stavano in fondo alla scheda
sbagliata, spente, a occuparne la metà bassa. Ora sotto ognuna c'è scritto
**perché** è spenta: un pulsante grigio non lo dice, e il suggerimento lo legge
solo chi sospetta già che ci sia qualcosa da leggere.

**L'avviso sulla data è una riga, non un paragrafo.** Erano 238 caratteri
arancioni su due righe, sempre a video. Ora la riga nomina la fonte e la riserva
sta nel suggerimento — con due eccezioni volute: quando la data è stata messa a
mano il valore che risultava dai dati resta in riga, e quando non c'è nessuna
fonte il testo resta per esteso, perché lì non è una riserva ma un allarme.

**L'elenco dei risultati compare con la ricerca.** Un riquadro vuoto alto 110
pixel e due pulsanti grigi stavano sempre lì, sulla scheda già più carica.

### La consegna WebGIS, provata su Linux

Non era mai stata provata contro il consumatore vero. Provata, e c'era un
difetto che da Windows non si poteva vedere: il progetto consegnato portava un
`homePath` con il percorso assoluto della macchina che l'aveva prodotto.

Non era dimenticato, era impostato apposta — con l'intento di far risolvere i
percorsi relativi. Ma è un percorso di Windows, e su un server Linux quella
cartella non esiste. E `homePath`, quando è valorizzato, è la **base** con cui
QGIS risolve i percorsi relativi: proprio i `./symbols/...` che la consegna ha
appena reso relativi dipendono da lui. Ora resta vuoto, e QGIS ripiega sulla
cartella del progetto — giusta ovunque la si copi.

**Poi il server vero.** QGIS Server 3.34 LTR su Linux serve la consegna, e il
PNG di un GetMap è byte per byte identico a quello di un server 4.x su Windows.
Ma la 3.34 **non legge** le proprietà WMS del progetto: il formato è cambiato
fra la serie 3 e la 4. In concreto, EPSG:2056 non viene annunciato nelle
capabilities — ed è il sistema nativo del catasto svizzero. Il `LEGGIMI.txt` ora
lo dice, con l'elenco di cosa si perde sulla LTR.

### Due controlli che non sapevano di non controllare

**Le maiuscole.** Su Windows il controllo più importante di `verifica_consegna`
— che ogni file nominato esista davvero — non può fallire: il filesystem le
ignora, quindi un progetto che chiede `Symbol_1_Fels.svg` trova
`symbol_1_fels.svg` e passa. Sul server no. Ora lo dichiara, e lo **prova**
invece di dedurlo dal sistema operativo: crea un file e lo ricerca scritto in un
altro modo, perché esistono cartelle sensibili su Windows e insensibili su Linux.

**I comuni nel file.** Con l'archivio a più comuni il GeoPackage consegnato non
coincide con ciò che si pubblica: i layer portano il filtro del comune attivo,
quindi il WMS ne mostra uno, ma il file li contiene tutti. Su un archivio
cantonale vorrebbe dire spedire un gigabyte per pubblicarne uno, e consegnare
dati che non si intendeva consegnare. Il `LEGGIMI.txt` ora lo dice, coi numeri.

### In breve

- **714 prove, tredici suite.** `test_inventario` non era nella CI: dieci prove
  che non avevano mai girato su Linux. Ora c'è.
- Il verde di due righe era cablato a `#2E7D32`, illeggibile su tema scuro; il
  metodo che sceglie il colore giusto esisteva già e non veniva chiamato.
- Le opzioni di tolleranza nascono spente e le spunte si nascondono: la spunta
  del riquadro non è apri/chiudi, è l'interruttore generale.

## 1.3.1 — 27 agosto 2026 — sperimentale

Correzioni trovate **aprendo QGIS** dopo la 1.3.0, più i primi interventi sulla
finestra. Chi usa la 1.3.0 con più comuni dovrebbe passare a questa.

### La data del cartiglio non era quella del comune

Due difetti, e il secondo &egrave; rientrato dalla porta che avevo appena
chiuso.

Il campo ITF è **uno solo**, i comuni sono molti: la data di modifica di quel
file finiva in cartiglio per tutti. In una sessione vera il campo era rimasto
pieno dalle impostazioni precedenti — un ITF scaricato mesi dopo — e i due
comuni dichiaravano entrambi «stato al 20.08.2026», che non apparteneva a
nessuno dei due: i loro dati sono del 17.06 e del 20.05.

La correzione c'era già in `leggi_data_validita`, ma **veniva scavalcata**: la
data dell'ITF ha la precedenza e non si arrivava mai a leggere i dati. Ora con
più comuni la data dell'ITF si salta. Con **un** comune solo resta com'era.

Poi: cambiando comune dalla tendina la mappa si filtrava, ma il cartiglio
continuava a portare la data del comune di prima — la tendina era agganciata al
filtro dei dati e non alla rilettura della data.

Nessuna delle due l'avevano prese le prove, e per lo stesso motivo: **svuotavano
il campo ITF apposta** e chiamavano l'aggiornamento a mano, per arrivare al ramo
che stavano provando. Così facendo saltavano proprio la condizione che rompe.

### Il selettore di comune è salito sopra le schede

Stava dentro la planimetria, in fondo a una riga, con l'aria di un campo
dell'intestazione. Ma da quando l'archivio tiene più comuni decide **che cosa si
vede**: quali oggetti sulla mappa, su che estensione si centra il foglio, quale
data va nel cartiglio.

Ora una barra sopra le schede risponde alle due domande che servono in tutte e
cinque:

```
Archivio: archivio.gpkg  2 comuni - 14.7 MB     Comune attivo: [Coldrerio v]  2 di 2
```

Il **nome del file** e non il percorso: il campo di testo mostra il centro di un
percorso lungo, che è la parte che non serve, mentre l'unica cosa che identifica
un archivio sta in fondo e non si vede. La barra sparisce quando non c'è un
archivio.

Nella planimetria resta un'eco — «Il piano sarà intestato a Coldrerio» —
perché togliere la tendina senza lasciare niente avrebbe reso muto proprio il
punto in cui si decide l'intestazione.

### Le opzioni di tolleranza nascono spente

Il riquadro nasceva **acceso**, con «Non validare i dati» in prima fila. E la
sua spunta non è apri/chiudi: è l'interruttore generale, perché con essa spenta
non viene passato nessun flag a ili2gpkg. Nascere acceso voleva dire presentare
come normali delle opzioni da usare solo quando una consegna è rotta e si sa
perché.

Ora nasce spento e le spunte si **nascondono**: disabilitarle non basta, sei
opzioni grigie occupano lo stesso spazio e chi legge «Non validare i dati» non
guarda se è grigio. Il titolo dice quante ne sono attive anche a riquadro
chiuso, e quando ce n'è almeno una lo si ripete sopra il pulsante: senza,
un'importazione con la validazione spenta somiglierebbe in tutto a una normale.

Chi l'aveva già acceso se lo ritrova acceso: una scelta salvata non si
sovrascrive cambiando il valore iniziale.

### Due righe verdi illeggibili sul tema scuro

Il colore era cablato a `#2E7D32`. Il metodo che sceglie il verde giusto secondo
il tema **esisteva già** e in quei due punti non veniva chiamato. Una delle due
righe dice se il piano rispetta la proporzione della norma: un'informazione di
conformità, non una nota di servizio.

### In breve

- 675 prove, undici suite. Ogni correzione fatta girare contro il codice
  precedente per verificare che fallisse davvero.
- Le prove sulle tolleranze si isolano dalle impostazioni salvate: senza,
  leggerebbero la scelta di chi le esegue.

## 1.3.0 — 27 agosto 2026 — sperimentale

Fino a qui il plugin lavorava su **un comune per volta**: un file ITF, un
GeoPackage, un piano. Questa versione porta l'**archivio a più comuni**, e con
esso tutto ciò che ne deriva.

Prima di scrivere una riga ho provato l'architettura sui dati veri, importando
Lavertezzo e Coldrerio in un GeoPackage solo. Le misure hanno deciso il
progetto:

| prova | esito |
|---|---|
| due comuni in un GeoPackage | riuscito, `--dataset` li tiene separati |
| `T_datasetname` su ogni tabella | sì, e l'indice lo crea `ili2gpkg` da solo |
| `--replace` di un comune | gli altri restano intatti |
| costo per comune | **11 s, 6,5 MB** |

Undici secondi e sei megabyte per comune vogliono dire che un archivio
cantonale sta sotto il gigabyte e si carica in mezz'ora: **il GeoPackage
regge, PostGIS non serve**. E siccome SQLite usa l'indice su `T_datasetname`
(`SEARCH`, non `SCAN`), filtrare per comune resta immediato anche a 106.

Non ho invece fuso gli ITF a monte con ITFCOPY, che sarebbe stata la
scorciatoia: unire i comuni prima dell'importazione distrugge l'identità del
comune, cioè proprio quello che serve per esportare il DXF di uno solo.

### L'importazione aggiunge invece di distruggere

Era il difetto peggiore che il plugin avesse. `run_import` cancellava il
GeoPackage a ogni giro: con un comune solo era accettabile, con l'archivio a
più comuni significa che **importare il secondo buttava via il primo**. E la
conferma parlava di «sovrascrittura del file», non di «perdi i comuni già
dentro», quindi rispondere *sì* era ragionevole e distruttivo. Nessuna delle
159 prove dell'interfaccia lo copriva.

Ora la decisione la prende un pianificatore che sta fuori dalla finestra:

| caso | cosa fa |
|---|---|
| archivio assente | schema + dati, con `--createDatasetCol` |
| comune nuovo | `--import --dataset`, schema **saltato** |
| comune già dentro | `--replace --dataset`, gli altri intatti |
| tutto il resto | rifiuto, con il motivo scritto |

I rifiuti contano più del resto. Il più importante è l'archivio **senza
`T_datasetname`** — uno creato da una versione precedente: aggiungendoci un
comune, le righe già dentro resterebbero senza proprietario e nessun filtro
potrebbe più separarle. Danno che non si vede al momento e non si disfa.

### Una cartella intera, che riprende invece di ricominciare

106 comuni uno alla volta non li carica nessuno. Un pulsante nuovo prende una
cartella di `.itf` e li importa in coda. I comuni già dentro si **saltano**:
un giro da mezz'ora interrotto a metà riprende da dove si era fermato.

Un comune andato male non ferma gli altri — su cento consegne, fermarsi al
primo file storto vorrebbe dire rifare tutto il giro dopo averlo tolto — e
quali siano falliti si dice alla fine.

Due file per lo **stesso** comune sono un rifiuto per il secondo, non una
sovrascrittura silenziosa: quale dei due valga non lo può decidere il
programma.

### Il piano segue il comune scelto

Due difetti trovati misurando l'archivio vero, ed erano lo stesso difetto
visto da due lati: il codice leggeva l'archivio **intero** dove il piano parla
di **un** comune.

**La data era quella di un altro comune.** Il piano di Coldrerio dichiarava
«stato al 17.06.2026» — la data di Lavertezzo — mentre i dati di Coldrerio
erano fermi al 20.05.2026. «Stato al» è una delle nove iscrizioni
obbligatorie (circ154_allegato2 cap. 1.5.7): era un'affermazione falsa su un
atto ufficiale.

**Il foglio si centrava sull'unione dei comuni**: 10 101 × 37 213 m invece di
1 549 × 902 m, e nessuna delle otto scale di norma poteva contenerla — il
piano non era producibile.

Rimedio unico: filtrare per `T_datasetname`. Cambiando comune nella tendina
ora si riducono anche i dati, non solo l'intestazione. Con **un comune solo**
— il caso di gran lunga più frequente — nessun filtro viene applicato e il
comportamento resta identico a prima.

### Il contorno del fondo si legge anche quando è curvo (e lo è sempre)

Difetto preesistente, e non piccolo. Il lettore conosceva `POLYGON` e
`MULTIPOLYGON`, ma i fondi ticinesi non sono né l'uno né l'altro: misurato sui
dati veri, **500 geometrie su 500 sono `CURVEPOLYGON`**, ogni anello è un
`COMPOUNDCURVE`, e il 15% dei pezzi di confine è un arco.

Il contorno usciva quindi **sempre vuoto**, e con esso la sola cosa che sappia
dire se un fondo lungo e stretto ci starebbe nel foglio *girandolo*. Le prove
non se ne accorgevano perché costruivano poligoni dritti, un formato che in
questi dati non compare mai.

Ora si leggono anche `CURVEPOLYGON` e `MULTISURFACE`, e gli archi si
infittiscono ricostruendo il cerchio per i tre punti — tenere solo quei tre
darebbe una spezzata che taglia la curva con un errore pari alla saetta, la
stessa grandezza che ci aveva morso sul *bulge* del DXF. Sui dati veri: 2000
contorni su 2000, 16 vertici in media, 0,01 ms per geometria.

### La ricerca dice quando non ha potuto cercare

Un GeoPackage senza le tabelle dei fondi, uno danneggiato e un percorso
inesistente davano tutti e tre la lista vuota: **la stessa risposta di una
ricerca riuscita e senza esiti**. Si leggeva «Nessun fondo trovato. Controlla
numero, sezione e comune» e si andava a controllare dei dati che erano giusti.

È lo stesso principio già applicato al controllo di deviazione del DXF: un
controllo che non ha potuto controllare niente non ha trovato niente di buono.
Il caso legittimo — la ricerca c'è stata e non ha trovato nulla — resta
invariato, che è la distinzione che serviva.

### Il manifest della legenda trova l'ITF giusto

Il lato Java lo cerca accanto all'ITF che riceve. Si scriveva solo accanto a
quello dell'**importazione**: due campi indipendenti, e con più comuni quasi
mai lo stesso file. Il DXF usciva senza legenda, senza un errore. Ora si
riscrive al momento della conversione, e se nessuno stile è stato applicato lo
si **dice**.

### Ricominciare da capo

Avendo tolto la cancellazione automatica, serviva un modo esplicito di
ripartire da zero. La conferma **nomina i comuni** che sta per buttare, invece
di parlare genericamente di sovrascrittura, e non si cancella un file che non
sia un nostro archivio — nemmeno rispondendo di sì.

### In breve

- 658 prove, undici suite. Ogni correzione è stata fatta girare contro il
  codice precedente per verificare che fallisse davvero.
- Chi ha un GeoPackage creato con una versione precedente deve **rifarlo**: le
  sue tabelle non hanno la colonna che tiene separati i comuni. Il plugin lo
  riconosce e lo dice, invece di rovinarlo.

## 1.2.9.3 — 27 agosto 2026 — sperimentale

### Si misura che la conversione non ha spostato le coordinate

Finora il plugin *affermava* che ITF e DXF portano le stesse coordinate. Ora lo
**misura**: legge le coordinate dall'ITF, le ricerca nel DXF e riporta lo
scarto massimo.

```
Max X deviation: 0.0000 m
Max Y deviation: 0.0000 m
coordinate identiche: 65925 di 90735 (72.7%)   spostate: 0   collocate dal piano: 24810
```

Va detto subito che cosa questa misura **non** è: non è un cercatore di bachi.
Il convertitore le coordinate le passa così come sono, quindi quella riga dirà
`0.0000 m` praticamente sempre, e non avrebbe preso nessuno dei tre difetti
veri corretti nel jar (ancoraggio del testo, precisione del *bulge*, valori
d'intestazione). È una **prova documentale** per la consegna. Costa 0,8 s su un
comune intero (ITF 3,4 MB, DXF 16,5 MB).

Quello che prende davvero, verificato costruendo apposta i file rotti:

| caso | esito |
|---|---|
| uno spostamento di 5 mm | rilevato |
| uno spostamento uniforme di tutti i punti | rilevato |
| arrotondamento al centimetro | rilevato (0,7% di identiche) |
| arrotondamento al decimetro | rilevato (0,008%) |
| scambio di X con Y | «nessuna coordinata confrontabile» |
| una manciata di punti spostati | **non** rilevato |

L'ultima riga è un limite dichiarato, non un difetto nascosto.

Lo scambio X/Y merita una nota, perché la prima versione lo riportava come
`Max deviation: 0.0000 m`, cioè come un esito buono sul file più rotto di
tutti: scambiate le coordinate, nessun punto cade più nelle gamme di MN95,
non restava niente da confrontare e una misura **vuota** usciva come promossa.
Un controllo che non ha potuto controllare niente non ha trovato niente di
buono, e adesso lo dice.

### Un allarme che avevo costruito, e che ho tolto prima di collegarlo

Sopra quella misura avevo aggiunto un secondo allarme, per layer: fuori dalla
banda 10%-99,5% di coordinate identiche un layer è «a metà», quindi sospetto.
L'idea veniva da una misura vera — su due comuni interi i layer stanno o in
alto o in basso, mai in mezzo.

Rileggendola prima di collegarla, il margine è risultato di **due decimi di
punto**: il layer sano più basso sta al 99,7%, la soglia al 99,5%, tarati su
due soli comuni. Un allarme così stretto, il giorno che sbaglia, sbaglia su una
consegna buona — e un controllo che grida al lupo lo si spegne, portandosi via
anche la parte che funziona. Il caso che copriva non ha nemmeno un meccanismo
noto che lo produca: gli errori veri del convertitore sono sistematici, e
quelli si vedono nello scarto massimo.

La ripartizione per layer è rimasta come **dettaglio su un allarme già
scattato**: dice *dove*, quando qualcos'altro ha già detto *che cosa*. A
referto sano non si stampa.

### Gli archi si controllano anche da fermi

Il controllo del *bulge* introdotto nella 1.2.9.2 correggeva la scrittura degli
archi nel jar. Ora il plugin **rilegge** quello che il jar ha scritto e segnala
gli archi il cui scostamento supera 0,1 mm, senza dover riconvertire nulla.
Serve perché il secondo parere abituale non basta: GDAL rilegge fedelmente un
*bulge* impreciso, e quindi non se ne accorge.

## 1.2.9.2 — 25 agosto 2026 — sperimentale

### Gli archi del DXF erano scritti con troppe poche cifre

Il *bulge* — il numero con cui il DXF descrive un arco — usava la stessa
precisione delle coordinate LV95: **tre decimali**. Per una coordinata è
giusta, è il millimetro. Ma il bulge è un rapporto adimensionale fra 0 e 1, e
vale la relazione esatta `saetta = bulge × corda / 2`: tre decimali lasciano
passare uno scostamento dell'arco fino a

| corda | prima | ora |
|---|---|---|
| 10 m | 2,50 mm | 0,000025 mm |
| 50 m | 12,50 mm | 0,000125 mm |
| 150 m | 37,50 mm | 0,000375 mm |

E due archi del comune di prova avevano un bulge sotto `0.0005`, cioè scritti
come **zero**: due archi diventati segmenti retti.

Ora il bulge si scrive con otto decimali. La precisione delle coordinate resta
al millimetro: portarle a otto decimali gonfierebbe ogni riga del file per
descrivere il nanometro su una misura fatta al centimetro.

### `$ANGBASE` era in radianti su un campo in gradi

Il gruppo 50 dell'intestazione DXF è in **gradi**; c'era `1.571`, cioè π/2 in
radianti. Letto come gradi non dice né est (0) né nord (90), ma un angolo e
mezzo che non significa niente. Il piano per il registro fondiario misura gli
azimut da nord: ora è `90`.

### `$TDCREATE` era una data fissa

Ogni DXF prodotto dichiarava di essere nato lo stesso giorno di tutti gli
altri. Ora è il giorno giuliano del momento in cui il file viene scritto.

### Il controllo del DXF ora guarda anche i numeri

`verifica_dxf` confrontava le entità scritte con quelle rilette da GDAL. È un
buon secondo parere, ma **cieco su una famiglia di difetti**: GDAL rilegge
fedelmente anche un numero impreciso, quindi conferma. Il nuovo controllo
guarda il numero scritto e segnala gli archi le cui cifre non bastano per la
loro corda, con soglia a un decimo di millimetro sul terreno.

Sul file prodotto prima della correzione trova **1 609 archi imprecisi**, il
peggiore a 6,15 mm; su quello di adesso, zero.

## 1.2.9.1 — 25 agosto 2026 — sperimentale

### Nel DXF, `Base` e `Bottom` erano scambiati

Il gruppo 73 di un testo DXF vale, secondo la specifica: `0` = Baseline,
`1` = Bottom, `2` = Middle, `3` = Top. Il traduttore mappava `Base` su `1` e
`Bottom` su `0`: ogni scritta ancorata a quei due valori usciva spostata in
verticale della profondità dei discendenti del carattere. Sul comune di prova
sono **97 525 iscrizioni su 135 980**, il 71,7 %.

**Due lettori indipendenti non sono d'accordo su quei due codici.** Scritto un
DXF con gruppo 73 = 0, 1, 2, 3 e riletto:

| gruppo 73 | ezdxf 1.4.4 | GDAL |
|---|---|---|
| 0 | **BASELINE** | bottom |
| 1 | **BOTTOM** | baseline |
| 2 | MIDDLE | middle |
| 3 | TOP | top |

Su 2 e 3 concordano. Si segue la specifica, cioè ezdxf.

Ed è il motivo per cui il difetto non era mai emerso: il controllo del plugin
rilegge il DXF **con GDAL**, che scambia esattamente gli stessi due codici. I
due errori si annullavano e il secondo parere confermava il primo.

La correzione è stata verificata **sul binario**: stesso ITF convertito con il
traduttore vecchio e con quello nuovo, confronto riga per riga di 2 833 520
righe. Differenze: 6 048 sul solo gruppo 73, più la riga del watermark che
cambia a ogni esecuzione. Nient'altro si è mosso.

> **Da guardare in un CAD.** ezdxf dice cosa dice la specifica; solo AutoCAD o
> BricsCAD dicono cosa fa il programma con cui si lavora davvero. Se si
> comportassero come GDAL, questa correzione andrebbe rifatta al contrario.

### Il DXF non può più sovrascrivere il file da cui nasce

Il traduttore apre il file di destinazione troncandolo. Se il campo DXF
puntasse all'ITF — un percorso incollato male, una scelta sbagliata nel
dialogo — la conversione cancellerebbe il dato di consegna del Cantone e poi
fallirebbe, perché non avrebbe più niente da leggere. Ora la conversione si
ferma prima di partire se il DXF coincide con l'ITF, con il modello `.ili` o
con il traduttore stesso, confrontando i percorsi risolti.

## 1.2.9 — 25 agosto 2026 — sperimentale

Gli ultimi cinque difetti segnalati dalla valutazione esterna. Con questa
versione **tutti e otto sono chiusi**.

### Due iscrizioni obbligatorie potevano dire il falso

Sono le uniche due che finiscono *stampate* sul foglio, e per questo vengono
prima delle altre.

**Il cenno sugli spostamenti permanenti di terreno** (cap. 1.5.7) si decideva
cercando la parola «movimento» nel nome del layer. Dimostrato prima di
correggere: un layer qualunque chiamato «movimento terra», aggiunto al
progetto da chiunque, faceva scrivere sul cartiglio che gli spostamenti erano
rappresentati. Ora si guarda il nome della **tabella** — topic
`Zone_di_movimento`, classe `Movimento` — escludendo `PosMovimento`, che è il
punto di iscrizione dell'etichetta: contarlo vorrebbe dire dichiarare
rappresentate delle scritte.

**Il fattore di proporzionalità dopo un cambio scala nel compositore**
(cap. 1.5.2): il cartiglio veniva riscritto con la scala nuova e dichiarava il
fattore nuovo, mentre i layer disegnavano ancora con quello vecchio — due
iscrizioni obbligatorie in contraddizione sullo stesso foglio. Ora la scala di
riferimento si rimette sui cloni che il foglio già usa, senza rifare niente.
Dove non si può, resta l'avviso.

### Un file INTERLIS 2 passava come «non verificabile»

Il controllo del modello cercava solo la riga `MODL` dell'INTERLIS 1: davanti a
un `.xtf` federale rispondeva «non posso verificare» — un avviso, non un
blocco. Ma quel formato questa catena non lo importa affatto. Ora si riconosce
dal contenuto (un `.xtf` rinominato `.itf` non inganna) e si blocca.

### Un DXF senza tabella LAYER passava in silenzio

«Nessun layer dichiarato» veniva trattato come «niente da confrontare», ed era
invece il caso peggiore: colore, spessore e tipo di linea di *ogni* entità li
deciderebbe chi apre il file.

### Un GeoPackage corrotto poteva far cadere il programma

Il numero di punti di un poligono è un valore **letto dal file**: in un blob
rotto vale qualunque cosa, e la lettura veniva preparata prima di verificare
quanti byte restassero. Il risultato non era un errore di lettura ma un
`MemoryError`, cioè un guasto che sembra del programma invece che del dato.

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
