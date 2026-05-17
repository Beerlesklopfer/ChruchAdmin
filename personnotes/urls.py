from django.urls import path
from . import views

app_name = 'personnotes'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('mich/', views.my_notes, name='my_notes'),
    path('person/<str:target_cn>/', views.person_notes, name='list'),
    path('person/<str:target_cn>/neu/', views.note_create, name='create'),
    path('<int:pk>/', views.note_detail, name='detail'),
    path('<int:pk>/bearbeiten/', views.note_edit, name='edit'),
    path('<int:pk>/loeschen/', views.note_delete, name='delete'),
    path('<int:pk>/audit/', views.note_audit, name='audit'),
]
