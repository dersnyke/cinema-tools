#!/bin/sh

# Prüfen, ob beide Pfade übergeben wurden
if [ $# -ne 2 ]; then
    echo "./$(basename "$0") [Pfad_zur_OV] [Pfad_zur_VF]"
    exit 1
fi

ov_ordner="$1"
vf_ordner="$2"

# Dateigröße effizient aus den Dateisystem-Metadaten lesen.
# Linux/GNU stat:    stat -c %s
# BSD/FreeBSD stat: stat -f %z
get_size() {
    stat -c %s "$1" 2>/dev/null || stat -f %z "$1" 2>/dev/null
}

for datei2 in "$vf_ordner"/*; do
    [ -f "$datei2" ] || continue

    dateiname=$(basename "$datei2")
    datei1="$ov_ordner/$dateiname"

    case "$dateiname" in
        VOLINDEX*|ASSETMAP*)
            echo "Überspringe VOLINDEX/ASSETMAP: $dateiname"
            continue
            ;;
    esac

    [ -f "$datei1" ] || continue

    echo "Gefundenes Duplikat: $dateiname"

    groesse1=$(get_size "$datei1")
    groesse2=$(get_size "$datei2")

    if [ -z "$groesse1" ] || [ -z "$groesse2" ]; then
        echo " -> Konnte Dateigröße nicht ermitteln. Überspringe Datei."
        continue
    fi

    if [ "$groesse1" = "$groesse2" ]; then
        echo " -> Gleicher Dateiname und gleiche Größe ($groesse1 Bytes)."
        echo " -> Datei wird als identisch angenommen."
        echo " -> Duplikat entfernen."
        rm "$datei2"
    else
        echo " -> Unterschiedliche Dateigröße:"
        echo "    OV: $groesse1 Bytes"
        echo "    VF: $groesse2 Bytes"
        echo " -> Führe Inhaltsvergleich durch..."

        if cmp -s "$datei1" "$datei2"; then
            echo " -> Inhalt identisch. Duplikat entfernen."
            rm "$datei2"
        else
            echo " -> Datei '$dateiname' unterscheidet sich inhaltlich von der Datei im OV-Ordner."
        fi
    fi
done
