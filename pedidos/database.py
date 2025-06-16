import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()  # Carrega as variáveis do arquivo .env

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["Solicitações_db"]

# Teste de inserção
solicitacao_teste = {
    "numero": "0001",
    "descricao": "Teste de conexão com MongoDB",
    "status": "Aguardando"
}

resultado = db.solicitacoes.insert_one(solicitacao_teste)
print(f"Solicitação inserida com ID: {resultado.inserted_id}")