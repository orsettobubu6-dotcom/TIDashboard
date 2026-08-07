# av2geobau_ti - sorgente

Fork ticinese di [av2geobau](https://github.com/claeis/av2geobau): esporta DXF
direttamente dal modello cantonale MD01MUTI7MN95, senza la "TRANSLATION OF"
verso il modello tedesco usata dal jar ufficiale.

## Da dove viene questo sorgente

L'albero originale viveva in una cartella temporanea (`%TEMP%\claude\av2geobau_src2`)
ed **è andato perso** quando quella cartella è stata ripulita: restava solo il jar
compilato. Il 2026-08-03 il sorgente è stato **recuperato decompilando
`av2geobau_ti.jar`** con CFR 0.152 e correggendo a mano gli artefatti di
decompilazione.

Per questo il codice qui **non ha i commenti originali**: la compilazione li
scarta e nessun decompilatore può recuperarli. La logica invece è integrale e
verificata (vedi sotto). I commenti si possono riaggiungere nel tempo, man mano
che si rimette mano ai singoli punti.

**Questa cartella è dentro il progetto, non più in `%TEMP%`: non va spostata lì.**

## Verifica del recupero

Il jar ricompilato da questo sorgente è stato confrontato con quello originale
convertendo lo stesso file ITF reale (`5254010100.itf`, 209 MB di DXF,
33'448'292 righe): **output byte-identico**, stesso SHA-256, escludendo solo la
riga `Impronta_Sicurezza:` del watermark, che contiene un timestamp e cambia a
ogni esecuzione per definizione.

## Correzioni applicate agli artefatti di decompilazione

CFR non ricostruisce tutto in modo compilabile. Interventi, tutti verificati:

- **`DxfUtil.toString(int, Object)` - ricorsione infinita (il più insidioso).**
  CFR aveva perso l'unboxing esplicito: `toString(n, (Integer)object)` invece di
  `toString(n, ((Integer)object).intValue())`. Con un `Integer` la risoluzione
  degli overload sceglie `toString(int, Object)`, cioè lo stesso metodo →
  `StackOverflowError`. Confermato disassemblando il bytecode originale
  (`Integer.intValue()` + `invokestatic toString:(II)`). Stesso trattamento per
  il ramo `Double`.
- **Indici di ciclo non tipizzati**: 3 `void varN;` (for-each degenerati) →
  indici `int` inizializzati a 0.
- **Generici persi nell'erasure**: `LinkedHashMap` e `Map.Entry` resi raw,
  `ArrayList<Object>` al posto di `ArrayList<Coordinate>`/`ArrayList<CurveSegment>`,
  bucket di `reorderEntitiesForDrawOrder` tipizzati `Serializable`.
- **Slot locali riusati da CFR per tipi diversi**: `polygon`/`coordinate` che in
  realtà contenevano l'`IomObject` di riferimento, `string3` riusato per una
  `Configuration` ili2c, `iomObject2` per una `LineString`, writer/file
  temporaneo nella coda di `reorderEntitiesForDrawOrder`. Risolti dando
  variabili proprie e correttamente tipizzate.
- **84 cast** `((IomObject)object)` sulle chiamate `setattrvalue`/`addattrobj`.
- Aggiunto l'import mancante `com.vividsolutions.jts.geom.LineString`.

Nota: `DxfUtil.java` è stato recuperato per la prima volta qui. Prima mancava del
tutto e si compilava con un workaround di classpath che puntava a una vecchia
cartella di build.

## Ricompilare e installare

```bash
./build.sh
```

Compila `src/`, sovrappone le classi al jar base (che contiene anche le classi
del modello `ch/interlis/models/**`, non presenti in `src/` e non da
ricompilare) e installa il jar nelle 4 posizioni del progetto.
