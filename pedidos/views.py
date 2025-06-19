# pedidos/views.py

import requests
from django.shortcuts import render, redirect
from django.contrib import messages
from datetime import datetime, date  # Necessário para manipular datas

# Importe 'db' do seu arquivo database.py
# Certifique-se que 'pedidos/database.py' existe e está configurado para o MongoDB
from .database import db

# Imports para as funções da API (REST Framework)
from rest_framework.response import Response
from rest_framework.decorators import api_view
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.http import HttpResponse


# --- Função auxiliar para fazer requisições à API ---
# Esta função será usada pelas views de FRONTEND para se comunicar com as views de API
def api_request(method, endpoint, data=None, params=None):
    # Constrói a URL completa da API
    # Assumimos que a API e o frontend rodam no mesmo servidor Django.
    # A URL base da API é '/api/solicitacoes/' conforme definido em solicitacoes_principal/urls.py
    base_url = "http://127.0.0.1:8000/api/solicitacoes/"  # Ajuste para o domínio real em produção
    full_url = f"{base_url}{endpoint}"

    try:
        response = None  # Inicializa response para garantir que esteja definido
        if method == 'GET':
            response = requests.get(full_url, params=params)
        elif method == 'POST':
            response = requests.post(full_url, json=data)  # Envia dados como JSON
        elif method == 'PUT':
            response = requests.put(full_url, json=data)
        elif method == 'DELETE':
            response = requests.delete(full_url)
        else:
            raise ValueError("Método HTTP não suportado pela função api_request.")

        response.raise_for_status()  # Lança um erro para status de erro (4xx ou 5xx)

        # Retorna o JSON da resposta
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição API ({method} {full_url}): {e}")
        if response is not None and response.content:
            try:
                error_data = response.json()
                return {"error": True, "message": error_data.get("mensagem", str(e))}
            except ValueError:
                # Se a resposta não for JSON, retorna o texto bruto
                return {"error": True, "message": f"Erro na API (Resposta não JSON): {response.text}"}
        return {"error": True, "message": f"Erro de conexão com a API: {e}"}


# --- FUNÇÕES DA API (com @api_view) ---
# Estas funções INTERAGEM DIRETAMENTE com o MongoDB via 'db'

# pedidos/views.py

# ... (seus imports e outras funções) ...

@api_view(['POST'])
def criar_solicitacao(request):
    try:
        data = request.data

        # --- NOVAS OPÇÕES DE STATUS ---
        allowed_statuses = ["Recebido", "Aguardando", "Cancelada", "Reprovada"]
        status = data.get("status")
        if status and status not in allowed_statuses:
            return Response({"error": True,
                             "message": f"Status '{status}' inválido. Use um dos seguintes: {', '.join(allowed_statuses)}."},
                            status=400)
        # --- FIM NOVAS OPÇÕES DE STATUS ---

        # Validação de campos obrigatórios (mantida como está)
        required_fields = ["descricao", "solicitado_por", "safra", "centro_custo", "status", "data"]
        for field in required_fields:
            if not data.get(field):
                return Response({"error": True, "message": f"O campo '{field}' é obrigatório."}, status=400)

        # Geração de número (mantida como está)
        last_solicitacao = db.solicitacoes.find_one(sort=[("numero", -1)])
        new_numero = 1
        if last_solicitacao and 'numero' in last_solicitacao:
            try:
                new_numero = int(last_solicitacao['numero']) + 1
            except ValueError:
                # Se o último número não for um inteiro, comece do 1
                new_numero = 1
        data["numero"] = str(new_numero)

        # Converte a data para objeto datetime se for string
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
            data['data_recebido'] = None  # Garante que data_recebido é None se vazio

        data['data_criacao'] = datetime.now()  # Adiciona data de criação

        result = db.solicitacoes.insert_one(data)
        print(f"API - Solicitação criada com ID: {result.inserted_id}")
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

        # Lógica de validação: Não permitir busca vazia na API
        if not numero and not palavra and not centro_custo_busca:
            return Response({"mensagem": "Informe um número, palavra-chave ou centro de custo para a busca."},
                            status=400)

        query_params = {}

        if numero:
            # Busca exata por número
            query_params["numero"] = numero
            print(f"API - Buscando por número (exato): {numero}")

        # --- CORREÇÃO AQUI: REMOVIDO O '^' PARA BUSCA POR SUBSTRING ---
        if palavra:
            # Busca parcial por descrição usando regex (case-insensitive, qualquer parte da palavra)
            query_params["descricao"] = {"$regex": palavra, "$options": "i"}  # Removido o '^'
            print(f"API - Buscando por descrição (contém): {palavra}")

        if centro_custo_busca:
            # Busca parcial por centro de custo usando regex (case-insensitive, qualquer parte da palavra)
            query_params["centro_custo"] = {"$regex": centro_custo_busca, "$options": "i"}  # Removido o '^'
            print(f"API - Buscando por centro de custo (contém): {centro_custo_busca}")
        # --- FIM DA CORREÇÃO ---

        # Se houver múltiplos critérios, o MongoDB combinará com AND por padrão
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


# ... (resto das suas funções) ...

# pedidos/views.py

# ... (seus imports e outras funções) ...

@api_view(['PUT'])
def atualizar_solicitacao(request, numero):
    try:
        data = request.data

        # --- NOVAS OPÇÕES DE STATUS ---
        allowed_statuses = ["Recebido", "Aguardando", "Cancelada", "Reprovada"]
        status = data.get("status")
        if status and status not in allowed_statuses:
            return Response({"error": True,
                             "message": f"Status '{status}' inválido. Use um dos seguintes: {', '.join(allowed_statuses)}."},
                            status=400)
        # --- FIM NOVAS OPÇÕES DE STATUS ---

        # Converte a data para objeto datetime se for string
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
            data['data_recebido'] = None  # Garante que data_recebido é None se vazio

        # Remove campos vazios ou None para não sobrescrever com valores indesejados
        update_data = {k: v for k, v in data.items() if v is not None and v != ''}

        # Não permitir atualização do número
        if 'numero' in update_data:
            del update_data['numero']

        # Se não há dados para atualizar, retorna erro
        if not update_data:
            return Response({"mensagem": "Nenhum dado fornecido para atualização."}, status=400)

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
        solicitacoes = db.solicitacoes.find().sort("data_criacao", -1)  # Ordena pela data de criação
        resultados = []
        for solic in solicitacoes:
            solic["_id"] = str(solic["_id"])  # Converte ObjectId para string
            # As datas podem vir como objetos datetime do MongoDB, converta para string para API
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

        # Criar resposta com PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="solicitacao_{numero}.pdf"'
        p = canvas.Canvas(response, pagesize=A4)

        # Adicionar título
        p.setFont("Helvetica-Bold", 14)
        p.drawString(100, 800, f"Solicitação Nº {solicitacao.get('numero', '')}")

        # Adicionar detalhes da solicitação
        p.setFont("Helvetica", 12)
        y = 780
        # Mapeamento para exibir nomes mais amigáveis e na ordem desejada
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

        # Ordenar os campos para o PDF
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
                valor = "-"  # Exibir '-' para campos vazios

            p.drawString(100, y, f"{campos_exibicao.get(campo, campo.capitalize())}: {valor}")
            y -= 20
            if y < 100:  # Se estiver chegando ao final da página, adiciona nova página
                p.showPage()
                y = 800
                p.setFont("Helvetica", 12)  # Resetar fonte para nova página

        # Finalizar PDF
        p.showPage()
        p.save()
        print(f"API - PDF gerado para solicitação {numero}.")
        return response

    except Exception as e:
        print(f"API - Erro ao gerar PDF: {e}")
        return Response({"mensagem": f"Erro interno ao gerar PDF: {str(e)}"}, status=500)


# --- FUNÇÕES DO FRONTEND (sem @api_view) ---
# Estas funções usam 'api_request' para se comunicar com as funções da API acima

# Função auxiliar para fazer requisições à API
# (Esta função já está definida no topo do arquivo, não duplique)
# def api_request(...): ...

def home_page(request):
    print("FRONTEND - Acessando página inicial.")
    return render(request, 'pedidos/home.html')


# pedidos/views.py

# ... (seus imports e outras funções acima) ...

def pedido_list(request):
    print("FRONTEND - Acessando lista de pedidos.")
    response_data = api_request('GET', '') # GET para a base_url (listar)

    # --- INÍCIO DA CORREÇÃO ---
    # Verifica se a resposta é um dicionário e contém 'error' (indicando um erro na API)
    if isinstance(response_data, dict) and response_data.get("error"):
        messages.error(request, response_data["message"])
        pedidos = []
    else:
        # Se não for um erro, esperamos que seja uma lista de pedidos
        pedidos = response_data
        # Se por algum motivo a API retornar um dicionário que não seja erro (o que é inesperado aqui),
        # ou se a API retornar um único objeto em vez de uma lista,
        # precisamos garantir que 'pedidos' seja sempre uma lista para o loop.
        if not isinstance(pedidos, list):
            # Se a API retornou um único dicionário (ex: só um item foi retornado sem ser lista)
            # encapsulamos ele em uma lista.
            if isinstance(pedidos, dict):
                pedidos = [pedidos]
            else:
                # Caso a resposta não seja nem dict nem list (algo inesperado)
                messages.error(request, "Erro inesperado na resposta da API.")
                pedidos = []
                print(f"Erro: Resposta da API não é um dict nem list: {response_data}")

        # Formatar datas para exibição (a API retorna datetime como string 'YYYY-MM-DD HH:MM:SS')
        for pedido in pedidos: # Este loop agora tem certeza que 'pedidos' é uma lista
            if 'data' in pedido and pedido['data']:
                try:
                    pedido['data'] = datetime.strptime(pedido['data'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y')
                except (ValueError, TypeError):
                    pass # Deixa como está se não conseguir formatar ou já for string
            if 'data_recebido' in pedido and pedido['data_recebido']:
                try:
                    pedido['data_recebido'] = datetime.strptime(pedido['data_recebido'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y')
                except (ValueError, TypeError):
                    pass
            else:
                pedido['data_recebido'] = "-" # Exibir "-" para data_recebido vazio
            # Garante que _id é convertido para numero para usar no template
            if '_id' in pedido and 'numero' not in pedido:
                 pedido['numero'] = pedido.get('numero', '') # Garante que 'numero' existe para ser usado no template
            elif 'numero' not in pedido: # Se 'numero' não veio e nem '_id' (improvável)
                 pedido['numero'] = '' # Define como vazio para evitar erro no template


    return render(request, 'pedidos/pedido_list.html', {'pedidos': pedidos})



def pedido_create(request):
    print("FRONTEND - Acessando página de criação de pedido.")
    errors = {}
    if request.method == 'POST':
        data = {
            "data": request.POST.get('data'),  # Data já vem como YYYY-MM-DD do input type="date"
            "descricao": request.POST.get('descricao'),
            "safra": request.POST.get('safra'),
            "numero": request.POST.get('numero'),
            "solicitado_por": request.POST.get('solicitado_por'),
            "centro_custo": request.POST.get('centro_custo'),
            "status": request.POST.get('status'),
            "data_recebido": request.POST.get('data_recebido'),  # Data já vem como YYYY-MM-DD do input type="date"
            "fornecedor": request.POST.get('fornecedor'),
            "nota_fiscal": request.POST.get('nota_fiscal'),
        }

        # Validação simples no frontend antes de enviar (opcional, mas boa UX)
        required_fields = ["numero", "descricao", "solicitado_por", "safra", "centro_custo", "status"]
        for field in required_fields:
            if not data.get(field):
                errors[field] = ["Este campo é obrigatório."]

        # O campo 'data' também é obrigatório e vem do POST
        if not data.get('data'):
            errors['data'] = ["Este campo é obrigatório."]

        if errors:
            messages.error(request, "Por favor, corrija os erros no formulário.")
            return render(request, 'pedidos/pedido_form.html', {'pedido': data, 'errors': errors})

        # Remove campos vazios para não enviar strings vazias para a API
        # A API espera None para campos opcionais não preenchidos
        data_to_send = {}
        for k, v in data.items():
            if v == '':
                data_to_send[k] = None
            else:
                data_to_send[k] = v

        response_data = api_request('POST', 'criar/', data=data_to_send)
        if response_data.get("error"):
            messages.error(request, response_data["message"])
            # Se houver um erro de validação da API (ex: número duplicado), exibe no campo específico
            if "numero" in response_data["message"].lower() and "já existe" in response_data["message"].lower():
                errors['numero'] = [response_data["message"]]
            return render(request, 'pedidos/pedido_form.html', {'pedido': data, 'errors': errors})
        else:
            messages.success(request, response_data["mensagem"])
            return redirect('pedido_list')

    return render(request, 'pedidos/pedido_form.html', {'errors': errors})


# pedidos/views.py

# ... (seus imports e outras funções) ...

def pedido_update(request, numero):
    print(f"FRONTEND - Acessando página de edição do pedido: {numero}")
    errors = {}

    # Primeiro, buscar o pedido existente para preencher o formulário
    response_data = api_request('GET', f'buscar/?numero={numero}')

    # --- INÍCIO DA CORREÇÃO ---
    pedido = None  # Inicializa pedido como None
    if isinstance(response_data, dict) and response_data.get("error"):
        messages.error(request, response_data.get("message", "Erro ao buscar pedido para edição."))
        return redirect('pedido_list')
    elif isinstance(response_data, dict):  # Se é um dicionário e não tem "error", deve ser o pedido
        pedido = response_data
    elif isinstance(response_data, list) and response_data:  # Se por algum motivo retornar uma lista com 1 item
        pedido = response_data[0]  # Pega o primeiro item da lista
    else:  # Outro caso inesperado (resposta vazia, formato errado, etc.)
        messages.error(request, "Formato de dados inesperado da API ao buscar pedido.")
        return redirect('pedido_list')

    # Se o pedido não foi encontrado ou foi pego incorretamente
    if not pedido:
        messages.error(request, f"Pedido com número {numero} não encontrado ou dados inválidos.")
        return redirect('pedido_list')

    # --- FIM DA CORREÇÃO ---

    if request.method == 'POST':
        updated_data = {
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

        # Validação simples no frontend antes de enviar
        required_fields = ["descricao", "solicitado_por", "safra", "centro_custo", "status", "data"]
        for field in required_fields:
            if not updated_data.get(field):
                errors[field] = ["Este campo é obrigatório."]

        if errors:
            messages.error(request, "Por favor, corrija os erros no formulário.")
            # Permite reexibir o formulário com os dados enviados
            pedido.update(updated_data)  # Atualiza o dict 'pedido' com os dados do POST para re-preencher o form
            return render(request, 'pedidos/pedido_form.html', {'pedido': pedido, 'errors': errors})

        # Remove campos vazios para não enviar strings vazias para a API
        data_to_send = {}
        for k, v in updated_data.items():
            if v == '':
                data_to_send[k] = None  # Envia None para campos vazios
            else:
                data_to_send[k] = v

        response_data_update = api_request('PUT', f'atualizar/{numero}/', data=data_to_send)
        if response_data_update.get("error"):  # <--- Atenção: Use response_data_update aqui
            messages.error(request, response_data_update["message"])
            pedido.update(updated_data)
            return render(request, 'pedidos/pedido_form.html', {'pedido': pedido, 'errors': errors})
        else:
            messages.success(request, response_data_update["mensagem"])
            return redirect('pedido_list')

    # Para GET: Formatar as datas para o input type="date" (YYYY-MM-DD)
    # A API retorna datetime como string 'YYYY-MM-DD HH:MM:SS'
    if 'data' in pedido and pedido['data']:
        try:
            pedido['data'] = datetime.strptime(pedido['data'], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            pass
    if 'data_recebido' in pedido and pedido['data_recebido']:
        try:
            pedido['data_recebido'] = datetime.strptime(pedido['data_recebido'], '%Y-%m-%d %H:%M:%S').strftime(
                '%Y-%m-%d')
        except (ValueError, TypeError):
            pass
    else:
        pedido['data_recebido'] = ""  # Para exibir vazio no input type="date"

    return render(request, 'pedidos/pedido_form.html', {'pedido': pedido, 'errors': errors})


# pedidos/views.py

# ... (seus imports e outras funções) ...

def pedido_delete(request, numero):
    print(f"FRONTEND - Acessando página de exclusão do pedido: {numero}")

    # --- INÍCIO DA CORREÇÃO ---
    response_data = api_request('GET', f'buscar/?numero={numero}')

    pedido = None  # Inicializa pedido como None
    if isinstance(response_data, dict) and response_data.get("error"):
        messages.error(request, response_data.get("message", "Erro ao buscar pedido para exclusão."))
        return redirect('pedido_list')
    elif isinstance(response_data, dict):  # Se é um dicionário e não tem "error", deve ser o pedido
        pedido = response_data
    elif isinstance(response_data, list) and response_data:  # Se por algum motivo retornar uma lista com 1 item
        pedido = response_data[0]  # Pega o primeiro item da lista
    else:  # Outro caso inesperado (resposta vazia, formato errado, etc.)
        messages.error(request, "Formato de dados inesperado da API ao buscar pedido para exclusão.")
        return redirect('pedido_list')

    # Se o pedido não foi encontrado ou foi pego incorretamente
    if not pedido:
        messages.error(request, f"Pedido com número {numero} não encontrado ou dados inválidos para exclusão.")
        return redirect('pedido_list')

    # Garantir que 'numero' sempre tenha um valor válido (não vazio) para o template
    # (Mesma lógica robusta do pedido_search)
    temp_numero = pedido.get('numero')
    if not temp_numero:  # Se 'numero' não existe ou é vazio
        temp_numero = str(pedido.get('_id', ''))  # Tenta usar '_id' (convertido para string)
    if not temp_numero:  # Se mesmo depois de tentar '_id', ainda for vazio, use um placeholder
        temp_numero = 'INVALID_NUM'
        messages.warning(request,
                         f"Um pedido sem número ou _id válido foi encontrado para exclusão. ID: {pedido.get('_id', 'N/A')}")
    pedido['numero'] = temp_numero
    # --- FIM DA CORREÇÃO ---

    if request.method == 'POST':
        response_data_delete = api_request('DELETE', f'deletar/{numero}/')  # Renomeado para clareza
        if response_data_delete.get("error"):  # <--- Atenção: Usar response_data_delete aqui
            messages.error(request, response_data_delete["message"])
        else:
            messages.success(request, response_data_delete["mensagem"])
        return redirect('pedido_list')

    return render(request, 'pedidos/pedido_confirm_delete.html', {'pedido': pedido})

def pedido_search(request):
    print("FRONTEND - Acessando página de busca de pedidos.")
    query = request.GET.get('q', '')
    centro_custo_query = request.GET.get('centro_custo', '')  # Captura o novo campo de busca

    pedidos = []

    # --- NOVA LÓGICA: NÃO PERMITIR BUSCA COM CAMPO VAZIO NO FRONTEND ---
    if not query and not centro_custo_query:
        messages.info(request, "Por favor, digite algo para pesquisar.")
        # Retorna o template vazio, sem fazer chamada à API
        return render(request, 'pedidos/pedido_search_results.html',
                      {'pedidos': [], 'query': query, 'centro_custo_query': centro_custo_query})
    # --- FIM DA NOVA LÓGICA ---

    api_params = {}
    if query:
        # A API buscar_solicitacao agora lida com busca por numero exato
        # ou por palavra parcial na descrição.
        # Se for um número, tentaremos buscar por número
        if query.isdigit():
            api_params['numero'] = query
        else:  # Caso contrário, tratamos como palavra na descrição
            api_params['palavra'] = query

    if centro_custo_query:
        api_params['centro_custo'] = centro_custo_query

    # Faz a chamada à API com os parâmetros construídos
    response_data = api_request('GET', 'buscar/', params=api_params)

    # ... (o restante da lógica para lidar com response_data é a mesma da versão anterior,
    #      já corrigida para lidar com listas/dicionários de erro) ...

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

    # Formatar datas para exibição
        # pedidos/views.py

        # ... (código anterior da pedido_search) ...

        # Formatar datas para exibição e garantir 'numero'
        for pedido in pedidos:
            # --- Lógica de formatação de datas (mantida como está) ---
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
            # --- Fim da lógica de formatação de datas ---

            # --- CORREÇÃO AQUI: GARANTIR QUE 'numero' NUNCA SEJA VAZIO ---
            # Tenta pegar o 'numero' existente ou '_id' como fallback
            temp_numero = pedido.get('numero')
            if not temp_numero:  # Se 'numero' não existe ou é vazio
                temp_numero = str(pedido.get('_id', ''))  # Tenta usar '_id' (convertido para string)

            # Se mesmo depois de tentar '_id', ainda for vazio, use um placeholder
            if not temp_numero:
                temp_numero = 'INVALID_NUM'  # Um valor que não é vazio e indica um problema
                messages.warning(request,
                                 f"Um pedido sem número ou _id válido foi encontrado. ID: {pedido.get('_id', 'N/A')}")

            pedido['numero'] = temp_numero
            # --- FIM DA CORREÇÃO REFORÇADA ---

        return render(request, 'pedidos/pedido_search_results.html',
                      {'pedidos': pedidos, 'query': query, 'centro_custo_query': centro_custo_query})