from django.contrib import admin
from django.urls import path, include

# Importa o módulo 'views' do seu app 'pedidos' e dá a ele o alias 'pedidos_views'.
# Isso abrange TODAS as funções dentro de pedidos/views.py.
from pedidos import views as pedidos_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # URLs da API (agora usando o alias pedidos_views para todas as funções de API)
    path('api/solicitacoes/', pedidos_views.listar_solicitacoes, name='api_listar_solicitacoes'),
    path('api/solicitacoes/criar/', pedidos_views.criar_solicitacao, name='api_criar_solicitacao'),
    path('api/solicitacoes/buscar/', pedidos_views.buscar_solicitacao, name='api_buscar_solicitacao'),
    path('api/solicitacoes/atualizar/<str:numero>/', pedidos_views.atualizar_solicitacao, name='api_atualizar_solicitacao'),
    path('api/solicitacoes/deletar/<str:numero>/', pedidos_views.deletar_solicitacao, name='api_deletar_solicitacao'),
    path('api/solicitacoes/pdf/', pedidos_views.gerar_pdf_solicitacao, name='api_gerar_pdf_solicitacao'),

    # URLs do app 'pedidos' (frontend)
    # Esta linha já inclui todas as URLs definidas em 'pedidos/urls.py'.
    # O 'pedidos/urls.py' internamente usará `from . import views`
    # para suas URLs de frontend (home_page, pedido_list, etc.).
    path('', include('pedidos.urls')),
]