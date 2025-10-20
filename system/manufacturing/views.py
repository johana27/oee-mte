from django.shortcuts import render, get_object_or_404, redirect
from planning.models import plannedDownTime, plannedDownTimeCells, plannedProduction, productionDetail
from .models import Defect, DownTime, hourlyProduction, Production
from .forms import PlannedProductionFullForm, DownTimeForm, DefectForm, HrxhrFormSet, ProductionFormSet, RecapForm
from core.models import Cell, modelRouting 
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone
from django.forms import formset_factory
from datetime import date

# =========================================
# Vista para la pantalla de detalles de máquina
# =========================================
def machineDetails(request, cell_id):
    cell = get_object_or_404(Cell, id=cell_id)
    today = timezone.localdate()
    plannings = plannedProduction.objects.filter(cell=cell)
    production_details = productionDetail.objects.filter(planned_production__cell=cell, planned_production__date=today)
    planned_today = plannedProduction.objects.filter(cell=cell, date=today)
    hrxhr = hourlyProduction.objects.filter(production_detail__planned_production__cell=cell, production_detail__planned_production__date=today)
    

    context = {
        'cell': cell,
        'plannings': plannings,
        'hrxhr': hrxhr,
        'production_details': production_details,
        'planned_today': planned_today,
        'today': today,
    }

    return render(request, 'manufacturing/machineDetails.html', context)

# =========================================
# Vista para agregar la producción planeada
# =========================================
def addHrxhr(request, cell_id):
    cell = get_object_or_404(Cell, id=cell_id)
    PlannedProductionFormSet = formset_factory(PlannedProductionFullForm, extra=1)

    if request.method == "POST":
        formset = PlannedProductionFormSet(request.POST)

        if formset.is_valid():
            master_date = None
            for form in formset:
                if form.cleaned_data and form.cleaned_data.get("date"):
                    master_date = form.cleaned_data["date"]
                    break
            
            if not master_date:
                return render(request, "manufacturing/addHrxhr.html", {
                    "formset": formset,
                    "error": "Debe especificar una fecha"
                })

            for form in formset:
                if not form.cleaned_data:
                    continue
                    
                workorder = form.cleaned_data["workorder"]
                model_routing = form.cleaned_data["model_routing"]
                quantity = form.cleaned_data["quantity"]

                planned = plannedProduction.objects.create(
                    cell_id=cell_id,
                    date=master_date, 
                    created_by=request.user,
                    workorder=workorder
                )

                productionDetail.objects.create(
                    planned_production=planned,
                    model_routing=model_routing,
                    quantity=quantity
                )

            return redirect("hrxhr", cell_id=cell.id)
        else:
            print("Formset errors:", formset.errors)
    else:
        formset = PlannedProductionFormSet(form_kwargs={'cell': cell})

    return render(request, "manufacturing/addHrxhr.html", {
        "formset": formset
    })

# =========================================
# Vista para generar el hora por hora
# =========================================
def hrxhr (request, cell_id):
    today = date.today()

    queryset = hourlyProduction.objects.filter(
        production_detail__planned_production__cell_id=cell_id,
        production_detail__planned_production__date=today
    )

    if request.method == "POST":
        formset = HrxhrFormSet(request.POST, queryset=queryset, form_kwargs={
            'cell': get_object_or_404(Cell, id=cell_id),
            'date': today,
        })
        if formset.is_valid():
            instances = formset.save(commit=False)
            for inst in instances:
                inst.created_by = request.user
                inst.save()
            return redirect("machineDetails", cell_id=cell_id)
    else:
        formset = HrxhrFormSet(queryset=queryset, form_kwargs={
            'cell': get_object_or_404(Cell, id=cell_id),
            'date': today,
        })

    context = {
        "formset": formset, 
    }

    return render(request, "manufacturing/registerHrxhr.html", context)

# =========================================
# Vista para registrar la producción durante el día
# =========================================
def addProduction(request, cell_id):
    cell = get_object_or_404(Cell, id=cell_id)
    today = timezone.localdate()

    planned_today = productionDetail.objects.filter(
        planned_production__cell=cell,
        planned_production__date=today
    )

    hourly_production = hourlyProduction.objects.filter(
        production_detail__planned_production__cell=cell,
        production_detail__planned_production__date=today
    )

    # aseguramos que haya un Production por cada hourlyProduction
    for hp in hourly_production:
        Production.objects.get_or_create(hrxhr=hp)

    existing_productions = Production.objects.filter(hrxhr__in=hourly_production)

    if request.method == "POST":
        formset = ProductionFormSet(request.POST, queryset=existing_productions)
        if formset.is_valid():
            instances = formset.save(commit=False)
            for instance in instances:
                instance.created_by = request.user
                instance.save()
            return redirect("machineDetails", cell_id=cell.id)
        else:
            print("ProductionFormSet errors:", formset.errors)
    else:
        formset = ProductionFormSet(queryset=existing_productions)

    # combinamos hourly_production con el formset en pares
    rows = zip(hourly_production, formset.forms)

    context = {
        "cell": cell,
        "planned_today": planned_today,
        "hourly_production": hourly_production,
        "today": today,
        "formset": formset,
        "rows": rows,  # mandamos los pares al template
    }
    return render(request, "manufacturing/hrxhr.html", context)

# =========================================
# Vista para registrar tiempos muertos
# =========================================
def downtime (request, cell_id):
    cell = get_object_or_404(Cell, id=cell_id)
    if request.method == "POST":
        form = DownTimeForm(request.POST, cell=cell)
        if form.is_valid():
            downtime_instance = form.save(commit=False) 
            downtime_instance.cell = cell
            downtime_instance.created_by = request.user
            downtime_instance.save()
            return redirect("machineDetails", cell_id=cell.id)
    else:
        form = DownTimeForm(cell=cell)

    context = {
        "form": form,
        "cell": cell,
    }
    return render(request, "manufacturing/downtime.html", context)


# =========================================
# Vista para registrar defectos
# =========================================
def defects (request, cell_id): 
    cell = get_object_or_404(Cell, id=cell_id)
    if request.method == "POST":
        form = DefectForm(request.POST, cell=cell_id, date=timezone.localdate())
        if form.is_valid():
            model_detail = form.cleaned_data["model"]  
            cause = form.cleaned_data["cause"]
            comments = form.cleaned_data["comments"]
            quantity = form.cleaned_data["quantity"]

            Defect.objects.create(
                production_detail=model_detail,
                cause=cause,
                quantity=quantity,
                comments=comments,
                created_by=request.user,
            )
            return redirect("machineDetails", cell_id=cell.id)
    else:
        form = DefectForm(cell=cell_id, date=timezone.localdate())

    return render(request, "manufacturing/defects.html", {
        "form": form,
        "cell_id": cell_id
    })

# =========================================
# Vista para el recap del día
# =========================================
def recap (request, cell_id):
    cell = get_object_or_404(Cell, id=cell_id)
    today = date.today()
    production = Production.objects.filter(hrxhr__production_detail__planned_production__cell=cell, hrxhr__production_detail__planned_production__date=today)
    defects = Defect.objects.filter(production_detail__model_routing__cell=cell, created_at__date=today)
    downtime = DownTime.objects.filter(cell=cell, created_at__date=today)

    total_planned_pieces = hourlyProduction.objects.filter(
        production_detail__planned_production__cell=cell,
        production_detail__planned_production__date=today
    ).aggregate(total=models.Sum("pieces"))["total"] or 0

    total_actual_pieces = Production.objects.filter(
        hrxhr__production_detail__planned_production__cell=cell,
        hrxhr__production_detail__planned_production__date=today
    ).aggregate(total=models.Sum("production"))["total"] or 0

    total_defects = Defect.objects.filter(
        production_detail__planned_production__cell=cell,
        production_detail__planned_production__date=today
    ).aggregate(total=models.Sum("quantity"))["total"] or 0

    downtimes = DownTime.objects.filter(cell=cell, created_at__date=today)
    total_downtime_minutes = sum(d.duration_minutes for d in downtimes)


    if request.method == "POST":
        form = RecapForm(request.POST)
        if form.is_valid():
            recap_instance = form.save(commit=False) 
            recap_instance.cell = cell
            recap_instance.pub_date = timezone.now()
            recap_instance.total_planned_pieces = total_planned_pieces
            recap_instance.total_actual_pieces = total_actual_pieces
            recap_instance.total_defects = total_defects
            recap_instance.total_downtime_minutes = total_downtime_minutes
            recap_instance.calculate_metrics()
            recap_instance.save()
            return redirect("machineDetails", cell_id=cell.id)
    else:
        form = RecapForm()

    context = {
        "production_today": production, 
        "defects_today": defects, 
        "downtime_today": downtime, 
        "cell":cell,
        "form": form,
        "total_planned_pieces": total_planned_pieces,
        "total_actual_pieces": total_actual_pieces,
        "total_defects": total_defects,
        "total_downtime_minutes": total_downtime_minutes,
        }
    return render(request, "manufacturing/recap.html", context)

