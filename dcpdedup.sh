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

            # Überspringe Dateien "VOLINDEX" und "ASSETMAP"
            if [[ "$dateiname" == VOLINDEX* || "$dateiname" == ASSETMAP* ]]; then
                echo "Überspringe VOLINDEX/ASSETMAP."
                continue
            fi

            if [ -f "$datei1" ]; then
                echo "Gefundenes Duplikat: $dateiname"
                echo " - Berechne Prüfsumme für $dateiname ..."
                checksum1=$(md5sum "$datei1" | cut -d ' ' -f 1)
                checksum2=$(md5sum "$datei2" | cut -d ' ' -f 1)

                if [ "$checksum1" = "$checksum2" ]; then
                    echo " - Die Datei '$dateiname' ist identisch mit jener im Ordner '$ov_ordner'."
                    echo -n "Löschen? (j/n): "
                    read -r bestaetigung
                    if [ "$bestaetigung" = "j" ]; then
                        rm "$datei2"
                        echo " - Die Datei '$dateiname' wurde gelöscht."
                    fi
                else
                    echo " - Die Datei '$dateiname' unterscheidet sich inhaltlich von der Datei im Ordner '$ov_ordner'."
                fi
            fi
        fi
    done
}

# Nach doppelt vorhandenen Dateien suchen und zur Löschung anbieten
find_duplicate_files
