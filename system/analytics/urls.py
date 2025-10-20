from django.urls import path
from .views import machineListView, machineDashboard, Reports, plantDashboard

urlpatterns = [
    path('', machineListView.as_view(), name='analyticsList'),
    path('dashboard/<int:cell_id>/', machineDashboard, name='machineDashboard'), 
    path('dashboard/', plantDashboard, name='plantDashboard'),
    path('reportes/', Reports, name='reports'),
]