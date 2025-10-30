from django.urls import path
from .views import machineListView, machineDashboard, Reports, plantDashboard, noAccess

urlpatterns = [
    path('acceso-denegado/', noAccess, name='noAccess'),
    path('', machineListView.as_view(), name='analyticsList'),
    path('dashboard/<int:cell_id>/', machineDashboard, name='machineDashboard'), 
    path('dashboard/', plantDashboard, name='plantDashboard'),
    path('reportes/', Reports, name='reports'),
]