from django.contrib import admin
from .models import MailCampaign, MailLog, MailTemplate


@admin.register(MailCampaign)
class MailCampaignAdmin(admin.ModelAdmin):
    list_display = ['subject', 'recipient_type', 'status', 'total_recipients',
                    'successful_count', 'failed_count', 'created_by', 'created_at', 'sent_at']
    list_filter = ['status', 'recipient_type', 'created_at']
    search_fields = ['subject', 'body_text']
    readonly_fields = ['created_at', 'updated_at', 'sent_at', 'total_recipients',
                       'successful_count', 'failed_count']


@admin.register(MailLog)
class MailLogAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'recipient_email', 'recipient_name', 'status', 'sent_at']
    list_filter = ['status', 'sent_at']
    search_fields = ['recipient_email', 'recipient_name']
    readonly_fields = ['sent_at']


@admin.register(MailTemplate)
class MailTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'subject', 'created_by', 'updated_at']
    search_fields = ['name', 'subject']
