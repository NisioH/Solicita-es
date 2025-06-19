# solicitacoes_principal/urls.py

from django.contrib import admin
from django.urls import path, include

# Importa o módulo 'views' do seu app 'pedidos' e dá a ele o alias 'pedidos_views'.
# Isso abrange TODAS as funções dentro de pedidos/views.py.
from pedidos import views as pedidos_views # <--- Certifique-se de que esta linha está presente!

urlpatterns = [
    path('admin/', admin.site.urls),

    # URLs da API (essas são as que estão faltando na lista de padrões do erro!)
    path('api/solicitacoes/', pedidos_views.listar_solicitacoes, name='api_listar_solicitacoes'),
    path('api/solicitacoes/criar/', pedidos_views.criar_solicitacao, name='api_criar_solicitacao'),
    path('api/solicitacoes/buscar/', pedidos_views.buscar_solicitacao, name='api_buscar_solicitacao'),
    path('api/solicitacoes/atualizar/<str:numero>/', pedidos_views.atualizar_solicitacao, name='api_atualizar_solicitacao'),
    path('api/solicitacoes/deletar/<str:numero>/', pedidos_views.deletar_solicitacao, name='api_deletar_solicitacao'),
    path('api/solicitacoes/pdf/', pedidos_views.gerar_pdf_solicitacao, name='api_gerar_pdf_solicitacao'),

    # URLs do app 'pedidos' (frontend)
    path('', include('pedidos.urls')), # <--- Certifique-se de que esta linha está presente!
]