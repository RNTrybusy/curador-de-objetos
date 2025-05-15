from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
import datetime
import os

# Usaremos SQLite para o MVP
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./curador_objetos.db")
# Para test_gemini.py, podemos usar um banco em memória:
# DATABASE_URL_TEST = "sqlite+aiosqlite:///:memory:"

# Cria a engine do SQLAlchemy.
# `echo=True` é útil para debug, pois loga as queries SQL. Remova em produção.
# `connect_args` é específico para SQLite para permitir o mesmo thread em requisições (necessário para SQLite)
# mas com aiosqlite e asyncio, isso é gerenciado de forma diferente.
# Para asyncio com aiosqlite, a configuração é mais simples.
async_engine = create_async_engine(DATABASE_URL, echo=True)

# Cria uma sessão para interagir com o banco de dados.
# expire_on_commit=False é útil com asyncio para manter os objetos acessíveis após o commit.
AsyncSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=async_engine, class_=AsyncSession, expire_on_commit=False
)

# Base para os modelos ORM
Base = declarative_base()


# --- Modelos de Tabela SQLAlchemy ---

class DBMLocal(Base): # Renomeei para DBM (Database Model) para evitar conflito com Pydantic schema
    __tablename__ = "locais"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nome = Column(String(100), unique=True, nullable=False, index=True)
    descricao = Column(Text, nullable=True)
    data_criacao = Column(DateTime, default=datetime.datetime.utcnow)
    data_atualizacao = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    objetos = relationship("DBMObjeto", back_populates="local_ref") # Renomeado para local_ref

class DBMObjeto(Base):
    __tablename__ = "objetos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nome = Column(String(100), nullable=False, index=True)
    descricao = Column(Text, nullable=True)
    categoria = Column(String(100), nullable=True, index=True)
    tags = Column(Text, nullable=True) # Armazenar como string separada por vírgulas
    caminho_imagem = Column(String(255), nullable=True) # Caminho local ou URL
    data_cadastro = Column(DateTime, default=datetime.datetime.utcnow)
    data_atualizacao = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    localizacao_id = Column(Integer, ForeignKey("locais.id"), nullable=True)
    local_ref = relationship("DBMLocal", back_populates="objetos") # Renomeado de "local" para "local_ref"


# Função para criar as tabelas no banco de dados
async def create_db_and_tables():
    async with async_engine.connect() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Cuidado: apaga tudo! Use para resetar.
        await conn.run_sync(Base.metadata.create_all)
    print("Tabelas criadas (se não existiam).")

# Dependência para obter uma sessão do banco de dados em rotas FastAPI
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()