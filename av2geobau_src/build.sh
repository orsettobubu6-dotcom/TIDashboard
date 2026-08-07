#!/usr/bin/env bash
# Ricompila av2geobau_ti.jar dal sorgente in src/ e lo installa nelle 4
# posizioni usate dal progetto. Eseguire da Git Bash:  ./build.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
COGO="C:/Users/gabri/Documents/Claude/Projects/COGO"
JAVAC="/c/Program Files/Java/jdk-20/bin/javac.exe"
JAR="/c/Program Files/Java/jdk-20/bin/jar.exe"

# Il jar installato fa anche da BASE: contiene le classi del modello
# (ch/interlis/models/**) che non sono in src/ e non vanno ricompilate.
BASE_JAR="$COGO/av2geobau_ti.jar"

CP="$(ls "$COGO"/libs/*.jar | tr '\n' ';')"

echo ">> compilo..."
rm -rf "$HERE/build" && mkdir -p "$HERE/build"
"$JAVAC" --release 8 -d "$HERE/build" -cp "$CP" $(find "$HERE/src" -name "*.java")

echo ">> impacchetto (overlay sul jar base)..."
rm -rf "$HERE/jarbuild" && mkdir -p "$HERE/jarbuild"
(cd "$HERE/jarbuild" && "$JAR" xf "$BASE_JAR")
cp -r "$HERE/build/"* "$HERE/jarbuild/"
(cd "$HERE/jarbuild" && "$JAR" cfm "$HERE/av2geobau_ti.jar" META-INF/MANIFEST.MF .)

echo ">> installo nelle 4 posizioni..."
for d in \
  "$COGO/av2geobau_ti.jar" \
  "$COGO/tidashboard/av2geobau/av2geobau_ti.jar" \
  "$COGO/cadastra_dashboard_pro/resources/av2geobau/av2geobau_ti.jar" \
  "C:/Users/gabri/AppData/Roaming/QGIS/QGIS4/profiles/default/python/plugins/tidashboard/av2geobau/av2geobau_ti.jar"
do
  if cp "$HERE/av2geobau_ti.jar" "$d" 2>/dev/null; then echo "   OK   $d"; else echo "   SALTATO (percorso assente) $d"; fi
done

echo ">> fatto."
