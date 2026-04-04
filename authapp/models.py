from django.db import models
from django.contrib.auth.models import User
import json

class LDAPConfig(models.Model):
    """LDAP Konfiguration speichern"""
    name = models.CharField(max_length=100, unique=True)
    server_uri = models.CharField(max_length=200)
    bind_dn = models.CharField(max_length=200)
    bind_password = models.CharField(max_length=200, blank=True)
    user_search_base = models.CharField(max_length=200)
    user_search_filter = models.CharField(max_length=200, default="(uid=%(user)s)")
    group_search_base = models.CharField(max_length=200, blank=True)
    
    # Attribute Mapping als JSON
    attribute_mapping = models.TextField(
        default='{"first_name": "givenName", "last_name": "sn", "email": "mail"}'
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def get_attribute_mapping(self):
        """Gibt Attribute Mapping als Dictionary zurück"""
        try:
            return json.loads(self.attribute_mapping)
        except:
            return {"first_name": "givenName", "last_name": "sn", "email": "mail"}
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "LDAP Konfiguration"
        verbose_name_plural = "LDAP Konfigurationen"

class LDAPUserLog(models.Model):
    """LDAP Benutzer Aktivitäten loggen"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=50)  # login, sync, error
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.timestamp}"

    class Meta:
        verbose_name = "LDAP Log"
        verbose_name_plural = "LDAP Logs"
        ordering = ['-timestamp']


class AppSettings(models.Model):
    """
    Anwendungseinstellungen in SQLite-Datenbank
    Key-Value Store für flexible Konfiguration
    """
    CATEGORY_CHOICES = [
        ('email', 'E-Mail'),
        ('recaptcha', 'reCAPTCHA'),
        ('ldap', 'LDAP'),
        ('registration', 'Registrierung'),
        ('general', 'Allgemein'),
    ]

    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='general')
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True)
    description = models.TextField(blank=True, help_text="Beschreibung der Einstellung")
    is_encrypted = models.BooleanField(default=False, help_text="Wert verschlüsselt speichern (z.B. Passwörter)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Anwendungseinstellung"
        verbose_name_plural = "Anwendungseinstellungen"
        ordering = ['category', 'key']

    def __str__(self):
        return f"{self.category}: {self.key}"

    @classmethod
    def get(cls, key, default=None):
        """Hole Einstellung nach Key"""
        try:
            setting = cls.objects.get(key=key)
            return setting.value if setting.value else default
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key, value, category='general', description=''):
        """Setze oder aktualisiere Einstellung"""
        setting, created = cls.objects.update_or_create(
            key=key,
            defaults={
                'value': value,
                'category': category,
                'description': description
            }
        )
        return setting


# ==================== WORKFLOW/PROZESS MANAGEMENT ====================

class ProcessTemplate(models.Model):
    """
    Wiederverwendbare Prozess-Templates
    z.B. "Mitglieder-Onboarding", "Familien-Onboarding", "Mitarbeiter-Onboarding", "Offboarding"
    """
    PROCESS_TYPE_CHOICES = [
        ('member_onboarding', 'Mitglieder-Onboarding'),
        ('family_onboarding', 'Familien-Onboarding'),
        ('volunteer_onboarding', 'Mitarbeiter-Onboarding'),
        ('offboarding', 'Offboarding'),
        ('custom', 'Benutzerdefiniert'),
    ]

    name = models.CharField(max_length=200)
    process_type = models.CharField(max_length=50, choices=PROCESS_TYPE_CHOICES)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_templates')

    # Automatische E-Mails aktivieren
    auto_email_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Prozess-Template"
        verbose_name_plural = "Prozess-Templates"
        ordering = ['process_type', 'name']

    def __str__(self):
        return f"{self.get_process_type_display()}: {self.name}"


class ProcessStep(models.Model):
    """
    Einzelne Schritte innerhalb eines Prozess-Templates
    Unterstützt Drag & Drop für Reihenfolge
    """
    template = models.ForeignKey(ProcessTemplate, on_delete=models.CASCADE, related_name='steps')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0, help_text="Reihenfolge (unterstützt Drag & Drop)")

    # Verantwortlichkeit
    ASSIGNEE_CHOICES = [
        ('pastor', 'Pastor'),
        ('admin', 'Administrator'),
        ('mentor', 'Mentor'),
        ('auto', 'Automatisch'),
    ]
    default_assignee = models.CharField(max_length=50, choices=ASSIGNEE_CHOICES, default='admin')

    # Ist dieser Schritt erforderlich?
    is_required = models.BooleanField(default=True)

    # Geschätzte Dauer in Tagen
    estimated_days = models.IntegerField(default=1, help_text="Geschätzte Dauer in Tagen")

    class Meta:
        verbose_name = "Prozess-Schritt"
        verbose_name_plural = "Prozess-Schritte"
        ordering = ['template', 'order']

    def __str__(self):
        return f"{self.template.name} - {self.order}. {self.title}"


class ProcessInstance(models.Model):
    """
    Eine konkrete Instanz eines Prozesses für eine Person/Familie
    """
    STATUS_CHOICES = [
        ('pending', 'Ausstehend'),
        ('in_progress', 'In Bearbeitung'),
        ('on_hold', 'Pausiert'),
        ('completed', 'Abgeschlossen'),
        ('cancelled', 'Abgebrochen'),
    ]

    template = models.ForeignKey(ProcessTemplate, on_delete=models.PROTECT)

    # Für wen ist dieser Prozess? (LDAP CN oder User ID)
    subject_ldap_cn = models.CharField(max_length=200, help_text="LDAP CN des Betroffenen")
    subject_name = models.CharField(max_length=200, help_text="Name des Betroffenen")

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Zugewiesen an
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_processes')

    # Timestamps
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Notizen
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Prozess-Instanz"
        verbose_name_plural = "Prozess-Instanzen"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.template.name} für {self.subject_name} ({self.get_status_display()})"

    @property
    def progress_percentage(self):
        """Berechne Fortschritt in Prozent"""
        total_steps = self.step_instances.count()
        if total_steps == 0:
            return 0
        completed_steps = self.step_instances.filter(status='completed').count()
        return int((completed_steps / total_steps) * 100)


class ProcessStepInstance(models.Model):
    """
    Eine konkrete Instanz eines Prozess-Schritts
    Mit Checkliste und Status-Tracking
    """
    STATUS_CHOICES = [
        ('pending', 'Ausstehend'),
        ('in_progress', 'In Bearbeitung'),
        ('completed', 'Abgeschlossen'),
        ('skipped', 'Übersprungen'),
    ]

    process = models.ForeignKey(ProcessInstance, on_delete=models.CASCADE, related_name='step_instances')
    step = models.ForeignKey(ProcessStep, on_delete=models.PROTECT)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Zugewiesen an (kann überschrieben werden)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_steps')

    # Timestamps
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)

    # Notizen für diesen Schritt
    notes = models.TextField(blank=True)

    # Completed by
    completed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='completed_steps')

    class Meta:
        verbose_name = "Schritt-Instanz"
        verbose_name_plural = "Schritt-Instanzen"
        ordering = ['process', 'step__order']

    def __str__(self):
        return f"{self.process.subject_name} - {self.step.title} ({self.get_status_display()})"


class ProcessChecklistItem(models.Model):
    """
    Checklisten-Items für Prozess-Schritte
    Unterstützt Drag & Drop für Neuordnung
    """
    step_instance = models.ForeignKey(ProcessStepInstance, on_delete=models.CASCADE, related_name='checklist_items')

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)

    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Checklisten-Item"
        verbose_name_plural = "Checklisten-Items"
        ordering = ['step_instance', 'order']

    def __str__(self):
        status = "✓" if self.is_completed else "○"
        return f"{status} {self.title}"


class ProcessNotification(models.Model):
    """
    Automatische Benachrichtigungen für Prozess-Events
    """
    EVENT_CHOICES = [
        ('process_started', 'Prozess gestartet'),
        ('process_completed', 'Prozess abgeschlossen'),
        ('step_assigned', 'Schritt zugewiesen'),
        ('step_completed', 'Schritt abgeschlossen'),
        ('step_overdue', 'Schritt überfällig'),
    ]

    process = models.ForeignKey(ProcessInstance, on_delete=models.CASCADE, related_name='notifications')
    event = models.CharField(max_length=50, choices=EVENT_CHOICES)

    recipient = models.ForeignKey(User, on_delete=models.CASCADE)

    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    # E-Mail gesendet?
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Prozess-Benachrichtigung"
        verbose_name_plural = "Prozess-Benachrichtigungen"
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.get_event_display()} - {self.recipient.username}"


# ==================== GEMEINDELISTEN-EXPORT ====================

class MemberListExportSettings(models.Model):
    """
    Einstellungen für den Export der Gemeindeliste
    Definiert welche Felder exportiert werden
    """
    name = models.CharField(max_length=200, help_text="Name der Export-Konfiguration")
    description = models.TextField(blank=True)

    # Welche Felder sollen exportiert werden?
    include_name = models.BooleanField(default=True, help_text="Vor- und Nachname")
    include_email = models.BooleanField(default=True, help_text="E-Mail-Adresse")
    include_phone = models.BooleanField(default=False, help_text="Telefonnummer")
    include_address = models.BooleanField(default=False, help_text="Adresse")
    include_birthday = models.BooleanField(default=False, help_text="Geburtsdatum")
    include_groups = models.BooleanField(default=True, help_text="Gruppenmitgliedschaften")
    include_family = models.BooleanField(default=True, help_text="Familienzugehörigkeit")

    # Filter: Welche Benutzer exportieren?
    FILTER_CHOICES = [
        ('all', 'Alle Benutzer'),
        ('members', 'Nur Mitglieder'),
        ('visitors', 'Nur Besucher'),
        ('family_heads', 'Nur Familienoberhäupter'),
    ]
    user_filter = models.CharField(max_length=50, choices=FILTER_CHOICES, default='all')

    # Sortierung
    SORT_CHOICES = [
        ('sn', 'Nach Nachname'),
        ('givenName', 'Nach Vorname'),
        ('mail', 'Nach E-Mail'),
    ]
    sort_by = models.CharField(max_length=50, choices=SORT_CHOICES, default='sn')

    # Wer darf diese Konfiguration verwenden?
    is_public = models.BooleanField(default=True, help_text="Für alle Benutzer verfügbar")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_export_settings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Export-Einstellung"
        verbose_name_plural = "Export-Einstellungen"
        ordering = ['name']

    def __str__(self):
        return self.name


# ==================== BERECHTIGUNGSVERWALTUNG ====================

class PermissionMapping(models.Model):
    """
    Zuordnung von Berechtigungen zu LDAP-Gruppen
    Ermöglicht dynamische Verwaltung von Berechtigungen
    """
    PERMISSION_CHOICES = [
        ('manage_users', 'Benutzer verwalten'),
        ('manage_groups', 'Gruppen verwalten'),
        ('manage_families', 'Familien verwalten'),
        ('manage_mail', 'Mail-Verwaltung'),
        ('manage_mail_domains', 'Mail-Domains verwalten'),
        ('view_members', 'Gemeindeliste ansehen'),
        ('edit_members', 'Gemeindeliste bearbeiten'),
        ('export_members', 'Gemeindeliste exportieren'),
    ]

    permission = models.CharField(
        max_length=50,
        choices=PERMISSION_CHOICES,
        help_text="Die Berechtigung, die zugewiesen wird"
    )
    group_name = models.CharField(
        max_length=200,
        help_text="Name der LDAP-Gruppe (z.B. 'Leitung', 'Pastor')"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Ist diese Zuordnung aktiv?"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_permissions'
    )

    class Meta:
        verbose_name = "Berechtigungs-Zuordnung"
        verbose_name_plural = "Berechtigungs-Zuordnungen"
        ordering = ['permission', 'group_name']
        unique_together = [['permission', 'group_name']]
        indexes = [
            models.Index(fields=['permission', 'is_active']),
            models.Index(fields=['group_name', 'is_active']),
        ]

    def __str__(self):
        return f"{self.get_permission_display()} → {self.group_name}"

    @classmethod
    def get_groups_for_permission(cls, permission):
        """
        Gibt alle aktiven Gruppen für eine bestimmte Berechtigung zurück

        Args:
            permission (str): Der Permission-Key (z.B. 'manage_users')

        Returns:
            list: Liste der Gruppennamen
        """
        return list(
            cls.objects.filter(
                permission=permission,
                is_active=True
            ).values_list('group_name', flat=True)
        )

    @classmethod
    def has_permission(cls, permission, group_names):
        """
        Prüft ob eine der angegebenen Gruppen die Berechtigung hat

        Args:
            permission (str): Der Permission-Key
            group_names (list): Liste der Gruppennamen des Benutzers

        Returns:
            bool: True wenn mindestens eine Gruppe die Berechtigung hat
        """
        if not group_names:
            return False

        return cls.objects.filter(
            permission=permission,
            group_name__in=group_names,
            is_active=True
        ).exists()

    @classmethod
    def set_permission(cls, permission, group_name, enabled, created_by=None):
        """
        Setzt oder entfernt eine Berechtigung für eine Gruppe

        Args:
            permission (str): Der Permission-Key
            group_name (str): Name der LDAP-Gruppe
            enabled (bool): Berechtigung aktivieren (True) oder deaktivieren (False)
            created_by (User): Der Benutzer, der die Änderung vornimmt

        Returns:
            PermissionMapping: Das erstellte/aktualisierte Objekt
        """
        mapping, created = cls.objects.update_or_create(
            permission=permission,
            group_name=group_name,
            defaults={
                'is_active': enabled,
                'created_by': created_by
            }
        )
        return mapping


class PasswordResetToken(models.Model):
    """
    Token für Passwort-Zurücksetzen
    Mit Ablaufzeit und Einmalverwendung
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens',
        help_text='Der Benutzer für den dieser Token gilt'
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        help_text='Kryptographisch sicherer Token'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        help_text='Ablaufzeitpunkt des Tokens (24 Stunden)'
    )
    used = models.BooleanField(
        default=False,
        help_text='Wurde der Token bereits verwendet?'
    )
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Zeitpunkt der Verwendung'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text='IP-Adresse der Anfrage'
    )

    class Meta:
        verbose_name = 'Passwort-Reset-Token'
        verbose_name_plural = 'Passwort-Reset-Tokens'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token', 'used']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"Reset-Token für {self.user.username} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

    def is_valid(self):
        """
        Prüft ob der Token noch gültig ist

        Returns:
            bool: True wenn Token gültig und nicht abgelaufen
        """
        from django.utils import timezone

        if self.used:
            return False

        if timezone.now() > self.expires_at:
            return False

        return True

    def mark_as_used(self):
        """Markiert den Token als verwendet"""
        from django.utils import timezone

        self.used = True
        self.used_at = timezone.now()
        self.save()

    @classmethod
    def create_token(cls, user, ip_address=None):
        """
        Erstellt einen neuen Reset-Token für einen Benutzer

        Args:
            user (User): Der Benutzer
            ip_address (str): IP-Adresse der Anfrage

        Returns:
            PasswordResetToken: Der erstellte Token
        """
        import secrets
        from django.utils import timezone
        from datetime import timedelta

        # Generiere kryptographisch sicheren Token
        token = secrets.token_urlsafe(48)

        # Token läuft nach 24 Stunden ab
        expires_at = timezone.now() + timedelta(hours=24)

        return cls.objects.create(
            user=user,
            token=token,
            expires_at=expires_at,
            ip_address=ip_address
        )

    @classmethod
    def cleanup_expired(cls):
        """
        Löscht abgelaufene und bereits verwendete Tokens
        (Sollte regelmäßig per Cronjob ausgeführt werden)
        """
        from django.utils import timezone
        from datetime import timedelta

        # Lösche Tokens älter als 7 Tage
        cutoff_date = timezone.now() - timedelta(days=7)
        deleted_count = cls.objects.filter(created_at__lt=cutoff_date).delete()[0]

        return deleted_count


# ==================== E-MAIL TEMPLATES ====================

class EmailTemplate(models.Model):
    """
    Editierbare E-Mail-Vorlagen für automatische E-Mails
    z.B. Willkommens-Mails bei Mitgliederaufnahme
    """
    TEMPLATE_TYPE_CHOICES = [
        ('member_welcome', 'Begrüßung neues Mitglied'),
        ('member_removed', 'Mitgliedschaft beendet'),
        ('password_reset', 'Passwort zurücksetzen'),
        ('account_created', 'Konto erstellt'),
        ('custom', 'Benutzerdefiniert'),
    ]

    name = models.CharField(
        max_length=200,
        verbose_name="Vorlagenname",
        help_text="Interner Name der Vorlage"
    )
    template_type = models.CharField(
        max_length=50,
        choices=TEMPLATE_TYPE_CHOICES,
        unique=True,
        verbose_name="Vorlagentyp",
        help_text="Typ der E-Mail-Vorlage"
    )
    subject = models.CharField(
        max_length=200,
        verbose_name="Betreff",
        help_text="Betreff der E-Mail. Platzhalter: {{name}}, {{email}}, {{username}}"
    )
    body = models.TextField(
        verbose_name="Nachricht",
        help_text="Nachrichtentext. Platzhalter: {{name}}, {{email}}, {{username}}, {{first_name}}, {{last_name}}"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv",
        help_text="Wenn deaktiviert, wird die E-Mail nicht versendet"
    )
    send_automatically = models.BooleanField(
        default=True,
        verbose_name="Automatisch senden",
        help_text="E-Mail automatisch beim Ereignis versenden"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        verbose_name = "E-Mail-Vorlage"
        verbose_name_plural = "E-Mail-Vorlagen"
        ordering = ['template_type', 'name']

    def __str__(self):
        return f"{self.get_template_type_display()}"

    def render(self, context):
        """
        Rendert die E-Mail-Vorlage mit dem gegebenen Kontext

        Args:
            context (dict): Dictionary mit Platzhalter-Werten

        Returns:
            tuple: (subject, body) mit ersetzten Platzhaltern
        """
        subject = self.subject
        body = self.body

        # Ersetze Platzhalter
        for key, value in context.items():
            placeholder = "{{" + key + "}}"
            subject = subject.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))

        return subject, body


# ==================== BACKUP SYSTEM ====================

class LDAPBackup(models.Model):
    """
    Historie aller LDAP-Backups (LDIF-Exporte)
    Ermöglicht Tracking, Download und Restore
    """
    STATUS_CHOICES = [
        ('running', 'Läuft'),
        ('completed', 'Erfolgreich'),
        ('failed', 'Fehlgeschlagen'),
    ]

    BACKUP_TYPE_CHOICES = [
        ('full', 'Vollständig'),
        ('users', 'Nur Benutzer'),
        ('groups', 'Nur Gruppen'),
        ('domains', 'Nur Mail-Domains'),
    ]

    # Backup Metadaten
    backup_type = models.CharField(
        max_length=20,
        choices=BACKUP_TYPE_CHOICES,
        default='full',
        verbose_name="Backup-Typ"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='running',
        verbose_name="Status"
    )

    # Datei-Informationen
    filename = models.CharField(
        max_length=255,
        verbose_name="Dateiname",
        help_text="LDIF-Dateiname"
    )
    file_path = models.CharField(
        max_length=500,
        verbose_name="Dateipfad",
        help_text="Vollständiger Pfad zur Backup-Datei"
    )
    file_size = models.BigIntegerField(
        default=0,
        verbose_name="Dateigröße (Bytes)"
    )

    # Statistiken
    entry_count = models.IntegerField(
        default=0,
        verbose_name="Anzahl Einträge",
        help_text="Anzahl exportierter LDAP-Einträge"
    )
    user_count = models.IntegerField(
        default=0,
        verbose_name="Anzahl Benutzer"
    )
    group_count = models.IntegerField(
        default=0,
        verbose_name="Anzahl Gruppen"
    )
    domain_count = models.IntegerField(
        default=0,
        verbose_name="Anzahl Mail-Domains"
    )

    # Zeitstempel
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Abgeschlossen am"
    )

    # Benutzer der das Backup erstellt hat
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Erstellt von"
    )

    # Fehler-Informationen (bei failed)
    error_message = models.TextField(
        blank=True,
        verbose_name="Fehlermeldung"
    )

    # Notizen
    notes = models.TextField(
        blank=True,
        verbose_name="Notizen",
        help_text="Optionale Notizen zum Backup"
    )

    class Meta:
        verbose_name = "LDAP Backup"
        verbose_name_plural = "LDAP Backups"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['backup_type']),
        ]

    def __str__(self):
        return f"{self.get_backup_type_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    def get_file_size_mb(self):
        """Dateigröße in MB zurückgeben"""
        return round(self.file_size / (1024 * 1024), 2)

    def get_duration(self):
        """Backup-Dauer berechnen"""
        if self.completed_at and self.created_at:
            duration = self.completed_at - self.created_at
            return duration.total_seconds()
        return None

    def delete_file(self):
        """LDIF-Datei vom Dateisystem löschen"""
        import os
        if os.path.exists(self.file_path):
            try:
                os.remove(self.file_path)
                return True
            except Exception as e:
                return False
        return False

    @classmethod
    def cleanup_old_backups(cls, keep_count=10):
        """
        Alte Backups löschen, nur die neuesten n behalten

        Args:
            keep_count (int): Anzahl der zu behaltenden Backups

        Returns:
            int: Anzahl gelöschter Backups
        """
        # Hole alle Backups sortiert nach Erstelldatum (neueste zuerst)
        all_backups = cls.objects.filter(status='completed').order_by('-created_at')

        # Finde Backups die gelöscht werden sollen
        backups_to_delete = all_backups[keep_count:]

        deleted_count = 0
        for backup in backups_to_delete:
            # Lösche Datei
            backup.delete_file()
            # Lösche DB-Eintrag
            backup.delete()
            deleted_count += 1

        return deleted_count