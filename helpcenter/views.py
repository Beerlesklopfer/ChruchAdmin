from collections import OrderedDict

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils.text import slugify

from authapp.views import is_ldap_admin
from .models import HelpArticle


ADMIN_ONLY_CATEGORIES = {'admin'}


@login_required
def index(request):
    """Hilfe-Index: alle veroeffentlichten Artikel nach Kategorie gruppiert.
    Admin-Kategorie ist nur fuer Admins sichtbar."""
    is_admin = is_ldap_admin(request.user)
    qs = HelpArticle.objects.filter(is_published=True)
    if not is_admin:
        qs = qs.exclude(category__in=ADMIN_ONLY_CATEGORIES)
    articles = qs.order_by('category', 'order', 'title')
    cat_dict = OrderedDict()
    for key, label in HelpArticle.CATEGORY_CHOICES:
        if key in ADMIN_ONLY_CATEGORIES and not is_admin:
            continue
        cat_dict[key] = {'label': label, 'articles': []}
    for art in articles:
        cat_dict.setdefault(art.category, {'label': art.category, 'articles': []})['articles'].append(art)
    cat_list = [c for c in cat_dict.values() if c['articles']]
    return render(request, 'helpcenter/index.html', {'categories': cat_list})


@login_required
def detail(request, slug):
    """Einzelner Hilfe-Artikel. Admin-Kategorie nur fuer Admins."""
    article = get_object_or_404(HelpArticle, slug=slug, is_published=True)
    if article.category in ADMIN_ONLY_CATEGORIES and not is_ldap_admin(request.user):
        from django.http import Http404
        raise Http404('Artikel nicht gefunden.')
    related = HelpArticle.objects.filter(category=article.category, is_published=True).exclude(pk=article.pk).order_by('order', 'title')[:5]
    return render(request, 'helpcenter/detail.html', {'article': article, 'related': related})


@login_required
@user_passes_test(is_ldap_admin)
def admin_list(request):
    """Admin: alle Artikel (auch unveroeffentlichte) verwalten."""
    articles = HelpArticle.objects.all().order_by('category', 'order', 'title')
    return render(request, 'helpcenter/admin_list.html', {'articles': articles})


@login_required
@user_passes_test(is_ldap_admin)
def admin_edit(request, pk=None):
    """Admin: Artikel erstellen/bearbeiten."""
    article = None
    if pk:
        article = get_object_or_404(HelpArticle, pk=pk)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        slug = request.POST.get('slug', '').strip() or slugify(title)[:120]
        category = request.POST.get('category', 'general')
        summary = request.POST.get('summary', '').strip()
        content_html = request.POST.get('content_html', '')
        try:
            order = int(request.POST.get('order', '0') or 0)
        except ValueError:
            order = 0
        is_published = request.POST.get('is_published') == 'on'

        if not title or not content_html:
            messages.error(request, 'Titel und Inhalt sind Pflichtfelder.')
        else:
            if article:
                article.title = title
                article.slug = slug
                article.category = category
                article.summary = summary
                article.content_html = content_html
                article.order = order
                article.is_published = is_published
                article.save()
                messages.success(request, f'Artikel "{title}" wurde aktualisiert.')
            else:
                if HelpArticle.objects.filter(slug=slug).exists():
                    messages.error(request, f'Slug "{slug}" existiert bereits.')
                    return render(request, 'helpcenter/admin_edit.html', {
                        'article': article, 'categories': HelpArticle.CATEGORY_CHOICES,
                        'form_data': request.POST,
                    })
                HelpArticle.objects.create(
                    title=title, slug=slug, category=category, summary=summary,
                    content_html=content_html, order=order, is_published=is_published,
                )
                messages.success(request, f'Artikel "{title}" wurde erstellt.')
            return redirect('helpcenter:admin_list')

    return render(request, 'helpcenter/admin_edit.html', {
        'article': article,
        'categories': HelpArticle.CATEGORY_CHOICES,
    })


@login_required
@user_passes_test(is_ldap_admin)
def admin_delete(request, pk):
    """Admin: Artikel loeschen."""
    article = get_object_or_404(HelpArticle, pk=pk)
    if request.method == 'POST':
        title = article.title
        article.delete()
        messages.success(request, f'Artikel "{title}" wurde geloescht.')
    return redirect('helpcenter:admin_list')
