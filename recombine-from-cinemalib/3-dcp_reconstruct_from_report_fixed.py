#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
# dcp_reconstruct_from_report.py
#
# Python 2.7.5 kompatibles Rekonstruktionsscript fuer eine zerlegte Cinema-Library.
#
# Erwartete Ausgangslage:
#   - Quell-Library: /share/USBDisk1/cinemalib
#   - Report-Datei: /share/USBDisk1/cinemalib/dcp_cpl_asset_report.json
#   - Zielordner:   /share/USBDisk1/DCP
#
# Das Script erstellt pro CPL einen DCP-Ordner und verlinkt CPL + Trackfiles per HARDLINK.
# Zusaetzlich erzeugt es pro DCP:
#   - ASSETMAP.xml
#   - VOLINDEX.xml
#   - PKL_<uuid>.xml
#
# Schreibzugriffe:
#   - nur unterhalb des Zielordners
#   - keine Loeschoperationen
#   - keine Aenderungen an der Quell-Library
#   - vorhandene DCP-Zielordner werden standardmaessig uebersprungen
#
# WICHTIG:
#   Hardlinks funktionieren nur innerhalb desselben Dateisystems.
#   Wenn /share/USBDisk1/cinemalib und /share/USBDisk1/DCP auf demselben Volume liegen, passt das.
#
# Aufruf:
#   python2 dcp_reconstruct_from_report.py /share/USBDisk1/cinemalib/dcp_cpl_asset_report.json /share/USBDisk1/DCP
#
# Testlauf ohne Schreiben:
#   python2 dcp_reconstruct_from_report.py /share/USBDisk1/cinemalib/dcp_cpl_asset_report.json /share/USBDisk1/DCP --dry-run
#
# Optional:
#   --limit N
#       nur die ersten N CPLs verarbeiten
#
#   --only-cpl UUID
#       nur eine bestimmte CPL rekonstruieren
#
#   --skip-existing
#       vorhandene Zielordner ueberspringen, Default
#
#   --fail-existing
#       abbrechen, wenn ein Zielordner bereits existiert
#

import os
import sys
import json
import time
import uuid
import hashlib
import base64
import re
from xml.sax.saxutils import escape

PKL_NS = "http://www.smpte-ra.org/schemas/429-8/2007/PKL"
AM_NS = "http://www.smpte-ra.org/schemas/429-9/2007/AM"
VOLINDEX_NS = "http://www.smpte-ra.org/schemas/429-9/2007/AM"

CREATOR = "dcp_reconstruct_from_report.py"
ISSUER = "Reconstructed from Cinema Library"


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    sys.stdout.write("[%s] %s\n" % (ts, msg))
    sys.stdout.flush()


def usage():
    print "Usage:"
    print "  %s <dcp_cpl_asset_report.json> <zielordner> [--dry-run] [--limit N] [--only-cpl UUID] [--skip-existing|--fail-existing]" % sys.argv[0]
    sys.exit(1)


def now_xml_time():
    return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())


def urn(uid):
    if uid is None:
        return ""
    uid = uid.strip()
    if uid.lower().startswith("urn:uuid:"):
        return uid
    return "urn:uuid:" + uid


def normalize_uuid(value):
    if value is None:
        return None
    value = value.strip()
    if value.lower().startswith("urn:uuid:"):
        value = value[9:]
    value = value.strip("{}")
    return value.lower()


def safe_filename(name, fallback):
    if name is None or name == "":
        name = fallback

    # In Python2 kann Unicode aus JSON kommen.
    try:
        name = name.encode("utf-8")
    except:
        name = str(name)

    # Unerwuenschtes fuer Dateinamen ersetzen.
    name = name.replace("/", "_")
    name = name.replace("\\", "_")
    name = name.replace(":", "_")
    name = name.replace("*", "_")
    name = name.replace("?", "_")
    name = name.replace("\"", "_")
    name = name.replace("<", "_")
    name = name.replace(">", "_")
    name = name.replace("|", "_")

    # Whitespace etwas zaehmen.
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^A-Za-z0-9._+=@#%,-]+', '_', name)

    if len(name) > 120:
        name = name[:120]

    name = name.strip("._- ")

    if name == "":
        name = fallback

    return name


def read_json(path):
    f = open(path, "rb")
    data = json.load(f)
    f.close()
    return data


def write_text(path, data):
    f = open(path, "wb")
    f.write(data)
    f.close()


def sha1_base64(path):
    h = hashlib.sha1()
    f = open(path, "rb")
    while True:
        chunk = f.read(1024 * 1024)
        if not chunk:
            break
        h.update(chunk)
    f.close()
    return base64.b64encode(h.digest())


def read_assethash(base, uid):
    """
    Liest assethashs/<uuid>:
      Hash_Result=<base64sha1>
      On_Nova=true/false
    """
    result = {
        "hash_result": None,
        "on_nova": None
    }

    path = os.path.join(base, "assethashs", uid)

    if not os.path.isfile(path):
        return result

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


def asset_type_for_resource(resource_type):
    """
    PKL Asset Type.
    Diese Strings sind in der Praxis fuer DCPs ueblich.
    """
    if resource_type in ("MainPicture", "MainStereoscopicPicture"):
        return "application/mxf;asdcpKind=Picture"

    if resource_type == "MainSound":
        return "application/mxf;asdcpKind=Sound"

    if resource_type in ("MainSubtitle", "Subtitle", "SubPicture", "SubtitleReel"):
        return "text/xml;asdcpKind=Subtitle"

    if resource_type in ("MainCaption", "MainClosedCaption", "ClosedCaption", "Caption"):
        return "text/xml;asdcpKind=Caption"

    return "application/octet-stream"


def extension_for_resource(resource_type, source_path):
    """
    Ziel-Dateiendung nur fuer bessere Lesbarkeit.
    Der DCP-Player nutzt die ASSETMAP, nicht die Endung.
    """
    lower = source_path.lower()

    if lower.endswith(".mxf"):
        return ".mxf"

    if lower.endswith(".xml"):
        return ".xml"

    if resource_type in ("MainPicture", "MainSound", "MainStereoscopicPicture"):
        return ".mxf"

    return ".xml"


def hardlink_file(src, dst, dry_run):
    if dry_run:
        log("  DRY-RUN hardlink: %s -> %s" % (src, dst))
        return

    if os.path.exists(dst):
        raise Exception("Zieldatei existiert bereits: %s" % dst)

    os.link(src, dst)


def ensure_dir(path, dry_run):
    if dry_run:
        log("  DRY-RUN mkdir: %s" % path)
        return

    if not os.path.isdir(path):
        os.makedirs(path)


def xml_escape(value):
    if value is None:
        return ""
    try:
        value = unicode(value)
    except:
        value = str(value)
    return escape(value.encode("utf-8"))


def pkl_asset_xml(asset):
    # asset: dict with id, annotation, hash, size, type, original_filename
    lines = []
    lines.append("      <Asset>")
    lines.append("        <Id>%s</Id>" % xml_escape(urn(asset["uuid"])))
    lines.append("        <AnnotationText>%s</AnnotationText>" % xml_escape(asset.get("annotation", asset["filename"])))
    lines.append("        <Hash>%s</Hash>" % xml_escape(asset["hash"]))
    lines.append("        <Size>%s</Size>" % asset["size"])
    lines.append("        <Type>%s</Type>" % xml_escape(asset["type"]))
    lines.append("        <OriginalFileName>%s</OriginalFileName>" % xml_escape(asset["filename"]))
    lines.append("      </Asset>")
    return "\n".join(lines)


def create_pkl_xml(pkl_uuid, cpl, assets, issue_date):
    title = cpl.get("content_title_text") or cpl.get("annotation") or cpl.get("cpl_uuid")

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<PackingList xmlns="%s">' % PKL_NS)
    lines.append("  <Id>%s</Id>" % xml_escape(urn(pkl_uuid)))
    lines.append("  <AnnotationText>%s</AnnotationText>" % xml_escape(title))
    lines.append("  <IssueDate>%s</IssueDate>" % xml_escape(issue_date))
    lines.append("  <Issuer>%s</Issuer>" % xml_escape(ISSUER))
    lines.append("  <Creator>%s</Creator>" % xml_escape(CREATOR))
    lines.append("  <AssetList>")

    for asset in assets:
        lines.append(pkl_asset_xml(asset))

    lines.append("  </AssetList>")
    lines.append("</PackingList>")
    lines.append("")
    return "\n".join(lines)


def assetmap_asset_xml(uid, path, size, packing_list=False):
    lines = []
    lines.append("      <Asset>")
    lines.append("        <Id>%s</Id>" % xml_escape(urn(uid)))
    if packing_list:
        lines.append("        <PackingList>true</PackingList>")
    lines.append("        <ChunkList>")
    lines.append("          <Chunk>")
    lines.append("            <Path>%s</Path>" % xml_escape(path))
    lines.append("            <VolumeIndex>1</VolumeIndex>")
    lines.append("            <Offset>0</Offset>")
    lines.append("            <Length>%s</Length>" % size)
    lines.append("          </Chunk>")
    lines.append("        </ChunkList>")
    lines.append("      </Asset>")
    return "\n".join(lines)


def create_assetmap_xml(assetmap_uuid, cpl, assetmap_assets, issue_date):
    title = cpl.get("content_title_text") or cpl.get("annotation") or cpl.get("cpl_uuid")

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<AssetMap xmlns="%s">' % AM_NS)
    lines.append("  <Id>%s</Id>" % xml_escape(urn(assetmap_uuid)))
    lines.append("  <AnnotationText>%s</AnnotationText>" % xml_escape(title))
    lines.append("  <Creator>%s</Creator>" % xml_escape(CREATOR))
    lines.append("  <VolumeCount>1</VolumeCount>")
    lines.append("  <IssueDate>%s</IssueDate>" % xml_escape(issue_date))
    lines.append("  <Issuer>%s</Issuer>" % xml_escape(ISSUER))
    lines.append("  <AssetList>")

    for asset in assetmap_assets:
        lines.append(assetmap_asset_xml(asset["uuid"], asset["path"], asset["size"], asset.get("packing_list", False)))

    lines.append("  </AssetList>")
    lines.append("</AssetMap>")
    lines.append("")
    return "\n".join(lines)


def create_volindex_xml():
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<VolumeIndex xmlns="%s">' % VOLINDEX_NS)
    lines.append("  <Index>1</Index>")
    lines.append("</VolumeIndex>")
    lines.append("")
    return "\n".join(lines)


def parse_args():
    if len(sys.argv) < 3:
        usage()

    report_path = sys.argv[1]
    dest_base = sys.argv[2]

    dry_run = False
    skip_existing = True
    fail_existing = False
    limit = None
    only_cpl = None

    i = 3
    while i < len(sys.argv):
        arg = sys.argv[i]

        if arg == "--dry-run":
            dry_run = True

        elif arg == "--skip-existing":
            skip_existing = True
            fail_existing = False

        elif arg == "--fail-existing":
            fail_existing = True
            skip_existing = False

        elif arg == "--limit":
            i += 1
            if i >= len(sys.argv):
                usage()
            limit = int(sys.argv[i])

        elif arg == "--only-cpl":
            i += 1
            if i >= len(sys.argv):
                usage()
            only_cpl = normalize_uuid(sys.argv[i])

        else:
            print "Unbekanntes Argument: %s" % arg
            usage()

        i += 1

    return report_path, dest_base, dry_run, skip_existing, fail_existing, limit, only_cpl


def main():
    report_path, dest_base, dry_run, skip_existing, fail_existing, limit, only_cpl = parse_args()

    if not os.path.isfile(report_path):
        print "Report nicht gefunden: %s" % report_path
        sys.exit(1)

    report = read_json(report_path)

    source_base = report.get("base")
    if source_base is None or not os.path.isdir(source_base):
        print "Quell-Basisordner aus Report nicht gefunden oder ungueltig: %s" % source_base
        sys.exit(1)

    log("Starte DCP-Rekonstruktion")
    log("Report: %s" % report_path)
    log("Quelle: %s" % source_base)
    log("Ziel: %s" % dest_base)

    if dry_run:
        log("Modus: DRY-RUN, es wird nichts geschrieben")

    if not dry_run:
        if not os.path.isdir(dest_base):
            os.makedirs(dest_base)

    cpls = report.get("cpls", [])

    done = 0
    skipped = 0
    failed = 0

    for cpl in cpls:
        cpl_uuid = normalize_uuid(cpl.get("cpl_uuid"))

        if only_cpl is not None and cpl_uuid != only_cpl:
            continue

        if limit is not None and done >= limit:
            break

        title = cpl.get("content_title_text") or cpl.get("annotation") or cpl_uuid
        safe_title = safe_filename(title, cpl_uuid)

        dcp_dir_name = "%s_%s" % (safe_title, cpl_uuid[:8])
        dcp_dir = os.path.join(dest_base, dcp_dir_name)

        log("------------------------------------------------------------")
        log("CPL: %s" % cpl_uuid)
        log("Titel: %s" % safe_title)
        log("Zielordner: %s" % dcp_dir)

        if os.path.exists(dcp_dir):
            if fail_existing:
                log("FEHLER: Zielordner existiert bereits: %s" % dcp_dir)
                failed += 1
                continue
            if skip_existing:
                log("Ueberspringe vorhandenen Zielordner")
                skipped += 1
                continue

        try:
            ensure_dir(dcp_dir, dry_run)

            issue_date = now_xml_time()

            # Dateinamen im rekonstruierten DCP
            cpl_target_name = "CPL_%s.xml" % cpl_uuid
            pkl_uuid = str(uuid.uuid4())
            pkl_target_name = "PKL_%s.xml" % pkl_uuid

            # CPL hardlinken
            cpl_src = os.path.join(source_base, cpl.get("filename"))
            cpl_dst = os.path.join(dcp_dir, cpl_target_name)

            if not os.path.isfile(cpl_src):
                raise Exception("CPL-Quelldatei fehlt: %s" % cpl_src)

            hardlink_file(cpl_src, cpl_dst, dry_run)

            # Hash fuer CPL: aus assethashs, sonst kleine CPL selbst hashen
            cpl_hash_info = read_assethash(source_base, cpl_uuid)
            cpl_hash = cpl_hash_info.get("hash_result")

            if cpl_hash is None:
                log("  Kein assethash fuer CPL gefunden, berechne SHA1 fuer CPL")
                cpl_hash = sha1_base64(cpl_src)

            pkl_assets = []
            assetmap_assets = []

            # CPL als Asset aufnehmen
            cpl_size = os.path.getsize(cpl_src)
            pkl_assets.append({
                "uuid": cpl_uuid,
                "filename": cpl_target_name,
                "annotation": title,
                "hash": cpl_hash,
                "size": cpl_size,
                "type": "text/xml;asdcpKind=CPL"
            })

            assetmap_assets.append({
                "uuid": cpl_uuid,
                "path": cpl_target_name,
                "size": cpl_size,
                "packing_list": False
            })

            # Trackfiles hardlinken
            assets = cpl.get("assets", [])

            for asset in assets:
                asset_uuid = normalize_uuid(asset.get("uuid"))
                resource_type = asset.get("resource_type")
                rel_source_path = asset.get("path")

                if rel_source_path is None:
                    raise Exception("Asset ohne Pfad: %s" % asset_uuid)

                src = os.path.join(source_base, rel_source_path)

                if not os.path.isfile(src):
                    raise Exception("Asset-Quelldatei fehlt: %s" % src)

                ext = extension_for_resource(resource_type, src)
                target_name = "ASSET_%s%s" % (asset_uuid, ext)
                dst = os.path.join(dcp_dir, target_name)

                hardlink_file(src, dst, dry_run)

                assethash = asset.get("assethash") or {}
                hash_result = assethash.get("hash_result")

                if hash_result is None:
                    # Sollte laut Analyse praktisch nicht passieren.
                    # Kein stilles Hashen riesiger MXF-Dateien, weil das auf dem NAS brutal dauert.
                    raise Exception("Kein Hash_Result fuer Asset %s vorhanden. Abbruch, damit keine unvollstaendige PKL entsteht." % asset_uuid)

                size = os.path.getsize(src)

                pkl_assets.append({
                    "uuid": asset_uuid,
                    "filename": target_name,
                    "annotation": resource_type,
                    "hash": hash_result,
                    "size": size,
                    "type": asset_type_for_resource(resource_type)
                })

                assetmap_assets.append({
                    "uuid": asset_uuid,
                    "path": target_name,
                    "size": size,
                    "packing_list": False
                })

            # PKL erzeugen
            pkl_xml = create_pkl_xml(pkl_uuid, cpl, pkl_assets, issue_date)

            pkl_dst = os.path.join(dcp_dir, pkl_target_name)

            if dry_run:
                log("  DRY-RUN write: %s" % pkl_dst)
                pkl_size = len(pkl_xml)
            else:
                write_text(pkl_dst, pkl_xml)
                pkl_size = os.path.getsize(pkl_dst)

            # PKL in ASSETMAP aufnehmen
            assetmap_assets.insert(0, {
                "uuid": pkl_uuid,
                "path": pkl_target_name,
                "size": pkl_size,
                "packing_list": True
            })

            # ASSETMAP + VOLINDEX erzeugen
            assetmap_uuid = str(uuid.uuid4())
            assetmap_xml = create_assetmap_xml(assetmap_uuid, cpl, assetmap_assets, issue_date)
            volindex_xml = create_volindex_xml()

            assetmap_dst = os.path.join(dcp_dir, "ASSETMAP.xml")
            volindex_dst = os.path.join(dcp_dir, "VOLINDEX.xml")

            if dry_run:
                log("  DRY-RUN write: %s" % assetmap_dst)
                log("  DRY-RUN write: %s" % volindex_dst)
            else:
                write_text(assetmap_dst, assetmap_xml)
                write_text(volindex_dst, volindex_xml)

            log("OK: DCP rekonstruiert, Assets: %d" % len(assets))
            done += 1

        except Exception as e:
            log("FEHLER bei CPL %s: %s" % (cpl_uuid, str(e)))
            failed += 1

    log("------------------------------------------------------------")
    log("Fertig.")
    log("Rekonstruiert: %d" % done)
    log("Uebersprungen: %d" % skipped)
    log("Fehler: %d" % failed)


if __name__ == "__main__":
    main()
