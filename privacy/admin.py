from django.contrib import admin
from .models import PrivacyPolicy, LegalPage, ConsentLog, DeletionRequest


@admin.register(PrivacyPolicy)
class PrivacyPolicyAdmin(admin.ModelAdmin):
    list_display = ['title', 'version', 'is_active', 'updated_at']
    list_filter = ['is_active']


@admin.register(LegalPage)
class LegalPageAdmin(admin.ModelAdmin):
    list_display = ['title', 'page_type', 'updated_at']


@admin.register(ConsentLog)
class ConsentLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'consent_type', 'granted', 'policy_version', 'timestamp']
    list_filter = ['consent_type', 'granted']
    search_fields = ['user__username']
    readonly_fields = ['timestamp']


@admin.register(DeletionRequest)
class DeletionRequestAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'status', 'created_at', 'reviewed_by']
    list_filter = ['status']
    search_fields = ['username', 'email']
