from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload # Para carregar relacionamentos se necessário no futuro

from models import schemas # Seus schemas Pydantic
from database import DBMLocal # Seu modelo de tabela SQLAlchemy

async def get_local(db: AsyncSession, local_id: int) -> DBMLocal | None:
    result = await db.execute(select(DBMLocal).filter(DBMLocal.id == local_id))
    return result.scalars().first()

async def get_local_by_nome(db: AsyncSession, nome: str) -> DBMLocal | None:
    result = await db.execute(select(DBMLocal).filter(DBMLocal.nome == nome))
    return result.scalars().first()

async def get_locais(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[DBMLocal]:
    result = await db.execute(select(DBMLocal).offset(skip).limit(limit))
    return result.scalars().all()

async def create_local(db: AsyncSession, local: schemas.LocalCreate) -> DBMLocal:
    db_local = DBMLocal(**local.model_dump()) # Usar model_dump() para Pydantic v2
    db.add(db_local)
    await db.commit()
    await db.refresh(db_local)
    return db_local

async def update_local(db: AsyncSession, local_id: int, local_update: schemas.LocalUpdate) -> DBMLocal | None:
    db_local = await get_local(db, local_id)
    if db_local is None:
        return None

    update_data = local_update.model_dump(exclude_unset=True) # Apenas campos fornecidos
    for key, value in update_data.items():
        setattr(db_local, key, value)

    await db.commit()
    await db.refresh(db_local)
    return db_local

async def delete_local(db: AsyncSession, local_id: int) -> DBMLocal | None:
    db_local = await get_local(db, local_id)
    if db_local is None:
        return None
    
    # Verificar se há objetos associados a este local antes de excluir (opcional, mas boa prática)
    # if db_local.objetos:
    #     raise ValueError("Não é possível excluir local pois existem objetos associados a ele.")

    await db.delete(db_local)
    await db.commit()
    return db_local