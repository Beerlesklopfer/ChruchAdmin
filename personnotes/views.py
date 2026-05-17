from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import Http404, HttpResponseForbidden
from django.db.models import Q

from authapp.views import is_ldap_admin, has_permission
from main.ldap_manager import LDAPManager

from .models import PersonNote, PersonNoteAccess


def _can_write_notes(user):
    """Berechtigt fuer beliebige Notizen (manage_notes oder Admin)."""
    return is_ldap_admin(user) or has_permission(user, 'manage_notes')


def _can_create_for(user, target_cn):
    """Notiz erstellen darf: Berechtigte (manage_notes) oder Betroffener selbst (ueber sich).
    Normale Benutzer koennen Notizen ueber sich selbst anlegen, aber NICHT spaeter editieren."""
    if not user.is_authenticated:
        return False
    if _can_write_notes(user):
        return True
    if user.username.lower() == target_cn.lower():
        return True
    return False


def _can_edit_note(user, note):
    """Editieren/Loeschen darf nur Admin oder (Autor MIT manage_notes-Permission).
    User, die nur ueber sich selbst geschrieben haben, koennen ihre Notiz nicht aendern
    (Journal-Charakter, audit-konformes Verhalten)."""
    if not user.is_authenticated:
        return False
    if is_ldap_admin(user):
        return True
    if note.author_id == user.id and _can_write_notes(user):
        return True
    return False


def _can_view_note(user, note):
    """Lesen darf: Autor, Berechtigte (manage_notes/admin), oder Betroffener selbst."""
    if not user.is_authenticated:
        return False
    if _can_write_notes(user):
        return True
    if note.author_id == user.id:
        return True
    if user.username.lower() == note.target_cn.lower():
        return True
    return False


def _client_ip(request):
    fwd = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if fwd:
        return fwd.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _log(request, note, action):
    PersonNoteAccess.objects.create(
        note=note,
        note_target_cn=note.target_cn,
        note_title=note.title,
        viewer=request.user if request.user.is_authenticated else None,
        action=action,
        ip_address=_client_ip(request),
    )


def _resolve_user_display(target_cn):
    """LDAP-Lookup fuer Anzeigename, fallback auf cn."""
    try:
        with LDAPManager() as m:
            u = m.get_user(target_cn)
            if u:
                attrs = u['attributes']
                given = attrs.get('givenName', '')
                sn = attrs.get('sn', '')
                if isinstance(given, list):
                    given = given[0] if given else ''
                if isinstance(sn, list):
                    sn = sn[0] if sn else ''
                if isinstance(given, bytes):
                    given = given.decode('utf-8', errors='replace')
                if isinstance(sn, bytes):
                    sn = sn.decode('utf-8', errors='replace')
                full = f'{given} {sn}'.strip()
                return full or target_cn
    except Exception:
        pass
    return target_cn


@login_required
def person_notes(request, target_cn):
    """Notizen-Liste fuer einen bestimmten Benutzer."""
    is_self = request.user.username.lower() == target_cn.lower()
    can_write = _can_write_notes(request.user)
    if not (can_write or is_self):
        return HttpResponseForbidden('Keine Berechtigung.')

    notes = PersonNote.objects.filter(target_cn__iexact=target_cn).select_related('author')
    return render(request, 'personnotes/list.html', {
        'target_cn': target_cn,
        'target_display': _resolve_user_display(target_cn),
        'notes': notes,
        'can_write': can_write,
        'is_self': is_self,
    })


@login_required
def note_detail(request, pk):
    """Einzelne Notiz lesen + Audit-Log Eintrag."""
    note = get_object_or_404(PersonNote, pk=pk)
    if not _can_view_note(request.user, note):
        return HttpResponseForbidden('Keine Berechtigung.')
    _log(request, note, 'view')
    return render(request, 'personnotes/detail.html', {
        'note': note,
        'target_display': _resolve_user_display(note.target_cn),
        'is_author': note.author_id == request.user.id,
        'can_write': _can_write_notes(request.user),
        'can_edit': _can_edit_note(request.user, note),
    })


@login_required
def note_create(request, target_cn):
    """Neue Notiz erstellen. Berechtigte oder Betroffener-ueber-sich-selbst."""
    if not _can_create_for(request.user, target_cn):
        return HttpResponseForbidden('Keine Berechtigung.')
    is_self_only = (request.user.username.lower() == target_cn.lower()) and not _can_write_notes(request.user)
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        if not title or not content:
            messages.error(request, 'Titel und Inhalt sind Pflichtfelder.')
        else:
            note = PersonNote(target_cn=target_cn, author=request.user, title=title)
            note.content = content
            note.save()
            _log(request, note, 'create')
            messages.success(request, 'Notiz angelegt.')
            if is_self_only:
                return redirect('personnotes:my_notes')
            return redirect('personnotes:list', target_cn=target_cn)
    return render(request, 'personnotes/edit.html', {
        'note': None,
        'target_cn': target_cn,
        'target_display': _resolve_user_display(target_cn),
        'is_self_only': is_self_only,
    })


@login_required
def note_edit(request, pk):
    """Notiz bearbeiten - nur Autor MIT manage_notes-Permission oder Admin.
    User, die ueber sich selbst geschrieben haben, koennen nicht editieren (Journal-Charakter)."""
    note = get_object_or_404(PersonNote, pk=pk)
    if not _can_edit_note(request.user, note):
        return HttpResponseForbidden('Notizen koennen nach dem Erstellen nicht mehr bearbeitet werden (nur Berechtigte mit manage_notes).')
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        if not title or not content:
            messages.error(request, 'Titel und Inhalt sind Pflichtfelder.')
        else:
            note.title = title
            note.content = content
            note.save()
            _log(request, note, 'update')
            messages.success(request, 'Notiz aktualisiert.')
            return redirect('personnotes:detail', pk=note.pk)
    return render(request, 'personnotes/edit.html', {
        'note': note,
        'target_cn': note.target_cn,
        'target_display': _resolve_user_display(note.target_cn),
        'plaintext': note.content,
    })


@login_required
def note_delete(request, pk):
    """Notiz loeschen - gleiche Regel wie Edit (nur Berechtigte oder Admin)."""
    note = get_object_or_404(PersonNote, pk=pk)
    if not _can_edit_note(request.user, note):
        return HttpResponseForbidden('Loeschen erfordert manage_notes-Permission.')
    if request.method == 'POST':
        target_cn = note.target_cn
        _log(request, note, 'delete')
        note.delete()
        messages.success(request, 'Notiz geloescht.')
        return redirect('personnotes:list', target_cn=target_cn)
    return redirect('personnotes:detail', pk=note.pk)


@login_required
def note_audit(request, pk):
    """Audit-Log einer Notiz: wer hat zugegriffen?
    Betroffener und Autor und Admins koennen einsehen."""
    note = get_object_or_404(PersonNote, pk=pk)
    if not _can_view_note(request.user, note):
        return HttpResponseForbidden('Keine Berechtigung.')
    accesses = note.access_log.select_related('viewer').all()
    return render(request, 'personnotes/audit.html', {
        'note': note,
        'accesses': accesses,
        'target_display': _resolve_user_display(note.target_cn),
    })


@login_required
def my_notes(request):
    """Eigene Sicht: Notizen ueber mich selbst + Zugriffshistorie."""
    target_cn = request.user.username
    notes = PersonNote.objects.filter(target_cn__iexact=target_cn).select_related('author')
    accesses = PersonNoteAccess.objects.filter(note_target_cn__iexact=target_cn).select_related('viewer')[:50]
    return render(request, 'personnotes/my_notes.html', {
        'target_cn': target_cn,
        'target_display': _resolve_user_display(target_cn),
        'notes': notes,
        'accesses': accesses,
    })


@login_required
def overview(request):
    """Admin: Uebersicht aller Notizen, gruppiert nach Betroffenem."""
    if not _can_write_notes(request.user):
        return HttpResponseForbidden('Keine Berechtigung.')
    q = request.GET.get('q', '').strip()
    notes = PersonNote.objects.all().select_related('author')
    if q:
        notes = notes.filter(Q(target_cn__icontains=q) | Q(title__icontains=q))
    # Gruppierung pro target_cn
    by_target = {}
    for n in notes:
        by_target.setdefault(n.target_cn, []).append(n)
    grouped = []
    for cn in sorted(by_target.keys(), key=str.lower):
        grouped.append({
            'target_cn': cn,
            'display': _resolve_user_display(cn),
            'notes': by_target[cn],
        })
    return render(request, 'personnotes/overview.html', {
        'grouped': grouped,
        'q': q,
        'total': sum(len(g['notes']) for g in grouped),
    })
