from django.db import models

# Create your models here.

class MyArray(models.Model):
    data=models.TextField(null=True)
    status=models.IntegerField(default=False)
        



    
