# cinema-tools

Die cinema-tools vereinfachen den Umgang mit DCP-Packages. Bei Doremi-IMS exportierten DCP-PKGs erhalten die Verzeichnisse UUID-Namen. Dadurch sind die Verzeichnisse so gut wie nicht zu überblicken. Ferner werden VFs von DCPs inklusive aller notwendigen Teile der OV exportiert. Sollen beide Versionen exportiert werden, wird unnötig viel Speicherplatz verwendet.
Die Scripte sind vorgeneriert mit ChatGPT und ggf. durch mich hie und da angepasst. Ich nutze sie direkt auf der Shell des Kino-NAS, nicht jedoch auf dem Doremi/Dolby IMS. Benutzung erfolgt natürlich auf eigene Gefahr.

Um aus einer DCP-Library den ursprünglichen Zustand wiederherzustellen nutzt man also z.B. folgende Vorgehensweise:

- Lokalisieren des Speicherorts auf dem Dateisystem
- Ausführen von dcpls.sh um Größe und Inhalt der Ordner festzustellen und wegkopieren in ein Arbeitsverzeichnis (oder direkt im export-Verzeichnis "incoming")
- Ausführen von dcpmv.sh um die UUID-Verzeichnisse in menschenlesbare Ordner umzubenennen
- Ausführen von dcpdedup.sh um VF-Ordner zu verschlanken, wenn Assets bereits im OV enthalten sind. (Es werden immer alle für ein Paket nötigen Assets exportiert, nicht nur die zusätzlichen wie ursprünglich importiert. Wenn nur das VF benötigt wird, muss das OV theoretisch nicht zusätzlich exportiert werden - die Benennung passt dann jedoch nicht, da VFs alleine gewöhnlich nicht lauffähig sind!)

 
--------
dcpls.sh
--------

Shellscript um eine tabellarische Übersicht über die UUID-Unterverzeichnisse zu erhalten, inkl. Größenangabe der Ordner und der darin lt. ASSETMAP enthaltenen Daten.

```
[/share/doremi/incoming] # ls
bfd590f1-aeba-4e04-a3e9-2fcdfc88fc26/  d9a6070d-6153-4af4-8baa-51c6f570a931/
[/share/doremi/incoming] # /root/dcpls.sh
UUID                                     Größe      Filmtitel
====================================================================================================
bfd590f1-aeba-4e04-a3e9-2fcdfc88fc26/    111G       ImHerzenJung_FTR-1_S_FR-XX_DE_51_2K_AMO_20230517_CPP_IOP_OV
d9a6070d-6153-4af4-8baa-51c6f570a931/    111G       ImHerzenJung_FTR-1_S_DE-DE_DE_51_2K_AMO_20230706_CPP_IOP_VF
[/share/doremi/incoming] # cd ..
```

--------
dcpmv.sh
--------

Exportierte DCP-PKGs werden als UUID-Ordner gespeichert. In reinen Dateisystem-Archiven sind die Ordner so nicht menschenlesbar.
Dieses Script benennt die Ordner entsprechend der ASSETMAP um.

```
[/share/doremi/incoming] # /root/dcpmv.sh
Das Verzeichnis 'bfd590f1-aeba-4e04-a3e9-2fcdfc88fc26/' umbenennen in 'ImHerzenJung_FTR-1_S_FR-XX_DE_51_2K_AMO_20230517_CPP_IOP_OV'? (j/n) j
Das Verzeichnis wurde erfolgreich in 'ImHerzenJung_FTR-1_S_FR-XX_DE_51_2K_AMO_20230517_CPP_IOP_OV' umbenannt.
Das Verzeichnis 'd9a6070d-6153-4af4-8baa-51c6f570a931/' umbenennen in 'ImHerzenJung_FTR-1_S_DE-DE_DE_51_2K_AMO_20230706_CPP_IOP_VF'? (j/n) j
Das Verzeichnis wurde erfolgreich in 'ImHerzenJung_FTR-1_S_DE-DE_DE_51_2K_AMO_20230706_CPP_IOP_VF' umbenannt.
[/share/doremi/incoming] #
```

-----------
dcpdedup.sh
-----------

Exportiert man im Doremi/Dolby IMS eine VF, so enthält diese alle zur Wiedergabe notwendigen Teile der OV ebenfalls. Werden mehrere VFs neben der OV archiviert, geht so übermäßig viel Speicherplatz verloren. Das Script bietet diese doppelten Inhalte zur Löschung an.

```
[/share/doremi/incoming] # /root/dcpdedup.sh
./dcpdedup.sh [Pfad_zur_OV] [Pfad_zur_VF]
[/share/doremi/incoming] # /root/dcpdedup.sh ImHerzenJung_FTR-1_S_FR-XX_DE_51_2K_AMO_20230517_CPP_IOP_OV/ ImHerzenJung_FTR-1_S_DE-DE_DE_51_2K_AMO_20230706_CPP_IOP_VF/
Gefundenes Duplikat: 2c1fb9a8-9ce8-430c-aedf-0504ea41b87c.mxf
 - Berechne Prüfsumme für 2c1fb9a8-9ce8-430c-aedf-0504ea41b87c.mxf ...
 - Die Datei '2c1fb9a8-9ce8-430c-aedf-0504ea41b87c.mxf' ist identisch mit jener im Ordner 'ImHerzenJung_FTR-1_S_FR-XX_DE_51_2K_AMO_20230517_CPP_IOP_OV/'.
Löschen? (j/n): j
 - Die Datei '2c1fb9a8-9ce8-430c-aedf-0504ea41b87c.mxf' wurde gelöscht.

[...]

Überspringe VOLINDEX/ASSETMAP.
Gefundenes Duplikat: f8e6c5a4-9551-45d8-901b-a0713823970f.mxf
 - Berechne Prüfsumme für f8e6c5a4-9551-45d8-901b-a0713823970f.mxf ...
 - Die Datei 'f8e6c5a4-9551-45d8-901b-a0713823970f.mxf' ist identisch mit jener im Ordner 'ImHerzenJung_FTR-1_S_FR-XX_DE_51_2K_AMO_20230517_CPP_IOP_OV/'.
Löschen? (j/n): j
 - Die Datei 'f8e6c5a4-9551-45d8-901b-a0713823970f.mxf' wurde gelöscht.
Gefundenes Duplikat: PKL.xml
 - Berechne Prüfsumme für PKL.xml ...
 - Die Datei 'PKL.xml' unterscheidet sich inhaltlich von der Datei im Ordner 'ImHerzenJung_FTR-1_S_FR-XX_DE_51_2K_AMO_20230517_CPP_IOP_OV/'.
Überspringe VOLINDEX/ASSETMAP.
[/share/doremi/incoming] #
```
