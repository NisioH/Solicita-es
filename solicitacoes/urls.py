# C:\Users\fazin\OneDrive\Documents\Nisio\Solicita-es\solicitacoes\urls.py

from django.contrib import admin
from django.urls import path, include

# Importa o módulo 'views' do seu aplicativo 'pedidos'
# Use 'views' diretamente, sem um alias, para clareza
from pedidos import views

urlpatterns = [
    path('admin/', admin.site.urls),

    # --- Rotas da API (Retornam JSON) ---
    # A rota raiz da API ('api/solicitacoes/') deve chamar 'listar_solicitacoes'
    # que é a sua função de API que retorna JSON.
    path('api/solicitacoes/', views.listar_solicitacoes, name='api_listar_solicitacoes'),

    path('api/solicitacoes/criar/', views.criar_solicitacao, name='api_criar_solicitacao'),
    path('api/solicitacoes/buscar/', views.buscar_solicitacao, name='api_buscar_solicitacao'),
    path('api/solicitacoes/atualizar/<str:numero>/', views.atualizar_solicitacao, name='api_atualizar_solicitacao'),
    path('api/solicitacoes/deletar/<str:numero>/', views.deletar_solicitacao, name='api_deletar_solicitacao'),
    path('api/solicitacoes/excel/', views.gerar_excel_relatorio_mensal, name='api_gerar_excel_relatorio_mensal'),
   # path('api/solicitacoes/pdf/', views.gerar_pdf_solicitacao, name='api_gerar_pdf_solicitacao'),

    path('', include('pedidos.urls')),
]