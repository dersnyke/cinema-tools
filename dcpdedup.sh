#!/bin/sh

# Überprüfen, ob beide Pfade als Argumente übergeben wurden
if [ $# -ne 2 ]; then
    echo "./$(basename "$0") [Pfad_zur_OV] [Pfad_zur_VF]"
    exit 1
fi

ov_ordner="$1"
vf_ordner="$2"

# Durchsuchen des VF-Ordners nach doppelt vorhandenen Dateien
find_duplicate_files() {
    for datei2 in "$vf_ordner"/*; do
        if [ -f "$datei2" ]; then
            dateiname=$(basename "$datei2")
            datei1="$ov_ordner/$dateiname"

            if [[ "$dateiname" == VOLINDEX* || "$dateiname" == ASSETMAP* ]]; then
                echo "Überspringe VOLINDEX/ASSETMAP."
                continue
            fi

            if [ -f "$datei1" ]; then
                echo "Gefundenes Duplikat: $dateiname"
                echo " - Vergleiche Exemplare..."
                if cmp -s "$datei1" "$datei2"; then
                    echo " -> Identisch. Duplikat entfernen."
                    rm "$datei2"
                else
                    echo " -> Die Datei '$dateiname' unterscheidet sich inhaltlich von der Datei im Ordner '$ov_ordner'."
                fi
            fi
        fi
    done
}

# Nach doppelt vorhandenen Dateien suchen und zur Löschung anbieten
find_duplicate_files
