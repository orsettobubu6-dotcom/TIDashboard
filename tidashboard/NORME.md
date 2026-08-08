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
| Circ. 202 — commenti cantonali, agosto 2012 | <https://www4.ti.ch/fileadmin/DFE/DE-UCR/circolari/Circ202.pdf> | |
| **Circ. 210 — aggiornamento delle istruzioni federali** | <https://www4.ti.ch/fileadmin/DFE/DE-UCR/circolari/Circ210.pdf> | 17.2.2014; allegato = circolare federale MO 2014/01 |
| Dati della misurazione ufficiale TI (ITF) | <https://data.geo.ti.ch/?p=ti_mu_version1_7_mn95> | scaricare in **INTERLIS 1** |

---

## ⚠️ La versione su cui è costruito il plugin non è l'ultima

Il codice cita ovunque `circ154_allegato2`, che è la **versione marzo 2007**.
L'istruzione federale corrispondente è però stata aggiornata: la versione in
vigore è **del 9 marzo 2007, stato 1° febbraio 2014**, ed è quella scaricabile
da cadastre-manual (`Weisung-GB-it.pdf`).

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

Ne discendono differenze concrete rispetto a `GEOS_ZORDER_SEQUENCE` in
`ordinamento.py`:

1. la **ripartizione dei piani** è quasi in fondo da noi, mentre la versione in
   vigore la mette *sopra* i segni di superficie della copertura del suolo;
2. la copertura del suolo è per noi **un solo livello**, mentre la versione in
   vigore la **divide in due** — la griglia degli edifici sopra i segni di
   superficie degli oggetti singoli, gli altri tipi sotto;
3. gli oggetti singoli con superficie e le condotte con superficie non
   compaiono più dove li abbiamo messi.

**Non è ancora stato deciso se allineare l'ordine di disegno alla versione in
vigore**: è una modifica che cambia il disegno prodotto, non una correzione
ovvia. Fino ad allora il plugin segue la versione marzo 2007, ed è questo che
va detto a chi chiede su quale norma si basa.

Il cap. 1.5.7 (iscrizioni obbligatorie) è invece **invariato** fra le due
versioni: le sette iscrizioni implementate nel cartiglio restano quelle giuste.

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
