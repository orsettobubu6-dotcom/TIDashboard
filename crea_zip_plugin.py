"""Costruisce lo zip installabile del plugin QGIS e lo verifica.

Eseguire con l'interprete di QGIS:
    & "C:\\Program Files\\QGIS 4.2.0\\bin\\python-qgis.bat" crea_zip_plugin.py

QGIS pretende una sola cartella di primo livello col nome del plugin, dentro
cui stanno metadata.txt e __init__.py. Il numero di versione viene letto da
metadata.txt, cosi' il nome del file non puo' divergere dal contenuto.
"""
import hashlib
import os
import zipfile

QUI = os.path.dirname(os.path.abspath(__file__))
NOME = "tidashboard"
SRC = os.path.join(QUI, NOME)

# __pycache__ e i .bak non vanno distribuiti: il primo puo' far girare a QGIS
# bytecode obsoleto, il secondo e' solo peso morto.
ESCLUDI_DIR = {"__pycache__", ".git"}
ESCLUDI_EST = {".bak", ".pyc", ".pyo"}

versione = "0.0.0"
with open(os.path.join(SRC, "metadata.txt"), encoding="utf-8") as f:
    for riga in f:
        if riga.startswith("version="):
            versione = riga.split("=", 1)[1].strip()
ZIP = os.path.join(QUI, "%s_%s.zip" % (NOME, versione))

if os.path.exists(ZIP):
    os.remove(ZIP)

n_file = 0
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for radice, cartelle, file in os.walk(SRC):
        cartelle[:] = [c for c in cartelle if c not in ESCLUDI_DIR]
        for nome_file in sorted(file):
            if os.path.splitext(nome_file)[1].lower() in ESCLUDI_EST:
                continue
            assoluto = os.path.join(radice, nome_file)
            z.write(assoluto, os.path.join(NOME, os.path.relpath(assoluto, SRC)))
            n_file += 1

print("creato: %s" % ZIP)
print("file inclusi: %d   dimensione: %.2f MB" % (n_file, os.path.getsize(ZIP) / 1048576.0))

esito = True
with zipfile.ZipFile(ZIP) as z:
    nomi = z.namelist()
    corrotto = z.testzip()
    radici = {n.split("/")[0] for n in nomi}
    print("\nintegrita' archivio       :", "OK" if corrotto is None else "CORROTTO: %s" % corrotto)
    print("cartella di primo livello :", radici)
    esito = esito and corrotto is None and radici == {NOME}

    attesi = ["metadata.txt", "__init__.py", "tidashboard.py", "planimetria.py",
              "dati_comune.py", "legend_manifest.py",
              # moduli nati dallo spacchettamento di tidashboard.py: se uno
              # sparisse dallo zip il plugin non si caricherebbe affatto
              "colori.py", "etichette.py", "ordinamento.py", "simbologia.py",
              "stili.py",
              # documenti richiesti per la pubblicazione
              "icon.png", "README.md", "CHANGELOG.md", "CREDITI.md",
              "av2geobau/av2geobau_ti.jar", "models/MD01MUTI7MN95.ili"]
    for rel in attesi:
        voce = "%s/%s" % (NOME, rel)
        ok = voce in nomi
        esito = esito and ok
        print("  %-42s %s" % (rel, "presente" if ok else "MANCANTE <--"))

    resti = [n for n in nomi if "__pycache__" in n or n.endswith(".bak")]
    print("residui indesiderati      :", resti if resti else "nessuno")
    esito = esito and not resti

    with z.open("%s/av2geobau/av2geobau_ti.jar" % NOME) as fz:
        md5_zip = hashlib.md5(fz.read()).hexdigest()
    with open(os.path.join(SRC, "av2geobau", "av2geobau_ti.jar"), "rb") as fs:
        md5_src = hashlib.md5(fs.read()).hexdigest()
    print("jar nello zip = jar corrente:", "SI" if md5_zip == md5_src else "NO <--")
    esito = esito and md5_zip == md5_src

    print("librerie java: %d   font: %d   simboli SVG: %d"
          % (len([n for n in nomi if "/av2geobau/libs/" in n]),
             len([n for n in nomi if "/fonts/" in n]),
             len([n for n in nomi if "/symbols/" in n])))

# plugins.qgis.org rifiuta il caricamento se manca uno di questi campi: senza
# questo controllo lo si scopre solo al momento della pubblicazione.
OBBLIGATORI = ("name", "qgisMinimumVersion", "description", "about", "version",
               "author", "email", "repository", "tracker")
campi = {}
with open(os.path.join(SRC, "metadata.txt"), encoding="utf-8") as f:
    for riga in f:
        if "=" in riga and not riga.startswith("["):
            chiave, valore = riga.split("=", 1)
            campi[chiave.strip()] = valore.strip()
print("\ncampi obbligatori metadata.txt:")
for c in OBBLIGATORI:
    v = campi.get(c, "")
    stato = "ASSENTE <--" if not v else ("DA COMPILARE <--" if "DA-COMPILARE" in v else "ok")
    if stato != "ok":
        esito = False
    print("  %-20s %s" % (c, stato))
print("  %-20s %s" % ("experimental", campi.get("experimental", "?")))

print("\nESITO:", "PACCHETTO VALIDO" if esito else "ANOMALIE PRESENTI")
