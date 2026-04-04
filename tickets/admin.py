from django.contrib import admin
from .models import Ticket, TicketComment


class TicketCommentInline(admin.TabularInline):
    model = TicketComment
    extra = 0


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'ticket_type', 'priority', 'status', 'created_by', 'assigned_to', 'created_at']
    list_filter = ['ticket_type', 'priority', 'status']
    search_fields = ['title', 'description']
    inlines = [TicketCommentInline]
