package org.interlis2.av2geobau.impl;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Sposta le etichette che si sovrappongono, e SOLO quelle.
 *
 * <p>Perche' non un layout automatico completo. In MD01MUTI7MN95 la posizione
 * di ogni scritta e' un dato: sta nelle tabelle Pos* (PosPunto_di_confine,
 * PosNumero_OS, ...) con Ori, HAli e VAli, e l'ha scelta il geometra. Sul
 * comune di prova sono 75 287 posizioni per 75 293 punti di confine: il 100%.
 * Ricalcolarle con una regola per tipo di simbolo vorrebbe dire buttare via
 * anche i casi - circa uno su sette - in cui il geometra ha spostato apposta
 * una scritta per schivare qualcosa. Misurata sui dati, del resto, la direzione
 * scelta NON dipende dal tipo di simbolo: GPUV, GPSTE, GPBOL e GPKRZ stanno
 * tutti fra NE ed E nell'85% dei casi.
 *
 * <p>Quello che invece succede davvero e' che il 19.7% delle etichette dei punti
 * di confine ha il proprio riquadro sovrapposto a quello di un'altra: 9 819
 * coppie. Questa classe risolve quelle, lasciando dov'e' tutto il resto.
 *
 * <p>Come: si tiene la posizione del geometra finche' e' libera; se non lo e',
 * si prova a scostare l'etichetta di poco, nelle otto direzioni, restando
 * entro {@link #SPOSTAMENTO_MASSIMO} metri dall'originale in modo che resti
 * chiaro a quale punto appartiene; se nemmeno cosi' c'e' posto, cede quella di
 * priorita' minore. "Cede" non vuol dire sparire: passa al layer
 * {@link #LAYER_NASCOSTE}, che nasce spento. Un numero catastale e' un dato
 * ufficiale e non lo si cancella da un piano - lo si mette da parte, e chi
 * apre il disegno puo' riaccenderlo.
 *
 * <p>Non ruota nulla. Ruotare una scritta per far posto sembra una soluzione
 * gratuita, ma in questo piano l'orientamento e' informazione (Ori, dalle
 * tabelle Pos*): una scritta girata di 90 gradi direbbe qualcosa di falso.
 */
public final class AntiCollisioneEtichette {

    /** Le etichette che possono essere spostate, con la loro priorita' di
     * partenza: chi ha il numero piu' alto resta dov'e' e fa spostare l'altra.
     * Sono i numeri dei PUNTI, dove il problema e' stato misurato; i nomi, i
     * numeri di fondo e le altre scritte non si spostano mai (vedi
     * LAYER_OSTACOLO: fanno da ostacolo e basta). */
    private static final Map<String, Integer> PRIORITA_ETICHETTA = new HashMap<String, Integer>();
    /** Scritte che non si spostano ma occupano spazio. */
    private static final Set<String> LAYER_OSTACOLO = new HashSet<String>();
    /** Affina la priorita' del numero di un punto di confine secondo il tipo di
     * punto: un punto materializzato pesa piu' di uno che sul terreno non
     * esiste. */
    private static final Map<String, Integer> PRIORITA_BLOCCO = new HashMap<String, Integer>();
    private static final Set<String> LAYER_SIMBOLO_CONFINE = new HashSet<String>();

    /** Dove finiscono le etichette per cui non si e' trovato posto. */
    public static final String LAYER_NASCOSTE = "TI_ETICHETTE_NASCOSTE";

    /** Oltre questo scostamento (metri, cioe' unita' di disegno) l'etichetta
     * non si capisce piu' a chi si riferisce: meglio nasconderla. */
    private static final double SPOSTAMENTO_MASSIMO = 2.5;

    /** Larghezza di una cifra rispetto all'altezza del testo. In Arial la cifra
     * avanza di 0.556 em e l'altezza del gruppo 40 e' l'altezza della
     * maiuscola, 0.729 em (lo stesso rapporto usato dal lato QGIS in
     * simbologia.py): 0.556/0.729 = 0.762. */
    private static final double LARGHEZZA_CARATTERE = 0.762;

    /** Un margine di respiro attorno al riquadro, in frazione dell'altezza:
     * due scritte che si sfiorano sono gia' illeggibili. */
    private static final double MARGINE = 0.15;

    static {
        PRIORITA_ETICHETTA.put("TI_NUMERO_PCGIURISDIZIONALE", 100);
        PRIORITA_ETICHETTA.put("TI_PF_AUSILIARIO_TXT", 70);
        PRIORITA_ETICHETTA.put("TI_NUMERO_PUNTO_DI_CONFINE", 50);
        PRIORITA_ETICHETTA.put("TI_NUMERO_PUNTO_SINGOLO_CS", 40);
        PRIORITA_ETICHETTA.put("TI_NUMERO_PUNTO_SINGOLO_OS", 30);
        PRIORITA_ETICHETTA.put("TI_PUNTO_QUOTATO", 20);

        Collections.addAll(LAYER_OSTACOLO, "TI_NUMERO_NE", "TI_NUMERO_OGGETTO", "TI_NOME_EDIFICIO",
                "TI_NOME_LOCALITA_CAP", "01619", "01219", "01229", "01919", "01139", "01119", "01129");

        // Materializzato sul terreno: cippo, termine artificiale, bullone, tubo,
        // palo. Scolpito: c'e' ma e' meno evidente. Non materializzato: sul
        // terreno non c'e' niente, ed e' anche il caso piu' numeroso (38 754 su
        // 75 293), quindi e' giusto che sia il primo a cedere.
        PRIORITA_BLOCCO.put("GPSTE", 9);
        PRIORITA_BLOCCO.put("GPKST", 9);
        PRIORITA_BLOCCO.put("GPBOL", 9);
        PRIORITA_BLOCCO.put("GPROH", 8);
        PRIORITA_BLOCCO.put("GPPFA", 8);
        PRIORITA_BLOCCO.put("GPKRZ", 5);
        PRIORITA_BLOCCO.put("GPUV", 0);
        Collections.addAll(LAYER_SIMBOLO_CONFINE, "01651", "01652", "01653", "01654", "01655", "01656", "01657");
    }

    private AntiCollisioneEtichette() {
    }

    /** Quanto si e' dovuto intervenire. */
    public static final class Esito {
        public final int totali;
        public final int spostate;
        public final int nascoste;

        Esito(int totali, int spostate, int nascoste) {
            this.totali = totali;
            this.spostate = spostate;
            this.nascoste = nascoste;
        }
    }

    /** Un'etichetta candidata, con la sua posizione di partenza. */
    private static final class Etichetta {
        int ordine;              // n. progressivo fra le etichette mobili nel file
        String layer;
        double x;
        double y;
        double altezza;
        int caratteri;
        int hali;
        int vali;
        double priorita;
        double nuovaX;
        double nuovaY;
        boolean nascosta;
    }

    private static final class Riquadro {
        double x0, y0, x1, y1;

        Riquadro(double x0, double y0, double x1, double y1) {
            this.x0 = x0;
            this.y0 = y0;
            this.x1 = x1;
            this.y1 = y1;
        }

        boolean tocca(Riquadro altro) {
            return this.x0 < altro.x1 && altro.x0 < this.x1 && this.y0 < altro.y1 && altro.y0 < this.y1;
        }
    }

    /** Indice a griglia: le etichette sono decine di migliaia, il confronto di
     * tutte con tutte sarebbe di ore. */
    private static final class Griglia {
        private static final double LATO = 4.0;
        private final Map<Long, List<Riquadro>> celle = new HashMap<Long, List<Riquadro>>();

        private static long chiave(int x, int y) {
            return (long)x << 32 ^ (long)y & 0xFFFFFFFFL;
        }

        boolean libero(Riquadro riquadro) {
            for (int gx = (int)Math.floor(riquadro.x0 / LATO); gx <= (int)Math.floor(riquadro.x1 / LATO); ++gx) {
                for (int gy = (int)Math.floor(riquadro.y0 / LATO); gy <= (int)Math.floor(riquadro.y1 / LATO); ++gy) {
                    List<Riquadro> list = this.celle.get(chiave(gx, gy));
                    if (list == null) continue;
                    for (Riquadro altro : list) {
                        if (!riquadro.tocca(altro)) continue;
                        return false;
                    }
                }
            }
            return true;
        }

        void occupa(Riquadro riquadro) {
            for (int gx = (int)Math.floor(riquadro.x0 / LATO); gx <= (int)Math.floor(riquadro.x1 / LATO); ++gx) {
                for (int gy = (int)Math.floor(riquadro.y0 / LATO); gy <= (int)Math.floor(riquadro.y1 / LATO); ++gy) {
                    long k = chiave(gx, gy);
                    List<Riquadro> list = this.celle.get(k);
                    if (list == null) {
                        list = new ArrayList<Riquadro>(4);
                        this.celle.put(k, list);
                    }
                    list.add(riquadro);
                }
            }
        }
    }

    /**
     * Legge il DXF, decide, e lo riscrive. Due passate in streaming e non un
     * caricamento in memoria: i file veri sono da centinaia di MB.
     */
    public static Esito risolvi(File file, int precision) throws IOException {
        List<Etichetta> etichette = new ArrayList<Etichetta>();
        Griglia griglia = new Griglia();
        List<double[]> simboli = new ArrayList<double[]>();
        Map<Integer, String> bloccoDiSimbolo = new HashMap<Integer, String>();
        raccogli(file, etichette, griglia, simboli, bloccoDiSimbolo);
        assegnaPriorita(etichette, simboli, bloccoDiSimbolo);
        int[] conti = disponi(etichette, griglia);
        riscrivi(file, etichette, precision);
        return new Esito(etichette.size(), conti[0], conti[1]);
    }

    /** Prima passata: le scritte mobili, quelle fisse (che entrano subito nella
     * griglia come ostacoli) e i simboli dei punti di confine. */
    private static void raccogli(File file, List<Etichetta> etichette, Griglia griglia, List<double[]> simboli, Map<Integer, String> bloccoDiSimbolo) throws IOException {
        BufferedReader bufferedReader = new BufferedReader(new InputStreamReader(new FileInputStream(file), "ISO-8859-1"));
        try {
            String tipo = null;
            Map<String, String> gruppi = new HashMap<String, String>();
            int ordine = 0;
            while (true) {
                String riga = bufferedReader.readLine();
                if (riga == null) {
                    break;
                }
                String valore = bufferedReader.readLine();
                if (valore == null) {
                    break;
                }
                String codice = riga.trim();
                String v = valore.trim();
                if (!codice.equals("0")) {
                    if (tipo != null && !gruppi.containsKey(codice)) {
                        gruppi.put(codice, v);
                    }
                    continue;
                }
                ordine = chiudi(tipo, gruppi, etichette, griglia, simboli, bloccoDiSimbolo, ordine);
                gruppi.clear();
                tipo = v.equals("TEXT") || v.equals("INSERT") ? v : null;
            }
            chiudi(tipo, gruppi, etichette, griglia, simboli, bloccoDiSimbolo, ordine);
        }
        finally {
            bufferedReader.close();
        }
    }

    private static int chiudi(String tipo, Map<String, String> gruppi, List<Etichetta> etichette, Griglia griglia, List<double[]> simboli, Map<Integer, String> bloccoDiSimbolo, int ordine) {
        if (tipo == null) {
            return ordine;
        }
        String layer = gruppi.get("8");
        if (layer == null) {
            return ordine;
        }
        if (tipo.equals("INSERT")) {
            if (LAYER_SIMBOLO_CONFINE.contains(layer)) {
                bloccoDiSimbolo.put(simboli.size(), gruppi.get("2"));
                simboli.add(new double[]{numero(gruppi.get("10")), numero(gruppi.get("20"))});
            }
            return ordine;
        }
        boolean mobile = PRIORITA_ETICHETTA.containsKey(layer);
        if (!mobile && !LAYER_OSTACOLO.contains(layer)) {
            return ordine;
        }
        String testo = gruppi.get("1");
        Etichetta etichetta = new Etichetta();
        etichetta.layer = layer;
        etichetta.x = numero(gruppi.get("10"));
        etichetta.y = numero(gruppi.get("20"));
        etichetta.altezza = gruppi.containsKey("40") ? numero(gruppi.get("40")) : 0.9;
        etichetta.caratteri = testo == null ? 0 : testo.length();
        etichetta.hali = gruppi.containsKey("72") ? (int)numero(gruppi.get("72")) : 0;
        etichetta.vali = gruppi.containsKey("73") ? (int)numero(gruppi.get("73")) : 0;
        if (mobile) {
            // Anche una scritta vuota prende il suo numero progressivo: la
            // seconda passata conta le entita' sul layer, non i testi non
            // vuoti, e i due conteggi devono coincidere o si sposta l'etichetta
            // sbagliata. Larghezza zero, quindi non da' comunque fastidio.
            etichetta.ordine = ordine++;
            etichette.add(etichetta);
        } else if (etichetta.caratteri > 0) {
            griglia.occupa(riquadro(etichetta, etichetta.x, etichetta.y));
        }
        return ordine;
    }

    private static double numero(String string) {
        if (string == null) {
            return 0.0;
        }
        try {
            return Double.parseDouble(string);
        }
        catch (NumberFormatException numberFormatException) {
            return 0.0;
        }
    }

    /** Il numero di un punto di confine eredita il peso del punto: per saperlo
     * serve sapere di che punto si tratta, e l'unico legame nel DXF e' la
     * vicinanza. E' lo stesso abbinamento che regge la misura da cui e' nato
     * questo passaggio: lo scostamento mediano e' 1.41 m e il punto piu' vicino
     * e' quasi sempre l'unico entro il raggio. */
    private static void assegnaPriorita(List<Etichetta> etichette, List<double[]> simboli, Map<Integer, String> bloccoDiSimbolo) {
        double lato = 5.0;
        Map<Long, List<Integer>> indice = new HashMap<Long, List<Integer>>();
        for (int i = 0; i < simboli.size(); ++i) {
            double[] p = simboli.get(i);
            long k = (long)(int)Math.floor(p[0] / lato) << 32 ^ (long)(int)Math.floor(p[1] / lato) & 0xFFFFFFFFL;
            List<Integer> list = indice.get(k);
            if (list == null) {
                list = new ArrayList<Integer>(4);
                indice.put(k, list);
            }
            list.add(i);
        }
        for (Etichetta etichetta : etichette) {
            etichetta.priorita = PRIORITA_ETICHETTA.get(etichetta.layer).intValue();
            if (!etichetta.layer.equals("TI_NUMERO_PUNTO_DI_CONFINE")) continue;
            int gx = (int)Math.floor(etichetta.x / lato);
            int gy = (int)Math.floor(etichetta.y / lato);
            double miglioreDistanza = Double.MAX_VALUE;
            String migliore = null;
            for (int dx = -1; dx <= 1; ++dx) {
                for (int dy = -1; dy <= 1; ++dy) {
                    List<Integer> list = indice.get((long)(gx + dx) << 32 ^ (long)(gy + dy) & 0xFFFFFFFFL);
                    if (list == null) continue;
                    for (Integer i : list) {
                        double[] p = simboli.get(i);
                        double d = Math.hypot(etichetta.x - p[0], etichetta.y - p[1]);
                        if (!(d < miglioreDistanza)) continue;
                        miglioreDistanza = d;
                        migliore = bloccoDiSimbolo.get(i);
                    }
                }
            }
            if (migliore == null || !PRIORITA_BLOCCO.containsKey(migliore)) continue;
            etichetta.priorita += PRIORITA_BLOCCO.get(migliore).doubleValue();
        }
    }

    /** Il riquadro occupato dalla scritta, tenuto conto dell'allineamento: il
     * punto scritto nel DXF e' l'angolo solo quando HAli/VAli sono a zero. */
    private static Riquadro riquadro(Etichetta etichetta, double x, double y) {
        double larghezza = LARGHEZZA_CARATTERE * etichetta.altezza * etichetta.caratteri;
        double margine = MARGINE * etichetta.altezza;
        double dx = 0.0;
        if (etichetta.hali == 1 || etichetta.hali == 4) {
            dx = -larghezza / 2.0;
        } else if (etichetta.hali == 2) {
            dx = -larghezza;
        }
        double dy = 0.0;
        if (etichetta.vali == 1) {
            dy = -etichetta.altezza / 2.0;
        } else if (etichetta.vali == 2) {
            dy = -etichetta.altezza;
        }
        return new Riquadro(x + dx - margine, y + dy - margine,
                x + dx + larghezza + margine, y + dy + etichetta.altezza + margine);
    }

    /** Chi ha priorita' piu' alta si serve per primo e quindi resta dov'e'. A
     * parita' di priorita' vince chi viene prima nel file, cosi' il risultato
     * non dipende dall'ordinamento. */
    private static int[] disponi(List<Etichetta> etichette, Griglia griglia) {
        List<Etichetta> ordinate = new ArrayList<Etichetta>(etichette);
        Collections.sort(ordinate, new Comparator<Etichetta>(){

            @Override
            public int compare(Etichetta a, Etichetta b) {
                if (a.priorita != b.priorita) {
                    return a.priorita > b.priorita ? -1 : 1;
                }
                return a.ordine - b.ordine;
            }
        });
        int spostate = 0;
        int nascoste = 0;
        for (Etichetta etichetta : ordinate) {
            etichetta.nuovaX = etichetta.x;
            etichetta.nuovaY = etichetta.y;
            Riquadro riquadro = riquadro(etichetta, etichetta.x, etichetta.y);
            if (griglia.libero(riquadro)) {
                griglia.occupa(riquadro);
                continue;
            }
            boolean sistemata = false;
            for (double passo = 1.0; passo <= 2.5 && !sistemata; passo += 0.75) {
                double raggio = passo * etichetta.altezza;
                if (raggio > SPOSTAMENTO_MASSIMO) break;
                for (int direzione = 0; direzione < 8 && !sistemata; ++direzione) {
                    double angolo = Math.PI / 4 * (double)direzione;
                    double nx = etichetta.x + raggio * Math.cos(angolo);
                    double ny = etichetta.y + raggio * Math.sin(angolo);
                    Riquadro prova = riquadro(etichetta, nx, ny);
                    if (!griglia.libero(prova)) continue;
                    griglia.occupa(prova);
                    etichetta.nuovaX = nx;
                    etichetta.nuovaY = ny;
                    sistemata = true;
                    ++spostate;
                }
            }
            if (sistemata) continue;
            etichetta.nascosta = true;
            ++nascoste;
        }
        return new int[]{spostate, nascoste};
    }

    /** Seconda passata: riscrive solo le etichette toccate. Le coordinate di un
     * TEXT stanno in DUE punti - 10/20 (posizione) e 11/21 (allineamento) - e
     * DxfWriter.text2Dxf le scrive uguali: vanno cambiate tutte e due, se no
     * AutoCAD disegna la scritta a un posto e la allinea a un altro. */
    private static void riscrivi(File file, List<Etichetta> etichette, int precision) throws IOException {
        Map<Integer, Etichetta> daCambiare = new HashMap<Integer, Etichetta>();
        for (Etichetta etichetta : etichette) {
            if (!etichetta.nascosta && etichetta.nuovaX == etichetta.x && etichetta.nuovaY == etichetta.y) continue;
            daCambiare.put(etichetta.ordine, etichetta);
        }
        if (daCambiare.isEmpty()) {
            return;
        }
        File temporaneo = new File(file.getParentFile(), file.getName() + ".etichette.tmp");
        BufferedReader bufferedReader = new BufferedReader(new InputStreamReader(new FileInputStream(file), "ISO-8859-1"));
        BufferedWriter bufferedWriter = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(temporaneo), "ISO-8859-1"));
        try {
            String tipo = null;
            int ordine = 0;
            Etichetta corrente = null;
            boolean mobile = false;
            while (true) {
                String riga = bufferedReader.readLine();
                if (riga == null) {
                    break;
                }
                String valore = bufferedReader.readLine();
                if (valore == null) {
                    bufferedWriter.write(riga);
                    bufferedWriter.write("\n");
                    break;
                }
                String codice = riga.trim();
                String v = valore.trim();
                if (codice.equals("0")) {
                    tipo = v;
                    corrente = null;
                    mobile = false;
                } else if (codice.equals("8") && tipo != null && tipo.equals("TEXT") && PRIORITA_ETICHETTA.containsKey(v)) {
                    // Il layer e' il primo gruppo utile dell'entita': e' qui che
                    // si assegna il numero progressivo, con la stessa regola
                    // della prima passata.
                    mobile = true;
                    corrente = daCambiare.get(ordine);
                    ++ordine;
                    if (corrente != null && corrente.nascosta) {
                        bufferedWriter.write(riga);
                        bufferedWriter.write("\n");
                        bufferedWriter.write(LAYER_NASCOSTE);
                        bufferedWriter.write("\n");
                        continue;
                    }
                }
                if (corrente != null && !corrente.nascosta &&
                        (codice.equals("10") || codice.equals("11") || codice.equals("20") || codice.equals("21"))) {
                    double nuovo = codice.equals("10") || codice.equals("11") ? corrente.nuovaX : corrente.nuovaY;
                    bufferedWriter.write(riga);
                    bufferedWriter.write("\n");
                    bufferedWriter.write(valoreFormattato(Integer.parseInt(codice), nuovo, precision));
                    bufferedWriter.write("\n");
                    continue;
                }
                bufferedWriter.write(riga);
                bufferedWriter.write("\n");
                bufferedWriter.write(valore);
                bufferedWriter.write("\n");
            }
        }
        finally {
            bufferedWriter.close();
            bufferedReader.close();
        }
        if (!file.delete() || !temporaneo.renameTo(file)) {
            throw new IOException("AntiCollisioneEtichette: impossibile sostituire " + file);
        }
    }

    /** Solo la riga del valore, formattata esattamente come la scriverebbe
     * DxfWriter: stesso numero di decimali, cosi' la coordinata spostata e'
     * indistinguibile da una scritta al primo giro. */
    private static String valoreFormattato(int codice, double valore, int precision) {
        String string = DxfUtil.toString(codice, valore, precision);
        return string.substring(string.indexOf(10) + 1).trim();
    }
}
