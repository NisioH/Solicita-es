from django.contrib import admin
from django.urls import path, include
from pedidos import views as pedidos_views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/solicitacoes/', pedidos_views.listar_solicitacoes, name='api_listar_solicitacoes'),
    path('api/solicitacoes/criar/', pedidos_views.criar_solicitacao, name='api_criar_solicitacao'),
    path('api/solicitacoes/buscar/', pedidos_views.buscar_solicitacao, name='api_buscar_solicitacao'),
    path('api/solicitacoes/atualizar/<str:numero>/', pedidos_views.atualizar_solicitacao, name='api_atualizar_solicitacao'),
    path('api/solicitacoes/deletar/<str:numero>/', pedidos_views.deletar_solicitacao, name='api_deletar_solicitacao'),
    path('api/solicitacoes/pdf/', pedidos_views.gerar_pdf_solicitacao, name='api_gerar_pdf_solicitacao'),

    path('', include('pedidos.urls')),
]