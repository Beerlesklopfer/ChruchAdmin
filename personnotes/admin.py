from django.contrib import admin
from .models import PersonNote, PersonNoteAccess


@admin.register(PersonNote)
class PersonNoteAdmin(admin.ModelAdmin):
    list_display = ('target_cn', 'title', 'author', 'updated_at')
    list_filter = ('author',)
    search_fields = ('target_cn', 'title')
    readonly_fields = ('_content_ciphertext', 'created_at', 'updated_at')


@admin.register(PersonNoteAccess)
class PersonNoteAccessAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'viewer', 'action', 'note_target_cn', 'note_title', 'ip_address')
    list_filter = ('action',)
    search_fields = ('note_target_cn', 'note_title', 'viewer__username')
    date_hierarchy = 'timestamp'
    readonly_fields = [f.name for f in PersonNoteAccess._meta.fields]
