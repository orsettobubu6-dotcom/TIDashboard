# Norme di riferimento

Documenti su cui è costruita la rappresentazione del plugin. Tutti gli
indirizzi sono stati **aperti e verificati**; dove il documento ha una data o
uno stato, sono riportati, perché è l'informazione che serve per sapere se
quello che stiamo implementando è ancora quello in vigore.

## Federali

| Risorsa | Indirizzo | Verificato |
|---|---|---|
| Atti normativi della misurazione ufficiale | <https://www.cadastre-manual.admin.ch/it/atti-normativi-della-misurazione-ufficiale> | raccolta swisstopo, pubblicata 1.7.2024 |
| Piano per il registro fondiario (manuale) | <https://www.cadastre-manual.admin.ch/it/piano-per-il-registro-fondiario> | |
| **Istruzione — Rappresentazione del «Piano per il registro fondiario»** (PDF) | <https://www.cadastre-manual.admin.ch/dam/it/sd-web/pysw2JgMIIer/Weisung-GB-it.pdf> | «del 9 marzo 2007 (**Stato 1° febbraio 2014**)» — 26 pagine |
| **Rappresentazione del piano di base della misurazione ufficiale PB-MU** (PDF) | <https://www.cadastre-manual.admin.ch/dam/it/sd-web/Zi4MHUCeFgtz/Weisung-BP-AV-it.pdf> | marzo 2022 |
| Legenda (indirizzo citato nel cartiglio, cap. 1.5.7) | <https://www.cadastre.ch/legende> | |
| ORF — Ordinanza sul registro fondiario | <https://www.fedlex.admin.ch/eli/cc/2011/667/it> | RS 211.432.1, del 23.9.2011, in vigore (stato 1.1.2024) |

## Cantonali (Ticino, UCR)

| Risorsa | Indirizzo | Verificato |
|---|---|---|
| Direttive UCR (elenco delle circolari) | <https://www4.ti.ch/dfe/de/ucr/documentazione/direttive> | |
| Circ. 154, allegato 2 — istruzioni federali | <https://m4.ti.ch/fileadmin/DFE/DE-UCR/circolari/circ154_allegato2.pdf> | «**Versione marzo 2007**», 24 pagine |
| Circ. 154, allegato 4 — complemento cantonale | <https://www4.ti.ch/fileadmin/DFE/DE-UCR/circolari/circ154_allegato4.pdf> | |
| **Circ. 202 — annulla e sostituisce la 154** | <https://www4.ti.ch/fileadmin/DFE/DE-UCR/circolari/Circ202.pdf> | 27.9.2012; istruzioni federali versione agosto 2012, in vigore dall'1.9.2012 |
| Circ. 202 allegato 2 — complemento cantonale | <https://www4.ti.ch/fileadmin/DFE/DE-UCR/circolari/Circ202_Allegato2_.pdf> | «Versione settembre 2012»; sostituisce l'allegato 4 della 154 |
| **Circ. 210 — aggiornamento delle istruzioni federali** | <https://www4.ti.ch/fileadmin/DFE/DE-UCR/circolari/Circ210.pdf> | 17.2.2014; allegato = circolare federale MO 2014/01 |
| Dati della misurazione ufficiale TI (ITF) | <https://data.geo.ti.ch/?p=ti_mu_version1_7_mn95> | scaricare in **INTERLIS 1** |

---

## ⚠️ La circolare 154 è annullata dal 2012

Il codice cita ovunque `circ154_allegato2`, che è la **versione marzo 2007**.
Quella circolare non è più in vigore: la **circolare 202** del 27 settembre
2012 dice testualmente «*Questa circolare annulla e sostituisce la circolare
154 del 30 maggio 2007 e, di conseguenza, le istruzioni federali e cantonali
del 2007 sono sostituite dalle nuove istruzioni in oggetto*», con termine di
attuazione **1° gennaio 2013**. Anche l'allegato 4 (complemento cantonale) è
sostituito, dal complemento «versione settembre 2012».

La versione federale in vigore è **del 9 marzo 2007, stato 1° febbraio 2014**,
scaricabile da cadastre-manual (`Weisung-GB-it.pdf`). Fra il 2007 e oggi ci
sono quindi **due** passaggi: agosto 2012 (circ. 202: piano a colori e zone di
spostamento permanente di terreno, entrambi opzionali per la Confederazione ma
le zone **obbligatorie** in Ticino) e 1° febbraio 2014 (circ. 210).

Il confronto dei **tipi di tratto** del complemento cantonale 2012 con quanto
implementato non ha mostrato differenze: facciata_aperta → interrotto2,
parte_interrata → punteggiato, sentiero → interrotto1 e gli altri corrispondono.

La modifica è dichiarata dalla circolare federale MO **2014/01** del 28 gennaio
2014, trasmessa in Ticino con la **circolare 210**:

> «Chapitre 1.5.4, Priorités — Les signes conventionnels surfaciques de la
> couche "objets divers" ont été déplacés en avant-dernière position de la
> table.»

Confrontate le due tabelle del cap. 1.5.4, la coda è cambiata così:

| | **marzo 2007** (usata dal plugin) | **stato 1.2.2014** (in vigore) |
|---|---|---|
| | Oggetti singoli: 1. puntuali, 2. lineari, **3. con simboli associati a superfici** | Oggetti singoli: 1. segni dei punti, 2. segni delle linee |
| | Copertura del suolo: 1. senza trama, 2. con trama | Copertura del suolo: oggetti lineari |
| | Condotte: 1. gestore, 2. puntuali, 3. lineari, **4. con simboli associati a superfici** | Condotte: 1. gestore, 2. puntuali, 3. lineari |
| | Margine di piano: croce della rete | Ripartizione dei piani: geometria del confine |
| | | Copertura del suolo: segni di superficie tipo **«Edificio»** (griglia) |
| | | **Oggetti singoli: segni delle superfici** ← penultima |
| | | Copertura del suolo: segni di superficie **altri tipi** (griglia) ← ultima |

## L'ordine di disegno è stato allineato

`GEOS_ZORDER_SEQUENCE` in `ordinamento.py` **segue ora la tabella in vigore**
(stato 1.2.2014). Prima non seguiva nemmeno quella del 2007: era derivata
dall'export della legenda di **GEOS Pro**, e metteva condotte e copertura del
suolo *sopra* gli oggetti singoli, mentre entrambe le versioni della norma li
vogliono sotto. L'allineamento corregge quindi due cose insieme.

Sui dati reali di Chiasso, **56 layer su 121** cambiano posizione. I movimenti
principali:

| layer | prima | dopo |
|---|---|---|
| croce della rete | 52 | **0** |
| zone di franamento | 57 | 22 |
| oggetti singoli: punti | 29 | 23 |
| oggetti singoli: linee | 32 | 25 |
| condotte (4 layer) | 21-24 | 28-31 |
| ripartizione dei piani | — | 28ª voce, sopra i segni di superficie |
| oggetti singoli: superfici | — | penultima |
| copertura del suolo | — | ultima |

**Un punto della tabella non è riproducibile.** La versione in vigore divide i
segni di superficie della copertura del suolo in *due* posizioni — la griglia
del tipo «Edificio» sopra i segni di superficie degli oggetti singoli, gli
altri tipi sotto. Gli edifici però sono regole dentro lo stesso layer
poligonale della copertura del suolo, e **un layer QGIS occupa una sola
posizione z**: separarli richiederebbe di spezzare il layer in due. Per ora
tutta la copertura del suolo sta nell'ultima posizione.

## Rilettura capitolo per capitolo dell'istruzione in vigore

| Capitolo | Esito |
|---|---|
| 1.4 Leggenda | ✔ `www.cadastre.ch/legende`, «presente su ogni estratto» — implementato |
| 1.5.1 Scale | ✔ le otto scale coincidono |
| 1.5.2 Fattore di proporzionalità | ✔ testo identico al 2007 |
| 1.5.3 Contenuto del piano | ⚠ l'elenco dei temi non rappresentati è cambiato: 2007 «Altimetria, Perimetro_numerazione, Ripartizione_piani, RipartizioneGT, Zone_di_movimento»; oggi «Altezza, Aree di numerazione, Ripartizione del piano, TSRipartizione», e le zone di spostamento diventano **rappresentabili** |
| 1.5.4 Priorità | ✔ **allineato** (vedi sopra) |
| 1.5.5 Simboli | ✔ i quattro tipi coincidono |
| 1.5.6 Colore | ⚠ il 2007 diceva «esclusivamente il colore nero»; oggi il colore è ammesso e descritto al cap. 6 |
| **1.5.7 Iscrizioni** | ✖ **erano sette, ora sono NOVE** — corretto, vedi sotto |
| 1.5.8 Zone di spostamento | ⚠ bandatura di 10 mm all'interno del perimetro + menzione aggiuntiva: **non implementato** |
| 5.12 Indirizzo degli edifici | da riverificare: nome_localizzazione 3.0 corsivo, numero_casa 1.8, Nome_edificio 1.8, Nome_località 4.5 grassetto |
| **6 Piano RF a colori** | ✖ capitolo **interamente nuovo**, non implementato |
| 7 Allegati | esempi, non prescrittivi |

### 1.5.7: mancavano due iscrizioni obbligatorie

Nel commit precedente avevo scritto che il cap. 1.5.7 era «invariato fra le due
versioni». **Era sbagliato.** La versione marzo 2007 elenca sette iscrizioni,
quella in vigore ne elenca **nove**: si aggiungono

- «Il cenno relativo alla rappresentazione di oggetti in progetto»
- «Il cenno relativo alla rappresentazione di territori di spostamento
  permanente di terreno»

Entrambe sono ora nel cartiglio, e dicono il vero: gli oggetti in progetto il
plugin non li rappresenta mai (regola del cap. 1.5.3), mentre il cenno sugli
spostamenti si decide guardando i layer del foglio. `H_CARTIGLIO` è passato da
32 a 40 mm per farci stare le due righe in più.

L'esempio dell'istruzione etichetta la data come «Allestimento»; il cartiglio
continua a scrivere **«Stato al»**, perché l'iscrizione obbligatoria è «una data
di validità» e la data che scriviamo è quella dei *dati*, non quella in cui il
foglio è stato prodotto — «Allestimento» sarebbe una data diversa.

### Il capitolo 6 è un terzo prodotto

«Piano per il registro fondiario **a colori**»: si allestisce sul piano RF in
bianco e nero più le integrazioni a colori del PB-MU, e colora **soltanto** i
segni di superficie di edificio, rivestimento duro, corsi d'acqua e superfici
boscate, più gli edifici sotterranei. Tutto il resto resta come nel bianco e
nero. È **opzionale**.

Il plugin oggi ha due prodotti — RF in bianco e nero e PB-MU a colori — e non
questo. Non è un difetto: è una funzione in più, con colori propri (edificio
rosa CMYK 0,25,25,0 = RGB 255,191,191; edificio sotterraneo e cisterna
0,41,41,0 = 255,150,150) che **non vanno confusi** con quelli del PB-MU.

---

## Diritto di emissione: chi può fare cosa

Questo è il motivo per cui ogni foglio prodotto dal plugin porta in rosso la
dicitura «Riproduzione senza valore legale».

| Concetto | Implicazione |
|---|---|
| Il piano per il registro fondiario **come estratto ufficiale** | È emesso secondo le regole del registro fondiario, dall'autorità competente o dal geometra revisore nel quadro legale |
| Una **riproduzione da dati ITF in QGIS** | È tecnicamente utile, ma non acquista un «valore legale» per il fatto di essere conforme nella grafica |
| **ORF** (RS 211.432.1) | Collega registro fondiario e dati della misurazione ufficiale: il piano è un estratto conforme alle regole di rappresentazione |

In pratica: la conformità grafica che questo plugin persegue è una condizione
**necessaria** e non **sufficiente**. Un foglio può essere disegnato
esattamente secondo l'istruzione e non essere un estratto ufficiale, perché
manca l'atto di emissione da parte di chi ne ha la competenza. Per questo la
dicitura è fissa, in rosso, e non disattivabile.
