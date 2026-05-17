# Predigt-Cover-Watcher installieren

## Auf dem Nextcloud-Host als root:

```bash
# 1. Mutagen-Library installieren
sudo apt install python3-mutagen

# 2. Script + Logo deployen
sudo mkdir -p /etc/churchadmin
sudo cp embed_cover.py /usr/local/bin/predigt_embed_cover.py
sudo chmod +x /usr/local/bin/predigt_embed_cover.py
sudo cp <dein-logo.png> /etc/churchadmin/predigt-cover.png

# 3. systemd-Units deployen
sudo cp predigt-cover.service /etc/systemd/system/
sudo cp predigt-cover.path    /etc/systemd/system/

# 4. ggf. Pfade in den Units anpassen (Predigt-Verzeichnis, occ-Pfad)
sudo nano /etc/systemd/system/predigt-cover.service
sudo nano /etc/systemd/system/predigt-cover.path

# 5. Erst Dry-Run!
sudo /usr/local/bin/predigt_embed_cover.py \
    --logo /etc/churchadmin/predigt-cover.png \
    --dir /var/lib/nextcloud/data/__groupfolders/1/Predigtaufnahmen/ \
    --description "Bibelgemeinde Lage"

# 6. Wenn Dry-Run okay, einmal manuell scharf:
sudo /usr/local/bin/predigt_embed_cover.py \
    --logo /etc/churchadmin/predigt-cover.png \
    --dir /var/lib/nextcloud/data/__groupfolders/1/Predigtaufnahmen/ \
    --description "Bibelgemeinde Lage" \
    --overwrite --apply

# 7. Watcher aktivieren
sudo systemctl daemon-reload
sudo systemctl enable --now predigt-cover.path

# 8. Pruefen
systemctl status predigt-cover.path
journalctl -u predigt-cover.service -n 50
```

## Test
Eine neue MP3 in das Predigt-Verzeichnis legen (oder eine vorhandene `touch`-en):
```bash
sudo touch /var/lib/nextcloud/data/__groupfolders/1/Predigtaufnahmen/test.mp3
journalctl -u predigt-cover.service -f
```

## Wartung
- Logo aendern: einfach `/etc/churchadmin/predigt-cover.png` ueberschreiben + `--overwrite --apply` einmalig laufen lassen.
- Watcher stoppen: `sudo systemctl disable --now predigt-cover.path`
- Logs: `journalctl -u predigt-cover.service -n 100`
