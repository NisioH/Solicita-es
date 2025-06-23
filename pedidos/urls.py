# C:\Users\fazin\OneDrive\Documents\Nisio\Solicita-es\pedidos\urls.py

from django.urls import path
from . import views # <-- Importa as views do próprio app 'pedidos'

urlpatterns = [
    # Esta é a rota que serve a página HTML da lista de pedidos
    path('', views.pedido_list, name='pedido_list'),
    path('create/', views.pedido_create, name='pedido_create'),
    path('editar/<str:numero>/', views.pedido_update, name='pedido_update'),
    path('deletar/<str:numero>/', views.pedido_delete, name='pedido_delete'),
    path('buscar/', views.pedido_search, name='pedido_search'),
    # ... outras rotas do seu frontend, se houver
]