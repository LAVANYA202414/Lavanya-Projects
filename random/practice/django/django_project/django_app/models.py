from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    name = models.CharField(max_length = 200)
    email = models.EmailField(unique = True)
    phone_number = models.IntegerField(blank = True, null = True)
    birth_date = models.DateField(blank = True, null = True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username","name"]

    def __str__(self):
        return self.email