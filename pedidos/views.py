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

@api_view(['POST'])
def criar_solicitacao(request):
    data = request.data
    print("API - Recebido para criar:", data)
    campos_obrigatorios = ["numero", "descricao", "solicitado_por", "safra", "centro_custo", "status"]
    for campo in campos_obrigatorios:
        if campo not in data or data[campo] is None or str(data[campo]).strip() == '':
            return Response({"mensagem": f"Campo '{campo}' é obrigatório."}, status=400)

    # Adicionar timestamp de criação
    data['data_criacao'] = datetime.now().isoformat()  # Armazena como string ISO formatada

    try:
        # Verifica unicidade do número da solicitação antes de inserir
        if db.solicitacoes.find_one({"numero": data["numero"]}):
            return Response({"mensagem": f"O número de solicitação '{data['numero']}' já existe."}, status=400)

        db.solicitacoes.insert_one(data)
        print("API - Solicitação criada com sucesso!")
        return Response({"mensagem": "Solicitação criada com sucesso!"}, status=201)
    except Exception as e:
        print(f"API - Erro ao criar solicitação: {e}")
        return Response({"mensagem": f"Erro interno ao criar solicitação: {str(e)}"}, status=500)


@api_view(['GET'])
def buscar_solicitacao(request):
    try:
        numero = request.GET.get("numero")
        palavra = request.GET.get("palavra")

        if numero:
            print(f"API - Buscando por número: {numero}")
            solicitacao = db.solicitacoes.find_one({"numero": numero})
            if solicitacao:
                solicitacao["_id"] = str(solicitacao["_id"])  # Converte ObjectId para string
                # As datas podem vir como objetos datetime do MongoDB, converta para string para API
                if 'data' in solicitacao and isinstance(solicitacao['data'], datetime):
                    solicitacao['data'] = solicitacao['data'].strftime('%Y-%m-%d %H:%M:%S')
                if 'data_recebido' in solicitacao and isinstance(solicitacao['data_recebido'], datetime):
                    solicitacao['data_recebido'] = solicitacao['data_recebido'].strftime('%Y-%m-%d %H:%M:%S')
                return Response(solicitacao)
            print(f"API - Solicitação não encontrada para número: {numero}")
            return Response({"mensagem": "Solicitação não encontrada."}, status=404)

        elif palavra:
            print(f"API - Buscando por palavra na descrição: {palavra}")
            # Para busca de texto completo, MongoDB precisa de índices de texto
            # Certifique-se de ter um índice de texto em 'descricao' ou nos campos que você quer pesquisar
            # Ex: db.solicitacoes.create_index([("descricao", "text")]) no shell do MongoDB
            solicitacoes = db.solicitacoes.find({"$text": {"$search": palavra}})
            resultados = []
            for solic in solicitacoes:
                solic["_id"] = str(solic["_id"])
                if 'data' in solic and isinstance(solic['data'], datetime):
                    solic['data'] = solic['data'].strftime('%Y-%m-%d %H:%M:%S')
                if 'data_recebido' in solic and isinstance(solic['data_recebido'], datetime):
                    solic['data_recebido'] = solic['data_recebido'].strftime('%Y-%m-%d %H:%M:%S')
                resultados.append(solic)

            if resultados:
                return Response(resultados)
            print(f"API - Nenhuma solicitação encontrada para palavra: {palavra}")
            return Response({"mensagem": "Nenhuma solicitação encontrada com essa palavra."}, status=404)

        print("API - Nenhuma busca informada.")
        return Response({"mensagem": "Informe um número ou palavra de busca."}, status=400)

    except Exception as e:
        print(f"API - Erro ao buscar no MongoDB: {e}")
        return Response({"mensagem": f"Erro interno ao buscar: {str(e)}"}, status=500)


@api_view(['PUT'])
def atualizar_solicitacao(request, numero):
    dados = request.data
    print(f"API - Recebido para atualizar {numero}:", dados)
    # Garante que o campo 'numero' não pode ser alterado
    if 'numero' in dados:
        del dados['numero']

    # Converte string de data para objeto datetime se vier do frontend
    if 'data' in dados and dados['data']:
        try:
            dados['data'] = datetime.strptime(dados['data'], '%Y-%m-%d')
        except ValueError:
            return Response({"mensagem": "Formato de 'data' inválido. Use AAAA-MM-DD."}, status=400)
    if 'data_recebido' in dados and dados['data_recebido']:
        try:
            dados['data_recebido'] = datetime.strptime(dados['data_recebido'], '%Y-%m-%d')
        except ValueError:
            return Response({"mensagem": "Formato de 'data_recebido' inválido. Use AAAA-MM-DD."}, status=400)
    elif 'data_recebido' in dados and not dados['data_recebido']:  # Se vier vazio, salva como None
        dados['data_recebido'] = None

    try:
        resultado = db.solicitacoes.update_one({"numero": numero}, {"$set": dados})

        if resultado.matched_count > 0:
            print(f"API - Solicitação {numero} atualizada com sucesso. Modificados: {resultado.modified_count}")
            return Response({"mensagem": "Solicitação atualizada com sucesso."})
        print(f"API - Solicitação {numero} não encontrada para atualização.")
        return Response({"mensagem": "Solicitação não encontrada."}, status=404)
    except Exception as e:
        print(f"API - Erro ao atualizar solicitação: {e}")
        return Response({"mensagem": f"Erro interno ao atualizar: {str(e)}"}, status=500)


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


def pedido_update(request, numero):
    print(f"FRONTEND - Acessando página de edição do pedido: {numero}")
    errors = {}
    # Primeiro, buscar o pedido existente para preencher o formulário
    response_data = api_request('GET', f'buscar/?numero={numero}')
    if response_data.get("error"):
        messages.error(request, response_data["message"])
        return redirect('pedido_list')

    pedido = response_data  # Dados do pedido existente

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

        response_data = api_request('PUT', f'atualizar/{numero}/', data=data_to_send)
        if response_data.get("error"):
            messages.error(request, response_data["message"])
            pedido.update(updated_data)
            return render(request, 'pedidos/pedido_form.html', {'pedido': pedido, 'errors': errors})
        else:
            messages.success(request, response_data["mensagem"])
            return redirect('pedido_list')

    # Para GET: Formatar as datas para o input type="date" (YYYY-MM-DD)
    # A API retorna datetime como string 'YYYY-MM-DD HH:MM:SS'
    if 'data' in pedido and pedido['data']:
        try:
            pedido['data'] = datetime.strptime(pedido['data'], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            pass  # Deixa como está se já for string correta ou outro formato
    if 'data_recebido' in pedido and pedido['data_recebido']:
        try:
            pedido['data_recebido'] = datetime.strptime(pedido['data_recebido'], '%Y-%m-%d %H:%M:%S').strftime(
                '%Y-%m-%d')
        except (ValueError, TypeError):
            pass
    else:
        pedido['data_recebido'] = ""  # Para exibir vazio no input type="date"

    return render(request, 'pedidos/pedido_form.html', {'pedido': pedido, 'errors': errors})


def pedido_delete(request, numero):
    print(f"FRONTEND - Acessando página de exclusão do pedido: {numero}")
    response_data = api_request('GET', f'buscar/?numero={numero}')
    if response_data.get("error"):
        messages.error(request, response_data["message"])
        return redirect('pedido_list')

    pedido = response_data  # Dados do pedido para confirmação

    if request.method == 'POST':
        response_data = api_request('DELETE', f'deletar/{numero}/')
        if response_data.get("error"):
            messages.error(request, response_data["message"])
        else:
            messages.success(request, response_data["mensagem"])
        return redirect('pedido_list')

    return render(request, 'pedidos/pedido_confirm_delete.html', {'pedido': pedido})


# pedidos/views.py

# ... (seus imports e outras funções) ...

def pedido_search(request):
    print("FRONTEND - Acessando página de busca de pedidos.")
    query = request.GET.get('q', '')
    pedidos = []  # Inicializa pedidos como uma lista vazia
    response_data = {}  # Inicializa response_data como um dicionário vazio

    if query:
        # A API tem duas formas de busca: 'numero' ou 'palavra'.
        if query.isdigit():
            response_data = api_request('GET', f'buscar/?numero={query}')
            # Verifica se é um dicionário e tem erro ANTES de tentar .get('error')
            if isinstance(response_data, dict) and response_data.get("error"):
                messages.info(request, "Nenhum resultado encontrado para sua busca por número.")
                pedidos = []
            elif isinstance(response_data, dict):  # Se for um dicionário e NÃO for erro, é um único resultado
                pedidos = [response_data]  # Encapsula o único resultado em uma lista
            else:  # Se não é dict, deve ser uma lista de resultados (inesperado aqui, mas para segurança)
                pedidos = response_data
                if not isinstance(pedidos, list):
                    pedidos = []  # Garante que é uma lista ou vazio
                    messages.error(request, "Erro inesperado na resposta da API para busca por número.")

            # Se não encontrou por numero ou houve erro, tenta por palavra
            if not pedidos:  # Se a busca por número não retornou nada
                response_data = api_request('GET', f'buscar/?palavra={query}')
                # A partir daqui, a lógica é a mesma para busca por palavra
                if isinstance(response_data, dict) and response_data.get("error"):
                    messages.info(request, "Nenhum resultado encontrado para sua busca por palavra-chave.")
                    pedidos = []
                elif isinstance(response_data, list):  # Se for uma lista, são os resultados
                    pedidos = response_data
                elif isinstance(response_data, dict):  # Se for um dict e não erro, é um único resultado
                    pedidos = [response_data]
                else:
                    pedidos = []  # Se for algo inesperado
                    messages.error(request, "Erro inesperado na resposta da API para busca por palavra-chave.")
        else:  # Se a query não for numérica, busca diretamente por palavra-chave
            response_data = api_request('GET', f'buscar/?palavra={query}')
            if isinstance(response_data, dict) and response_data.get("error"):
                messages.info(request, "Nenhum resultado encontrado para sua busca.")
                pedidos = []
            elif isinstance(response_data, list):
                pedidos = response_data
            elif isinstance(response_data, dict):
                pedidos = [response_data]  # Encapsula o único resultado em uma lista
            else:
                pedidos = []
                messages.error(request, "Erro inesperado na resposta da API.")

    # Formatar datas para exibição
    for pedido in pedidos:  # Este loop agora tem certeza que 'pedidos' é uma lista
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

        # Garante que 'numero' existe para usar no template
        if 'numero' not in pedido:
            pedido['numero'] = pedido.get('_id', '')  # Usa _id como fallback se 'numero' não existir

    return render(request, 'pedidos/pedido_search_results.html', {'pedidos': pedidos, 'query': query})