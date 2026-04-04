from django.urls import path
from . import views

app_name = 'tickets'

urlpatterns = [
    path('', views.ticket_list, name='ticket_list'),
    path('new/', views.ticket_create, name='ticket_create'),
    path('<int:pk>/', views.ticket_detail, name='ticket_detail'),
    path('<int:pk>/comment/', views.ticket_comment, name='ticket_comment'),
    path('<int:pk>/status/', views.ticket_update_status, name='ticket_update_status'),
    path('<int:pk>/assign/', views.ticket_assign, name='ticket_assign'),
    path('<int:pk>/edit/', views.ticket_edit, name='ticket_edit'),
    path('<int:pk>/delete/', views.ticket_delete, name='ticket_delete'),
]
