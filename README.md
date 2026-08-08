# TIDashboard

Plugin QGIS per i dati della **misurazione ufficiale svizzera**, modello ticinese
`MD01MUTI7MN95`. Importa un file INTERLIS/ITF, applica la simbologia prescritta
dalle istruzioni federali e produce planimetrie stampabili e file DXF.

> **Sperimentale.** La conformità alla norma è stata verificata sul testo delle
> istruzioni, **non** con un confronto affiancato a un estratto ufficiale né con
> una validazione dell'autorità competente. Ogni foglio prodotto riporta la
> dicitura «Riproduzione senza valore legale».

## Cosa c'è qui

| | |
|---|---|
| `tidashboard/` | il plugin QGIS — è la cartella che si installa |
| `av2geobau_src/` | sorgente Java del traduttore DXF, versione adattata al modello ticinese (LGPL 2.1) |
| `crea_zip_plugin.py` | costruisce lo ZIP installabile e lo verifica |

## Installazione

Serve **QGIS 4.0** o superiore e **Java 8** o superiore installato a parte.

Costruire lo ZIP e installarlo da QGIS:

```bash
python crea_zip_plugin.py
```

poi in QGIS: *Estensioni → Gestisci ed installa estensioni → Installa da ZIP*.
Essendo marcato sperimentale, va prima attivata l'opzione *Mostra anche le
estensioni sperimentali*.

## Documentazione

- **[tidashboard/README.md](tidashboard/README.md)** — cosa fa, come si usa, limiti noti
- **[tidashboard/NORME.md](tidashboard/NORME.md)** — documenti normativi di riferimento, con indirizzi verificati e **su quale versione** è costruita la rappresentazione
- **[tidashboard/CREDITI.md](tidashboard/CREDITI.md)** — componenti di terze parti e relative licenze
- **[tidashboard/CHANGELOG.md](tidashboard/CHANGELOG.md)**

## Prova

I test si eseguono con l'interprete Python di QGIS, non con uno generico:

```bash
cd tidashboard && python test_planimetria.py
```

Quattro suite: `test_planimetria`, `test_style_logic`, `test_dialog_ui`,
`test_dati_comune`.

## Licenza

**GPL-2.0-or-later** — vedi [tidashboard/LICENSE](tidashboard/LICENSE). È la
convenzione dei plugin QGIS ed è compatibile con i componenti LGPL 2.1
distribuiti insieme.
