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
import ch.interlis.iom_j.Iom_jObject;
import ch.interlis.iox.IoxEvent;
import ch.interlis.iox.ObjectEvent;
import ch.interlis.iox_j.jts.Iox2jts;
import ch.interlis.iox_j.jts.Iox2jtsException;
import com.vividsolutions.jts.geom.Coordinate;
import com.vividsolutions.jts.geom.Envelope;
import com.vividsolutions.jts.geom.Geometry;
import com.vividsolutions.jts.geom.LineString;
import com.vividsolutions.jts.geom.GeometryFactory;
import com.vividsolutions.jts.geom.Point;
import com.vividsolutions.jts.geom.Polygon;
import com.vividsolutions.jts.geom.prep.PreparedGeometry;
import com.vividsolutions.jts.geom.prep.PreparedGeometryFactory;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import org.interlis2.av2geobau.impl.DxfWriter;

public class Mapper {
    private static final double STROKE_ARC = 1.0E-4;
    private List<IomObject> out = new ArrayList<IomObject>();
    private HashMap<String, String> lfp1_tid2nummer = new HashMap();
    private GeometryFactory jtsFactory = new GeometryFactory();
    private HashMap<String, String> lfp2_tid2nummer = new HashMap();
    private HashMap<String, String> lfp3_tid2nummer = new HashMap();
    private HashMap<String, String> hfp1_tid2nummer = new HashMap();
    private HashMap<String, String> hfp2_tid2nummer = new HashMap();
    private HashMap<String, String> hfp3_tid2nummer = new HashMap();
    private HashSet<String> gebaeude = new HashSet();
    private HashSet<String> gewaesser = new HashSet();
    /** tid della SuperficieCS -> suo Genere. La geometria dei simboli e delle
     * trame arriva in record ITF successivi a quello della superficie: senza
     * questa cache non si saprebbe piu' a quale genere applicarli, perche' il
     * file viene letto in un'unica passata in streaming. */
    private final Map<String, String> superficieCsGenereByTid = new HashMap<String, String>();
    private HashMap<String, String> gebaeudename = new HashMap();
    private HashMap<String, String> gewaessername = new HashMap();
    private HashMap<String, String> gebaeudenummer = new HashMap();
    private HashMap<String, String> einzelobjekte = new HashMap();
    private HashSet<String> geleise = new HashSet();
    HashMap<String, String> geleisename = new HashMap();
    private HashMap<String, String> flurname_tid2name = new HashMap();
    private HashMap<String, String> ortsname_tid2name = new HashMap();
    private HashMap<String, String> gelaendename_tid2name = new HashMap();
    private HashMap<String, String> projLiegenschaften = new HashMap();
    private HashMap<String, String> projSelbstRecht = new HashMap();
    private HashMap<String, String> liegenschaften = new HashMap();
    private HashMap<String, String> selbstRecht = new HashMap();
    private HashMap<String, String> lokalisationsName = new HashMap();
    private HashMap<String, String> hausnummerReal = new HashMap();
    private HashMap<String, String> hausnummerProjektiert = new HashMap();
    private Geometry perimeter = null;
    private HashMap<String, String> pfp1_tid2nummer = new HashMap();
    private HashMap<String, String> pfa1_tid2nummer = new HashMap();
    private HashMap<String, String> pfp2_tid2nummer = new HashMap();
    private HashMap<String, String> pfa2_tid2nummer = new HashMap();
    private HashMap<String, String> pfp3_tid2nummer = new HashMap();
    private HashMap<String, String> pfa3_tid2nummer = new HashMap();
    private HashMap<String, String> puntoDiConfine_tid2identificatore = new HashMap();
    /** tid del Punto_di_confine -> sua Provenienza. Serve perche' il testo del
     * numero (PosPunto_di_confine) va colorato come il punto, ma la Provenienza
     * e' un attributo del punto, letto in un record ITF diverso e precedente. */
    private HashMap<String, String> puntoDiConfine_tid2provenienza = new HashMap();
    private static final Map<String, Integer> PROVENIENZA_ACI = new HashMap<String, Integer>();
    private HashMap<String, String> pcGiurisdizionale_tid2identificatore = new HashMap();
    private static final String CS_DOMAIN = "__CS__";
    private static final double SCALE_MM_TO_M = 0.5;
    private static final int MAX_TRAMA_DOTS_PER_POLYGON = 4000;
    private HashMap<String, String> puntoSingolo_tid2identificatore = new HashMap();
    private static final Set<String> ZERO_WIDTH_LAYERS;
    private HashMap<String, String> nomeLocale_tid2nome = new HashMap();
    private HashMap<String, String> nomeDiLocalita_tid2nome = new HashMap();
    private HashMap<String, String> nomeDelLuogo_tid2nome = new HashMap();
    private HashMap<String, String> nomeLocalizzazione_tid2testo = new HashMap();
    private HashMap<String, String> numeroOS_tid2numero = new HashMap();
    private HashMap<String, String> ptoFissoAus_tid2numero = new HashMap();
    private HashMap<String, String> fondo_tid2numero = new HashMap();
    private HashMap<String, String> fondo_tid2numeroTraParentesi = new HashMap();
    private HashMap<String, String> nomeEdificio_tid2testo = new HashMap();
    private HashMap<String, String> nomeLocalitaCAP_tid2testo = new HashMap();
    private HashMap<String, String> numeroNE_tid2numero = new HashMap();
    private HashMap<String, String> numeroOggetto_tid2numero = new HashMap();

    public void addInput(IoxEvent ioxEvent) {
        if (ioxEvent instanceof ObjectEvent) {
            IomObject iomObject = ((ObjectEvent)ioxEvent).getIomObject();
            String string = iomObject.getobjecttag();
            if (string.equals("DM01AVCH24LV95D.FixpunkteKategorie1.LFP1")) {
                this.mapLFP1(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.FixpunkteKategorie1.LFP1Pos")) {
                this.mapLFP1Pos(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.FixpunkteKategorie2.LFP2")) {
                this.mapLFP2(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.FixpunkteKategorie2.LFP2Pos")) {
                this.mapLFP2Pos(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.FixpunkteKategorie3.LFP3")) {
                this.mapLFP3(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.FixpunkteKategorie3.LFP3Pos")) {
                this.mapLFP3Pos(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.FixpunkteKategorie1.HFP1")) {
                this.mapHFP1(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.FixpunkteKategorie1.HFP1Pos")) {
                this.mapHFP1Pos(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.FixpunkteKategorie2.HFP2")) {
                this.mapHFP2(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.FixpunkteKategorie2.HFP2Pos")) {
                this.mapHFP2Pos(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.FixpunkteKategorie3.HFP3")) {
                this.mapHFP3(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.FixpunkteKategorie3.HFP3Pos")) {
                this.mapHFP3Pos(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Bodenbedeckung.ProjBoFlaeche")) {
                this.mapProjBoFlaeche(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Bodenbedeckung.BoFlaeche")) {
                this.mapBoFlaeche(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Bodenbedeckung.Gebaeudenummer")) {
                this.mapBoFlaecheGebaeudenummer(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Bodenbedeckung.GebaeudenummerPos")) {
                this.mapBoFlaecheGebaeudenummerPos(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Bodenbedeckung.Objektname")) {
                this.mapBoFlaecheObjektname(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Bodenbedeckung.ObjektnamePos")) {
                this.mapBoFlaecheObjektnamePos(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Einzelobjekte.Einzelobjekt")) {
                this.mapEinzelobjekt(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Einzelobjekte.Flaechenelement")) {
                this.mapEOFlaechenelement(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Einzelobjekte.Linienelement")) {
                this.mapEOLinienelement(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Einzelobjekte.Punktelement")) {
                this.mapEOPunktelement(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Einzelobjekte.Objektname")) {
                this.mapEOObjektname(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Einzelobjekte.ObjektnamePos")) {
                this.mapEOObjektnamePos(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Nomenklatur.Flurname")) {
                this.mapFlurname(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Nomenklatur.FlurnamePos")) {
                this.mapFlurnamePos(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Nomenklatur.Ortsname")) {
                this.mapOrtsname(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Nomenklatur.OrtsnamePos")) {
                this.mapOrtsnamePos(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Nomenklatur.Gelaendename")) {
                this.mapGelaendename(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Nomenklatur.GelaendenamePos")) {
                this.mapGelaendenamePos(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Liegenschaften.Grenzpunkt")) {
                this.mapGrenzpunkt(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Liegenschaften.ProjGrundstueck")) {
                this.mapProjGrundstueck(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Liegenschaften.ProjGrundstueckPos")) {
                this.mapProjGrundstueckPos(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Liegenschaften.ProjLiegenschaft")) {
                this.mapProjLiegenschaft(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Liegenschaften.ProjSelbstRecht")) {
                this.mapProjSelbstRecht(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Liegenschaften.Grundstueck")) {
                this.mapGrundstueck(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Liegenschaften.GrundstueckPos")) {
                this.mapGrundstueckPos(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Liegenschaften.Liegenschaft")) {
                this.mapLiegenschaft(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Liegenschaften.SelbstRecht")) {
                this.mapSelbstRecht(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Rohrleitungen.Linienelement")) {
                this.mapRLLinienelement(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Gemeindegrenzen.Hoheitsgrenzpunkt")) {
                this.mapHoheitsgrenzpunkt(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Gemeindegrenzen.Gemeindegrenze")) {
                this.mapGemeindegrenze(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Bezirksgrenzen.Bezirksgrenzabschnitt")) {
                this.mapBezirksgrenzabschnitt(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Kantonsgrenzen.Kantonsgrenzabschnitt")) {
                this.mapKantonsgrenzabschnitt(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Landesgrenzen.Landesgrenzabschnitt")) {
                this.mapLandesgrenzabschnitt(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Gebaeudeadressen.LokalisationsName")) {
                this.mapLokalisationsName(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Gebaeudeadressen.LokalisationsNamePos")) {
                this.mapLokalisationsNamePos(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Gebaeudeadressen.Gebaeudeeingang")) {
                this.mapGebaeudeeingang(iomObject);
            } else if (string.equals("DM01AVCH24LV95D.Gebaeudeadressen.HausnummerPos")) {
                this.mapHausnummerPos(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Punti_fissiCategoria1.PFP1")) {
                this.mapPFP1(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Punti_fissiCategoria1.PosPFP1")) {
                this.mapPFP1Pos(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Punti_fissiCategoria1.PFA1")) {
                this.mapPFA1(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Punti_fissiCategoria1.PosPFA1")) {
                this.mapPFA1Pos(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Punti_fissiCategoria2.PFP2")) {
                this.mapPFP2(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Punti_fissiCategoria2.PosPFP2")) {
                this.mapPFP2Pos(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Punti_fissiCategoria2.PFA2")) {
                this.mapPFA2(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Punti_fissiCategoria2.PosPFA2")) {
                this.mapPFA2Pos(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Punti_fissiCategoria3.PFP3")) {
                this.mapPFP3(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Punti_fissiCategoria3.PosPFP3")) {
                this.mapPFP3Pos(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Punti_fissiCategoria3.PFA3")) {
                this.mapPFA3(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Punti_fissiCategoria3.PosPFA3")) {
                this.mapPFA3Pos(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Beni_immobili.Punto_di_confine")) {
                this.mapPuntoDiConfine(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Beni_immobili.PosPunto_di_confine")) {
                this.mapPosPuntoDiConfine(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Beni_immobili.Bene_immobile")) {
                this.mapBeneImmobile(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Beni_immobili.DPSSP")) {
                this.mapDPSSP(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Beni_immobili.Miniera")) {
                this.mapMiniera(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Confini_distrettuali.ParteConfineDistrettuale")) {
                this.mapParteConfineDistrettuale(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Confini_comunali.PCGiurisdizionale")) {
                this.mapPCGiurisdizionale(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Confini_comunali.PosPCGiurisdizionale")) {
                this.mapPosPCGiurisdizionale(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Copertura_del_suolo.SuperficieCS")) {
                this.mapSuperficieCS(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Copertura_del_suolo.SimboloSuperficieCS")) {
                this.mapSimboloSuperficieCS(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Copertura_del_suolo.Punto_singolo")) {
                this.mapPuntoSingoloCS(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Copertura_del_suolo.PosPunto_singolo")) {
                this.mapPosPuntoSingoloCS(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Oggetti_singoli.Punto_singolo")) {
                this.mapPuntoSingoloOS(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Oggetti_singoli.PosPunto_singolo")) {
                this.mapPosPuntoSingoloOS(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Altimetria.Punto_quotato")) {
                this.mapPuntoQuotato(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Copertura_del_suolo.Numero_di_edificio")) {
                this.mapNumeroDiEdificio(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Copertura_del_suolo.PosNumero_di_edificio")) {
                this.mapPosNumeroDiEdificio(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Copertura_del_suolo.Nome_Oggetto")) {
                this.mapNomeOggettoCS(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Copertura_del_suolo.PosNome_Oggetto")) {
                this.mapPosNomeOggettoCS(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Oggetti_singoli.Oggetto_singolo")) {
                this.mapOggettoSingolo(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Oggetti_singoli.Elemento_con_superficie")) {
                this.mapElementoConSuperficie(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Oggetti_singoli.Elemento_lineare")) {
                this.mapElementoLineare(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Oggetti_singoli.Elemento_puntiforme")) {
                this.mapElementoPuntiforme(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Oggetti_singoli.Nome_Oggetto")) {
                this.mapNomeOggettoOS(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Oggetti_singoli.PosNome_Oggetto")) {
                this.mapPosNomeOggettoOS(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Confini_nazionali.Parte_confine_nazionale")) {
                this.mapParteConfineNazionale(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Confini_cantonali.Parte_confine_cantonale")) {
                this.mapParteConfineCantonale(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Confini_comunali.Confine_comunale")) {
                this.mapConfineComunale(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Condotte.Elemento_lineare")) {
                this.mapCondotteElementoLineare(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Nomenclatura.Nome_locale")) {
                this.mapNomeLocale(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Nomenclatura.PosNome_locale")) {
                this.mapPosNomeLocale(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Nomenclatura.Nome_di_localita")) {
                this.mapNomeDiLocalita(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Nomenclatura.PosNome_di_localita")) {
                this.mapPosNomeDiLocalita(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Nomenclatura.Nome_del_luogo")) {
                this.mapNomeDelLuogo(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Nomenclatura.PosNome_del_luogo")) {
                this.mapPosNomeDelLuogo(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Indirizzi_degli_edifici.Nome_localizzazione")) {
                this.mapNomeLocalizzazione(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Indirizzi_degli_edifici.PosNome_localizzazione")) {
                this.mapPosNomeLocalizzazione(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Indirizzi_degli_edifici.Entrata_edificio")) {
                this.mapEntrataEdificio(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Indirizzi_degli_edifici.PosNumero_casa")) {
                this.mapPosNumeroCasa(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Limite_legale_del_bosco.Limite_del_bosco")) {
                this.mapLimiteDelBosco(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Margine_del_piano.Superficie_disegno")) {
                this.mapSuperficieDisegno(iomObject);
            } else if (string.equals("MD01MUTI7MN95.RipartizioneGT.Grado_di_tolleranza")) {
                this.mapGradoDiTolleranza(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Zone_di_movimento.Movimento")) {
                this.mapMovimento(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Ripartizione_dei_piani.Geometria_Piano")) {
                this.mapGeometriaPiano(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Oggetti_singoli.Numero_OS")) {
                this.mapNumeroOS(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Oggetti_singoli.PosNumero_OS")) {
                this.mapPosNumeroOS(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Punti_fissiCategoria3.Punto_fisso_ausiliario")) {
                this.mapPuntoFissoAusiliario(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Punti_fissiCategoria3.PosPto_fisso_ausiliario")) {
                this.mapPosPtoFissoAusiliario(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Beni_immobili.Fondo")) {
                this.mapFondo(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Beni_immobili.PosFondo")) {
                this.mapPosFondo(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Indirizzi_degli_edifici.Nome_edificio")) {
                this.mapNomeEdificio(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Indirizzi_degli_edifici.PosNome_Edificio")) {
                this.mapPosNomeEdificio(iomObject);
            } else if (string.equals("MD01MUTI7MN95.CAP_localita.Nome_localita")) {
                this.mapNomeLocalitaCAP(iomObject);
            } else if (string.equals("MD01MUTI7MN95.CAP_localita.PosNome_localita")) {
                this.mapPosNomeLocalitaCAP(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Copertura_del_suolo.Numero_NE")) {
                this.mapNumeroNE(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Copertura_del_suolo.PosNumero_NE")) {
                this.mapPosNumeroNE(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Oggetti_singoli.Numero_Oggetto")) {
                this.mapNumeroOggetto(iomObject);
            } else if (string.equals("MD01MUTI7MN95.Oggetti_singoli.PosNumero_Oggetto")) {
                this.mapPosNumeroOggetto(iomObject);
            }
        }
    }

    public void close() {
    }

    public IomObject getMappedObject() {
        if (this.out.size() == 0) {
            return null;
        }
        IomObject iomObject = this.out.remove(0);
        return iomObject;
    }

    private String mapOri(String string) {
        if (string == null) {
            return null;
        }
        double d = Double.parseDouble(string);
        string = Double.toString((100.0 - d) * 0.9);
        return string;
    }

    private String mapVali(String string) {
        if (string == null) {
            return null;
        }
        if (string.equals("Top")) {
            return "3";
        }
        if (string.equals("Cap")) {
            return "3";
        }
        if (string.equals("Half")) {
            return "2";
        }
        // BASE E BOTTOM ERANO SCAMBIATI. Il gruppo 73 del TEXT vale, secondo
        // la specifica DXF: 0 = Baseline, 1 = Bottom, 2 = Middle, 3 = Top.
        // Qui Base finiva su 1 (bottom) e Bottom su 0 (baseline), cioe' ogni
        // scritta ancorata a quei due valori usciva spostata in verticale
        // della profondita' dei discendenti del carattere. Sul comune di
        // prova sono 97 525 iscrizioni su 135 980, il 71.7%.
        //
        // MISURATO CON DUE LETTORI, e non sono d'accordo fra loro: scritto un
        // DXF con gruppo 73 = 0,1,2,3 e riletto,
        //     ezdxf 1.4.4   0 -> BASELINE, 1 -> BOTTOM   (la specifica)
        //     GDAL          0 -> bottom,   1 -> baseline (scambiati)
        // Su 2 e 3 concordano. Si segue la specifica.
        //
        // E' anche il motivo per cui il difetto non era mai emerso: il
        // controllo del plugin (verifica_dxf.py) rilegge il DXF con GDAL, che
        // scambia esattamente gli stessi due codici - i due errori si
        // annullavano e il secondo parere confermava il primo.
        if (string.equals("Base")) {
            return "0";
        }
        if (string.equals("Bottom")) {
            return "1";
        }
        return null;
    }

    private String mapHali(String string) {
        if (string == null) {
            return null;
        }
        if (string.equals("Left")) {
            return "0";
        }
        if (string.equals("Center")) {
            return "1";
        }
        if (string.equals("Right")) {
            return "2";
        }
        return null;
    }

    private void mapLFP1(IomObject iomObject) {
        Object object;
        String string = iomObject.getattrvalue("Begehbarkeit");
        String string2 = null;
        String string3 = null;
        if (string.equals("begehbar")) {
            string2 = "LFP1";
            string3 = "01111";
        } else if (string.equals("nicht_begehbar")) {
            string2 = "LFP1";
            string3 = "01112";
        } else {
            return;
        }
        String string4 = iomObject.getobjectoid();
        String string5 = iomObject.getattrvalue("Nummer");
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        this.lfp1_tid2nummer.put(string4, string5);
        object = iomObject.getattrvalue("HoeheGeom");
        if (object != null) {
            iomObject2.setattrvalue("C3", (String)object);
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        iom_jObject.setattrvalue("layername", string3);
        iom_jObject.setattrvalue("block", string2);
        iom_jObject.addattrobj("geom", iomObject2);
        this.out.add(iom_jObject);
    }

    private void mapLFP1Pos(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("LFP1Pos_von", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.lfp1_tid2nummer.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "01119";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.35");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapLFP2(IomObject iomObject) {
        Object object;
        String string = iomObject.getattrvalue("Begehbarkeit");
        String string2 = null;
        String string3 = null;
        if (string.equals("begehbar")) {
            string2 = "LFP2";
            string3 = "01121";
        } else if (string.equals("nicht_begehbar")) {
            string2 = "LFP2";
            string3 = "01122";
        } else {
            return;
        }
        String string4 = iomObject.getobjectoid();
        String string5 = iomObject.getattrvalue("Nummer");
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        this.lfp2_tid2nummer.put(string4, string5);
        object = iomObject.getattrvalue("HoeheGeom");
        if (object != null) {
            iomObject2.setattrvalue("C3", (String)object);
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        iom_jObject.setattrvalue("layername", string3);
        iom_jObject.setattrvalue("block", string2);
        iom_jObject.addattrobj("geom", iomObject2);
        this.out.add(iom_jObject);
    }

    private void mapLFP2Pos(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("LFP2Pos_von", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.lfp2_tid2nummer.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "01129";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.35");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapLFP3(IomObject iomObject) {
        Object object;
        String string = iomObject.getattrvalue("Punktzeichen");
        String string2 = null;
        String string3 = null;
        if (string.equals("Stein") || string.equals("Kunststoffzeichen")) {
            string2 = "LFP3ST";
            string3 = "01131";
        } else if (string.equals("Bolzen") || string.equals("Rohr")) {
            string2 = "LFP3BO";
            string3 = "01132";
        } else if (string.equals("Kreuz")) {
            string2 = "LFP3KR";
            string3 = "01133";
        } else if (string.equals("unversichert") || string.equals("Pfahl")) {
            string2 = "LFP3UV";
            string3 = "01134";
        } else {
            return;
        }
        String string4 = iomObject.getobjectoid();
        String string5 = iomObject.getattrvalue("Nummer");
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        this.lfp3_tid2nummer.put(string4, string5);
        object = iomObject.getattrvalue("HoeheGeom");
        if (object != null) {
            iomObject2.setattrvalue("C3", (String)object);
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        iom_jObject.setattrvalue("layername", string3);
        iom_jObject.setattrvalue("block", string2);
        iom_jObject.addattrobj("geom", iomObject2);
        this.out.add(iom_jObject);
    }

    private void mapLFP3Pos(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("LFP3Pos_von", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.lfp3_tid2nummer.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "01139";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.35");
        iom_jObject.setattrvalue("style", "ARIAL");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapHFP1(IomObject iomObject) {
        Object object;
        String string = null;
        String string2 = null;
        string = "HFP1";
        string2 = "01141";
        String string3 = iomObject.getobjectoid();
        String string4 = iomObject.getattrvalue("Nummer");
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        this.hfp1_tid2nummer.put(string3, string4);
        object = iomObject.getattrvalue("HoeheGeom");
        if (object != null) {
            iomObject2.setattrvalue("C3", (String)object);
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        iom_jObject.setattrvalue("layername", string2);
        iom_jObject.setattrvalue("block", string);
        iom_jObject.addattrobj("geom", iomObject2);
        this.out.add(iom_jObject);
    }

    private void mapHFP1Pos(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("HFP1Pos_von", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.hfp1_tid2nummer.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "01149";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.35");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapHFP2(IomObject iomObject) {
        Object object;
        String string = null;
        String string2 = null;
        string = "HFP2";
        string2 = "01151";
        String string3 = iomObject.getobjectoid();
        String string4 = iomObject.getattrvalue("Nummer");
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        this.hfp2_tid2nummer.put(string3, string4);
        object = iomObject.getattrvalue("HoeheGeom");
        if (object != null) {
            iomObject2.setattrvalue("C3", (String)object);
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        iom_jObject.setattrvalue("layername", string2);
        iom_jObject.setattrvalue("block", string);
        iom_jObject.addattrobj("geom", iomObject2);
        this.out.add(iom_jObject);
    }

    private void mapHFP2Pos(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("HFP2Pos_von", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.hfp2_tid2nummer.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "01159";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.35");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapHFP3(IomObject iomObject) {
        Object object;
        String string = null;
        String string2 = null;
        string = "HFP3";
        string2 = "01161";
        String string3 = iomObject.getobjectoid();
        String string4 = iomObject.getattrvalue("Nummer");
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        this.hfp3_tid2nummer.put(string3, string4);
        object = iomObject.getattrvalue("HoeheGeom");
        if (object != null) {
            iomObject2.setattrvalue("C3", (String)object);
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        iom_jObject.setattrvalue("layername", string2);
        iom_jObject.setattrvalue("block", string);
        iom_jObject.addattrobj("geom", iomObject2);
        this.out.add(iom_jObject);
    }

    private void mapHFP3Pos(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("HFP3Pos_von", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.hfp3_tid2nummer.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "01169";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.35");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapProjBoFlaeche(IomObject iomObject) {
        Object object;
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Art");
        String string3 = null;
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.surface2JTS(iomObject2, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        if (!string2.equals("Gebaeude")) {
            return;
        }
        string3 = "01911";
        this.gebaeude.add(string);
        object = new Iom_jObject("Dxf.Topic.Polygon2d", null);
        ((IomObject)object).setattrvalue("layername", string3);
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapBoFlaeche(IomObject iomObject) {
        Object object;
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Art");
        String string3 = null;
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.surface2JTS(iomObject2, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        if (string2.equals("Gebaeude")) {
            string3 = "01211";
            this.gebaeude.add(string);
        } else if (string2.equals("befestigt.Strasse_Weg")) {
            string3 = "01221";
        } else if (string2.equals("befestigt.Bahn")) {
            string3 = "01222";
        } else if (string2.equals("befestigt.Flugplatz")) {
            string3 = "01223";
        } else if (string2.equals("befestigt.Wasserbecken")) {
            string3 = "01224";
        } else if (string2.equals("befestigt.uebrige_befestigte")) {
            string3 = "01225";
        } else if (string2.equals("humusiert.Acker_Wiese_Weide")) {
            string3 = "01231";
        } else if (string2.equals("humusiert.Intensivkultur.Reben")) {
            string3 = "01232";
        } else if (string2.equals("humusiert.Intensivkultur.uebrige_Intensivkultur")) {
            string3 = "01233";
        } else if (string2.equals("humusiert.Gartenanlage")) {
            string3 = "01234";
        } else if (string2.equals("humusiert.Hoch_Flachmoor")) {
            string3 = "01235";
        } else if (string2.equals("humusiert.uebrige_humusierte")) {
            string3 = "01236";
        } else if (string2.equals("Gewaesser.fliessendes") || string2.equals("Gewaesser.stehendes")) {
            string3 = "01241";
            this.gewaesser.add(string);
        } else if (string2.equals("Gewaesser.Schilfguertel")) {
            string3 = "01242";
        } else if (string2.equals("bestockt.geschlossener_Wald")) {
            string3 = "01251";
        } else if (string2.equals("bestockt.uebrige_bestockte")) {
            string3 = "01252";
        } else if (string2.equals("vegetationslos.Fels")) {
            string3 = "01261";
        } else if (string2.equals("vegetationslos.Geroell_Sand")) {
            string3 = "01263";
        } else if (string2.equals("vegetationslos.Abbau_Deponie")) {
            string3 = "01264";
        } else if (string2.equals("vegetationslos.uebrige_vegetationslose")) {
            string3 = "01265";
        } else if (string2.equals("befestigt.Trottoir") || string2.equals("befestigt.Verkehrsinsel")) {
            string3 = "01332";
        } else {
            return;
        }
        object = new Iom_jObject("Dxf.Topic.Polygon2d", null);
        ((IomObject)object).setattrvalue("layername", string3);
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapBoFlaecheObjektname(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        IomObject iomObject2 = iomObject.getattrobj("Objektname_von", 0);
        String string2 = iomObject2.getobjectrefoid();
        String string3 = iomObject.getattrvalue("Name");
        if (this.gebaeude.contains(string2)) {
            this.gebaeudename.put(string, string3);
        } else if (this.gewaesser.contains(string2)) {
            this.gewaessername.put(string, string3);
        }
    }

    private void mapBoFlaecheObjektnamePos(IomObject iomObject) {
        IomObject iomObject2 = iomObject.getattrobj("ObjektnamePos_von", 0);
        String string = iomObject2.getobjectrefoid();
        String string2 = null;
        String string3 = null;
        if (this.gebaeudename.containsKey(string)) {
            string2 = this.gebaeudename.get(string);
            string3 = "01219";
        } else if (this.gewaessername.containsKey(string)) {
            string2 = this.gewaessername.get(string);
            string3 = "01249";
        }
        if (string3 != null) {
            String string4;
            String string5;
            Object object;
            Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
            iom_jObject.setattrvalue("layername", string3);
            iom_jObject.setattrvalue("text", string2);
            iom_jObject.setattrvalue("text_size", "0.9");
            IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
            if (this.perimeter != null) {
                try {
                    object = Iox2jts.coord2JTS(iomObject3);
                    if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                        return;
                    }
                }
                catch (Iox2jtsException iox2jtsException) {
                    throw new IllegalArgumentException(iox2jtsException);
                }
            }
            iom_jObject.addattrobj("geom", iomObject3);
            object = this.mapOri(iomObject.getattrvalue("Ori"));
            if (object != null) {
                iom_jObject.setattrvalue("ori", (String)object);
            }
            if ((string5 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
                iom_jObject.setattrvalue("hali", string5);
            }
            if ((string4 = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
                iom_jObject.setattrvalue("vali", string4);
            }
            this.out.add(iom_jObject);
        }
    }

    private void mapBoFlaecheGebaeudenummer(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        IomObject iomObject2 = iomObject.getattrobj("Gebaeudenummer_von", 0);
        String string2 = iomObject2.getobjectrefoid();
        String string3 = iomObject.getattrvalue("Nummer");
        if (this.gebaeude.contains(string2)) {
            this.gebaeudenummer.put(string, string3);
        }
    }

    private void mapBoFlaecheGebaeudenummerPos(IomObject iomObject) {
        IomObject iomObject2 = iomObject.getattrobj("GebaeudenummerPos_von", 0);
        String string = iomObject2.getobjectrefoid();
        String string2 = null;
        String string3 = null;
        if (this.gebaeudenummer.containsKey(string)) {
            string2 = this.gebaeudenummer.get(string);
            string3 = "01219";
        }
        if (string3 != null) {
            String string4;
            String string5;
            Object object;
            Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
            iom_jObject.setattrvalue("layername", string3);
            iom_jObject.setattrvalue("text", string2);
            iom_jObject.setattrvalue("text_size", "0.9");
            IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
            if (this.perimeter != null) {
                try {
                    object = Iox2jts.coord2JTS(iomObject3);
                    if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                        return;
                    }
                }
                catch (Iox2jtsException iox2jtsException) {
                    throw new IllegalArgumentException(iox2jtsException);
                }
            }
            iom_jObject.addattrobj("geom", iomObject3);
            object = this.mapOri(iomObject.getattrvalue("Ori"));
            if (object != null) {
                iom_jObject.setattrvalue("ori", (String)object);
            }
            if ((string5 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
                iom_jObject.setattrvalue("hali", string5);
            }
            if ((string4 = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
                iom_jObject.setattrvalue("vali", string4);
            }
            this.out.add(iom_jObject);
        }
    }

    private void mapEinzelobjekt(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Art");
        this.einzelobjekte.put(string, string2);
        if (string2.equals("Bahngeleise")) {
            this.geleise.add(string);
        }
    }

    private void mapEOFlaechenelement(IomObject iomObject) {
        Polygon polygon;
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                polygon = Iox2jts.surface2JTS(iomObject2, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)polygon)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        IomObject refObj = iomObject.getattrobj("Flaechenelement_von", 0);
        String string = refObj.getobjectrefoid();
        String string2 = this.einzelobjekte.get(string);
        String string3 = null;
        if (string2.equals("uebriger_Gebaeudeteil")) {
            string3 = "01311";
        } else if (string2.equals("wichtige_Treppe")) {
            string3 = "01312";
        } else if (string2.equals("Mauer") || string2.equals("massiver_Sockel")) {
            string3 = "01313";
        } else if (string2.equals("Aussichtsturm") || string2.equals("Silo_Turm_Gasometer")) {
            string3 = "01314";
        } else if (string2.equals("Bruecke_Passerelle") || string2.equals("Landungssteg")) {
            string3 = "01316";
        } else if (string2.equals("unterirdisches_Gebaeude") || string2.equals("Reservoir") || string2.equals("Unterstand")) {
            string3 = "01321";
        } else if (string2.equals("Tunnel_Unterfuehrung_Galerie")) {
            string3 = "01322";
        } else if (string2.equals("schmaler_Weg")) {
            string3 = "01331";
        } else if (string2.equals("Bahnsteig")) {
            string3 = "01332";
        } else if (string2.equals("eingedoltes_oeffentliches_Gewaesser")) {
            string3 = "01341";
        } else if (string2.equals("Uferverbauung") || string2.equals("Schwelle")) {
            string3 = "01342";
        } else if (string2.equals("Brunnen")) {
            string3 = "01351";
        } else if (string2.equals("Denkmal") || string2.equals("Ruine_archaeologisches_Objekt")) {
            string3 = "01352";
        } else if (string2.equals("weitere")) {
            string3 = "01370";
        } else {
            return;
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Polygon2d", null);
        iom_jObject.setattrvalue("layername", string3);
        iom_jObject.addattrobj("geom", iomObject2);
        this.out.add(iom_jObject);
    }

    private void mapEOLinienelement(IomObject iomObject) {
        IomObject iomObject2;
        IomObject iomObject3 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                LineString jtsLine = Iox2jts.polyline2JTSlineString(iomObject3, false, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)jtsLine)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iomObject2 = iomObject.getattrobj("Linienelement_von", 0);
        String string = iomObject2.getobjectrefoid();
        String string2 = this.einzelobjekte.get(string);
        String string3 = null;
        if (string2.equals("uebriger_Gebaeudeteil")) {
            string3 = "01311";
        } else if (string2.equals("wichtige_Treppe")) {
            string3 = "01312";
        } else if (string2.equals("Mauer") || string2.equals("massiver_Sockel")) {
            string3 = "01313";
        } else if (string2.equals("Aussichtsturm") || string2.equals("Silo_Turm_Gasometer")) {
            string3 = "01314";
        } else if (string2.equals("Hochkamin") || string2.equals("Mast_Antenne") || string2.equals("Pfeiler")) {
            string3 = "01315";
        } else if (string2.equals("unterirdisches_Gebaeude") || string2.equals("Reservoir") || string2.equals("Unterstand")) {
            string3 = "01321";
        } else if (string2.equals("Tunnel_Unterfuehrung_Galerie")) {
            string3 = "01322";
        } else if (string2.equals("schmaler_Weg")) {
            string3 = "01331";
        } else if (string2.equals("Bahngeleise") || string2.equals("Achse")) {
            string3 = "01334";
        } else if (string2.equals("Gondelbahn_Sesselbahn") || string2.equals("Luftseilbahn") || string2.equals("Skilift") || string2.equals("Faehre")) {
            string3 = "01335";
        } else if (string2.equals("Materialseilbahn")) {
            string3 = "01336";
        } else if (string2.equals("eingedoltes_oeffentliches_Gewaesser")) {
            string3 = "01341";
        } else if (string2.equals("Uferverbauung") || string2.equals("Schwelle")) {
            string3 = "01342";
        } else if (string2.equals("Rinnsal")) {
            string3 = "01343";
        } else if (string2.equals("Brunnen")) {
            string3 = "01351";
        } else if (string2.equals("Denkmal") || string2.equals("Ruine_archaeologisches_Objekt")) {
            string3 = "01352";
        } else if (string2.equals("Hochspannungsfreileitung")) {
            string3 = "01364";
        } else {
            return;
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Polyline2d", null);
        iom_jObject.setattrvalue("layername", string3);
        iom_jObject.addattrobj("geom", iomObject3);
        this.out.add(iom_jObject);
    }

    private void mapEOPunktelement(IomObject iomObject) {
        String string;
        Coordinate coordinate;
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                coordinate = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint(coordinate))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        IomObject refObj = iomObject.getattrobj("Punktelement_von", 0);
        String string2 = refObj.getobjectrefoid();
        String string3 = this.einzelobjekte.get(string2);
        String string4 = null;
        if (string3.equals("Bildstock_Kruzifix")) {
            string4 = "01353";
            string = "EOPNT";
        } else if (string3.equals("einzelner_Fels") || string3.equals("wichtiger_Einzelbaum")) {
            string4 = "01361";
            string = "EOPNT";
        } else if (string3.equals("Grotte_Hoehleneingang")) {
            string4 = "01363";
            string = "EOPNT";
        } else {
            return;
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        iom_jObject.setattrvalue("layername", string4);
        iom_jObject.setattrvalue("block", string);
        iom_jObject.addattrobj("geom", iomObject2);
        this.out.add(iom_jObject);
    }

    private void mapEOObjektname(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        IomObject iomObject2 = iomObject.getattrobj("Objektname_von", 0);
        String string2 = iomObject2.getobjectrefoid();
        String string3 = iomObject.getattrvalue("Name");
        if (this.geleise.contains(string2)) {
            this.geleisename.put(string, string3);
        }
    }

    private void mapEOObjektnamePos(IomObject iomObject) {
        IomObject iomObject2 = iomObject.getattrobj("ObjektnamePos_von", 0);
        String string = iomObject2.getobjectrefoid();
        String string2 = null;
        String string3 = null;
        if (this.geleisename.containsKey(string)) {
            string2 = this.geleisename.get(string);
            string3 = "01339";
        }
        if (string3 != null) {
            String string4;
            String string5;
            Object object;
            Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
            iom_jObject.setattrvalue("layername", string3);
            iom_jObject.setattrvalue("text", string2);
            iom_jObject.setattrvalue("text_size", "0.9");
            IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
            if (this.perimeter != null) {
                try {
                    object = Iox2jts.coord2JTS(iomObject3);
                    if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                        return;
                    }
                }
                catch (Iox2jtsException iox2jtsException) {
                    throw new IllegalArgumentException(iox2jtsException);
                }
            }
            iom_jObject.addattrobj("geom", iomObject3);
            object = this.mapOri(iomObject.getattrvalue("Ori"));
            if (object != null) {
                iom_jObject.setattrvalue("ori", (String)object);
            }
            if ((string5 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
                iom_jObject.setattrvalue("hali", string5);
            }
            if ((string4 = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
                iom_jObject.setattrvalue("vali", string4);
            }
            this.out.add(iom_jObject);
        }
    }

    private void mapFlurname(IomObject iomObject) {
        String string;
        String string2;
        if (this.perimeter != null) {
            IomObject geomObj = iomObject.getattrobj("Geometrie", 0);
            try {
                Polygon jtsPoly = Iox2jts.surface2JTS(geomObj, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)jtsPoly)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        string2 = iomObject.getobjectoid();
        string = iomObject.getattrvalue("Name");
        this.flurname_tid2name.put(string2, string);
    }

    private void mapFlurnamePos(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("FlurnamePos_von", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.flurname_tid2name.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "01519";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.8");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapOrtsname(IomObject iomObject) {
        String string;
        String string2;
        if (this.perimeter != null) {
            IomObject geomObj = iomObject.getattrobj("Geometrie", 0);
            try {
                Polygon jtsPoly = Iox2jts.surface2JTS(geomObj, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)jtsPoly)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        string2 = iomObject.getobjectoid();
        string = iomObject.getattrvalue("Name");
        this.ortsname_tid2name.put(string2, string);
    }

    private void mapOrtsnamePos(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("OrtsnamePos_von", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.ortsname_tid2name.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "01529";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.8");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapGelaendename(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Name");
        this.gelaendename_tid2name.put(string, string2);
    }

    private void mapGelaendenamePos(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("GelaendenamePos_von", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.gelaendename_tid2name.get(string3);
        String string5 = "01539";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.8");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapGrenzpunkt(IomObject iomObject) {
        String string = null;
        String string2 = null;
        String string3 = iomObject.getattrvalue("Punktzeichen");
        if (string3.equals("Stein")) {
            string = "GPSTE";
            string2 = "01651";
        } else if (string3.equals("Kunststoffzeichen")) {
            string = "GPKST";
            string2 = "01652";
        } else if (string3.equals("Bolzen")) {
            string = "GPBOL";
            string2 = "01653";
        } else if (string3.equals("Rohr")) {
            string = "GPROH";
            string2 = "01654";
        } else if (string3.equals("Pfahl")) {
            string = "GPPFA";
            string2 = "01655";
        } else if (string3.equals("Kreuz")) {
            string = "GPKRZ";
            string2 = "01656";
        } else if (string3.equals("unversichert")) {
            string = "GPUV";
            string2 = "01657";
        }
        if (string2 != null) {
            Object object;
            String string4 = iomObject.getobjectoid();
            IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
            if (this.perimeter != null) {
                try {
                    object = Iox2jts.coord2JTS(iomObject2);
                    if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                        return;
                    }
                }
                catch (Iox2jtsException iox2jtsException) {
                    throw new IllegalArgumentException(iox2jtsException);
                }
            }
            object = new Iom_jObject("Dxf.Topic.BlockInsert", null);
            ((IomObject)object).setattrvalue("layername", string2);
            ((IomObject)object).setattrvalue("block", string);
            ((IomObject)object).addattrobj("geom", iomObject2);
            this.out.add((IomObject)object);
        }
    }

    private void mapProjGrundstueck(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Art");
        String string3 = iomObject.getattrvalue("Nummer");
        if (string2.equals("Liegenschaft")) {
            this.projLiegenschaften.put(string, string3);
        } else if (string2.equals("SelbstRecht.Baurecht") || string2.equals("SelbstRecht.Konzessionsrecht") || string2.equals("SelbstRecht.Quellenrecht") || string2.equals("SelbstRecht.weitere")) {
            this.projSelbstRecht.put(string, string3);
        }
    }

    private void mapProjGrundstueckPos(IomObject iomObject) {
        IomObject iomObject2 = iomObject.getattrobj("ProjGrundstueckPos_von", 0);
        String string = iomObject2.getobjectrefoid();
        String string2 = null;
        String string3 = null;
        if (this.projLiegenschaften.containsKey(string)) {
            string2 = this.projLiegenschaften.get(string);
            string3 = "01629";
        } else if (this.projSelbstRecht.containsKey(string)) {
            string2 = "(" + this.projSelbstRecht.get(string) + ")";
            string3 = "01649";
        }
        if (string2 != null) {
            String string4;
            String string5;
            Object object;
            Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
            iom_jObject.setattrvalue("layername", string3);
            iom_jObject.setattrvalue("text", string2);
            iom_jObject.setattrvalue("text_size", "1.35");
            IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
            if (this.perimeter != null) {
                try {
                    object = Iox2jts.coord2JTS(iomObject3);
                    if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                        return;
                    }
                }
                catch (Iox2jtsException iox2jtsException) {
                    throw new IllegalArgumentException(iox2jtsException);
                }
            }
            iom_jObject.addattrobj("geom", iomObject3);
            object = this.mapOri(iomObject.getattrvalue("Ori"));
            if (object != null) {
                iom_jObject.setattrvalue("ori", (String)object);
            }
            if ((string5 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
                iom_jObject.setattrvalue("hali", string5);
            }
            if ((string4 = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
                iom_jObject.setattrvalue("vali", string4);
            }
            this.out.add(iom_jObject);
        }
    }

    private void mapProjLiegenschaft(IomObject iomObject) {
        Object object;
        String string = iomObject.getobjectoid();
        String string2 = null;
        string2 = "01621";
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.surface2JTS(iomObject2, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polygon2d", null);
        ((IomObject)object).setattrvalue("layername", string2);
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapProjSelbstRecht(IomObject iomObject) {
        Object object;
        String string = iomObject.getobjectoid();
        String string2 = null;
        string2 = "01641";
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.surface2JTS(iomObject2, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polygon2d", null);
        ((IomObject)object).setattrvalue("layername", string2);
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapGrundstueck(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Art");
        String string3 = iomObject.getattrvalue("Nummer");
        if (string2.equals("Liegenschaft")) {
            this.liegenschaften.put(string, string3);
        } else if (string2.equals("SelbstRecht.Baurecht") || string2.equals("SelbstRecht.Konzessionsrecht") || string2.equals("SelbstRecht.Quellenrecht") || string2.equals("SelbstRecht.weitere")) {
            this.selbstRecht.put(string, string3);
        }
    }

    private void mapGrundstueckPos(IomObject iomObject) {
        IomObject iomObject2 = iomObject.getattrobj("GrundstueckPos_von", 0);
        String string = iomObject2.getobjectrefoid();
        String string2 = null;
        String string3 = null;
        if (this.liegenschaften.containsKey(string)) {
            string2 = this.liegenschaften.get(string);
            string3 = "01619";
        } else if (this.selbstRecht.containsKey(string)) {
            string2 = "(" + this.selbstRecht.get(string) + ")";
            string3 = "01639";
        }
        if (string2 != null) {
            String string4;
            String string5;
            Object object;
            Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
            iom_jObject.setattrvalue("layername", string3);
            iom_jObject.setattrvalue("text", string2);
            iom_jObject.setattrvalue("text_size", "1.35");
            IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
            if (this.perimeter != null) {
                try {
                    object = Iox2jts.coord2JTS(iomObject3);
                    if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                        return;
                    }
                }
                catch (Iox2jtsException iox2jtsException) {
                    throw new IllegalArgumentException(iox2jtsException);
                }
            }
            iom_jObject.addattrobj("geom", iomObject3);
            object = this.mapOri(iomObject.getattrvalue("Ori"));
            if (object != null) {
                iom_jObject.setattrvalue("ori", (String)object);
            }
            if ((string5 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
                iom_jObject.setattrvalue("hali", string5);
            }
            if ((string4 = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
                iom_jObject.setattrvalue("vali", string4);
            }
            this.out.add(iom_jObject);
        }
    }

    private void mapLiegenschaft(IomObject iomObject) {
        Object object;
        String string = iomObject.getobjectoid();
        String string2 = null;
        string2 = "01611";
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.surface2JTS(iomObject2, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polygon2d", null);
        ((IomObject)object).setattrvalue("layername", string2);
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapSelbstRecht(IomObject iomObject) {
        Object object;
        String string = iomObject.getobjectoid();
        String string2 = null;
        string2 = "01631";
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.surface2JTS(iomObject2, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polygon2d", null);
        ((IomObject)object).setattrvalue("layername", string2);
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapRLLinienelement(IomObject iomObject) {
        Object object;
        String string = "01712";
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.polyline2JTSlineString(iomObject2, false, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polyline2d", null);
        ((IomObject)object).setattrvalue("layername", string);
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapHoheitsgrenzpunkt(IomObject iomObject) {
        String string = "HGP";
        String string2 = "01812";
        if (string2 != null) {
            Object object;
            String string3 = iomObject.getobjectoid();
            IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
            if (this.perimeter != null) {
                try {
                    object = Iox2jts.coord2JTS(iomObject2);
                    if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                        return;
                    }
                }
                catch (Iox2jtsException iox2jtsException) {
                    throw new IllegalArgumentException(iox2jtsException);
                }
            }
            object = new Iom_jObject("Dxf.Topic.BlockInsert", null);
            ((IomObject)object).setattrvalue("layername", string2);
            ((IomObject)object).setattrvalue("block", string);
            ((IomObject)object).addattrobj("geom", iomObject2);
            this.out.add((IomObject)object);
        }
    }

    private void mapGemeindegrenze(IomObject iomObject) {
        Object object;
        String string = iomObject.getobjectoid();
        String string2 = null;
        string2 = "01811";
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.surface2JTS(iomObject2, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polygon2d", null);
        ((IomObject)object).setattrvalue("layername", string2);
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapBezirksgrenzabschnitt(IomObject iomObject) {
        Object object;
        String string = "01821";
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.polyline2JTSlineString(iomObject2, false, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polyline2d", null);
        ((IomObject)object).setattrvalue("layername", string);
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapKantonsgrenzabschnitt(IomObject iomObject) {
        Object object;
        String string = "01831";
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.polyline2JTSlineString(iomObject2, false, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polyline2d", null);
        ((IomObject)object).setattrvalue("layername", string);
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapLandesgrenzabschnitt(IomObject iomObject) {
        Object object;
        String string = "01841";
        IomObject iomObject2 = iomObject.getattrobj("Geometrie", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.polyline2JTSlineString(iomObject2, false, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polyline2d", null);
        ((IomObject)object).setattrvalue("layername", string);
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapLokalisationsName(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Text");
        this.lokalisationsName.put(string, string2);
    }

    private void mapLokalisationsNamePos(IomObject iomObject) {
        IomObject iomObject2 = iomObject.getattrobj("LokalisationsNamePos_von", 0);
        String string = iomObject2.getobjectrefoid();
        String string2 = null;
        String string3 = null;
        if (this.lokalisationsName.containsKey(string)) {
            string2 = this.lokalisationsName.get(string);
            string3 = "01229";
        }
        if (string2 != null) {
            String string4;
            String string5;
            Object object;
            Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
            iom_jObject.setattrvalue("layername", string3);
            iom_jObject.setattrvalue("text", string2);
            iom_jObject.setattrvalue("text_size", "1.5");
            IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
            if (this.perimeter != null) {
                try {
                    object = Iox2jts.coord2JTS(iomObject3);
                    if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                        return;
                    }
                }
                catch (Iox2jtsException iox2jtsException) {
                    throw new IllegalArgumentException(iox2jtsException);
                }
            }
            iom_jObject.addattrobj("geom", iomObject3);
            object = this.mapOri(iomObject.getattrvalue("Ori"));
            if (object != null) {
                iom_jObject.setattrvalue("ori", (String)object);
            }
            if ((string5 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
                iom_jObject.setattrvalue("hali", string5);
            }
            if ((string4 = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
                iom_jObject.setattrvalue("vali", string4);
            }
            this.out.add(iom_jObject);
        }
    }

    private void mapGebaeudeeingang(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Hausnummer");
        String string3 = iomObject.getattrvalue("Status");
        if (string3.equals("real")) {
            this.hausnummerReal.put(string, string2);
        } else if (string3.equals("projektiert")) {
            this.hausnummerProjektiert.put(string, string2);
        }
    }

    private void mapHausnummerPos(IomObject iomObject) {
        IomObject iomObject2 = iomObject.getattrobj("HausnummerPos_von", 0);
        String string = iomObject2.getobjectrefoid();
        String string2 = null;
        String string3 = null;
        if (this.hausnummerReal.containsKey(string)) {
            string2 = this.hausnummerReal.get(string);
            string3 = "01219";
        } else if (this.hausnummerProjektiert.containsKey(string)) {
            string2 = this.hausnummerProjektiert.get(string);
            string3 = "01919";
        }
        if (string2 != null) {
            String string4;
            String string5;
            Object object;
            Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
            iom_jObject.setattrvalue("layername", string3);
            iom_jObject.setattrvalue("text", string2);
            iom_jObject.setattrvalue("text_size", "0.9");
            IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
            if (this.perimeter != null) {
                try {
                    object = Iox2jts.coord2JTS(iomObject3);
                    if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                        return;
                    }
                }
                catch (Iox2jtsException iox2jtsException) {
                    throw new IllegalArgumentException(iox2jtsException);
                }
            }
            iom_jObject.addattrobj("geom", iomObject3);
            object = this.mapOri(iomObject.getattrvalue("Ori"));
            if (object != null) {
                iom_jObject.setattrvalue("ori", (String)object);
            }
            if ((string5 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
                iom_jObject.setattrvalue("hali", string5);
            }
            if ((string4 = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
                iom_jObject.setattrvalue("vali", string4);
            }
            this.out.add(iom_jObject);
        }
    }

    public void setPerimeter(Geometry geometry) {
        this.perimeter = geometry;
    }

    private boolean intersectsPerimeter(Geometry geometry) {
        return this.perimeter.intersects(geometry);
    }

    private boolean matchesMateriale(String string, String ... stringArray) {
        if (string == null) {
            return false;
        }
        for (String string2 : stringArray) {
            if (!string.equals(string2) && !string.endsWith("." + string2)) continue;
            return true;
        }
        return false;
    }

    private String[] materialeToGrenzpunktBlockLayer(String string) {
        if (this.matchesMateriale(string, "termine_cippo")) {
            return new String[]{"GPSTE", "01651"};
        }
        if (this.matchesMateriale(string, "termine_artificiale")) {
            return new String[]{"GPKST", "01652"};
        }
        if (this.matchesMateriale(string, "bullone")) {
            return new String[]{"GPBOL", "01653"};
        }
        if (this.matchesMateriale(string, "tubo")) {
            return new String[]{"GPROH", "01654"};
        }
        if (this.matchesMateriale(string, "palo_picchetto")) {
            return new String[]{"GPPFA", "01655"};
        }
        if (this.matchesMateriale(string, "croce_scolpito", "croce", "scolpito")) {
            return new String[]{"GPKRZ", "01656"};
        }
        if (this.matchesMateriale(string, "non_materializzato")) {
            return new String[]{"GPUV", "01657"};
        }
        return null;
    }

    private String[] materialeToLFP3BlockLayer(String string) {
        if (this.matchesMateriale(string, "termine_cippo", "termine_artificiale")) {
            return new String[]{"LFP3ST", "01131"};
        }
        if (this.matchesMateriale(string, "bullone", "tubo")) {
            return new String[]{"LFP3BO", "01132"};
        }
        if (this.matchesMateriale(string, "croce_scolpito", "croce", "scolpito")) {
            return new String[]{"LFP3KR", "01133"};
        }
        if (this.matchesMateriale(string, "non_materializzato", "palo_picchetto")) {
            return new String[]{"LFP3UV", "01134"};
        }
        return null;
    }

    private void mapPFP1(IomObject iomObject) {
        Object object;
        String string = iomObject.getattrvalue("Accessibilita");
        String string2 = null;
        String string3 = null;
        if ("accessibile".equals(string)) {
            string2 = "LFP1";
            string3 = "01111";
        } else if ("inaccessibile".equals(string)) {
            string2 = "LFP1";
            string3 = "01112";
        } else {
            return;
        }
        String string4 = iomObject.getobjectoid();
        String string5 = iomObject.getattrvalue("Numero");
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        this.pfp1_tid2nummer.put(string4, string5);
        object = iomObject.getattrvalue("GeomAlt");
        if (object != null) {
            iomObject2.setattrvalue("C3", (String)object);
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        iom_jObject.setattrvalue("layername", string3);
        iom_jObject.setattrvalue("block", string2);
        iom_jObject.addattrobj("geom", iomObject2);
        this.out.add(iom_jObject);
    }

    private void mapPFP1Pos(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("PosPFP1_di", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.pfp1_tid2nummer.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "01119";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.MText", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.35");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapPFA1(IomObject iomObject) {
        Object object;
        String string = "HFP1";
        String string2 = "01141";
        String string3 = iomObject.getobjectoid();
        String string4 = iomObject.getattrvalue("Numero");
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        this.pfa1_tid2nummer.put(string3, string4);
        object = iomObject.getattrvalue("GeomAlt");
        if (object != null) {
            iomObject2.setattrvalue("C3", (String)object);
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        iom_jObject.setattrvalue("layername", string2);
        iom_jObject.setattrvalue("block", string);
        iom_jObject.addattrobj("geom", iomObject2);
        this.out.add(iom_jObject);
    }

    private void mapPFA1Pos(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("PosPFA1_di", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.pfa1_tid2nummer.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "01149";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.MText", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.35");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapPFP2(IomObject iomObject) {
        Object object;
        String string = iomObject.getattrvalue("Accessibilita");
        String string2 = null;
        String string3 = null;
        if ("accessibile".equals(string)) {
            string2 = "LFP2";
            string3 = "01121";
        } else if ("inaccessibile".equals(string)) {
            string2 = "LFP2";
            string3 = "01122";
        } else {
            return;
        }
        String string4 = iomObject.getobjectoid();
        String string5 = iomObject.getattrvalue("Numero");
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        this.pfp2_tid2nummer.put(string4, string5);
        object = iomObject.getattrvalue("GeomAlt");
        if (object != null) {
            iomObject2.setattrvalue("C3", (String)object);
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        iom_jObject.setattrvalue("layername", string3);
        iom_jObject.setattrvalue("block", string2);
        iom_jObject.addattrobj("geom", iomObject2);
        this.out.add(iom_jObject);
    }

    private void mapPFP2Pos(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("PosPFP2_di", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.pfp2_tid2nummer.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "01129";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.MText", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.35");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapPFA2(IomObject iomObject) {
        Object object;
        String string = "HFP2";
        String string2 = "01151";
        String string3 = iomObject.getobjectoid();
        String string4 = iomObject.getattrvalue("Numero");
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        this.pfa2_tid2nummer.put(string3, string4);
        object = iomObject.getattrvalue("GeomAlt");
        if (object != null) {
            iomObject2.setattrvalue("C3", (String)object);
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        iom_jObject.setattrvalue("layername", string2);
        iom_jObject.setattrvalue("block", string);
        iom_jObject.addattrobj("geom", iomObject2);
        this.out.add(iom_jObject);
    }

    private void mapPFA2Pos(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("PosPFA2_di", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.pfa2_tid2nummer.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "01159";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.MText", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.35");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapPFP3(IomObject iomObject) {
        Object object;
        String string = iomObject.getattrvalue("Segno");
        String[] stringArray = this.materialeToLFP3BlockLayer(string);
        if (stringArray == null) {
            return;
        }
        String string2 = stringArray[0];
        String string3 = stringArray[1];
        String string4 = iomObject.getobjectoid();
        String string5 = iomObject.getattrvalue("Numero");
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        this.pfp3_tid2nummer.put(string4, string5);
        object = iomObject.getattrvalue("GeomAlt");
        if (object != null) {
            iomObject2.setattrvalue("C3", (String)object);
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        iom_jObject.setattrvalue("layername", string3);
        iom_jObject.setattrvalue("block", string2);
        iom_jObject.addattrobj("geom", iomObject2);
        this.out.add(iom_jObject);
    }

    private void mapPFP3Pos(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("PosPFP3_di", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.pfp3_tid2nummer.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "01139";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.MText", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.35");
        iom_jObject.setattrvalue("style", "ARIAL");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapPFA3(IomObject iomObject) {
        Object object;
        String string = "HFP3";
        String string2 = "01161";
        String string3 = iomObject.getobjectoid();
        String string4 = iomObject.getattrvalue("Numero");
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        this.pfa3_tid2nummer.put(string3, string4);
        object = iomObject.getattrvalue("GeomAlt");
        if (object != null) {
            iomObject2.setattrvalue("C3", (String)object);
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        iom_jObject.setattrvalue("layername", string2);
        iom_jObject.setattrvalue("block", string);
        iom_jObject.addattrobj("geom", iomObject2);
        this.out.add(iom_jObject);
    }

    private void mapPFA3Pos(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("PosPFA3_di", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.pfa3_tid2nummer.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "01169";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.MText", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.35");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private Integer provenienzaToAci(String string) {
        if (string == null) {
            return null;
        }
        Integer n = PROVENIENZA_ACI.get(string.trim().toLowerCase());
        return n != null ? n : Integer.valueOf(7);
    }

    private void mapPuntoDiConfine(IomObject iomObject) {
        Object object;
        this.puntoDiConfine_tid2identificatore.put(iomObject.getobjectoid(), iomObject.getattrvalue("Identificatore"));
        this.puntoDiConfine_tid2provenienza.put(iomObject.getobjectoid(), iomObject.getattrvalue("Provenienza"));
        String string = iomObject.getattrvalue("Segno");
        String[] stringArray = this.materialeToGrenzpunktBlockLayer(string);
        if (stringArray == null) {
            return;
        }
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        ((IomObject)object).setattrvalue("layername", stringArray[1]);
        ((IomObject)object).setattrvalue("block", stringArray[0]);
        Integer n = this.provenienzaToAci(iomObject.getattrvalue("Provenienza"));
        if (n != null) {
            ((IomObject)object).setattrvalue("color", n.toString());
        }
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapPCGiurisdizionale(IomObject iomObject) {
        Object object;
        this.pcGiurisdizionale_tid2identificatore.put(iomObject.getobjectoid(), iomObject.getattrvalue("Identificatore"));
        String string = "HGP";
        String string2 = "01812";
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        ((IomObject)object).setattrvalue("layername", string2);
        ((IomObject)object).setattrvalue("block", string);
        Integer n = this.provenienzaToAci(iomObject.getattrvalue("Provenienza"));
        if (n != null) {
            ((IomObject)object).setattrvalue("color", n.toString());
        }
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private String linetypeForFondoGenereDiLinea(String string) {
        if (string == null) {
            return null;
        }
        if (this.matchesMateriale(string, "contestato")) {
            return "INTERROTTO3";
        }
        if (this.matchesMateriale(string, "incompleto")) {
            return "CONFINE_INCOMPLETO";
        }
        return null;
    }

    private String linetypeForCSGenereDiLinea(String string) {
        if (string == null) {
            return null;
        }
        if (this.matchesMateriale(string, "facciata_aperta")) {
            return "INTERROTTO2";
        }
        if (this.matchesMateriale(string, "parte_interrata")) {
            return "PUNTEGGIATO";
        }
        return null;
    }

    private Object[] lineStyleForOS(String string, String string2) {
        double d;
        double d2 = d = this.matchesMateriale(string, "sentiero") ? 0.3 : 0.2;
        if (this.matchesMateriale(string, "muro", "arginatura", "ruscello", "fontana", "ponte_passerella", "banchina", "rovina_oggetto_archeologico", "briglia", "silo_torre_gasometro", "zoccolo_massiccio", "ciminiera", "pilastro", "debarcadero", "scala_importante", "grotta_entrata_di_caverna", "masso_erratico", "monumento", "palo_antenna", "torre_panoramica", "concimaia", "riparo_fonico", "serra")) {
            if (this.matchesMateriale(string2, "parte_interrata")) {
                return new Object[]{"PUNTEGGIATO", d};
            }
            return new Object[]{null, d};
        }
        if (this.matchesMateriale(string, "accesso_lago")) {
            return new Object[]{"INTERROTTO1", d};
        }
        if (this.matchesMateriale(string, "muro_di_sostegno")) {
            if (this.matchesMateriale(string2, "parte_interrata")) {
                return new Object[]{"PUNTEGGIATO", d};
            }
            return new Object[]{null, d};
        }
        if (this.matchesMateriale(string, "muro_divisorio")) {
            return new Object[]{"INTERROTTO", d};
        }
        if (this.matchesMateriale(string, "sentiero")) {
            return new Object[]{"INTERROTTO2", d};
        }
        if (this.matchesMateriale(string, "edificio_sotterraneo", "edificio_sotterraneo_indipendente", "parte_sotterranea_di_edificio", "acqua_sotterranea_canalizzata", "serbatoio", "tunnel_sottopassaggio_galleria")) {
            return new Object[]{"PUNTEGGIATO", d};
        }
        if (this.matchesMateriale(string, "altra_parte_di_edificio", "scala", "altra_parte_costruttiva", "riparo", "fascia_boscata", "riparo_antivalanghe")) {
            return new Object[]{"INTERROTTO2", d};
        }
        if (this.matchesMateriale(string, "linea_aerea_ad_alta_tensione", "condotta_forzata")) {
            return new Object[]{"MISTO1", d};
        }
        if (this.matchesMateriale(string, "teleferica", "telecabina_seggiovia", "teleferica_per_il_materiale", "binari_ferrovia", "asse", "traghetto", "scilift")) {
            return new Object[]{"MISTO2", d};
        }
        return new Object[]{null, d};
    }

    private void emitGenereDiLineaOverlay(IomObject iomObject, String string, String string2) {
        try {
            int n = iomObject.getattrvaluecount("surface");
            for (int i = 0; i < n; ++i) {
                IomObject iomObject2 = iomObject.getattrobj("surface", i);
                int n2 = iomObject2.getattrvaluecount("boundary");
                for (int j = 0; j < n2; ++j) {
                    IomObject iomObject3 = iomObject2.getattrobj("boundary", j);
                    int n3 = iomObject3.getattrvaluecount("polyline");
                    for (int k = 0; k < n3; ++k) {
                        this.emitGenereDiLineaOverlayForPolyline(iomObject3.getattrobj("polyline", k), string, string2);
                    }
                }
            }
        }
        catch (Throwable throwable) {
            // empty catch block
        }
    }

    private void emitGenereDiLineaOverlayForPolyline(IomObject iomObject, String string, String string2) {
        int n = iomObject.getattrvaluecount("sequence");
        for (int i = 0; i < n; ++i) {
            IomObject iomObject2 = iomObject.getattrobj("sequence", i);
            int n2 = iomObject2.getattrvaluecount("segment");
            ArrayList<Coordinate> arrayList = new ArrayList<Coordinate>();
            String string3 = null;
            for (int j = 0; j < n2; ++j) {
                boolean bl;
                IomObject iomObject3 = iomObject2.getattrobj("segment", j);
                if (!"COORD".equals(iomObject3.getobjecttag())) {
                    this.flushGenereDiLineaRun(arrayList, string3, string, string2);
                    arrayList = new ArrayList();
                    string3 = null;
                    continue;
                }
                double d = Double.parseDouble(iomObject3.getattrvalue("C1"));
                double d2 = Double.parseDouble(iomObject3.getattrvalue("C2"));
                IomObject iomObject4 = iomObject3.getattrobj("lineattr", 0);
                String string4 = iomObject4 != null ? iomObject4.getattrvalue("Genere_di_linea") : null;
                boolean bl2 = bl = string4 == null && string3 == null || string4 != null && string4.equals(string3);
                if (arrayList.isEmpty()) {
                    string3 = string4;
                    arrayList.add(new Coordinate(d, d2));
                    continue;
                }
                if (bl) {
                    arrayList.add(new Coordinate(d, d2));
                    continue;
                }
                arrayList.add(new Coordinate(d, d2));
                this.flushGenereDiLineaRun(arrayList, string3, string, string2);
                arrayList = new ArrayList();
                arrayList.add(new Coordinate(d, d2));
                string3 = string4;
            }
            this.flushGenereDiLineaRun(arrayList, string3, string, string2);
        }
    }

    private void flushGenereDiLineaRun(ArrayList<Coordinate> arrayList, String string, String string2, String string3) {
        if (string == null || arrayList.size() < 2) {
            return;
        }
        String string4 = string3 == null ? this.linetypeForFondoGenereDiLinea(string) : (CS_DOMAIN.equals(string3) ? this.linetypeForCSGenereDiLinea(string) : (String)this.lineStyleForOS(string3, string)[0]);
        if (string4 == null) {
            return;
        }
        Iom_jObject iom_jObject = new Iom_jObject("POLYLINE", null);
        IomObject iomObject = iom_jObject.addattrobj("sequence", "SEGMENTS");
        for (Coordinate coordinate : arrayList) {
            iomObject.addattrobj("segment", this.coord2Iom(coordinate.x, coordinate.y));
        }
        Iom_jObject iom_jObject2 = new Iom_jObject("Dxf.Topic.Polyline2d", null);
        iom_jObject2.setattrvalue("layername", string2);
        iom_jObject2.setattrvalue("linetype", string4);
        iom_jObject2.addattrobj("geom", iom_jObject);
        this.out.add(iom_jObject2);
    }

    private void mapBeneImmobile(IomObject iomObject) {
        Object object;
        String string = "01611";
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.surface2JTS(iomObject2, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polygon2d", null);
        ((IomObject)object).setattrvalue("layername", string);
        // Bene_immobile (01611), larghezza 0.30 su richiesta esplicita.
        // circ154_allegato2 cap.3.6 dava 0.40 ("I tratti sono rappresentati per
        // una scala di riferimento 1:1000, con uno spessore di 0.40 mm"), ed e'
        // il valore usato fino ad ora anche dallo stile QGIS. La larghezza qui
        // e' in unita' di disegno, cioe' METRI: 0.40 significa una fascia nera
        // di 40 cm sul terreno, che al vero ingoia il simbolo del punto di
        // confine (il cerchio GPBOL ha raggio 0.5 m). Insieme a 01811 (Confine
        // comunale) e' uno dei soli due layer con larghezza non nulla: tutto il
        // resto - compreso 01221 (strada_sentiero), in passato un'eccezione a
        // 0.20 - sta a 0.00, perche' la resa degli altri generi e' affidata al
        // riempimento HATCH (emitTramaSuperficieCS), non allo spessore del
        // contorno.
        ((IomObject)object).setattrvalue("width", "0.30");
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
        this.emitGenereDiLineaOverlay(iomObject2, string, null);
    }

    private void mapDPSSP(IomObject iomObject) {
        Object object;
        String string = "01631";
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.surface2JTS(iomObject2, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polygon2d", null);
        ((IomObject)object).setattrvalue("layername", string);
        ((IomObject)object).setattrvalue("width", "0.00");
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
        this.emitGenereDiLineaOverlay(iomObject2, string, null);
    }

    private void mapMiniera(IomObject iomObject) {
        Object object;
        String string = "01631";
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.surface2JTS(iomObject2, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polygon2d", null);
        ((IomObject)object).setattrvalue("layername", string);
        ((IomObject)object).setattrvalue("width", "0.00");
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
        this.emitGenereDiLineaOverlay(iomObject2, string, null);
    }

    private String genereCSToLayer(String string) {
        if (this.matchesMateriale(string, "edificio")) {
            return "01211";
        }
        if (this.matchesMateriale(string, "strada_sentiero", "nazionale", "cantonale", "comunale", "altra_strada", "sentiero")) {
            return "01221";
        }
        if (this.matchesMateriale(string, "ferrovia")) {
            return "01222";
        }
        if (this.matchesMateriale(string, "aeroporto")) {
            return "01223";
        }
        if (this.matchesMateriale(string, "bacino_idrico", "piscina", "altro_bacino_idrico")) {
            return "01224";
        }
        if (this.matchesMateriale(string, "altro_rivestimento_duro")) {
            return "01225";
        }
        if (this.matchesMateriale(string, "campo_prato_pascolo")) {
            return "01231";
        }
        if (this.matchesMateriale(string, "vigna")) {
            return "01232";
        }
        if (this.matchesMateriale(string, "altra_coltura_intensiva")) {
            return "01233";
        }
        if (this.matchesMateriale(string, "giardino")) {
            return "01234";
        }
        if (this.matchesMateriale(string, "torbiera")) {
            return "01235";
        }
        if (this.matchesMateriale(string, "altro_humus")) {
            return "01236";
        }
        if (this.matchesMateriale(string, "specchio_acqua", "corso_acqua", "fiume", "torrente", "canale")) {
            return "01241";
        }
        if (this.matchesMateriale(string, "canneti")) {
            return "01242";
        }
        if (this.matchesMateriale(string, "bosco_fitto")) {
            return "01251";
        }
        if (this.matchesMateriale(string, "pascolo_boscato", "pascolo_boscato_fitto", "pascolo_boscato_rado", "altro_bosco")) {
            return "01252";
        }
        if (this.matchesMateriale(string, "roccia")) {
            return "01261";
        }
        if (this.matchesMateriale(string, "pietraia_sabbia")) {
            return "01263";
        }
        if (this.matchesMateriale(string, "cava_di_ghiaia_discarica")) {
            return "01264";
        }
        if (this.matchesMateriale(string, "ghiacciaio_nevaio", "altra_senza_vegetazione")) {
            return "01265";
        }
        if (this.matchesMateriale(string, "marciapiede", "spartitraffico")) {
            return "01332";
        }
        return null;
    }

    /** Colore ACI dell'edificio secondo "Qualita" (StandardQualita: MU93,
     * MP74, DP, PRP, altro): MU93 = grigio scuro (rilievo di misurazione
     * ufficiale, il caso piu' comune e affidabile), DP = arancio (dati
     * provvisori). Sono i colori voluti per la legenda, non un ripiego:
     * la trasparenza vera esiste ed e' usata altrove in questa stessa classe
     * (riempimento HATCH degli edifici al 45%, vedi emitTramaSuperficieCS),
     * dato che il DXF prodotto e' R2000/AC1015 e supporta il group 440.
     * MP74/PRP/altro: nessuna indicazione, colore di default (null = BYLAYER). */
    private Integer edificioColorForQualita(String string) {
        if (string == null) {
            return null;
        }
        if (string.equals("MU93")) {
            return 8;
        }
        if (string.equals("DP")) {
            return 41;
        }
        return null;
    }

    private void mapSuperficieCS(IomObject iomObject) {
        Polygon polygon;
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Genere");
        this.superficieCsGenereByTid.put(string, string2);
        String string3 = iomObject.getattrvalue("Qualita");
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        try {
            polygon = Iox2jts.surface2JTS(iomObject2, 1.0E-4);
        }
        catch (Iox2jtsException iox2jtsException) {
            throw new IllegalArgumentException(iox2jtsException);
        }
        if (this.perimeter != null && !this.intersectsPerimeter((Geometry)polygon)) {
            return;
        }
        if (this.matchesMateriale(string2, "edificio")) {
            this.gebaeude.add(string);
        } else if (this.matchesMateriale(string2, "specchio_acqua", "corso_acqua", "fiume", "torrente", "canale")) {
            this.gewaesser.add(string);
        }
        String string4 = this.genereCSToLayer(string2);
        if (string4 == null) {
            return;
        }
        Integer n = this.matchesMateriale(string2, "edificio") ? this.edificioColorForQualita(string3) : null;
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Polygon2d", null);
        iom_jObject.setattrvalue("layername", string4);
        iom_jObject.setattrvalue("width", "0.00");
        if (n != null) {
            iom_jObject.setattrvalue("color", n.toString());
        }
        if (this.matchesMateriale(string2, "sentiero")) {
            iom_jObject.setattrvalue("linetype", "INTERROTTO1");
        }
        iom_jObject.addattrobj("geom", iomObject2);
        this.out.add(iom_jObject);
        this.emitTramaSuperficieCS(string2, string4, polygon, n);
        this.emitGenereDiLineaOverlay(iomObject2, string4, CS_DOMAIN);
    }

    private void mapSimboloSuperficieCS(IomObject iomObject) {
        Object object;
        String string;
        IomObject iomObject2 = iomObject.getattrobj("SimboloSuperficieCS_di", 0);
        String string2 = iomObject2.getobjectrefoid();
        String string3 = this.superficieCsGenereByTid.get(string2);
        if (string3 == null) {
            return;
        }
        if (this.matchesMateriale(string3, "bacino_idrico", "piscina", "altro_bacino_idrico", "specchio_acqua")) {
            string = "BACIDR";
        } else if (this.matchesMateriale(string3, "corso_acqua", "fiume", "torrente", "canale")) {
            string = "DIRCOR";
        } else {
            return;
        }
        String string4 = this.genereCSToLayer(string3);
        if (string4 == null) {
            return;
        }
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        ((IomObject)object).setattrvalue("layername", string4);
        ((IomObject)object).setattrvalue("block", string);
        ((IomObject)object).addattrobj("geom", iomObject3);
        if (string.equals("DIRCOR")) {
            String string5 = iomObject.getattrvalue("Ori");
            String string6 = this.mapOri(string5 != null ? string5 : "0.0");
            ((IomObject)object).setattrvalue("ori", string6);
        }
        this.out.add((IomObject)object);
    }

    private void emitTramaSuperficieCS(String string, String string2, Polygon polygon, Integer n) {
        double d;
        if (this.matchesMateriale(string, "edificio")) {
            // Riempimento pieno con trasparenza al 45% (group 440), su
            // richiesta esplicita dell'utente: l'edificio resta leggibile
            // senza nascondere cio' che ha sotto.
            this.emitHatchFill(polygon, string2, n, true, 0.0, 45);
            return;
        }
        if (this.matchesMateriale(string, "vigna")) {
            this.emitVignaGrid(polygon, string2);
            return;
        }
        if (this.matchesMateriale(string, "bosco_fitto")) {
            d = 2.0;
        } else if (this.matchesMateriale(string, "altro_bosco")) {
            d = 4.0;
        } else if (this.matchesMateriale(string, "pascolo_boscato_fitto")) {
            d = 8.0;
        } else if (this.matchesMateriale(string, "pascolo_boscato_rado", "pascolo_boscato")) {
            d = 16.0;
        } else if (this.matchesMateriale(string, "pietraia_sabbia")) {
            d = 1.5;
        } else {
            return;
        }
        this.emitHatchFill(polygon, string2, n, false, d * 0.5);
    }

    private void emitHatchFill(Polygon polygon, String string, Integer n, boolean bl, double d) {
        this.emitHatchFill(polygon, string, n, bl, d, null);
    }

    private void emitHatchFill(Polygon polygon, String string, Integer n, boolean bl, double d, Integer n2) {
        int n3 = polygon.getNumInteriorRing();
        Coordinate[][] coordinateArrayArray = new Coordinate[1 + n3][];
        coordinateArrayArray[0] = polygon.getExteriorRing().getCoordinates();
        for (int i = 0; i < n3; ++i) {
            coordinateArrayArray[1 + i] = polygon.getInteriorRingN(i).getCoordinates();
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Raw", null);
        iom_jObject.setattrvalue("raw_text", DxfWriter.hatch2Dxf(string, n, coordinateArrayArray, bl, d, n2));
        this.out.add(iom_jObject);
    }

    private void emitVignaGrid(Polygon polygon, String string) {
        this.emitBlockGrid(polygon, string, 2.5, "VIGNA", null);
    }

    private void emitBlockGrid(Polygon polygon, String string, double d, String string2, Integer n) {
        if (d <= 0.0) {
            return;
        }
        Envelope envelope = polygon.getEnvelopeInternal();
        double d2 = envelope.getWidth() / d * (envelope.getHeight() / d);
        if (d2 > 4000.0) {
            d *= Math.sqrt(d2 / 4000.0);
        }
        PreparedGeometry preparedGeometry = PreparedGeometryFactory.prepare((Geometry)polygon);
        double d3 = Math.ceil(envelope.getMinX() / d) * d;
        double d4 = Math.ceil(envelope.getMinY() / d) * d;
        for (double d5 = d3; d5 <= envelope.getMaxX(); d5 += d) {
            for (double d6 = d4; d6 <= envelope.getMaxY(); d6 += d) {
                Point point = this.jtsFactory.createPoint(new Coordinate(d5, d6));
                if (!preparedGeometry.contains((Geometry)point)) continue;
                Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.BlockInsert", null);
                iom_jObject.setattrvalue("layername", string);
                iom_jObject.setattrvalue("block", string2);
                if (n != null) {
                    iom_jObject.setattrvalue("color", n.toString());
                }
                iom_jObject.addattrobj("geom", this.coord2Iom(d5, d6));
                this.out.add(iom_jObject);
            }
        }
    }

    private IomObject coord2Iom(double d, double d2) {
        Iom_jObject iom_jObject = new Iom_jObject("COORD", null);
        iom_jObject.setattrvalue("C1", this.formatCoord(d));
        iom_jObject.setattrvalue("C2", this.formatCoord(d2));
        return iom_jObject;
    }

    private String formatCoord(double d) {
        return String.format(Locale.US, "%.3f", d);
    }

    private void mapPuntoSingoloCS(IomObject iomObject) {
        this.mapPuntoSingolo(iomObject, "TI_PUNTO_SINGOLO_CS");
    }

    private void mapPuntoSingoloOS(IomObject iomObject) {
        this.mapPuntoSingolo(iomObject, "TI_PUNTO_SINGOLO_OS");
    }

    private void mapPuntoSingolo(IomObject iomObject, String string) {
        Object object;
        this.puntoSingolo_tid2identificatore.put(iomObject.getobjectoid(), iomObject.getattrvalue("Identificatore"));
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        ((IomObject)object).setattrvalue("layername", string);
        ((IomObject)object).setattrvalue("block", "PSING");
        // Colore ACI 241 per i punti singoli (Copertura del suolo e Oggetti
        // singoli): valore richiesto esplicitamente dall'utente.
        ((IomObject)object).setattrvalue("color", "241");
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapPuntoQuotato(IomObject iomObject) {
        Object object;
        String string = "TI_PUNTO_QUOTATO";
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        ((IomObject)object).setattrvalue("layername", string);
        ((IomObject)object).setattrvalue("block", "PQUOT");
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapNumeroDiEdificio(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        IomObject iomObject2 = iomObject.getattrobj("Numero_di_edificio_di", 0);
        String string2 = iomObject2.getobjectrefoid();
        String string3 = iomObject.getattrvalue("Numero");
        if (this.gebaeude.contains(string2)) {
            this.gebaeudenummer.put(string, string3);
        }
    }

    private void mapPosNumeroDiEdificio(IomObject iomObject) {
        IomObject iomObject2 = iomObject.getattrobj("PosNumero_di_edificio_di", 0);
        String string = iomObject2.getobjectrefoid();
        String string2 = null;
        String string3 = null;
        if (this.gebaeudenummer.containsKey(string)) {
            string2 = this.gebaeudenummer.get(string);
            string3 = "01219";
        }
        if (string3 != null) {
            String string4;
            String string5;
            Object object;
            Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
            iom_jObject.setattrvalue("layername", string3);
            iom_jObject.setattrvalue("text", string2);
            iom_jObject.setattrvalue("text_size", "0.9");
            iom_jObject.setattrvalue("style", "ARIAL_ITALIC");
            IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
            if (this.perimeter != null) {
                try {
                    object = Iox2jts.coord2JTS(iomObject3);
                    if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                        return;
                    }
                }
                catch (Iox2jtsException iox2jtsException) {
                    throw new IllegalArgumentException(iox2jtsException);
                }
            }
            iom_jObject.addattrobj("geom", iomObject3);
            object = this.mapOri(iomObject.getattrvalue("Ori"));
            if (object != null) {
                iom_jObject.setattrvalue("ori", (String)object);
            }
            if ((string5 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
                iom_jObject.setattrvalue("hali", string5);
            }
            if ((string4 = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
                iom_jObject.setattrvalue("vali", string4);
            }
            this.out.add(iom_jObject);
        }
    }

    private void mapNomeOggettoCS(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        IomObject iomObject2 = iomObject.getattrobj("Nome_Oggetto_di", 0);
        String string2 = iomObject2.getobjectrefoid();
        String string3 = iomObject.getattrvalue("Nome");
        if (this.gebaeude.contains(string2)) {
            this.gebaeudename.put(string, string3);
        } else if (this.gewaesser.contains(string2)) {
            this.gewaessername.put(string, string3);
        }
    }

    private void mapPosNomeOggettoCS(IomObject iomObject) {
        IomObject iomObject2 = iomObject.getattrobj("PosNome_Oggetto_di", 0);
        String string = iomObject2.getobjectrefoid();
        String string2 = null;
        String string3 = null;
        if (this.gebaeudename.containsKey(string)) {
            string2 = this.gebaeudename.get(string);
            string3 = "01219";
        } else if (this.gewaessername.containsKey(string)) {
            string2 = this.gewaessername.get(string);
            string3 = "01249";
        }
        if (string3 != null) {
            String string4;
            String string5;
            Object object;
            Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
            iom_jObject.setattrvalue("layername", string3);
            iom_jObject.setattrvalue("text", string2);
            iom_jObject.setattrvalue("text_size", "0.9");
            iom_jObject.setattrvalue("style", "ARIAL_ITALIC");
            IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
            if (this.perimeter != null) {
                try {
                    object = Iox2jts.coord2JTS(iomObject3);
                    if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                        return;
                    }
                }
                catch (Iox2jtsException iox2jtsException) {
                    throw new IllegalArgumentException(iox2jtsException);
                }
            }
            iom_jObject.addattrobj("geom", iomObject3);
            object = this.mapOri(iomObject.getattrvalue("Ori"));
            if (object != null) {
                iom_jObject.setattrvalue("ori", (String)object);
            }
            if ((string5 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
                iom_jObject.setattrvalue("hali", string5);
            }
            if ((string4 = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
                iom_jObject.setattrvalue("vali", string4);
            }
            this.out.add(iom_jObject);
        }
    }

    private double zeroWidthIfNeeded(String string, double d) {
        return ZERO_WIDTH_LAYERS.contains(string) ? 0.0 : d;
    }

    private String genereOSToLayer(String string) {
        if (this.matchesMateriale(string, "muro", "muro_di_sostegno", "muro_divisorio", "zoccolo_massiccio")) {
            return "01313";
        }
        if (this.matchesMateriale(string, "edificio_sotterraneo", "edificio_sotterraneo_indipendente", "parte_sotterranea_di_edificio", "serbatoio", "riparo")) {
            return "01321";
        }
        if (this.matchesMateriale(string, "altra_parte_di_edificio", "altra_parte_costruttiva")) {
            return "01311";
        }
        if (this.matchesMateriale(string, "scala", "scala_importante")) {
            return "01312";
        }
        if (this.matchesMateriale(string, "acqua_sotterranea_canalizzata")) {
            return "01341";
        }
        if (this.matchesMateriale(string, "tunnel_sottopassaggio_galleria")) {
            return "01322";
        }
        if (this.matchesMateriale(string, "ponte_passerella", "debarcadero")) {
            return "01316";
        }
        if (this.matchesMateriale(string, "banchina")) {
            return "01332";
        }
        if (this.matchesMateriale(string, "fontana", "sorgente")) {
            return "01351";
        }
        if (this.matchesMateriale(string, "silo_torre_gasometro", "torre_panoramica")) {
            return "01314";
        }
        if (this.matchesMateriale(string, "ciminiera", "palo_antenna", "pilastro")) {
            return "01315";
        }
        if (this.matchesMateriale(string, "monumento", "rovina_oggetto_archeologico")) {
            return "01352";
        }
        if (this.matchesMateriale(string, "arginatura", "briglia")) {
            return "01342";
        }
        if (this.matchesMateriale(string, "masso_erratico", "albero_importante")) {
            return "01361";
        }
        if (this.matchesMateriale(string, "ruscello")) {
            return "01343";
        }
        if (this.matchesMateriale(string, "sentiero")) {
            return "01331";
        }
        if (this.matchesMateriale(string, "linea_aerea_ad_alta_tensione")) {
            return "01364";
        }
        if (this.matchesMateriale(string, "binari_ferrovia", "asse")) {
            return "01334";
        }
        if (this.matchesMateriale(string, "teleferica", "telecabina_seggiovia", "scilift", "traghetto")) {
            return "01335";
        }
        if (this.matchesMateriale(string, "teleferica_per_il_materiale")) {
            return "01336";
        }
        if (this.matchesMateriale(string, "grotta_entrata_di_caverna")) {
            return "01363";
        }
        if (this.matchesMateriale(string, "cappella_statua_crocifisso")) {
            return "01353";
        }
        if (this.matchesMateriale(string, "altro", "concimaia", "riparo_fonico", "serra", "accesso_lago", "riparo_antivalanghe", "fascia_boscata", "condotta_forzata", "punto_di_riferimento")) {
            return "01370";
        }
        return null;
    }

    private void mapOggettoSingolo(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Genere");
        this.einzelobjekte.put(string, string2);
        if (this.matchesMateriale(string2, "binari_ferrovia")) {
            this.geleise.add(string);
        }
    }

    private void mapElementoConSuperficie(IomObject iomObject) {
        String string;
        String string2;
        String string3;
        Polygon polygon;
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                polygon = Iox2jts.surface2JTS(iomObject2, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)polygon)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        if ((string3 = this.genereOSToLayer(string2 = this.einzelobjekte.get(string = iomObject.getattrobj("Elemento_con_sup_di", 0).getobjectrefoid()))) == null) {
            return;
        }
        Object[] objectArray = this.lineStyleForOS(string2, null);
        String string4 = (String)objectArray[0];
        double d = this.zeroWidthIfNeeded(string3, (Double)objectArray[1]);
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Polygon2d", null);
        iom_jObject.setattrvalue("layername", string3);
        if (string4 != null) {
            iom_jObject.setattrvalue("linetype", string4);
        }
        iom_jObject.setattrvalue("width", Double.toString(d));
        iom_jObject.addattrobj("geom", iomObject2);
        this.out.add(iom_jObject);
        this.emitGenereDiLineaOverlay(iomObject2, string3, string2);
    }

    private void mapElementoLineare(IomObject iomObject) {
        String string;
        String string2;
        String string3;
        IomObject iomObject2;
        IomObject iomObject3 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                LineString jtsLine = Iox2jts.polyline2JTSlineString(iomObject3, false, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)jtsLine)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        if ((string3 = this.genereOSToLayer(string2 = this.einzelobjekte.get(string = (iomObject2 = iomObject.getattrobj("Elemento_lineare_di", 0)).getobjectrefoid()))) == null) {
            return;
        }
        Object[] objectArray = this.lineStyleForOS(string2, iomObject.getattrvalue("Genere_di_linea"));
        String string4 = (String)objectArray[0];
        double d = this.zeroWidthIfNeeded(string3, (Double)objectArray[1]);
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Polyline2d", null);
        iom_jObject.setattrvalue("layername", string3);
        if (string4 != null) {
            iom_jObject.setattrvalue("linetype", string4);
        }
        iom_jObject.setattrvalue("width", Double.toString(d));
        iom_jObject.addattrobj("geom", iomObject3);
        this.out.add(iom_jObject);
    }

    private void mapElementoPuntiforme(IomObject iomObject) {
        Coordinate coordinate;
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                coordinate = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint(coordinate))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        IomObject refObj = iomObject.getattrobj("Elemento_puntiforme_di", 0);
        String string = refObj.getobjectrefoid();
        String string2 = this.einzelobjekte.get(string);
        String string3 = null;
        String string4 = "EOPNT";
        if (this.matchesMateriale(string2, "cappella_statua_crocifisso")) {
            string3 = "01353";
        } else if (this.matchesMateriale(string2, "masso_erratico", "albero_importante")) {
            string3 = "01361";
        } else if (this.matchesMateriale(string2, "grotta_entrata_di_caverna")) {
            string3 = "01363";
        } else {
            return;
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        iom_jObject.setattrvalue("layername", string3);
        iom_jObject.setattrvalue("block", string4);
        iom_jObject.addattrobj("geom", iomObject2);
        this.out.add(iom_jObject);
    }

    private void mapNomeOggettoOS(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        IomObject iomObject2 = iomObject.getattrobj("Nome_Oggetto_di", 0);
        String string2 = iomObject2.getobjectrefoid();
        String string3 = iomObject.getattrvalue("Nome");
        if (this.geleise.contains(string2)) {
            this.geleisename.put(string, string3);
        }
    }

    private void mapPosNomeOggettoOS(IomObject iomObject) {
        IomObject iomObject2 = iomObject.getattrobj("PosNome_Oggetto_di", 0);
        String string = iomObject2.getobjectrefoid();
        String string2 = null;
        String string3 = null;
        if (this.geleisename.containsKey(string)) {
            string2 = this.geleisename.get(string);
            string3 = "01339";
        }
        if (string3 != null) {
            String string4;
            String string5;
            Object object;
            Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
            iom_jObject.setattrvalue("layername", string3);
            iom_jObject.setattrvalue("text", string2);
            iom_jObject.setattrvalue("text_size", "0.9");
            iom_jObject.setattrvalue("style", "ARIAL_ITALIC");
            IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
            if (this.perimeter != null) {
                try {
                    object = Iox2jts.coord2JTS(iomObject3);
                    if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                        return;
                    }
                }
                catch (Iox2jtsException iox2jtsException) {
                    throw new IllegalArgumentException(iox2jtsException);
                }
            }
            iom_jObject.addattrobj("geom", iomObject3);
            object = this.mapOri(iomObject.getattrvalue("Ori"));
            if (object != null) {
                iom_jObject.setattrvalue("ori", (String)object);
            }
            if ((string5 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
                iom_jObject.setattrvalue("hali", string5);
            }
            if ((string4 = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
                iom_jObject.setattrvalue("vali", string4);
            }
            this.out.add(iom_jObject);
        }
    }

    private String linetypeForValidita(String string) {
        if (string == null) {
            return null;
        }
        if (string.equals("contestato")) {
            return "STREITIGE_GRENZEN";
        }
        if (string.equals("provvisorio")) {
            return "PROVISORISCHE_GRENZEN";
        }
        return null;
    }

    private double widthForValidita(String string) {
        return "in_vigore".equals(string) ? 0.4 : 0.3;
    }

    private void mapParteConfineNazionale(IomObject iomObject) {
        Object object;
        String string = "01841";
        String string2 = iomObject.getattrvalue("Validita");
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.polyline2JTSlineString(iomObject2, false, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polyline2d", null);
        ((IomObject)object).setattrvalue("layername", string);
        ((IomObject)object).setattrvalue("width", "0.00");
        String string3 = this.linetypeForValidita(string2);
        if (string3 != null) {
            ((IomObject)object).setattrvalue("linetype", string3);
        }
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapParteConfineCantonale(IomObject iomObject) {
        Object object;
        String string = "01831";
        String string2 = iomObject.getattrvalue("Validita");
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.polyline2JTSlineString(iomObject2, false, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polyline2d", null);
        ((IomObject)object).setattrvalue("layername", string);
        ((IomObject)object).setattrvalue("width", "0.00");
        String string3 = this.linetypeForValidita(string2);
        if (string3 != null) {
            ((IomObject)object).setattrvalue("linetype", string3);
        }
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapParteConfineDistrettuale(IomObject iomObject) {
        Object object;
        String string = "01821";
        String string2 = iomObject.getattrvalue("Validita");
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.polyline2JTSlineString(iomObject2, false, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polyline2d", null);
        ((IomObject)object).setattrvalue("layername", string);
        ((IomObject)object).setattrvalue("width", "0.00");
        String string3 = this.linetypeForValidita(string2);
        if (string3 != null) {
            ((IomObject)object).setattrvalue("linetype", string3);
        }
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapConfineComunale(IomObject iomObject) {
        Object object;
        String string = "01811";
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.surface2JTS(iomObject2, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polygon2d", null);
        ((IomObject)object).setattrvalue("layername", string);
        ((IomObject)object).setattrvalue("width", "0.30");
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
        this.emitConfineComunaleInVigoreOverlay(iomObject2, string);
    }

    private void emitConfineComunaleInVigoreOverlay(IomObject iomObject, String string) {
        try {
            int n = iomObject.getattrvaluecount("surface");
            for (int i = 0; i < n; ++i) {
                IomObject iomObject2 = iomObject.getattrobj("surface", i);
                int n2 = iomObject2.getattrvaluecount("boundary");
                for (int j = 0; j < n2; ++j) {
                    IomObject iomObject3 = iomObject2.getattrobj("boundary", j);
                    int n3 = iomObject3.getattrvaluecount("polyline");
                    for (int k = 0; k < n3; ++k) {
                        this.emitConfineComunaleInVigoreOverlayForPolyline(iomObject3.getattrobj("polyline", k), string);
                    }
                }
            }
        }
        catch (Throwable throwable) {
            // empty catch block
        }
    }

    private void emitConfineComunaleInVigoreOverlayForPolyline(IomObject iomObject, String string) {
        int n = iomObject.getattrvaluecount("sequence");
        for (int i = 0; i < n; ++i) {
            IomObject iomObject2 = iomObject.getattrobj("sequence", i);
            int n2 = iomObject2.getattrvaluecount("segment");
            ArrayList<Coordinate> arrayList = new ArrayList<Coordinate>();
            boolean bl = false;
            for (int j = 0; j < n2; ++j) {
                IomObject iomObject3 = iomObject2.getattrobj("segment", j);
                if (!"COORD".equals(iomObject3.getobjecttag())) {
                    this.flushConfineComunaleInVigoreRun(arrayList, bl, string);
                    arrayList = new ArrayList();
                    bl = false;
                    continue;
                }
                double d = Double.parseDouble(iomObject3.getattrvalue("C1"));
                double d2 = Double.parseDouble(iomObject3.getattrvalue("C2"));
                IomObject iomObject4 = iomObject3.getattrobj("lineattr", 0);
                String string2 = iomObject4 != null ? iomObject4.getattrvalue("Genere_di_linea") : null;
                boolean bl2 = "in_vigore".equals(string2);
                if (arrayList.isEmpty()) {
                    bl = bl2;
                    arrayList.add(new Coordinate(d, d2));
                    continue;
                }
                if (bl2 == bl) {
                    arrayList.add(new Coordinate(d, d2));
                    continue;
                }
                arrayList.add(new Coordinate(d, d2));
                this.flushConfineComunaleInVigoreRun(arrayList, bl, string);
                arrayList = new ArrayList();
                arrayList.add(new Coordinate(d, d2));
                bl = bl2;
            }
            this.flushConfineComunaleInVigoreRun(arrayList, bl, string);
        }
    }

    private void flushConfineComunaleInVigoreRun(ArrayList<Coordinate> arrayList, boolean bl, String string) {
        if (!bl || arrayList.size() < 2) {
            return;
        }
        Iom_jObject iom_jObject = new Iom_jObject("POLYLINE", null);
        IomObject iomObject = iom_jObject.addattrobj("sequence", "SEGMENTS");
        for (Coordinate coordinate : arrayList) {
            iomObject.addattrobj("segment", this.coord2Iom(coordinate.x, coordinate.y));
        }
        Iom_jObject iom_jObject2 = new Iom_jObject("Dxf.Topic.Polyline2d", null);
        iom_jObject2.setattrvalue("layername", string);
        iom_jObject2.setattrvalue("width", "0.40");
        iom_jObject2.addattrobj("geom", iom_jObject);
        this.out.add(iom_jObject2);
    }

    private void mapCondotteElementoLineare(IomObject iomObject) {
        Object object;
        String string = "01712";
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.polyline2JTSlineString(iomObject2, false, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polyline2d", null);
        ((IomObject)object).setattrvalue("layername", string);
        ((IomObject)object).setattrvalue("width", "0.00");
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapNomeLocale(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Nome");
        this.nomeLocale_tid2nome.put(string, string2);
    }

    private void mapPosNomeLocale(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("PosNome_locale_di", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.nomeLocale_tid2nome.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "01519";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.8");
        iom_jObject.setattrvalue("style", "ARIAL_ITALIC");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapNomeDiLocalita(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Nome");
        this.nomeDiLocalita_tid2nome.put(string, string2);
    }

    private void mapPosNomeDiLocalita(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("PosNome_di_localita_di", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.nomeDiLocalita_tid2nome.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "01529";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.8");
        iom_jObject.setattrvalue("style", "ARIAL_BOLD");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapNomeDelLuogo(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Nome");
        this.nomeDelLuogo_tid2nome.put(string, string2);
    }

    private void mapPosNomeDelLuogo(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("PosNome_del_luogo_di", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.nomeDelLuogo_tid2nome.get(string3);
        String string5 = "01539";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.8");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapNomeLocalizzazione(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Testo");
        this.nomeLocalizzazione_tid2testo.put(string, string2);
    }

    private void mapPosNomeLocalizzazione(IomObject iomObject) {
        IomObject iomObject2 = iomObject.getattrobj("PosNomeLocalizzazione_di", 0);
        String string = iomObject2.getobjectrefoid();
        String string2 = null;
        String string3 = null;
        if (this.nomeLocalizzazione_tid2testo.containsKey(string)) {
            string2 = this.nomeLocalizzazione_tid2testo.get(string);
            string3 = "01229";
        }
        if (string2 != null) {
            String string4;
            String string5;
            Object object;
            Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
            iom_jObject.setattrvalue("layername", string3);
            iom_jObject.setattrvalue("text", string2);
            iom_jObject.setattrvalue("text_size", "1.5");
            iom_jObject.setattrvalue("style", "ARIAL_ITALIC");
            IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
            if (this.perimeter != null) {
                try {
                    object = Iox2jts.coord2JTS(iomObject3);
                    if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                        return;
                    }
                }
                catch (Iox2jtsException iox2jtsException) {
                    throw new IllegalArgumentException(iox2jtsException);
                }
            }
            iom_jObject.addattrobj("geom", iomObject3);
            object = this.mapOri(iomObject.getattrvalue("Ori"));
            if (object != null) {
                iom_jObject.setattrvalue("ori", (String)object);
            }
            if ((string5 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
                iom_jObject.setattrvalue("hali", string5);
            }
            if ((string4 = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
                iom_jObject.setattrvalue("vali", string4);
            }
            this.out.add(iom_jObject);
        }
    }

    private void mapEntrataEdificio(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Numero_casa");
        if (string2 == null) {
            return;
        }
        String string3 = iomObject.getattrvalue("Validita");
        if ("reale".equals(string3)) {
            this.hausnummerReal.put(string, string2);
        } else if ("in_progetto".equals(string3)) {
            this.hausnummerProjektiert.put(string, string2);
        }
    }

    private void mapPosNumeroCasa(IomObject iomObject) {
        IomObject iomObject2 = iomObject.getattrobj("PosNumero_casa_di", 0);
        String string = iomObject2.getobjectrefoid();
        String string2 = null;
        String string3 = null;
        if (this.hausnummerReal.containsKey(string)) {
            string2 = this.hausnummerReal.get(string);
            string3 = "01219";
        } else if (this.hausnummerProjektiert.containsKey(string)) {
            string2 = this.hausnummerProjektiert.get(string);
            string3 = "01919";
        }
        if (string2 != null) {
            String string4;
            String string5;
            Object object;
            Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
            iom_jObject.setattrvalue("layername", string3);
            iom_jObject.setattrvalue("text", string2);
            iom_jObject.setattrvalue("text_size", "0.9");
            IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
            if (this.perimeter != null) {
                try {
                    object = Iox2jts.coord2JTS(iomObject3);
                    if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                        return;
                    }
                }
                catch (Iox2jtsException iox2jtsException) {
                    throw new IllegalArgumentException(iox2jtsException);
                }
            }
            iom_jObject.addattrobj("geom", iomObject3);
            object = this.mapOri(iomObject.getattrvalue("Ori"));
            if (object != null) {
                iom_jObject.setattrvalue("ori", (String)object);
            }
            if ((string5 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
                iom_jObject.setattrvalue("hali", string5);
            }
            if ((string4 = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
                iom_jObject.setattrvalue("vali", string4);
            }
            this.out.add(iom_jObject);
        }
    }

    private void mapLimiteDelBosco(IomObject iomObject) {
        Object object;
        String string = "TI_LIMITE_BOSCO_LEGALE";
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.polyline2JTSlineString(iomObject2, false, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polyline2d", null);
        ((IomObject)object).setattrvalue("layername", string);
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapSuperficieDisegno(IomObject iomObject) {
        Object object;
        String string = "TI_MARGINE_FOGLIO";
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.surface2JTS(iomObject2, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polygon2d", null);
        ((IomObject)object).setattrvalue("layername", string);
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapGradoDiTolleranza(IomObject iomObject) {
        Object object;
        String string = "TI_GRADO_TOLLERANZA";
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.surface2JTS(iomObject2, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polygon2d", null);
        ((IomObject)object).setattrvalue("layername", string);
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapMovimento(IomObject iomObject) {
        Object object;
        String string = "TI_ZONA_MOVIMENTO";
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.surface2JTS(iomObject2, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polygon2d", null);
        ((IomObject)object).setattrvalue("layername", string);
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapGeometriaPiano(IomObject iomObject) {
        Object object;
        String string = "RIPARTIZIONE_PIANI";
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.surface2JTS(iomObject2, 1.0E-4);
                if (!this.intersectsPerimeter((Geometry)object)) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        object = new Iom_jObject("Dxf.Topic.Polygon2d", null);
        ((IomObject)object).setattrvalue("layername", string);
        ((IomObject)object).addattrobj("geom", iomObject2);
        this.out.add((IomObject)object);
    }

    private void mapNumeroOS(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Numero");
        this.numeroOS_tid2numero.put(string, string2);
    }

    private void mapPosNumeroOS(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("PosNumero_OS_di", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.numeroOS_tid2numero.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "TI_NUMERO_OS";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "0.9");
        iom_jObject.setattrvalue("style", "ARIAL_ITALIC");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    /** Materializzazione del punto fisso ausiliario -> {nome blocco, nome
     * layer}. Il BLOCCO cambia col tipo di materializzazione (termine, bullone,
     * croce, non materializzato), il LAYER e' volutamente lo STESSO per tutti:
     * "TI_PF_AUSILIARIO". Correzione esplicita dell'utente: la
     * differenziazione per tipo vale per la simbologia QGIS, NON per la
     * struttura dei layer del DXF, che qui deve restare unificata. Non
     * "sistemare" tornando a quattro layer separati come per i PFP3. */
    private String[] materialeToPFAusiliarioBlockLayer(String string) {
        if (this.matchesMateriale(string, "termine_cippo", "termine_artificiale")) {
            return new String[]{"LFP3ST", "TI_PF_AUSILIARIO"};
        }
        if (this.matchesMateriale(string, "bullone", "tubo")) {
            return new String[]{"LFP3BO", "TI_PF_AUSILIARIO"};
        }
        if (this.matchesMateriale(string, "croce_scolpito", "croce", "scolpito")) {
            return new String[]{"LFP3KR", "TI_PF_AUSILIARIO"};
        }
        if (this.matchesMateriale(string, "non_materializzato", "palo_picchetto")) {
            return new String[]{"LFP3UV", "TI_PF_AUSILIARIO"};
        }
        return null;
    }

    private void mapPuntoFissoAusiliario(IomObject iomObject) {
        Object object;
        String string = iomObject.getattrvalue("Segno");
        String[] stringArray = this.materialeToPFAusiliarioBlockLayer(string);
        if (stringArray == null) {
            return;
        }
        String string2 = stringArray[0];
        String string3 = stringArray[1];
        String string4 = iomObject.getobjectoid();
        String string5 = iomObject.getattrvalue("Numero");
        IomObject iomObject2 = iomObject.getattrobj("Geometria", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject2);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        this.ptoFissoAus_tid2numero.put(string4, string5);
        object = iomObject.getattrvalue("GeomAlt");
        if (object != null) {
            iomObject2.setattrvalue("C3", (String)object);
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.BlockInsert", null);
        iom_jObject.setattrvalue("layername", string3);
        iom_jObject.setattrvalue("block", string2);
        iom_jObject.addattrobj("geom", iomObject2);
        this.out.add(iom_jObject);
    }

    private void mapPosPtoFissoAusiliario(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("PosPto_fisso_ausil_di", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.ptoFissoAus_tid2numero.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "TI_PF_AUSILIARIO_TXT";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.MText", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.35");
        iom_jObject.setattrvalue("style", "ARIAL");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapFondo(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Genere");
        String string3 = iomObject.getattrvalue("Numero");
        if ("bene_immobile".equals(string2)) {
            this.fondo_tid2numero.put(string, string3);
        } else {
            this.fondo_tid2numeroTraParentesi.put(string, "(" + string3 + ")");
        }
    }

    private void mapPosFondo(IomObject iomObject) {
        IomObject iomObject2 = iomObject.getattrobj("PosFondo_di", 0);
        String string = iomObject2.getobjectrefoid();
        String string2 = null;
        String string3 = null;
        if (this.fondo_tid2numero.containsKey(string)) {
            string2 = this.fondo_tid2numero.get(string);
            string3 = "01619";
        } else if (this.fondo_tid2numeroTraParentesi.containsKey(string)) {
            string2 = this.fondo_tid2numeroTraParentesi.get(string);
            string3 = "01639";
        }
        if (string2 != null) {
            String string4;
            String string5;
            Object object;
            Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
            iom_jObject.setattrvalue("layername", string3);
            iom_jObject.setattrvalue("text", string2);
            iom_jObject.setattrvalue("text_size", "1.35");
            iom_jObject.setattrvalue("style", "ARIAL_BOLD");
            IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
            if (this.perimeter != null) {
                try {
                    object = Iox2jts.coord2JTS(iomObject3);
                    if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                        return;
                    }
                }
                catch (Iox2jtsException iox2jtsException) {
                    throw new IllegalArgumentException(iox2jtsException);
                }
            }
            iom_jObject.addattrobj("geom", iomObject3);
            object = this.mapOri(iomObject.getattrvalue("Ori"));
            if (object != null) {
                iom_jObject.setattrvalue("ori", (String)object);
            }
            if ((string5 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
                iom_jObject.setattrvalue("hali", string5);
            }
            if ((string4 = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
                iom_jObject.setattrvalue("vali", string4);
            }
            this.out.add(iom_jObject);
        }
    }

    private void mapNomeEdificio(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Testo");
        this.nomeEdificio_tid2testo.put(string, string2);
    }

    private void mapPosNomeEdificio(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("PosNome_Edificio_di", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.nomeEdificio_tid2testo.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "TI_NOME_EDIFICIO";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "0.9");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapNomeLocalitaCAP(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Testo");
        this.nomeLocalitaCAP_tid2testo.put(string, string2);
    }

    private void mapPosNomeLocalitaCAP(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("PosNome_localita_di", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.nomeLocalitaCAP_tid2testo.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "TI_NOME_LOCALITA_CAP";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "1.8");
        iom_jObject.setattrvalue("style", "ARIAL_BOLD");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapNumeroNE(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Numero");
        this.numeroNE_tid2numero.put(string, string2);
    }

    private void mapPosNumeroNE(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("PosNumero_NE_di", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.numeroNE_tid2numero.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "TI_NUMERO_NE";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "0.9");
        iom_jObject.setattrvalue("style", "ARIAL_ITALIC");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapNumeroOggetto(IomObject iomObject) {
        String string = iomObject.getobjectoid();
        String string2 = iomObject.getattrvalue("Numero");
        this.numeroOggetto_tid2numero.put(string, string2);
    }

    private void mapPosNumeroOggetto(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("PosNumero_Oggetto_di", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.numeroOggetto_tid2numero.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "TI_NUMERO_OGGETTO";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "0.9");
        iom_jObject.setattrvalue("style", "ARIAL_ITALIC");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapPosPuntoDiConfine(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("PosPunto_di_confine_di", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.puntoDiConfine_tid2identificatore.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "TI_NUMERO_PUNTO_DI_CONFINE";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "0.9");
        iom_jObject.setattrvalue("style", "ARIAL");
        // Il numero del punto di confine deve avere lo STESSO colore del punto
        // a cui si riferisce, che dipende dalla Provenienza. La Provenienza
        // pero' sta sull'oggetto Punto_di_confine, non sulla sua posizione:
        // viene percio' memorizzata quando si mappa il punto
        // (puntoDiConfine_tid2provenienza) e ripresa qui tramite il
        // riferimento. Richiede che il TEXT sappia scrivere il colore
        // per-entita' - vedi la chiamata a writeOverrides in DxfWriter.text2Dxf.
        Integer n = this.provenienzaToAci(this.puntoDiConfine_tid2provenienza.get(string3));
        if (n != null) {
            iom_jObject.setattrvalue("color", n.toString());
        }
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    private void mapPosPuntoSingoloCS(IomObject iomObject) {
        this.mapPosPuntoSingolo(iomObject, "TI_NUMERO_PUNTO_SINGOLO_CS");
    }

    private void mapPosPuntoSingoloOS(IomObject iomObject) {
        this.mapPosPuntoSingolo(iomObject, "TI_NUMERO_PUNTO_SINGOLO_OS");
    }

    private void mapPosPuntoSingolo(IomObject iomObject, String string) {
        String string2;
        String string3;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("PosPunto_singolo_di", 0);
        String string4 = iomObject2.getobjectrefoid();
        String string5 = this.puntoSingolo_tid2identificatore.get(string4);
        if (string5 == null) {
            return;
        }
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string);
        iom_jObject.setattrvalue("text", string5);
        iom_jObject.setattrvalue("text_size", "0.9");
        iom_jObject.setattrvalue("style", "ARIAL");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string3 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string3);
        }
        if ((string2 = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string2);
        }
        this.out.add(iom_jObject);
    }

    private void mapPosPCGiurisdizionale(IomObject iomObject) {
        String string;
        String string2;
        Object object;
        IomObject iomObject2 = iomObject.getattrobj("PosPCGiurisdizionale_di", 0);
        String string3 = iomObject2.getobjectrefoid();
        String string4 = this.pcGiurisdizionale_tid2identificatore.get(string3);
        if (string4 == null) {
            return;
        }
        String string5 = "TI_NUMERO_PCGIURISDIZIONALE";
        Iom_jObject iom_jObject = new Iom_jObject("Dxf.Topic.Text", null);
        iom_jObject.setattrvalue("layername", string5);
        iom_jObject.setattrvalue("text", string4);
        iom_jObject.setattrvalue("text_size", "0.9");
        iom_jObject.setattrvalue("style", "ARIAL");
        IomObject iomObject3 = iomObject.getattrobj("Pos", 0);
        if (this.perimeter != null) {
            try {
                object = Iox2jts.coord2JTS(iomObject3);
                if (!this.intersectsPerimeter((Geometry)this.jtsFactory.createPoint((Coordinate)object))) {
                    return;
                }
            }
            catch (Iox2jtsException iox2jtsException) {
                throw new IllegalArgumentException(iox2jtsException);
            }
        }
        iom_jObject.addattrobj("geom", iomObject3);
        object = this.mapOri(iomObject.getattrvalue("Ori"));
        if (object != null) {
            iom_jObject.setattrvalue("ori", (String)object);
        }
        if ((string2 = this.mapHali(iomObject.getattrvalue("HAli"))) != null) {
            iom_jObject.setattrvalue("hali", string2);
        }
        if ((string = this.mapVali(iomObject.getattrvalue("VAli"))) != null) {
            iom_jObject.setattrvalue("vali", string);
        }
        this.out.add(iom_jObject);
    }

    static {
        PROVENIENZA_ACI.put("digitalizzazione", 1);
        PROVENIENZA_ACI.put("terrestre", 3);
        PROVENIENZA_ACI.put("fotogrammetria", 6);
        PROVENIENZA_ACI.put("costruzione", 30);
        PROVENIENZA_ACI.put("gps", 2);
        PROVENIENZA_ACI.put("altri", 7);
        // Layer per i quali l'utente ha chiesto esplicitamente larghezza
        // globale 0 (linea sempre sottile), indipendentemente dal genere o
        // dalla tabella di provenienza - vedi zeroWidthIfNeeded.
        // 01315 (ciminiera, palo/antenna, pilastro) e 01351 (fontana, sorgente)
        // aggiunti per ultimi: stavano a 0.20 mentre tutti gli altri oggetti
        // singoli sono a spessore normale, e spiccavano senza motivo.
        ZERO_WIDTH_LAYERS = new HashSet<String>(Arrays.asList("01311", "01312", "01313", "01321", "01322", "01334", "01316", "01370", "01341", "01342", "01331", "01315", "01351"));
    }
}

