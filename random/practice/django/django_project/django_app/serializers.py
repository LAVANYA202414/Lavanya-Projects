from rest_framework import serializers
from django.contrib.auth import get_user_model

user = get_user_model()

class UserSignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only = True)