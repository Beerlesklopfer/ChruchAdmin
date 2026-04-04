from django.db import models
from django.contrib.auth.models import User


class PrivacyPolicy(models.Model):
    """Datenschutzerklaerung - versioniert und editierbar im Admin"""
    version = models.CharField('Version', max_length=20)
    title = models.CharField('Titel', max_length=200,
        default='Datenschutzerklaerung der Beispielgemeinde')
    content_html = models.TextField('Inhalt (HTML)')
    is_active = models.BooleanField('Aktiv', default=False,
        help_text='Nur eine Version kann aktiv sein')
    created_at = models.DateTimeField('Erstellt am', auto_now_add=True)
    updated_at = models.DateTimeField('Aktualisiert am', auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Datenschutzerklaerung'
        verbose_name_plural = 'Datenschutzerklaerungen'

    def __str__(self):
        return f'{self.title} (v{self.version}){"  [AKTIV]" if self.is_active else ""}'

    def save(self, *args, **kwargs):
        # Nur eine Version aktiv
        if self.is_active:
            PrivacyPolicy.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_active(cls):
        return cls.objects.filter(is_active=True).first()


class LegalPage(models.Model):
    """Rechtliche Seiten (Impressum, Nutzungsbedingungen, etc.) - editierbar im Admin"""
    PAGE_CHOICES = [
        ('impressum', 'Impressum'),
        ('nutzungsbedingungen', 'Nutzungsbedingungen'),
    ]

    page_type = models.CharField('Seitentyp', max_length=50, choices=PAGE_CHOICES, unique=True)
    title = models.CharField('Titel', max_length=200)
    content_html = models.TextField('Inhalt (HTML)')
    updated_at = models.DateTimeField('Aktualisiert am', auto_now=True)

    class Meta:
        verbose_name = 'Rechtliche Seite'
        verbose_name_plural = 'Rechtliche Seiten'

    def __str__(self):
        return self.title

    @classmethod
    def get_page(cls, page_type):
        return cls.objects.filter(page_type=page_type).first()


class ConsentLog(models.Model):
    """Protokoll der Einwilligungen pro Benutzer"""
    CONSENT_TYPES = [
        ('privacy_policy', 'Datenschutzerklaerung'),
        ('data_processing', 'Datenverarbeitung'),
        ('email_communication', 'E-Mail-Kommunikation'),
        ('member_list', 'Gemeindeliste (Name, Kontaktdaten sichtbar fuer Mitglieder)'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE,
        related_name='consents', verbose_name='Benutzer')
    consent_type = models.CharField('Art der Einwilligung', max_length=50,
        choices=CONSENT_TYPES)
    policy_version = models.CharField('Version', max_length=20, blank=True)
    granted = models.BooleanField('Erteilt', default=True)
    ip_address = models.GenericIPAddressField('IP-Adresse', null=True, blank=True)
    timestamp = models.DateTimeField('Zeitpunkt', auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Einwilligung'
        verbose_name_plural = 'Einwilligungen'

    def __str__(self):
        status = 'erteilt' if self.granted else 'widerrufen'
        return f'{self.user.username} - {self.get_consent_type_display()} ({status})'


class DeletionRequest(models.Model):
    """Antrag auf Loeschung (Recht auf Vergessenwerden)"""
    STATUS_CHOICES = [
        ('pending', 'Ausstehend'),
        ('approved', 'Genehmigt'),
        ('completed', 'Abgeschlossen'),
        ('rejected', 'Abgelehnt'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL,
        null=True, related_name='deletion_requests', verbose_name='Benutzer')
    username = models.CharField('Benutzername', max_length=150)
    email = models.EmailField('E-Mail')
    reason = models.TextField('Begruendung', blank=True)
    status = models.CharField('Status', max_length=20,
        choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_deletions',
        verbose_name='Bearbeitet von')
    reviewed_at = models.DateTimeField('Bearbeitet am', null=True, blank=True)
    created_at = models.DateTimeField('Erstellt am', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Loeschantrag'
        verbose_name_plural = 'Loeschantraege'

    def __str__(self):
        return f'{self.username} - {self.get_status_display()}'
