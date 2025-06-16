import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()  # Carrega as variáveis do arquivo .env

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["Solicitações_db"]

