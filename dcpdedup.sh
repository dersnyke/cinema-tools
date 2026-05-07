#!/bin/sh

# Prüfen, ob beide Pfade übergeben wurden
if [ $# -ne 2 ]; then
    echo "./$(basename "$0") [Pfad_zur_OV] [Pfad_zur_VF]"
    exit 1
fi

ov_ordner="$1"
vf_ordner="$2"

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

    groesse1=$(wc -c < "$datei1" | tr -d ' ')
    groesse2=$(wc -c < "$datei2" | tr -d ' ')

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
