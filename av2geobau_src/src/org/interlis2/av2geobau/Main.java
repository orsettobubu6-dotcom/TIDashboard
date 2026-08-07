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

import ch.ehi.basics.i18n.ResourceBundle;
import ch.ehi.basics.logging.EhiLogger;
import ch.ehi.basics.settings.Settings;
import java.io.File;
import java.io.IOException;
import org.interlis2.av2geobau.Av2geobau;

public class Main {
    public static final String APP_NAME = "av2geobau";
    public static final String APP_JAR = "av2geobau.jar";
    private static String version = null;
    private static final String SETTINGS_FILE = System.getProperty("user.home") + "/.av2geobau";

    public static void main(String[] stringArray) {
        File file;
        File file2;
        boolean bl;
        int n;
        int n2;
        Settings settings = new Settings();
        settings.setValue("org.interlis2.av2geobau.ilidirs", "%ITF_DIR;http://models.interlis.ch/;%JAR_DIR/ilimodels");
        String string = Main.getAppHome();
        Object var3_3 = null;
        Object var4_4 = null;
        Object var5_5 = null;
        boolean bl2 = false;
        for (n2 = 0; n2 < stringArray.length; ++n2) {
            String string2 = stringArray[n2];
            if (string2.equals("--trace")) {
                EhiLogger.getInstance().setTraceFilter(false);
                continue;
            }
            if (string2.equals("--modeldir")) {
                settings.setValue("org.interlis2.av2geobau.ilidirs", stringArray[++n2]);
                continue;
            }
            if (string2.equals("--config")) {
                settings.setValue("org.interlis2.av2geobau.configfile", stringArray[++n2]);
                continue;
            }
            if (string2.equals("--perimeter")) {
                settings.setValue("org.interlis2.av2geobau.perimeter", stringArray[++n2]);
                continue;
            }
            if (string2.equals("--log")) {
                settings.setValue("org.interlis2.av2geobau.log", stringArray[++n2]);
                continue;
            }
            if (string2.equals("--proxy")) {
                settings.setValue("ch.interlis.ili2c.http_proxy_host", stringArray[++n2]);
                continue;
            }
            if (string2.equals("--proxyPort")) {
                settings.setValue("ch.interlis.ili2c.http_proxy_port", stringArray[++n2]);
                continue;
            }
            if (string2.equals("--version")) {
                Main.printVersion();
                return;
            }
            if (string2.equals("--help")) {
                Main.printVersion();
                System.err.println();
                Main.printDescription();
                System.err.println();
                Main.printUsage();
                System.err.println();
                System.err.println("OPTIONS");
                System.err.println();
                System.err.println("--config file         config file to control mapping.");
                System.err.println("--perimeter WKT       perimeter as WKT polygon, that is used to limit the conversion.");
                System.err.println("--log file            text file, that receives conversion results.");
                System.err.println("--modeldir %ITF_DIR;http://models.interlis.ch/;%JAR_DIR/ilimodels list of directories/repositories with ili-files.");
                System.err.println("--proxy host          proxy server to access model repositories.");
                System.err.println("--proxyPort port      proxy port to access model repositories.");
                System.err.println("--trace               enable trace messages.");
                System.err.println("--help                Display this help text.");
                System.err.println("--version             Display the version of av2geobau.");
                System.err.println();
                return;
            }
            if (!string2.startsWith("-")) break;
            EhiLogger.logAdaption((String)(string2 + ": unknown option; ignored"));
        }
        if ((n = stringArray.length - n2) != 2 && n == 0) {
            EhiLogger.logError((String)"av2geobau: wrong number of arguments");
            System.exit(2);
        }
        System.exit((bl = Av2geobau.convert(file2 = new File(stringArray[n2++]), file = new File(stringArray[n2++]), settings)) ? 0 : 1);
    }

    public static void readSettings(Settings settings) {
        File file = new File(SETTINGS_FILE);
        try {
            if (file.exists()) {
                settings.load(file);
            }
        }
        catch (IOException iOException) {
            EhiLogger.logError((String)("failed to load settings from file " + SETTINGS_FILE), (Throwable)iOException);
        }
    }

    public static void writeSettings(Settings settings) {
        File file = new File(SETTINGS_FILE);
        try {
            settings.store(file, "av2geobau settings");
        }
        catch (IOException iOException) {
            EhiLogger.logError((String)("failed to settings settings to file " + SETTINGS_FILE), (Throwable)iOException);
        }
    }

    protected static void printVersion() {
        System.err.println("av2geobau, Version " + Main.getVersion());
        System.err.println("  Developed by Eisenhut Informatik AG, CH-3400 Burgdorf");
    }

    protected static void printDescription() {
        System.err.println("DESCRIPTION");
        System.err.println("  Converts an ITF/DM01 file to a DXF/geobau.");
    }

    protected static void printUsage() {
        System.err.println("USAGE");
        System.err.println("  java -jar av2geobau.jar [Options] in.itf out.dxf");
    }

    public static String getVersion() {
        if (version == null) {
            java.util.ResourceBundle resourceBundle = java.util.ResourceBundle.getBundle(ResourceBundle.class2qpackageName(Main.class) + ".Version");
            StringBuffer stringBuffer = new StringBuffer(20);
            stringBuffer.append(resourceBundle.getString("version"));
            stringBuffer.append('-');
            stringBuffer.append(resourceBundle.getString("versionCommit"));
            version = stringBuffer.toString();
        }
        return version;
    }

    public static String getAppHome() {
        String[] stringArray;
        for (String string : stringArray = System.getProperty("java.class.path").split(System.getProperty("path.separator"))) {
            File file;
            String string2;
            if (!string.toLowerCase().endsWith(".jar") || !(string2 = (file = new File(string)).getName()).toLowerCase().startsWith(APP_NAME) || !(file = new File(file.getAbsolutePath())).exists()) continue;
            return file.getParent();
        }
        return null;
    }
}

