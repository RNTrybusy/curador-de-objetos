from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from models import schemas # Seus schemas Pydantic
from crud import crud_local # Suas funções CRUD
from database import get_db # Sua dependência de sessão do BD

router = APIRouter()

@router.post("/", response_model=schemas.Local, status_code=status.HTTP_201_CREATED)
async def create_novo_local(local: schemas.LocalCreate, db: AsyncSession = Depends(get_db)):
    db_local_existente = await crud_local.get_local_by_nome(db, nome=local.nome)
    if db_local_existente:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Local com este nome já existe")
    return await crud_local.create_local(db=db, local=local)

@router.get("/", response_model=List[schemas.Local])
async def read_locais(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    locais = await crud_local.get_locais(db, skip=skip, limit=limit)
    return locais

@router.get("/{local_id}", response_model=schemas.Local)
async def read_local(local_id: int, db: AsyncSession = Depends(get_db)):
    db_local = await crud_local.get_local(db, local_id=local_id)
    if db_local is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local não encontrado")
    return db_local

@router.put("/{local_id}", response_model=schemas.Local)
async def update_existing_local(local_id: int, local_update: schemas.LocalUpdate, db: AsyncSession = Depends(get_db)):
    # Verificar se o novo nome (se fornecido) já existe em outro local
    if local_update.nome:
        db_local_existente_com_nome = await crud_local.get_local_by_nome(db, nome=local_update.nome)
        if db_local_existente_com_nome and db_local_existente_com_nome.id != local_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Outro local com este nome já existe")

    db_local = await crud_local.update_local(db=db, local_id=local_id, local_update=local_update)
    if db_local is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local não encontrado para atualizar")
    return db_local

@router.delete("/{local_id}", response_model=schemas.Local) # Ou poderia retornar status 204 e sem corpo
async def delete_existing_local(local_id: int, db: AsyncSession = Depends(get_db)):
    # Antes de deletar, verifique se o local existe
    local_para_deletar = await crud_local.get_local(db, local_id=local_id)
    if local_para_deletar is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local não encontrado para deletar")

    # Adicionar verificação se há objetos associados, se desejado, conforme crud_local.py
    # if local_para_deletar.objetos: # Requer que a relação `objetos` seja carregada ou verificada de outra forma
    #     raise HTTPException(
    #         status_code=status.HTTP_409_CONFLICT,
    #         detail="Não é possível excluir local pois existem objetos associados a ele. Remova ou realoque os objetos primeiro."
    #     )
    
    deleted_local = await crud_local.delete_local(db=db, local_id=local_id)
    # A função crud_local.delete_local já retorna o objeto deletado ou None.
    # Se retornou None é porque não encontrou (já tratado acima).
    # Se chegou aqui, foi deletado.
    return deleted_local # Retorna o objeto deletado como confirmação.