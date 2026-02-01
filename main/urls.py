from django.urls import path
from django.contrib import admin
from authapp import views as auth_views
from authapp import export_views
from authapp import permissions_views
from authapp import password_reset_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', auth_views.home, name='home'),
    path('login/', auth_views.ldap_login, name='login'),
    path('logout/', auth_views.custom_logout, name='logout'),
    path('register/', auth_views.register, name='register'),
    path('profile/', auth_views.profile, name='profile'),

    # LDAP URLs
    path('ldap/', auth_views.ldap_dashboard, name='ldap_dashboard'),
    path('ldap/admin/', auth_views.ldap_admin, name='ldap_admin'),
    path('ldap/users/', auth_views.ldap_user_search, name='ldap_user_search'),

    # Family Management URLs
    path('ldap/family-tree/', auth_views.family_tree, name='family_tree'),
    path('ldap/family/create/', auth_views.family_create, name='family_create'),
    path('ldap/family/<str:parent_cn>/add-member/', auth_views.family_add_member, name='family_add_member'),
    path('ldap/user/<str:cn>/edit/', auth_views.user_edit, name='user_edit'),
    path('ldap/user/create/', auth_views.user_create, name='user_create'),

    # Member List Export URLs
    path('ldap/export/', export_views.member_list_export, name='member_list_export'),
    path('ldap/export/pdf/', export_views.member_list_export_pdf, name='member_list_export_pdf'),
    path('ldap/export/pdf/<int:settings_id>/', export_views.member_list_export_pdf, name='member_list_export_pdf_settings'),
    path('ldap/export/vcard/', export_views.member_list_export_vcard, name='member_list_export_vcard'),
    path('ldap/export/vcard/<int:settings_id>/', export_views.member_list_export_vcard, name='member_list_export_vcard_settings'),
    path('ldap/export/settings/', export_views.member_list_export_settings, name='member_list_export_settings'),

    # Permissions Management URLs
    path('ldap/permissions/', permissions_views.permissions_overview, name='permissions_overview'),
    path('ldap/permissions/matrix/', permissions_views.permissions_matrix, name='permissions_matrix'),
    path('ldap/permissions/matrix/edit/', permissions_views.permissions_matrix_edit, name='permissions_matrix_edit'),
    path('ldap/my-permissions/', permissions_views.my_permissions, name='my_permissions'),

    # Password Reset URLs
    path('password-reset/', password_reset_views.password_reset_request, name='password_reset_request'),
    path('password-reset/confirm/<str:token>/', password_reset_views.password_reset_confirm, name='password_reset_confirm'),

    # Group Management URLs
    path('ldap/groups/', auth_views.group_list, name='group_list'),
    path('ldap/groups/<str:group_cn>/', auth_views.group_detail, name='group_detail'),
    path('ldap/groups/<str:group_cn>/add-member/', auth_views.group_add_member, name='group_add_member'),
    path('ldap/groups/<str:group_cn>/remove-member/', auth_views.group_remove_member, name='group_remove_member'),

    # Member Management URLs
    path('ldap/member/add/', auth_views.member_add, name='member_add'),
    path('ldap/member/add-existing/', auth_views.member_add_existing, name='member_add_existing'),
]