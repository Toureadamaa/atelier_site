from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("vhod/", auth_views.LoginView.as_view(template_name="atelier/login.html"), name="login"),
    path("vyhod/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("atelier.urls")),
]
