from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload # Para carregar relacionamentos (eager loading)
from typing import List, Optional

from models import schemas # Seus schemas Pydantic
from database import DBMObjeto, DBMLocal # Seus modelos de tabela SQLAlchemy

async def get_objeto(db: AsyncSession, objeto_id: int) -> DBMObjeto | None:
    result = await db.execute(
        select(DBMObjeto)
        .options(selectinload(DBMObjeto.local_ref)) # Eager load do local associado
        .filter(DBMObjeto.id == objeto_id)
    )
    return result.scalars().first()

async def get_objetos(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100,
    nome: Optional[str] = None,
    categoria: Optional[str] = None,
    tag: Optional[str] = None, # Busca por uma tag específica dentro da string de tags
    localizacao_id: Optional[int] = None
) -> List[DBMObjeto]:
    
    query = select(DBMObjeto).options(selectinload(DBMObjeto.local_ref))

    if nome:
        query = query.filter(DBMObjeto.nome.ilike(f"%{nome}%")) # Case-insensitive search
    if categoria:
        query = query.filter(DBMObjeto.categoria.ilike(f"%{categoria}%"))
    if tag:
        # Assume que tags são armazenadas como "tag1,tag2,tag3"
        # Esta é uma busca simples. Para buscas mais complexas em tags,
        # uma tabela separada de tags ou um DB NoSQL seria melhor.
        query = query.filter(DBMObjeto.tags.ilike(f"%{tag}%"))
    if localizacao_id is not None:
        query = query.filter(DBMObjeto.localizacao_id == localizacao_id)
        
    query = query.order_by(DBMObjeto.id.desc()).offset(skip).limit(limit) # Ordenar por mais recente
    
    result = await db.execute(query)
    return result.scalars().all()

async def create_objeto(db: AsyncSession, objeto: schemas.ObjetoCreate, caminho_imagem: Optional[str] = None) -> DBMObjeto:
    # Verificar se o local_id fornecido existe, se houver
    if objeto.localizacao_id:
        local_existente = await db.get(DBMLocal, objeto.localizacao_id)
        if not local_existente:
            raise ValueError(f"Local com ID {objeto.localizacao_id} não encontrado.")

    db_objeto_data = objeto.model_dump()
    if caminho_imagem:
        db_objeto_data['caminho_imagem'] = caminho_imagem
    
    db_objeto = DBMObjeto(**db_objeto_data)
    db.add(db_objeto)
    await db.commit()
    await db.refresh(db_objeto)
    
    # Para retornar o objeto com o local carregado após a criação:
    # Poderia fazer outra consulta, ou se a sessão ainda estiver ativa e o objeto tiver o local_id,
    # o Pydantic schema pode tentar acessá-lo. Para garantir, recarregamos:
    if db_objeto.localizacao_id:
         await db.refresh(db_objeto, attribute_names=['local_ref'])

    return db_objeto

async def update_objeto(db: AsyncSession, objeto_id: int, objeto_update: schemas.ObjetoUpdate) -> DBMObjeto | None:
    db_objeto = await get_objeto(db, objeto_id) # get_objeto já carrega o local_ref
    if db_objeto is None:
        return None

    update_data = objeto_update.model_dump(exclude_unset=True)

    # Se localizacao_id está sendo atualizado, verificar se o novo local existe
    if 'localizacao_id' in update_data and update_data['localizacao_id'] is not None:
        local_existente = await db.get(DBMLocal, update_data['localizacao_id'])
        if not local_existente:
            raise ValueError(f"Novo local com ID {update_data['localizacao_id']} não encontrado.")
    
    for key, value in update_data.items():
        setattr(db_objeto, key, value)

    await db.commit()
    await db.refresh(db_objeto)
    # Se local_ref precisa ser atualizado devido a mudança no localizacao_id
    if 'localizacao_id' in update_data:
        await db.refresh(db_objeto, attribute_names=['local_ref'])
        
    return db_objeto

async def delete_objeto(db: AsyncSession, objeto_id: int) -> DBMObjeto | None:
    db_objeto = await get_objeto(db, objeto_id)
    if db_objeto is None:
        return None
    
    # Lógica para deletar a imagem associada do sistema de arquivos (importante!)
    # if db_objeto.caminho_imagem and os.path.exists(db_objeto.caminho_imagem):
    #     try:
    #         os.remove(db_objeto.caminho_imagem)
    #         print(f"Imagem {db_objeto.caminho_imagem} deletada.")
    #     except OSError as e:
    #         print(f"Erro ao deletar imagem {db_objeto.caminho_imagem}: {e}")

    await db.delete(db_objeto)
    await db.commit()
    return db_objeto # Retorna o objeto que foi deletado (sem o relacionamento, pois foi deletado)