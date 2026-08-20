"""Costruisce lo zip installabile del plugin QGIS e lo verifica.

Eseguire con l'interprete di QGIS:
    & "C:\\Program Files\\QGIS 4.2.0\\bin\\python-qgis.bat" crea_zip_plugin.py

QGIS pretende una sola cartella di primo livello col nome del plugin, dentro
cui stanno metadata.txt e __init__.py. Il numero di versione viene letto da
metadata.txt, cosi' il nome del file non puo' divergere dal contenuto.
"""
import hashlib
import os
import stat
import sys
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
# I pacchetti stanno in dist/, non sparsi nella radice del repository: e' la
# cartella che la CI carica come artefatto.
DIST = os.path.join(QUI, "dist")
ZIP = os.path.join(DIST, "%s_%s.zip" % (NOME, versione))

# Data fissa delle voci dello zip: vedi la nota sulla riproducibilita' in
# testa al file. Il 1980 e' il minimo che il formato ZIP sappia scrivere.
DATA_FISSA = (1980, 1, 1, 0, 0, 0)

# plugins.qgis.org rifiuta il caricamento se manca uno di questi campi: senza
# questo controllo lo si scopre solo al momento della pubblicazione.
OBBLIGATORI = ("name", "qgisMinimumVersion", "description", "about", "version",
               "author", "email", "repository", "tracker")


def controlla_metadata():
    """I campi che plugins.qgis.org pretende. Ritorna True se ci sono tutti."""
    campi = {}
    with open(os.path.join(SRC, "metadata.txt"), encoding="utf-8") as f:
        for riga in f:
            if "=" in riga and not riga.startswith("["):
                chiave, valore = riga.split("=", 1)
                campi[chiave.strip()] = valore.strip()
    ok = True
    print("campi obbligatori metadata.txt:")
    for c in OBBLIGATORI:
        v = campi.get(c, "")
        stato = "ASSENTE <--" if not v else (
            "DA COMPILARE <--" if "DA-COMPILARE" in v else "ok")
        if stato != "ok":
            ok = False
        print("  %-20s %s" % (c, stato))
    print("  %-20s %s" % ("experimental", campi.get("experimental", "?")))
    return ok


# --solo-check-metadata: il controllo piu' veloce che ci sia, senza costruire
# niente. La CI lo usa nel job che non ha QGIS.
if "--solo-check-metadata" in sys.argv:
    sys.exit(0 if controlla_metadata() else 1)

os.makedirs(DIST, exist_ok=True)
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
            interno = os.path.join(NOME, os.path.relpath(assoluto, SRC))
            info = zipfile.ZipInfo(interno.replace(os.sep, "/"), DATA_FISSA)
            info.compress_type = zipfile.ZIP_DEFLATED
            # Permessi fissi (rw-r--r--): quelli veri del filesystem
            # cambierebbero l'impronta fra Windows e Linux.
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            with open(assoluto, "rb") as sorgente:
                z.writestr(info, sorgente.read())
            n_file += 1

with open(ZIP, "rb") as f:
    impronta = hashlib.sha256(f.read()).hexdigest()
with open(ZIP + ".sha256", "w", encoding="utf-8") as f:
    f.write("%s  %s\n" % (impronta, os.path.basename(ZIP)))

print("creato: %s" % ZIP)
print("SHA256: %s" % impronta)
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
              "dati_comune.py", "cerca_fondo.py", "legend_manifest.py",
              # moduli nati dallo spacchettamento di tidashboard.py: se uno
              # sparisse dallo zip il plugin non si caricherebbe affatto
              "colori.py", "etichette.py", "ordinamento.py", "simbologia.py",
              "stili.py",
              # documenti richiesti per la pubblicazione
              "icon.png", "README.md", "CHANGELOG.md", "CREDITI.md", "NORME.md",
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

print()
esito = controlla_metadata() and esito

print("\nESITO:", "PACCHETTO VALIDO" if esito else "ANOMALIE PRESENTI")

# Il codice di uscita, non solo la riga stampata: lanciato da un'automazione
# (vedi .github/workflows/ci.yml) un pacchetto con anomalie verrebbe
# altrimenti pubblicato lo stesso, e nessuno legge il registro di una cosa
# che dice di essere andata bene.
sys.exit(0 if esito else 1)
