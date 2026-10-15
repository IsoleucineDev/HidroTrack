from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/simular", views.simular, name="simular"),
    path("api/salud", views.salud, name="salud"),
]
