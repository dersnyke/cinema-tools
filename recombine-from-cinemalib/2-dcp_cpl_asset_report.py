#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
# dcp_cpl_asset_report.py
#
# Python 2.7.5 kompatibles Analyse-Script fuer zerlegte Cinema-Library/DCP-Ordner.
#
# Zweck:
#   - findet rekursiv CPL-Dateien
#   - extrahiert aus jeder CPL die referenzierten Asset-UUIDs
#   - sucht passende Dateien anhand UUID/Basename im gesamten Library-Ordner
#   - liest optional assethashs/<uuid> mit Hash_Result und On_Nova
#   - schreibt einen Report:
#       dcp_cpl_asset_report.json
#       dcp_cpl_asset_report.txt
#
# Schreibzugriffe:
#   - nur die zwei Report-Dateien im angegebenen Basisordner
#   - vorhandene Report-Dateien werden NICHT ueberschrieben
#
# Aufruf:
#   python2 dcp_cpl_asset_report.py /share/USBDisk1/cinemalib
#
# Hinweis:
#   Dieses Script rekonstruiert noch keine DCP-Ordner.
#   Es liefert die Datenbasis dafuer: Welche CPL braucht welche Assets, und wo liegen sie?

import os
import sys
import json
import time
import re
import xml.etree.ElementTree as ET

UUID_RE = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    sys.stdout.write("[%s] %s\n" % (ts, msg))
    sys.stdout.flush()


def strip_namespace(tag):
    if tag is None:
        return None
    return tag.split("}")[-1]


def normalize_uuid(value):
    if value is None:
        return None

    value = value.strip()

    if value.lower().startswith("urn:uuid:"):
        value = value[9:]

    value = value.strip("{}")
    return value.lower()


def is_uuid(value):
    if value is None:
        return False
    return UUID_RE.match(value) is not None


def safe_text(value):
    if value is None:
        return ""
    try:
        return value.encode("utf-8")
    except:
        return str(value)


def read_head(path, maxbytes):
    try:
        f = open(path, "rb")
        data = f.read(maxbytes)
        f.close()
        return data
    except:
        return ""


def sniff_file(path):
    head = read_head(path, 16384)

    if head.startswith("\x06\x0e\x2b\x34"):
        return "mxf"

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

    return "unknown"


def xml_root_tag(path):
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        return strip_namespace(root.tag)
    except:
        return None


def find_first_text(root, local_name):
    for elem in root.iter():
        if strip_namespace(elem.tag) == local_name:
            return elem.text
    return None


def parse_assethash_file(path):
    result = {
        "hash_result": None,
        "on_nova": None
    }

    try:
        f = open(path, "rb")
        data = f.read(1024)
        f.close()

        for line in data.splitlines():
            line = line.strip()

            if line.startswith("Hash_Result="):
                result["hash_result"] = line.split("=", 1)[1]

            elif line.startswith("On_Nova="):
                result["on_nova"] = line.split("=", 1)[1]

    except Exception as e:
        result["error"] = str(e)

    return result


def parse_cpl(path):
    """
    Parst CPL und extrahiert:
      - CPL-ID
      - ContentTitleText
      - AnnotationText
      - Issuer
      - alle referenzierten Asset-UUIDs aus Marker/MainPicture/MainSound/MainSubtitle/MainCaption/etc.
    """
    result = {
        "cpl_id": None,
        "cpl_uuid": None,
        "annotation": None,
        "content_title_text": None,
        "issuer": None,
        "referenced_assets": []
    }

    tree = ET.parse(path)
    root = tree.getroot()

    result["cpl_id"] = find_first_text(root, "Id")
    result["cpl_uuid"] = normalize_uuid(result["cpl_id"])
    result["annotation"] = find_first_text(root, "AnnotationText")
    result["content_title_text"] = find_first_text(root, "ContentTitleText")
    result["issuer"] = find_first_text(root, "Issuer")

    # In CPLs stehen die AssetRefs typischerweise als Id innerhalb von
    # MainPicture, MainSound, MainSubtitle, MainCaption, MarkerResource usw.
    # Wir nehmen nicht blind jede Id, sondern merken uns den Eltern-Tag.
    known_asset_parents = set([
        "MainPicture",
        "MainSound",
        "MainSubtitle",
        "MainCaption",
        "MainClosedCaption",
        "MainStereoscopicPicture",
        "SubPicture",
        "ClosedCaption",
        "Caption",
        "Subtitle",
        "MarkerResource",
        "AuxData",
        "Data"
    ])

    seen = {}

    def walk(parent):
        parent_tag = strip_namespace(parent.tag)

        for child in list(parent):
            child_tag = strip_namespace(child.tag)

            if child_tag == "Id" and parent_tag in known_asset_parents:
                uid = normalize_uuid(child.text)

                if is_uuid(uid) and uid not in seen:
                    seen[uid] = True
                    result["referenced_assets"].append({
                        "uuid": uid,
                        "resource_type": parent_tag
                    })

            walk(child)

    walk(root)

    return result


def build_file_index(base):
    """
    Indexiert alle Dateien.
    Wichtige Annahme:
      Viele echte Asset-Dateien heissen direkt nach UUID oder mit Prefix wie cpl_<uuid>.
    """
    all_files = []
    by_uuid = {}
    assethash_by_uuid = {}
    cpl_files = []

    for root, dirs, files in os.walk(base):
        for name in files:
            full = os.path.join(root, name)

            if not os.path.isfile(full):
                continue

            rel = os.path.relpath(full, base)
            basename = os.path.basename(full)
            size = os.path.getsize(full)

            entry = {
                "path": full,
                "relpath": rel,
                "basename": basename,
                "size": size
            }

            all_files.append(entry)

            # UUID aus Basename direkt
            candidates = []

            if is_uuid(basename):
                candidates.append(basename.lower())

            # UUID aus bekannten Prefix-Namen wie cpl_<uuid>
            if basename.startswith("cpl_"):
                maybe = basename[4:]
                if is_uuid(maybe):
                    candidates.append(maybe.lower())

            # allgemeiner Fallback: letzte UUID im Dateinamen suchen
            m = re.search(r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})', basename)
            if m:
                candidates.append(m.group(1).lower())

            for uid in candidates:
                if uid not in by_uuid:
                    by_uuid[uid] = []
                by_uuid[uid].append(entry)

            # assethashs/<uuid>
            if os.path.basename(os.path.dirname(full)) == "assethashs" and is_uuid(basename):
                assethash_by_uuid[basename.lower()] = parse_assethash_file(full)

            # CPL erkennen ueber Pfad/Praefix und XML Root
            if basename.startswith("cpl_"):
                cpl_files.append(entry)
            else:
                # Nur kleine/mittlere Dateien als XML testparsen, nicht jede MXF.
                if size < 20 * 1024 * 1024:
                    if sniff_file(full) == "xml" and xml_root_tag(full) == "CompositionPlaylist":
                        cpl_files.append(entry)

    return all_files, by_uuid, assethash_by_uuid, cpl_files


def pick_best_match(matches):
    """
    Wählt aus mehreren Kandidaten einen plausiblen Asset-Dateipfad.
    assethashs-Dateien sind nur Hash-Metadaten, nicht das eigentliche Asset.
    compositions/cpl_* sind CPLs, auch nicht das Ziel-Asset fuer Picture/Sound.
    """
    if not matches:
        return None

    filtered = []

    for m in matches:
        rel = m["relpath"]

        if rel.startswith("assethashs/"):
            continue

        if rel.startswith("compositions/"):
            continue

        filtered.append(m)

    if len(filtered) == 0:
        filtered = matches

    # Echte MXF/Subtitles sind groesser als die kleinen assethashs.
    filtered.sort(key=lambda x: x["size"], reverse=True)
    return filtered[0]


def main():
    if len(sys.argv) != 2:
        print "Usage: %s <cinemalib-ordner>" % sys.argv[0]
        sys.exit(1)

    base = sys.argv[1]

    if not os.path.isdir(base):
        print "Pfad ist kein Ordner."
        sys.exit(1)

    base_abs = os.path.abspath(base)

    out_json = os.path.join(base, "dcp_cpl_asset_report.json")
    out_txt = os.path.join(base, "dcp_cpl_asset_report.txt")

    if os.path.exists(out_json):
        log("Abbruch: Datei existiert bereits: %s" % out_json)
        sys.exit(1)

    if os.path.exists(out_txt):
        log("Abbruch: Datei existiert bereits: %s" % out_txt)
        sys.exit(1)

    log("Starte CPL-Asset-Analyse")
    log("Basisordner: %s" % base_abs)

    log("Indexiere Dateien...")
    all_files, by_uuid, assethash_by_uuid, cpl_files = build_file_index(base)

    log("Dateien gesamt: %d" % len(all_files))
    log("UUIDs im Dateinamen-Index: %d" % len(by_uuid.keys()))
    log("AssetHash-Dateien: %d" % len(assethash_by_uuid.keys()))
    log("CPL-Kandidaten: %d" % len(cpl_files))

    report = {
        "base": base_abs,
        "summary": {
            "files_total": len(all_files),
            "uuid_index_entries": len(by_uuid.keys()),
            "assethash_files": len(assethash_by_uuid.keys()),
            "cpl_candidates": len(cpl_files),
            "cpl_parsed": 0,
            "assets_referenced_total": 0,
            "assets_found_total": 0,
            "assets_missing_total": 0
        },
        "cpls": []
    }

    cpl_no = 0

    for cpl_entry in sorted(cpl_files, key=lambda x: x["relpath"]):
        cpl_no += 1
        log("CPL %d/%d: %s" % (cpl_no, len(cpl_files), cpl_entry["relpath"]))

        try:
            cpl = parse_cpl(cpl_entry["path"])
        except Exception as e:
            log("  WARNUNG: CPL konnte nicht geparst werden: %s" % str(e))
            report["cpls"].append({
                "filename": cpl_entry["relpath"],
                "error": str(e)
            })
            continue

        report["summary"]["cpl_parsed"] += 1

        cpl_result = {
            "filename": cpl_entry["relpath"],
            "basename": cpl_entry["basename"],
            "size": cpl_entry["size"],
            "cpl_id": cpl["cpl_id"],
            "cpl_uuid": cpl["cpl_uuid"],
            "annotation": cpl["annotation"],
            "content_title_text": cpl["content_title_text"],
            "issuer": cpl["issuer"],
            "assets": [],
            "assets_found": 0,
            "assets_missing": 0
        }

        for asset in cpl["referenced_assets"]:
            uid = asset["uuid"]
            matches = by_uuid.get(uid, [])
            best = pick_best_match(matches)
            ah = assethash_by_uuid.get(uid)

            asset_result = {
                "uuid": uid,
                "resource_type": asset["resource_type"],
                "found": best is not None,
                "match_count": len(matches),
                "path": None,
                "size": None,
                "assethash": ah
            }

            if best is not None:
                asset_result["path"] = best["relpath"]
                asset_result["size"] = best["size"]
                cpl_result["assets_found"] += 1
                report["summary"]["assets_found_total"] += 1
            else:
                cpl_result["assets_missing"] += 1
                report["summary"]["assets_missing_total"] += 1

            report["summary"]["assets_referenced_total"] += 1
            cpl_result["assets"].append(asset_result)

        log("  Titel: %s" % safe_text(cpl_result["content_title_text"]))
        log("  Assets: %d gefunden: %d fehlt: %d" % (
            len(cpl_result["assets"]),
            cpl_result["assets_found"],
            cpl_result["assets_missing"]
        ))

        report["cpls"].append(cpl_result)

    log("Schreibe JSON: %s" % out_json)
    f = open(out_json, "w")
    json.dump(report, f, indent=2)
    f.close()

    log("Schreibe TXT: %s" % out_txt)
    f = open(out_txt, "w")

    f.write("DCP CPL Asset Report fuer: %s\n\n" % report["base"])
    f.write("Zusammenfassung:\n")
    for k in sorted(report["summary"].keys()):
        f.write("  %s: %s\n" % (k, report["summary"][k]))

    f.write("\nCPLs:\n")

    for cpl in report["cpls"]:
        f.write("\n------------------------------------------------------------\n")
        f.write("Datei: %s\n" % cpl.get("filename"))
        f.write("CPL-ID: %s\n" % cpl.get("cpl_id"))
        f.write("CPL-UUID: %s\n" % cpl.get("cpl_uuid"))
        f.write("Annotation: %s\n" % cpl.get("annotation"))
        f.write("ContentTitleText: %s\n" % cpl.get("content_title_text"))
        f.write("Issuer: %s\n" % cpl.get("issuer"))
        f.write("Assets: %d gefunden: %d fehlt: %d\n" % (
            len(cpl.get("assets", [])),
            cpl.get("assets_found", 0),
            cpl.get("assets_missing", 0)
        ))

        for asset in cpl.get("assets", []):
            f.write("  - %s %s\n" % (asset.get("resource_type"), asset.get("uuid")))
            f.write("    gefunden: %s\n" % asset.get("found"))
            f.write("    match_count: %s\n" % asset.get("match_count"))
            f.write("    pfad: %s\n" % asset.get("path"))
            f.write("    size: %s\n" % asset.get("size"))

            ah = asset.get("assethash")
            if ah:
                f.write("    Hash_Result: %s\n" % ah.get("hash_result"))
                f.write("    On_Nova: %s\n" % ah.get("on_nova"))

    f.close()

    log("Fertig.")
    log("Report geschrieben:")
    log("  %s" % out_json)
    log("  %s" % out_txt)


if __name__ == "__main__":
    main()
