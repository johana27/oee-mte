from django import forms
from django.forms import formset_factory, inlineformset_factory, modelformset_factory                       
from datetime import date
from django.utils import timezone
from .models import Defect, DownTime, hourlyProduction, Production
from analytics.models import Recap
from core.models import Model, Cell, Cause
from planning.models import productionDetail, plannedProduction
from django.core.exceptions import ValidationError

# =========================================
# Form para ingresar producción planeada
# =========================================
class PlannedProductionFullForm(forms.Form):
    workorder = forms.CharField(widget=forms.TextInput(attrs={"class": "form-input", "required":"true", "placeholder": "Ingrese un valor"}))
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-input", "required":"true"}), required=False)
    model = forms.ModelChoiceField(
        queryset=Model.objects.all(),
        widget=forms.Select(attrs={"class": "form-select", "required":"true"})
    )
    quantity = forms.IntegerField(widget=forms.NumberInput(attrs={"class": "form-input", "min": 1, "required":"true", "placeholder":"0"}))

    def __init__(self, *args, **kwargs):
        self.cell = kwargs.pop('cell', None)
        super().__init__(*args, **kwargs)
        if self.cell:
            self.fields['model'].queryset = Model.objects.all()

    def clean_date(self):
        selected_date = self.cleaned_data.get('date')
        if selected_date and selected_date < date.today():
            raise ValidationError("No se puede ingresar producción de días anteriores.")
        return selected_date


class BasePlannedProductionFormSet(forms.BaseFormSet):
    def clean(self):
        if any(self.errors):
            return
        
        workorders = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                workorder = form.cleaned_data.get('workorder')
                if workorder:
                    if workorder in workorders:
                        raise ValidationError(f"La workorder '{workorder}' está duplicada. Salga de esta pantalla y vuelva a empezar.")
                    workorders.append(workorder)


PlannedProductionFormSet = formset_factory(
    PlannedProductionFullForm, 
    formset=BasePlannedProductionFormSet,
    extra=1, 
    can_delete=True
)

# =========================================
# Form para registrar el hora por hora
# =========================================
class HourlyProductionForm(forms.ModelForm):
    class Meta:
        model = hourlyProduction
        fields = ["hour", "pieces", "production_detail"]
        widgets = {
            "hour": forms.Select(attrs={"class": "form-input"}),
            "pieces": forms.NumberInput(attrs={"class": "form-input", "placeholder": "0"}),
            "production_detail": forms.Select(attrs={"class":"form-select"}),
        }

    def __init__(self, *args, **kwargs):
        self.cell = kwargs.pop('cell', None)
        self.date = kwargs.pop('date', date.today())
        super().__init__(*args, **kwargs)
        if self.cell and self.date:
            planned = plannedProduction.objects.filter(cell=self.cell, date=self.date)
            pd_qs = productionDetail.objects.filter(planned_production__in=planned)
            self.fields['production_detail'].queryset = pd_qs.select_related('model')
            # Mostrar solo el nombre del modelo en el select
            self.fields['production_detail'].label_from_instance = lambda obj: f"{obj.model.name}"
            #self.fields['production_detail'].label_from_instance = lambda obj: f"{obj.planned_production.workorder}"


class BaseHrxhrFormSet(forms.BaseModelFormSet):
    def clean(self):
        if any(self.errors):
            return
        
        hours = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                hour = form.cleaned_data.get('hour')
                if hour:
                    if hour in hours:
                        raise ValidationError(f"La hora '{hour}' está duplicada. Cada hora debe ser única.")
                    hours.append(hour)


HrxhrFormSet = modelformset_factory(
    hourlyProduction,
    form=HourlyProductionForm,
    formset=BaseHrxhrFormSet,
    extra=11,
    can_delete=True,
)

# =========================================
# Form para registrar la producción
# =========================================
class ProductionForm(forms.ModelForm):
    class Meta:
        model = Production
        fields = ["production", "comments"]  
        widgets = {
            "production": forms.NumberInput(attrs={"class": "form-input", "style": "width: 100px;", "min": "0", "required": "true"}),
            "comments": forms.Textarea(attrs={"class": "form-input", "style": "width: 300px;", "rows": 1}),
        }

ProductionFormSet = modelformset_factory(
    Production,
    form=ProductionForm,
    extra=0,  
    can_delete=False
)


# =========================================
# Form para registrar tiempos muertos
# =========================================
class DownTimeForm(forms.ModelForm):
    class Meta:
        model = DownTime
        fields = ['cause', 'start', 'end', 'comments']
        widgets = {
            'start': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input', 'required': 'true'}),
            'end': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input', 'required': 'true'}),
            'cause': forms.Select(attrs={'class': 'form-select', 'required': 'true'}),
            'comments': forms.Textarea(attrs={'class': 'form-input', 'placeholder': 'Ingrese un comentario....', 'style': 'height:150px'}),
        }

    def __init__(self, *args, **kwargs):
        self.cell = kwargs.pop('cell', None)
        super().__init__(*args, **kwargs)
        self.fields['cause'].queryset = Cause.objects.filter(type='downtime')

    def clean_end(self):
        end = self.cleaned_data.get('end')
        if end:
            # Check if end date is before today
            if end.date() < timezone.localdate():
                raise ValidationError("No se puede registrar tiempo muerto de fechas pasadas.")
        return end

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start')
        end = cleaned_data.get('end')
        
        # Check that end is after start
        if start and end:
            if end < start:
                raise ValidationError("La fecha de fin debe ser posterior a la fecha de inicio.")
        
        return cleaned_data

# =========================================
# Form para registrar defectos
# =========================================
class DefectForm (forms.Form):
    model = forms.ModelChoiceField(
        queryset = productionDetail.objects.all(),
        widget = forms.Select(attrs={"class":"form-select", "required":"true"})
    )
    cause = forms.ModelChoiceField(
        queryset = Cause.objects.all(),
        widget = forms.Select(attrs={"class":"form-select", "required":"true"})
    )
    comments = forms.CharField(widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Ingrese un comentario....", "style": "height:150px"}), required=False)
    quantity = forms.IntegerField(widget = forms.NumberInput(attrs={"class": "form-input", "required": "true", "placeholder": "0", "min": 1}))

    def __init__(self, *args, **kwargs):
        self.cell = kwargs.pop('cell', None)
        self.date = kwargs.pop('date', date.today())
        super().__init__(*args, **kwargs)
        self.fields['cause'].queryset = Cause.objects.filter(type='defect')
        if self.cell and self.date:
            planned_productions = plannedProduction.objects.filter(cell=self.cell, date=self.date)
            production_details = productionDetail.objects.filter(planned_production__in=planned_productions)
            self.fields['model'].queryset = production_details.select_related('model')
            self.fields['model'].label_from_instance = lambda obj: f"{obj.model.name}"

# =========================================
# Form para registrar comentarios de recap
# =========================================
class RecapForm (forms.ModelForm):
    class Meta:
        model = Recap
        fields = ['comments']
        widgets = {
            'comments': forms.Textarea(attrs={'class': 'form-input', 'placeholder': 'Ingrese un comentario....', 'style': 'height:150px'}),
        }