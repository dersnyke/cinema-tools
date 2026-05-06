# Christie IMB Cinemalib Reconstruction Tools

Dieses Repository enthält Python-2.7-kompatible Werkzeuge zur Analyse und Rekonstruktion von DCP-Inhalten aus der `cinemalib` eines Christie IMB (Integrated Media Block).

Die Christie-`cinemalib` speichert DCP-Inhalte nicht als klassische DCP-Ordnerstruktur, sondern dedupliziert und verteilt Assets intern anhand von UUIDs. Diese Scripts helfen dabei, aus dieser Speicherstruktur wieder rekonstruierbare DCP-Verzeichnisse zu erzeugen.

Die Scripts wurden auf einem Linux-/QNAP-System entwickelt und verwenden ausschließlich lesende Zugriffe auf die ursprüngliche `cinemalib`. Die Rekonstruktion erfolgt mittels Hardlinks, sodass keine zusätzlichen Kopien großer MXF-Dateien erzeugt werden.

---

# Enthaltene Scripts

## `dcp_inventory.py`

Erstellt ein grundlegendes Inventory der gesamten `cinemalib`.

## `dcp_cpl_asset_report.py`

Analysiert CPL-Dateien und ordnet referenzierte Assets den tatsächlich vorhandenen Dateien in der `cinemalib` zu.

## `dcp_reconstruct_from_report.py`

Rekonstruiert vollständige DCP-Ordner aus dem zuvor erzeugten Asset-Report.

---

# Typische Christie-IMB-Struktur

```text
cinemalib/
├── compositions/
│   └── cpl_<uuid>
├── trackfiles/
│   └── <uuid>
├── assethashs/
│   └── <uuid>
```

---

# Voraussetzungen

- Python 2.7.x
- Linux/QNAP
- Hardlink-Unterstützung im Dateisystem

---

# Sicherheitshinweise

Die Analyse-Scripts führen ausschließlich lesende Zugriffe auf die ursprüngliche `cinemalib` aus.

Das Rekonstruktionsscript schreibt ausschließlich in den angegebenen Zielordner.

Es werden keine Dateien in der ursprünglichen `cinemalib` verändert oder gelöscht.

---

# Hinweis

Die erzeugten PKLs werden synthetisch rekonstruiert, basierend auf:

- CPL-Referenzen
- vorhandenen Asset-Dateien
- Asset-Größen
- SHA1-Hashes aus `assethashs`

Je nach Zielsystem empfiehlt sich eine abschließende Validierung mit einem DCP-Validator oder einem Test-Ingest auf einem echten Kino-System.
