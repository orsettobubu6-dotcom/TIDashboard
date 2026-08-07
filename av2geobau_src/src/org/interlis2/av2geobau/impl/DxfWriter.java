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

import ch.interlis.iom.IomObject;
import ch.interlis.iom_j.itf.impl.jtsext.geom.ArcSegment;
import ch.interlis.iom_j.itf.impl.jtsext.geom.CompoundCurve;
import ch.interlis.iom_j.itf.impl.jtsext.geom.CompoundCurveRing;
import ch.interlis.iom_j.itf.impl.jtsext.geom.CurveSegment;
import ch.interlis.iom_j.itf.impl.jtsext.geom.StraightSegment;
import ch.interlis.iox.IoxException;
import ch.interlis.iox_j.jts.Iox2jts;
import ch.interlis.iox_j.jts.Iox2jtsext;
import com.vividsolutions.jts.algorithm.Angle;
import com.vividsolutions.jts.geom.Coordinate;
import com.vividsolutions.jts.geom.LineString;
import com.vividsolutions.jts.geom.Polygon;
import java.io.Serializable;
import java.util.ArrayList;
import org.interlis2.av2geobau.impl.DxfUtil;

public class DxfWriter {
    public static final String IOM_DXF_TOPIC = "Dxf.Topic";
    public static final String IOM_TEXT = "Dxf.Topic.Text";
    public static final String IOM_MTEXT = "Dxf.Topic.MText";
    public static final String IOM_BLOCKINSERT = "Dxf.Topic.BlockInsert";
    public static final String IOM_2D_POLYLINE = "Dxf.Topic.Polyline2d";
    public static final String IOM_2D_POLYGON = "Dxf.Topic.Polygon2d";
    public static final String IOM_2D_SOLID = "Dxf.Topic.Solid2d";
    public static final String IOM_RAW = "Dxf.Topic.Raw";
    public static final String IOM_ATTR_RAW_TEXT = "raw_text";
    public static final String IOM_ATTR_TEXT = "text";
    public static final String IOM_ATTR_TEXT_SIZE = "text_size";
    public static final String IOM_ATTR_GEOM = "geom";
    public static final String IOM_ATTR_BLOCK = "block";
    public static final String IOM_ATTR_LAYERNAME = "layername";
    public static final String IOM_ATTR_ORI = "ori";
    public static final String IOM_ATTR_HALI = "hali";
    public static final String IOM_ATTR_VALI = "vali";
    public static final String IOM_ATTR_STYLE = "style";
    public static final String STYLE_ARIAL = "ARIAL";
    public static final String STYLE_ARIAL_BOLD = "ARIAL_BOLD";
    public static final String STYLE_ARIAL_ITALIC = "ARIAL_ITALIC";
    public static final String STYLE_ARIAL_BOLD_ITALIC = "ARIAL_BOLD_ITALIC";
    public static final String IOM_ATTR_LINETYPE = "linetype";
    public static final String IOM_ATTR_COLOR = "color";
    public static final String IOM_ATTR_WIDTH = "width";
    /** Handle della voce BLOCK_RECORD "*Model_Space", usato come owner
     * (group 330) di OGNI entita' scritta in sezione ENTITIES: obbligatorio
     * dal formato R13 in poi. Impostato da Av2geobau.doConversion subito dopo
     * writeTables, che e' cio' che lo rende noto. */
    public static String modelSpaceHandle = "0";
    public static final String LT_LANDSGRENZEN = "LANDSGRENZEN";
    public static final String LT_KANTONSGRENZEN = "KANTONSGRENZEN";
    public static final String LT_BEZIRKSGRENZEN = "BEZIRKSGRENZEN";
    public static final String LT_GEMEINDEGRENZEN = "GEMEINDEGRENZEN";
    public static final String LT_ZONENGRENZEN = "ZONENGRENZEN";
    public static final String LT_LIEGENSCHAFTSGRENZEN = "LIEGENSCHAFTSGRENZEN";
    public static final String LT_STREITIGE_GRENZEN = "STREITIGE_GRENZEN";
    public static final String LT_PROVISORISCHE_GRENZEN = "PROVISORISCHE_GRENZEN";
    public static final String LT_DIENSTBARKEITSGRENZEN = "DIENSTBARKEITSGRENZEN";
    public static final String LT_LIMITE_FOGLIO = "LIMITE_DEL_FOGLIO";
    public static final String LT_PUNTEGGIATO = "PUNTEGGIATO";
    public static final String LT_MISTO1 = "MISTO1";
    public static final String LT_MISTO2 = "MISTO2";
    public static final String LT_INTERROTTO = "INTERROTTO";
    public static final String LT_INTERROTTO1 = "INTERROTTO1";
    public static final String LT_INTERROTTO2 = "INTERROTTO2";
    public static final String LT_INTERROTTO3 = "INTERROTTO3";
    public static final String LT_CONFINE_INCOMPLETO = "CONFINE_INCOMPLETO";
    public static final String LT_LIMITE_BOSCO_LEGALE = "LIMITE_BOSCO_LEGALE";
    public static final String LT_CONF_GIUR_COMUNALE = "1100400000";
    public static final String LT_LIMITE_COPERTURA_SUOLO = "0200000000";
    private static int precision = 3;

    private static void writeHandle(StringBuffer stringBuffer) {
        stringBuffer.append(DxfUtil.toString(5, DxfUtil.nextHandle()));
        stringBuffer.append(DxfUtil.toString(330, modelSpaceHandle));
    }

    private static void writeOverrides(StringBuffer stringBuffer, IomObject iomObject) {
        String string;
        String string2 = iomObject.getattrvalue(IOM_ATTR_LINETYPE);
        if (string2 != null) {
            stringBuffer.append(DxfUtil.toString(6, string2));
        }
        if ((string = iomObject.getattrvalue(IOM_ATTR_COLOR)) != null) {
            stringBuffer.append(DxfUtil.toString(62, Integer.parseInt(string)));
        }
    }

    public static String feature2Dxf(IomObject iomObject) throws Exception {
        String string = iomObject.getobjecttag();
        if (string.equals(IOM_BLOCKINSERT)) {
            return DxfWriter.blockinsert2Dxf(iomObject);
        }
        if (string.equals(IOM_TEXT)) {
            return DxfWriter.text2Dxf(iomObject);
        }
        if (string.equals(IOM_MTEXT)) {
            return DxfWriter.mtext2Dxf(iomObject);
        }
        if (string.equals(IOM_2D_POLYLINE)) {
            return DxfWriter.lineString2d_2Dxf(iomObject);
        }
        if (string.equals(IOM_2D_POLYGON)) {
            return DxfWriter.polygon2d_2Dxf(iomObject);
        }
        if (string.equals(IOM_2D_SOLID)) {
            return DxfWriter.solid2Dxf(iomObject);
        }
        if (string.equals(IOM_RAW)) {
            return iomObject.getattrvalue(IOM_ATTR_RAW_TEXT);
        }
        throw new IllegalArgumentException("unexpected type " + string);
    }

    public static String hatch2Dxf(String string, Integer n, Coordinate[][] coordinateArray, boolean bl, double d) {
        return DxfWriter.hatch2Dxf(string, n, coordinateArray, bl, d, null);
    }

    public static String hatch2Dxf(String string, Integer n, Coordinate[][] coordinateArray, boolean bl, double d, Integer n2) {
        int n3;
        StringBuffer stringBuffer = new StringBuffer(DxfUtil.toString(0, "HATCH"));
        DxfWriter.writeHandle(stringBuffer);
        stringBuffer.append(DxfUtil.toString(100, "AcDbEntity"));
        stringBuffer.append(DxfUtil.toString(8, string));
        if (n != null) {
            stringBuffer.append(DxfUtil.toString(62, n));
        }
        if (n2 != null) {
            // Trasparenza per-entita' (group 440): alfa 0-255 nel byte basso,
            // 0x02000000 = "valore di trasparenza esplicito" (non BYLAYER).
            n3 = (int)Math.round((double)(100 - n2) / 100.0 * 255.0);
            int n4 = 0x2000000 | n3;
            // BUG REALE EVITATO QUI: si passa la stringa gia' formattata, NON
            // l'int. DxfUtil.toString(int,int) tronca silenziosamente ai
            // ultimi 6 caratteri (vedi int6car) e questo valore ne ha 8:
            // 33554572 diventerebbe "554572". Non "semplificare" tornando
            // all'overload (int,int).
            stringBuffer.append(DxfUtil.toString(440, Integer.toString(n4)));
        }
        stringBuffer.append(DxfUtil.toString(100, "AcDbHatch"));
        stringBuffer.append(DxfUtil.toString(10, "0.0"));
        stringBuffer.append(DxfUtil.toString(20, "0.0"));
        stringBuffer.append(DxfUtil.toString(30, "0.0"));
        stringBuffer.append(DxfUtil.toString(210, "0.0"));
        stringBuffer.append(DxfUtil.toString(220, "0.0"));
        stringBuffer.append(DxfUtil.toString(230, "1.0"));
        stringBuffer.append(DxfUtil.toString(2, bl ? "SOLID" : "DOTS"));
        stringBuffer.append(DxfUtil.toString(70, bl ? 1 : 0));
        stringBuffer.append(DxfUtil.toString(71, 0));
        stringBuffer.append(DxfUtil.toString(91, coordinateArray.length));
        for (n3 = 0; n3 < coordinateArray.length; ++n3) {
            Coordinate[] coordinateArray2 = coordinateArray[n3];
            int n5 = coordinateArray2.length - 1;
            int n6 = n3 == 0 ? 1 : 0;
            stringBuffer.append(DxfUtil.toString(92, n6));
            stringBuffer.append(DxfUtil.toString(93, n5));
            for (int i = 0; i < n5; ++i) {
                Coordinate coordinate = coordinateArray2[i];
                Coordinate coordinate2 = coordinateArray2[(i + 1) % n5];
                stringBuffer.append(DxfUtil.toString(72, 1));
                stringBuffer.append(DxfUtil.toString(10, coordinate.x, precision));
                stringBuffer.append(DxfUtil.toString(20, coordinate.y, precision));
                stringBuffer.append(DxfUtil.toString(11, coordinate2.x, precision));
                stringBuffer.append(DxfUtil.toString(21, coordinate2.y, precision));
            }
            // Group 97 (numero di edge di raccordo del contorno) scritto
            // SEMPRE, anche a 0: senza, AutoCAD 2024/2025 rifiuta il disegno.
            stringBuffer.append(DxfUtil.toString(97, 0));
        }
        stringBuffer.append(DxfUtil.toString(75, 1));
        stringBuffer.append(DxfUtil.toString(76, 1));
        if (!bl) {
            stringBuffer.append(DxfUtil.toString(52, "0.0"));
            stringBuffer.append(DxfUtil.toString(41, "1.0"));
            stringBuffer.append(DxfUtil.toString(77, 0));
            stringBuffer.append(DxfUtil.toString(78, 1));
            stringBuffer.append(DxfUtil.toString(53, "0.0"));
            stringBuffer.append(DxfUtil.toString(43, "0.0"));
            stringBuffer.append(DxfUtil.toString(44, "0.0"));
            stringBuffer.append(DxfUtil.toString(45, "0.0"));
            stringBuffer.append(DxfUtil.toString(46, d, precision));
            stringBuffer.append(DxfUtil.toString(79, 2));
            stringBuffer.append(DxfUtil.toString(49, "0.0"));
            stringBuffer.append(DxfUtil.toString(49, -d, precision));
        }
        stringBuffer.append(DxfUtil.toString(98, 0));
        return stringBuffer.toString();
    }

    public static String solid2Dxf(IomObject iomObject) throws Exception {
        String string = iomObject.getattrvalue(IOM_ATTR_LAYERNAME);
        StringBuffer stringBuffer = new StringBuffer(DxfUtil.toString(0, "SOLID"));
        DxfWriter.writeHandle(stringBuffer);
        stringBuffer.append(DxfUtil.toString(100, "AcDbEntity"));
        stringBuffer.append(DxfUtil.toString(8, string));
        DxfWriter.writeOverrides(stringBuffer, iomObject);
        stringBuffer.append(DxfUtil.toString(100, "AcDbTrace"));
        int n = iomObject.getattrvaluecount(IOM_ATTR_GEOM);
        Coordinate[] coordinateArray = new Coordinate[4];
        for (int i = 0; i < 4; ++i) {
            IomObject iomObject2 = iomObject.getattrobj(IOM_ATTR_GEOM, Math.min(i, n - 1));
            coordinateArray[i] = Iox2jts.coord2JTS(iomObject2);
        }
        stringBuffer.append(DxfUtil.toString(10, coordinateArray[0].x, precision));
        stringBuffer.append(DxfUtil.toString(20, coordinateArray[0].y, precision));
        stringBuffer.append(DxfUtil.toString(30, 0.0, precision));
        stringBuffer.append(DxfUtil.toString(11, coordinateArray[1].x, precision));
        stringBuffer.append(DxfUtil.toString(21, coordinateArray[1].y, precision));
        stringBuffer.append(DxfUtil.toString(31, 0.0, precision));
        stringBuffer.append(DxfUtil.toString(12, coordinateArray[2].x, precision));
        stringBuffer.append(DxfUtil.toString(22, coordinateArray[2].y, precision));
        stringBuffer.append(DxfUtil.toString(32, 0.0, precision));
        stringBuffer.append(DxfUtil.toString(13, coordinateArray[3].x, precision));
        stringBuffer.append(DxfUtil.toString(23, coordinateArray[3].y, precision));
        stringBuffer.append(DxfUtil.toString(33, 0.0, precision));
        return stringBuffer.toString();
    }

    public static String blockinsert2Dxf(IomObject iomObject) throws Exception {
        StringBuffer stringBuffer = null;
        String string = iomObject.getattrvalue(IOM_ATTR_LAYERNAME);
        stringBuffer = new StringBuffer(DxfUtil.toString(0, "INSERT"));
        DxfWriter.writeHandle(stringBuffer);
        stringBuffer.append(DxfUtil.toString(100, "AcDbEntity"));
        stringBuffer.append(DxfUtil.toString(8, string));
        DxfWriter.writeOverrides(stringBuffer, iomObject);
        stringBuffer.append(DxfUtil.toString(100, "AcDbBlockReference"));
        stringBuffer.append(DxfUtil.toString(2, iomObject.getattrvalue(IOM_ATTR_BLOCK)));
        Coordinate coordinate = Iox2jts.coord2JTS(iomObject.getattrobj(IOM_ATTR_GEOM, 0));
        stringBuffer.append(DxfUtil.toString(10, coordinate.x, precision));
        stringBuffer.append(DxfUtil.toString(20, coordinate.y, precision));
        if (!Double.isNaN(coordinate.z)) {
            double d = coordinate.z;
            if (d > 0.0) {
                stringBuffer.append(DxfUtil.toString(30, d, precision));
            } else {
                stringBuffer.append(DxfUtil.toString(30, 0.0f, precision));
            }
        } else {
            stringBuffer.append(DxfUtil.toString(30, 0.0f, precision));
        }
        String string2 = iomObject.getattrvalue(IOM_ATTR_ORI);
        stringBuffer.append(DxfUtil.toString(50, string2 != null ? string2 : "0.0"));
        stringBuffer.append(DxfUtil.toString(41, "0.5"));
        stringBuffer.append(DxfUtil.toString(42, "0.5"));
        stringBuffer.append(DxfUtil.toString(43, "0.5"));
        return stringBuffer.toString();
    }

    public static String text2Dxf(IomObject iomObject) throws Exception {
        StringBuffer stringBuffer = null;
        String string = iomObject.getattrvalue(IOM_ATTR_LAYERNAME);
        stringBuffer = new StringBuffer(DxfUtil.toString(0, "TEXT"));
        DxfWriter.writeHandle(stringBuffer);
        stringBuffer.append(DxfUtil.toString(100, "AcDbEntity"));
        stringBuffer.append(DxfUtil.toString(8, string));
        // writeOverrides anche sul TEXT (prima non c'era): serve al colore
        // per-etichetta dei numeri di Punto_di_confine, che deve coincidere
        // con quello del punto secondo la Provenienza (vedi mapPosPuntoDiConfine).
        DxfWriter.writeOverrides(stringBuffer, iomObject);
        stringBuffer.append(DxfUtil.toString(100, "AcDbText"));
        Coordinate coordinate = Iox2jts.coord2JTS(iomObject.getattrobj(IOM_ATTR_GEOM, 0));
        stringBuffer.append(DxfUtil.toString(10, coordinate.x, precision));
        stringBuffer.append(DxfUtil.toString(20, coordinate.y, precision));
        stringBuffer.append(DxfUtil.toString(30, 0.0f, precision));
        stringBuffer.append(DxfUtil.toString(40, Double.valueOf(iomObject.getattrvalue(IOM_ATTR_TEXT_SIZE))));
        stringBuffer.append(DxfUtil.toString(1, iomObject.getattrvalue(IOM_ATTR_TEXT)));
        String string2 = iomObject.getattrvalue(IOM_ATTR_STYLE);
        stringBuffer.append(DxfUtil.toString(7, string2 != null ? string2 : STYLE_ARIAL));
        Double d = null;
        String string3 = iomObject.getattrvalue(IOM_ATTR_ORI);
        if (string3 != null) {
            d = Double.valueOf(string3);
        }
        if (d != null) {
            stringBuffer.append(DxfUtil.toString(50, d));
        } else {
            stringBuffer.append(DxfUtil.toString(50, 0.0));
        }
        Integer n = null;
        String string4 = iomObject.getattrvalue(IOM_ATTR_HALI);
        if (string4 != null) {
            n = Integer.valueOf(string4);
        }
        if (n != null) {
            stringBuffer.append(DxfUtil.toString(72, n));
        } else {
            stringBuffer.append(DxfUtil.toString(72, 1));
        }
        stringBuffer.append(DxfUtil.toString(11, coordinate.x, precision));
        stringBuffer.append(DxfUtil.toString(21, coordinate.y, precision));
        stringBuffer.append(DxfUtil.toString(31, 0));
        Integer n2 = 2;
        String string5 = iomObject.getattrvalue(IOM_ATTR_VALI);
        if (string5 != null) {
            n2 = Integer.parseInt(string5);
        }
        stringBuffer.append(DxfUtil.toString(100, "AcDbText"));
        stringBuffer.append(DxfUtil.toString(73, n2.toString()));
        return stringBuffer.toString();
    }

    public static String mtext2Dxf(IomObject iomObject) throws Exception {
        StringBuffer stringBuffer = null;
        String string = iomObject.getattrvalue(IOM_ATTR_LAYERNAME);
        stringBuffer = new StringBuffer(DxfUtil.toString(0, "MTEXT"));
        DxfWriter.writeHandle(stringBuffer);
        stringBuffer.append(DxfUtil.toString(100, "AcDbEntity"));
        stringBuffer.append(DxfUtil.toString(8, string));
        stringBuffer.append(DxfUtil.toString(100, "AcDbMText"));
        Coordinate coordinate = Iox2jts.coord2JTS(iomObject.getattrobj(IOM_ATTR_GEOM, 0));
        stringBuffer.append(DxfUtil.toString(10, coordinate.x, precision));
        stringBuffer.append(DxfUtil.toString(20, coordinate.y, precision));
        stringBuffer.append(DxfUtil.toString(30, 0.0f, precision));
        double d = Double.valueOf(iomObject.getattrvalue(IOM_ATTR_TEXT_SIZE));
        stringBuffer.append(DxfUtil.toString(40, d));
        String string2 = iomObject.getattrvalue(IOM_ATTR_TEXT);
        stringBuffer.append(DxfUtil.toString(41, d * (double)Math.max(1, string2.length()) * 1.2));
        stringBuffer.append(DxfUtil.toString(71, DxfWriter.mtextAttachmentPoint(iomObject)));
        stringBuffer.append(DxfUtil.toString(72, 1));
        stringBuffer.append(DxfUtil.toString(1, string2));
        String string3 = iomObject.getattrvalue(IOM_ATTR_STYLE);
        stringBuffer.append(DxfUtil.toString(7, string3 != null ? string3 : STYLE_ARIAL));
        Double d2 = null;
        String string4 = iomObject.getattrvalue(IOM_ATTR_ORI);
        if (string4 != null) {
            d2 = Double.valueOf(string4);
        }
        stringBuffer.append(DxfUtil.toString(50, d2 != null ? d2 : 0.0));
        // Maschera di sfondo, impostazioni ESATTE della finestra "Background
        // Mask" di AutoCAD fornita dall'utente: 90=2 significa "usa il colore
        // di sfondo del disegno" (con 90=1 servirebbe invece un colore ACI
        // fisso nel group 63, qui volutamente non scritto perche' irrilevante
        // in modalita' 2); 45=1.0 e' il "border offset factor" (il default
        // AutoCAD sarebbe 1.5). E' il motivo per cui questi testi sono MTEXT
        // e non TEXT: il TEXT non supporta la maschera.
        stringBuffer.append(DxfUtil.toString(90, 2));
        stringBuffer.append(DxfUtil.toString(45, 1.0));
        return stringBuffer.toString();
    }

    private static int mtextAttachmentPoint(IomObject iomObject) throws Exception {
        int n = 0;
        String string = iomObject.getattrvalue(IOM_ATTR_HALI);
        if (string != null) {
            n = Integer.parseInt(string);
        }
        int n2 = 0;
        String string2 = iomObject.getattrvalue(IOM_ATTR_VALI);
        if (string2 != null) {
            n2 = Integer.parseInt(string2);
        }
        // MTEXT non ha HAli/VAli separati come il TEXT: usa un unico "punto di
        // ancoraggio" 1-9 (group 71) su griglia 3x3, numerata da alto-sinistra
        // (1) a basso-destra (9). Qui si ricompone: riga dal VAli
        // (3=top->0, 2=half->1, altrimenti base/bottom->2), colonna dall'HAli
        // (0=sinistra, 1=centro, 2=destra), indice = riga*3 + colonna + 1.
        int n3 = n2 == 3 ? 0 : (n2 == 2 ? 1 : 2);
        int n4 = Math.min(Math.max(n, 0), 2);
        return n3 * 3 + n4 + 1;
    }

    public static String lineString2d_2Dxf(IomObject iomObject) throws Exception {
        String string = iomObject.getattrvalue(IOM_ATTR_LAYERNAME);
        CompoundCurve compoundCurve = Iox2jtsext.polyline2JTS(iomObject.getattrobj(IOM_ATTR_GEOM, 0), false, 0.0);
        StringBuffer stringBuffer = new StringBuffer();
        DxfWriter.writePolyline(stringBuffer, string, compoundCurve, false, false, iomObject);
        return stringBuffer.toString();
    }

    private static void writePolyline(StringBuffer stringBuffer, String string, LineString lineString, boolean bl, boolean bl2) {
        DxfWriter.writePolyline(stringBuffer, string, lineString, bl, bl2, null);
    }

    private static void writePolyline(StringBuffer stringBuffer, String string, LineString lineString, boolean bl, boolean bl2, IomObject iomObject) {
        Object object;
        Coordinate coordinate;
        Serializable serializable;
        Object object2;
        ArrayList<CurveSegment> arrayList = new ArrayList<CurveSegment>();
        if (lineString instanceof CompoundCurveRing) {
            for (Object ringLine : ((CompoundCurveRing)lineString).getLines()) {
                arrayList.addAll(((CompoundCurve)ringLine).getSegments());
            }
        } else if (lineString instanceof CompoundCurve) {
            arrayList = ((CompoundCurve)lineString).getSegments();
        } else {
            Coordinate[] coords = lineString.getCoordinates();
            for (int i = 1; i < coords.length; ++i) {
                arrayList.add(new StraightSegment(coords[i - 1], coords[i]));
            }
        }
        stringBuffer.append(DxfUtil.toString(0, "POLYLINE"));
        DxfWriter.writeHandle(stringBuffer);
        stringBuffer.append(DxfUtil.toString(100, "AcDbEntity"));
        stringBuffer.append(DxfUtil.toString(8, string));
        if (iomObject != null) {
            DxfWriter.writeOverrides(stringBuffer, iomObject);
        }
        stringBuffer.append(DxfUtil.toString(100, bl ? "AcDb3dPolyline" : "AcDb2dPolyline"));
        stringBuffer.append(DxfUtil.toString(66, 1));
        stringBuffer.append(DxfUtil.toString(10, "0.0"));
        stringBuffer.append(DxfUtil.toString(20, "0.0"));
        stringBuffer.append(DxfUtil.toString(30, "0.0"));
        stringBuffer.append(DxfUtil.toString(70, (bl ? 8 : 0) + (bl2 ? 1 : 0)));
        if (iomObject != null && (object2 = iomObject.getattrvalue(IOM_ATTR_WIDTH)) != null) {
            double d = Double.parseDouble((String)object2);
            stringBuffer.append(DxfUtil.toString(40, d, precision));
            stringBuffer.append(DxfUtil.toString(41, d, precision));
        }
        for (int i = 0; i < arrayList.size(); ++i) {
            stringBuffer.append(DxfUtil.toString(0, "VERTEX"));
            DxfWriter.writeHandle(stringBuffer);
            stringBuffer.append(DxfUtil.toString(100, "AcDbEntity"));
            stringBuffer.append(DxfUtil.toString(8, string));
            stringBuffer.append(DxfUtil.toString(100, "AcDbVertex"));
            stringBuffer.append(DxfUtil.toString(100, bl ? "AcDb3dPolylineVertex" : "AcDb2dVertex"));
            serializable = (CurveSegment)arrayList.get(i);
            coordinate = ((CurveSegment)serializable).getStartPoint();
            stringBuffer.append(DxfUtil.toString(10, coordinate.x, precision));
            stringBuffer.append(DxfUtil.toString(20, coordinate.y, precision));
            if (bl && !Double.isNaN(coordinate.z)) {
                stringBuffer.append(DxfUtil.toString(30, coordinate.z, precision));
            } else {
                stringBuffer.append(DxfUtil.toString(30, 0.0, precision));
            }
            if (serializable instanceof ArcSegment && !((ArcSegment)(object = (ArcSegment)serializable)).isStraight()) {
                double d = DxfWriter.calcBulge((ArcSegment)object);
                String string2 = DxfUtil.toString(42, d, precision);
                stringBuffer.append(string2);
            }
            stringBuffer.append(DxfUtil.toString(70, 1));
        }
        stringBuffer.append(DxfUtil.toString(0, "VERTEX"));
        DxfWriter.writeHandle(stringBuffer);
        stringBuffer.append(DxfUtil.toString(100, "AcDbEntity"));
        stringBuffer.append(DxfUtil.toString(8, string));
        stringBuffer.append(DxfUtil.toString(100, "AcDbVertex"));
        stringBuffer.append(DxfUtil.toString(100, bl ? "AcDb3dPolylineVertex" : "AcDb2dVertex"));
        Coordinate coordinate2 = ((CurveSegment)arrayList.get(arrayList.size() - 1)).getEndPoint();
        stringBuffer.append(DxfUtil.toString(10, coordinate2.x, precision));
        stringBuffer.append(DxfUtil.toString(20, coordinate2.y, precision));
        if (bl && !Double.isNaN(coordinate2.z)) {
            stringBuffer.append(DxfUtil.toString(30, coordinate2.z, precision));
        } else {
            stringBuffer.append(DxfUtil.toString(30, 0.0, precision));
        }
        stringBuffer.append(DxfUtil.toString(70, 1));
        stringBuffer.append(DxfUtil.toString(0, "SEQEND"));
        DxfWriter.writeHandle(stringBuffer);
        stringBuffer.append(DxfUtil.toString(100, "AcDbEntity"));
    }

    public static double calcBulge(ArcSegment arcSegment) {
        double d = (Math.PI - Angle.angle((Coordinate)arcSegment.getMidPoint(), (Coordinate)arcSegment.getStartPoint()) + Angle.angle((Coordinate)arcSegment.getMidPoint(), (Coordinate)arcSegment.getEndPoint())) / 2.0;
        double d2 = Math.sin(d) / Math.cos(d);
        if (!Double.isFinite(d2)) {
            throw new IllegalStateException("unexpected bulge " + d2);
        }
        return d2;
    }

    public static String polygon2d_2Dxf(IomObject iomObject) {
        Polygon polygon;
        String string = iomObject.getattrvalue(IOM_ATTR_LAYERNAME);
        try {
            polygon = Iox2jtsext.surface2JTS(iomObject.getattrobj(IOM_ATTR_GEOM, 0), 0.0);
        }
        catch (IoxException ioxException) {
            throw new IllegalArgumentException(ioxException);
        }
        LineString lineString = polygon.getExteriorRing();
        StringBuffer stringBuffer = new StringBuffer();
        DxfWriter.writePolyline(stringBuffer, string, lineString, false, true, iomObject);
        for (int i = 0; i < polygon.getNumInteriorRing(); ++i) {
            lineString = polygon.getInteriorRingN(i);
            DxfWriter.writePolyline(stringBuffer, string, lineString, false, true, iomObject);
        }
        return stringBuffer.toString();
    }
}

