# Test della ricerca di Java.
#
# NIENTE JAVA VERO, NIENTE DISCO: l'albero delle cartelle e l'esito di
# 'java -version' sono finti e iniettati. Un test che cercasse il Java della
# macchina direbbe cose diverse su ogni computer - e soprattutto passerebbe
# per il motivo sbagliato su quello di chi lo scrive.
#
# Eseguire con un Python qualunque (non serve QGIS):
#   python test_java_env.py
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tidashboard import java_env as J


class _Risposta(object):
    """Il minimo che sonda_versione legge da subprocess.run."""

    def __init__(self, stdout="", stderr=""):
        self.stdout = stdout
        self.stderr = stderr


def _albero(percorsi):
    """Un finto filesystem: da un elenco di file costruisce le tre funzioni
    che elenca_candidati usa (isfile, isdir, walk).

    IL WALKER RISPETTA LA POTATURA. os.walk permette al chiamante di svuotare
    la lista 'dirs' per non scendere oltre, ed e' esattamente cio' che fa la
    scansione dei vendor - e' la correzione che ha smesso di congelare la
    finestra di QGIS per secondi. Un finto walker che ignorasse quella
    mutazione farebbe passare il test anche con la potatura rotta, cioe'
    proverebbe il contrario di quello che dichiara.
    """
    file_set = set(os.path.normpath(p) for p in percorsi)
    cartelle = set()
    for p in file_set:
        d = os.path.dirname(p)
        while d and d not in cartelle:
            cartelle.add(d)
            padre = os.path.dirname(d)
            if padre == d:
                break
            d = padre

    def esiste_file(p):
        return os.path.normpath(p) in file_set

    def esiste_dir(p):
        return os.path.normpath(p) in cartelle

    def figli_di(d):
        return sorted(set(os.path.basename(x) for x in cartelle
                          if os.path.dirname(x) == d))

    def file_di(d):
        return sorted(os.path.basename(x) for x in file_set
                      if os.path.dirname(x) == d)

    def cammina(base):
        base = os.path.normpath(base)
        if base not in cartelle:
            return
        da_fare = [base]
        while da_fare:
            d = da_fare.pop(0)
            dirs = figli_di(d)
            yield d, dirs, file_di(d)
            # dirs puo' essere stata svuotata o filtrata dal chiamante: si
            # scende SOLO in quello che ci ha lasciato.
            da_fare = [os.path.join(d, x) for x in dirs] + da_fare

    return esiste_file, esiste_dir, cammina


def _p(*pezzi):
    """Un percorso nella forma del sistema su cui gira il test: le assert
    non devono dipendere dal separatore."""
    return os.path.normpath(os.path.join(*pezzi))


class TestParseVersione(unittest.TestCase):
    def test_stile_vecchio_e_java_8_non_java_1(self):
        """'1.8.0_401' e' Java 8: leggere "1" darebbe una versione piu' bassa
        di qualunque altra e farebbe scartare un JRE perfettamente valido."""
        self.assertEqual(J.parse_versione('java version "1.8.0_401"'), (8, 0))
        self.assertEqual(J.parse_versione('java version "1.7.0_80"'), (7, 0))

    def test_stile_nuovo(self):
        self.assertEqual(J.parse_versione('openjdk version "17.0.9" 2023'), (17, 0))
        self.assertEqual(J.parse_versione('openjdk version "21" 2023-09-19'), (21, 0))
        self.assertEqual(J.parse_versione('openjdk version "11.0.21"'), (11, 0))

    def test_output_che_non_dice_niente(self):
        self.assertIsNone(J.parse_versione(""))
        self.assertIsNone(J.parse_versione(None))
        self.assertIsNone(J.parse_versione("non sono java"))
        self.assertIsNone(J.parse_versione('version senza virgolette 17'))

    def test_ordinamento_fra_versioni(self):
        """E' l'unico uso che se ne fa: scegliere la piu' alta."""
        self.assertGreater(J.parse_versione('version "21"'),
                           J.parse_versione('version "1.8.0_401"'))
        self.assertGreater(J.parse_versione('version "17.0.9"'),
                           J.parse_versione('version "11.0.21"'))


class TestSondaVersione(unittest.TestCase):
    def test_legge_da_stderr(self):
        """java -version scrive su STDERR, non su stdout: leggendo solo
        stdout non si troverebbe mai nessuna versione."""
        v = J.sonda_versione("/finto/java", esegui=lambda *a, **k: _Risposta(
            stderr='openjdk version "17.0.9" 2023-10-17'))
        self.assertEqual(v, (17, 0))

    def test_eseguibile_che_non_parte(self):
        righe = []

        def esplode(*a, **k):
            raise OSError("non e' un'applicazione win32 valida")

        v = J.sonda_versione("/rotto/java", log=righe.append, esegui=esplode)
        self.assertIsNone(v)
        self.assertTrue(righe and "fallita" in righe[0])

    def test_output_non_interpretabile_viene_segnalato(self):
        righe = []
        v = J.sonda_versione("/strano/java", log=righe.append,
                             esegui=lambda *a, **k: _Risposta(stdout="ciao"))
        self.assertIsNone(v)
        self.assertTrue(righe and "non interpretabile" in righe[0])


class TestElencaCandidatiWindows(unittest.TestCase):
    PF = r"C:\Program Files"

    def _elenca(self, files, environ=None, which=None):
        f, d, w = _albero(files)
        return J.elenca_candidati(
            os_name="nt",
            environ=environ if environ is not None else {"PROGRAMFILES": self.PF},
            which=which or (lambda _n: None),
            esiste_file=f, esiste_dir=d, cammina=w)

    def test_path_viene_per_primo(self):
        c = self._elenca([], which=lambda _n: r"C:\Windows\System32\java.exe")
        self.assertEqual(c, [r"C:\Windows\System32\java.exe"])

    def test_java_home(self):
        home = r"C:\jdk17"
        c = self._elenca([home + r"\bin\java.exe"],
                         environ={"PROGRAMFILES": self.PF, "JAVA_HOME": home})
        self.assertIn(home + r"\bin\java.exe", c)

    def test_java_home_che_punta_a_niente_non_entra(self):
        c = self._elenca([], environ={"PROGRAMFILES": self.PF,
                                      "JAVA_HOME": r"C:\non\esiste"})
        self.assertEqual(c, [])

    def test_trova_i_vendor(self):
        c = self._elenca([
            self.PF + r"\Eclipse Adoptium\jdk-17.0.9\bin\java.exe",
            self.PF + r"\Java\jre1.8.0_401\bin\java.exe",
        ])
        self.assertEqual(len(c), 2)

    def test_sotto_microsoft_si_entra_solo_nelle_jdk(self):
        """Sotto Program Files\\Microsoft convivono decine di prodotti non
        Java: camminarli tutti congelava la finestra per secondi."""
        c = self._elenca([
            self.PF + r"\Microsoft\jdk-17.0.9\bin\java.exe",
            self.PF + r"\Microsoft\Office\root\java.exe",
        ])
        self.assertEqual(len(c), 1)
        self.assertIn("jdk-17.0.9", c[0])

    def test_i_duplicati_si_contano_una_volta_sola(self):
        """PATH e JAVA_HOME indicano spesso lo stesso eseguibile, scritto in
        due modi: sonderemmo due volte lo stesso file."""
        home = r"C:\jdk17"
        exe = home + r"\bin\java.exe"
        c = self._elenca([exe],
                         environ={"PROGRAMFILES": self.PF, "JAVA_HOME": home},
                         which=lambda _n: exe.replace("\\jdk17\\", "\\JDK17\\"))
        self.assertEqual(len(c), 1)


class TestElencaCandidatiUnix(unittest.TestCase):
    def _elenca(self, files, environ=None, which=None, radici=None):
        f, d, w = _albero(files)
        return J.elenca_candidati(
            os_name="posix", environ=environ or {},
            which=which or (lambda _n: None),
            esiste_file=f, esiste_dir=d, cammina=w,
            radici_unix=radici or ("/usr/lib/jvm",))

    def test_trova_il_java_di_apt(self):
        """Il caso vero: macchina d'ufficio con Java installato da apt e
        nessuna JAVA_HOME esportata. Prima il plugin diceva "non trovato"."""
        atteso = _p("/usr/lib/jvm/java-17-openjdk-amd64/bin/java")
        c = self._elenca([atteso])
        self.assertEqual([_p(x) for x in c], [atteso])

    def test_cerca_java_non_java_exe(self):
        c = self._elenca(["/usr/lib/jvm/jdk-21/bin/java.exe"])
        self.assertEqual(c, [])

    def test_solo_dentro_una_cartella_bin(self):
        """Un file di nome 'java' che non sta in bin/ non e' l'eseguibile:
        e' un sorgente, uno script, una cartella di esempi."""
        c = self._elenca(["/usr/lib/jvm/jdk-21/lib/java"])
        self.assertEqual(c, [])

    def test_radice_inesistente_non_esplode(self):
        self.assertEqual(self._elenca([], radici=("/non/esiste",)), [])


class TestTrovaJava(unittest.TestCase):
    def _esito(self, files, versioni, which=None):
        f, d, w = _albero(files)
        return J.trova_java(
            sonda=lambda exe: versioni.get(_p(exe)),
            os_name="posix", environ={}, which=which or (lambda _n: None),
            esiste_file=f, esiste_dir=d, cammina=w,
            radici_unix=("/usr/lib/jvm",))

    def test_sceglie_la_versione_piu_alta_fra_quelle_che_funzionano(self):
        otto = _p("/usr/lib/jvm/jdk-8/bin/java")
        ventuno = _p("/usr/lib/jvm/jdk-21/bin/java")
        diciassette = _p("/usr/lib/jvm/jdk-17/bin/java")
        esito = self._esito([otto, ventuno, diciassette],
                            {otto: (8, 0), ventuno: (21, 0), diciassette: (17, 0)})
        self.assertEqual(_p(esito.percorso), ventuno)
        self.assertEqual(esito.versione, (21, 0))
        self.assertEqual(esito.n_candidati, 3)

    def test_un_eseguibile_rotto_viene_scartato_anche_se_e_il_primo(self):
        """E' il motivo per cui si esegue 'java -version' invece di fidarsi
        del file: sul PATH di Windows c'e' spesso lo stub di WindowsApps, che
        esiste e non parte."""
        buono = _p("/usr/lib/jvm/jdk-11/bin/java")
        stub = _p("/WindowsApps/stub/java")
        esito = self._esito([buono], {buono: (11, 0)}, which=lambda _n: stub)
        self.assertEqual(_p(esito.percorso), buono)
        self.assertEqual(esito.versione, (11, 0))
        self.assertEqual(esito.n_candidati, 2, "lo stub va comunque provato")

    def test_nessun_java(self):
        esito = self._esito([], {})
        self.assertIsNone(esito.percorso)
        self.assertIsNone(esito.versione)
        self.assertEqual(esito.n_candidati, 0)

    def test_candidati_trovati_ma_nessuno_funzionante(self):
        """Il chiamante distingue i due casi per dire cose diverse: "Java non
        installato" e "Java installato ma rotto" si risolvono in modi
        diversi."""
        rotto = _p("/usr/lib/jvm/jdk-9/bin/java")
        esito = self._esito([rotto], {})
        self.assertIsNone(esito.percorso)
        self.assertEqual(esito.n_candidati, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
