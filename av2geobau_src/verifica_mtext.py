# Verifica dei MTEXT prodotti dal jar: la maschera di sfondo va scritta con i
# tre group 45, 90 e 63, in quest'ordine e su OGNI entita'. Il controllo e' in
# streaming perche' il file e' da 209 MB.
import io, sys
from ezdxf.lldxf.extendedtags import ExtendedTags
from ezdxf.lldxf.tagger import internal_tag_compiler
from ezdxf.entities import factory

percorso = sys.argv[1]

totale = 0
fuori_regola = []
primi = []
corrente = None

with io.open(percorso, encoding="cp1252", errors="replace") as f:
    while True:
        codice = f.readline()
        if not codice:
            break
        valore = f.readline()
        if not valore:
            break
        try:
            c = int(codice.strip())
        except ValueError:
            continue
        v = valore.rstrip("\n").rstrip("\r")
        if c == 0:
            if corrente is not None:
                totale += 1
                sequenza = [k for k, _ in corrente if k in (45, 90, 63)]
                if sequenza != [45, 90, 63]:
                    fuori_regola.append((totale, sequenza))
                if len(primi) < 3:
                    primi.append(corrente)
                corrente = None
            if v.strip() == "MTEXT":
                corrente = [(0, "MTEXT")]
        elif corrente is not None:
            corrente.append((c, v))

print("MTEXT totali            : %d" % totale)
print("senza la terna 45/90/63 : %d" % len(fuori_regola))
for n, seq in fuori_regola[:5]:
    print("   n.%d -> %s" % (n, seq))

# Rilettura vera con ezdxf: se la maschera non fosse riconosciuta, gli
# attributi resterebbero assenti.
print("\nrilettura con ezdxf dei primi %d:" % len(primi))
for tags in primi:
    # internal_tag_compiler: i group di punto (10/20/30) vanno fusi in un
    # vettore, altrimenti ezdxf rifiuta i tag grezzi.
    grezzo = "".join("%d\n%s\n" % (c, v) for c, v in tags)
    xt = ExtendedTags(internal_tag_compiler(grezzo))
    e = factory.load(xt)
    print("   testo=%-10s bg_fill=%s bg_fill_color=%s box_fill_scale=%s rotation=%s"
          % (e.text, e.dxf.get("bg_fill", "ASSENTE"),
             e.dxf.get("bg_fill_color", "ASSENTE"),
             e.dxf.get("box_fill_scale", "ASSENTE"),
             e.dxf.get("rotation", "ASSENTE")))
