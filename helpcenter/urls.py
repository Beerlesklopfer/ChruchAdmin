from django.urls import path
from . import views

app_name = 'helpcenter'

urlpatterns = [
    path('', views.index, name='index'),
    path('admin/', views.admin_list, name='admin_list'),
    path('admin/create/', views.admin_edit, name='admin_create'),
    path('admin/<int:pk>/edit/', views.admin_edit, name='admin_edit'),
    path('admin/<int:pk>/delete/', views.admin_delete, name='admin_delete'),
    path('<slug:slug>/', views.detail, name='detail'),
]
