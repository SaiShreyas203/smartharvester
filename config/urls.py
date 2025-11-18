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
]