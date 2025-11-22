from django.contrib import admin
from django.urls import path, include
from tracker import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),  # If you have a custom login view; otherwise, see below.
    path('', views.index, name='index'),
    # ... your other patterns ...
    path('profile/', views.profile, name='profile'),
    # Django auth URLs
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('tracker.urls')),
    # Cognito Hosted UI endpoints
    path('auth/login/', views.cognito_login, name='cognito_login'),
    path('auth/callback/', views.cognito_callback, name='cognito_callback'),
    path('auth/logout/', views.cognito_logout, name='cognito_logout'),
    # Custom logout that clears Cognito tokens (overrides Django's default logout)
    path('accounts/logout/', views.cognito_logout, name='logout'),
    # removed cognito_auth in favor of `tracker` app
]