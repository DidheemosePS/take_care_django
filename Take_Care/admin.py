from django.contrib import admin
from .models import Post, Saved, Interested

# Register your models here.

admin.site.register(Post)
admin.site.register(Saved)
admin.site.register(Interested)
