#!/usr/bin/env bash
# Ricompila av2geobau_ti.jar dal sorgente in src/ e lo installa.
# Eseguire da Git Bash, da qualunque cartella:  ./build.sh
#
# Non usa percorsi assoluti ne' file fuori dal repository: tutto quello che
# serve - le 15 librerie del classpath e il jar di base - e' gia' in
# tidashboard/av2geobau/, quindi una copia appena clonata compila senza
# dover ricostruire a mano un albero di cartelle attorno.
set -euo pipefail

QUI="$(cd "$(dirname "$0")" && pwd)"
RADICE="$(cd "$QUI/.." && pwd)"
DOTAZIONE="$RADICE/tidashboard/av2geobau"

# javac/jar: prima JAVA_HOME, poi il PATH. Serve un JDK, non un semplice JRE.
if [ -n "${JAVA_HOME:-}" ] && [ -x "$JAVA_HOME/bin/javac" ]; then
  JAVAC="$JAVA_HOME/bin/javac"; JAR="$JAVA_HOME/bin/jar"
elif command -v javac >/dev/null 2>&1; then
  JAVAC="$(command -v javac)"; JAR="$(command -v jar)"
else
  echo "ERRORE: javac non trovato. Serve un JDK (non basta il JRE)." >&2
  echo "        Imposta JAVA_HOME oppure metti javac nel PATH." >&2
  exit 1
fi
echo ">> javac: $JAVAC"

# Il jar in dotazione fa anche da BASE: contiene le classi del modello
# (ch/interlis/models/**) che non sono in src/ e non vanno ricompilate. Viene
# letto e scompattato PRIMA che il nuovo jar venga scritto, quindi il fatto
# che sia anche una destinazione di installazione non lo corrompe.
BASE_JAR="$DOTAZIONE/av2geobau_ti.jar"
[ -f "$BASE_JAR" ] || { echo "ERRORE: jar di base assente: $BASE_JAR" >&2; exit 1; }

# Il classpath va costruito con percorsi in forma WINDOWS separati da ';'.
# Git Bash converte da solo i singoli argomenti che sembrano percorsi, ma non
# l'interno di una stringa gia' unita da ';': passandogli "/c/Users/..." javac
# non trova nulla e la compilazione muore con oltre mille "cannot find
# symbol". Su sistemi senza cygpath si usa la forma POSIX con ':'.
if command -v cygpath >/dev/null 2>&1; then
  CP="$(for j in "$DOTAZIONE"/libs/*.jar; do printf '%s;' "$(cygpath -m "$j")"; done)"
else
  CP="$(for j in "$DOTAZIONE"/libs/*.jar; do printf '%s:' "$j"; done)"
fi

echo ">> compilo..."
rm -rf "$QUI/build" && mkdir -p "$QUI/build"
"$JAVAC" --release 8 -nowarn -d "$QUI/build" -cp "$CP" $(find "$QUI/src" -name "*.java")

echo ">> impacchetto (overlay sul jar base)..."
rm -rf "$QUI/jarbuild" && mkdir -p "$QUI/jarbuild"
(cd "$QUI/jarbuild" && "$JAR" xf "$BASE_JAR")
cp -r "$QUI/build/"* "$QUI/jarbuild/"
(cd "$QUI/jarbuild" && "$JAR" cfm "$QUI/av2geobau_ti.jar" META-INF/MANIFEST.MF .)

echo ">> installo..."
# La prima destinazione e' il jar in dotazione dentro il repository: e' quello
# che finisce nello zip del plugin. La seconda e' il plugin installato in
# QGIS, se c'e': permette di provare subito senza reinstallare lo zip.
PROFILO="${QGIS_PROFILE_DIR:-$APPDATA/QGIS/QGIS4/profiles/default}"
for d in \
  "$DOTAZIONE/av2geobau_ti.jar" \
  "$PROFILO/python/plugins/tidashboard/av2geobau/av2geobau_ti.jar"
do
  if [ -d "$(dirname "$d")" ] && cp "$QUI/av2geobau_ti.jar" "$d" 2>/dev/null; then
    echo "   OK      $d"
  else
    echo "   SALTATO $d"
  fi
done

echo ">> fatto."
