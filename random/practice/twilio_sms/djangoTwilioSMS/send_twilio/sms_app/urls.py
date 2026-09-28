from django.urls import path
from . import views
from .views import *


urlpatterns = [
    path('send-sms', Send_sms_twilio.as_view(), name='send_sms'),
]