from django.urls import path
from . import views

app_name = 'mailing'

urlpatterns = [
    # Kampagnen
    path('', views.campaign_list, name='campaign_list'),
    path('compose/', views.campaign_compose, name='campaign_compose'),
    path('<int:pk>/edit/', views.campaign_compose, name='campaign_edit'),
    path('<int:pk>/', views.campaign_detail, name='campaign_detail'),
    path('<int:pk>/preview/', views.campaign_preview, name='campaign_preview'),
    path('<int:pk>/test/', views.campaign_test, name='campaign_test'),
    path('<int:pk>/send/', views.campaign_send, name='campaign_send'),
    path('<int:pk>/delete/', views.campaign_delete, name='campaign_delete'),
    path('<int:pk>/duplicate/', views.campaign_duplicate, name='campaign_duplicate'),

    # Vorlagen
    path('templates/', views.template_list, name='template_list'),
    path('templates/new/', views.template_edit, name='template_create'),
    path('templates/<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('templates/<int:pk>/delete/', views.template_delete, name='template_delete'),
    path('templates/<int:pk>/load/', views.template_load, name='template_load'),
]
