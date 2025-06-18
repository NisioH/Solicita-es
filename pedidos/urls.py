from django.urls import path
from . import views # <--- Este import é fundamental para as views do frontend DENTRO do app 'pedidos'

urlpatterns = [
    path('', views.home_page, name='home'),
    path('pedidos/', views.pedido_list, name='pedido_list'),
    path('pedidos/novo/', views.pedido_create, name='pedido_create'),
    path('pedidos/editar/<str:numero>/', views.pedido_update, name='pedido_update'),
    path('pedidos/excluir/<str:numero>/', views.pedido_delete, name='pedido_delete'),
    path('pedidos/buscar/', views.pedido_search, name='pedido_search'),
]