from email.headerregistry import Group
from django.contrib import admin
from .models import *
from django.contrib.auth.models import *

@admin.register(registration_details)
class PersonAdmin(admin.ModelAdmin):
    pass

@admin.register(clusterNum)
class CourseAdmin(admin.ModelAdmin):
    pass

@admin.register(user_answers)
class GradeAdmin(admin.ModelAdmin):
    pass
admin.site.unregister(Group)
admin.site.site_header  =  "All Seeing Chamber"  
admin.site.site_title  =  "admin site"
admin.site.index_title  =  "Predicto's Lobby"