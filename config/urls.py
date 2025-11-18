from django.contrib import admin
from django.urls import path, include

from core.views import health

urlpatterns = [
    path('', include('tracker.urls')),      # site root -> tracker app
    path('accounts/', include('django.contrib.auth.urls')),  # built-in auth URLs (password reset, etc)
    path('admin/', admin.site.urls),
    path('health', health, name='health'),
]