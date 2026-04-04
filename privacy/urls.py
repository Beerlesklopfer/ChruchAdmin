from django.urls import path
from . import views

app_name = 'privacy'

urlpatterns = [
    path('', views.privacy_policy, name='privacy_policy'),
    path('impressum/', views.impressum, name='impressum'),
    path('seite/<str:page_type>/', views.legal_page, name='legal_page'),
    path('my-data/', views.my_data, name='my_data'),
    path('my-data/export/', views.export_my_data, name='export_my_data'),
    path('my-data/delete/', views.request_deletion, name='request_deletion'),
    path('consent/', views.consent_update, name='consent_update'),
]
