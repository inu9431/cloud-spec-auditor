from django.conf import settings 
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # API 엔드포인트
    path('api/users/', include('apps.users.urls')),
    path('api/costs/', include('apps.costs.urls')),
    path('api/inventories/', include('apps.inventories.urls')),
    path('api/recommendations/', include('apps.recommendations.urls')),

    # Swagger 문서
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api//docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc')
]

# debug Toolbar
if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]