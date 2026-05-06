#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
# dcp_inventory.py
#
# Python 2.7.5 kompatibles Inventory-Script fuer zerlegte DCP-/Cinema-Library-Ordner.
#
# Eigenschaften:
#   - liest rekursiv alle Dateien unterhalb des angegebenen Ordners
#   - erkennt grob XML-/DCP-Dateitypen anhand des Inhalts
#   - parst PKL-Dateien und listet deren Assets
#   - schreibt nur zwei Dateien in den Basisordner:
#       dcp_inventory.json
#       dcp_inventory.txt
#   - ueberschreibt diese Dateien NICHT, sondern bricht ab, wenn sie schon existieren
#
# Aufruf:
#   python2 dcp_inventory.py /pfad/zum/cinemalib-ordner
#

import os
import sys
import json
import time
import xml.etree.ElementTree as ET


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    sys.stdout.write("[%s] %s\n" % (ts, msg))
    sys.stdout.flush()


def strip_namespace(tag):
    if tag is None:
        return None
    return tag.split("}")[-1]


def sniff_file(path):
    """
    Erkennt Dateitypen grob anhand der ersten Bytes.
    Viele DCP-Dateien haben keine Dateiendung, daher bringt filename-basiertes Raten wenig.
    """
    try:
        f = open(path, "rb")
        head = f.read(16384)
        f.close()
    except Exception as e:
        log("  WARNUNG: Datei nicht lesbar: %s - %s" % (path, str(e)))
        return "unreadable"

    # MXF beginnt typischerweise mit SMPTE UL
    if head.startswith("\x06\x0e\x2b\x34"):
        return "mxf"

    # Fuer XML-Erkennung robust gegen BOM, Leerzeichen, fehlende XML-Deklaration.
    head_l = head.lower()

    if "<?xml" in head_l:
        return "xml"

    if "<packinglist" in head_l:
        return "xml"

    if "<compositionplaylist" in head_l:
        return "xml"

    if "<assetmap" in head_l:
        return "xml"

    if "<volumeindex" in head_l:
        return "xml"

    if "<dcsubtitle" in head_l:
        return "xml"

    if "<subtitle" in head_l:
        return "xml"

    if "<subtitlereel" in head_l:
        return "xml"

    if "<dcinemasecuritymessage" in head_l:
        return "xml"

    if "<signeddcinemasecuritymessage" in head_l:
        return "xml"

    # Einige kleine Management-/Hash-Dateien koennen Text sein.
    # Wird hier absichtlich nur grob markiert.
    if len(head) > 0:
        printable = 0
        for c in head:
            o = ord(c)
            if o in (9, 10, 13) or (32 <= o <= 126):
                printable += 1
        if printable > len(head) * 0.90:
            return "text?"

    return "unknown"


def xml_root_info(path):
    """
    Parst XML und gibt Root-Tag + Namespace zurueck.
    """
    try:
        tree = ET.parse(path)
        root = tree.getroot()

        tag = strip_namespace(root.tag)

        if "}" in root.tag:
            ns = root.tag.split("}")[0].replace("{", "")
        else:
            ns = ""

        return tag, ns

    except Exception as e:
        log("  WARNUNG: XML konnte nicht geparst werden: %s - %s" % (path, str(e)))
        return None, None


def find_text(elem, name):
    """
    Sucht erstes XML-Element mit lokalem Tag-Namen ohne Namespace.
    """
    for x in elem.iter():
        tag = strip_namespace(x.tag)
        if tag == name:
            return x.text
    return None


def normalize_uuid(value):
    """
    Macht aus 'urn:uuid:xxxx' einfach 'xxxx'.
    """
    if value is None:
        return None

    value = value.strip()

    if value.lower().startswith("urn:uuid:"):
        return value[9:]

    return value


def parse_pkl(path):
    """
    Extrahiert die PKL-Kopfdaten und Assetliste.
    """
    result = {
        "kind": "PKL",
        "id": None,
        "id_uuid": None,
        "annotation": None,
        "issuer": None,
        "assets": []
    }

    try:
        tree = ET.parse(path)
        root = tree.getroot()

        result["id"] = find_text(root, "Id")
        result["id_uuid"] = normalize_uuid(result["id"])
        result["annotation"] = find_text(root, "AnnotationText")
        result["issuer"] = find_text(root, "Issuer")

        for asset in root.iter():
            tag = strip_namespace(asset.tag)

            if tag != "Asset":
                continue

            entry = {}

            for child in asset:
                key = strip_namespace(child.tag)
                entry[key] = child.text

            if entry.get("Id"):
                entry["IdUuid"] = normalize_uuid(entry.get("Id"))
                result["assets"].append(entry)

        log("  PKL geparst: %s Assets: %d" % (path, len(result["assets"])))

    except Exception as e:
        result["error"] = str(e)
        log("  WARNUNG: PKL konnte nicht geparst werden: %s - %s" % (path, str(e)))

    return result


def parse_cpl(path):
    """
    Extrahiert einfache CPL-Kopfdaten.
    Fuer die spaetere Rekonstruktion interessant, aber hier noch bewusst kompakt.
    """
    result = {
        "kind": "CPL",
        "id": None,
        "id_uuid": None,
        "annotation": None,
        "content_title_text": None,
        "issuer": None
    }

    try:
        tree = ET.parse(path)
        root = tree.getroot()

        result["id"] = find_text(root, "Id")
        result["id_uuid"] = normalize_uuid(result["id"])
        result["annotation"] = find_text(root, "AnnotationText")
        result["content_title_text"] = find_text(root, "ContentTitleText")
        result["issuer"] = find_text(root, "Issuer")

    except Exception as e:
        result["error"] = str(e)
        log("  WARNUNG: CPL konnte nicht geparst werden: %s - %s" % (path, str(e)))

    return result


def main():

    if len(sys.argv) != 2:
        print "Usage: %s <ordner>" % sys.argv[0]
        sys.exit(1)

    base = sys.argv[1]

    if not os.path.isdir(base):
        print "Pfad ist kein Ordner."
        sys.exit(1)

    base_abs = os.path.abspath(base)

    log("Starte DCP-Inventory")
    log("Basisordner: %s" % base_abs)

    out_json = os.path.join(base, "dcp_inventory.json")
    out_txt = os.path.join(base, "dcp_inventory.txt")

    if os.path.exists(out_json):
        log("Abbruch: Datei existiert bereits: %s" % out_json)
        sys.exit(1)

    if os.path.exists(out_txt):
        log("Abbruch: Datei existiert bereits: %s" % out_txt)
        sys.exit(1)

    inventory = {
        "base": base_abs,
        "files": [],
        "pkl": [],
        "cpl": [],
        "summary": {}
    }

    all_files = []

    log("Suche Dateien rekursiv...")

    for root, dirs, files in os.walk(base):
        log("  Durchsuche Ordner: %s Dateien: %d Unterordner: %d" % (
            root,
            len(files),
            len(dirs)
        ))

        for name in files:
            full = os.path.join(root, name)

            if os.path.isfile(full):
                all_files.append(full)

    all_files.sort()

    log("Gefundene Dateien: %d" % len(all_files))

    if len(all_files) == 0:
        log("Keine Dateien gefunden. Da kann ich auch nix inventarisieren, mei.")
        sys.exit(1)

    file_no = 0

    for path in all_files:
        file_no += 1

        filename = os.path.relpath(path, base)
        basename = os.path.basename(path)
        size = os.path.getsize(path)

        log("Datei %d/%d: %s (%d Bytes)" % (
            file_no,
            len(all_files),
            filename,
            size
        ))

        sniffed = sniff_file(path)
        log("  Typ erkannt: %s" % sniffed)

        root_tag = None
        namespace = None
        xml_kind = None

        if sniffed == "xml":
            root_tag, namespace = xml_root_info(path)

            if root_tag == "PackingList":
                xml_kind = "PKL"
            elif root_tag == "CompositionPlaylist":
                xml_kind = "CPL"
            elif root_tag == "AssetMap":
                xml_kind = "ASSETMAP"
            elif root_tag == "VolumeIndex":
                xml_kind = "VOLINDEX"
            elif root_tag == "DCSubtitle":
                xml_kind = "DCSubtitle"
            elif root_tag == "SubtitleReel":
                xml_kind = "SubtitleReel"
            elif root_tag == "DCinemaSecurityMessage":
                xml_kind = "DCinemaSecurityMessage"
            elif root_tag == "SignedDCinemaSecurityMessage":
                xml_kind = "SignedDCinemaSecurityMessage"
            else:
                xml_kind = root_tag

            log("  XML-Art: %s" % xml_kind)

        entry = {
            "filename": filename,
            "basename": basename,
            "size": size,
            "sniffed_type": sniffed,
            "xml_kind": xml_kind,
            "xml_root": root_tag,
            "xml_namespace": namespace
        }

        inventory["files"].append(entry)

        key = xml_kind or sniffed

        if key not in inventory["summary"]:
            inventory["summary"][key] = 0

        inventory["summary"][key] += 1

        if xml_kind == "PKL":
            pkl_data = parse_pkl(path)
            pkl_data["filename"] = filename
            pkl_data["basename"] = basename
            inventory["pkl"].append(pkl_data)

        if xml_kind == "CPL":
            cpl_data = parse_cpl(path)
            cpl_data["filename"] = filename
            cpl_data["basename"] = basename
            inventory["cpl"].append(cpl_data)

    log("Schreibe JSON: %s" % out_json)

    f = open(out_json, "w")
    json.dump(inventory, f, indent=2)
    f.close()

    log("Schreibe TXT: %s" % out_txt)

    f = open(out_txt, "w")

    f.write("DCP Inventory fuer: %s\n\n" % inventory["base"])

    f.write("Zusammenfassung:\n")

    for k in sorted(inventory["summary"].keys()):
        f.write("  %s: %s\n" % (k, inventory["summary"][k]))

    f.write("\nPKL-Dateien:\n")

    for pkl in inventory["pkl"]:
        f.write("\n  Datei: %s\n" % pkl.get("filename"))
        f.write("  PKL-ID: %s\n" % pkl.get("id"))
        f.write("  PKL-UUID: %s\n" % pkl.get("id_uuid"))
        f.write("  Annotation: %s\n" % pkl.get("annotation"))
        f.write("  Issuer: %s\n" % pkl.get("issuer"))
        f.write("  Assets: %d\n" % len(pkl.get("assets", [])))

        for asset in pkl.get("assets", []):
            f.write("    - Id: %s\n" % asset.get("Id"))
            f.write("      IdUuid: %s\n" % asset.get("IdUuid"))
            f.write("      Type: %s\n" % asset.get("Type"))
            f.write("      OriginalFileName: %s\n" % asset.get("OriginalFileName"))
            f.write("      Size: %s\n" % asset.get("Size"))
            f.write("      Hash: %s\n" % asset.get("Hash"))

    f.write("\nCPL-Dateien:\n")

    for cpl in inventory["cpl"]:
        f.write("\n  Datei: %s\n" % cpl.get("filename"))
        f.write("  CPL-ID: %s\n" % cpl.get("id"))
        f.write("  CPL-UUID: %s\n" % cpl.get("id_uuid"))
        f.write("  Annotation: %s\n" % cpl.get("annotation"))
        f.write("  ContentTitleText: %s\n" % cpl.get("content_title_text"))
        f.write("  Issuer: %s\n" % cpl.get("issuer"))

    f.close()

    log("Fertig.")
    log("Inventory geschrieben:")
    log("  %s" % out_json)
    log("  %s" % out_txt)


if __name__ == "__main__":
    main()
