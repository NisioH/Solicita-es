# C:\Users\fazin\OneDrive\Documents\Nisio\Solicita-es\pedidos\views.py

import requests
from django.shortcuts import render, redirect
from django.contrib import messages
from datetime import datetime
from .database import db # Certifique-se de que este import está correto para o seu arquivo database.py
from rest_framework.response import Response
from rest_framework.decorators import api_view
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from bson.objectid import ObjectId # Importar ObjectId para lidar com IDs do MongoDB


BASE_API_URL = "http://127.0.0.1:8000/api/solicitacoes/"


def api_request(method, endpoint, data=None, params=None):
    full_url = f"{BASE_API_URL}{endpoint}"

    try:
        response = None
        if method == 'GET':
            response = requests.get(full_url, params=params)
        elif method == 'POST':
            response = requests.post(full_url, json=data)
        elif method == 'PUT':
            response = requests.put(full_url, json=data)
        elif method == 'DELETE':
            response = requests.delete(full_url)
        else:
            raise ValueError("Método HTTP não suportado pela função api_request.")
        
        response.raise_for_status() 
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição API ({method} {full_url}): {e}")
        if response is not None and response.content:
            try:
                # Tenta analisar a resposta de erro como JSON
                error_data = response.json()
                # Retorna a mensagem de erro específica da API, se disponível
                return {"error": True, "message": error_data.get("mensagem", str(e))}
            except ValueError:
                # Se a resposta não for JSON, retorna o texto bruto
                return {"error": True, "message": f"Erro na API (Resposta não JSON): {response.text}"}
        # Em caso de erro de conexão (ex: servidor da API não está rodando)
        return {"error": True, "message": f"Erro de conexão com a API: {e}"}


@api_view(['GET'])
def listar_solicitacoes(request):
   
    try:
        # Parâmetros de paginação
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 10

        skip = (page - 1) * page_size

        total = db.solicitacoes.count_documents({})
        solicitacoes_cursor = db.solicitacoes.find({}).sort('data_criacao', -1).skip(skip).limit(page_size)
        solicitacoes_list = []
        for doc in solicitacoes_cursor:
            doc['_id'] = str(doc['_id'])
            for key, value in doc.items():
                if isinstance(value, datetime):
                    doc[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            solicitacoes_list.append(doc)

        return Response({
            "results": solicitacoes_list,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }, status=200)

    except Exception as e:
        print(f"API - Erro ao listar solicitações: {e}")
        return Response({"mensagem": f"Erro interno ao listar solicitações: {str(e)}"}, status=500)


@api_view(['POST'])
def criar_solicitacao(request):
   
    try:
        data = request.data # request.data é usado para dados JSON/form no DRF

        allowed_statuses = ["Recebido", "Aguardando", "Cancelada", "Reprovada"]
        status_val = data.get("status") # Usar nome diferente para evitar conflito com built-in
        if status_val and status_val not in allowed_statuses:
            return Response({"error": True,
                             "message": f"Status '{status_val}' inválido. "
                                        f"Use um dos seguintes: {', '.join(allowed_statuses)}."},
                            status=400)

        required_fields = ["numero", "descricao", "solicitado_por", "safra", "centro_custo", "status", "data"]
        for field in required_fields:
            if not data.get(field):
                return Response({"error": True, "message": f"O campo '{field}' é obrigatório."}, status=400)

        
        existing_solicitation = db.solicitacoes.find_one({
            "numero": data["numero"],
            "safra": data["safra"]
        })

        if existing_solicitation:
            return Response({"error": True,
                             "message": f"Já existe uma solicitação com o número '{data['numero']}' "
                                        f"para a safra '{data['safra']}'. Por favor, verifique ou use outra combinação."},
                            status=409) # 409 Conflict - indica conflito de recurso
       

        if 'data' in data and isinstance(data['data'], str):
            try:
                data['data'] = datetime.strptime(data['data'], '%Y-%m-%d')
            except ValueError:
                return Response({"error": True, "message":
                    "Formato de data inválido para 'data'. Use YYYY-MM-DD."},
                                status=400)

        if 'data_recebido' in data and isinstance(data['data_recebido'], str) and data['data_recebido']:
            try:
                data['data_recebido'] = datetime.strptime(data['data_recebido'], '%Y-%m-%d')
            except ValueError:
                return Response(
                    {"error": True, "message":
                        "Formato de data inválido para 'data_recebido'. Use YYYY-MM-DD."},
                    status=400)
        else:
            data['data_recebido'] = None # Garante que seja None se estiver vazio ou não for fornecido

        data['data_criacao'] = datetime.now() # Adiciona a data/hora de criação

        result = db.solicitacoes.insert_one(data)
        print(f"API - Solicitação criada com ID: {result.inserted_id} e número: {data['numero']}")
        return Response(
            {"mensagem": "Solicitação criada com sucesso!",
             "id": str(result.inserted_id), "numero": data["numero"]},
            status=201) # 201 Created - indica que o recurso foi criado

    except Exception as e:
        print(f"API - Erro ao criar solicitação: {e}")
        return Response({"mensagem": f"Erro interno ao criar solicitação: {str(e)}"}, status=500)

""" 
@api_view(['GET'])
def buscar_solicitacao(request):
    try:
        numero = request.GET.get("numero")
        palavra = request.GET.get("palavra")
        centro_custo_busca = request.GET.get("centro_custo")

        if not numero and not palavra and not centro_custo_busca:
            return Response({"mensagem": "Informe um número, palavra-chave ou centro de custo para a busca."},
                            status=400)
        query_params = {}

        if numero:
            query_params["numero"] = numero
            print(f"API - Buscando por número (exato): {numero}")

        if palavra:
            query_params["descricao"] = {"$regex": palavra, "$options": "i"} # Busca case-insensitive
            print(f"API - Buscando por descrição (contém): {palavra}")

        if centro_custo_busca:
            query_params["centro_custo"] = {"$regex": centro_custo_busca, "$options": "i"}
            print(f"API - Buscando por centro de custo (contém): {centro_custo_busca}")

        solicitacoes_cursor = db.solicitacoes.find(query_params)
        resultados = []
        for solic in solicitacoes_cursor:
            solic["_id"] = str(solic["_id"])
            
            for key, value in solic.items():
                if isinstance(value, datetime):
                    solic[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            resultados.append(solic)

        if resultados:
            print(f"API - Encontrados {len(resultados)} resultados.")
            return Response(resultados, status=200)

        print("API - Nenhuma solicitação encontrada para os critérios.")
        return Response({"mensagem": "Nenhuma solicitação encontrada "
                                     "para os critérios informados.", "resultados": []},
                        status=200)

    except Exception as e:
        print(f"API - Erro ao buscar no MongoDB: {e}")
        return Response({"mensagem": f"Erro interno ao buscar: {str(e)}"}, status=500)
 """

@api_view(['GET'])
def buscar_solicitacao(request):
    try:
        numero = request.GET.get("numero")
        palavra = request.GET.get("palavra")
        centro_custo_busca = request.GET.get("centro_custo")
        status_busca = request.GET.get("status")

        if not any([numero, palavra, centro_custo_busca, status_busca]):
            return Response({"mensagem": "Informe ao menos um critério para a busca."}, status=400)

        query_params = {}

        if numero:
            query_params["numero"] = numero
            print(f"API - Buscando por número (exato): {numero}")

        if palavra:
            query_params["descricao"] = {"$regex": palavra, "$options": "i"}
            print(f"API - Buscando por descrição (contém): {palavra}")

        if centro_custo_busca:
            query_params["centro_custo"] = {"$regex": centro_custo_busca, "$options": "i"}
            print(f"API - Buscando por centro de custo (contém): {centro_custo_busca}")

        if status_busca:
            status_opcoes = ["Recebido", "Aguardando", "Cancelada", "Reprovada"]
            if status_busca not in status_opcoes:
                return Response({"mensagem": f"Status inválido. Use um dos seguintes: {', '.join(status_opcoes)}"},
                                status=400)
            query_params["status"] = status_busca
            print(f"API - Buscando por status (exato): {status_busca}")

          

        solicitacoes_cursor = db.solicitacoes.find(query_params)
        resultados = []
        for solic in solicitacoes_cursor:
            solic["_id"] = str(solic["_id"])
            for key, value in solic.items():
                if isinstance(value, datetime):
                    solic[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            resultados.append(solic)

        if resultados:
            print(f"API - Encontrados {len(resultados)} resultados.")
            return Response(resultados, status=200)

        print("API - Nenhuma solicitação encontrada para os critérios.")
        return Response({"mensagem": "Nenhuma solicitação encontrada para os critérios informados.",
                         "resultados": []}, status=200)

    except Exception as e:
        print(f"API - Erro ao buscar no MongoDB: {e}")
        return Response({"mensagem": f"Erro interno ao buscar: {str(e)}"}, status=500)

@api_view(['PUT'])
def atualizar_solicitacao(request, numero):
    try:
        data = request.data

        allowed_statuses = ["Recebido", "Aguardando", "Cancelada", "Reprovada"]
        status_val = data.get("status")
        if status_val and status_val not in allowed_statuses:
            return Response({"error": True,
                             "message": f"Status '{status_val}' inválido. "
                                        f"Use um dos seguintes: {', '.join(allowed_statuses)}."},
                            status=400)

        if 'data' in data and isinstance(data['data'], str):
            try:
                data['data'] = datetime.strptime(data['data'], '%Y-%m-%d')
            except ValueError:
                return Response({"error": True, "message":
                    "Formato de data inválido para 'data'. Use YYYY-MM-DD."},
                                status=400)

        if 'data_recebido' in data and isinstance(data['data_recebido'], str) and data['data_recebido']:
            try:
                data['data_recebido'] = datetime.strptime(data['data_recebido'], '%Y-%m-%d')
            except ValueError:
                return Response(
                    {"error": True, "message":
                        "Formato de data inválido para 'data_recebido'. Use YYYY-MM-DD."},
                    status=400)
        else:
            data['data_recebido'] = None # Garante que seja None se vazio

        update_data = {k: v for k, v in data.items() if v is not None and v != ''}

        # Lógica para evitar duplicidade de número ao atualizar
        if 'numero' in update_data and update_data['numero'] != numero:
            if db.solicitacoes.find_one({"numero": update_data['numero']}):
                return Response({"error": True,
                                 "message": f"O novo número de solicitação "
                                            f"'{update_data['numero']}' já existe. Por favor, escolha outro."},
                                status=409)

        if not update_data:
            return Response({"mensagem": "Nenhum dado fornecido para atualização."}, status=400)

        result = db.solicitacoes.update_one({"numero": numero}, {"$set": update_data})

        if result.matched_count == 0:
            print(f"API - Solicitação {numero} não encontrada para atualização.")
            return Response({"mensagem": f"Solicitação com número {numero} não encontrada."}, status=404)

        print(f"API - Solicitação {numero} atualizada com sucesso.")
        return Response({"mensagem": f"Solicitação {numero} atualizada com sucesso!"}, status=200)

    except Exception as e:
        print(f"API - Erro ao atualizar solicitação: {e}")
        return Response({"mensagem": f"Erro interno ao atualizar solicitação: {str(e)}"}, status=500)

@api_view(['DELETE'])
def deletar_solicitacao(request, numero):
   
    print(f"API - Recebido para deletar: {numero}")
    try:
        resultado = db.solicitacoes.delete_one({"numero": numero})

        if resultado.deleted_count > 0:
            print(f"API - Solicitação {numero} deletada com sucesso.")
            return Response({"mensagem": "Solicitação deletada com sucesso."}, status=200) # 200 OK ou 204 No Content
        
        print(f"API - Solicitação {numero} não encontrada para deleção.")
        return Response({"mensagem": "Solicitação não encontrada."}, status=404)
    except Exception as e:
        print(f"API - Erro ao deletar solicitação: {e}")
        return Response({"mensagem": f"Erro interno ao deletar: {str(e)}"}, status=500)


from django.http import HttpResponse
from openpyxl import Workbook
from datetime import datetime

def gerar_excel_relatorio_mensal(request):
    try:
        mes = request.GET.get("mes")  # Ex: '07' para julho
        ano = request.GET.get("ano")  # Ex: '2025'

        if not mes or not ano:
            return HttpResponse("Informe o mês e ano para gerar o relatório.", status=400)

        print(f"API - Gerando relatório para {mes}/{ano}")

        # Buscar todas as solicitações do mês e ano
        inicio = datetime(int(ano), int(mes), 1)
        fim = datetime(int(ano), int(mes) + 1, 1) if int(mes) < 12 else datetime(int(ano)+1, 1, 1)

        solicitacoes = db.solicitacoes.find({
            "data_criacao": {"$gte": inicio, "$lt": fim}
        })

        # Criação do Excel
        wb = Workbook()
        ws = wb.active
        ws.title = f"Solicitações_{mes}_{ano}"

        # Cabeçalhos
        campos = ["Número", "Descrição", "Solicitado Por", "Safra", "Centro de Custo",
                  "Status", "Data da Solicitação", "Data Recebido", "Fornecedor",
                  "Nota Fiscal", "Data de Criação"]
        ws.append(campos)

        for s in solicitacoes:
            linha = [
                s.get("numero", ""),
                s.get("descricao", ""),
                s.get("solicitado_por", ""),
                s.get("safra", ""),
                s.get("centro_custo", ""),
                s.get("status", ""),
                s.get("data", "").strftime('%d/%m/%Y') if isinstance(s.get("data"), datetime) else "",
                s.get("data_recebido", "").strftime('%d/%m/%Y') if isinstance(s.get("data_recebido"), datetime) else "",
                s.get("fornecedor", ""),
                s.get("nota_fiscal", ""),
                s.get("data_criacao", "").strftime('%d/%m/%Y %H:%M:%S') if isinstance(s.get("data_criacao"), datetime) else ""
            ]
            ws.append(linha)

        # Resposta HTTP com arquivo Excel
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        filename = f"relatorio_solicitacoes_{mes}_{ano}.xlsx"
        response['Content-Disposition'] = f'attachment; filename={filename}'
        wb.save(response)
        print(f"API - Relatório gerado para {mes}/{ano}.")
        return response

    except Exception as e:
        print(f"API - Erro ao gerar Excel: {e}")
        return HttpResponse(f"Erro interno ao gerar Excel: {str(e)}", status=500)


def home_page(request):
    print("FRONTEND - Acessando página inicial.")
    return render(request, 'pedidos/home.html')

def pedido_list(request):
    print("FRONTEND - Acessando lista de pedidos.")
    
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))

    response_data = api_request('GET', '', params={'page': page, 'page_size': page_size})

    pedidos = []
    total = 0
    total_pages = 1

    if isinstance(response_data, dict) and "results" in response_data:
        for pedido in response_data["results"]:
            temp_numero = pedido.get('numero')
            if not temp_numero:
                temp_numero = str(pedido.get('_id', ''))
            if not temp_numero:
                temp_numero = 'INVALID_NUM'
            pedido['numero'] = temp_numero

            if 'data_criacao' in pedido and pedido['data_criacao']:
                try:
                    dt_obj = datetime.strptime(pedido['data_criacao'], '%Y-%m-%d %H:%M:%S')
                    pedido['data_criacao_formatada'] = dt_obj.strftime('%d/%m/%Y')
                except (ValueError, TypeError):
                    pedido['data_criacao_formatada'] = "Formato Inválido"
            else:
                pedido['data_criacao_formatada'] = 'N/A'
            pedidos.append(pedido)
        total = response_data.get('total', 0)
        total_pages = response_data.get('total_pages', 1)
    elif isinstance(response_data, dict) and response_data.get("error"):
        messages.error(request, response_data["message"])
        pedidos = []
    else:
        messages.error(request, "Erro inesperado na resposta da API ao listar pedidos.")
        pedidos = []
        print(f"Erro: Resposta da API não é uma lista nem um dict de erro: {response_data}")

    context = {
        'pedidos': pedidos,
        'search_query': request.GET.get('search_query', ''),
        'errors': {},
        'page': page,
        'page_size': page_size,
        'total': total,
        'total_pages': total_pages,
        'has_previous': page > 1,
        'has_next': page < total_pages,
        'previous_page': page - 1,
        'next_page': page + 1,
    }
    return render(request, 'pedidos/pedido_list.html', context)


def pedido_create(request):
    print("FRONTEND - Acessando página de criação de pedidos.")
    errors = {}

    if request.method == 'POST':
        new_data = {
            "numero": request.POST.get('numero'), 
            "descricao": request.POST.get('descricao'),
            "solicitado_por": request.POST.get('solicitado_por'),
            "safra": request.POST.get('safra'),
            "centro_custo": request.POST.get('centro_custo'),
            "status": request.POST.get('status'),
            "data": request.POST.get('data'),
            "data_recebido": request.POST.get('data_recebido'),
            "fornecedor": request.POST.get('fornecedor'),
            "nota_fiscal": request.POST.get('nota_fiscal'),
        }

        required_fields = ["numero", "descricao", "solicitado_por", "safra", "centro_custo", "status", "data"]
        for field in required_fields:
            if not new_data.get(field):
                errors[field] = ["Este campo é obrigatório."]

        if errors:
            messages.error(request, "Por favor, corrija os erros no formulário.")
            return render(request, 'pedidos/pedido_form.html',
                          {'pedido': new_data, 'errors': errors})

        data_to_send = {}
        for k, v in new_data.items():
            if v == '':
                data_to_send[k] = None
            else:
                data_to_send[k] = v

        response_data = api_request('POST', 'criar/', data=data_to_send)
        if response_data.get("error"):
            messages.error(request, response_data["message"])
            return render(request, 'pedidos/pedido_form.html',
                          {'pedido': new_data, 'errors': errors})
        else:
            messages.success(request, response_data["mensagem"])
            return redirect('pedido_list')

    return render(request, 'pedidos/pedido_form.html', {'pedido': {}, 'errors': errors})

def pedido_update(request, numero):
    print(f"FRONTEND - Acessando página de edição do pedido: {numero}")
    errors = {}

    # Busca o pedido da API
    response_data = api_request('GET', f'buscar/?numero={numero}')

    pedido_data = {}

    # Trata a resposta da API (pode vir como lista com um item, ou um dict único se a busca for exata)
    if isinstance(response_data, dict) and response_data.get("error"):
        messages.error(request, response_data.get("message", "Erro ao buscar pedido para edição."))
        return redirect('pedido_list')
    elif isinstance(response_data, dict) and not response_data.get("resultados"): # Se for um único dict e não tiver "resultados"
         pedido_data = response_data
    elif isinstance(response_data, list) and response_data:
        # Se vier uma lista, pegamos o primeiro item
        pedido_data = response_data[0]
    elif isinstance(response_data, dict) and response_data.get("resultados"): # Se a API retornar com 'resultados'
        if response_data['resultados']:
            pedido_data = response_data['resultados'][0]
        else:
            messages.error(request, f"Pedido com número {numero} não encontrado.")
            return redirect('pedido_list')
    else:
        messages.error(request, "Formato de dados inesperado da API ao buscar pedido.")
        return redirect('pedido_list')

    if not pedido_data:
        messages.error(request, f"Pedido com número {numero} não encontrado ou dados inválidos.")
        return redirect('pedido_list')

    
    temp_numero = pedido_data.get('numero') 
    if not temp_numero:
        temp_numero = str(pedido_data.get('_id', ''))
    if not temp_numero:
        temp_numero = 'INVALID_NUM'
        messages.warning(request,
                         f"Um pedido sem número ou "
                         f"_id válido foi encontrado para edição. ID: {pedido_data.get('_id', 'N/A')}")
    pedido_data['numero'] = temp_numero

    if request.method == 'POST':
        updated_data = {
            "numero": request.POST.get('numero'),
            "descricao": request.POST.get('descricao'),
            "solicitado_por": request.POST.get('solicitado_por'),
            "safra": request.POST.get('safra'),
            "centro_custo": request.POST.get('centro_custo'),
            "status": request.POST.get('status'),
            "data": request.POST.get('data'),
            "data_recebido": request.POST.get('data_recebido'),
            "fornecedor": request.POST.get('fornecedor'),
            "nota_fiscal": request.POST.get('nota_fiscal'),
        }

        required_fields = ["numero", "descricao", "solicitado_por", "safra", "centro_custo", "status", "data"]
        for field in required_fields:
            if not updated_data.get(field):
                errors[field] = ["Este campo é obrigatório."]

        if errors:
            messages.error(request, "Por favor, corrija os erros no formulário.")
            return render(request, 'pedidos/pedido_form.html',
                          {'pedido': updated_data, 'errors': errors})

        data_to_send = {}
        for k, v in updated_data.items():
            if v == '':
                data_to_send[k] = None
            else:
                data_to_send[k] = v

        response_data_update = api_request('PUT', f'atualizar/{numero}/', data=data_to_send)

        if response_data_update.get("error"):
            messages.error(request, response_data_update["message"])
            return render(request, 'pedidos/pedido_form.html',
                          {'pedido': updated_data, 'errors': errors})
        else:
            messages.success(request, response_data_update["mensagem"])
            # Se o número foi alterado, redireciona para o novo número na URL
            if updated_data['numero'] != numero:
                return redirect('pedido_update', numero=updated_data['numero'])
            return redirect('pedido_list')

    # Para GET: Formatar as datas para o input type="date" (YYYY-MM-DD)
    if 'data' in pedido_data and pedido_data['data']:
        try:
            # A API retorna no formato '%Y-%m-%d %H:%M:%S', precisamos para '%Y-%m-%d' para input type=date
            pedido_data['data'] = datetime.strptime(pedido_data['data'], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            pass
    if 'data_recebido' in pedido_data and pedido_data['data_recebido']:
        try:
            pedido_data['data_recebido'] = datetime.strptime(pedido_data['data_recebido'], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            pass
    else:
        pedido_data['data_recebido'] = "" # Garante que o campo esteja vazio se for None

    return render(request, 'pedidos/pedido_form.html', {'pedido': pedido_data, 'errors': errors})


def pedido_delete(request, numero):
    print(f"FRONTEND - Acessando página de exclusão do pedido: {numero}")

    response_data = api_request('GET', f'buscar/?numero={numero}')

    pedido = None
    if isinstance(response_data, dict) and response_data.get("error"):
        messages.error(request, response_data.get("message", "Erro ao buscar pedido para exclusão."))
        return redirect('pedido_list')
    elif isinstance(response_data, dict) and not response_data.get("resultados"):
         pedido = response_data
    elif isinstance(response_data, list) and response_data:
        pedido = response_data[0]
    elif isinstance(response_data, dict) and response_data.get("resultados"):
        if response_data['resultados']:
            pedido = response_data['resultados'][0]
        else:
            messages.error(request, f"Pedido com número {numero} não encontrado.")
            return redirect('pedido_list')
    else:
        messages.error(request, "Formato de dados inesperado da API ao buscar pedido para exclusão.")
        return redirect('pedido_list')

    if not pedido:
        messages.error(request, f"Pedido com número {numero} "
                                 f"não encontrado ou dados inválidos para exclusão.")
        return redirect('pedido_list')

    temp_numero = pedido.get('numero')
    if not temp_numero:
        temp_numero = str(pedido.get('_id', ''))
    if not temp_numero:
        temp_numero = 'INVALID_NUM'
        messages.warning(request,
                         f"Um pedido sem número ou "
                         f"_id válido foi encontrado para exclusão. ID: {pedido.get('_id', 'N/A')}")
    pedido['numero'] = temp_numero

    if request.method == 'POST':
        response_data_delete = api_request('DELETE', f'deletar/{numero}/')
        if response_data_delete.get("error"):
            messages.error(request, response_data_delete["message"])
        else:
            messages.success(request, response_data_delete["mensagem"])
        return redirect('pedido_list')

    return render(request, 'pedidos/pedido_confirm_delete.html', {'pedido': pedido})

def pedido_search(request):
    
    query = request.GET.get('q', '')
    centro_custo_query = request.GET.get('centro_custo', '')

    pedidos = []

    if not query and not centro_custo_query:
        messages.info(request, "Por favor, digite algo para pesquisar.")
        return render(request, 'pedidos/pedido_search_results.html',
                      {'pedidos': [], 'query': query, 'centro_custo_query': centro_custo_query})

    api_params = {}
    if query:
        if query.isdigit():
            api_params['numero'] = query
        else:
            api_params['palavra'] = query

    if centro_custo_query:
        api_params['centro_custo'] = centro_custo_query

    response_data = api_request('GET', 'buscar/', params=api_params)

    if isinstance(response_data, dict) and response_data.get("error"):
        messages.info(request, response_data.get("message", "Nenhum resultado encontrado para sua busca."))
        pedidos = []
    elif isinstance(response_data, dict) and response_data.get("resultados"): # Se a API retornar com 'resultados'
        pedidos = response_data['resultados']
        if not pedidos: # Se a lista de resultados estiver vazia
            messages.info(request, response_data.get("mensagem", "Nenhum resultado encontrado para sua busca."))
    elif isinstance(response_data, list): # Se a API retornar uma lista diretamente
        pedidos = response_data
    else:
        messages.error(request, "Erro inesperado na resposta da API.")
        pedidos = []
        print(f"Erro: Resposta da API não é um dict nem list: {response_data}")

    for pedido in pedidos:
        if 'data' in pedido and pedido['data']:
            try:
                # API retorna %Y-%m-%d %H:%M:%S, formatamos para %d/%m/%Y para exibição
                pedido['data'] = datetime.strptime(pedido['data'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y')
            except (ValueError, TypeError):
                pass
        if 'data_recebido' in pedido and pedido['data_recebido']:
            try:
                pedido['data_recebido'] = datetime.strptime(pedido['data_recebido'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y')
            except (ValueError, TypeError):
                pass
        else:
            pedido['data_recebido'] = "-"

        temp_numero = pedido.get('numero')
        if not temp_numero:
            temp_numero = str(pedido.get('_id', ''))
        if not temp_numero:
            temp_numero = 'INVALID_NUM' 
            messages.warning(request,
                             f"Um pedido sem número ou "
                             f"_id válido foi encontrado. ID: {pedido.get('_id', 'N/A')}")
        pedido['numero'] = temp_numero

    return render(request, 'pedidos/pedido_search_results.html',
                  {'pedidos': pedidos, 'query': query, 'centro_custo_query': centro_custo_query})
