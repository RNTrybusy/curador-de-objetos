# main.py
import os
from fastapi import FastAPI, Depends # Adicionado Depends
from dotenv import load_dotenv
import google.generativeai as genai
from routers import locais as locais_router # Módulo do router
from fastapi.staticfiles import StaticFiles
import shutil # Para operações de arquivo
from pathlib import Path # Para manipulação de caminhos
from routers import locais as locais_router, objetos as objetos_router # Importar os routers

# Importar funções e modelos do banco de dados e schemas
from database import create_db_and_tables, get_db, AsyncSessionLocal # Adicionado AsyncSessionLocal se necessário diretamente
# Ajustar os imports dos schemas se estiverem em subpastas
# from models import schemas # Se schemas.py está em models/

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Configurar a API Key do Gemini
# (código de configuração do Gemini permanece o mesmo)
# ...

app = FastAPI(
    title="O Curador de Objetos API",
    version="0.1.0",
    description="API para o aplicativo 'O Curador de Objetos', auxiliando na catalogação e organização de itens pessoais com IA."
)

# Evento de inicialização da aplicação
@app.on_event("startup")
async def on_startup():
    print("Aplicação iniciando...")
    await create_db_and_tables()
    print("Banco de dados e tabelas verificados/criados.")
    # Configurar a API Key do Gemini aqui também pode ser uma opção
    # para garantir que só aconteça uma vez e antes de qualquer rota ser chamada.
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("API Key do Google não encontrada. Verifique o arquivo .env e a variável GOOGLE_API_KEY.")
        genai.configure(api_key=api_key)
        print("API Key do Gemini configurada com sucesso na inicialização.")
    except ValueError as e:
        print(f"Erro ao configurar a API Key na inicialização: {e}")
    except Exception as e:
        print(f"Ocorreu um erro inesperado ao configurar a API Key na inicialização: {e}")


@app.get("/")
async def read_root():
    return {"message": "Bem-vindo à API 'O Curador de Objetos'!"}

@app.get("/health")
async def health_check():
    return {"status": "API está operacional"}

@app.get("/test-gemini")
async def test_gemini_connection():
    try:
        # Teste para verificar se gemini-pro-vision está disponível
        model_to_check = 'models/gemini-pro-vision'
        model_found = False
        for m in genai.list_models():
            if m.name == model_to_check and 'generateContent' in m.supported_generation_methods:
                model_found = True
                break
        
        if not model_found:
             return {"status": f"Modelo {model_to_check} não encontrado ou não suporta 'generateContent'. Verifique sua API Key e permissões.", "available_models": [m.name for m in genai.list_models()]}

        return {"status": "Conectado ao Gemini com sucesso!", f"{model_to_check}_status": "Disponível e pronto para uso!"}
    except Exception as e:
        return {"status": "Falha ao conectar ou listar modelos do Gemini", "error": str(e)}

# Criar o diretório se não existir
Path("static/images_objetos").mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Adicionar Routers aqui ---
app.include_router(locais_router.router, prefix="/api/v1/locais", tags=["Locais"])
app.include_router(objetos_router.router, prefix="/api/v1/objetos", tags=["Objetos"])

if __name__ == "__main__":
    import uvicorn
    # O uvicorn.run não executa os eventos de startup/shutdown diretamente se chamado assim.
    # Para desenvolvimento, é melhor rodar via comando `uvicorn main:app --reload`
    # Para produção, você pode configurar o uvicorn para chamar a app factory ou usar um entrypoint diferente.
    # Por agora, foque em rodar com `uvicorn main:app --reload` no terminal.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)