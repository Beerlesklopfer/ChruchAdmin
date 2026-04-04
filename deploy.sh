#!/usr/bin/env bash
#
# Deploy-Script für ChurchAdmin
# Deployed aus dem Git-Repo nach /usr/share/python/ChruchAdmin/
#
set -euo pipefail

# === Konfiguration ===
SRC_DIR="/home/jbernau/ChruchAdmin"
DEPLOY_DIR="/usr/share/python/ChruchAdmin"
VENV_DIR="${DEPLOY_DIR}/.venv"
STATIC_DIR="/usr/share/churchadmin/static"
SERVICE_NAME="churchadmin"
MANAGE="${VENV_DIR}/bin/python3 ${DEPLOY_DIR}/main/manage.py"

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[DEPLOY]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# === Prüfungen ===
if [[ ! -d "$SRC_DIR" ]]; then
    err "Quellverzeichnis $SRC_DIR existiert nicht."
    exit 1
fi

# Prüfe ob sudo funktioniert
if ! sudo -n true 2>/dev/null; then
    log "sudo-Passwort wird benötigt:"
    sudo -v || { err "sudo-Authentifizierung fehlgeschlagen."; exit 1; }
fi

# === 1. Zielverzeichnis vorbereiten ===
log "Synchronisiere Dateien nach ${DEPLOY_DIR} ..."
sudo rsync -a --delete \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.venv' \
    --exclude='.claude' \
    --exclude='db.sqlite3' \
    --exclude='db.sqlite3.backup_*' \
    --exclude='media/' \
    "${SRC_DIR}/" "${DEPLOY_DIR}/"

# === 2. Venv erstellen falls nötig ===
if [[ ! -f "${VENV_DIR}/bin/python3" ]]; then
    log "Erstelle Virtual Environment ..."
    sudo python3 -m venv "${VENV_DIR}"
fi

# === 3. Abhängigkeiten installieren ===
log "Installiere Python-Abhängigkeiten ..."
sudo "${VENV_DIR}/bin/pip" install --quiet --upgrade pip
sudo "${VENV_DIR}/bin/pip" install --quiet -r "${DEPLOY_DIR}/requirements.txt"

# Gunicorn sicherstellen
sudo "${VENV_DIR}/bin/pip" install --quiet gunicorn

# === 4. Berechtigungen setzen (vor Django-Befehlen, damit www-data schreiben kann) ===
log "Setze Berechtigungen ..."
sudo chown -R www-data:www-data "${DEPLOY_DIR}"
sudo mkdir -p "${DEPLOY_DIR}/backups"
sudo chown www-data:www-data "${DEPLOY_DIR}/backups"
sudo mkdir -p "${STATIC_DIR}"
sudo chown -R www-data:www-data "${STATIC_DIR}"
sudo chmod -R 755 "${DEPLOY_DIR}"

# === 5. Django-Befehle ===
log "Führe Migrationen aus ..."
sudo -u www-data ${MANAGE} migrate --noinput

log "Setze Standard-Berechtigungen ..."
sudo -u www-data ${MANAGE} shell -c "
from authapp.models import PermissionMapping
defaults = [
    ('view_members', 'Mitglieder'),
    ('export_members', 'Mitglieder'),
]
for perm, group in defaults:
    obj, created = PermissionMapping.objects.get_or_create(
        permission=perm, group_name=group,
        defaults={'is_active': True}
    )
    if created:
        print(f'  Berechtigung {perm} fuer {group} angelegt')
"

log "Aktualisiere Mail-Vorlagen ..."
sudo -u www-data ${MANAGE} seed_templates

log "Setze Standard-Einstellungen ..."
sudo -u www-data ${MANAGE} shell -c "
from authapp.models import AppSettings
defaults = {
    'church_name': ('Beispielgemeinde', 'general', 'Name der Gemeinde'),
    'church_domain': ('example-church.de', 'general', 'Domain der Gemeinde'),
    'church_address': ('Gasstr. 4, 32791 Lage', 'general', 'Anschrift der Gemeinde'),
    'church_phone': ('+49 5261 808 6 494', 'general', 'Telefonnummer'),
    'church_email': ('info@example-church.de', 'general', 'Kontakt-E-Mail'),
    'church_contact_person': ('Die Gemeindeleitung', 'general', 'Ansprechperson'),
    'privacy_contact_person': ('Die Gemeindeleitung', 'general', 'Datenschutz-Ansprechperson'),
}
for key, (val, cat, desc) in defaults.items():
    obj, created = AppSettings.objects.get_or_create(key=key, defaults={'value': val, 'category': cat, 'description': desc})
    if created:
        print(f'  {key} angelegt')
"

log "Sammle statische Dateien ..."
sudo -u www-data ${MANAGE} collectstatic --noinput

# Static-Verzeichnis für nginx sicherstellen
if [[ -d "${DEPLOY_DIR}/staticfiles" ]]; then
    sudo rsync -a --chown=www-data:www-data "${DEPLOY_DIR}/staticfiles/" "${STATIC_DIR}/"
fi

# === 6. Service neu starten ===
log "Starte ${SERVICE_NAME} neu ..."
sudo systemctl daemon-reload
sudo systemctl restart "${SERVICE_NAME}.service"

# Kurz warten und Status prüfen
sleep 2
if sudo systemctl is-active --quiet "${SERVICE_NAME}.service"; then
    log "Service ${SERVICE_NAME} läuft."
else
    err "Service ${SERVICE_NAME} konnte nicht gestartet werden!"
    sudo systemctl status "${SERVICE_NAME}.service" --no-pager -l
    exit 1
fi

log "Deployment abgeschlossen."
