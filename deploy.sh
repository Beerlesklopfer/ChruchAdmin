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
    ('send_massmail', 'Leitung'),
    ('send_massmail', 'Pastor'),
    ('send_massmail', 'Admin'),
    ('send_massmail', 'Admins'),
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
    'church_address': ('Musterstrasse 1, 12345 Beispielstadt', 'general', 'Anschrift der Gemeinde'),
    'church_phone': ('', 'general', 'Telefonnummer'),
    'church_email': ('pastor-beispiel@example-church.de', 'general', 'Kontakt-E-Mail'),
    'church_contact_person': ('Der Pastor', 'general', 'Ansprechperson / Verantwortlicher'),
    'church_register': ('VR XXXX, Amtsgericht Beispielstadt', 'general', 'Vereinsregister'),
    'church_tax_id': ('XXX/XXXX/XXXX, Finanzamt Beispielstadt', 'general', 'Steuernummer'),
    'privacy_contact_person': ('Die Gemeindeleitung', 'general', 'Datenschutz-Ansprechperson'),
    'autoconfig_imap_host': ('imap.example-church.de', 'autoconfig', 'IMAP Server Hostname'),
    'autoconfig_imap_port': ('993', 'autoconfig', 'IMAP Server Port'),
    'autoconfig_smtp_host': ('smtp.example-church.de', 'autoconfig', 'SMTP Server Hostname'),
    'autoconfig_smtp_port': ('465', 'autoconfig', 'SMTP Server Port'),
    'autoconfig_caldav_url': ('https://cloud.example-church.de/', 'autoconfig', 'CalDAV/CardDAV Server URL (Nextcloud)'),
}
for key, (val, cat, desc) in defaults.items():
    obj, created = AppSettings.objects.get_or_create(key=key, defaults={'value': val, 'category': cat, 'description': desc})
    if created:
        print(f'  {key} angelegt')
"

log "Setze Autoconfig-Einstellungen (bestehende werden aktualisiert) ..."
sudo -u www-data ${MANAGE} shell -c "
from authapp.models import AppSettings
autoconfig = {
    'autoconfig_imap_host': ('imap.bibelgemeinde-lage.de', 'autoconfig', 'IMAP Server Hostname'),
    'autoconfig_imap_port': ('993', 'autoconfig', 'IMAP Server Port'),
    'autoconfig_smtp_host': ('smtp.bibelgemeinde-lage.de', 'autoconfig', 'SMTP Server Hostname'),
    'autoconfig_smtp_port': ('465', 'autoconfig', 'SMTP Server Port'),
    'autoconfig_caldav_url': ('https://cloud.bibelgemeinde-lage.de/', 'autoconfig', 'CalDAV/CardDAV Server URL (Nextcloud)'),
}
for key, (val, cat, desc) in autoconfig.items():
    obj, created = AppSettings.objects.update_or_create(
        key=key,
        defaults={'value': val, 'category': cat, 'description': desc}
    )
    status = 'angelegt' if created else 'aktualisiert'
    print(f'  {key} {status}')

from authapp.models import WiFiNetwork
obj, created = WiFiNetwork.objects.get_or_create(
    ssid='Bibelgemeinde-lage',
    defaults={
        'name': 'Gemeinde-WLAN',
        'encryption_type': 'WPA2',
        'is_active': True,
        'sort_order': 0,
    }
)
if created:
    print('  WiFi-Netzwerk Bibelgemeinde-lage angelegt')

from authapp.models import RegistrationResponseTemplate
reg_templates = [
    ('approve_default', 'Willkommen', 'Liebe(r) {{vorname}},\n\nherzlich willkommen in der {{gemeinde}}!\n\nIhr Benutzerkonto wurde erstellt. Sie erhalten in Kuerze eine separate E-Mail mit Ihren Zugangsdaten.\n\nBei Fragen stehen wir Ihnen gerne zur Verfuegung.\n\nMit freundlichen Gruessen\n{{gemeinde}}', 0),
    ('reject_default', 'Ablehnung', 'Liebe(r) {{vorname}},\n\nvielen Dank fuer Ihre Registrierungsanfrage bei der {{gemeinde}}.\n\nLeider koennen wir Ihre Anfrage derzeit nicht genehmigen.\n\nBei Fragen stehen wir Ihnen gerne zur Verfuegung.\n\nMit freundlichen Gruessen\n{{gemeinde}}', 0),
    ('snippet', 'Konto bereits vorhanden', 'Es existiert bereits ein Benutzerkonto fuer Sie. Bitte nutzen Sie die Passwort-Zuruecksetzen-Funktion auf der Login-Seite, falls Sie Ihre Zugangsdaten vergessen haben.', 1),
    ('snippet', 'E-Mail lange nicht verifiziert', 'Ihre E-Mail-Adresse wurde ueber einen laengeren Zeitraum nicht bestaetigt. Bitte stellen Sie eine neue Anfrage und bestaetigen Sie die E-Mail zeitnah.', 2),
    ('snippet', 'Unbekannte Person', 'Wir konnten Sie leider keinem Gemeindemitglied oder Besucher zuordnen. Bitte wenden Sie sich persoenlich an die Gemeindeleitung.', 3),
    ('snippet', 'Bitte persoenlich vorbeikommen', 'Wir wuerden Sie gerne persoenlich kennenlernen. Bitte besuchen Sie uns im naechsten Gottesdienst, damit wir Ihren Zugang einrichten koennen.', 4),
]
for ttype, name, text, order in reg_templates:
    obj, created = RegistrationResponseTemplate.objects.get_or_create(
        template_type=ttype, name=name,
        defaults={'text': text, 'sort_order': order, 'is_active': True}
    )
    if created:
        print(f'  Antwortvorlage {name} angelegt')
"

# systemd Service aktualisieren
if [[ -f "${DEPLOY_DIR}/config/systemd/churchadmin.service" ]]; then
    sudo cp "${DEPLOY_DIR}/config/systemd/churchadmin.service" /usr/lib/systemd/system/churchadmin.service
    sudo systemctl daemon-reload
    log "systemd Service aktualisiert"
fi

# sudoers fuer slapcat (Schema-Backup)
if [[ -f "${DEPLOY_DIR}/config/sudoers.d/churchadmin-slapcat" ]]; then
    sudo cp "${DEPLOY_DIR}/config/sudoers.d/churchadmin-slapcat" /etc/sudoers.d/churchadmin-slapcat
    sudo chmod 440 /etc/sudoers.d/churchadmin-slapcat
    log "sudoers fuer slapcat installiert"
fi

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
