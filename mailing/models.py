from django.db import models
from django.contrib.auth.models import User


class MailCampaign(models.Model):
    """Eine Massen-E-Mail-Kampagne (Gemeindebrief, Ankuendigung, etc.)"""
    STATUS_CHOICES = [
        ('draft', 'Entwurf'),
        ('sending', 'Wird versendet'),
        ('sent', 'Versendet'),
        ('failed', 'Fehlgeschlagen'),
    ]

    RECIPIENT_CHOICES = [
        ('all', 'Alle Benutzer'),
        ('members', 'Mitglieder'),
        ('family', 'Angehoerige'),
        ('visitors', 'Besucher'),
        ('guests', 'Gaeste'),
        ('groups', 'Bestimmte Gruppen'),
        ('manual', 'Manuelle Auswahl'),
    ]

    subject = models.CharField('Betreff', max_length=255)
    body_html = models.TextField('Inhalt (HTML)')
    body_text = models.TextField('Inhalt (Text)', blank=True,
        help_text='Wird automatisch aus HTML generiert, kann aber manuell angepasst werden.')

    recipient_type = models.CharField('Empfaenger-Typ', max_length=20,
        choices=RECIPIENT_CHOICES, default='members')
    recipient_groups = models.TextField('Gruppen', blank=True,
        help_text='Komma-getrennte LDAP-Gruppennamen (nur bei Typ "Bestimmte Gruppen")')
    recipient_emails_manual = models.TextField('Manuelle Empfaenger', blank=True,
        help_text='Eine E-Mail-Adresse pro Zeile (nur bei Typ "Manuelle Auswahl")')

    footer_html = models.TextField('Footer (HTML)', blank=True, default='')

    from_name = models.CharField('Absender-Name', max_length=100,
        default='Beispielgemeinde')
    reply_to = models.EmailField('Antwort-an', blank=True)

    status = models.CharField('Status', max_length=20,
        choices=STATUS_CHOICES, default='draft')

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL,
        null=True, related_name='mail_campaigns', verbose_name='Erstellt von')
    created_at = models.DateTimeField('Erstellt am', auto_now_add=True)
    updated_at = models.DateTimeField('Aktualisiert am', auto_now=True)
    sent_at = models.DateTimeField('Versendet am', null=True, blank=True)

    total_recipients = models.IntegerField('Empfaenger gesamt', default=0)
    successful_count = models.IntegerField('Erfolgreich', default=0)
    failed_count = models.IntegerField('Fehlgeschlagen', default=0)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Mail-Kampagne'
        verbose_name_plural = 'Mail-Kampagnen'

    def __str__(self):
        return f'{self.subject} ({self.get_status_display()})'


class MailLog(models.Model):
    """Protokoll fuer jeden einzelnen E-Mail-Versand"""
    STATUS_CHOICES = [
        ('pending', 'Ausstehend'),
        ('sent', 'Zugestellt'),
        ('failed', 'Fehlgeschlagen'),
    ]

    campaign = models.ForeignKey(MailCampaign, on_delete=models.CASCADE,
        related_name='logs', verbose_name='Kampagne')
    recipient_email = models.EmailField('Empfaenger')
    recipient_name = models.CharField('Name', max_length=200, blank=True)
    status = models.CharField('Status', max_length=20,
        choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField('Fehlermeldung', blank=True)
    sent_at = models.DateTimeField('Gesendet am', null=True, blank=True)

    class Meta:
        ordering = ['-sent_at']
        verbose_name = 'Mail-Protokoll'
        verbose_name_plural = 'Mail-Protokolle'

    def __str__(self):
        return f'{self.recipient_email} - {self.get_status_display()}'


class MailTemplate(models.Model):
    """Wiederverwendbare E-Mail-Vorlagen"""
    name = models.CharField('Name', max_length=100)
    subject = models.CharField('Betreff', max_length=255)
    body_html = models.TextField('Inhalt (HTML)')
    description = models.TextField('Beschreibung', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL,
        null=True, verbose_name='Erstellt von')
    created_at = models.DateTimeField('Erstellt am', auto_now_add=True)
    updated_at = models.DateTimeField('Aktualisiert am', auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Mail-Vorlage'
        verbose_name_plural = 'Mail-Vorlagen'

    def __str__(self):
        return self.name
