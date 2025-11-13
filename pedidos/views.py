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
from openpyxl import Workbook


BASE_API_URL = "http://127.0.0.1:8000/api/solicitacoes/"


def api_request(method, endpoint, data=None, params=None):
    full_url = f"{BASE_API_URL}{endpoint}"

    try:
        response = None
        if method == 'GET':
            response = requests.get(full_url, params=params, timeout=10)
        elif method == 'POST':
            response = requests.post(full_url, json=data, params=params, timeout=10)
        elif method == 'PUT':
            response = requests.put(full_url, json=data, params=params, timeout=10)
        elif method == 'DELETE':
            response = requests.delete(full_url, params=params, timeout=10)
        else:
            raise ValueError("Método HTTP não suportado pela função api_request.")
        
        response.raise_for_status() 
        
        try:
            return response.json()
        except ValueError:
            return {"error": True, "message": response.text}

    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição API ({method} {full_url}): {e}")
        if response is not None and response.content:
            try:
                error_data = response.json()
                return {"error": True, "message": error_data.get("mensagem", str(e))}
            except ValueError:
                return {"error": True, "message": f"Erro na API (Resposta não JSON): {response.text}"}
        return {"error": True, "message": f"Erro de conexão com a API: {e}"}


@api_view(['GET'])
def listar_solicitacoes(request):
   
    try:

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
        data = request.data 

        allowed_statuses = ["Recebido", "Aguardando", "Cancelada", "Reprovada"]
        status_val = data.get("status") 
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
            status=201) 

    except Exception as e:
        print(f"API - Erro ao criar solicitação: {e}")
        return Response({"mensagem": f"Erro interno ao criar solicitação: {str(e)}"}, status=500)

@api_view(['GET'])
def buscar_solicitacao(request):
    try:
        numero = request.GET.get("numero")
        palavra = request.GET.get("palavra")
        centro_custo_busca = request.GET.get("centro_custo")
        safra = request.GET.get("safra")  # Novo parâmetro

        
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 10
        skip = (page - 1) * page_size

        if not numero and not palavra and not centro_custo_busca:
            return Response({"mensagem": "Informe um número, palavra-chave ou centro de custo para a busca."},
                            status=400)
        
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

        if safra:
            query_params["safra"] = safra
            print(f"API - Filtrando por safra: {safra}")

        total = db.solicitacoes.count_documents(query_params)
        solicitacoes_cursor = db.solicitacoes.find(query_params).sort('data_criacao', -1).skip(skip).limit(page_size)
        
        resultados = []
        for solic in solicitacoes_cursor:
            solic["_id"] = str(solic["_id"])
            for key, value in solic.items():
                if isinstance(value, datetime):
                    solic[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            resultados.append(solic)

        if resultados:
            print(f"API - Encontrados {len(resultados)} resultados.")
            return Response({
                "results": resultados,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }, status=200)

        print("API - Nenhuma solicitação encontrada para os critérios.")
        return Response({"mensagem": "Nenhuma solicitação encontrada para os critérios informados.", 
                        "results": []}, status=200)

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
            data['data_recebido'] = None 

        
        safra_from_request = data.get('safra') or request.GET.get('safra')

        update_data = {k: v for k, v in data.items() if v is not None and v != ''}

        
        if 'numero' in update_data and update_data['numero'] != numero:
            dup_query = {"numero": update_data['numero']}
            # se safra está sendo atualizada/fornecida, usa-a; senão usa safra_from_request se disponível
            dup_safra = update_data.get('safra') or safra_from_request
            if dup_safra:
                dup_query['safra'] = dup_safra
            if db.solicitacoes.find_one(dup_query):
                return Response({"error": True,
                                 "message": f"O novo número de solicitação "
                                            f"'{update_data['numero']}' já existe para a safra '{dup_safra or 'N/A'}'. Por favor, escolha outro."},
                                status=409)

        if not update_data:
            return Response({"mensagem": "Nenhum dado fornecido para atualização."}, status=400)

        
        filter_query = {"numero": numero}
        if safra_from_request:
            filter_query["safra"] = safra_from_request

        result = db.solicitacoes.update_one(filter_query, {"$set": update_data})

        if result.matched_count == 0:
            print(f"API - Solicitação {numero} não encontrada para atualização (filtro: {filter_query}).")
            return Response({"mensagem": f"Solicitação com número {numero} não encontrada para a safra especificada."}, status=404)

        print(f"API - Solicitação {numero} atualizada com sucesso (filtro: {filter_query}).")
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


def gerar_excel_relatorio_mensal(request):
    try:
        mes = request.GET.get("mes")  # Ex: '07' para julho
        ano = request.GET.get("ano")  # Ex: '2025'

        if not mes or not ano:
            return HttpResponse("Informe o mês e ano para gerar o relatório.", status=400)

        print(f"API - Gerando relatório para {mes}/{ano}")

       
        inicio = datetime(int(ano), int(mes), 1)
        fim = datetime(int(ano), int(mes) + 1, 1) if int(mes) < 12 else datetime(int(ano)+1, 1, 1)

        solicitacoes = db.solicitacoes.find({
            "data_criacao": {"$gte": inicio, "$lt": fim}
        })

        
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
   
    errors = {}
    safra = request.GET.get('safra', '')  # ex: /editar/5401/?safra=2025

    # Busca a solicitação exata via API (numero + safra)
    params = {'numero': numero}
    if safra:
        params['safra'] = safra
    response_data = api_request('GET', 'buscar/', params=params)

    pedido_data = {}
  
    if isinstance(response_data, dict) and response_data.get("error"):
        messages.error(request, response_data.get("message", "Erro ao buscar pedido."))
        return redirect('pedido_list')
    elif isinstance(response_data, dict) and response_data.get("results"):
        resultados = response_data.get("results", [])
        if not resultados:
            messages.error(request, f"Pedido {numero} não encontrado para a safra {safra}.")
            return redirect('pedido_list')
        pedido_data = resultados[0]
    elif isinstance(response_data, list) and response_data:
        pedido_data = response_data[0]
    else:
        messages.error(request, "Pedido não encontrado.")
        return redirect('pedido_list')

    # Normaliza número para exibição
    pedido_data['numero'] = pedido_data.get('numero') or str(pedido_data.get('_id', ''))

    if request.method == 'POST':
       
        updated_data = {
            "numero": request.POST.get('numero'),
            "descricao": request.POST.get('descricao'),
            "solicitado_por": request.POST.get('solicitado_por'),
            "safra": request.POST.get('safra') or safra,
            "centro_custo": request.POST.get('centro_custo'),
            "status": request.POST.get('status'),
            "data": request.POST.get('data'),
            "data_recebido": request.POST.get('data_recebido', ''),
            "fornecedor": request.POST.get('fornecedor'),
            "nota_fiscal": request.POST.get('nota_fiscal'),
        }

        # Validação mínima
        required_fields = ["numero", "descricao", "solicitado_por", "safra", "centro_custo", "status", "data"]
        for field in required_fields:
            if not updated_data.get(field):
                errors[field] = f"O campo '{field}' é obrigatório."

        if errors:
            messages.error(request, "Por favor, corrija os erros no formulário.")
            return render(request, 'pedidos/pedido_form.html', {'pedido': updated_data, 'errors': errors})

        # Ajusta valores vazios para None para enviar à API
        data_to_send = {k: (v if v != '' else None) for k, v in updated_data.items()}
        
        # Enviar para o endpoint correto com safra na query string
        api_response = api_request('PUT', f'atualizar/{numero}/', data=data_to_send, params={'safra': data_to_send.get('safra')})

        if isinstance(api_response, dict) and api_response.get("error"):
            messages.error(request, api_response.get("message", "Erro ao atualizar pedido."))
            errors = {'form': api_response.get("message", "Erro desconhecido")}
            return render(request, 'pedidos/pedido_form.html', {'pedido': updated_data, 'errors': errors})
        else:
            messages.success(request, f"Pedido {numero} atualizado com sucesso!")
            return redirect('pedido_list')

    # Formatar datas para inputs tipo date (GET)
    if 'data' in pedido_data and pedido_data['data']:
        try:
            dt_obj = datetime.strptime(pedido_data['data'], '%Y-%m-%d %H:%M:%S')
            pedido_data['data'] = dt_obj.strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            pass

    if 'data_recebido' in pedido_data and pedido_data['data_recebido']:
        try:
            dt_obj = datetime.strptime(pedido_data['data_recebido'], '%Y-%m-%d %H:%M:%S')
            pedido_data['data_recebido'] = dt_obj.strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            pass
    else:
        pedido_data['data_recebido'] = ""

    return render(request, 'pedidos/pedido_form.html', {'pedido': pedido_data, 'errors': errors})


def pedido_delete(request, numero):
    print(f"FRONTEND - Acessando página de exclusão do pedido: {numero}")

    response_data = api_request('GET', 'buscar/', params={'numero': numero})

    pedido = None
    if isinstance(response_data, dict) and response_data.get("error"):
        messages.error(request, response_data.get("message", "Erro ao buscar pedido para exclusão."))
        return redirect('pedido_list')
    elif isinstance(response_data, dict) and response_data.get("results"):
        resultados = response_data.get("results", [])
        if resultados:
            pedido = resultados[0]
        else:
            messages.error(request, f"Pedido com número {numero} não encontrado.")
            return redirect('pedido_list')
    elif isinstance(response_data, list) and response_data:
        pedido = response_data[0]
    else:
        messages.error(request, "Formato de dados inesperado da API ao buscar pedido para exclusão.")
        return redirect('pedido_list')

    if not pedido:
        messages.error(request, f"Pedido com número {numero} não encontrado ou dados inválidos para exclusão.")
        return redirect('pedido_list')

    temp_numero = pedido.get('numero')
    if not temp_numero:
        temp_numero = str(pedido.get('_id', ''))
    if not temp_numero:
        temp_numero = 'INVALID_NUM'
        messages.warning(request, f"Um pedido sem número ou _id válido foi encontrado para exclusão. ID: {pedido.get('_id', 'N/A')}")
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
    print("FRONTEND - Acessando página de busca de pedidos.")
    query = request.GET.get('q', '')
    centro_custo_query = request.GET.get('centro_custo', '')
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))

    pedidos = []
    total = 0
    total_pages = 1

    if not query and not centro_custo_query:
        messages.info(request, "Por favor, digite algo para pesquisar.")
        return render(request, 'pedidos/pedido_search_results.html',
                      {'pedidos': [], 'query': query, 'centro_custo_query': centro_custo_query,
                       'page': page, 'page_size': page_size, 'total': total, 'total_pages': total_pages,
                       'has_previous': False, 'has_next': False})

    api_params = {'page': page, 'page_size': page_size}
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
    elif isinstance(response_data, dict) and response_data.get("results"):
        pedidos = response_data['results']
        total = response_data.get('total', 0)
        total_pages = response_data.get('total_pages', 1)
        if not pedidos:
            messages.info(request, response_data.get("mensagem", "Nenhum resultado encontrado para sua busca."))
    elif isinstance(response_data, list):
        pedidos = response_data
        total = len(pedidos)
        total_pages = 1
    else:
        messages.error(request, "Erro inesperado na resposta da API.")
        pedidos = []
        print(f"Erro: Resposta da API não é um dict nem list: {response_data}")

    for pedido in pedidos:
        if 'data' in pedido and pedido['data']:
            try:
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
            messages.warning(request, f"Um pedido sem número ou _id válido foi encontrado. ID: {pedido.get('_id', 'N/A')}")
        pedido['numero'] = temp_numero

    context = {
        'pedidos': pedidos,
        'query': query,
        'centro_custo_query': centro_custo_query,
        'page': page,
        'page_size': page_size,
        'total': total,
        'total_pages': total_pages,
        'has_previous': page > 1,
        'has_next': page < total_pages,
        'previous_page': page - 1,
        'next_page': page + 1,
    }
    return render(request, 'pedidos/pedido_search_results.html', context)
