# Componenti di terze parti

> ⚠️ **Il progetto è pubblicato** su
> <https://github.com/orsettobubu6-dotcom/TIDashboard>, font e simboli
> compresi. Resta aperto **un** punto: i diritti di **ridistribuzione** di font
> e simboli Cadastra, che sono materiale swisstopo / cadastre.ch. Le istruzioni
> federali li dicono scaricabili dal sito del catasto, ma «scaricabile» non
> equivale a «ridistribuibile in un repository pubblico».
>
> Le licenze delle librerie Java sono invece **accertate**, tranne tre su
> quindici: vedi la tabella sotto.

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

| libreria | uso | licenza | accertata |
|---|---|---|---|
| `ili2c-core` 5.6.8 | compilatore INTERLIS | **LGPL** | README del progetto |
| `ili2c-tool` 5.6.8 | compilatore INTERLIS | **LGPL** | come sopra, stesso progetto |
| `iox-ili` 1.24.4 | lettura/scrittura INTERLIS | **MIT/X** | README del progetto |
| `iox-api` 1.0.3 | interfacce di iox | *da confermare* | né nel jar né nel README |
| `ehibasics` 1.4.1 | utilità di base | *da confermare* | né nel jar né nel README |
| `jts-core` 1.14.0 | JTS Topology Suite | **LGPL 2.1** | dichiarata nel `pom.xml` dentro il jar |
| `antlr` 2.7.7 | generatore di parser | **pubblico dominio** | antlr2.org/license.html |
| `jaxb-api` 2.3.1 | binding XML | **CDDL 1.1** | `META-INF/LICENSE.txt` nel jar |
| `jaxb-impl` 2.3.2 | binding XML | **BSD 3 clausole** (Oracle 2018) | `META-INF/LICENSE.md` nel jar |
| `jaxb-core` 2.3.0.1 | binding XML | *da confermare* | il jar non la dichiara |
| `activation` 1.1.1 | tipi MIME | **CDDL 1.0** | `META-INF/LICENSE.txt` nel jar |
| `javax.activation-api` 1.2.0 | tipi MIME | **CDDL 1.1** | `META-INF/LICENSE.txt` nel jar |
| `slf4j-api` 1.7.25 | logging | **MIT** | slf4j.org/license.html |
| `slf4j-simple` 1.7.25 | logging | **MIT** | come sopra, stesso progetto |
| `base64` 2.3.9 | codifica | **pubblico dominio** | dichiarata nel `pom.xml` dentro il jar |

Le licenze sono state ricavate **dai jar stessi** — file `META-INF/LICENSE*` e
`pom.xml` incorporato — e, dove il jar non dice nulla, dalla pagina ufficiale
del progetto. Non sono state dedotte dal nome della libreria.

Nessuna delle licenze accertate è incompatibile con la GPL 2 o successiva del
plugin: LGPL, MIT, BSD e pubblico dominio si possono ridistribuire in un
pacchetto GPL rispettando l'attribuzione. Il CDDL è la sola nota di attenzione —
è una licenza per file, storicamente considerata di dubbia compatibilità con la
GPL quando i due codici sono *collegati*; qui però i jar `jaxb-*` e
`activation` non sono collegati al plugin: sono eseguiti da Java in un processo
separato, avviato dal plugin come programma esterno.

**Restano tre da confermare** (`iox-api`, `ehibasics`, `jaxb-core`): il jar non
le dichiara e la pagina del progetto non le espone. Le prime due vengono dallo
stesso autore di `iox-ili` (MIT/X) e `ili2c` (LGPL), la terza dallo stesso
gruppo di `jaxb-api` (CDDL 1.1), quindi è probabile che seguano quelle — ma
finché non è verificato resta scritto che non lo è.

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
