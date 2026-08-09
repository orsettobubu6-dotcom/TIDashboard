# Componenti di terze parti

> ⚠️ **Prima di pubblicare il repository** (https://github.com/orsettobubu6-dotcom/TIDashboard)
> restano da chiarire due punti segnati qui sotto: le licenze delle 15 librerie
> Java in dotazione e i diritti di **ridistribuzione** di font e simboli
> Cadastra, che sono materiale swisstopo / cadastre.ch. «Scaricabile dal sito
> del catasto» non equivale a «ridistribuibile in un repository pubblico».
> Il repository e il remoto sono già configurati ma **non è stato fatto alcun
> push**: nulla di tutto ciò è ancora online.

Il pacchetto distribuisce i componenti elencati qui sotto. Le rispettive licenze
restano quelle originali e vanno rispettate anche ridistribuendo TIDashboard.

## av2geobau (versione adattata)

`av2geobau/av2geobau_ti.jar` è una versione modificata di
[av2geobau](https://github.com/claeis/av2geobau) di Claude Eisenhut, rilasciato
sotto **LGPL 2.1**.

Modifiche: lettura diretta del modello MD01MUTI7MN95 (l'originale passa da una
traduzione verso il modello tedesco, che fallisce per le divergenze strutturali
reali), mappature aggiuntive di simboli e testi, scrittura di tratteggi e
retini nativi.

La LGPL comporta alcuni obblighi per chi ridistribuisce, fra cui rendere
disponibile il sorgente della libreria modificata e non impedire il reverse
engineering per il debug delle modifiche. Il sorgente ricostruito si trova in
`av2geobau_src/` nel repository del progetto.

## Librerie Java in `av2geobau/libs/`

Quindici jar, distribuiti insieme al traduttore perché il suo MANIFEST vi fa
riferimento. Provengono dalla catena INTERLIS e dall'ecosistema Java:

| libreria | origine |
|---|---|
| `ili2c-core`, `ili2c-tool` | compilatore INTERLIS |
| `iox-api`, `iox-ili`, `ehibasics` | lettura/scrittura INTERLIS |
| `jts-core` | JTS Topology Suite |
| `antlr` | generatore di parser |
| `jaxb-api`, `jaxb-core`, `jaxb-impl`, `activation`, `javax.activation-api` | binding XML |
| `slf4j-api`, `slf4j-simple` | logging |
| `base64` | codifica |

**Da verificare prima della pubblicazione:** le licenze esatte di ciascuna
(prevalentemente LGPL, Apache 2.0, EPL/EDL e BSD) e i relativi obblighi di
attribuzione.

## Font e simboli

- `fonts/` — sei file del tipo di scrittura **Cadastra**, prescritto dal cap. 5.3
  delle istruzioni federali per tutte le scritture del piano. Il documento lo
  indica come lista open source basata su Bitstream, scaricabile dal sito del
  catasto.
- `symbols/` — 117 file SVG dei simboli Cadastra.

**Da verificare prima della pubblicazione:** i diritti di ridistribuzione di
font e simboli, che sono materiale swisstopo / cadastre.ch.

## Modello dei dati

`models/MD01MUTI7MN95.ili` — modello dei dati della misurazione ufficiale,
versione del Canton Ticino. Editore: Ufficio federale di topografia swisstopo,
Direzione federale delle misurazioni catastali; Sezione bonifiche fondiarie e
catasto, Ufficio misurazioni catastali.

## Norme di riferimento

Non distribuite col plugin, ma alla base della simbologia implementata:

- Circolare 154, allegato 2 — *Rappresentazione del «Piano per il registro
  fondiario»*, versione marzo 2007
- Circolare 154, allegato 4 — generi di linea del modello cantonale
- Circolare 202, allegato 2 — settembre 2012, che aggiorna l'allegato 4
- *Rappresentazione del piano di base della misurazione ufficiale «PB-MU»* e
  relativa legenda
