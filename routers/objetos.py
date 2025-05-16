# routers/objetos.py
from fastapi import (
    APIRouter, 
    Depends, 
    HTTPException, 
    status, 
    UploadFile, 
    File, 
    Form
)
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import shutil
import os
import uuid
from pathlib import Path
import google.generativeai as genai # Importar a biblioteca do Gemini
from PIL import Image # Para manipulação de imagem se necessário (ex: converter formato)

from models import schemas
from crud import crud_objeto # crud_local não é diretamente usado aqui, mas sim no crud_objeto
from database import get_db

router = APIRouter()

IMAGE_DIR = Path("static/images_objetos/")

# Função auxiliar para processar a resposta do Gemini (pode ser movida para um utils.py)
def parse_gemini_response_for_curation(response_text: str) -> tuple[Optional[str], Optional[str]]:
    sugestao_categoria = None
    sugestao_tags_str = None

    # Limpar possíveis marcadores de markdown para JSON
    clean_response_text = response_text.strip()
    if clean_response_text.startswith("```json"):
        clean_response_text = clean_response_text[len("```json"):]
    if clean_response_text.endswith("```"):
        clean_response_text = clean_response_text[:-len("```")]
    clean_response_text = clean_response_text.strip() # Remover espaços em branco extras

    print(f"Texto limpo para parsear JSON: {clean_response_text!r}")

    try:
        import json
        data = json.loads(clean_response_text) # Usar o texto limpo
        sugestao_categoria = data.get("categoria")
        tags_list = data.get("tags")
        
        # descricao_ia = data.get("descricao_ia") # Você pode querer usar isso também
        # print(f"Descrição da IA: {descricao_ia}")

        if isinstance(tags_list, list):
            sugestao_tags_str = ", ".join(tag.strip() for tag in tags_list if tag.strip()) # Garante que tags não sejam vazias
        elif isinstance(tags_list, str):
             sugestao_tags_str = tags_list.strip()
        
        print(f"JSON Parse - Categoria: {sugestao_categoria!r}, Tags: {sugestao_tags_str!r}")

    except json.JSONDecodeError as e_json:
        print(f"Falha ao parsear JSON: {e_json}. Tentando parsing por linha.")
        # Fallback para parsing por linha (mantenha como estava ou melhore)
        lines = response_text.lower().split('\n') # Usar response_text original para fallback
        for line in lines:
            if "categoria:" in line: # Mais flexível que startswith
                sugestao_categoria = line.split("categoria:", 1)[1].strip().capitalize()
            elif "tags:" in line:
                sugestao_tags_str = line.split("tags:", 1)[1].strip()
        print(f"Line Parse - Categoria: {sugestao_categoria!r}, Tags: {sugestao_tags_str!r}")
    
    if sugestao_categoria:
        sugestao_categoria = sugestao_categoria.strip()
        if sugestao_categoria:
            sugestao_categoria = sugestao_categoria[0].upper() + sugestao_categoria[1:]

    if sugestao_tags_str:
        sugestao_tags_str = sugestao_tags_str.strip()
        if not sugestao_tags_str: # Se ficou vazia após strip
            sugestao_tags_str = None


    return sugestao_categoria, sugestao_tags_str


@router.post("/", response_model=schemas.ObjetoComSugestoes, status_code=status.HTTP_201_CREATED) # Alterado response_model
async def create_novo_objeto(
    nome: str = Form(...),
    descricao: Optional[str] = Form(None),
    # categoria e tags agora são primariamente da IA, mas o usuário pode sobrescrever/editar depois
    # Por isso, não os pegamos diretamente do Form aqui para serem preenchidos pela IA
    localizacao_id: Optional[int] = Form(None),
    imagem: UploadFile = File(...), # Tornar imagem obrigatória para sugestão da IA
    db: AsyncSession = Depends(get_db)
):
    if not imagem.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo enviado não é uma imagem válida.")

    caminho_imagem_salva = None
    sugestao_categoria_ia = None
    sugestao_tags_ia_str = None # Tags como string

    try:
        # 1. Salvar a imagem
        extensao = Path(imagem.filename).suffix
        if not extensao.lower() in ['.png', '.jpg', '.jpeg', '.webp']:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Formato de imagem não suportado. Use PNG, JPG, JPEG ou WEBP.")

        nome_arquivo_unico = f"{uuid.uuid4()}{extensao}"
        caminho_imagem_salva = IMAGE_DIR / nome_arquivo_unico
        
        # Ler o conteúdo da imagem para enviar ao Gemini e para salvar
        image_bytes = await imagem.read() # Lê todo o conteúdo do arquivo em memória
        await imagem.seek(0) # Reposiciona o cursor do arquivo para o início para o shutil.copyfileobj

        with open(caminho_imagem_salva, "wb") as buffer:
            shutil.copyfileobj(imagem.file, buffer)
        
        # 2. Interagir com a API Gemini
        try:
            # Escolher o modelo Vision
            # Verifique o nome exato do modelo na sua lista de modelos disponíveis (via /test-gemini)
            model = genai.GenerativeModel('models/gemini-2.0-flash') 
            
            # Preparar a parte da imagem para o prompt multimodal
            image_part = {
                "mime_type": imagem.content_type,
                "data": image_bytes 
            }

            # Prompt para o Gemini
            # Ajuste este prompt para obter os melhores resultados!
            # Peça explicitamente por JSON para facilitar o parsing.
            prompt_parts = [
                image_part,
                "\n\nDescreva este objeto, sugira uma categoria principal e até 5 tags relevantes. ",
                "Formato da resposta desejado (JSON):\n",
                "{\n",
                "  \"descricao_ia\": \"Uma breve descrição do objeto principal na imagem.\",\n",
                "  \"categoria\": \"Nome da Categoria Sugerida\",\n",
                "  \"tags\": [\"tag1\", \"tag2\", \"tag3\"]\n",
                "}"
            ]
            
            print("Enviando requisição para o Gemini Vision...")
            response = await model.generate_content_async(prompt_parts) # Usar versão async
            print("Resposta do Gemini recebida.")

            if response.parts:
                response_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
                print(f"Texto da resposta Gemini (bruto): {response_text!r}") # Use !r para ver aspas, etc.
                
                parsed_categoria, parsed_tags_str = parse_gemini_response_for_curation(response_text)
                
                print(f"Parseado - Categoria: {parsed_categoria!r}")
                print(f"Parseado - Tags String: {parsed_tags_str!r}")

                sugestao_categoria_ia = parsed_categoria # Atribuição explícita
                sugestao_tags_ia_str = parsed_tags_str   # Atribuição explícita
            else:
                print("Resposta do Gemini não continha 'parts' utilizáveis ou foi bloqueada.")

        except Exception as e_gemini:
            print(f"Erro ao interagir com a API Gemini: {e_gemini}")
            # Aqui, sugestao_categoria_ia e sugestao_tags_ia_str permanecem com seus
            # valores iniciais (None), o que é correto para o caso de erro.

        # 3. Criar o objeto no banco com as sugestões (ou sem, se falhar)
        # ESTA PARTE PRECISA GARANTIR QUE OS VALORES DA IA SEJAM USADOS
        print(f"ANTES de criar ObjetoData - Categoria IA: {sugestao_categoria_ia!r}")
        print(f"ANTES de criar ObjetoData - Tags IA: {sugestao_tags_ia_str!r}")

        objeto_data = schemas.ObjetoCreate(
            nome=nome,
            descricao=descricao, # Descrição manual do usuário
            categoria=sugestao_categoria_ia, # DEVE USAR o valor parseado
            tags=sugestao_tags_ia_str,       # DEVE USAR o valor parseado
            localizacao_id=localizacao_id
        )
        
        caminho_relativo_imagem = str(caminho_imagem_salva.relative_to(Path("static"))).replace("\\","/") if caminho_imagem_salva else None
        
        db_objeto = await crud_objeto.create_objeto(
            db=db, 
            objeto=objeto_data, 
            caminho_imagem=caminho_relativo_imagem
        )

        # Retornar ObjetoComSugestoes
        return schemas.ObjetoComSugestoes(
            sugestao_categoria=sugestao_categoria_ia,
            sugestao_tags=sugestao_tags_ia_str.split(", ") if sugestao_tags_ia_str else [], # Converte string de tags para lista
            objeto_parcial=schemas.Objeto( # Retorna o objeto completo como foi salvo
                id=db_objeto.id,
                nome=db_objeto.nome,
                descricao=db_objeto.descricao,
                categoria=db_objeto.categoria,
                tags=db_objeto.tags,
                localizacao_id=db_objeto.localizacao_id,
                data_cadastro=db_objeto.data_cadastro,
                caminho_imagem=db_objeto.caminho_imagem,
                local= await crud_local.get_local(db, db_objeto.localizacao_id) if db_objeto.localizacao_id else None # Carregar local
            )
        )

    except HTTPException: # Re-lançar HTTPExceptions para que o FastAPI as trate
        raise
    except ValueError as e_val: # Captura erro de local_id não encontrado do CRUD
        if caminho_imagem_salva and caminho_imagem_salva.exists():
            os.remove(caminho_imagem_salva)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e_val))
    except Exception as e_geral:
        if caminho_imagem_salva and caminho_imagem_salva.exists():
            os.remove(caminho_imagem_salva)
        print(f"Erro geral ao criar objeto: {e_geral}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro interno ao processar o objeto: {str(e_geral)}")
    finally:
        if 'imagem' in locals() and hasattr(imagem, 'file') and imagem.file: # Garantir que imagem e imagem.file existem
            imagem.file.close()


@router.get("/", response_model=List[schemas.Objeto])
async def read_all_objetos(
    skip: int = 0, 
    limit: int = 100, 
    nome: Optional[str] = None,
    categoria: Optional[str] = None,
    tag: Optional[str] = None,
    localizacao_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    objetos = await crud_objeto.get_objetos(db, skip, limit, nome, categoria, tag, localizacao_id)
    return objetos

@router.get("/{objeto_id}", response_model=schemas.Objeto)
async def read_single_objeto(objeto_id: int, db: AsyncSession = Depends(get_db)):
    db_objeto = await crud_objeto.get_objeto(db, objeto_id=objeto_id)
    if db_objeto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objeto não encontrado")
    return db_objeto

@router.put("/{objeto_id}", response_model=schemas.Objeto)
async def update_existing_objeto(
    objeto_id: int, 
    objeto_update: schemas.ObjetoUpdate, # Recebe como JSON normal
    db: AsyncSession = Depends(get_db)
):
    # Nota: Este endpoint não suporta atualização de imagem por simplicidade no MVP.
    # Para atualizar imagem, seria um endpoint separado ou lógica mais complexa aqui.
    try:
        updated_objeto = await crud_objeto.update_objeto(db=db, objeto_id=objeto_id, objeto_update=objeto_update)
    except ValueError as e: # Captura erro de local_id não encontrado do CRUD
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if updated_objeto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objeto não encontrado para atualizar")
    return updated_objeto

@router.delete("/{objeto_id}", response_model=schemas.Objeto)
async def delete_existing_objeto(objeto_id: int, db: AsyncSession = Depends(get_db)):
    db_objeto = await crud_objeto.get_objeto(db, objeto_id=objeto_id) # get_objeto para pegar o caminho_imagem
    if db_objeto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objeto não encontrado para deletar")

    caminho_imagem_a_deletar = db_objeto.caminho_imagem

    deleted_objeto_data = await crud_objeto.delete_objeto(db=db, objeto_id=objeto_id)
    
    # Se o objeto foi deletado do banco com sucesso e tinha uma imagem
    if deleted_objeto_data and caminho_imagem_a_deletar:
        caminho_completo = Path("static") / caminho_imagem_a_deletar
        if caminho_completo.exists():
            try:
                os.remove(caminho_completo)
                print(f"Imagem {caminho_completo} deletada com sucesso.")
            except OSError as e:
                print(f"Erro ao tentar deletar a imagem {caminho_completo}: {e}")
                # Considerar logar este erro, pois o objeto no DB foi removido.
    
    return deleted_objeto_data