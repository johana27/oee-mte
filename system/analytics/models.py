from django.db import models
from core.models import Cell
from manufacturing.models import Production, DownTime, Defect, hourlyProduction
from planning.models import plannedDownTimeCells
from django.db.models import Avg, Sum, Min, Max, Count
from django.utils import timezone
from calendar import monthrange
from datetime import date

class RecapManager(models.Manager):
    """Manager personalizado para cálculos agregados de Recap"""
    
    def weekly_metrics(self, cell_id, start_date, end_date):
        """Calcula métricas semanales para una celda"""
        recaps = self.filter(
            pub_date__gte=start_date,
            pub_date__lte=end_date,
            cell_id=cell_id,
        )
        
        metrics = recaps.aggregate(
            avg_availability=Avg("availability"),
            avg_performance=Avg("performance"),
            avg_quality=Avg("quality"),
            sum_planned_pieces=Sum("total_planned_pieces"),
            sum_actual_pieces=Sum("total_actual_pieces"),
        )
        
        # Calcular OEE
        availability = metrics["avg_availability"] or 0
        performance = metrics["avg_performance"] or 0
        quality = metrics["avg_quality"] or 0
        oee = availability * performance * quality * 100
        
        # Calcular porcentaje de completado
        planned = metrics["sum_planned_pieces"] or 0
        actual = metrics["sum_actual_pieces"] or 0
        completion = (actual * 100 / planned) if planned > 0 else 0
        
        return {
            "availability": round(availability * 100, 2),
            "performance": round(performance * 100, 2),
            "quality": round(quality * 100, 2),
            "oee": round(oee, 2),
            "planned_pieces": planned,
            "actual_pieces": actual,
            "completion_percentage": round(completion, 1),
            "recaps": recaps,
        }
    
    def monthly_metrics(self, cell_id, year=None, month=None):
        """Calcula métricas mensuales para una celda"""
        now = timezone.now()
        year = year or now.year
        month = month or now.month
        
        recaps = self.filter(
            cell_id=cell_id,
            pub_date__year=year,
            pub_date__month=month
        )
        
        metrics = recaps.aggregate(
            avg_availability=Avg("availability"),
            avg_performance=Avg("performance"),
            avg_quality=Avg("quality"),
            sum_downtime=Sum("total_downtime_minutes"),
            sum_total_defects=Sum("total_defects")
        )

        # Calcular suma de operating minutes (property)
        sum_operating_minutes = sum(recap.total_operating_minutes for recap in recaps)
        
        # Calcular OEE
        availability = metrics["avg_availability"] or 0
        performance = metrics["avg_performance"] or 0
        quality = metrics["avg_quality"] or 0
        oee = availability * performance * quality * 100
        
        return {
            "availability": round(availability * 100, 2),
            "performance": round(performance * 100, 2),
            "quality": round(quality * 100, 2),
            "oee": round(oee, 2),
            "downtime": metrics["sum_downtime"] or 0,
            "sum_total_defects": metrics["sum_total_defects"] or 0,
            "operating_minutes": sum_operating_minutes,
            "recaps": recaps,
        }

    def defectsList (self, cell_id, year=None, month=None, limit=5):
        now = timezone.now()
        year = year or now.year
        month = month or now.month

        defects = (
            Defect.objects.filter(
                production_detail__planned_production__cell=cell_id, 
                cause__type="defect",
                created_at__year=year,
                created_at__month=month,
            )
            .values("cause__name")
            .annotate(total=Count("id"))
            .order_by("-total")[:limit]
        )

        return list(defects)

    def daily_oee_data(self, cell_id, year=None, month=None):
        """Obtiene datos de OEE diario para gráficas, incluyendo días sin producción"""
        now = timezone.now()
        year = year or now.year
        month = month or now.month
        
        # Obtener todos los recaps del mes
        recaps = self.filter(
            cell_id=cell_id,
            pub_date__year=year,
            pub_date__month=month
        ).order_by('pub_date')
        
        # Crear un diccionario con los datos existentes (día -> recap)
        recap_dict = {}
        for recap in recaps:
            day = recap.pub_date.day
            recap_dict[day] = recap
        
        # Obtener el número de días en el mes
        num_days = monthrange(year, month)[1]
        
        # Generar datos para todos los días del mes
        labels = []
        data = []
        colors = []
        
        for day in range(1, num_days + 1):
            labels.append(str(day))
            
            if day in recap_dict:
                # Hay datos para este día
                oee = recap_dict[day].oee_percentage
                data.append(round(oee, 2))
                
                # Color según el OEE
                if oee >= 85:
                    colors.append('rgba(34, 197, 94, 0.8)')  # Verde
                elif oee >= 70:
                    colors.append('rgba(251, 191, 36, 0.8)')  # Amarillo
                else:
                    colors.append('rgba(239, 68, 68, 0.8)')  # Rojo
            else:
                # No hay datos para este día
                data.append(0)
                colors.append('rgba(156, 163, 175, 0.3)')  # Gris claro
        
        return {
            'labels': labels,
            'data': data,
            'colors': colors,
            'month_name': date(year, month, 1).strftime('%B %Y')
        }

class Recap(models.Model):
    cell = models.ForeignKey(Cell, on_delete=models.CASCADE)
    total_planned_pieces = models.IntegerField()
    total_actual_pieces = models.IntegerField()
    total_downtime_minutes = models.IntegerField()
    total_defects = models.IntegerField()
    availability = models.FloatField()
    performance = models.FloatField()
    quality = models.FloatField()
    oee_percentage = models.FloatField()
    comments = models.TextField(blank=True, null=True)
    pub_date = models.DateTimeField(auto_now_add=True)
    
    # Manager personalizado
    objects = RecapManager()

    @property
    def total_operating_minutes(self):
        from django.db.models import Min, Max

        productions = hourlyProduction.objects.filter(
            production_detail__model_routing__cell=self.cell,
            pieces__gt=0
        ).aggregate(
            first_hour=Min("hour"),
            last_hour=Max("hour")
        )

        first_hour = productions["first_hour"]
        last_hour = productions["last_hour"]

        if first_hour is None or last_hour is None:
            return 0  

        return (last_hour - first_hour + 1) * 60

    def calculate_metrics(self):
        """Calcula availability, performance, quality y OEE"""
        try:
            self.availability = (self.total_operating_minutes - self.total_downtime_minutes) / self.total_operating_minutes
        except ZeroDivisionError:
            self.availability = 0

        try:
            self.performance = self.total_actual_pieces / self.total_planned_pieces
        except ZeroDivisionError:
            self.performance = 0

        try:
            self.quality = (self.total_actual_pieces - self.total_defects) / self.total_actual_pieces
        except ZeroDivisionError:
            self.quality = 0

        self.oee_percentage = self.availability * self.performance * self.quality * 100
    
    def __str__(self):
        return f"{self.cell.name} - {self.pub_date.strftime('%Y-%m-%d')}"

    class Meta:
        verbose_name_plural = "Recaps"


