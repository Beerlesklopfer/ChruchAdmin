from django.db import models
from django.utils.text import slugify


class HelpArticle(models.Model):
    CATEGORY_CHOICES = [
        ('general', 'Allgemein'),
        ('mail', 'E-Mail'),
        ('account', 'Konto & Profil'),
        ('devices', 'Geraete-Einrichtung'),
        ('privacy', 'Datenschutz'),
        ('admin', 'Administration'),
    ]

    slug = models.SlugField(max_length=120, unique=True, help_text='URL-Pfad, z.B. "mail-routing"')
    title = models.CharField(max_length=200, verbose_name='Titel')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general', verbose_name='Kategorie')
    summary = models.CharField(max_length=300, blank=True, verbose_name='Kurzfassung', help_text='Wird in der Index-Liste angezeigt')
    content_html = models.TextField(verbose_name='Inhalt (HTML)')
    order = models.IntegerField(default=0, verbose_name='Reihenfolge')
    is_published = models.BooleanField(default=True, verbose_name='Veroeffentlicht')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Hilfe-Artikel'
        verbose_name_plural = 'Hilfe-Artikel'
        ordering = ['category', 'order', 'title']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:120]
        super().save(*args, **kwargs)
