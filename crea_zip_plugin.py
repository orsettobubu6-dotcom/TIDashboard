"""Costruisce lo zip installabile del plugin QGIS e lo verifica.

Eseguire con l'interprete di QGIS:
    & "C:\\Program Files\\QGIS 4.2.0\\bin\\python-qgis.bat" crea_zip_plugin.py

QGIS pretende una sola cartella di primo livello col nome del plugin, dentro
cui stanno metadata.txt e __init__.py. Il numero di versione viene letto da
metadata.txt, cosi' il nome del file non puo' divergere dal contenuto.
"""
import hashlib
import os
import re
import stat
import sys
import zipfile
from xml.sax.saxutils import escape

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


def leggi_metadata():
    campi = {}
    with open(os.path.join(SRC, "metadata.txt"), encoding="utf-8") as f:
        for riga in f:
            if "=" in riga and not riga.startswith("["):
                chiave, valore = riga.split("=", 1)
                campi[chiave.strip()] = valore.strip()
    return campi


def scrivi_plugins_xml(campi):
    """Il catalogo che QGIS legge per installare e AGGIORNARE il plugin.

    PERCHE' ESISTE. "Code -> Download ZIP" di GitHub non potra' mai funzionare
    con QGIS, e non e' una questione di come e' fatto questo repository: quel
    file ha sempre una cartella in piu' in cima chiamata "<nome>-<ramo>", QGIS
    usa il nome della cartella come nome di modulo Python, e un trattino non e'
    un nome valido. Il rimedio non e' aggiustare quel download, e' rendere
    inutile usarlo - dando a QGIS un indirizzo da cui prendere il pacchetto
    giusto da solo.

    L'INDIRIZZO PUNTA AL TAG, non a "latest". Se un domani si alzasse la
    versione in metadata.txt senza pubblicare la Release, un indirizzo
    "latest" servirebbe il pacchetto VECCHIO facendolo passare per quello
    nuovo: QGIS lo installerebbe e direbbe di avere la versione nuova. Con
    l'indirizzo del tag, invece, finche' la Release non c'e' il download
    fallisce e si vede.

    Il file si RIGENERA a ogni costruzione: scritto a mano si scollerebbe da
    metadata.txt alla prima versione, che e' la stessa trappola della lista
    dei moduli attesi."""
    versione = campi.get("version", "0.0.0")
    deposito = campi.get("repository", "").rstrip("/")
    scarico = "%s/releases/download/v%s/%s_%s.zip" % (
        deposito, versione, NOME, versione)

    # I PUNTI IN file_name NON SONO UN VEZZO. Letto nel codice che consuma
    # questo file (pyplugin_installer/installer_data.py, xmlDownloaded):
    #
    #     name = fileName.partition(".")[0]
    #     plugin = {"id": name, ...}
    #
    # QGIS ricava l'IDENTIFICATIVO del plugin da file_name, prendendo tutto
    # cio' che sta prima del PRIMO PUNTO, e quell'identificativo deve
    # coincidere con il nome della cartella installata - e' cosi' che QGIS
    # capisce se il plugin c'e' gia' e se esiste una versione piu' nuova.
    # Con "tidashboard_1.2.1.zip" verrebbe fuori "tidashboard_1": il plugin
    # comparirebbe come una cosa diversa da quella installata, resterebbe
    # "non installato" anche dopo l'installazione e nessun aggiornamento
    # verrebbe mai proposto. Nessun errore, da nessuna parte. E' anche il
    # motivo per cui plugins.qgis.org nomina i suoi file con i punti.
    #
    # Il nome del file ALLEGATO alla Release resta quello con la
    # sottolineatura: qui conta solo cio' che QGIS legge, e download_url
    # indirizza il file vero.
    nome_file = "%s.%s.zip" % (NOME, versione)
    identificativo = nome_file.partition(".")[0]
    if identificativo != NOME:
        raise SystemExit("file_name %r darebbe l'identificativo %r invece di %r"
                         % (nome_file, identificativo, NOME))
    voci = [
        ("description", campi.get("description", "")),
        ("about", campi.get("about", "")),
        ("version", versione),
        ("qgis_minimum_version", campi.get("qgisMinimumVersion", "")),
        ("qgis_maximum_version", campi.get("qgisMaximumVersion", "")),
        ("homepage", campi.get("homepage", deposito)),
        ("file_name", nome_file),
        ("author_name", campi.get("author", "")),
        ("download_url", scarico),
        ("uploaded_by", campi.get("author", "")),
        ("experimental", campi.get("experimental", "False")),
        ("deprecated", campi.get("deprecated", "False")),
        ("tracker", campi.get("tracker", "")),
        ("repository", deposito),
        ("tags", campi.get("tags", "")),
    ]
    righe = ['<?xml version="1.0" encoding="UTF-8"?>',
             "<!-- Generato da crea_zip_plugin.py: non modificare a mano. -->",
             "<plugins>",
             '  <pyqgis_plugin name="%s" version="%s">'
             % (escape(campi.get("name", NOME), {'"': "&quot;"}),
                escape(versione, {'"': "&quot;"}))]
    # Le voci vuote si omettono invece di scriverle come <tag></tag>: un
    # catalogo pubblico non deve far indovinare a chi lo legge se un campo e'
    # assente o solo non compilato.
    righe += ["    <%s>%s</%s>" % (c, escape(v), c) for c, v in voci if v]
    righe += ["  </pyqgis_plugin>", "</plugins>", ""]
    percorso = os.path.join(QUI, "plugins.xml")
    with open(percorso, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(righe))
    return percorso, scarico


def controlla_metadata():
    """I campi che plugins.qgis.org pretende. Ritorna True se ci sono tutti."""
    campi = leggi_metadata()
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

# L'ORDINE DELLE VOCI, che e' la terza cosa da fissare dopo date e permessi e
# l'unica che era rimasta fuori. os.walk visita le SOTTOCARTELLE nell'ordine
# che gli da' il filesystem, e quell'ordine non e' lo stesso su NTFS e su
# ext4: ordinare i file dentro ciascuna cartella - come si faceva - non basta.
#
# MISURATO sui due archivi della 1.2.2, quello pubblicato dalla CI e quello
# ricostruito qui: 174 file identici, contenuti identici, permessi e date
# identici, perfino le dimensioni compresse identiche voce per voce. Diverso
# solo l'ORDINE - su Linux "models/" prima di "fonts/", qui "av2geobau/"
# prima di tutto - e quindi diversa l'impronta dell'archivio.
#
# Vale anche per la 1.2.1, verificato ricostruendo dal suo tag: la
# dichiarazione "da questa versione l'impronta si puo' verificare" era falsa.
# Si raccoglie tutto, si ordina per nome interno, poi si scrive.
voci = []
for radice, cartelle, file in os.walk(SRC):
    cartelle[:] = [c for c in cartelle if c not in ESCLUDI_DIR]
    for nome_file in file:
        if os.path.splitext(nome_file)[1].lower() in ESCLUDI_EST:
            continue
        assoluto = os.path.join(radice, nome_file)
        interno = os.path.join(NOME, os.path.relpath(assoluto, SRC))
        voci.append((interno.replace(os.sep, "/"), assoluto))
voci.sort()

n_file = 0
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for interno, assoluto in voci:
        info = zipfile.ZipInfo(interno, DATA_FISSA)
        info.compress_type = zipfile.ZIP_DEFLATED
        # Permessi fissi (rw-r--r--): quelli veri del filesystem
        # cambierebbero l'impronta fra Windows e Linux.
        info.external_attr = (stat.S_IFREG | 0o644) << 16
        # E IL SISTEMA CHE HA PRODOTTO L'ARCHIVIO, che lo zip si annota da
        # solo: zipfile mette 0 (MS-DOS) su Windows e 3 (Unix) altrove. Era
        # l'ultima cosa che restava a distinguere i due archivi - stessi file,
        # stesso ordine, stessi byte compressi, e un byte diverso nella
        # directory centrale di ognuna delle 174 voci ("\x14\x03" contro
        # "\x14\x00").
        #
        # Si fissa a 3 e non a 0 perche' i permessi qui sopra sono permessi
        # UNIX: hanno senso solo se l'archivio dichiara di venire da un
        # sistema Unix. Con 0 quei bit c'erano ma nessuno li avrebbe letti.
        info.create_system = 3
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

_xml, _scarico = scrivi_plugins_xml(leggi_metadata())
print("plugins.xml -> %s" % _scarico)

esito = True
with zipfile.ZipFile(ZIP) as z:
    nomi = z.namelist()
    corrotto = z.testzip()
    radici = {n.split("/")[0] for n in nomi}
    print("\nintegrita' archivio       :", "OK" if corrotto is None else "CORROTTO: %s" % corrotto)
    print("cartella di primo livello :", radici)
    esito = esito and corrotto is None and radici == {NOME}

    # L'invariante che rende l'impronta verificabile altrove. Se un domani si
    # tornasse a scrivere seguendo os.walk, l'archivio uscirebbe identico nel
    # contenuto e diverso nell'impronta - cioe' il difetto tornerebbe senza
    # che nulla si rompa: solo il confronto con la Release smetterebbe di
    # tornare, e su una macchina sola non si vede.
    ordinato = nomi == sorted(nomi)
    print("voci in ordine alfabetico :", "SI" if ordinato else
          "NO <-- l'impronta dipenderebbe dal filesystem")
    esito = esito and ordinato

    sistemi = {i.create_system for i in z.infolist()}
    print("sistema dichiarato        :", sistemi,
          "" if sistemi == {3} else "<-- deve essere {3}: dipenderebbe dall'OS")
    esito = esito and sistemi == {3}

    # I MODULI ATTESI SI LEGGONO DAGLI IMPORT, non dal disco. Prima erano
    # scritti a mano e la lista si era scollata: dei 17 moduli ne controllava
    # 11, e i sei rimasti fuori erano tutti nati dopo.
    #
    # Ricavarli da os.listdir sembrava la correzione ovvia e NON HA DENTI:
    # elencando la stessa cartella da cui si costruisce lo zip, un modulo
    # cancellato sparisce da tutt'e due e il confronto torna. Provato -
    # spostando via coordinate.py il controllo diceva ancora PACCHETTO VALIDO.
    #
    # Cio' che conta e' un'altra cosa: che nello zip ci sia tutto quello che
    # tidashboard.py IMPORTA. Se un modulo sparisce, l'import resta e il
    # plugin muore al caricamento con ModuleNotFoundError - che e' esattamente
    # il guasto che questo controllo esiste per impedire.
    with open(os.path.join(SRC, "tidashboard.py"), encoding="utf-8") as f:
        sorgente = f.read()
    # Le due forme usate nel file: "from . import x as _x" e "from .x import y".
    coppie = re.findall(r"^\s*from \. import (\w+)|^\s*from \.(\w+) import",
                        sorgente, re.MULTILINE)
    importati = sorted({nome for coppia in coppie for nome in coppia if nome})
    moduli = ["%s.py" % m for m in importati]
    print("moduli importati da tidashboard.py: %d" % len(moduli))
    attesi = ["metadata.txt", "__init__.py", "tidashboard.py"] + moduli + [
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
