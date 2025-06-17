from rest_framework.response import Response
from rest_framework.decorators import api_view
from .database import db

@api_view(['POST'])
def criar_solicitacao(request):
    data = request.data
    print("Recebido:", data)
    campos_obrigatorios = ["numero", "descricao", "solicitado_por", "safra", "centro_custo", "status"]
    for campo in campos_obrigatorios:
        if campo not in data:
            return Response({"mensagem": f"Campo '{campo}' é obrigatório."}, status=400)
    db.solicitacoes.insert_one(data)
    return Response({"mensagem": "Solicitação criada com sucesso!"}, status=201)

# @api_view(['POST'])
# def criar_solicitacao(request):
#     try:
#         data = request.data
#         resultado = db.solicitacoes.insert_one(data)
#         return Response({"mensagem": "Solicitação criada!", "id": str(resultado.inserted_id)}, status=201)
#     except Exception as e:
#         print("Erro ao salvar no MongoDB:", e)  # 👈 Aqui veremos o erro no terminal
#         return Response({"mensagem": f"Erro interno: {str(e)}"}, status=500)


@api_view(['GET'])
def buscar_solicitacao(request):
    numero = request.GET.get("numero")
    palavra = request.GET.get("palavra")

    if numero:
        solicitacao = db.solicitacoes.find_one({"numero": numero})
        if solicitacao:
            solicitacao["_id"] = str(solicitacao["_id"])
            return Response(solicitacao)
        return Response({"mensagem": "Solicitação não encontrada."}, status=404)
    elif palavra:
        solicitacoes = db.solicitacoes.find({"$text": {"$search": palavra}})
        resultado = [dict(solic, _id=str(solic["_id"])) for solic in solicitacoes]
        if resultado:
            return Response(resultado)
        return Response({"mensagem": "Nenhuma solcitação encontrada com essa palavra."}, status=404)
    return Response({"mensagem": "Informe um número ou palavra de busca."}, status=400)

@api_view(['PUT'])
def atualizar_solicitacao(request, numero):
    dados = request.data
    resultado = db.solicitacoes.update_one({"numero": numero}, {"$set": dados})

    if resultado.matched_count > 0:
        return Response({"mensagem": "Solicitação atualizada com sucesso."})
    return Response({"mensagem": "Solicitação não encontrada."}, status=404)

@api_view(['DELETE'])
def deletar_solicitacao(request, numero):
    resultado = db.solicitacoes.delete_one({"numero": numero})

    if resultado.deleted_count > 0:
        return Response({"mensagem": "Solicitação deletada com sucesso."})
    return Response({"mensagem": "Solicitação não encontrada."}, status=404)

@api_view(['GET'])
def listar_solicitacoes(request):
    solicitacoes = db.solicitacoes.find()
    resultados = [dict(solic, _id=str(solic["_id"])) for solic in solicitacoes]
    return Response(resultados)

