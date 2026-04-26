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

SPIDER_DB_FOLDER = "spider_data/database"

# ==========================================
# 2. Configuração do ChromaDB + Gemini
# ==========================================
print("⏳ Configurando o motor de embeddings do Google (gemini-embedding-001)...")
google_ef = embedding_functions.GoogleGenerativeAiEmbeddingFunction(
    api_key=google_api_key,
    model_name="models/gemini-embedding-001",
    task_type="RETRIEVAL_DOCUMENT"
)

print("📂 Conectando ao ChromaDB (path: ./spider_rag_db_gemini)...")
chroma_client = chromadb.PersistentClient(path="./spider_rag_db_gemini")

schema_collection = chroma_client.get_or_create_collection(
    name="spider_schemas",
    embedding_function=google_ef
)

# ==========================================
# 3. Função de Leitura Limpa (Anti-Poluição)
# ==========================================
def read_schema_clean(db_id):
    """
    Extrai APENAS a estrutura DDL. 
    Ignora os comandos INSERT para economizar tokens e evitar arquivos de 50MB.
    """
    db_folder = os.path.join(SPIDER_DB_FOLDER, db_id)
    sqlite_db_path = os.path.join(db_folder, f"{db_id}.sqlite")
    schema_txt_path = os.path.join(db_folder, "schema.sql")

    # Tentativa 1: Extração direta do banco .sqlite (Limpo e Seguro)
    if os.path.exists(sqlite_db_path):
        try:
            conn = sqlite3.connect(sqlite_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = cursor.fetchall()
            conn.close()
            
            ddl_reverso = "\n\n".join([t[0] for t in tables if t[0] is not None])
            if ddl_reverso.strip():
                return ddl_reverso
        except Exception:
            pass # Se falhar, tenta o texto

    # Tentativa 2: Lendo o arquivo de texto, mas excluindo os INSERTs
    if os.path.exists(schema_txt_path):
        try:
            with open(schema_txt_path, "r", encoding="utf-8") as f:
                linhas = f.readlines()
            
            # Mantém apenas as linhas que não começam com INSERT
            linhas_limpas = [linha for linha in linhas if not linha.strip().upper().startswith("INSERT")]
            return "".join(linhas_limpas)
        except UnicodeDecodeError:
            pass

    return None

# ==========================================
# 4. Pipeline Principal de Ingestão
# ==========================================
def main():
    print("\nIniciando a Fase 2: Ingestão e Indexação de Schemas...")

    if not os.path.exists(SPIDER_DB_FOLDER):
        print(f"Erro: A pasta '{SPIDER_DB_FOLDER}' não foi encontrada.")
        return

    db_folders = [f.name for f in os.scandir(SPIDER_DB_FOLDER) if f.is_dir()]
    
    documents = []
    metadatas = []
    ids = []

    print(f"Varrendo {len(db_folders)} bancos de dados e extraindo DDLs limpos...")

    for db_id in db_folders:
        ddl_content = read_schema_clean(db_id)

        if ddl_content:
            documents.append(ddl_content)
            metadatas.append({"db_id": db_id})
            ids.append(db_id)
        else:
            print(f"Aviso: Não foi possível extrair esquema para o banco '{db_id}'.")

    # ==========================================
    # 5. Salvando no Banco Vetorial (Um a Um)
    # ==========================================
    if documents:
        print(f"\nTransformando {len(documents)} schemas em vetores e salvando no ChromaDB...")
        
        # Lote reduzido para 1 para evitar estouro de limite
        batch_size = 1 
        total_batches = len(documents)

        for i in range(0, len(documents), batch_size):
            doc_batch = documents[i : i + batch_size]
            meta_batch = metadatas[i : i + batch_size]
            id_batch = ids[i : i + batch_size]

            sucesso = False
            tentativas = 0
            max_tentativas = 3

            while not sucesso and tentativas < max_tentativas:
                try:
                    schema_collection.upsert(
                        documents=doc_batch,
                        metadatas=meta_batch,
                        ids=id_batch
                    )
                    sucesso = True 
                    print(f"✅ Banco {i + 1}/{total_batches} ({id_batch[0]}) vetorizado com sucesso.")
                    
                    # Pausa leve entre bancos para a API respirar
                    time.sleep(2) 

                except Exception as e:
                    error_msg = str(e)
                    if "429" in error_msg or "Quota" in error_msg or "ResourceExhausted" in error_msg:
                        tentativas += 1
                        print(f"⏳ Limite atingido no banco '{id_batch[0]}'. Tentativa {tentativas}/{max_tentativas}. Pausando por 60 segundos...")
                        time.sleep(60) 
                    else:
                        print(f"❌ Erro desconhecido no banco '{id_batch[0]}': {e}")
                        break

            # Se falhou 3 vezes seguidas, a cota diária acabou. Interrompe o processo.
            if not sucesso:
                print("\n⛔ O script parou para evitar loops infinitos. É provável que sua cota diária de tokens tenha zerado.")
                print("Tente rodar novamente amanhã ou utilize uma nova chave de API.")
                return

        print("\n🎉 Fase 2 concluída com sucesso! Banco RAG montado.")
    else:
        print("\nNenhum schema válido foi encontrado para indexar.")

if __name__ == "__main__":
    main()