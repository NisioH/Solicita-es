# C:\Users\fazin\OneDrive\Documents\Nisio\Solicita-es\pedidos\views.py

import requests
from django.shortcuts import render, redirect, reverse
from django.contrib import messages
from datetime import datetime
from .database import db 
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.http import HttpResponse
from openpyxl import Workbook
from django.utils.http import urlencode

BASE_API_URL = "http://127.0.0.1:8000/api/solicitacoes/"


def api_request(method, endpoint, data=None, params=None):
    """Gerenciador central de chamadas para a API interna."""
    full_url = f"{BASE_API_URL}{endpoint}"
    response = None
    try:
        response = requests.request(method, full_url, json=data, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:     
        print(f"Erro na requisição API ({method} {full_url}): {e}")
        message = str(e)
        if response is not None:
            try:
                message = response.json().get("message", response.text)
            except ValueError:
                message = response.text
        return {"error": True, "message": message}

def formatar_data_exibicao(data_str):
    """Formata datas vindas do banco para exibição nas tabelas (DD/MM/AAAA)."""
    if not data_str or data_str == "None":
        return "-"
    try:
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y'):
            try:
                return datetime.strptime(data_str[:10], fmt).strftime('%d/%m/%Y')
            except:
                continue
        return data_str
    except:
        return "-"


@api_view(['GET'])
def listar_solicitacoes(request):
    try:
        page = max(int(request.GET.get('page', 1)), 1)
        page_size = 10
        status_filtro = request.GET.get('status', None)
        busca_texto = request.GET.get('q', None) # Captura o termo de busca
        skip = (page - 1) * page_size

        query_mongo = {}
        
        # 1. Aplica o filtro de status (se houver)
        if status_filtro:
            query_mongo["status"] = status_filtro
            
        # 2. Aplica o filtro de busca (se o usuário digitou algo)
        if busca_texto:
            if busca_texto.isdigit():
                query_mongo["numero"] = busca_texto # Busca exata pelo número
            else:
                # Busca por qualquer pedaço de palavra na descrição (case insensitive)
                query_mongo["descricao"] = {"$regex": busca_texto, "$options": "i"}

        total = db.solicitacoes.count_documents(query_mongo)
        cursor = db.solicitacoes.find(query_mongo).sort('data_criacao', -1).skip(skip).limit(page_size)
        
        solicitacoes_list = []
        for doc in cursor:
            doc['_id'] = str(doc['_id'])
            for key, value in doc.items():
                if isinstance(value, datetime):
                    doc[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            solicitacoes_list.append(doc)

        return Response({
            "results": solicitacoes_list,
            "total": total,
            "page": page,
            "total_pages": (total + page_size - 1) // page_size
        }, status=200)
    except Exception as e:
        return Response({"mensagem": str(e)}, status=500)

@api_view(['POST'])
def criar_solicitacao(request):
    try:
        data = request.data 
        required = ["numero", "descricao", "solicitado_por", "safra", "centro_custo", "status", "data"]
        
        for field in required:
            if not data.get(field):
                return Response({"error": True, "message": f"Campo '{field}' obrigatório."}, status=400)

        # Processamento de datas para o MongoDB
        for field in ['data', 'data_recebido']:
            if data.get(field):
                try:
                    data[field] = datetime.strptime(data[field][:10], '%Y-%m-%d')
                except:
                    return Response({"error": True, "message": f"Data {field} inválida."}, status=400)
            else:
                data[field] = None

        data['data_criacao'] = datetime.now() 
        db.solicitacoes.insert_one(data)
        return Response({"mensagem": "Sucesso"}, status=201) 
    except Exception as e:
        return Response({"mensagem": str(e)}, status=500)

@api_view(['PUT'])
def atualizar_solicitacao(request, numero):
    try:
        data = request.data
        safra = data.get('safra') or request.GET.get('safra')
        
        for field in ['data', 'data_recebido']:
            if data.get(field):
                try: 
                    data[field] = datetime.strptime(data[field][:10], '%Y-%m-%d')
                except: pass

        update_data = {k: v for k, v in data.items() if v is not None}
        db.solicitacoes.update_one({"numero": numero, "safra": safra}, {"$set": update_data})
        return Response({"mensagem": "Atualizado"}, status=200)
    except Exception as e:
        return Response({"mensagem": str(e)}, status=500)

@api_view(['DELETE'])
def deletar_solicitacao(request, numero):
    try:
        safra = request.GET.get('safra')
        
        filtro = {"numero": numero}
        if safra:
            filtro["safra"] = safra # Garante que apaga o pedido da safra certa

        result = db.solicitacoes.delete_one(filtro)
        
        if result.deleted_count == 0:
            return Response({"error": True, "message": "Nenhuma solicitação encontrada com esses dados."}, status=404)
            
        return Response({"mensagem": "Deletado com sucesso"}, status=200)
    except Exception as e:
        return Response({"error": True, "message": str(e)}, status=500)

@api_view(['GET'])
def buscar_solicitacao(request):
    try:
        query = {}
        if request.GET.get("numero"): query["numero"] = request.GET.get("numero")
        if request.GET.get("safra"): query["safra"] = request.GET.get("safra")
        if request.GET.get("palavra"): query["descricao"] = {"$regex": request.GET.get("palavra"), "$options": "i"}

        cursor = db.solicitacoes.find(query).sort('data_criacao', -1)
        results = []
        for s in cursor:
            s["_id"] = str(s["_id"])
            for k, v in s.items():
                if isinstance(v, datetime): s[k] = v.strftime('%Y-%m-%d %H:%M:%S')
            results.append(s)
        return Response({"results": results}, status=200)
    except Exception as e:
        return Response({"mensagem": str(e)}, status=500)


def home_page(request):
    return render(request, 'pedidos/home.html')

def pedido_list(request):
    # pega o parâmetros
    page = int(request.GET.get('page', 1))
    status_filter = request.GET.get('status', '')
    busca = request.GET.get('q', '')

    # Prepara os parâmetros 
    params = {
        'page': page,
        'page_size': 10, 
        'status': status_filter,
        'q': busca     
    }
    
    api_res = api_request('GET', '', params=params)

    # Trata pra API não quebrar
    if api_res.get("error"):
        messages.error(request, api_res["message"])
        return render(request, 'pedidos/pedido_list.html', {'pedidos': []})

    pedidos = api_res.get("results", [])
    for p in pedidos:
        p['numero'] = p.get('numero') or str(p.get('_id', ''))
        p['data_formatada'] = formatar_data_exibicao(p.get('data'))

    total_pages = api_res.get('total_pages', 1)

    return render(request, 'pedidos/pedido_list.html', {
        'pedidos': pedidos,
        'page': page,
        'status_selecionado': status_filter, 
        'busca': busca,
        'total_pages': total_pages,
        'has_previous': page > 1,
        'has_next': page < total_pages,
        'previous_page': page - 1,
        'next_page': page + 1,
    })

def pedido_create(request):
    if request.method == 'POST':
        form_data = {
            'numero': request.POST.get('numero'),
            'safra': request.POST.get('safra'),
            'descricao': request.POST.get('descricao'),
            'solicitado_por': request.POST.get('solicitado_por'),
            'centro_custo': request.POST.get('centro_custo'),
            'data': request.POST.get('data'), 
            'data_recebido': request.POST.get('data_recebido') or None,
            'status': request.POST.get('status'),
            'fornecedor': request.POST.get('fornecedor', ''),
            'nota_fiscal': request.POST.get('nota_fiscal', ''),
        }
        api_res = api_request('POST', 'criar/', data=form_data)
        if api_res.get("error"):
            messages.error(request, f"Erro: {api_res.get('message')}")
            return render(request, 'pedidos/pedido_form.html', {'pedido': form_data})

        messages.success(request, "Solicitação criada!")
        return redirect('pedido_list')

    return render(request, 'pedidos/pedido_form.html', {
        'pedido': {'data': datetime.now().strftime('%Y-%m-%d')}
    })

def pedido_update(request, numero):
    page = request.GET.get('page', '1')
    status_f = request.GET.get('status', '')
    safra = request.GET.get('safra', '')

    if request.method == 'POST':
        form_data = {
            'numero': request.POST.get('numero'),
            'safra': request.POST.get('safra'),
            'descricao': request.POST.get('descricao'),
            'solicitado_por': request.POST.get('solicitado_por'),
            'centro_custo': request.POST.get('centro_custo'),
            'data': request.POST.get('data'),
            'data_recebido': request.POST.get('data_recebido') or None,
            'status': request.POST.get('status'),
            'fornecedor': request.POST.get('fornecedor'),
            'nota_fiscal': request.POST.get('nota_fiscal'),
        }
        api_res = api_request('PUT', f'atualizar/{numero}/', data=form_data, params={'safra': safra})
        if not api_res.get("error"):
            messages.success(request, f"Solicitação {numero} atualizada!")
            query = urlencode({'page': request.POST.get('page', '1'), 'status': request.POST.get('status_filtro', '')})
            return redirect(f"{reverse('pedido_list')}?{query}")

    res = api_request('GET', 'buscar/', params={'numero': numero, 'safra': safra})
    pedido = res['results'][0]
    pedido['data'] = pedido.get('data', '')[:10]
    pedido['data_recebido'] = pedido.get('data_recebido', '')[:10] if pedido.get('data_recebido') else ""

    return render(request, 'pedidos/pedido_form.html', {
        'pedido': pedido, 'current_page': page, 'current_status': status_f
    })

def pedido_delete(request, numero):
    safra = request.GET.get('safra', '')

    if request.method == 'POST':
        api_res = api_request('DELETE', f'deletar/{numero}/', params={'safra': safra})
        
        if not api_res.get("error"):
            messages.success(request, f"Solicitação {numero} excluída com sucesso.")
        else:
            messages.error(request, f"Erro ao excluir: {api_res.get('message')}")
            
        return redirect('pedido_list')

    res = api_request('GET', 'buscar/', params={'numero': numero, 'safra': safra})
    
    pedido = {}
    if res.get('results') and len(res['results']) > 0:
        pedido = res['results'][0]
    else:
        messages.error(request, "Solicitação não encontrada para exclusão.")
        return redirect('pedido_list')

    return render(request, 'pedidos/pedido_confirm_delete.html', {
        'pedido': pedido
    })


def gerar_excel_relatorio_mensal(request):
    try:
        mes, ano = request.GET.get("mes"), request.GET.get("ano")
        if not mes or not ano: return HttpResponse("Parâmetros ausentes", status=400)
        
        inicio = datetime(int(ano), int(mes), 1)
        fim = datetime(int(ano), int(mes)+1, 1) if int(mes) < 12 else datetime(int(ano)+1, 1, 1)
        
        solicitacoes = db.solicitacoes.find({"data_criacao": {"$gte": inicio, "$lt": fim}})
        wb = Workbook()
        ws = wb.active
        ws.append(["Número", "Descrição", "Solicitado Por", "Safra", "Status", "Data"])
        
        for s in solicitacoes:
            dt = s.get("data").strftime('%d/%m/%Y') if isinstance(s.get("data"), datetime) else ""
            ws.append([s.get("numero"), s.get("descricao"), s.get("solicitado_por"), s.get("safra"), s.get("status"), dt])

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=relatorio_{mes}_{ano}.xlsx'
        wb.save(response)
        return response
    except Exception as e:
        return HttpResponse(str(e), status=500)

def pedido_search(request):
    q = request.GET.get('q', '')
    res = api_request('GET', 'buscar/', params={'palavra': q} if not q.isdigit() else {'numero': q})
    pedidos = res.get('results', [])
    for p in pedidos:
        p['data_formatada'] = formatar_data_exibicao(p.get('data'))
    return render(request, 'pedidos/pedido_search_results.html', {'pedidos': pedidos, 'query': q})