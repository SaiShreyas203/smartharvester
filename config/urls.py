from django.contrib import admin
from django.urls import path, include

# Import the health view from core
from core.views import health

urlpatterns = [
    path('', include('tracker.urls')),      # site root -> tracker app
    path('accounts/', include('django.contrib.auth.urls')),  # <-- add this line
    path('admin/', admin.site.urls),
    path('health', health, name='health'),
]