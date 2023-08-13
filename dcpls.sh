#!/bin/sh

# Funktion, um Filmtitel für eine gegebene UUID zu erhalten
get_movie_title() {
    uuid="$1"

    # Den Wert von AnnotationText aus der ASSETMAP-Datei auslesen (mit Berücksichtigung von .xml-Endung)
    titel=$(grep -o -m 1 -E "<AnnotationText>[^<]*</AnnotationText>" "$uuid"/ASSETMAP* | sed 's/<AnnotationText>//;s/<\/AnnotationText>//')

    echo "$titel"
}

# Funktion, um die Ordnergröße in menschenlesbarer Form zu erhalten
get_readable_size() {
    size="$1"
    units="BKMGTP"
    index=0

    while [ "$size" -ge 1024 ] && [ "$index" -lt 6 ]; do
        size=$(($size / 1024))
        index=$(($index + 1))
    done

    echo "$size${units:$index:1}"
}

# Funktion, um Inhalte eines Ordners aufzulisten und tabellarisch anzuzeigen
list_movies() {
    printf "%-40s %-10s %-50s\n" "UUID" "Größe" "Filmtitel"
    printf "=%.0s" {1..100}
    echo

    for dir in */; do
        # Überprüfen, ob der Ordnername dem UUID-Format entspricht
        if echo "$dir" | grep -qiE "^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}/$"; then
            uuid="$dir"
            title=$(get_movie_title "$uuid")
            size=$(du -sB1 "$uuid" | cut -f1)
            readable_size=$(get_readable_size "$size")

            printf "%-40s %-10s %-50s\n" "$uuid" "$readable_size" "$title"
        fi
    done
}

# Ordnerinhalt auflisten und tabellarisch anzeigen
list_movies
