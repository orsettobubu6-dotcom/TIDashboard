/*
 * Fork ticinese di av2geobau (modello MD01MUTI7MN95).
 *
 * ORIGINE DI QUESTO FILE: il sorgente originale e' andato perso (viveva in una
 * cartella temporanea, poi ripulita) ed e' stato RECUPERATO decompilando
 * av2geobau_ti.jar con CFR 0.152, correggendo a mano gli artefatti di
 * decompilazione. Conseguenze pratiche:
 *   - i nomi delle variabili locali NON sono quelli originali (n, string3,
 *     iomObject2, ...): la compilazione li scarta;
 *   - i commenti originali sono persi; quelli presenti sono stati riscritti a
 *     posteriori e coprono solo le decisioni essenziali;
 *   - la logica invece e' integrale e verificata: il jar ricompilato da questo
 *     sorgente produce un DXF byte-identico a quello del jar originale su un
 *     file ITF reale da 209 MB.
 * Dettagli e correzioni applicate: vedi RECUPERO.md nella radice del progetto.
 */
package org.interlis2.av2geobau.impl;

import java.text.DecimalFormat;
import java.text.DecimalFormatSymbols;
import java.util.Locale;

public class DxfUtil {
    private static final DecimalFormatSymbols dfs = new DecimalFormatSymbols(Locale.US);
    private static final DecimalFormat[] decimalFormats = new DecimalFormat[]{new DecimalFormat("#0", dfs), new DecimalFormat("#0.0", dfs), new DecimalFormat("#0.00", dfs), new DecimalFormat("#0.000", dfs), new DecimalFormat("#0.0000", dfs), new DecimalFormat("#0.00000", dfs), new DecimalFormat("#0.000000", dfs), new DecimalFormat("#0.0000000", dfs), new DecimalFormat("#0.00000000", dfs), new DecimalFormat("#0.000000000", dfs), new DecimalFormat("#0.0000000000", dfs), new DecimalFormat("#0.00000000000", dfs), new DecimalFormat("#0.000000000000", dfs)};
    private static long handleCounter = 256L;

    private DxfUtil() {
    }

    public static synchronized String nextHandle() {
        return Long.toHexString(handleCounter++).toUpperCase();
    }

    public static synchronized String currentHandleHex8() {
        return String.format("%08X", handleCounter);
    }

    private static String int34car(int n) {
        if (n < 10) {
            return "  " + Integer.toString(n);
        }
        if (n < 100) {
            return " " + Integer.toString(n);
        }
        return Integer.toString(n);
    }

    /** ATTENZIONE - TRONCA i valori oltre le 6 cifre: la substring qui sotto
     * prende solo gli ULTIMI 6 caratteri, senza alcun errore ne' avviso (es.
     * 33554572 diventa "554572"). E' il formato storico dei group code interi
     * del DXF, largo 6 caratteri. Per qualunque valore che possa superare le 6
     * cifre - trasparenza (440), true color (420), handle - NON usare
     * toString(int,int): usare l'overload toString(int,String) passando
     * Integer.toString(valore), che scrive il valore integrale (vedi
     * hatch2Dxf in DxfWriter). */
    private static String int6car(int n) {
        String string = "     " + Integer.toString(n);
        return string.substring(string.length() - 6, string.length());
    }

    public static String toString(int n, String string) {
        return DxfUtil.int34car(n) + "\r\n" + string + "\r\n";
    }

    public static String toString(int n, int n2) {
        return DxfUtil.int34car(n) + "\r\n" + DxfUtil.int6car(n2) + "\r\n";
    }

    public static String toString(int n, float f, int n2) {
        if (!Double.isFinite(f)) {
            throw new IllegalArgumentException("unexpeced value " + f);
        }
        return DxfUtil.int34car(n) + "\r\n" + decimalFormats[n2].format(f) + "\r\n";
    }

    public static String toString(int n, double d, int n2) {
        if (!Double.isFinite(d)) {
            throw new IllegalArgumentException("unexpeced value " + d);
        }
        return DxfUtil.int34car(n) + "\r\n" + decimalFormats[n2].format(d) + "\r\n";
    }

    public static String toString(int n, Object object) {
        if (object instanceof String) {
            return DxfUtil.toString(n, (String)object);
        }
        if (object instanceof Integer) {
            // .intValue() ESPLICITO (confermato nel bytecode originale:
            // Integer.intValue() + invokestatic toString:(II)). Senza, il
            // parametro resta un Integer e la risoluzione degli overload
            // sceglie toString(int,Object) - cioe' QUESTO stesso metodo:
            // ricorsione infinita (StackOverflowError). Perso in decompilazione.
            return DxfUtil.toString(n, ((Integer)object).intValue());
        }
        if (object instanceof Float) {
            return DxfUtil.toString(n, ((Float)object).floatValue(), 3);
        }
        if (object instanceof Double) {
            return DxfUtil.toString(n, ((Double)object).doubleValue(), 6);
        }
        return DxfUtil.toString(n, object.toString());
    }
}

