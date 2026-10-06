from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Smart Shop Administration"
admin.site.site_title = "Smart Shop Admin"
admin.site.index_title = "Store management"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("shop.urls")),
]
if settings.DEBUG:
    urlpatterns += static("/media/", document_root=settings.MEDIA_ROOT)
