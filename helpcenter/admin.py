from django.contrib import admin
from .models import HelpArticle


@admin.register(HelpArticle)
class HelpArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'order', 'is_published', 'updated_at')
    list_filter = ('category', 'is_published')
    search_fields = ('title', 'summary', 'content_html')
    prepopulated_fields = {'slug': ('title',)}
