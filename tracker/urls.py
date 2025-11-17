from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('', views.index, name='index'),
    path('add/', views.add_planting_view, name='add_planting'),
    path('save_planting/', views.save_planting, name='save_planting'),
    path('delete/<int:planting_id>/', views.delete_planting, name='delete_planting'),

    # New URLs for editing
    path('edit/<int:planting_id>/', views.edit_planting_view, name='edit_planting'),
    path('update/<int:planting_id>/', views.update_planting, name='update_planting'),
    path('', views.index, name='index'),
]