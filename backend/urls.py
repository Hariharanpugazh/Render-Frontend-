# main urls.py

from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("",include('coding.urls')),
    # path("",include('contest_details.urls')),
    # path("",include('problems.urls')),
    # path("",include('manualProblems.urls')),
    path("",include('staff.urls')),
    path('api/staff/', include('staff.urls')),
    path('api/student/', include('student.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('staff/', include('staff.urls')),
    path('api/mcq/', include('mcq_platform.urls')),
]
