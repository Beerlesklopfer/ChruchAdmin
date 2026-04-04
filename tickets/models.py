from django.db import models
from django.contrib.auth.models import User


class Ticket(models.Model):
    TYPE_CHOICES = [
        ('bug', 'Fehlermeldung'),
        ('feature', 'Funktionswunsch'),
        ('task', 'Aufgabe'),
        ('question', 'Frage'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Niedrig'),
        ('medium', 'Mittel'),
        ('high', 'Hoch'),
        ('critical', 'Kritisch'),
    ]

    STATUS_CHOICES = [
        ('open', 'Offen'),
        ('in_progress', 'In Bearbeitung'),
        ('waiting', 'Wartet'),
        ('resolved', 'Geloest'),
        ('closed', 'Geschlossen'),
    ]

    title = models.CharField('Titel', max_length=255)
    description = models.TextField('Beschreibung')
    ticket_type = models.CharField('Typ', max_length=20, choices=TYPE_CHOICES, default='bug')
    priority = models.CharField('Prioritaet', max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='open')

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL,
        null=True, related_name='created_tickets', verbose_name='Erstellt von')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_tickets', verbose_name='Zugewiesen an')

    created_at = models.DateTimeField('Erstellt am', auto_now_add=True)
    updated_at = models.DateTimeField('Aktualisiert am', auto_now=True)
    resolved_at = models.DateTimeField('Geloest am', null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Ticket'
        verbose_name_plural = 'Tickets'

    def __str__(self):
        return f'#{self.pk} {self.title}'

    @property
    def type_icon(self):
        icons = {'bug': 'bi-bug', 'feature': 'bi-lightbulb', 'task': 'bi-check2-square', 'question': 'bi-question-circle'}
        return icons.get(self.ticket_type, 'bi-ticket')

    @property
    def priority_color(self):
        colors = {'low': 'secondary', 'medium': 'info', 'high': 'warning', 'critical': 'danger'}
        return colors.get(self.priority, 'secondary')

    @property
    def status_color(self):
        colors = {'open': 'primary', 'in_progress': 'warning', 'waiting': 'info', 'resolved': 'success', 'closed': 'secondary'}
        return colors.get(self.status, 'secondary')


class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE,
        related_name='comments', verbose_name='Ticket')
    author = models.ForeignKey(User, on_delete=models.SET_NULL,
        null=True, verbose_name='Autor')
    content = models.TextField('Kommentar')
    created_at = models.DateTimeField('Erstellt am', auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Kommentar'
        verbose_name_plural = 'Kommentare'

    def __str__(self):
        return f'Kommentar von {self.author} zu #{self.ticket.pk}'
