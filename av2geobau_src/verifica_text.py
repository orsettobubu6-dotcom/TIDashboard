# Verifica strutturale delle entita' TEXT prodotte dal jar.
#
# Il TEXT del DXF vuole il marcatore di sottoclasse AcDbText DUE VOLTE: una
# prima della geometria e una seconda prima del gruppo 73. Mancando la
# seconda, AutoCAD non degrada il testo - rifiuta l'INTERO disegno con
#   "while reading in TEXT ... Class separator for class AcDbText expected"
# e il file diventa inservibile per intero, anche se il difetto e' su una
# manciata di entita' su centinaia di migliaia.
#
# Uso:  python verifica_text.py percorso.dxf
# In streaming: i file veri sono da centinaia di MB.
import io
import sys

percorso = sys.argv[1]

totale = 0
senza_secondo_marcatore = []
senza_stile = []
corrente = None


def esamina(entita, n):
    marcatori = [v for c, v in entita if c == "100"]
    if marcatori.count("AcDbText") < 2:
        senza_secondo_marcatore.append((n, [v for v in marcatori]))
    if not any(c == "7" for c, _ in entita):
        senza_stile.append(n)


with io.open(percorso, encoding="cp1252", errors="replace") as f:
    while True:
        riga_codice = f.readline()
        if not riga_codice:
            break
        riga_valore = f.readline()
        if not riga_valore:
            break
        codice = riga_codice.strip()
        valore = riga_valore.rstrip("\n").rstrip("\r").strip()
        if codice == "0":
            if corrente is not None:
                totale += 1
                esamina(corrente, totale)
                corrente = None
            if valore == "TEXT":
                corrente = [("0", "TEXT")]
        elif corrente is not None:
            corrente.append((codice, valore))

print("TEXT totali                  : %d" % totale)
print("senza il SECONDO AcDbText    : %d" % len(senza_secondo_marcatore))
for n, marc in senza_secondo_marcatore[:5]:
    print("   n.%d marcatori=%s" % (n, marc))
# Lo stile e' un'altra cosa gia' corretta in passato (le scritture del piano
# vanno in Cadastra/Arial): qui si controlla solo che non manchi del tutto.
print("senza il gruppo 7 (stile)    : %d" % len(senza_stile))

ok = not senza_secondo_marcatore
print("\nESITO:", "OK" if ok else "ANOMALIE PRESENTI")
sys.exit(0 if ok else 1)
