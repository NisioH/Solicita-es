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

# --- Configuração da URL base da API ---
# A API e o frontend estão no mesmo projeto/servidor, então a porta é a mesma (8000)
BASE_API_URL = "http://127.0.0.1:8000/api/solicitacoes/"

# --- Função auxiliar para requisições à API (chamando a si mesma) ---
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
        
        # Levanta um HTTPError para respostas de status 4xx/5xx
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



## Funções de API (Endpoints REST)

#Estas funções são destinadas a serem chamadas por outros serviços ou pelo seu próprio frontend via `api_request`. Elas retornam dados JSON.

#```python

@api_view(['GET'])
def listar_solicitacoes(request):
    """
    Lista todas as solicitações do MongoDB, ordenadas pelas mais recentes primeiro.
    Retorna uma lista de objetos JSON.
    """
    try:
        # Adiciona .sort('data_criacao', -1) para ordenar por 'data_criacao'
        # em ordem decrescente (-1 para mais recente primeiro)
        solicitacoes_cursor = db.solicitacoes.find({}).sort('data_criacao', -1)
        solicitacoes_list = []
        for doc in solicitacoes_cursor:
            # Converte ObjectId para string para JSON
            doc['_id'] = str(doc['_id'])

            # Formata objetos datetime para strings ISO 8601 para JSON
            for key, value in doc.items():
                if isinstance(value, datetime):
                    doc[key] = value.strftime('%Y-%m-%d %H:%M:%S')

            solicitacoes_list.append(doc)

        return Response(solicitacoes_list, status=200)

    except Exception as e:
        print(f"API - Erro ao listar solicitações: {e}")
        return Response({"mensagem": f"Erro interno ao listar solicitações: {str(e)}"}, status=500)

@api_view(['POST'])
def criar_solicitacao(request):
    """
    Cria uma nova solicitação no MongoDB.
    Recebe dados JSON no corpo da requisição.
    """
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

        # --- AQUI ESTÁ A CORREÇÃO PRINCIPAL ---
        # A validação agora checa se existe uma solicitação com o MESMO NÚMERO E a MESMA SAFRA.
        existing_solicitation = db.solicitacoes.find_one({
            "numero": data["numero"],
            "safra": data["safra"]
        })

        if existing_solicitation:
            return Response({"error": True,
                             "message": f"Já existe uma solicitação com o número '{data['numero']}' "
                                        f"para a safra '{data['safra']}'. Por favor, verifique ou use outra combinação."},
                            status=409) # 409 Conflict - indica conflito de recurso
        # --- FIM DA CORREÇÃO ---


        # Converter strings de data para objetos datetime, se existirem
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


@api_view(['GET'])
def buscar_solicitacao(request):
    """
    Busca solicitações no MongoDB por número, palavra-chave na descrição ou centro de custo.
    Retorna uma lista de objetos JSON.
    """
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
            solic["_id"] = str(solic["_id"]) # Converte ObjectId para string
            # Formata objetos datetime para strings ISO 8601
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

@api_view(['PUT'])
def atualizar_solicitacao(request, numero):
    """
    Atualiza uma solicitação existente no MongoDB pelo número.
    Recebe dados JSON no corpo da requisição.
    """
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
    """
    Deleta uma solicitação do MongoDB pelo número.
    """
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

@api_view(['GET'])
def gerar_pdf_solicitacao(request):
    """
    Gera um PDF para uma solicitação específica.
    """
    try:
        numero = request.GET.get("numero")
        print(f"API - Gerando PDF para solicitação número: {numero}")

        if not numero:
            return Response({"mensagem": "Informe um número para gerar o PDF."}, status=400)

        solicitacao = db.solicitacoes.find_one({"numero": numero})

        if not solicitacao:
            print(f"API - Solicitação {numero} não encontrada para PDF.")
            return Response({"mensagem": "Solicitação não encontrada."}, status=404)

        # Configuração da resposta HTTP para PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="solicitacao_{numero}.pdf"'
        p = canvas.Canvas(response, pagesize=A4)

        # Conteúdo do PDF
        p.setFont("Helvetica-Bold", 14)
        p.drawString(100, 800, f"Solicitação Nº {solicitacao.get('numero', '')}")

        p.setFont("Helvetica", 12)
        y = 780
        campos_exibicao = {
            "numero": "Número",
            "descricao": "Descrição",
            "solicitado_por": "Solicitado Por",
            "safra": "Safra",
            "centro_custo": "Centro de Custo",
            "status": "Status",
            "data": "Data da Solicitação",
            "data_recebido": "Data Recebido",
            "fornecedor": "Fornecedor",
            "nota_fiscal": "Nota Fiscal",
            "data_criacao": "Data de Criação"
        }

        ordem_campos = [
            "numero", "descricao", "solicitado_por", "safra", "centro_custo",
            "status", "data", "data_recebido", "fornecedor", "nota_fiscal", "data_criacao"
        ]

        for campo in ordem_campos:
            valor = solicitacao.get(campo)
            if isinstance(valor, datetime):
                # Formata datas para exibição no PDF
                if campo == "data_criacao":
                    valor = valor.strftime('%d/%m/%Y %H:%M:%S')
                else:
                    valor = valor.strftime('%d/%m/%Y')
            elif valor is None:
                valor = "-"

            p.drawString(100, y, f"{campos_exibicao.get(campo, campo.capitalize())}: {valor}")
            y -= 20
            if y < 100: # Nova página se o conteúdo exceder
                p.showPage()
                y = 800
                p.setFont("Helvetica", 12)

        p.showPage()
        p.save()
        print(f"API - PDF gerado para solicitação {numero}.")
        return response

    except Exception as e:
        print(f"API - Erro ao gerar PDF: {e}")
        return Response({"mensagem": f"Erro interno ao gerar PDF: {str(e)}"}, status=500)

## Funções do Frontend (Renderizam Páginas HTML)

#Estas funções são responsáveis por processar as requisições do navegador e renderizar os templates HTML.

#```python
def home_page(request):
    print("FRONTEND - Acessando página inicial.")
    return render(request, 'pedidos/home.html')

def pedido_list(request):
    print("FRONTEND - Acessando lista de pedidos.")
    # Chama o endpoint da API interna para obter os dados em JSON
    response_data = api_request('GET', '') 

    pedidos = []
    if isinstance(response_data, list):
        for pedido in response_data:
            # Garante que 'numero' sempre tenha um valor válido para o template
            temp_numero = pedido.get('numero')
            if not temp_numero:
                temp_numero = str(pedido.get('_id', ''))
            if not temp_numero:
                temp_numero = 'INVALID_NUM'
            pedido['numero'] = temp_numero # Atualiza o 'numero' no dicionário do pedido

            # Formatar APENAS a data de criação para exibição no HTML
            if 'data_criacao' in pedido and pedido['data_criacao']:
                try:
                    # A API envia 'YYYY-MM-DD HH:MM:SS', então parseamos assim
                    dt_obj = datetime.strptime(pedido['data_criacao'], '%Y-%m-%d %H:%M:%S')
                    pedido['data_criacao_formatada'] = dt_obj.strftime('%d/%m/%Y') # Ex: 23/06/2025
                except (ValueError, TypeError):
                    pedido['data_criacao_formatada'] = "Formato Inválido"
            else:
                pedido['data_criacao_formatada'] = 'N/A' # Se não houver data de criação ou for nula
            
            pedidos.append(pedido)
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

    # Garantir que 'numero' exista, mesmo que seja 'INVALID_NUM'
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
    print("FRONTEND - Acessando página de busca de pedidos.")
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