import flet as ft
import requests

def main(page: ft.Page):
    page.title = "Consultar Solicitação"
    page.padding = 20  # Adiciona espaçamento na tela

    numero_input = ft.TextField(label="Número da Solicitação", width=300)
    palavra_input = ft.TextField(label="Palavra na Descrição", width=300)
    resultado = ft.Text(width=500, color=ft.Colors.BLUE_700)


    def buscar_solicitacao(e):
        numero = numero_input.value
        palavra = palavra_input.value
        url = "http://127.0.0.1:8000/solicitacoes/buscar/"
        params = {}

        if numero:
            params["numero"] = numero
        if palavra:
            params["palavra"] = palavra
        
        if params:
            response = requests.get(url, params=params)
            data = response.json()
            resultado.value = data.get("mensagem", str(data))
        else:
            resultado.value = "Informe um número ou palavra para buscar."
        
        page.update()

    botao_busca = ft.ElevatedButton(text="Buscar", width=150, height=40, on_click=buscar_solicitacao)

    page.add(
        ft.Row(controls=[numero_input, palavra_input], spacing=10),  
        botao_busca,
        resultado
    )

ft.app(target=main)
