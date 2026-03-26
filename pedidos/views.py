# C:\Users\fazin\OneDrive\Documents\Nisio\Solicita-es\pedidos\views.py

import requests
from django.shortcuts import render, redirect, reverse
from django.contrib import messages
from datetime import datetime
from .database import db 
from rest_framework.response import Response
from rest_framework.decorators import api_view
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from bson.objectid import ObjectId 
from openpyxl import Workbook
from django.utils.http import urlencode


BASE_API_URL = "http://127.0.0.1:8000/api/solicitacoes/"


def api_request(method, endpoint, data=None, params=None):
    full_url = f"{BASE_API_URL}{endpoint}"

    try:
        response = requests.request(method, full_url, json=data, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:     
        print(f"Erro na requisição API ({method} {full_url}): {e}")
        if response is not None:
            try:
                error_data = response.json().get("message", response.text)
                
            except ValueError:
                return {"error": True, "message": f"Erro na API (Resposta não JSON): {response.text}"}
        return {"error": True, "message": f"Erro de conexão com a API: {e}"}

    
def formatar_data_exibicao(data_str, formato_saida='%d/%m/%Y'):
    if not data_str or data_str == "None":
        return "-"
    try:
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.strptime(data_str, fmt).strftime(formato_saida)
            except ValueError:
                continue
        
        return data_str
    except (ValueError, TypeError):
        return "-"
    
def preparar_dados_formulario(post_data):
    return {k: (v if v.strip() != '' else None) for k, v in post_data.items() if k != 'csrfmiddlewaretoken'}


@api_view(['GET'])
def listar_solicitacoes(request):
   
    try:

        page = max(int(request.GET.get('page', 1)), 1)
        page_size = min(int(request.GET.get('page_size', 10)), 100)
        status_filtro = request.GET.get('status', None)
        skip = (page - 1) * page_size

        query_mongo = {}
        if status_filtro:
            query_mongo["status"] = status_filtro

        total = db.solicitacoes.count_documents({})
        solicitacoes_cursor = db.solicitacoes.find(query_mongo).sort('data_criacao', -1).skip(skip).limit(page_size)
        
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

        data['data_criacao'] = datetime.now() 

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
        query_params = {}
        if request.GET.get("numero"): query_params["numero"] = request.GET.get("numero")
        if request.GET.get("palavra"): query_params["descricao"] = {"$regex": request.GET.get("palavra"), "$options": "i"}
        if request.GET.get("centro_custo"): query_params["centro_custo"] = {"$regex": request.GET.get("centro_custo"), "$options": "i"}
        if request.GET.get("safra"): query_params["safra"] = request.GET.get("safra")

        solicitacoes_cursor = db.solicitacoes.find(query_params).sort('data_criacao', -1)
        resultados = []
        for solic in solicitacoes_cursor:
            solic["_id"] = str(solic["_id"])
            for k, v in solic.items():
                if isinstance(v, datetime): solic[k] = v.strftime('%Y-%m-%d %H:%M:%S')
            resultados.append(solic)
        
        return Response({"results": resultados}, status=200)
    except Exception as e:
        return Response({"mensagem": str(e)}, status=500)


@api_view(['PUT'])
def atualizar_solicitacao(request, numero):
    try:
        data = request.data
        safra = data.get('safra') or request.GET.get('safra')
        
        # Converter datas de string para objeto datetime
        for field in ['data', 'data_recebido']:
            if data.get(field):
                try: data[field] = datetime.strptime(data[field], '%Y-%m-%d')
                except: pass

        update_data = {k: v for k, v in data.items() if v is not None}
        filter_query = {"numero": numero}
        if safra: filter_query["safra"] = safra

        result = db.solicitacoes.update_one(filter_query, {"$set": update_data})
        if result.matched_count == 0:
            return Response({"mensagem": "Não encontrado"}, status=404)
        return Response({"mensagem": "Atualizado com sucesso"}, status=200)
    except Exception as e:
        return Response({"mensagem": str(e)}, status=500)

@api_view(['DELETE'])
def deletar_solicitacao(request, numero):
    try:
        db.solicitacoes.delete_one({"numero": numero})
        return Response({"mensagem": "Deletado"}, status=200)
    except Exception as e:
        return Response({"mensagem": str(e)}, status=500)


def gerar_excel_relatorio_mensal(request):
    try:
        mes, ano = request.GET.get("mes"), request.GET.get("ano")
        if not mes or not ano: return HttpResponse("Mês/Ano obrigatórios", status=400)

        inicio = datetime(int(ano), int(mes), 1)
        fim = datetime(int(ano), int(mes) + 1, 1) if int(mes) < 12 else datetime(int(ano)+1, 1, 1)

        solicitacoes = db.solicitacoes.find({"data_criacao": {"$gte": inicio, "$lt": fim}})

        wb = Workbook()
        ws = wb.active
        ws.append(["Número", "Descrição", "Solicitado Por", "Safra", "Status", "Data"])

        for s in solicitacoes:
            ws.append([
                s.get("numero", ""), s.get("descricao", ""), s.get("solicitado_por", ""),
                s.get("safra", ""), s.get("status", ""),
                s.get("data").strftime('%d/%m/%Y') if isinstance(s.get("data"), datetime) else ""
            ])

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=relatorio_{mes}_{ano}.xlsx'
        wb.save(response)
        return response
    except Exception as e:
        return HttpResponse(str(e), status=500)

def home_page(request):
    return render(request, 'pedidos/home.html')


def pedido_list(request):
    page = int(request.GET.get('page', 1))
    status_filter = request.GET.get('status', '')
    busca_texto = request.GET.get('q', '') # Captura o texto de busca também

    params = {
        'page': page,
        'page_size': 10,
        'status': status_filter,
        'q': busca_texto
    }
    
    api_res = api_request('GET', '', params=params)

    if api_res.get("error"):
        messages.error(request, api_res["message"])
        return render(request, 'pedidos/pedido_list.html', {'pedidos': []})

    pedidos = api_res.get("results", [])
    for p in pedidos:
        p['numero'] = p.get('numero') or str(p.get('_id', ''))
        p['data_formatada'] = formatar_data_exibicao(p.get('data'))

    return render(request, 'pedidos/pedido_list.html', {
        'pedidos': pedidos,
        'page': page,
        'status_selecionado': status_filter, 
        'total_pages': api_res.get('total_pages', 1),
        'has_previous': page > 1,
        'has_next': page < api_res.get('total_pages', 1),
        'previous_page': page - 1,
        'next_page': page + 1,
    })

def pedido_create(request):
    if request.method == 'POST':
        form_data = preparar_dados_formulario(request.POST)
        api_res = api_request('POST', 'criar/', data=form_data)
        
        if api_res.get("error"):
            messages.error(request, api_res["message"])
            return render(request, 'pedidos/pedido_form.html', {'pedido': form_data})
        
        messages.success(request, "Solicitação criada com sucesso!")
        return redirect('pedido_list')

    return render(request, 'pedidos/pedido_form.html', {'pedido': {}, 'errors': {}})

from django.shortcuts import render, redirect, reverse
from django.contrib import messages
from django.utils.http import urlencode

def pedido_update(request, numero):
    
    page = request.GET.get('page', '1')
    status_f = request.GET.get('status', '')
    safra = request.GET.get('safra', '')

    if request.method == 'POST':
        # Captura os dados do formulário para enviar à API
        form_data = {
            'numero': request.POST.get('numero'),
            'safra': request.POST.get('safra'),
            'descricao': request.POST.get('descricao'),
            'solicitado_por': request.POST.get('solicitado_por'),
            'centro_custo': request.POST.get('centro_custo'),
            'data': request.POST.get('data'),
            'data_recebido': request.POST.get('data_recebido'),
            'status': request.POST.get('status'),
            'fornecedor': request.POST.get('fornecedor'),
            'nota_fiscal': request.POST.get('nota_fiscal'),
        }

        api_res = api_request('PUT', f'atualizar/{numero}/', data=form_data, params={'safra': safra})

        if api_res.get("error"):
            messages.error(request, f"Erro ao atualizar: {api_res.get('message')}")
            return render(request, 'pedidos/pedido_form.html', {'pedido': form_data})

        messages.success(request, f"Solicitação {numero} atualizada com sucesso!")

        
        p_retorno = request.POST.get('page', '1')
        s_retorno = request.POST.get('status_filtro', '')

       
        base_url = reverse('pedido_list') 
        query_string = urlencode({'page': p_retorno, 'status': s_retorno})
        
        return redirect(f"{base_url}?{query_string}")

    res = api_request('GET', 'buscar/', params={'numero': numero, 'safra': safra})
    
    if not res or not res.get('results'):
        messages.error(request, "Solicitação não encontrada.")
        return redirect('pedido_list')

    pedido = res['results'][0]

    return render(request, 'pedidos/pedido_form.html', {
        'pedido': pedido,
        'current_page': page,    # Usado no botão 'Voltar' e no campo hidden
        'current_status': status_f
    })

def pedido_delete(request, numero):
    if request.method == 'POST':
        api_res = api_request('DELETE', f'deletar/{numero}/')
        if not api_res.get("error"):
            messages.success(request, "Pedido excluído.")
        return redirect('pedido_list')

    res = api_request('GET', 'buscar/', params={'numero': numero})
    pedido = res.get('results', [{}])[0]
    return render(request, 'pedidos/pedido_confirm_delete.html', {'pedido': pedido})

def pedido_search(request):
    q = request.GET.get('q', '')
    cc = request.GET.get('centro_custo', '')
    params = {'page': request.GET.get('page', 1)}
    
    if q:
        if q.isdigit(): params['numero'] = q
        else: params['palavra'] = q
    if cc: params['centro_custo'] = cc

    api_res = api_request('GET', 'buscar/', params=params)
    pedidos = api_res.get('results', [])

    for p in pedidos:
        p['data_formatada'] = formatar_data_exibicao(p.get('data'))
        p['numero'] = p.get('numero') or str(p.get('_id', ''))

    return render(request, 'pedidos/pedido_search_results.html', {
        'pedidos': pedidos,
        'query': q,
        'centro_custo_query': cc,
        'page': params['page']
    })
