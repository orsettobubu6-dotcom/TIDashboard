# Diario delle versioni

## 1.2.0 — sperimentale

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

### Scala di stampa

- La scala del layout del piano di base non è più fissata a 1:5000 nel codice:
  la decide il menu «Scala», come già per la planimetria RF. Prima chi ne
  sceglieva un'altra otteneva comunque un foglio 1:5000, con sopra stampato
  «Scala: 1:5000». Passando a PB-MU il menu si porta su 1:5000 solo se
  l'utente non ha già scelto.

### Correzioni

- Chiudere la finestra mentre una conversione era in corso poteva sollevare
  «wrapped C/C++ object of type JavaWorker has been deleted».

## 1.1.1 — sperimentale

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
