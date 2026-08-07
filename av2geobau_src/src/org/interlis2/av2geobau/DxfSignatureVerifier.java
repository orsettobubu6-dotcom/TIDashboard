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
package org.interlis2.av2geobau;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

public class DxfSignatureVerifier {
    private static final String FIRMA = "Peverelli";

    private static String sha256Hex(String string) throws NoSuchAlgorithmException {
        MessageDigest messageDigest = MessageDigest.getInstance("SHA-256");
        byte[] byArray = messageDigest.digest(string.getBytes(StandardCharsets.UTF_8));
        StringBuilder stringBuilder = new StringBuilder();
        for (byte by : byArray) {
            String string2 = Integer.toHexString(0xFF & by);
            if (string2.length() == 1) {
                stringBuilder.append('0');
            }
            stringBuilder.append(string2);
        }
        return stringBuilder.toString();
    }

    public static boolean verificaProprietaDxf(String string) {
        try {
            String string2 = new String(Files.readAllBytes(Paths.get(string, new String[0])), StandardCharsets.UTF_8);
            String string3 = DxfSignatureVerifier.sha256Hex(FIRMA);
            if (string2.contains(string3)) {
                System.out.println("VERIFICA RIUSCITA: il file contiene la firma cifrata di Peverelli.");
                System.out.println("Hash atteso (ID_Creatore): " + string3);
                return true;
            }
            System.out.println("La firma di Peverelli non e' presente in questo file.");
            return false;
        }
        catch (IOException | NoSuchAlgorithmException exception) {
            System.err.println("Impossibile leggere o elaborare il file: " + exception.getMessage());
            return false;
        }
    }

    public static void main(String[] stringArray) {
        boolean bl;
        if (stringArray.length != 1) {
            System.err.println("Uso: java org.interlis2.av2geobau.DxfSignatureVerifier <percorso.dxf>");
            System.exit(2);
        }
        System.exit((bl = DxfSignatureVerifier.verificaProprietaDxf(stringArray[0])) ? 0 : 1);
    }
}

