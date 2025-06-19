import requests
from django.shortcuts import render, redirect
from django.contrib import messages
from datetime import datetime
from .database import db
from rest_framework.response import Response
from rest_framework.decorators import api_view
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.http import HttpResponse


def api_request(method, endpoint, data=None, params=None):
    base_url = "http://127.0.0.1:8000/api/solicitacoes/"
    full_url = f"{base_url}{endpoint}"

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
                error_data = response.json()
                return {"error": True, "message": error_data.get("mensagem", str(e))}
            except ValueError:
                return {"error": True, "message": f"Erro na API (Resposta não JSON): {response.text}"}
        return {"error": True, "message": f"Erro de conexão com a API: {e}"}


# pedidos/views.py

# ... (seus imports e outras funções) ...

@api_view(['POST'])
def criar_solicitacao(request):
    try:
        data = request.data

        # Validação de status (mantida como está)
        allowed_statuses = ["Recebido", "Aguardando", "Cancelada", "Reprovada"]
        status = data.get("status")
        if status and status not in allowed_statuses:
            return Response({"error": True,
                             "message": f"Status '{status}' inválido. Use um dos seguintes: {', '.join(allowed_statuses)}."},
                            status=400)

        # --- ALTERAÇÃO AQUI: 'numero' AGORA É UM CAMPO OBRIGATÓRIO E FORNECIDO PELO USUÁRIO ---
        required_fields = ["numero", "descricao", "solicitado_por", "safra", "centro_custo", "status", "data"]
        for field in required_fields:
            if not data.get(field):
                return Response({"error": True, "message": f"O campo '{field}' é obrigatório."}, status=400)

        # --- NOVO: Verificar se o número já existe ---
        if db.solicitacoes.find_one({"numero": data["numero"]}):
            return Response({"error": True,
                             "message": f"O número de solicitação '{data['numero']}' já existe. Por favor, escolha outro."},
                            status=409)  # 409 Conflict

        # Remover a lógica de geração de new_numero

        # Converte a data para objeto datetime (mantida como está)
        if 'data' in data and isinstance(data['data'], str):
            try:
                data['data'] = datetime.strptime(data['data'], '%Y-%m-%d')
            except ValueError:
                return Response({"error": True, "message": "Formato de data inválido para 'data'. Use YYYY-MM-DD."},
                                status=400)

        if 'data_recebido' in data and isinstance(data['data_recebido'], str) and data['data_recebido']:
            try:
                data['data_recebido'] = datetime.strptime(data['data_recebido'], '%Y-%m-%d')
            except ValueError:
                return Response(
                    {"error": True, "message": "Formato de data inválido para 'data_recebido'. Use YYYY-MM-DD."},
                    status=400)
        else:
            data['data_recebido'] = None

        data['data_criacao'] = datetime.now()

        result = db.solicitacoes.insert_one(data)
        print(f"API - Solicitação criada com ID: {result.inserted_id} e número: {data['numero']}")
        return Response(
            {"mensagem": "Solicitação criada com sucesso!", "id": str(result.inserted_id), "numero": data["numero"]},
            status=201)

    except Exception as e:
        print(f"API - Erro ao criar solicitação: {e}")
        return Response({"mensagem": f"Erro interno ao criar solicitação: {str(e)}"}, status=500)


# ... (resto das funções) ...
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
            query_params["descricao"] = {"$regex": palavra, "$options": "i"}  # Removido o '^'
            print(f"API - Buscando por descrição (contém): {palavra}")

        if centro_custo_busca:
            query_params["centro_custo"] = {"$regex": centro_custo_busca, "$options": "i"}  # Removido o '^'
            print(f"API - Buscando por centro de custo (contém): {centro_custo_busca}")

        solicitacoes = db.solicitacoes.find(query_params)
        resultados = []
        for solic in solicitacoes:
            solic["_id"] = str(solic["_id"])
            if 'data' in solic and isinstance(solic['data'], datetime):
                solic['data'] = solic['data'].strftime('%Y-%m-%d %H:%M:%S')
            if 'data_recebido' in solic and isinstance(solic['data_recebido'], datetime):
                solic['data_recebido'] = solic['data_recebido'].strftime('%Y-%m-%d %H:%M:%S')
            if 'data_criacao' in solic and isinstance(solic['data_criacao'], datetime):
                solic['data_criacao'] = solic['data_criacao'].strftime('%Y-%m-%d %H:%M:%S')
            resultados.append(solic)

        if resultados:
            print(f"API - Encontrados {len(resultados)} resultados.")
            return Response(resultados)

        print("API - Nenhuma solicitação encontrada para os critérios.")
        # Mantendo 200 OK com lista vazia para o frontend lidar de forma mais suave
        return Response({"mensagem": "Nenhuma solicitação encontrada para os critérios informados.", "resultados": []},
                        status=200)

    except Exception as e:
        print(f"API - Erro ao buscar no MongoDB: {e}")
        return Response({"mensagem": f"Erro interno ao buscar: {str(e)}"}, status=500)


# pedidos/views.py

# ... (seus imports e outras funções) ...

@api_view(['PUT'])
def atualizar_solicitacao(request, numero):  # 'numero' aqui é o número ORIGINAL do pedido
    try:
        data = request.data

        # Validação de status (mantida como está)
        allowed_statuses = ["Recebido", "Aguardando", "Cancelada", "Reprovada"]
        status = data.get("status")
        if status and status not in allowed_statuses:
            return Response({"error": True,
                             "message": f"Status '{status}' inválido. Use um dos seguintes: {', '.join(allowed_statuses)}."},
                            status=400)

        # Converte a data para objeto datetime (mantida como está)
        if 'data' in data and isinstance(data['data'], str):
            try:
                data['data'] = datetime.strptime(data['data'], '%Y-%m-%d')
            except ValueError:
                return Response({"error": True, "message": "Formato de data inválido para 'data'. Use YYYY-MM-DD."},
                                status=400)

        if 'data_recebido' in data and isinstance(data['data_recebido'], str) and data['data_recebido']:
            try:
                data['data_recebido'] = datetime.strptime(data['data_recebido'], '%Y-%m-%d')
            except ValueError:
                return Response(
                    {"error": True, "message": "Formato de data inválido para 'data_recebido'. Use YYYY-MM-DD."},
                    status=400)
        else:
            data['data_recebido'] = None

        # --- ALTERAÇÃO AQUI: Permitir a atualização do 'numero' ---
        update_data = {k: v for k, v in data.items() if v is not None and v != ''}

        # Se um novo 'numero' for fornecido e for diferente do original, verificar unicidade
        if 'numero' in update_data and update_data['numero'] != numero:
            if db.solicitacoes.find_one({"numero": update_data['numero']}):
                return Response({"error": True,
                                 "message": f"O novo número de solicitação '{update_data['numero']}' já existe. Por favor, escolha outro."},
                                status=409)

        # Se não há dados para atualizar, retorna erro
        if not update_data:
            return Response({"mensagem": "Nenhum dado fornecido para atualização."}, status=400)

        # A busca pelo pedido é feita pelo 'numero' original na URL
        # O $set irá atualizar o campo 'numero' no documento
        result = db.solicitacoes.update_one({"numero": numero}, {"$set": update_data})

        if result.matched_count == 0:
            print(f"API - Solicitação {numero} não encontrada para atualização.")
            return Response({"mensagem": f"Solicitação com número {numero} não encontrada."}, status=404)

        print(f"API - Solicitação {numero} atualizada com sucesso.")
        return Response({"mensagem": f"Solicitação {numero} atualizada com sucesso!"})

    except Exception as e:
        print(f"API - Erro ao atualizar solicitação: {e}")
        return Response({"mensagem": f"Erro interno ao atualizar solicitação: {str(e)}"}, status=500)


# ... (resto das funções) ...
@api_view(['DELETE'])
def deletar_solicitacao(request, numero):
    print(f"API - Recebido para deletar: {numero}")
    try:
        resultado = db.solicitacoes.delete_one({"numero": numero})

        if resultado.deleted_count > 0:
            print(f"API - Solicitação {numero} deletada com sucesso.")
            return Response({"mensagem": "Solicitação deletada com sucesso."})
        print(f"API - Solicitação {numero} não encontrada para deleção.")
        return Response({"mensagem": "Solicitação não encontrada."}, status=404)
    except Exception as e:
        print(f"API - Erro ao deletar solicitação: {e}")
        return Response({"mensagem": f"Erro interno ao deletar: {str(e)}"}, status=500)

@api_view(['GET'])
def listar_solicitacoes(request):
    print("API - Listando todas as solicitações.")
    try:
        solicitacoes = db.solicitacoes.find().sort("data_criacao", -1)
        resultados = []
        for solic in solicitacoes:
            solic["_id"] = str(solic["_id"])
            if 'data' in solic and isinstance(solic['data'], datetime):
                solic['data'] = solic['data'].strftime('%Y-%m-%d %H:%M:%S')
            if 'data_recebido' in solic and isinstance(solic['data_recebido'], datetime):
                solic['data_recebido'] = solic['data_recebido'].strftime('%Y-%m-%d %H:%M:%S')
            resultados.append(solic)
        print(f"API - Retornando {len(resultados)} solicitações.")
        return Response(resultados)
    except Exception as e:
        print(f"API - Erro ao listar solicitações: {e}")
        return Response({"mensagem": f"Erro interno ao listar: {str(e)}"}, status=500)

@api_view(['GET'])
def gerar_pdf_solicitacao(request):
    try:
        numero = request.GET.get("numero")
        print(f"API - Gerando PDF para solicitação número: {numero}")

        if not numero:
            return Response({"mensagem": "Informe um número para gerar o PDF."}, status=400)

        solicitacao = db.solicitacoes.find_one({"numero": numero})

        if not solicitacao:
            print(f"API - Solicitação {numero} não encontrada para PDF.")
            return Response({"mensagem": "Solicitação não encontrada."}, status=404)

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="solicitacao_{numero}.pdf"'
        p = canvas.Canvas(response, pagesize=A4)

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
            "data_criacao": "Data de Criação"  # Adicionado
        }

        ordem_campos = [
            "numero", "descricao", "solicitado_por", "safra", "centro_custo",
            "status", "data", "data_recebido", "fornecedor", "nota_fiscal", "data_criacao"
        ]

        for campo in ordem_campos:
            valor = solicitacao.get(campo)
            if campo == "data" and isinstance(valor, datetime):
                valor = valor.strftime('%d/%m/%Y')
            elif campo == "data_recebido" and isinstance(valor, datetime):
                valor = valor.strftime('%d/%m/%Y')
            elif campo == "data_criacao" and isinstance(valor, datetime):
                valor = valor.strftime('%d/%m/%Y %H:%M:%S')
            elif valor is None:
                valor = "-"

            p.drawString(100, y, f"{campos_exibicao.get(campo, campo.capitalize())}: {valor}")
            y -= 20
            if y < 100:
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

def home_page(request):
    print("FRONTEND - Acessando página inicial.")
    return render(request, 'pedidos/home.html')

def pedido_list(request):
    print("FRONTEND - Acessando lista de pedidos.")
    response_data = api_request('GET', '') # GET para a base_url (listar)

    if isinstance(response_data, dict) and response_data.get("error"):
        messages.error(request, response_data["message"])
        pedidos = []
    else:
        pedidos = response_data

        if not isinstance(pedidos, list):
            if isinstance(pedidos, dict):
                pedidos = [pedidos]
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
            if '_id' in pedido and 'numero' not in pedido:
                 pedido['numero'] = pedido.get('numero', '')
            elif 'numero' not in pedido:
                 pedido['numero'] = ''

    return render(request, 'pedidos/pedido_list.html', {'pedidos': pedidos})


# pedidos/views.py (função do frontend)

def pedido_create(request):
    print("FRONTEND - Acessando página de criação de pedidos.")
    errors = {}

    if request.method == 'POST':
        # Captura o 'numero' do formulário
        new_data = {
            "numero": request.POST.get('numero'),  # <--- Capturando o número digitado
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

        # Validação simples no frontend (adicionado 'numero')
        required_fields = ["numero", "descricao", "solicitado_por", "safra", "centro_custo", "status", "data"]
        for field in required_fields:
            if not new_data.get(field):
                errors[field] = ["Este campo é obrigatório."]

        if errors:
            messages.error(request, "Por favor, corrija os erros no formulário.")
            return render(request, 'pedidos/pedido_form.html', {'pedido': new_data, 'errors': errors})

        # Remove campos vazios para não enviar strings vazias para a API
        data_to_send = {}
        for k, v in new_data.items():
            if v == '':
                data_to_send[k] = None
            else:
                data_to_send[k] = v

        response_data = api_request('POST', 'criar/', data=data_to_send)
        if response_data.get("error"):
            messages.error(request, response_data["message"])
            return render(request, 'pedidos/pedido_form.html', {'pedido': new_data, 'errors': errors})
        else:
            messages.success(request, response_data["mensagem"])
            return redirect('pedido_list')

    return render(request, 'pedidos/pedido_form.html', {'pedido': {}, 'errors': errors})
# pedidos/views.py (função do frontend)

# pedidos/views.py (função do frontend)

# pedidos/views.py

# ... (seus imports e outras funções) ...

def pedido_update(request, numero):
    print(f"FRONTEND - Acessando página de edição do pedido: {numero}")
    errors = {}

    # Primeiro, buscar o pedido existente para preencher o formulário
    response_data = api_request('GET', f'buscar/?numero={numero}')

    # --- INÍCIO DA CORREÇÃO (mais robusta para inicialização de 'pedido') ---
    pedido_data = {}  # Inicializa como um dicionário vazio por padrão

    if isinstance(response_data, dict) and response_data.get("error"):
        messages.error(request, response_data.get("message", "Erro ao buscar pedido para edição."))
        return redirect('pedido_list')
    elif isinstance(response_data, dict):  # Se é um dicionário e não tem "error", deve ser o pedido
        pedido_data = response_data
    elif isinstance(response_data, list) and response_data:  # Se por algum motivo retornar uma lista com 1 item
        pedido_data = response_data[0]  # Pega o primeiro item da lista
    else:  # Outro caso inesperado (resposta vazia, formato errado, etc.)
        messages.error(request, "Formato de dados inesperado da API ao buscar pedido.")
        return redirect('pedido_list')

    # Se o pedido_data ainda estiver vazio após as verificações (ex: API retornou sucesso, mas sem dados)
    if not pedido_data:
        messages.error(request, f"Pedido com número {numero} não encontrado ou dados inválidos.")
        return redirect('pedido_list')

    # Agora, use 'pedido_data' para preencher o formulário
    # A variável 'pedido' que é passada para o template deve ser 'pedido_data'
    # E os próximos passos usarão 'pedido_data' no lugar de 'pedido'

    # Garantir que 'numero' sempre tenha um valor válido (não vazio) para o template
    # (Mesma lógica robusta do pedido_search)
    temp_numero = pedido_data.get('numero')  # Use pedido_data aqui
    if not temp_numero:
        temp_numero = str(pedido_data.get('_id', ''))
    if not temp_numero:
        temp_numero = 'INVALID_NUM'
        messages.warning(request,
                         f"Um pedido sem número ou _id válido foi encontrado para edição. ID: {pedido_data.get('_id', 'N/A')}")
    pedido_data['numero'] = temp_numero
    # --- FIM DA CORREÇÃO ---

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
            # Ao renderizar o form com erros do POST, use os dados do POST
            return render(request, 'pedidos/pedido_form.html',
                          {'pedido': updated_data, 'errors': errors})  # Use updated_data aqui

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
                          {'pedido': updated_data, 'errors': errors})  # Use updated_data aqui
        else:
            messages.success(request, response_data_update["mensagem"])
            return redirect('pedido_list')

    # Para GET: Formatar as datas para o input type="date"
    # A linha 479 (ou próxima) está aqui:
    if 'data' in pedido_data and pedido_data['data']:  # Use pedido_data aqui
        try:
            pedido_data['data'] = datetime.strptime(pedido_data['data'], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            pass
    if 'data_recebido' in pedido_data and pedido_data['data_recebido']:  # Use pedido_data aqui
        try:
            pedido_data['data_recebido'] = datetime.strptime(pedido_data['data_recebido'],
                                                             '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            pass
    else:
        pedido_data['data_recebido'] = ""

    return render(request, 'pedidos/pedido_form.html',
                  {'pedido': pedido_data, 'errors': errors})  # Passe pedido_data para o template


def pedido_delete(request, numero):
    print(f"FRONTEND - Acessando página de exclusão do pedido: {numero}")

    response_data = api_request('GET', f'buscar/?numero={numero}')

    pedido = None
    if isinstance(response_data, dict) and response_data.get("error"):
        messages.error(request, response_data.get("message", "Erro ao buscar pedido para exclusão."))
        return redirect('pedido_list')
    elif isinstance(response_data, dict):
        pedido = response_data
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
        messages.warning(request,
                         f"Um pedido sem número ou _id válido foi encontrado para exclusão. ID: {pedido.get('_id', 'N/A')}")
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
    else:
        pedidos = response_data
        if not isinstance(pedidos, list):
            if isinstance(pedidos, dict):
                pedidos = [pedidos]
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
                    pedido['data_recebido'] = datetime.strptime(pedido['data_recebido'], '%Y-%m-%d %H:%M:%S').strftime(
                        '%d/%m/%Y')
                except (ValueError, TypeError):
                    pass
            else:
                pedido['data_recebido'] = "-"

            temp_numero = pedido.get('numero')
            if not temp_numero:
                temp_numero = str(pedido.get('_id', ''))

            if not temp_numero:
                temp_numero = 'INVALID_NUM'  # Um valor que não é vazio e indica um problema
                messages.warning(request,
                                 f"Um pedido sem número ou _id válido foi encontrado. ID: {pedido.get('_id', 'N/A')}")

            pedido['numero'] = temp_numero

        return render(request, 'pedidos/pedido_search_results.html',
                      {'pedidos': pedidos, 'query': query, 'centro_custo_query': centro_custo_query})
