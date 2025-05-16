from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# --- Modelos para Locais ---
class LocalBase(BaseModel):
    nome: str = Field(..., min_length=1, max_length=100, examples=["Escritório", "Gaveta da Cômoda"])
    descricao: Optional[str] = Field(None, max_length=255, examples=["Mesa principal do escritório", "Primeira gaveta à esquerda"])

class LocalCreate(LocalBase):
    pass

class LocalUpdate(BaseModel): # Permite atualização parcial
    nome: Optional[str] = Field(None, min_length=1, max_length=100)
    descricao: Optional[str] = Field(None, max_length=255)

class Local(LocalBase): # Para leitura (resposta da API)
    id: int
    # Se quisermos adicionar a contagem de objetos por local no futuro:
    # num_objetos: Optional[int] = 0

    class Config:
        from_attributes = True # Antigo orm_mode = True


# --- Modelos para Objetos ---
class ObjetoBase(BaseModel):
    nome: str = Field(..., min_length=1, max_length=100, examples=["Meu Livro Favorito", "Caneca de Café"])
    descricao: Optional[str] = Field(None, max_length=500, examples=["Livro de ficção científica de 2023", "Caneca temática de super-herói"])
    categoria: Optional[str] = Field(None, max_length=100, examples=["Livro", "Utensílio de Cozinha"])
    tags: Optional[str] = Field(None, examples=["ficcao, aventura", "presente, colecionavel"]) # Separadas por vírgula
    localizacao_id: Optional[int] = None
    # Para o MVP, o caminho da imagem será gerenciado separadamente no upload
    # e armazenado no DB. O retorno pode incluir a URL/caminho.
    # caminho_imagem: Optional[str] = None # Adicionaremos depois

class ObjetoCreate(ObjetoBase):
    # No momento da criação, o nome pode ser opcional se a IA for preencher,
    # mas para o MVP, vamos manter obrigatório, como definido no checklist.
    # A IA vai sugerir categoria e tags.
    pass

class ObjetoUpdate(BaseModel): # Permite atualização parcial
    nome: Optional[str] = Field(None, min_length=1, max_length=100)
    descricao: Optional[str] = Field(None, max_length=500)
    categoria: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = Field(None)
    localizacao_id: Optional[int] = None
    # caminho_imagem: Optional[str] = None # Se permitir atualizar imagem

class Objeto(ObjetoBase): # Para leitura (resposta da API)
    id: int
    data_cadastro: datetime
    caminho_imagem: Optional[str] = None # Será o caminho/URL da imagem
    local: Optional[Local] = None # Para mostrar informações do local associado

    class Config:
        from_attributes = True # Antigo orm_mode = True

class ObjetoComSugestoes(BaseModel):
    sugestao_categoria: Optional[str] = None
    sugestao_tags: Optional[List[str]] = None # Mudei para List[str] para ser mais semântico
    objeto_parcial: Optional[Objeto] = None # Alterado para Objeto completo
    # Em breve, adicionaremos o ID do objeto temporário ou imagem aqui
    # para o usuário confirmar e salvar completamente.