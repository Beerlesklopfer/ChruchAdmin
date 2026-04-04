from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from .models import Ticket, TicketComment


@login_required
def ticket_list(request):
    """Uebersicht aller Tickets"""
    tickets = Ticket.objects.all()

    # Filter
    ticket_type = request.GET.get('type')
    status = request.GET.get('status')
    mine = request.GET.get('mine')

    if ticket_type:
        tickets = tickets.filter(ticket_type=ticket_type)
    if status:
        tickets = tickets.filter(status=status)
    if mine:
        tickets = tickets.filter(created_by=request.user)

    # Statistiken
    stats = {
        'total': Ticket.objects.count(),
        'open': Ticket.objects.filter(status='open').count(),
        'in_progress': Ticket.objects.filter(status='in_progress').count(),
        'bugs_open': Ticket.objects.filter(ticket_type='bug', status__in=['open', 'in_progress']).count(),
    }

    return render(request, 'tickets/ticket_list.html', {
        'tickets': tickets,
        'stats': stats,
        'current_type': ticket_type,
        'current_status': status,
    })


@login_required
def ticket_create(request):
    """Neues Ticket erstellen"""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        ticket_type = request.POST.get('ticket_type', 'bug')
        priority = request.POST.get('priority', 'medium')

        if not title:
            messages.error(request, 'Bitte geben Sie einen Titel ein.')
            return render(request, 'tickets/ticket_create.html')

        ticket = Ticket.objects.create(
            title=title,
            description=description,
            ticket_type=ticket_type,
            priority=priority,
            created_by=request.user,
        )
        messages.success(request, f'Ticket #{ticket.pk} erstellt.')
        return redirect('tickets:ticket_detail', pk=ticket.pk)

    return render(request, 'tickets/ticket_create.html')


@login_required
def ticket_detail(request, pk):
    """Ticket-Details mit Kommentaren"""
    ticket = get_object_or_404(Ticket, pk=pk)
    comments = ticket.comments.all()

    return render(request, 'tickets/ticket_detail.html', {
        'ticket': ticket,
        'comments': comments,
    })


@login_required
@require_http_methods(["POST"])
def ticket_comment(request, pk):
    """Kommentar hinzufuegen"""
    ticket = get_object_or_404(Ticket, pk=pk)
    content = request.POST.get('content', '').strip()

    if content:
        TicketComment.objects.create(
            ticket=ticket,
            author=request.user,
            content=content,
        )
        messages.success(request, 'Kommentar hinzugefuegt.')

    return redirect('tickets:ticket_detail', pk=pk)


@login_required
@require_http_methods(["POST"])
def ticket_update_status(request, pk):
    """Status aendern"""
    ticket = get_object_or_404(Ticket, pk=pk)
    new_status = request.POST.get('status')

    if new_status in dict(Ticket.STATUS_CHOICES):
        old_status = ticket.get_status_display()
        ticket.status = new_status
        if new_status == 'resolved':
            ticket.resolved_at = timezone.now()
        ticket.save()

        TicketComment.objects.create(
            ticket=ticket,
            author=request.user,
            content=f'Status geaendert: {old_status} → {ticket.get_status_display()}',
        )
        messages.success(request, f'Status auf "{ticket.get_status_display()}" geaendert.')

    return redirect('tickets:ticket_detail', pk=pk)


@login_required
@require_http_methods(["POST"])
def ticket_assign(request, pk):
    """Ticket zuweisen"""
    ticket = get_object_or_404(Ticket, pk=pk)
    action = request.POST.get('action')

    if action == 'me':
        ticket.assigned_to = request.user
        ticket.save()
        TicketComment.objects.create(
            ticket=ticket, author=request.user,
            content=f'Ticket uebernommen von {request.user.get_full_name() or request.user.username}',
        )
        messages.success(request, 'Ticket uebernommen.')
    elif action == 'unassign':
        ticket.assigned_to = None
        ticket.save()
        messages.success(request, 'Zuweisung entfernt.')

    return redirect('tickets:ticket_detail', pk=pk)


@login_required
@require_http_methods(["POST"])
def ticket_edit(request, pk):
    """Ticket bearbeiten"""
    ticket = get_object_or_404(Ticket, pk=pk)

    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    ticket_type = request.POST.get('ticket_type', ticket.ticket_type)
    priority = request.POST.get('priority', ticket.priority)

    if title:
        ticket.title = title
    if description:
        ticket.description = description
    ticket.ticket_type = ticket_type
    ticket.priority = priority
    ticket.save()

    messages.success(request, 'Ticket aktualisiert.')
    return redirect('tickets:ticket_detail', pk=pk)


@login_required
@require_http_methods(["POST"])
def ticket_delete(request, pk):
    """Ticket loeschen (nur Ersteller oder Admin)"""
    ticket = get_object_or_404(Ticket, pk=pk)
    if ticket.created_by == request.user or request.user.is_superuser:
        ticket.delete()
        messages.success(request, 'Ticket geloescht.')
    else:
        messages.error(request, 'Nur der Ersteller oder ein Admin kann Tickets loeschen.')
    return redirect('tickets:ticket_list')
