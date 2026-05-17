from django.conf import settings
from django.db import models

from .crypto import encrypt, decrypt


class PersonNote(models.Model):
    """Seelsorge-Notiz ueber einen LDAP-Benutzer. Inhalt AES-256-GCM verschluesselt.
    Pro Designentscheidung sieht der Betroffene seine eigenen Notizen unverschluesselt.
    """
    target_cn = models.CharField(
        max_length=120,
        db_index=True,
        verbose_name='Betroffener (LDAP-cn)',
        help_text='Benutzer, ueber den die Notiz geht',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='authored_notes',
        verbose_name='Autor',
    )
    title = models.CharField(max_length=200, verbose_name='Titel')
    _content_ciphertext = models.TextField(
        db_column='content_ciphertext',
        verbose_name='Inhalt (verschluesselt)',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Seelsorge-Notiz'
        verbose_name_plural = 'Seelsorge-Notizen'
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.target_cn}: {self.title}'

    @property
    def content(self) -> str:
        return decrypt(self._content_ciphertext) if self._content_ciphertext else ''

    @content.setter
    def content(self, value: str):
        self._content_ciphertext = encrypt(value or '')


class PersonNoteAccess(models.Model):
    """Audit-Log fuer Zugriffe auf Seelsorge-Notizen.
    Pflicht zur Nachvollziehbarkeit (Betroffener kann seine Zugriffshistorie einsehen).
    """
    ACTION_CHOICES = [
        ('view', 'Angesehen'),
        ('create', 'Erstellt'),
        ('update', 'Bearbeitet'),
        ('delete', 'Geloescht'),
    ]
    note = models.ForeignKey(
        PersonNote,
        on_delete=models.SET_NULL,
        null=True,
        related_name='access_log',
    )
    note_target_cn = models.CharField(max_length=120, db_index=True,
        help_text='Wird redundant gespeichert, damit Audit nach Loeschen erhalten bleibt')
    note_title = models.CharField(max_length=200, blank=True)
    viewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='note_accesses',
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Zugriffs-Eintrag'
        verbose_name_plural = 'Zugriffs-Eintraege'
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.timestamp:%Y-%m-%d %H:%M} {self.viewer} {self.action} {self.note_target_cn}'
