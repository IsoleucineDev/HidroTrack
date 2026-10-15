from django.conf import settings
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.BASE_DIR / "public" / "static"}),
    path("", include("simulador.urls")),
]
