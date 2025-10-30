from django.db import models

class Cell (models.Model):
    name = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=50, choices=[
        ('small', 'Small'), 
        ('medium', 'Medianas'),
        ('large', 'Large'),
        ('embobinadora', 'Embobinadora'),
    ])
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = 'Celdas'

class Model (models.Model):
    name = models.CharField(max_length=100, unique=True)
    production_time = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
    class Meta: 
        verbose_name_plural = 'Modelos'

class Cause (models.Model):
    name = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=50, choices=[
        ("downtime", 'Tiempo muerto'), 
        ("defect", 'Defecto'),
    ], default='downtime')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = 'Causas'