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

import ch.ehi.basics.logging.EhiLogger;
import ch.ehi.basics.logging.LogListener;
import ch.ehi.basics.logging.StdListener;
import ch.ehi.basics.settings.Settings;
import ch.interlis.ili2c.Ili2c;
import ch.interlis.ili2c.Ili2cException;
import ch.interlis.ili2c.config.Configuration;
import ch.interlis.ili2c.metamodel.Ili2cMetaAttrs;
import ch.interlis.ili2c.metamodel.TransferDescription;
import ch.interlis.ilirepository.IliManager;
import ch.interlis.iom.IomObject;
import ch.interlis.iom_j.itf.ItfReader2;
import ch.interlis.iox.EndTransferEvent;
import ch.interlis.iox.IoxEvent;
import ch.interlis.iox.IoxException;
import ch.interlis.iox.ObjectEvent;
import ch.interlis.iox_j.IoxUtility;
import ch.interlis.iox_j.filter.TranslateToOrigin;
import ch.interlis.iox_j.logging.FileLogger;
import ch.interlis.iox_j.logging.StdLogger;
import ch.interlis.iox_j.statistics.IoxStatistics;
import com.vividsolutions.jts.geom.Geometry;
import com.vividsolutions.jts.io.ParseException;
import com.vividsolutions.jts.io.WKTReader;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.FilterWriter;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import java.io.RandomAccessFile;
import java.io.Serializable;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.interlis2.av2geobau.Main;
import org.interlis2.av2geobau.impl.DxfUtil;
import org.interlis2.av2geobau.impl.DxfWriter;
import org.interlis2.av2geobau.impl.Mapper;

public class Av2geobau {
    private long handSeedValueOffset = -1L;
    public static final String DM01_IT = "MD01MUCH24MN95I";
    public static final String DM01_FR = "MD01MOCH24MN95F";
    public static final String DM01_DE = "DM01AVCH24LV95D";
    public static final String MD01_TI = "MD01MUTI7MN95";
    private static final double MIN_DASH_LENGTH = 0.001;
    private static final Object[][] GDV_LINETYPES = new Object[][]{{"LANDSGRENZEN", "Confine Nazionale", new double[]{4.0, -2.0, 4.0, -2.0, 4.0, -2.0}}, {"KANTONSGRENZEN", "Confine Cantonale", new double[]{3.5, -1.5, 3.5, -1.5, 3.5, -1.5}}, {"BEZIRKSGRENZEN", "Confine Distrettuale", new double[]{4.0, -1.0, 1.0, -1.0, 1.0, -1.0}}, {"GEMEINDEGRENZEN", "Confine Comunale", new double[]{4.0, -1.0, 1.0, -1.0}}, {"ZONENGRENZEN", "Confine di zona", new double[]{0.0, -1.5}}, {"LIEGENSCHAFTSGRENZEN", "Confine di proprieta'", new double[0]}, {"STREITIGE_GRENZEN", "Confine litigioso", new double[]{5.0, -1.5, 0.0, -1.5}}, {"PROVISORISCHE_GRENZEN", "Confine provvisorio", new double[]{8.0, -1.5, 0.0, -1.5, 2.0, -1.5}}, {"DIENSTBARKEITSGRENZEN", "Confine di servitu'", new double[]{3.0, -1.5, 0.0, -1.5}}};
    private static final Object[][] GENERIC_LINETYPES = new Object[][]{{"LIMITE_DEL_FOGLIO", "Limite del foglio", new double[]{1.0, -1.0}}, {"PUNTEGGIATO", "Punteggiato", new double[]{0.5, -0.5}}, {"MISTO1", "Tratto misto 6.5/1.0/1.0", new double[]{6.5, -1.0, 1.0, -1.0, 1.0, -1.0}}, {"MISTO2", "Tratto misto 10.0/1.0/1.8/1.0", new double[]{10.0, -1.0, 1.8, -1.0}}, {"INTERROTTO", "Interrotto 2.5/0.7", new double[]{2.5, -0.7}}, {"INTERROTTO1", "Interrotto1 1.5/0.5", new double[]{1.5, -0.5}}, {"INTERROTTO2", "Interrotto2 1.0/0.7", new double[]{1.0, -0.7}}, {"INTERROTTO3", "Interrotto3 4.0/1.0", new double[]{4.0, -1.0}}, {"CONFINE_INCOMPLETO", "Confine incompleto 1.5/1.0", new double[]{1.5, -1.0}}, {"LIMITE_BOSCO_LEGALE", "Limite legale del bosco 3.5/1.0", new double[]{3.5, -1.0}}, {"1100400000", "-- - --   (CONF.GIUR.-COMUNALE)", new double[]{3.5, -1.0, 1.0, -1.0}}, {"0200000000", "- - - - - (LIMITE COPERTURA SUOLO)", new double[]{1.5, -0.5}}};
    private static final String[][] LAYER_LINETYPES = new String[][]{{"01841", "LANDSGRENZEN"}, {"01831", "KANTONSGRENZEN"}, {"01821", "BEZIRKSGRENZEN"}, {"01811", "1100400000"}, {"01611", "LIEGENSCHAFTSGRENZEN"}, {"01631", "INTERROTTO"}, {"TI_MARGINE_FOGLIO", "LIMITE_DEL_FOGLIO"}, {"TI_GRADO_TOLLERANZA", "PUNTEGGIATO"}, {"TI_ZONA_MOVIMENTO", "PUNTEGGIATO"}, {"RIPARTIZIONE_PIANI", "0200000000"}, {"TI_LIMITE_BOSCO_LEGALE", "LIMITE_BOSCO_LEGALE"}};
    /** TUTTI i nomi di layer usati da Mapper.java. Devono essere dichiarati
     * nella tabella LAYER anche quando non hanno un linetype proprio: in
     * precedenza la tabella era costruita solo da LAYER_LINETYPES (11 voci) e
     * la maggior parte dei layer realmente usati nelle ENTITIES non risultava
     * dichiarata - causa probabile dei simboli "mancanti" (punti fissi, punti
     * singoli, ecc.) nei lettori DXF che non creano da soli i layer non
     * dichiarati. */
    private static final String[] ALL_LAYERS = new String[]{"01111", "01112", "01119", "01121", "01122", "01129", "01131", "01132", "01133", "01134", "01139", "01141", "01149", "01151", "01159", "01161", "01169", "01211", "01219", "01221", "01222", "01223", "01224", "01225", "01229", "01231", "01232", "01233", "01234", "01235", "01236", "01241", "01242", "01249", "01251", "01252", "01261", "01263", "01264", "01265", "01311", "01312", "01313", "01314", "01315", "01316", "01321", "01322", "01331", "01332", "01334", "01335", "01336", "01339", "01341", "01342", "01343", "01351", "01352", "01353", "01361", "01363", "01364", "01370", "01519", "01529", "01539", "01611", "01619", "01621", "01629", "01631", "01639", "01641", "01649", "01651", "01652", "01653", "01654", "01655", "01656", "01657", "01712", "01811", "01812", "01821", "01831", "01841", "01911", "01919", "TI_GRADO_TOLLERANZA", "TI_LIMITE_BOSCO_LEGALE", "TI_MARGINE_FOGLIO", "TI_NOME_EDIFICIO", "TI_NOME_LOCALITA_CAP", "TI_NUMERO_NE", "TI_NUMERO_OGGETTO", "TI_NUMERO_OS", "TI_PF_AUSILIARIO", "TI_PF_AUSILIARIO_TXT", "TI_PUNTO_QUOTATO", "TI_PUNTO_SINGOLO_CS", "TI_PUNTO_SINGOLO_OS", "TI_ZONA_MOVIMENTO", "TI_NUMERO_PUNTO_DI_CONFINE", "TI_NUMERO_PUNTO_SINGOLO_CS", "TI_NUMERO_PUNTO_SINGOLO_OS", "TI_NUMERO_PCGIURISDIZIONALE", "TI_LEGENDA"};
    private static final Map<String, Integer> LAYER_COLOR_OVERRIDES = new HashMap<String, Integer>();
    private static final String[] BLOCK_NAMES;
    private final Map<String, String> blockRecordHandles = new LinkedHashMap<String, String>();
    private static final double[] BACIDR_SPLINE_UPPER_KNOTS;
    private static final double[][] BACIDR_SPLINE_UPPER_CTRL;
    private static final double[][] BACIDR_SPLINE_UPPER_FIT;
    private static final double[] BACIDR_SPLINE_LOWER_KNOTS;
    private static final double[][] BACIDR_SPLINE_LOWER_CTRL;
    private static final double[][] BACIDR_SPLINE_LOWER_FIT;
    private static final Set<String> FRONT_LAYERS;
    public static final String SETTING_DEFAULT_ILIDIRS = "%ITF_DIR;http://models.interlis.ch/;%JAR_DIR/ilimodels";
    public static final String SETTING_ILIDIRS = "org.interlis2.av2geobau.ilidirs";
    public static final String SETTING_APPHOME = "org.interlis2.av2geobau.appHome";
    public static final String SETTING_CONFIGFILE = "org.interlis2.av2geobau.configfile";
    public static final String SETTING_PERIMETER = "org.interlis2.av2geobau.perimeter";
    public static final String SETTING_LOGFILE = "org.interlis2.av2geobau.log";
    public static final String ITF_DIR = "%ITF_DIR";
    public static final String JAR_DIR = "%JAR_DIR";

    public static boolean convert(File file, File file2, Settings settings) {
        return new Av2geobau().doConversion(file, file2, settings);
    }

    /*
     * WARNING - Removed try catching itself - possible behaviour change.
     */
    public boolean doConversion(File file, File file2, Settings settings) {
        boolean bl;
        StdLogger stdLogger;
        block55: {
            boolean bl2;
            TransferDescription transferDescription;
            Geometry geometry;
            FileLogger fileLogger;
            block51: {
                boolean bl3;
                block52: {
                    if (file == null) {
                        EhiLogger.logError((String)"no ITF file given");
                        return false;
                    }
                    if (file2 == null) {
                        EhiLogger.logError((String)"no DXF file given");
                        return false;
                    }
                    if (settings == null) {
                        settings = new Settings();
                    }
                    String string = settings.getValue(SETTING_LOGFILE);
                    fileLogger = null;
                    stdLogger = null;
                    bl = false;
                    if (string != null) {
                        fileLogger = new FileLogger(new File(string));
                        EhiLogger.getInstance().addListener((LogListener)fileLogger);
                    }
                    stdLogger = new StdLogger(string);
                    EhiLogger.getInstance().addListener((LogListener)stdLogger);
                    EhiLogger.getInstance().removeListener((LogListener)StdListener.getInstance());
                    String string2 = settings.getValue(SETTING_CONFIGFILE);
                    String string3 = settings.getValue(SETTING_PERIMETER);
                    String string4 = settings.getValue(SETTING_APPHOME);
                    EhiLogger.logState((String)("av2geobau-" + Main.getVersion()));
                    EhiLogger.logState((String)("ili2c-" + Ili2c.getVersion()));
                    EhiLogger.logState((String)("iox-ili-" + IoxUtility.getVersion()));
                    EhiLogger.logState((String)("maxMemory " + Runtime.getRuntime().maxMemory() / 1024L + " KB"));
                    EhiLogger.logState((String)("itfFile <" + file.getPath() + ">"));
                    EhiLogger.logState((String)("dxfFile <" + file2.getPath() + ">"));
                    if (string2 != null) {
                        EhiLogger.logState((String)("configFile <" + string2 + ">"));
                    }
                    geometry = null;
                    if (string3 != null) {
                        EhiLogger.logState((String)("perimeter <" + string3 + ">"));
                        try {
                            geometry = new WKTReader().read(string3);
                        }
                        catch (ParseException parseException) {
                            throw new IllegalArgumentException("failed to parse perimeter", parseException);
                        }
                    }
                    transferDescription = null;
                    String string5 = ch.interlis.iox_j.utility.IoxUtility.getModelFromXtf(file.getPath());
                    bl2 = string5.equals(MD01_TI);
                    if (!(string5.equals(DM01_DE) || string5.equals(DM01_FR) || string5.equals(DM01_IT) || bl2)) {
                        throw new IllegalArgumentException("only DM01AVCH24LV95D, MD01MOCH24MN95F, MD01MUCH24MN95I or MD01MUTI7MN95 supported");
                    }
                    String[] stringArray = null;
                    Ili2cMetaAttrs ili2cMetaAttrs = new Ili2cMetaAttrs();
                    if (bl2) {
                        stringArray = new String[]{MD01_TI};
                    } else if (string5.equals(DM01_FR) || string5.equals(DM01_IT)) {
                        ili2cMetaAttrs.setMetaAttrValue(string5, "ili2c.translationOf", DM01_DE);
                        stringArray = new String[]{DM01_DE, string5};
                    } else {
                        stringArray = new String[]{DM01_DE};
                    }
                    transferDescription = Av2geobau.compileIli(stringArray, null, file.getAbsoluteFile().getParentFile().getAbsolutePath(), string4, settings, ili2cMetaAttrs);
                    if (transferDescription != null) break block51;
                    bl3 = false;
                    if (fileLogger == null) break block52;
                    fileLogger.close();
                    EhiLogger.getInstance().removeListener((LogListener)fileLogger);
                    fileLogger = null;
                }
                if (stdLogger != null) {
                    EhiLogger.getInstance().addListener((LogListener)StdListener.getInstance());
                    EhiLogger.getInstance().removeListener((LogListener)stdLogger);
                    stdLogger = null;
                }
                return bl3;
            }
            try {
                TranslateToOrigin translateToOrigin = null;
                if (!bl2) {
                    translateToOrigin = new TranslateToOrigin(transferDescription, settings);
                }
                EhiLogger.logState((String)"convert data...");
                IoxStatistics ioxStatistics = null;
                try {
                    Object object;
                    ioxStatistics = new IoxStatistics(transferDescription, settings);
                    ItfReader2 itfReader2 = new ItfReader2(file, true);
                    itfReader2.setModel(transferDescription);
                    ioxStatistics.setFilename(file.getPath());
                    CountingWriter countingWriter = new CountingWriter(new OutputStreamWriter((OutputStream)new FileOutputStream(file2), "ISO-8859-1"));
                    BufferedWriter bufferedWriter = new BufferedWriter(countingWriter);
                    Mapper mapper = new Mapper();
                    mapper.setPerimeter(geometry);
                    try {
                        String string;
                        IomObject iomObject;
                        this.writeOwnershipWatermark(bufferedWriter, file.getName());
                        this.writeHeader(bufferedWriter, countingWriter);
                        this.writeTables(bufferedWriter);
                        DxfWriter.modelSpaceHandle = this.blockRecordHandles.get("*Model_Space");
                        this.writeBlocks(bufferedWriter);
                        bufferedWriter.write(DxfUtil.toString(0, "SECTION"));
                        bufferedWriter.write(DxfUtil.toString(2, "ENTITIES"));
                        object = null;
                        do {
                            object = itfReader2.read();
                            ioxStatistics.add((IoxEvent)object);
                            if (translateToOrigin != null) {
                                object = translateToOrigin.filter((IoxEvent)object);
                            }
                            mapper.addInput((IoxEvent)object);
                            if (!(object instanceof ObjectEvent)) continue;
                            iomObject = mapper.getMappedObject();
                            while (iomObject != null) {
                                string = DxfWriter.feature2Dxf(iomObject);
                                bufferedWriter.write(string);
                                iomObject = mapper.getMappedObject();
                            }
                        } while (!(object instanceof EndTransferEvent));
                        iomObject = mapper.getMappedObject();
                        while (iomObject != null) {
                            string = DxfWriter.feature2Dxf(iomObject);
                            bufferedWriter.write(string);
                            iomObject = mapper.getMappedObject();
                        }
                        bufferedWriter.write(DxfUtil.toString(0, "ENDSEC"));
                        bufferedWriter.write(DxfUtil.toString(0, "SECTION"));
                        bufferedWriter.write(DxfUtil.toString(2, "OBJECTS"));
                        string = DxfUtil.nextHandle();
                        String string6 = DxfUtil.nextHandle();
                        bufferedWriter.write(DxfUtil.toString(0, "DICTIONARY"));
                        bufferedWriter.write(DxfUtil.toString(5, string));
                        bufferedWriter.write(DxfUtil.toString(330, "0"));
                        bufferedWriter.write(DxfUtil.toString(100, "AcDbDictionary"));
                        bufferedWriter.write(DxfUtil.toString(281, "1"));
                        bufferedWriter.write(DxfUtil.toString(3, "ACAD_GROUP"));
                        bufferedWriter.write(DxfUtil.toString(350, string6));
                        bufferedWriter.write(DxfUtil.toString(0, "DICTIONARY"));
                        bufferedWriter.write(DxfUtil.toString(5, string6));
                        bufferedWriter.write(DxfUtil.toString(330, string));
                        bufferedWriter.write(DxfUtil.toString(100, "AcDbDictionary"));
                        bufferedWriter.write(DxfUtil.toString(281, "1"));
                        bufferedWriter.write(DxfUtil.toString(0, "ENDSEC"));
                        bufferedWriter.write(DxfUtil.toString(0, "EOF"));
                    }
                    finally {
                        if (translateToOrigin != null) {
                            translateToOrigin.close();
                        }
                        if (itfReader2 != null) {
                            try {
                                itfReader2.close();
                            }
                            catch (IoxException ioxException) {
                                EhiLogger.logError((Throwable)ioxException);
                            }
                            itfReader2 = null;
                        }
                        if (mapper != null) {
                            mapper.close();
                            mapper = null;
                        }
                        if (bufferedWriter != null) {
                            ((Writer)bufferedWriter).close();
                            bufferedWriter = null;
                        }
                    }
                    // Correzione in-place del placeholder $HANDSEED col
                    // conteggio handle reale, noto solo ora a file chiuso.
                    // Deve avvenire PRIMA di reorderEntitiesForDrawOrder: quel
                    // metodo riscrive il file riga per riga normalizzando i
                    // "\r\n" dell'header in "\n", il che accorcia le righe e
                    // invalida ogni offset in byte calcolato prima.
                    if (this.handSeedValueOffset >= 0L) {
                        try {
                            object = new RandomAccessFile(file2, "rw");
                            try {
                                ((RandomAccessFile)object).seek(this.handSeedValueOffset);
                                ((RandomAccessFile)object).write(DxfUtil.currentHandleHex8().getBytes("ISO-8859-1"));
                            }
                            finally {
                                ((RandomAccessFile)object).close();
                            }
                        }
                        catch (IOException iOException) {
                            EhiLogger.logError((Throwable)iOException);
                        }
                    }
                    try {
                        this.reorderEntitiesForDrawOrder(file2);
                    }
                    catch (IOException iOException) {
                        EhiLogger.logError((Throwable)iOException);
                    }
                    try {
                        this.appendLegendBlock(file2, new File(file.getParentFile(), "legenda_manifest.txt"));
                    }
                    catch (IOException iOException) {
                        EhiLogger.logError((Throwable)iOException);
                    }
                    ioxStatistics.write2logger();
                    if (stdLogger.hasSeenErrors()) {
                        EhiLogger.logState((String)"...conversion failed");
                    } else {
                        EhiLogger.logState((String)"...conversion done");
                        bl = true;
                    }
                }
                catch (Throwable throwable) {
                    if (ioxStatistics != null) {
                        ioxStatistics.write2logger();
                    }
                    EhiLogger.logError((Throwable)throwable);
                    EhiLogger.logState((String)"...conversion failed");
                }
                if (fileLogger == null) break block55;
            }
            catch (Throwable throwable) {
                if (fileLogger != null) {
                    fileLogger.close();
                    EhiLogger.getInstance().removeListener(fileLogger);
                    fileLogger = null;
                }
                if (stdLogger != null) {
                    EhiLogger.getInstance().addListener((LogListener)StdListener.getInstance());
                    EhiLogger.getInstance().removeListener((LogListener)stdLogger);
                    stdLogger = null;
                }
                throw throwable;
            }
            fileLogger.close();
            EhiLogger.getInstance().removeListener((LogListener)fileLogger);
            fileLogger = null;
        }
        if (stdLogger != null) {
            EhiLogger.getInstance().addListener((LogListener)StdListener.getInstance());
            EhiLogger.getInstance().removeListener((LogListener)stdLogger);
            stdLogger = null;
        }
        return bl;
    }

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

    /** Firma di proprieta': due righe di commento DXF (group 999) in testa al
     * file, con l'hash SHA-256 dell'autore e un'impronta che lega progetto e
     * timestamp. Verificabile con org.interlis2.av2geobau.DxfSignatureVerifier.
     * Usa java.security.MessageDigest, incluso nel JDK: NON aggiungere una
     * libreria DXF esterna (jdxf o simili) per questo - il progetto ha il
     * proprio writer DXF scritto a mano e quella dipendenza era gia' stata
     * valutata e scartata. */
    private void writeOwnershipWatermark(Writer writer, String string) throws IOException {
        try {
            String string2 = "Peverelli";
            String string3 = Av2geobau.sha256Hex(string2);
            String string4 = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
            String string5 = Av2geobau.sha256Hex(string + "_" + string4 + "_" + string2);
            writer.write(DxfUtil.toString(999, "ID_Creatore:" + string3));
            writer.write(DxfUtil.toString(999, "Impronta_Sicurezza:" + string5));
        }
        catch (NoSuchAlgorithmException noSuchAlgorithmException) {
            EhiLogger.logError((Throwable)noSuchAlgorithmException);
        }
    }

    private void writeHeader(Writer writer, CountingWriter countingWriter) throws IOException {
        writer.write(DxfUtil.toString(0, "SECTION"));
        writer.write(DxfUtil.toString(2, "HEADER"));
        // R2004 (AC1018). La versione dichiarata deve coprire TUTTE le funzioni
        // realmente usate nel file, altrimenti il DXF e' formalmente
        // incoerente:
        //  - HATCH nativi (bosco/pascolo a punti, edifici pieni) al posto
        //    delle approssimazioni a griglia di blocchi/SOLID: richiedono R14;
        //  - handle obbligatori (group 5) su tabelle/blocchi/entita', vedi
        //    DxfUtil.nextHandle() e DxfWriter.modelSpaceHandle: da R13 in poi
        //    ($HANDLING, il flag on/off degli handle, esisteva solo in R12 e
        //    non va piu' scritto);
        //  - trasparenza per-entita' (group 440, riempimento degli edifici al
        //    45%) e true color (group 420, riquadri della legenda): richiedono
        //    R2004. Erano gia' emessi quando l'header dichiarava ancora
        //    AC1015/R2000 - incoerenza rilevata da un audit del file prodotto.
        // Conseguenza voluta: il lettore minimo diventa AutoCAD 2004.
        writer.write(DxfUtil.toString(9, "$ACADVER"));
        writer.write(DxfUtil.toString(1, "AC1018"));
        writer.write(DxfUtil.toString(9, "$HANDSEED"));
        // $HANDSEED deve contenere il conteggio finale degli handle, che qui
        // NON e' ancora noto (l'header si scrive per primo, prima di tabelle,
        // blocchi ed entita' che consumano quasi tutti gli handle). Si scrive
        // quindi un placeholder a larghezza FISSA di 8 cifre esadecimali e si
        // annota l'offset in byte del suo primo carattere, per correggerlo
        // in-place a file chiuso (vedi doConversion). Un placeholder scelto a
        // caso e mai corretto ("FFFFFFFF", usato in precedenza) veniva
        // rifiutato da alcune versioni di AutoCAD 2024/2025 con "drawing file
        // is not valid". La flush() prima di leggere il contatore e'
        // indispensabile: senza, si otterrebbe la posizione nel buffer, non
        // quella reale nel file.
        writer.write("  5\r\n");
        writer.flush();
        this.handSeedValueOffset = countingWriter.count;
        writer.write("00000000\r\n");
        writer.write(DxfUtil.toString(9, "$LTSCALE"));
        writer.write(DxfUtil.toString(40, "1.0"));
        writer.write(DxfUtil.toString(9, "$LUNITS"));
        writer.write(DxfUtil.toString(70, "2"));
        writer.write(DxfUtil.toString(9, "$LUPREC"));
        writer.write(DxfUtil.toString(70, "3"));
        writer.write(DxfUtil.toString(9, "$AUNITS"));
        writer.write(DxfUtil.toString(70, "2"));
        writer.write(DxfUtil.toString(9, "$AUPREC"));
        writer.write(DxfUtil.toString(70, "3"));
        writer.write(DxfUtil.toString(9, "$TDCREATE"));
        writer.write(DxfUtil.toString(40, "2461181.5130902780219913"));
        writer.write(DxfUtil.toString(9, "$ANGBASE"));
        writer.write(DxfUtil.toString(50, "1.571"));
        writer.write(DxfUtil.toString(9, "$ANGDIR"));
        writer.write(DxfUtil.toString(70, "1"));
        writer.write(DxfUtil.toString(9, "$PLINEGEN"));
        writer.write(DxfUtil.toString(70, "1"));
        writer.write(DxfUtil.toString(9, "$PSLTSCALE"));
        writer.write(DxfUtil.toString(70, "1"));
        writer.write(DxfUtil.toString(0, "ENDSEC"));
    }

    private static Object[][] cat(Object[][] objectArray, Object[][] objectArray2) {
        Object[][] objectArray3 = new Object[objectArray.length + objectArray2.length][];
        System.arraycopy(objectArray, 0, objectArray3, 0, objectArray.length);
        System.arraycopy(objectArray2, 0, objectArray3, objectArray.length, objectArray2.length);
        return objectArray3;
    }

    private void writeEmptyTable(Writer writer, String string) throws IOException {
        writer.write(DxfUtil.toString(0, "TABLE"));
        writer.write(DxfUtil.toString(2, string));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, "0"));
        writer.write(DxfUtil.toString(100, "AcDbSymbolTable"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(0, "ENDTAB"));
    }

    /*
     * WARNING - void declaration
     */
    private void writeTables(Writer writer) throws IOException {
        int var6_17;
        int var6_15;
        writer.write(DxfUtil.toString(0, "SECTION"));
        writer.write(DxfUtil.toString(2, "TABLES"));
        String string = DxfUtil.nextHandle();
        writer.write(DxfUtil.toString(0, "TABLE"));
        writer.write(DxfUtil.toString(2, "VPORT"));
        writer.write(DxfUtil.toString(5, string));
        writer.write(DxfUtil.toString(330, "0"));
        writer.write(DxfUtil.toString(100, "AcDbSymbolTable"));
        writer.write(DxfUtil.toString(70, "1"));
        writer.write(DxfUtil.toString(0, "VPORT"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, string));
        writer.write(DxfUtil.toString(100, "AcDbSymbolTableRecord"));
        writer.write(DxfUtil.toString(100, "AcDbViewportTableRecord"));
        writer.write(DxfUtil.toString(2, "*ACTIVE"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "1000.0"));
        writer.write(DxfUtil.toString(41, "1.0"));
        writer.write(DxfUtil.toString(42, "50.0"));
        writer.write(DxfUtil.toString(43, "0.0"));
        writer.write(DxfUtil.toString(44, "0.0"));
        writer.write(DxfUtil.toString(50, "0.0"));
        writer.write(DxfUtil.toString(51, "0.0"));
        writer.write(DxfUtil.toString(71, "0"));
        writer.write(DxfUtil.toString(72, "100"));
        writer.write(DxfUtil.toString(73, "1"));
        writer.write(DxfUtil.toString(74, "3"));
        writer.write(DxfUtil.toString(75, "0"));
        writer.write(DxfUtil.toString(76, "0"));
        writer.write(DxfUtil.toString(77, "0"));
        writer.write(DxfUtil.toString(78, "0"));
        writer.write(DxfUtil.toString(0, "ENDTAB"));
        string = DxfUtil.nextHandle();
        writer.write(DxfUtil.toString(0, "TABLE"));
        writer.write(DxfUtil.toString(2, "LTYPE"));
        writer.write(DxfUtil.toString(5, string));
        writer.write(DxfUtil.toString(330, "0"));
        writer.write(DxfUtil.toString(100, "AcDbSymbolTable"));
        writer.write(DxfUtil.toString(70, GDV_LINETYPES.length + GENERIC_LINETYPES.length + 3));
        writer.write(DxfUtil.toString(0, "LTYPE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, string));
        writer.write(DxfUtil.toString(100, "AcDbSymbolTableRecord"));
        writer.write(DxfUtil.toString(100, "AcDbLinetypeTableRecord"));
        writer.write(DxfUtil.toString(2, "CONTINUOUS"));
        writer.write(DxfUtil.toString(70, "64"));
        writer.write(DxfUtil.toString(3, "Solid line"));
        writer.write(DxfUtil.toString(72, "65"));
        writer.write(DxfUtil.toString(73, "0"));
        writer.write(DxfUtil.toString(40, "0.0"));
        for (String string4 : new String[]{"ByBlock", "ByLayer"}) {
            writer.write(DxfUtil.toString(0, "LTYPE"));
            writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
            writer.write(DxfUtil.toString(330, string));
            writer.write(DxfUtil.toString(100, "AcDbSymbolTableRecord"));
            writer.write(DxfUtil.toString(100, "AcDbLinetypeTableRecord"));
            writer.write(DxfUtil.toString(2, string4));
            writer.write(DxfUtil.toString(70, "64"));
            writer.write(DxfUtil.toString(3, ""));
            writer.write(DxfUtil.toString(72, "65"));
            writer.write(DxfUtil.toString(73, "0"));
            writer.write(DxfUtil.toString(40, "0.0"));
        }
        for (Object[] string2 : Av2geobau.cat(GDV_LINETYPES, GENERIC_LINETYPES)) {
            double d;
            String string3 = (String)string2[0];
            String string4 = (String)string2[1];
            double[] dArray = (double[])string2[2];
            writer.write(DxfUtil.toString(0, "LTYPE"));
            writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
            writer.write(DxfUtil.toString(330, string));
            writer.write(DxfUtil.toString(100, "AcDbSymbolTableRecord"));
            writer.write(DxfUtil.toString(100, "AcDbLinetypeTableRecord"));
            writer.write(DxfUtil.toString(2, string3));
            writer.write(DxfUtil.toString(70, "64"));
            writer.write(DxfUtil.toString(3, string4));
            writer.write(DxfUtil.toString(72, "65"));
            writer.write(DxfUtil.toString(73, dArray.length));
            double d2 = 0.0;
            for (double d3 : dArray) {
                d = Math.abs(d3) < 1.0E-9 ? 0.001 : d3;
                d2 += Math.abs(d);
            }
            writer.write(DxfUtil.toString(40, d2, 3));
            for (double d3 : dArray) {
                d = Math.abs(d3) < 1.0E-9 ? 0.001 : d3;
                writer.write(DxfUtil.toString(49, d, 3));
                writer.write(DxfUtil.toString(74, "0"));
            }
        }
        writer.write(DxfUtil.toString(0, "ENDTAB"));
        LinkedHashMap<String, String> linkedHashMap = new LinkedHashMap<String, String>();
        linkedHashMap.put("0", "CONTINUOUS");
        String[][] stringArray = LAYER_LINETYPES;
        int n = stringArray.length;
        var6_15 = 0;
        while (var6_15 < n) {
            String[] stringArray2 = stringArray[var6_15];
            linkedHashMap.put(stringArray2[0], stringArray2[1]);
            ++var6_15;
        }
        String[] stringArray3 = ALL_LAYERS;
        n = stringArray3.length;
        var6_17 = 0;
        while (var6_17 < n) {
            String string5 = stringArray3[var6_17];
            if (!linkedHashMap.containsKey(string5)) {
                linkedHashMap.put(string5, "CONTINUOUS");
            }
            ++var6_17;
        }
        String string6 = DxfUtil.nextHandle();
        writer.write(DxfUtil.toString(0, "TABLE"));
        writer.write(DxfUtil.toString(2, "LAYER"));
        writer.write(DxfUtil.toString(5, string6));
        writer.write(DxfUtil.toString(330, "0"));
        writer.write(DxfUtil.toString(100, "AcDbSymbolTable"));
        writer.write(DxfUtil.toString(70, linkedHashMap.size()));
        for (Map.Entry<String, String> entry : linkedHashMap.entrySet()) {
            int n2 = LAYER_COLOR_OVERRIDES.containsKey(entry.getKey()) ? LAYER_COLOR_OVERRIDES.get(entry.getKey()) : 7;
            writer.write(DxfUtil.toString(0, "LAYER"));
            writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
            writer.write(DxfUtil.toString(330, string6));
            writer.write(DxfUtil.toString(100, "AcDbSymbolTableRecord"));
            writer.write(DxfUtil.toString(100, "AcDbLayerTableRecord"));
            writer.write(DxfUtil.toString(2, (String)entry.getKey()));
            writer.write(DxfUtil.toString(70, "0"));
            writer.write(DxfUtil.toString(62, Integer.toString(n2)));
            writer.write(DxfUtil.toString(6, (String)entry.getValue()));
            writer.write(DxfUtil.toString(290, "1"));
            writer.write(DxfUtil.toString(370, "-3"));
            writer.write(DxfUtil.toString(390, "1"));
        }
        writer.write(DxfUtil.toString(0, "ENDTAB"));
        String[][] stringArrayArray = new String[][]{{"ARIAL", "arial.ttf"}, {"ARIAL_BOLD", "arialbd.ttf"}, {"ARIAL_ITALIC", "ariali.ttf"}, {"ARIAL_BOLD_ITALIC", "arialbi.ttf"}};
        String string7 = DxfUtil.nextHandle();
        writer.write(DxfUtil.toString(0, "TABLE"));
        writer.write(DxfUtil.toString(2, "STYLE"));
        writer.write(DxfUtil.toString(5, string7));
        writer.write(DxfUtil.toString(330, "0"));
        writer.write(DxfUtil.toString(100, "AcDbSymbolTable"));
        writer.write(DxfUtil.toString(70, stringArrayArray.length));
        for (String[] stringArray4 : stringArrayArray) {
            writer.write(DxfUtil.toString(0, "STYLE"));
            writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
            writer.write(DxfUtil.toString(330, string7));
            writer.write(DxfUtil.toString(100, "AcDbSymbolTableRecord"));
            writer.write(DxfUtil.toString(100, "AcDbTextStyleTableRecord"));
            writer.write(DxfUtil.toString(2, stringArray4[0]));
            writer.write(DxfUtil.toString(70, "0"));
            writer.write(DxfUtil.toString(40, "0.0"));
            writer.write(DxfUtil.toString(41, "1.0"));
            writer.write(DxfUtil.toString(50, "0.0"));
            writer.write(DxfUtil.toString(71, "0"));
            writer.write(DxfUtil.toString(42, "2.5"));
            writer.write(DxfUtil.toString(3, stringArray4[1]));
            writer.write(DxfUtil.toString(4, ""));
        }
        writer.write(DxfUtil.toString(0, "ENDTAB"));
        this.writeEmptyTable(writer, "VIEW");
        this.writeEmptyTable(writer, "UCS");
        String string8 = DxfUtil.nextHandle();
        writer.write(DxfUtil.toString(0, "TABLE"));
        writer.write(DxfUtil.toString(2, "APPID"));
        writer.write(DxfUtil.toString(5, string8));
        writer.write(DxfUtil.toString(330, "0"));
        writer.write(DxfUtil.toString(100, "AcDbSymbolTable"));
        writer.write(DxfUtil.toString(70, "1"));
        writer.write(DxfUtil.toString(0, "APPID"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, string8));
        writer.write(DxfUtil.toString(100, "AcDbSymbolTableRecord"));
        writer.write(DxfUtil.toString(100, "AcDbRegAppTableRecord"));
        writer.write(DxfUtil.toString(2, "ACAD"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(0, "ENDTAB"));
        writer.write(DxfUtil.toString(0, "TABLE"));
        writer.write(DxfUtil.toString(2, "DIMSTYLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, "0"));
        writer.write(DxfUtil.toString(100, "AcDbSymbolTable"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(100, "AcDbDimStyleTable"));
        writer.write(DxfUtil.toString(71, "0"));
        writer.write(DxfUtil.toString(0, "ENDTAB"));
        String string9 = DxfUtil.nextHandle();
        writer.write(DxfUtil.toString(0, "TABLE"));
        writer.write(DxfUtil.toString(2, "BLOCK_RECORD"));
        writer.write(DxfUtil.toString(5, string9));
        writer.write(DxfUtil.toString(330, "0"));
        writer.write(DxfUtil.toString(100, "AcDbSymbolTable"));
        writer.write(DxfUtil.toString(70, BLOCK_NAMES.length + 2));
        for (String string10 : Av2geobau.cat2("*Model_Space", "*Paper_Space", BLOCK_NAMES)) {
            String string11 = DxfUtil.nextHandle();
            this.blockRecordHandles.put(string10, string11);
            writer.write(DxfUtil.toString(0, "BLOCK_RECORD"));
            writer.write(DxfUtil.toString(5, string11));
            writer.write(DxfUtil.toString(330, string9));
            writer.write(DxfUtil.toString(100, "AcDbSymbolTableRecord"));
            writer.write(DxfUtil.toString(100, "AcDbBlockTableRecord"));
            writer.write(DxfUtil.toString(2, string10));
        }
        writer.write(DxfUtil.toString(0, "ENDTAB"));
        writer.write(DxfUtil.toString(0, "ENDSEC"));
    }

    private static String[] cat2(String string, String string2, String[] stringArray) {
        String[] stringArray2 = new String[stringArray.length + 2];
        stringArray2[0] = string;
        stringArray2[1] = string2;
        System.arraycopy(stringArray, 0, stringArray2, 2, stringArray.length);
        return stringArray2;
    }

    private void writeClosedPolylineBlock(Writer writer, double[][] dArray, String string) throws IOException {
        this.writePolylineBlock(writer, dArray, string, true);
    }

    private void writePolylineBlock(Writer writer, double[][] dArray, String string, boolean bl) throws IOException {
        writer.write(DxfUtil.toString(0, "POLYLINE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, string));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDb2dPolyline"));
        writer.write(DxfUtil.toString(66, "1"));
        writer.write(DxfUtil.toString(70, bl ? "1" : "0"));
        for (double[] dArray2 : dArray) {
            writer.write(DxfUtil.toString(0, "VERTEX"));
            writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
            writer.write(DxfUtil.toString(330, string));
            writer.write(DxfUtil.toString(100, "AcDbEntity"));
            writer.write(DxfUtil.toString(8, "0"));
            writer.write(DxfUtil.toString(100, "AcDbVertex"));
            writer.write(DxfUtil.toString(100, "AcDb2dVertex"));
            writer.write(DxfUtil.toString(10, Double.toString(dArray2[0])));
            writer.write(DxfUtil.toString(20, Double.toString(dArray2[1])));
            writer.write(DxfUtil.toString(30, "0.0"));
        }
        writer.write(DxfUtil.toString(0, "SEQEND"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, string));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
    }

    private void writeSplineBlock(Writer writer, double[] dArray, double[][] dArray2, double[][] dArray3, String string) throws IOException {
        writer.write(DxfUtil.toString(0, "SPLINE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, string));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbSpline"));
        writer.write(DxfUtil.toString(210, "0.0"));
        writer.write(DxfUtil.toString(220, "0.0"));
        writer.write(DxfUtil.toString(230, "1.0"));
        writer.write(DxfUtil.toString(70, "8"));
        writer.write(DxfUtil.toString(71, "3"));
        writer.write(DxfUtil.toString(72, dArray.length));
        writer.write(DxfUtil.toString(73, dArray2.length));
        writer.write(DxfUtil.toString(74, dArray3.length));
        writer.write(DxfUtil.toString(42, "0.0000001"));
        writer.write(DxfUtil.toString(43, "0.0000001"));
        writer.write(DxfUtil.toString(44, "0.0000000001"));
        for (double d : dArray) {
            writer.write(DxfUtil.toString(40, Double.toString(d)));
        }
        for (double[] dArray4 : dArray2) {
            writer.write(DxfUtil.toString(10, Double.toString(dArray4[0])));
            writer.write(DxfUtil.toString(20, Double.toString(dArray4[1])));
            writer.write(DxfUtil.toString(30, "0.0"));
        }
        for (double[] dArray5 : dArray3) {
            writer.write(DxfUtil.toString(11, Double.toString(dArray5[0])));
            writer.write(DxfUtil.toString(21, Double.toString(dArray5[1])));
            writer.write(DxfUtil.toString(31, "0.0"));
        }
    }

    /*
     * WARNING - Removed try catching itself - possible behaviour change.
     */
    /** Riordina la sezione ENTITIES di un DXF gia' scritto e chiuso: gli HATCH
     * in testa (quindi visivamente sul fondo), i layer di FRONT_LAYERS in coda
     * (in primo piano), tutto il resto in mezzo nell'ordine originale.
     * Perche' a posteriori e non durante la scrittura: il Mapper produce le
     * entita' in streaming nell'ordine del file ITF (vedi
     * Mapper.getMappedObject, che estrae dalla coda con remove(0)) senza mai
     * tenere l'intero disegno in memoria - non esiste quindi, in fase di
     * scrittura, un momento in cui siano note tutte le entita' da ordinare.
     * Rilegge e riscrive tutto il file: un patch in-place e' impossibile,
     * spostare un blocco cambia la posizione di ogni byte successivo.
     * NB: VERTEX e SEQEND non sono entita' di primo livello ma continuazioni
     * della POLYLINE precedente, e vanno spostati insieme ad essa. */
    private void reorderEntitiesForDrawOrder(File file) throws IOException {
        String object2;
        ArrayList<String> serializable;
        ArrayList<String> arrayList = new ArrayList<String>();
        try (BufferedReader bufferedReader = new BufferedReader(new InputStreamReader((InputStream)new FileInputStream(file), "ISO-8859-1"));){
            String string;
            while ((string = bufferedReader.readLine()) != null) {
                arrayList.add(string);
            }
        }
        int n = -1;
        int n2 = -1;
        for (int i = 0; i < arrayList.size() - 1; ++i) {
            if (((String)arrayList.get(i)).trim().equals("2") && ((String)arrayList.get(i + 1)).trim().equals("ENTITIES")) {
                n = i + 2;
                continue;
            }
            if (n < 0 || n2 >= 0 || !((String)arrayList.get(i)).trim().equals("0") || !((String)arrayList.get(i + 1)).trim().equals("ENDSEC")) continue;
            n2 = i;
            break;
        }
        if (n < 0 || n2 < 0) {
            EhiLogger.logError((Throwable)new IllegalStateException("reorderEntitiesForDrawOrder: sezione ENTITIES non trovata, riordino saltato"));
            return;
        }
        ArrayList<ArrayList<String>> arrayList2 = new ArrayList<ArrayList<String>>();
        ArrayList<ArrayList<String>> arrayList3 = new ArrayList<ArrayList<String>>();
        ArrayList<ArrayList<String>> arrayList4 = new ArrayList<ArrayList<String>>();
        int n3 = n;
        while (n3 < n2) {
            serializable = new ArrayList<String>();
            serializable.add((String)arrayList.get(n3));
            serializable.add((String)arrayList.get(n3 + 1));
            object2 = ((String)arrayList.get(n3 + 1)).trim();
            String string = null;
            n3 += 2;
            while (n3 < n2) {
                String object3 = ((String)arrayList.get(n3)).trim();
                if (object3.equals("0")) {
                    String string2 = ((String)arrayList.get(n3 + 1)).trim();
                    if (!string2.equals("VERTEX") && !string2.equals("SEQEND")) break;
                    serializable.add((String)arrayList.get(n3));
                    serializable.add((String)arrayList.get(n3 + 1));
                    n3 += 2;
                    continue;
                }
                if (object3.equals("8") && string == null) {
                    string = ((String)arrayList.get(n3 + 1)).trim();
                }
                serializable.add((String)arrayList.get(n3));
                serializable.add((String)arrayList.get(n3 + 1));
                n3 += 2;
            }
            if (((String)object2).equals("HATCH")) {
                arrayList2.add(serializable);
                continue;
            }
            if (string != null && FRONT_LAYERS.contains(string)) {
                arrayList3.add(serializable);
                continue;
            }
            arrayList4.add(serializable);
        }
        File tmpFile = new File(file.getParentFile(), file.getName() + ".reorder.tmp");
        BufferedWriter writer = new BufferedWriter(new OutputStreamWriter((OutputStream)new FileOutputStream(tmpFile), "ISO-8859-1"));
        try {
            for (int i = 0; i < n; ++i) {
                writer.write((String)arrayList.get(i));
                writer.write("\n");
            }
            for (ArrayList<ArrayList<String>> list : Arrays.asList(arrayList2, arrayList4, arrayList3)) {
                for (ArrayList<String> list2 : list) {
                    for (String string : list2) {
                        writer.write(string);
                        writer.write("\n");
                    }
                }
            }
            for (int i = n2; i < arrayList.size(); ++i) {
                writer.write((String)arrayList.get(i));
                if (i >= arrayList.size() - 1) continue;
                writer.write("\n");
            }
        }
        finally {
            writer.close();
        }
        if (!file.delete() || !tmpFile.renameTo(file)) {
            throw new IOException("reorderEntitiesForDrawOrder: impossibile sostituire " + file);
        }
        EhiLogger.logState((String)("...ordine di disegno riordinato (" + arrayList2.size() + " HATCH dietro, " + arrayList3.size() + " entita' in primo piano)"));
    }

    /*
     * WARNING - Removed try catching itself - possible behaviour change.
     */
    private List<String> readAllLinesIso(File file) throws IOException {
        ArrayList<String> arrayList = new ArrayList<String>();
        try (BufferedReader bufferedReader = new BufferedReader(new InputStreamReader((InputStream)new FileInputStream(file), "ISO-8859-1"));){
            String string;
            while ((string = bufferedReader.readLine()) != null) {
                arrayList.add(string);
            }
        }
        return arrayList;
    }

    /** Estensione approssimata {minX, minY, maxX, maxY} delle entita' gia'
     * scritte, ricavata scandendo i group 10/20 della sezione ENTITIES.
     * ATTENZIONE, solo i MASSIMI sono affidabili: il punto 10/20 dell'header di
     * una POLYLINE e l'elevation point di un HATCH valgono per definizione
     * (0,0), quindi minX/minY risultano sempre 0 (misurati 47'000 POLYLINE e
     * 8'204 HATCH in un file reale). Basta allo scopo - posizionare la legenda
     * appena FUORI dal disegno, vedi appendLegendBlock - ma non usare i minimi
     * per un calcolo cartografico. */
    private double[] computeEntitiesExtent(File file) throws IOException {
        List<String> list = this.readAllLinesIso(file);
        int n = -1;
        int n2 = -1;
        for (int i = 0; i < list.size() - 1; ++i) {
            if (list.get(i).trim().equals("2") && list.get(i + 1).trim().equals("ENTITIES")) {
                n = i + 2;
                continue;
            }
            if (n < 0 || n2 >= 0 || !list.get(i).trim().equals("0") || !list.get(i + 1).trim().equals("ENDSEC")) continue;
            n2 = i;
            break;
        }
        if (n < 0 || n2 < 0) {
            return null;
        }
        double d = Double.POSITIVE_INFINITY;
        double d2 = Double.NEGATIVE_INFINITY;
        double d3 = Double.POSITIVE_INFINITY;
        double d4 = Double.NEGATIVE_INFINITY;
        for (int i = n; i < n2 - 1; ++i) {
            String string = list.get(i).trim();
            if (!string.equals("10") && !string.equals("20")) continue;
            try {
                double d5 = Double.parseDouble(list.get(i + 1).trim());
                if (string.equals("10")) {
                    if (d5 < d) {
                        d = d5;
                    }
                    if (!(d5 > d2)) continue;
                    d2 = d5;
                    continue;
                }
                if (d5 < d3) {
                    d3 = d5;
                }
                if (!(d5 > d4)) continue;
                d4 = d5;
                continue;
            }
            catch (NumberFormatException numberFormatException) {
                // empty catch block
            }
        }
        if (d == Double.POSITIVE_INFINITY || d3 == Double.POSITIVE_INFINITY) {
            return null;
        }
        return new double[]{d, d3, d2, d4};
    }

    private String rawLegendText(double d, double d2, double d3, String string, String string2, String string3) throws IOException {
        StringBuilder stringBuilder = new StringBuilder();
        stringBuilder.append(DxfUtil.toString(0, "TEXT"));
        stringBuilder.append(DxfUtil.toString(5, DxfUtil.nextHandle()));
        stringBuilder.append(DxfUtil.toString(330, string3));
        stringBuilder.append(DxfUtil.toString(100, "AcDbEntity"));
        stringBuilder.append(DxfUtil.toString(8, "TI_LEGENDA"));
        stringBuilder.append(DxfUtil.toString(100, "AcDbText"));
        stringBuilder.append(DxfUtil.toString(10, Double.toString(d)));
        stringBuilder.append(DxfUtil.toString(20, Double.toString(d2)));
        stringBuilder.append(DxfUtil.toString(30, "0.0"));
        stringBuilder.append(DxfUtil.toString(40, Double.toString(d3)));
        stringBuilder.append(DxfUtil.toString(1, string));
        stringBuilder.append(DxfUtil.toString(7, string2));
        // IL TEXT VUOLE IL MARCATORE DI SOTTOCLASSE DUE VOLTE. E' una
        // stranezza del formato: AcDbText compare una prima volta prima della
        // geometria e una SECONDA prima del gruppo 73 (allineamento
        // verticale). Senza la seconda, AutoCAD non degrada il testo -
        // ABORTISCE L'INTERO DISEGNO:
        //   "while reading in TEXT ... Class separator for class AcDbText
        //    expected. Invalid or incomplete DXF input -- drawing discarded."
        // Il testo delle entita' vere lo scrive gia' (DxfWriter.text2Dxf);
        // questo scrittore separato della legenda no, e i suoi 638 testi
        // rendevano illeggibile un file da 209 MB.
        //
        // 73 = 0 (linea di base) e non 2 come in text2Dxf: e' il valore che
        // AutoCAD assume quando il gruppo manca, quindi scriverlo esplicito
        // NON sposta la legenda gia' impaginata.
        stringBuilder.append(DxfUtil.toString(100, "AcDbText"));
        stringBuilder.append(DxfUtil.toString(73, "0"));
        return stringBuilder.toString();
    }

    private String rawLegendSwatch(double d, double d2, double d3, int n, int n2, int n3, String string) throws IOException {
        int n4 = n << 16 | n2 << 8 | n3;
        StringBuilder stringBuilder = new StringBuilder();
        stringBuilder.append(DxfUtil.toString(0, "SOLID"));
        stringBuilder.append(DxfUtil.toString(5, DxfUtil.nextHandle()));
        stringBuilder.append(DxfUtil.toString(330, string));
        stringBuilder.append(DxfUtil.toString(100, "AcDbEntity"));
        stringBuilder.append(DxfUtil.toString(8, "TI_LEGENDA"));
        stringBuilder.append(DxfUtil.toString(420, Integer.toString(n4)));
        stringBuilder.append(DxfUtil.toString(100, "AcDbTrace"));
        stringBuilder.append(DxfUtil.toString(10, Double.toString(d)));
        stringBuilder.append(DxfUtil.toString(20, Double.toString(d2 - d3)));
        stringBuilder.append(DxfUtil.toString(30, "0.0"));
        stringBuilder.append(DxfUtil.toString(11, Double.toString(d + d3)));
        stringBuilder.append(DxfUtil.toString(21, Double.toString(d2 - d3)));
        stringBuilder.append(DxfUtil.toString(31, "0.0"));
        stringBuilder.append(DxfUtil.toString(12, Double.toString(d)));
        stringBuilder.append(DxfUtil.toString(22, Double.toString(d2)));
        stringBuilder.append(DxfUtil.toString(32, "0.0"));
        stringBuilder.append(DxfUtil.toString(13, Double.toString(d + d3)));
        stringBuilder.append(DxfUtil.toString(23, Double.toString(d2)));
        stringBuilder.append(DxfUtil.toString(33, "0.0"));
        return stringBuilder.toString();
    }

    /*
     * WARNING - Removed try catching itself - possible behaviour change.
     */
    /** Ponte QGIS -> DXF per la legenda: legge il manifest di testo scritto dal
     * lato Python (cadastra_dashboard/legend_manifest.py) e aggiunge alla
     * sezione ENTITIES gia' chiusa un blocco legenda (titolo, intestazione per
     * layer, riquadro colorato piu' etichetta per ogni regola del renderer
     * QGIS). E' un ponte ESPLICITO, non un collegamento vivo: lo stile QGIS e
     * questo generatore sono due programmi separati, quindi il flusso corretto
     * e' "ristila il progetto (rigenera il manifest) poi rilancia l'export".
     * Il manifest e' pipe-delimited e va letto in ISO-8859-1 come il resto del
     * DXF - il lato Python lo scrive nella stessa codifica: con UTF-8 ogni
     * carattere accentato diventava mojibake. Se il manifest non esiste non fa
     * nulla e non segnala errori: la legenda e' una funzione opzionale. */
    private void appendLegendBlock(File file, File file2) throws IOException {
        int n;
        int n2;
        if (!file2.exists()) {
            return;
        }
        double[] dArray = this.computeEntitiesExtent(file);
        if (dArray == null) {
            return;
        }
        ArrayList<String[]> arrayList = new ArrayList<String[]>();
        for (String string : this.readAllLinesIso(file2)) {
            String[] stringArray;
            if (string.trim().isEmpty() || (stringArray = string.split("\\|", -1)).length != 5) continue;
            arrayList.add(stringArray);
        }
        if (arrayList.isEmpty()) {
            return;
        }
        double d = 20.0;
        double d2 = 3.5;
        double d3 = 2.2;
        double d4 = 1.8;
        double d5 = 5.0;
        double d6 = 3.6;
        double d7 = 3.0;
        double d8 = 1.4;
        double d9 = 2.2;
        double d10 = dArray[2] + d;
        double d11 = dArray[3];
        String string = this.blockRecordHandles.get("*Model_Space");
        StringBuilder stringBuilder = new StringBuilder();
        stringBuilder.append(this.rawLegendText(d10, d11, d2, "LEGENDA", "ARIAL_BOLD", string));
        d11 -= d5;
        String string2 = null;
        for (String[] stringArray : arrayList) {
            int n3;
            int n4;
            String string3 = stringArray[0];
            String string4 = stringArray[1];
            try {
                n4 = Integer.parseInt(stringArray[2].trim());
                n2 = Integer.parseInt(stringArray[3].trim());
                n3 = Integer.parseInt(stringArray[4].trim());
            }
            catch (NumberFormatException numberFormatException) {
                continue;
            }
            if (!string3.equals(string2)) {
                stringBuilder.append(this.rawLegendText(d10, d11, d3, string3, "ARIAL_BOLD", string));
                d11 -= d6;
                string2 = string3;
            }
            stringBuilder.append(this.rawLegendSwatch(d10 + 0.5, d11, d8, n4, n2, n3, string));
            stringBuilder.append(this.rawLegendText(d10 + 0.5 + d8 + d9, d11, d4, string4, "ARIAL", string));
            d11 -= d7;
        }
        List<String> list = this.readAllLinesIso(file);
        int n5 = -1;
        boolean bl = false;
        for (n = 0; n < list.size() - 1; ++n) {
            if (((String)list.get(n)).trim().equals("2") && ((String)list.get(n + 1)).trim().equals("ENTITIES")) {
                bl = true;
                continue;
            }
            if (!bl || !((String)list.get(n)).trim().equals("0") || !((String)list.get(n + 1)).trim().equals("ENDSEC")) continue;
            n5 = n;
            break;
        }
        if (n5 < 0) {
            return;
        }
        for (n = 0; n < list.size() - 3; ++n) {
            // Le entita' della legenda hanno appena consumato NUOVI handle:
            // $HANDSEED va corretto un'altra volta. Qui si cerca per NOME di
            // riga, non con un secondo seek all'offset in byte salvato
            // nell'header: quell'offset e' ormai sbagliato perche'
            // reorderEntitiesForDrawOrder ha riscritto il file convertendo i
            // "\r\n" in "\n" (bug reale riscontrato: il seek finiva a meta' di
            // "$LTSCALE", corrompendo l'header).
            if (!((String)list.get(n)).trim().equals("9") || !((String)list.get(n + 1)).trim().equals("$HANDSEED") || !((String)list.get(n + 2)).trim().equals("5")) continue;
            list.set(n + 3, DxfUtil.currentHandleHex8());
            break;
        }
        File file3 = new File(file.getParentFile(), file.getName() + ".legend.tmp");
        try (BufferedWriter bufferedWriter = new BufferedWriter(new OutputStreamWriter((OutputStream)new FileOutputStream(file3), "ISO-8859-1"));){
            for (n2 = 0; n2 < n5; ++n2) {
                bufferedWriter.write((String)list.get(n2));
                bufferedWriter.write("\n");
            }
            bufferedWriter.write(stringBuilder.toString());
            for (n2 = n5; n2 < list.size(); ++n2) {
                bufferedWriter.write((String)list.get(n2));
                if (n2 >= list.size() - 1) continue;
                bufferedWriter.write("\n");
            }
        }
        if (!file.delete() || !file3.renameTo(file)) {
            throw new IOException("appendLegendBlock: impossibile sostituire " + file);
        }
        EhiLogger.logState((String)("...legenda aggiunta (" + arrayList.size() + " voci, manifest " + file2.getName() + ")"));
    }

    /*
     * WARNING - void declaration
     */
    private void writeBlocks(Writer writer) throws IOException {
        int var5_12;
        int n;
        writer.write(DxfUtil.toString(0, "SECTION"));
        writer.write(DxfUtil.toString(2, "BLOCKS"));
        for (String object2 : new String[]{"*Model_Space", "*Paper_Space"}) {
            String dArray = this.blockRecordHandles.get(object2);
            writer.write(DxfUtil.toString(0, "BLOCK"));
            writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
            writer.write(DxfUtil.toString(330, dArray));
            writer.write(DxfUtil.toString(100, "AcDbEntity"));
            writer.write(DxfUtil.toString(8, "0"));
            writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
            writer.write(DxfUtil.toString(2, object2));
            writer.write(DxfUtil.toString(70, "0"));
            writer.write(DxfUtil.toString(10, "0.0"));
            writer.write(DxfUtil.toString(20, "0.0"));
            writer.write(DxfUtil.toString(30, "0.0"));
            writer.write(DxfUtil.toString(3, object2));
            writer.write(DxfUtil.toString(0, "ENDBLK"));
            writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
            writer.write(DxfUtil.toString(330, dArray));
            writer.write(DxfUtil.toString(100, "AcDbEntity"));
            writer.write(DxfUtil.toString(8, "0"));
            writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        }
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPBOL")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "GPBOL"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPBOL")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "0.5"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPBOL")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPROH")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "GPROH"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPROH")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "0.5"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPROH")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPPFA")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "GPPFA"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPPFA")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "0.5"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPPFA")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPUV")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "GPUV"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPUV")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "0.1"));
        writer.write(DxfUtil.toString(0, "HATCH"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPUV")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbHatch"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(210, "0.0"));
        writer.write(DxfUtil.toString(220, "0.0"));
        writer.write(DxfUtil.toString(230, "1.0"));
        writer.write(DxfUtil.toString(2, "SOLID"));
        writer.write(DxfUtil.toString(70, "1"));
        writer.write(DxfUtil.toString(71, "0"));
        writer.write(DxfUtil.toString(91, "1"));
        writer.write(DxfUtil.toString(92, "1"));
        writer.write(DxfUtil.toString(93, "1"));
        writer.write(DxfUtil.toString(72, "2"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(40, "0.1"));
        writer.write(DxfUtil.toString(50, "0.0"));
        writer.write(DxfUtil.toString(51, "360.0"));
        writer.write(DxfUtil.toString(73, "1"));
        writer.write(DxfUtil.toString(97, "0"));
        writer.write(DxfUtil.toString(75, "1"));
        writer.write(DxfUtil.toString(76, "1"));
        writer.write(DxfUtil.toString(98, "0"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPUV")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPSTE")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "GPSTE"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPSTE")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "0.7"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPSTE")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPKST")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "GPKST"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPKST")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "0.7"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPKST")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPKRZ")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "GPKRZ"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPKRZ")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "0.5"));
        writer.write(DxfUtil.toString(0, "LINE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPKRZ")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbLine"));
        writer.write(DxfUtil.toString(10, "-0.849"));
        writer.write(DxfUtil.toString(20, "-0.849"));
        writer.write(DxfUtil.toString(30, "0.000"));
        writer.write(DxfUtil.toString(11, "-0.283"));
        writer.write(DxfUtil.toString(21, "-0.283"));
        writer.write(DxfUtil.toString(31, "0.000"));
        writer.write(DxfUtil.toString(0, "LINE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPKRZ")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbLine"));
        writer.write(DxfUtil.toString(10, "-0.284"));
        writer.write(DxfUtil.toString(20, "0.284"));
        writer.write(DxfUtil.toString(30, "0.000"));
        writer.write(DxfUtil.toString(11, "-0.849"));
        writer.write(DxfUtil.toString(21, "0.849"));
        writer.write(DxfUtil.toString(31, "0.000"));
        writer.write(DxfUtil.toString(0, "LINE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPKRZ")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbLine"));
        writer.write(DxfUtil.toString(10, "0.283"));
        writer.write(DxfUtil.toString(20, "0.283"));
        writer.write(DxfUtil.toString(30, "0.000"));
        writer.write(DxfUtil.toString(11, "0.849"));
        writer.write(DxfUtil.toString(21, "0.849"));
        writer.write(DxfUtil.toString(31, "0.000"));
        writer.write(DxfUtil.toString(0, "LINE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPKRZ")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbLine"));
        writer.write(DxfUtil.toString(10, "0.849"));
        writer.write(DxfUtil.toString(20, "-0.849"));
        writer.write(DxfUtil.toString(30, "0.000"));
        writer.write(DxfUtil.toString(11, "0.283"));
        writer.write(DxfUtil.toString(21, "-0.283"));
        writer.write(DxfUtil.toString(31, "0.000"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("GPKRZ")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("HGP")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "HGP"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("HGP")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "1.5"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("HGP")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP1")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "LFP1"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP1")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "0.8"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP1")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "1.3"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP1")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP2")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "LFP2"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP2")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "0.8"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP2")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "1.3"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP2")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("HFP1")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "HFP1"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("HFP1")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "1.0"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("HFP1")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("HFP2")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "HFP2"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("HFP2")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "1.0"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("HFP2")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("HFP3")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "HFP3"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("HFP3")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "1.0"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("HFP3")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP3ST")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "LFP3ST"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP3ST")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "0.8"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP3ST")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "1.3"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP3ST")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP3BO")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "LFP3BO"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP3BO")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "1.0"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP3BO")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP3UV")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "LFP3UV"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP3UV")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "0.3"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP3UV")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP3KR")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "LFP3KR"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP3KR")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "0.4"));
        writer.write(DxfUtil.toString(0, "LINE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP3KR")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbLine"));
        writer.write(DxfUtil.toString(10, "-0.849"));
        writer.write(DxfUtil.toString(20, "-0.849"));
        writer.write(DxfUtil.toString(30, "0.000"));
        writer.write(DxfUtil.toString(11, "-0.283"));
        writer.write(DxfUtil.toString(21, "-0.283"));
        writer.write(DxfUtil.toString(31, "0.000"));
        writer.write(DxfUtil.toString(0, "LINE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP3KR")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbLine"));
        writer.write(DxfUtil.toString(10, "-0.284"));
        writer.write(DxfUtil.toString(20, "0.284"));
        writer.write(DxfUtil.toString(30, "0.000"));
        writer.write(DxfUtil.toString(11, "-0.849"));
        writer.write(DxfUtil.toString(21, "0.849"));
        writer.write(DxfUtil.toString(31, "0.000"));
        writer.write(DxfUtil.toString(0, "LINE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP3KR")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbLine"));
        writer.write(DxfUtil.toString(10, "0.283"));
        writer.write(DxfUtil.toString(20, "0.283"));
        writer.write(DxfUtil.toString(30, "0.000"));
        writer.write(DxfUtil.toString(11, "0.849"));
        writer.write(DxfUtil.toString(21, "0.849"));
        writer.write(DxfUtil.toString(31, "0.000"));
        writer.write(DxfUtil.toString(0, "LINE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP3KR")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbLine"));
        writer.write(DxfUtil.toString(10, "0.849"));
        writer.write(DxfUtil.toString(20, "-0.849"));
        writer.write(DxfUtil.toString(30, "0.000"));
        writer.write(DxfUtil.toString(11, "0.283"));
        writer.write(DxfUtil.toString(21, "-0.283"));
        writer.write(DxfUtil.toString(31, "0.000"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP3KR")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "1.200667"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("LFP3KR")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("EOPNT")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "EOPNT"));
        writer.write(DxfUtil.toString(0, "CIRCLE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("EOPNT")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbCircle"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(40, "0.4"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("EOPNT")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("TRAMA")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "TRAMA"));
        int n2 = 8;
        double d = 0.15;
        double[][] dArray = new double[n2][2];
        for (n = 0; n < n2; ++n) {
            double d2 = Math.PI * 2 * (double)n / (double)n2;
            dArray[n][0] = d * Math.cos(d2);
            dArray[n][1] = d * Math.sin(d2);
        }
        for (n = 0; n < n2; ++n) {
            double[] dArray2 = dArray[n];
            double[] dArray3 = dArray[(n + 1) % n2];
            writer.write(DxfUtil.toString(0, "SOLID"));
            writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
            writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("TRAMA")));
            writer.write(DxfUtil.toString(100, "AcDbEntity"));
            writer.write(DxfUtil.toString(8, "0"));
            writer.write(DxfUtil.toString(62, "0"));
            writer.write(DxfUtil.toString(100, "AcDbTrace"));
            writer.write(DxfUtil.toString(10, "0.0"));
            writer.write(DxfUtil.toString(20, "0.0"));
            writer.write(DxfUtil.toString(30, "0.0"));
            writer.write(DxfUtil.toString(11, Double.toString(dArray2[0])));
            writer.write(DxfUtil.toString(21, Double.toString(dArray2[1])));
            writer.write(DxfUtil.toString(31, "0.0"));
            writer.write(DxfUtil.toString(12, Double.toString(dArray3[0])));
            writer.write(DxfUtil.toString(22, Double.toString(dArray3[1])));
            writer.write(DxfUtil.toString(32, "0.0"));
            writer.write(DxfUtil.toString(13, Double.toString(dArray3[0])));
            writer.write(DxfUtil.toString(23, Double.toString(dArray3[1])));
            writer.write(DxfUtil.toString(33, "0.0"));
        }
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("TRAMA")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("PSING")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "PSING"));
        writer.write(DxfUtil.toString(0, "LINE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("PSING")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbLine"));
        writer.write(DxfUtil.toString(10, "-0.4"));
        writer.write(DxfUtil.toString(20, "-0.4"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(11, "0.4"));
        writer.write(DxfUtil.toString(21, "0.4"));
        writer.write(DxfUtil.toString(31, "0.0"));
        writer.write(DxfUtil.toString(0, "LINE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("PSING")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(62, "0"));
        writer.write(DxfUtil.toString(100, "AcDbLine"));
        writer.write(DxfUtil.toString(10, "-0.4"));
        writer.write(DxfUtil.toString(20, "0.4"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(11, "0.4"));
        writer.write(DxfUtil.toString(21, "-0.4"));
        writer.write(DxfUtil.toString(31, "0.0"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("PSING")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        double[][][] dArrayArray = new double[][][]{new double[][]{{-0.2186, 0.6}, {-0.212, 0.5844}, {-0.204, 0.5694}, {-0.1942, 0.555}, {-0.183, 0.5414}, {-0.17, 0.5286}, {-0.1556, 0.5158}, {-0.1398, 0.503}, {-0.1226, 0.4898}, {-0.1042, 0.4764}, {-0.0842, 0.4628}, {-0.0842, 0.0028}, {-0.1244, -0.0178}, {-0.1602, -0.0388}, {-0.1916, -0.0598}, {-0.2186, -0.0812}, {-0.2414, -0.1028}, {-0.26, -0.1252}, {-0.2744, -0.149}, {-0.2846, -0.1742}, {-0.2908, -0.2006}, {-0.2928, -0.2286}, {-0.2908, -0.2626}, {-0.2846, -0.294}, {-0.2744, -0.3226}, {-0.26, -0.3484}, {-0.2414, -0.3714}, {-0.219, -0.3934}, {-0.193, -0.4162}, {-0.1632, -0.4396}, {-0.1298, -0.4638}, {-0.0928, -0.4886}, {-0.0842, -0.4942}, {-0.0842, -0.6}, {-0.0042, -0.6}, {-0.0042, -0.5486}, {0.0086, -0.5598}, {0.02, -0.5706}, {0.0296, -0.5808}, {0.0378, -0.5906}, {0.0442, -0.6}, {0.1328, -0.6}, {0.1182, -0.5684}, {0.0972, -0.5378}, {0.0698, -0.5082}, {0.036, -0.4794}, {-0.0042, -0.4514}, {-0.0042, -0.0486}, {0.034, -0.0342}, {0.0734, -0.0166}, {0.114, 0.0046}, {0.1558, 0.0292}, {0.1986, 0.0572}, {0.2326, 0.0876}, {0.259, 0.1194}, {0.2778, 0.1524}, {0.289, 0.187}, {0.2928, 0.2228}, {0.29, 0.2602}, {0.2812, 0.2946}, {0.2666, 0.326}, {0.2462, 0.3546}, {0.22, 0.38}, {0.1886, 0.404}, {0.1528, 0.428}, {0.1126, 0.452}, {0.0678, 0.476}, {0.0186, 0.5}, {-0.0042, 0.5114}, {-0.0042, 0.6}, {-0.0842, 0.6}, {-0.0842, 0.56}, {-0.0934, 0.5662}, {-0.1022, 0.5732}, {-0.1106, 0.5812}, {-0.119, 0.5902}, {-0.1272, 0.6}}, new double[][]{{0.01, 0.4142}, {0.05, 0.3932}, {0.0854, 0.3734}, {0.1162, 0.3548}, {0.1426, 0.3374}, {0.1642, 0.3214}, {0.1818, 0.3052}, {0.1954, 0.2872}, {0.205, 0.2674}, {0.211, 0.246}, {0.2128, 0.2228}, {0.2106, 0.2018}, {0.2042, 0.1818}, {0.1934, 0.1628}, {0.1782, 0.1452}, {0.1586, 0.1286}, {0.1346, 0.1122}, {0.1064, 0.0952}, {0.0738, 0.0774}, {0.037, 0.059}, {-0.0042, 0.04}, {-0.0042, 0.42}}, new double[][]{{-0.0842, -0.4}, {-0.1082, -0.384}, {-0.1298, -0.3682}, {-0.149, -0.3526}, {-0.1656, -0.337}, {-0.18, -0.3214}, {-0.1918, -0.3054}, {-0.201, -0.288}, {-0.2076, -0.2694}, {-0.2116, -0.2496}, {-0.2128, -0.2286}, {-0.2116, -0.2118}, {-0.2076, -0.1958}, {-0.201, -0.1808}, {-0.1918, -0.1664}, {-0.18, -0.1528}, {-0.1656, -0.1396}, {-0.149, -0.1264}, {-0.1298, -0.113}, {-0.1082, -0.0994}, {-0.0842, -0.0858}}};
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("VIGNA")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "VIGNA"));
        double[][][] dArrayArray2 = dArrayArray;
        int n3 = dArrayArray2.length;
        var5_12 = 0;
        while (var5_12 < n3) {
            double[][] dArray4 = dArrayArray2[var5_12];
            this.writeClosedPolylineBlock(writer, dArray4, this.blockRecordHandles.get("VIGNA"));
            ++var5_12;
        }
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("VIGNA")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("PQUOT")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "PQUOT"));
        writer.write(DxfUtil.toString(0, "LINE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("PQUOT")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbLine"));
        writer.write(DxfUtil.toString(10, "-0.4"));
        writer.write(DxfUtil.toString(20, "-0.4"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(11, "0.4"));
        writer.write(DxfUtil.toString(21, "0.4"));
        writer.write(DxfUtil.toString(31, "0.0"));
        writer.write(DxfUtil.toString(0, "LINE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("PQUOT")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbLine"));
        writer.write(DxfUtil.toString(10, "-0.4"));
        writer.write(DxfUtil.toString(20, "0.4"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(11, "0.4"));
        writer.write(DxfUtil.toString(21, "-0.4"));
        writer.write(DxfUtil.toString(31, "0.0"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("PQUOT")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("BACIDR")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "BACIDR"));
        this.writeSplineBlock(writer, BACIDR_SPLINE_UPPER_KNOTS, BACIDR_SPLINE_UPPER_CTRL, BACIDR_SPLINE_UPPER_FIT, this.blockRecordHandles.get("BACIDR"));
        this.writeSplineBlock(writer, BACIDR_SPLINE_LOWER_KNOTS, BACIDR_SPLINE_LOWER_CTRL, BACIDR_SPLINE_LOWER_FIT, this.blockRecordHandles.get("BACIDR"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("BACIDR")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(0, "BLOCK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("DIRCOR")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockBegin"));
        writer.write(DxfUtil.toString(70, "0"));
        writer.write(DxfUtil.toString(10, "0.0"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(2, "DIRCOR"));
        writer.write(DxfUtil.toString(0, "LINE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("DIRCOR")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbLine"));
        writer.write(DxfUtil.toString(10, "-0.75"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(11, "0.75"));
        writer.write(DxfUtil.toString(21, "0.0"));
        writer.write(DxfUtil.toString(31, "0.0"));
        writer.write(DxfUtil.toString(0, "LINE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("DIRCOR")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbLine"));
        writer.write(DxfUtil.toString(10, "0.75"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(11, "0.4"));
        writer.write(DxfUtil.toString(21, "0.25"));
        writer.write(DxfUtil.toString(31, "0.0"));
        writer.write(DxfUtil.toString(0, "LINE"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("DIRCOR")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbLine"));
        writer.write(DxfUtil.toString(10, "0.75"));
        writer.write(DxfUtil.toString(20, "0.0"));
        writer.write(DxfUtil.toString(30, "0.0"));
        writer.write(DxfUtil.toString(11, "0.4"));
        writer.write(DxfUtil.toString(21, "-0.25"));
        writer.write(DxfUtil.toString(31, "0.0"));
        writer.write(DxfUtil.toString(0, "ENDBLK"));
        writer.write(DxfUtil.toString(5, DxfUtil.nextHandle()));
        writer.write(DxfUtil.toString(330, this.blockRecordHandles.get("DIRCOR")));
        writer.write(DxfUtil.toString(100, "AcDbEntity"));
        writer.write(DxfUtil.toString(8, "0"));
        writer.write(DxfUtil.toString(100, "AcDbBlockEnd"));
        writer.write(DxfUtil.toString(0, "ENDSEC"));
    }

    public static TransferDescription compileIli(String[] stringArray, File file, String string, String string2, Settings settings, Ili2cMetaAttrs ili2cMetaAttrs) {
        String string3;
        ArrayList<String> arrayList = new ArrayList<String>();
        String string4 = settings.getValue(SETTING_ILIDIRS);
        if (string4 == null) {
            string4 = SETTING_DEFAULT_ILIDIRS;
        }
        EhiLogger.logState((String)("ilidirs <" + string4 + ">"));
        String[] stringArray2 = string4.split(";");
        HashSet hashSet = new HashSet();
        for (int i = 0; i < stringArray2.length; ++i) {
            string3 = stringArray2[i];
            if (string3.contains(ITF_DIR)) {
                if ((string3 = string3.replace(ITF_DIR, string)) == null || string3.length() <= 0 || arrayList.contains(string3)) continue;
                arrayList.add(string3);
                continue;
            }
            if (string3.contains(JAR_DIR)) {
                if (string2 == null) continue;
                string3 = string3.replace(JAR_DIR, string2);
                arrayList.add(string3);
                continue;
            }
            if (string3 == null || string3.length() <= 0) continue;
            arrayList.add(string3);
        }
        ch.interlis.ili2c.Main.setHttpProxySystemProperties(settings);
        TransferDescription transferDescription = null;
        Configuration config = null;
        if (file != null) {
            IliManager iliManager = (IliManager)settings.getTransientObject("ch.interlis.ili2c.customIliManager");
            if (iliManager == null) {
                iliManager = new IliManager();
                settings.setTransientObject("ch.interlis.ili2c.customIliManager", (Object)iliManager);
            }
            try {
                iliManager.setRepositories(arrayList.toArray(new String[0]));
                ArrayList<String> arrayList2 = new ArrayList<String>();
                arrayList2.add(file.getPath());
                config = iliManager.getConfigWithFiles(arrayList2, ili2cMetaAttrs);
                config.setGenerateWarnings(false);
            }
            catch (Ili2cException ili2cException) {
                EhiLogger.logError((Throwable)ili2cException);
                return null;
            }
        }
        ArrayList<String> arrayList3 = new ArrayList<String>();
        if (stringArray != null) {
            for (String string5 : stringArray) {
                if (string5 == null) continue;
                arrayList3.add(string5);
            }
        }
        try {
            IliManager iliManager = new IliManager();
            iliManager.setRepositories(arrayList.toArray(new String[0]));
            config = iliManager.getConfig(arrayList3, 0.0, ili2cMetaAttrs);
            config.setGenerateWarnings(false);
        }
        catch (Ili2cException ili2cException) {
            EhiLogger.logError((Throwable)ili2cException);
            return null;
        }
        Ili2c.logIliFiles(config);
        transferDescription = ch.interlis.ili2c.Main.runCompiler(config, settings, ili2cMetaAttrs);
        return transferDescription;
    }

    static {
        // Colore ACI per singoli layer, su richiesta esplicita dell'utente.
        // CONVENZIONE: valore NEGATIVO = layer SPENTO di default, col colore
        // dato dal valore assoluto (es. -7 = colore 7, spento). Rispecchia il
        // DXF, dove un layer spento e' proprio un group 62 negativo nella
        // tabella LAYER.
        LAYER_COLOR_OVERRIDES.put("TI_GRADO_TOLLERANZA", -1);
        LAYER_COLOR_OVERRIDES.put("RIPARTIZIONE_PIANI", -5);
        LAYER_COLOR_OVERRIDES.put("01811", 3);
        LAYER_COLOR_OVERRIDES.put("TI_NUMERO_OS", -7);
        LAYER_COLOR_OVERRIDES.put("TI_NUMERO_PUNTO_DI_CONFINE", -7);
        LAYER_COLOR_OVERRIDES.put("TI_NUMERO_PUNTO_SINGOLO_CS", -7);
        LAYER_COLOR_OVERRIDES.put("TI_NUMERO_PUNTO_SINGOLO_OS", -7);
        LAYER_COLOR_OVERRIDES.put("TI_NUMERO_PCGIURISDIZIONALE", -7);
        LAYER_COLOR_OVERRIDES.put("TI_LIMITE_BOSCO_LEGALE", -221);
        LAYER_COLOR_OVERRIDES.put("TI_PUNTO_SINGOLO_CS", -7);
        LAYER_COLOR_OVERRIDES.put("TI_PUNTO_SINGOLO_OS", -7);
        LAYER_COLOR_OVERRIDES.put("TI_PF_AUSILIARIO", -7);
        LAYER_COLOR_OVERRIDES.put("TI_PF_AUSILIARIO_TXT", -7);
        BLOCK_NAMES = new String[]{"GPBOL", "GPROH", "GPPFA", "GPUV", "GPSTE", "GPKST", "GPKRZ", "HGP", "LFP1", "LFP2", "HFP1", "HFP2", "HFP3", "LFP3ST", "LFP3BO", "LFP3UV", "LFP3KR", "EOPNT", "TRAMA", "PSING", "VIGNA", "PQUOT", "BACIDR", "DIRCOR"};
        BACIDR_SPLINE_UPPER_KNOTS = new double[]{0.0, 0.0, 0.0, 0.0, 0.1666759023, 0.2481242278, 0.3333425689, 0.4185609101, 0.5, 0.5814390899, 0.6666574311, 0.7518757722, 0.8333240977, 1.0, 1.0, 1.0, 1.0};
        BACIDR_SPLINE_UPPER_CTRL = new double[][]{{-2.0, 0.364}, {-1.8179238942, 0.4979851193}, {-1.4600011954, 0.7460759894}, {-0.9680146596, 0.5813072069}, {-0.6669504485, 0.363603671}, {-0.3648445172, 0.1472826262}, {0.0, 0.0233029771}, {0.3648445172, 0.1472826262}, {0.6669504485, 0.363603671}, {0.9680146596, 0.5813072069}, {1.4600011954, 0.7460759894}, {1.8179238942, 0.4979851193}, {2.0, 0.364}};
        BACIDR_SPLINE_UPPER_FIT = new double[][]{{-2.0, 0.364}, {-1.667, 0.576}, {-1.333, 0.664}, {-1.0, 0.576}, {-0.667, 0.364}, {-0.333, 0.152}, {0.0, 0.064}, {0.333, 0.152}, {0.667, 0.364}, {1.0, 0.576}, {1.333, 0.664}, {1.667, 0.576}, {2.0, 0.364}};
        BACIDR_SPLINE_LOWER_KNOTS = new double[]{0.0, 0.0, 0.0, 0.0, 0.1666781835, 0.2474799234, 0.3333448502, 0.4192097769, 0.5, 0.5807902231, 0.6666551498, 0.7525200766, 0.8333218165, 1.0, 1.0, 1.0, 1.0};
        BACIDR_SPLINE_LOWER_CTRL = new double[][]{{-2.0, -0.429}, {-1.8323307176, -0.280734983}, {-1.4655081643, 0.0353853149}, {-0.9568429581, -0.1745103425}, {-0.6670362326, -0.4294647463}, {-0.3758649573, -0.6826927071}, {0.0, -0.8405351006}, {0.3758649573, -0.6826927071}, {0.6670362326, -0.4294647463}, {0.9568429581, -0.1745103425}, {1.4655081643, 0.0353853149}, {1.8323307176, -0.280734983}, {2.0, -0.429}};
        BACIDR_SPLINE_LOWER_FIT = new double[][]{{-2.0, -0.429}, {-1.667, -0.174}, {-1.333, -0.069}, {-1.0, -0.174}, {-0.667, -0.429}, {-0.333, -0.684}, {0.0, -0.789}, {0.333, -0.684}, {0.667, -0.429}, {1.0, -0.174}, {1.333, -0.069}, {1.667, -0.174}, {2.0, -0.429}};
        // Layer che devono restare in PRIMO PIANO (punti di confine e
        // giurisdizionali, simboli e numeri dei punti fissi PFP/PFA): un punto
        // coperto da una linea di confine o da una copertura del suolo diventa
        // illeggibile. Usato da reorderEntitiesForDrawOrder.
        FRONT_LAYERS = new HashSet<String>(Arrays.asList("01651", "01652", "01653", "01654", "01655", "01656", "01657", "01812", "01111", "01112", "01121", "01122", "01131", "01132", "01133", "01134", "01141", "01151", "01161", "01119", "01129", "01139", "01149", "01159", "01169", "TI_NUMERO_PUNTO_DI_CONFINE", "TI_NUMERO_PCGIURISDIZIONALE"));
    }

    private static class CountingWriter
    extends FilterWriter {
        long count = 0L;

        CountingWriter(Writer writer) {
            super(writer);
        }

        @Override
        public void write(String string) throws IOException {
            super.write(string);
            this.count += (long)string.length();
        }

        @Override
        public void write(String string, int n, int n2) throws IOException {
            super.write(string, n, n2);
            this.count += (long)n2;
        }

        @Override
        public void write(int n) throws IOException {
            super.write(n);
            ++this.count;
        }

        @Override
        public void write(char[] cArray, int n, int n2) throws IOException {
            super.write(cArray, n, n2);
            this.count += (long)n2;
        }
    }
}

