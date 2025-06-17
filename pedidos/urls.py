from django.urls import path
from .views import criar_solicitacao, listar_solicitacoes, buscar_solicitacao, deletar_solicitacao, atualizar_solicitacao

urlpatterns = [
    path('solicitacoes/novo/', criar_solicitacao, name='criar_solicitacao'),
    path('solicitacoes/listar/', listar_solicitacoes, name='listar_solicitacoes'),
    path('solicitacoes/buscar/', buscar_solicitacao, name='buscar_solicitacao'),
    path('solicitacoes/atualizar/<str:numero>', atualizar_solicitacao, name='atualizar_solicitacao'),
    path('solicitacoes/deletar/<str:numero>', deletar_solicitacao, name='deletar_solicitacao'),
]