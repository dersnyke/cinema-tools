# cinema-tools

Die cinema-tools vereinfachen den Umgang mit DCP-Packages. Bei Doremi-IMS exportierten DCP-PKGs erhalten die Verzeichnisse UUID-Namen. Dadurch sind die Verzeichnisse so gut wie nicht zu überblicken. Ferner werden VFs von DCPs inklusive aller notwendigen Teile der OV exportiert. Sollen beide Versionen exportiert werden, wird unnötig viel Speicherplatz verwendet.
Die Scripte sind vorgeneriert mit ChatGPT und ggf. durch mich hie und da angepasst. Ich nutze sie direkt auf der Shell des Kino-NAS, nicht jedoch auf dem Doremi/Dolby IMS. Benutzung erfolgt natürlich auf eigene Gefahr.

--------
dcpls.sh
--------

Shellscript um eine tabellarische Übersicht über die UUID-Unterverzeichnisse zu erhalten, inkl. Größenangabe der Ordner.


--------
dcpmv.sh
--------

Exportierte DCP-PKGs werden als UUID-Ordner gespeichert. In reinen Dateisystem-Archiven sind die Ordner so nicht menschenlesbar.
Dieses Script benennt die Ordner entsprechend der ASSETMAP um.


-----------
dcpdedup.sh
-----------

Exportiert man im Doremi/Dolby IMS eine VF, so enthält diese alle zur Wiedergabe notwendigen Teile der OV ebenfalls. Werden mehrere VFs neben der OV archiviert, geht so übermäßig viel Speicherplatz verloren. Das Script bietet diese doppelten Inhalte zur Löschung an.
