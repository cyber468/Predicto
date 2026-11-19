from django.contrib import admin
from django.urls import path

from Personality import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.login, name="login"),
    path('personality/register', views.register, name="register"),
    path('personality/question', views.question, name="question"),
    path('personality/result', views.result, name="result"),
    path('personality/logout', views.logout, name="logout"),
]
