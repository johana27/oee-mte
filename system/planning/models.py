from django.db import models
from system.core.models import Cell, Model
from django.contrib.auth.models import User

class plannedProduction(models.Model):
    cell = models.ForeignKey(Cell, on_delete=models.CASCADE)
    date = models.DateField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    workorder = models.CharField(max_length=100)
    #100 caracteres para el wc

    def __str__(self):
        return f" Producción {self.cell.name} - {self.date.strftime('%Y-%m-%d')}"
    
    class Meta:
        verbose_name_plural = 'Producción Planeada'

class productionDetail(models.Model):
    planned_production = models.ForeignKey(plannedProduction, on_delete=models.CASCADE, related_name='details')
    model = models.ForeignKey(Model, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)
        
    def __str__(self):
        return f"{self.model.name} - {self.planned_production.cell.name} - {self.planned_production.date.strftime('%y-%m-%d')}"
    
    class Meta: 
        verbose_name_plural = "Produccion detalles"

class plannedDownTime(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    repetition = models.CharField(max_length=50, choices=[
        ('daily', 'Diario'),
        ('weekly', 'Semanal'),
        ('monthly', 'Mensual'),
        ('once', 'Una vez')
    ], default='once')
    valid_from = models.DateField(blank=True, null=True)
    valid_to = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    pub_date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name}"
    
    class Meta:
        verbose_name_plural = "Tiempo muerto planeado"

class plannedDownTimeCells (models.Model):
    cell = models.ForeignKey(Cell, on_delete=models.CASCADE)
    planned_downtime = models.ForeignKey(plannedDownTime, on_delete=models.CASCADE, related_name='downtime')

    def __str__(self):
        return f"{self.cell.name} - {self.planned_downtime.name}"

    class Meta:
        verbose_name_plural = "Celdas de tiempo muerto planeado"
