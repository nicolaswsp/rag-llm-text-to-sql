import os
import time
import sqlite3
import chromadb
import chromadb.utils.embedding_functions as embedding_functions
from dotenv import load_dotenv

# ==========================================
# 1. Configurações Iniciais e Chaves
# ==========================================
load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")

if not google_api_key:
    raise ValueError("A chave GOOGLE_API_KEY não foi encontrada no arquivo .env!")

# Caminho onde os bancos de dados do Spider estão salvos localmente
# Ajuste se a sua pasta se chamar diferente de "spider_data/database"
SPIDER_DB_FOLDER = "spider_data/database"

# ==========================================
# 2. Configuração do ChromaDB + Gemini
# ==========================================
print("⏳ Configurando o motor de embeddings do Google (text-embedding-004)...")
google_ef = embedding_functions.GoogleGenerativeAiEmbeddingFunction(
    api_key=google_api_key,
    model_name="models/gemini-embedding-001",
    task_type="RETRIEVAL_DOCUMENT" # Indica ao modelo que estamos armazenando conhecimento
)

# Criando/Conectando ao banco vetorial com o novo nome para não apagar o antigo
print("📂 Conectando ao ChromaDB (path: ./spider_rag_db_gemini)...")
chroma_client = chromadb.PersistentClient(path="./spider_rag_db_gemini")

# Criando a coleção com o motor do Google atrelado
schema_collection = chroma_client.get_or_create_collection(
    name="spider_schemas",
    embedding_function=google_ef
)

# ==========================================
# 3. Função de Leitura dos Dados do Spider
# ==========================================
def read_schema_from_sql(db_id):
    """
    Tenta ler o arquivo 'schema.sql'. Se ele não existir, 
    conecta no arquivo binário '.sqlite' e faz engenharia reversa do DDL.
    """
    db_folder = os.path.join(SPIDER_DB_FOLDER, db_id)
    schema_txt_path = os.path.join(db_folder, "schema.sql")
    sqlite_db_path = os.path.join(db_folder, f"{db_id}.sqlite")

    # Tentativa 1: Existe o arquivo de texto schema.sql?
    if os.path.exists(schema_txt_path):
        try:
            with open(schema_txt_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            pass # Se der erro de codificação, pula para a tentativa 2

    # Tentativa 2: Extração direta do banco .sqlite (Engenharia Reversa)
    if os.path.exists(sqlite_db_path):
        try:
            conn = sqlite3.connect(sqlite_db_path)
            cursor = conn.cursor()
            
            # Consulta a tabela interna do SQLite que guarda como o banco foi criado
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = cursor.fetchall()
            conn.close()
            
            # Junta todos os comandos CREATE TABLE em um único texto
            ddl_reverso = "\n\n".join([t[0] for t in tables if t[0] is not None])
            
            if ddl_reverso.strip():
                return ddl_reverso
                
        except Exception as e:
            print(f"Erro interno ao ler o sqlite do banco '{db_id}': {e}")
            
    return None

# ==========================================
# 4. Pipeline Principal de Ingestão
# ==========================================
def main():
    print("\nIniciando a Fase 2: Ingestão e Indexação de Schemas...")

    if not os.path.exists(SPIDER_DB_FOLDER):
        print(f"Erro: A pasta '{SPIDER_DB_FOLDER}' não foi encontrada.")
        return

    # Lista todas as pastas de banco de dados do Spider
    db_folders = [f.name for f in os.scandir(SPIDER_DB_FOLDER) if f.is_dir()]
    
    documents = []
    metadatas = []
    ids = []

    print(f"Varrendo {len(db_folders)} bancos de dados e extraindo DDLs...")

    for db_id in db_folders:
        ddl_content = read_schema_from_sql(db_id)

        if ddl_content:
            documents.append(ddl_content)
            metadatas.append({"db_id": db_id})
            ids.append(db_id) # Usamos o próprio nome do banco como ID único
        else:
            print(f"Aviso: schema.sql não encontrado para o banco '{db_id}'.")

    # ==========================================
    # 5. Salvando no Banco Vetorial em Lotes
    # ==========================================
    if documents:
        print(f"\nTransformando {len(documents)} schemas em vetores e salvando no ChromaDB...")
        
        # Reduzimos o lote para 5, pois DDLs são pesados e gastam muitos Tokens
        batch_size = 5 
        total_batches = (len(documents) // batch_size) + 1

        for i in range(0, len(documents), batch_size):
            doc_batch = documents[i : i + batch_size]
            meta_batch = metadatas[i : i + batch_size]
            id_batch = ids[i : i + batch_size]

            sucesso = False
            while not sucesso:
                try:
                    # Tenta inserir no banco de dados
                    schema_collection.upsert(
                        documents=doc_batch,
                        metadatas=meta_batch,
                        ids=id_batch
                    )
                    sucesso = True # Se passou da linha de cima sem erro, deu certo!
                    lote_atual = (i // batch_size) + 1
                    print(f"Lote {lote_atual}/{total_batches} processado com sucesso.")
                    
                    # Pausa leve de 15 segundos entre os lotes para não assustar o servidor
                    time.sleep(15) 

                except Exception as e:
                    error_msg = str(e)
                    # Se o erro for o 429 (Rate Limit / Quota Exceeded)
                    if "429" in error_msg or "Quota" in error_msg or "ResourceExhausted" in error_msg:
                        print(f"Limite do Google atingido no Lote {(i // batch_size) + 1}. Pausando por 60 segundos para recarregar a cota...")
                        time.sleep(60) # Espera 1 minuto inteiro
                    else:
                        # Se for um erro diferente, ele avisa e para o loop
                        print(f"Erro desconhecido no Lote {(i // batch_size) + 1}: {e}")
                        break

        print("\nFase 2 concluída com sucesso!")
        print("Seu RAG agora possui um cérebro semântico novinho em folha criado pelo Google.")
    else:
        print("\nNenhum schema válido foi encontrado para indexar.")
if __name__ == "__main__":
    main()