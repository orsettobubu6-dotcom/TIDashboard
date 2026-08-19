"""Ricerca di un JRE/JDK funzionante, senza Qt e senza QGIS.

Estratto da tidashboard.py perche' find_java mescolava tre cose: la scansione
dei dischi, l'esecuzione di 'java -version' e il log nella dialog. Le prime
due si provano con un Python qualunque; la cache e i messaggi restano al
chiamante (TIDashboardDialog.find_java).

Il jar av2geobau_ti.jar e' compilato con --release 8: qualunque JRE 8+ va
bene. Tra i candidati funzionanti si sceglie la versione piu' alta.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

# Cartelle vendor sotto Program Files. Oracle finisce in "Java"; Microsoft
# ospita anche Office e altro, quindi si entra solo nelle sottocartelle jdk*.
VENDOR_WINDOWS = (
    "Java",
    "Eclipse Adoptium",
    "Eclipse Foundation",
    "Microsoft",
    "Amazon Corretto",
    "Zulu",
    "BellSoft",
    "Semeru",
)

# Dove le distro Linux e i pacchetti macOS mettono i JDK. Senza queste,
# fuori da Windows restano solo PATH e JAVA_HOME: su una macchina d'ufficio
# con Java installato da apt ma senza JAVA_HOME il plugin diceva "non trovato".
RADICI_JAVA_UNIX = (
    "/usr/lib/jvm",
    "/usr/lib64/jvm",
    "/usr/java",
    "/opt/java",
    "/opt/jdk",
    "/Library/Java/JavaVirtualMachines",
    "/opt/homebrew/opt/openjdk",
    "/usr/local/opt/openjdk",
)

# java.exe non sta mai a profondita' 4 sotto la cartella vendor.
PROFONDITA_MAX_VENDOR = 3


def parse_versione(output):
    """Legge la major.minor da stdout+stderr di 'java -version'.

    '1.8.0_401' e' Java 8, non Java 1. Ritorna None se la riga non c'e'.
    """
    if not output:
        return None
    m = re.search(r'version "(\d+)(?:\.(\d+))?', output)
    if not m:
        return None
    major = int(m.group(1))
    minor = int(m.group(2)) if m.group(2) else 0
    if major == 1 and minor:
        major, minor = minor, 0
    return (major, minor)


def sonda_versione(java_exe, log=None, esegui=None):
    """Esegue 'java -version' e ne legge la tupla (major, minor).

    Ritorna None se l'eseguibile non parte o l'output non e' interpretabile.
    'esegui' e' iniettabile nei test (firma come subprocess.run).
    """
    esegui = esegui or subprocess.run
    try:
        result = esegui(
            [java_exe, "-version"], capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as e:
        if log:
            log("   ⚠️ Verifica 'java -version' fallita per %s: %s" % (java_exe, e))
        return None
    output = (result.stdout or "") + (result.stderr or "")
    versione = parse_versione(output)
    if versione is None and log:
        log("   ⚠️ Output 'java -version' non interpretabile per %s: %s"
            % (java_exe, (output or "").strip()[:200]))
    return versione


def _eseguibile(os_name):
    return "java.exe" if os_name == "nt" else "java"


def elenca_candidati(os_name=None, environ=None, which=None,
                     esiste_file=None, esiste_dir=None, cammina=None,
                     radici_unix=None):
    """Percorsi plausibili, senza eseguirli. L'ordine e' PATH, JAVA_HOME,
    poi le cartelle dei vendor (Windows) o di sistema (Unix).

    Tutti i parametri sono iniettabili: i test costruiscono un albero finto
    e non toccano il Java vero della macchina.
    """
    os_name = os.name if os_name is None else os_name
    environ = os.environ if environ is None else environ
    which = shutil.which if which is None else which
    esiste_file = os.path.isfile if esiste_file is None else esiste_file
    esiste_dir = os.path.isdir if esiste_dir is None else esiste_dir
    cammina = os.walk if cammina is None else cammina

    exe_name = _eseguibile(os_name)
    candidates = []

    # (a) PATH: la fonte piu' portabile. Puo' essere lo stub WindowsApps.
    which_java = which("java")
    if which_java:
        candidates.append(which_java)

    # (b) JAVA_HOME, se esportata.
    java_home = environ.get("JAVA_HOME")
    if java_home:
        candidate = str(Path(java_home) / "bin" / exe_name)
        if esiste_file(candidate):
            candidates.append(candidate)

    # (c) Cartelle di installazione, ultima risorsa.
    if os_name == "nt":
        candidates.extend(_scansiona_windows(
            exe_name, environ, esiste_dir, cammina))
    else:
        candidates.extend(_scansiona_unix(
            exe_name, esiste_file, esiste_dir, cammina,
            radici_unix or RADICI_JAVA_UNIX))

    seen = set()
    unique = []
    for c in candidates:
        key = os.path.normcase(os.path.normpath(c))
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def _scansiona_windows(exe_name, environ, esiste_dir, cammina):
    trovati = []
    program_files_dirs = [
        environ.get("PROGRAMFILES", r"C:\Program Files"),
        environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
    ]
    for pf in program_files_dirs:
        for vendor in VENDOR_WINDOWS:
            base_path = Path(pf) / vendor
            if not esiste_dir(str(base_path)):
                continue
            base_depth = len(base_path.parts)
            for root, dirs, files in cammina(str(base_path)):
                depth = len(Path(root).parts) - base_depth
                if depth >= PROFONDITA_MAX_VENDOR:
                    dirs[:] = []
                elif vendor == "Microsoft" and depth == 0:
                    dirs[:] = [d for d in dirs if d.lower().startswith("jdk")]
                if exe_name in files:
                    trovati.append(str(Path(root) / exe_name))
    return trovati


def _scansiona_unix(exe_name, esiste_file, esiste_dir, cammina, radici):
    """Stessa idea della scansione Windows: profondita' limitata, niente
    passeggiate in /opt intero. Su Debian/Ubuntu Java sta in /usr/lib/jvm
    come default-java o java-17-openjdk-amd64/bin/java."""
    trovati = []
    for base in radici:
        if not esiste_dir(base):
            continue
        diretto = str(Path(base) / "bin" / exe_name)
        if esiste_file(diretto):
            trovati.append(diretto)
        base_depth = len(Path(base).parts)
        try:
            walker = cammina(base)
        except (OSError, TypeError):
            continue
        for root, dirs, files in walker:
            depth = len(Path(root).parts) - base_depth
            if depth >= 4:
                dirs[:] = []
                continue
            if exe_name in files and os.path.basename(root) == "bin":
                trovati.append(str(Path(root) / exe_name))
    return trovati


class EsitoJava:
    """Risultato di trova_java: il chiamante decide cache e log UI."""

    def __init__(self, percorso, versione, candidati):
        self.percorso = percorso
        self.versione = versione
        self.candidati = list(candidati)

    @property
    def n_candidati(self):
        return len(self.candidati)


def trova_java(log=None, sonda=None, **kwargs_elenco):
    """Sceglie l'eseguibile funzionante con la versione piu' alta.

    Non tiene cache: la dialog la tiene sull'istanza, cosi' il pulsante
    'Verifica ambiente' puo' azzerarla. 'sonda' e i kwargs di elenca_candidati
    sono iniettabili nei test.
    """
    sonda = sonda or (lambda exe: sonda_versione(exe, log=log))
    candidati = elenca_candidati(**kwargs_elenco)
    best_path = None
    best_version = (-1, -1)
    for c in candidati:
        versione = sonda(c)
        if versione is not None and versione > best_version:
            best_version = versione
            best_path = c
    return EsitoJava(best_path, best_version if best_path else None, candidati)
