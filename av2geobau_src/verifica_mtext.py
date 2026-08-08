# Verifica dei MTEXT prodotti dal jar. Controlla le tre condizioni che AutoCAD
# impone alla maschera di sfondo e che sono state stabilite PROVANDO, non
# dedotte (vedi il commento in DxfWriter.mtext2Dxf): se una salta, AutoCAD non
# degrada la maschera - rifiuta l'INTERO disegno alla prima entita'.
#
#   1) i tre group 45, 90 e 63 presenti su ogni MTEXT;
#   2) il modo (group 90) vale 3, non 2: con 2 il disegno viene scartato;
#   3) i valori di 90 e 63 scritti senza riempimento a sinistra.
#
# Uso:  python verifica_mtext.py percorso.dxf
# Il controllo e' in streaming: i file veri sono da centinaia di MB.
import io
import sys

from ezdxf.entities import factory
from ezdxf.lldxf.extendedtags import ExtendedTags
from ezdxf.lldxf.tagger import internal_tag_compiler

percorso = sys.argv[1]

TERNA = ("45", "90", "63")

totale = 0
senza_terna = []
modo_sbagliato = []
con_riempimento = []
primi = []
corrente = None


def esamina(entita, n):
    presenti = [c for c, _ in entita if c in TERNA]
    if presenti != ["45", "90", "63"]:
        senza_terna.append((n, presenti))
        return
    for codice, valore in entita:
        if codice == "90" and valore.strip() != "3":
            modo_sbagliato.append((n, valore.strip()))
        if codice in ("90", "63") and valore != valore.strip():
            con_riempimento.append((n, codice, repr(valore)))


with io.open(percorso, encoding="cp1252", errors="replace") as f:
    while True:
        riga_codice = f.readline()
        if not riga_codice:
            break
        riga_valore = f.readline()
        if not riga_valore:
            break
        codice = riga_codice.strip()
        valore = riga_valore.rstrip("\n").rstrip("\r")
        if codice == "0":
            if corrente is not None:
                totale += 1
                esamina(corrente, totale)
                if len(primi) < 3:
                    primi.append(corrente)
                corrente = None
            if valore.strip() == "MTEXT":
                corrente = [("0", "MTEXT")]
        elif corrente is not None:
            corrente.append((codice, valore))

print("MTEXT totali              : %d" % totale)
print("senza la terna 45/90/63   : %d" % len(senza_terna))
print("con modo diverso da 3     : %d" % len(modo_sbagliato))
print("con valori riempiti       : %d" % len(con_riempimento))
for elenco in (senza_terna, modo_sbagliato, con_riempimento):
    for riga in elenco[:3]:
        print("   %s" % (riga,))

# Rilettura vera: se la maschera non fosse riconosciuta gli attributi
# resterebbero assenti.
print("\nrilettura con ezdxf dei primi %d:" % len(primi))
for entita in primi:
    # internal_tag_compiler: i group di punto (10/20/30) vanno fusi in un
    # vettore, altrimenti ezdxf rifiuta i tag grezzi.
    grezzo = "".join("%s\n%s\n" % (c, v) for c, v in entita)
    e = factory.load(ExtendedTags(internal_tag_compiler(grezzo)))
    print("   testo=%-10s bg_fill=%s bg_fill_color=%s box_fill_scale=%s"
          % (e.text, e.dxf.get("bg_fill", "ASSENTE"),
             e.dxf.get("bg_fill_color", "ASSENTE"),
             e.dxf.get("box_fill_scale", "ASSENTE")))

ok = not (senza_terna or modo_sbagliato or con_riempimento)
print("\nESITO:", "OK" if ok else "ANOMALIE PRESENTI")
sys.exit(0 if ok else 1)
