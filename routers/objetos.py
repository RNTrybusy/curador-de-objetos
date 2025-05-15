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
import uuid # Para gerar nomes de arquivo únicos
from pathlib import Path

from models import schemas
from crud import crud_objeto, crud_local # Importar crud_local para verificar local
from database import get_db

router = APIRouter()

# Diretório base para salvar imagens
IMAGE_DIR = Path("static/images_objetos/")

@router.post("/", response_model=schemas.Objeto, status_code=status.HTTP_201_CREATED)
async def create_novo_objeto(
    nome: str = Form(...),
    descricao: Optional[str] = Form(None),
    categoria: Optional[str] = Form(None), # A IA irá sugerir, mas pode ser preenchido manualmente
    tags: Optional[str] = Form(None),      # A IA irá sugerir, mas pode ser preenchido manualmente
    localizacao_id: Optional[int] = Form(None),
    imagem: Optional[UploadFile] = File(None), # Imagem é opcional no MVP inicial
    db: AsyncSession = Depends(get_db)
):
    caminho_imagem_salva = None
    if imagem:
        if not imagem.content_type.startswith("image/"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo enviado não é uma imagem válida.")
        
        # Gerar um nome de arquivo único para evitar colisões
        extensao = Path(imagem.filename).suffix
        nome_arquivo_unico = f"{uuid.uuid4()}{extensao}"
        caminho_imagem_salva = IMAGE_DIR / nome_arquivo_unico
        
        try:
            with open(caminho_imagem_salva, "wb") as buffer:
                shutil.copyfileobj(imagem.file, buffer)
        except Exception as e:
            # Em caso de erro ao salvar, remover arquivo parcial se existir
            if caminho_imagem_salva.exists():
                os.remove(caminho_imagem_salva)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Não foi possível salvar a imagem: {str(e)}")
        finally:
            imagem.file.close() # Sempre fechar o arquivo

    # Criar o schema para o objeto
    objeto_data = schemas.ObjetoCreate(
        nome=nome,
        descricao=descricao,
        categoria=categoria,
        tags=tags,
        localizacao_id=localizacao_id
    )
    
    try:
        # O caminho_imagem_salva para o CRUD será relativo à raiz do projeto ou /static/
        # Para ser acessível via URL, deve ser como /static/images_objetos/nome_arquivo_unico
        db_objeto = await crud_objeto.create_objeto(
            db=db, 
            objeto=objeto_data, 
            caminho_imagem=str(caminho_imagem_salva.relative_to(Path("static"))).replace("\\","/") if caminho_imagem_salva else None
            # Armazenamos o caminho relativo a 'static'
        )
    except ValueError as e: # Captura erro de local_id não encontrado do CRUD
        # Se o objeto foi criado mas o local_id era inválido, e a imagem foi salva,
        # podemos querer deletar a imagem órfã aqui.
        if caminho_imagem_salva and caminho_imagem_salva.exists():
            os.remove(caminho_imagem_salva)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        if caminho_imagem_salva and caminho_imagem_salva.exists():
            os.remove(caminho_imagem_salva)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao criar objeto no banco: {str(e)}")

    return db_objeto


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