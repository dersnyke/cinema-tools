#!/bin/sh

# Funktion, um nach Ordnern mit UUID-ähnlichen Namen zu suchen und zur Umbenennung vorzuschlagen
search_and_rename() {
    for dir in */; do
        # Überprüfen, ob der Ordnername dem UUID-Format entspricht
        if echo "$dir" | grep -qiE "^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}/$"; then
            film_verzeichnis="$dir"

            # Den Wert von AnnotationText aus der ASSETMAP-Datei auslesen (mit Berücksichtigung von .xml-Endung)
            titel=$(grep -o -m 1 -E '<AnnotationText>[^<]*</AnnotationText>' "$film_verzeichnis"/ASSETMAP* | sed 's/<AnnotationText>//;s/<\/AnnotationText>//')

            # Bestätigungsabfrage
            echo "Das Verzeichnis '$film_verzeichnis' umbenennen in '$titel'? (j/n)"
            read bestaetigung
            if [ "$bestaetigung" = "j" ]; then
                # Verzeichnis umbenennen
                mv "$film_verzeichnis" "$(dirname "$film_verzeichnis")/$titel"
                echo "Das Verzeichnis wurde erfolgreich in '$titel' umbenannt."
            fi
        fi
    done
}

# Wenn Skript ohne Parameter aufgerufen wird
if [ $# -eq 0 ]; then
    search_and_rename
    exit 0
fi

# Überprüfen, ob ein Verzeichnis als Parameter übergeben wurde
film_verzeichnis="$1"

# Überprüfen, ob das Verzeichnis existiert und eine ASSETMAP-Datei enthält (mit Berücksichtigung von .xml-Endung)
if [ ! -d "$film_verzeichnis" ] || [ ! -f "$film_verzeichnis"/ASSETMAP* ]; then
    echo "Ungültiges Verzeichnis oder keine ASSETMAP-Datei gefunden."
    exit 1
fi

# Den Wert von AnnotationText aus der ASSETMAP-Datei auslesen (mit Berücksichtigung von .xml-Endung)
titel=$(grep -o -m 1 -E '<AnnotationText>[^<]*</AnnotationText>' "$film_verzeichnis"/ASSETMAP* | sed 's/<AnnotationText>//;s/<\/AnnotationText>//')

# Bestätigungsabfrage, wenn Skript mit Parameter aufgerufen wird
echo "Das Verzeichnis '$film_verzeichnis' umbenennen in '$titel'? (j/n)"
read bestaetigung
if [ "$bestaetigung" = "j" ]; then
    # Verzeichnis umbenennen
    mv "$film_verzeichnis" "$(dirname "$film_verzeichnis")/$titel"
    echo "Das Verzeichnis wurde erfolgreich in '$titel' umbenannt."
fi
