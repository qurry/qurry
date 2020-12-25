from django.urls import path, include

from .views import register, activate, UserView

urlpatterns = [
    path('', include('django.contrib.auth.urls')),
    path('register/', register, name='register'),
    path('activate/<str:uidb64>/<str:token>/',
         activate, name='activate-account'),

    path('users/', UserView.as_view(), name='view-users'),
    path('users/<str:id>/', UserView.as_view(), name='view-user-details'),

    path('profile/', UserView.as_view(mode='profile'), name='view-own-profile'),
]
