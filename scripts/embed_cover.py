#!/usr/bin/env python3
"""
Cover-Art in MP3-Dateien einbetten (ID3v2 APIC-Frame).

Verwendung:
  python3 embed_cover.py --logo /pfad/zum/logo.png \
                         --dir /var/lib/nextcloud/data/__groupfolders/1/Predigtaufnahmen/ \
                         [--dry-run] [--overwrite] [--description "Bibelgemeinde Lage"]

Standardverhalten: Dry-Run (loggt was passieren wuerde, schreibt aber nichts).
Schreiben mit: --apply (kein Dry-Run mehr)
Existierende Cover ueberschreiben mit: --overwrite

Nach dem echten Lauf auf dem Nextcloud-Host:
  sudo chown -R www-data:www-data <dir>
  sudo -u www-data php /pfad/zu/nextcloud/occ files:scan --all
"""
import argparse
import sys
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('embed_cover')

try:
    from mutagen.id3 import ID3, APIC, ID3NoHeaderError, error as ID3Error
    from mutagen.mp3 import MP3
except ImportError:
    print('FEHLER: mutagen nicht installiert. Auf dem Nextcloud-Server:')
    print('  sudo apt install python3-mutagen   # Debian/Ubuntu')
    print('  oder: pip3 install mutagen')
    sys.exit(2)


MIME_BY_EXT = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
}


def load_logo(path):
    ext = os.path.splitext(path)[1].lower()
    mime = MIME_BY_EXT.get(ext)
    if not mime:
        raise SystemExit(f'Logo muss .png/.jpg/.jpeg sein (war: {ext})')
    with open(path, 'rb') as f:
        data = f.read()
    log.info(f'Logo geladen: {path} ({len(data)} Bytes, {mime})')
    return data, mime


def find_mp3s(root):
    for dp, _, files in os.walk(root):
        for fn in files:
            if fn.lower().endswith('.mp3'):
                yield os.path.join(dp, fn)


def has_cover(id3):
    return any(isinstance(v, APIC) or (hasattr(v, 'FrameID') and v.FrameID == 'APIC')
               for v in id3.values())


def process(mp3_path, logo_data, logo_mime, description, overwrite, apply_):
    try:
        try:
            tags = ID3(mp3_path)
        except ID3NoHeaderError:
            # Datei hat noch keine ID3-Tags - neu anlegen
            audio = MP3(mp3_path)
            audio.add_tags()
            audio.save()
            tags = ID3(mp3_path)

        existing = [k for k in tags.keys() if k.startswith('APIC')]
        if existing and not overwrite:
            return 'skip-has-cover'

        if existing:
            for k in existing:
                del tags[k]

        tags.add(APIC(
            encoding=3,        # UTF-8
            mime=logo_mime,
            type=3,            # Cover (front)
            desc=description,
            data=logo_data,
        ))

        if apply_:
            tags.save(mp3_path, v2_version=3)  # v2.3 fuer maximale Kompatibilitaet
            return 'written'
        return 'would-write'

    except Exception as e:
        log.error(f'  Fehler bei {mp3_path}: {e}')
        return f'error:{e}'


def main():
    p = argparse.ArgumentParser(description='Embed cover art into MP3 files.')
    p.add_argument('--logo', required=True, help='Pfad zum Logo-Bild (PNG/JPG)')
    p.add_argument('--dir', required=True, help='Wurzel-Verzeichnis (rekursiv)')
    p.add_argument('--description', default='Cover', help='Beschreibung im APIC-Tag')
    p.add_argument('--overwrite', action='store_true', help='Existierende Cover ueberschreiben')
    p.add_argument('--apply', action='store_true', help='Wirklich schreiben (sonst Dry-Run)')
    args = p.parse_args()

    if not os.path.isfile(args.logo):
        raise SystemExit(f'Logo nicht gefunden: {args.logo}')
    if not os.path.isdir(args.dir):
        raise SystemExit(f'Verzeichnis nicht gefunden: {args.dir}')

    logo_data, logo_mime = load_logo(args.logo)

    mode = 'APPLY' if args.apply else 'DRY-RUN'
    log.info(f'== {mode} == overwrite={args.overwrite}')
    log.info(f'Suche MP3s unter {args.dir} ...')

    stats = {}
    total = 0
    for mp3_path in find_mp3s(args.dir):
        total += 1
        result = process(mp3_path, logo_data, logo_mime, args.description, args.overwrite, args.apply)
        stats[result] = stats.get(result, 0) + 1
        rel = os.path.relpath(mp3_path, args.dir)
        log.info(f'  [{result:20}] {rel}')

    print()
    print('=== Zusammenfassung ===')
    print(f'  MP3-Dateien gesamt:  {total}')
    for k, v in sorted(stats.items()):
        print(f'  {k:25} {v}')

    if not args.apply and total:
        print()
        print('Dry-Run beendet. Zum tatsaechlichen Schreiben dieses Kommando mit --apply erneut ausfuehren.')


if __name__ == '__main__':
    main()
