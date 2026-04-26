# import os
# import csv
# import json
# import re
# import time
# import chromadb
# import chromadb.utils.embedding_functions as embedding_functions
# from openai import OpenAI
# from dotenv import load_dotenv

# # ==========================================
# # 1. Configurações
# # ==========================================
# load_dotenv()
# groq_api_key = os.getenv("GROQ_API_KEY")
# google_api_key = os.getenv("GOOGLE_API_KEY")

# groq_client = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")

# # Defina aqui qual modelo e modo RAG você quer consertar
# # MODEL_ID = "llama-3.3-70b-versatile"   # "qwen/qwen3-32b" "llama-3.3-70b-versatile"
# # MODEL_ID = "qwen/qwen3-32b"
# MODEL_ID = "gemini-3-flash-preview"
# # MODEL_KEY = "llama"          # "llama" "qwen"
# # MODEL_KEY = "qwen"
# MODEL_KEY = "gemini_flash"
# RAG_MODE = "default" # ou "default" ou "none"

# CSV_FILE = f"results_{MODEL_KEY}_rag_{RAG_MODE}.csv"
# TXT_FILE = f"predicted_{MODEL_KEY}_rag_{RAG_MODE}.txt"

# # ==========================================
# # 2. Conexão Condicional com o RAG
# # ==========================================
# print(f"⏳ Configurando a cirurgia para o modo RAG: {RAG_MODE.upper()}...")

# chroma_client = None
# schema_collection = None

# if RAG_MODE == "gemini":
#     google_ef = embedding_functions.GoogleGenerativeAiEmbeddingFunction(
#         api_key=google_api_key,
#         model_name="models/gemini-embedding-001",
#         task_type="RETRIEVAL_QUERY"
#     )
#     chroma_client = chromadb.PersistentClient(path="./spider_rag_db_gemini")
#     schema_collection = chroma_client.get_collection(name="spider_schemas", embedding_function=google_ef)

# elif RAG_MODE == "default":
#     chroma_client = chromadb.PersistentClient(path="./spider_rag_db")
#     schema_collection = chroma_client.get_collection(name="spider_schemas")

# elif RAG_MODE == "none":
#     print("⚠️ Atenção: A cirurgia será feita SEM contexto de RAG.")

# def retrieve_schema(db_id):
#     """Busca o contexto dinamicamente de acordo com o modo escolhido."""
#     if RAG_MODE == "none":
#         return "Schema não fornecido. Baseie-se apenas na intuição sobre os nomes."
        
#     results = schema_collection.get(where={"db_id": db_id})
#     if results and results['documents']:
#         return results['documents'][0]
#     return ""

# # ==========================================
# # 3. Refazendo a Inferência
# # ==========================================
# system_prompt = (
#     "You are a Senior Data Engineer expert in SQLite. "
#     "Given the database schema below, write the SQL query that answers the user's question. "
#     "Return ONLY the valid SQL code, without markdown formatting, without explanations, and in a single line."
# )

# def generate_sql_groq_fix(question, ddl_schema, model_id):
#     try:
#         user_prompt = f"Database Schema:\n{ddl_schema}\n\nQuestion: {question}"
#         response = groq_client.chat.completions.create(
#             model=model_id,
#             temperature=0.0,
#             messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
#         )
#         return clean_sql_output(response.choices[0].message.content)
#     except Exception as e:
#         return f"SELECT 'STILL ERROR: {e}'"

# # ==========================================
# # 4. O Motor de Correção (Patching)
# # ==========================================
# def main():
#     if not os.path.exists(CSV_FILE):
#         print(f"❌ Arquivo {CSV_FILE} não encontrado.")
#         return

#     print(f"\n🩺 Iniciando cirurgia de dados no arquivo: {CSV_FILE}")
    
#     # 1. Lê todos os dados atuais para a memória
#     rows = []
#     with open(CSV_FILE, "r", encoding="utf-8") as f:
#         reader = csv.DictReader(f)
#         fieldnames = reader.fieldnames
#         for row in reader:
#             rows.append(row)

#     erros_encontrados = 0
#     erros_corrigidos = 0

#     # 2. Procura pelas linhas corrompidas e conserta
#     pred_column = f"{MODEL_KEY}_predicted_sql"
    
#     for i, row in enumerate(rows):
#         predicted_sql = row[pred_column]
        
#         # Se a IA salvou o erro do limite de cota no SQL
#         if "ERROR: Error code: 429" in predicted_sql or predicted_sql.startswith("SELECT 'ERROR"):
#             erros_encontrados += 1
#             db_id = row["db_id"]
#             question = row["question"]
            
#             print(f"🔧 Consertando linha {i+1} (Banco: {db_id})...")
            
#             ddl_context = retrieve_schema(db_id)
#             novo_sql = generate_sql_groq_fix(question, ddl_context, MODEL_ID)
            
#             # Atualiza a linha na memória com o SQL correto
#             rows[i][pred_column] = novo_sql
#             erros_corrigidos += 1
            
#             # Pausa para não estourar a API novamente
#             time.sleep(2)

#     if erros_encontrados == 0:
#         print("✅ Nenhum erro encontrado! Seus arquivos já estão perfeitos.")
#         return

#     # 3. Salva o CSV consertado por cima do antigo
#     with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
#         writer = csv.DictWriter(f, fieldnames=fieldnames)
#         writer.writeheader()
#         writer.writerows(rows)

#     # 4. Recria o arquivo TXT perfeitamente alinhado
#     with open(TXT_FILE, "w", encoding="utf-8") as f:
#         for row in rows:
#             f.write(f"{row[pred_column]}\n")

#     print(f"\n🎉 Cirurgia concluída! {erros_corrigidos} erros foram consertados.")
#     print(f"Os arquivos '{CSV_FILE}' e '{TXT_FILE}' foram atualizados com sucesso e estão prontos para avaliação.")

# if __name__ == "__main__":
#     main()

# import os
# import csv
# import re
# import time
# import chromadb
# import chromadb.utils.embedding_functions as embedding_functions
# from openai import OpenAI
# from dotenv import load_dotenv

# # ==========================================
# # 1. Configurações
# # ==========================================
# load_dotenv()
# groq_api_key = os.getenv("GROQ_API_KEY")
# google_api_key = os.getenv("GOOGLE_API_KEY")

# groq_client = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")

# # Defina aqui qual modelo e modo RAG você quer consertar
# MODEL_ID = "llama-3.3-70b-versatile"   # "qwen/qwen3-32b" "llama-3.3-70b-versatile"
# # MODEL_ID = "qwen/qwen3-32b"
# MODEL_KEY = "llama"          # "llama" "qwen"
# # MODEL_KEY = "qwen"
# RAG_MODE = "default" # ou "default" ou "none"

# CSV_FILE = f"results_{MODEL_KEY}_rag_{RAG_MODE}.csv"
# TXT_FILE = f"predicted_{MODEL_KEY}_rag_{RAG_MODE}.txt"

# # ==========================================
# # 2. Conexão Condicional com o RAG
# # ==========================================
# print(f"⏳ Configurando a cirurgia para o modo RAG: {RAG_MODE.upper()}...")

# chroma_client = None
# schema_collection = None

# if RAG_MODE == "gemini":
#     google_ef = embedding_functions.GoogleGenerativeAiEmbeddingFunction(
#         api_key=google_api_key,
#         model_name="models/gemini-embedding-001",
#         task_type="RETRIEVAL_QUERY"
#     )
#     chroma_client = chromadb.PersistentClient(path="./spider_rag_db_gemini")
#     schema_collection = chroma_client.get_collection(name="spider_schemas", embedding_function=google_ef)

# elif RAG_MODE == "default":
#     chroma_client = chromadb.PersistentClient(path="./spider_rag_db")
#     schema_collection = chroma_client.get_collection(name="spider_schemas")

# elif RAG_MODE == "none":
#     print("⚠️ Atenção: A cirurgia será feita SEM contexto de RAG.")

# def retrieve_schema(db_id):
#     """Busca o contexto dinamicamente de acordo com o modo escolhido."""
#     if RAG_MODE == "none":
#         return "Schema não fornecido. Baseie-se apenas na intuição sobre os nomes."
        
#     results = schema_collection.get(where={"db_id": db_id})
#     if results and results['documents']:
#         return results['documents'][0]
#     return ""

# # A FUNÇÃO QUE HAVIA SIDO APAGADA VOLTOU!
# def clean_sql_output(raw_sql):
#     """Limpa pensamentos do Qwen e formatações markdown."""
#     clean_str = re.sub(r'<think>.*?</think>', '', raw_sql, flags=re.DOTALL)
#     clean_str = clean_str.replace("```sql", "").replace("```", "")
#     return clean_str.replace('\n', ' ').strip()

# # ==========================================
# # 3. Refazendo a Inferência
# # ==========================================
# system_prompt = (
#     "You are a Senior Data Engineer expert in SQLite. "
#     "Given the database schema below, write the SQL query that answers the user's question. "
#     "Return ONLY the valid SQL code, without markdown formatting, without explanations, and in a single line."
# )

# def generate_sql_groq_fix(question, ddl_schema, model_id):
#     try:
#         user_prompt = f"Database Schema:\n{ddl_schema}\n\nQuestion: {question}"
#         response = groq_client.chat.completions.create(
#             model=model_id,
#             temperature=0.0,
#             messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
#         )
#         return clean_sql_output(response.choices[0].message.content)
#     except Exception as e:
#         return f"SELECT 'STILL ERROR: {e}'"

# # ==========================================
# # 4. O Motor de Correção (Patching)
# # ==========================================
# def main():
#     if not os.path.exists(CSV_FILE):
#         print(f"❌ Arquivo {CSV_FILE} não encontrado.")
#         return

#     print(f"\n🩺 Iniciando cirurgia de dados no arquivo: {CSV_FILE}")
    
#     rows = []
#     with open(CSV_FILE, "r", encoding="utf-8") as f:
#         reader = csv.DictReader(f)
#         fieldnames = reader.fieldnames
#         for row in reader:
#             rows.append(row)

#     erros_encontrados = 0
#     erros_corrigidos = 0
#     pred_column = f"{MODEL_KEY}_predicted_sql"
    
#     for i, row in enumerate(rows):
#         predicted_sql = row[pred_column]
        
#         # AGORA ELE PROCURA TANTO PELO ERRO ORIGINAL QUANTO PELO 'STILL ERROR'
#         if "ERROR: Error code: 429" in predicted_sql or predicted_sql.startswith("SELECT 'ERROR") or "STILL ERROR" in predicted_sql:
#             erros_encontrados += 1
#             db_id = row["db_id"]
#             question = row["question"]
            
#             print(f"🔧 Consertando linha {i+1} (Banco: {db_id})...")
            
#             ddl_context = retrieve_schema(db_id)
#             novo_sql = generate_sql_groq_fix(question, ddl_context, MODEL_ID)
            
#             rows[i][pred_column] = novo_sql
#             erros_corrigidos += 1
#             time.sleep(2)

#     if erros_encontrados == 0:
#         print("✅ Nenhum erro encontrado! Seus arquivos já estão perfeitos.")
#         return

#     with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
#         writer = csv.DictWriter(f, fieldnames=fieldnames)
#         writer.writeheader()
#         writer.writerows(rows)

#     with open(TXT_FILE, "w", encoding="utf-8") as f:
#         for row in rows:
#             f.write(f"{row[pred_column]}\n")

#     print(f"\n🎉 Cirurgia concluída! {erros_corrigidos} erros foram consertados e o TXT recriado.")

# if __name__ == "__main__":
#     main()

import os
import csv
import re
import time
import chromadb
import chromadb.utils.embedding_functions as embedding_functions
from openai import OpenAI
import google.generativeai as genai
from dotenv import load_dotenv

# ==========================================
# 1. Configurações e Chaves de API
# ==========================================
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")
google_api_key = os.getenv("GOOGLE_API_KEY")

# Inicializando os dois clientes
groq_client = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")
genai.configure(api_key=google_api_key)


# ==========================================
# 2. Definição do Alvo da Cirurgia
# ==========================================
# Defina aqui qual modelo e modo RAG você quer consertar
# MODEL_ID = "llama-3.3-70b-versatile"   # "qwen/qwen3-32b" "llama-3.3-70b-versatile"
# MODEL_ID = "qwen/qwen3-32b"
MODEL_ID = "gemini-3-flash-preview"
# MODEL_KEY = "llama"          # "llama" "qwen"
# MODEL_KEY = "qwen"
MODEL_KEY = "gemini_flash"
RAG_MODE = "none" # ou "default" ou "none"

CSV_FILE = f"results_{MODEL_KEY}_rag_{RAG_MODE}.csv"
TXT_FILE = f"predicted_{MODEL_KEY}_rag_{RAG_MODE}.txt"

# ==========================================
# 3. Conexão Condicional com o RAG
# ==========================================
print(f"⏳ Configurando a cirurgia para o modelo {MODEL_KEY.upper()} no modo RAG: {RAG_MODE.upper()}...")

chroma_client = None
schema_collection = None

if RAG_MODE == "gemini":
    google_ef = embedding_functions.GoogleGenerativeAiEmbeddingFunction(
        api_key=google_api_key,
        model_name="models/gemini-embedding-001",
        task_type="RETRIEVAL_QUERY"
    )
    chroma_client = chromadb.PersistentClient(path="./spider_rag_db_gemini")
    schema_collection = chroma_client.get_collection(name="spider_schemas", embedding_function=google_ef)

elif RAG_MODE == "default":
    chroma_client = chromadb.PersistentClient(path="./spider_rag_db")
    schema_collection = chroma_client.get_collection(name="spider_schemas")

elif RAG_MODE == "none":
    print("⚠️ Atenção: A cirurgia será feita SEM contexto de RAG.")

def retrieve_schema(db_id):
    if RAG_MODE == "none":
        return "Schema não fornecido. Baseie-se apenas na intuição sobre os nomes das tabelas."
        
    results = schema_collection.get(where={"db_id": db_id})
    if results and results['documents']:
        return results['documents'][0]
    return ""

def clean_sql_output(raw_sql):
    """Limpa pensamentos (do Qwen) e formatações markdown (do Gemini/Llama)."""
    clean_str = re.sub(r'<think>.*?</think>', '', raw_sql, flags=re.DOTALL)
    clean_str = clean_str.replace("```sql", "").replace("```", "")
    return clean_str.replace('\n', ' ').strip()

# ==========================================
# 4. Roteador de Inferência (Gemini vs Groq)
# ==========================================
system_prompt = (
    "You are a Senior Data Engineer expert in SQLite. "
    "Given the database schema below, write the SQL query that answers the user's question. "
    "Return ONLY the valid SQL code, without markdown formatting, without explanations, and in a single line."
)

def generate_sql_fix(question, ddl_schema, model_id, model_key):
    user_prompt = f"Database Schema:\n{ddl_schema}\n\nQuestion: {question}"
    
    try:
        if "gemini" in model_key.lower():
            # Rota do Google Gemini
            model = genai.GenerativeModel(
                model_name=model_id,
                system_instruction=system_prompt
            )
            response = model.generate_content(
                user_prompt,
                generation_config=genai.types.GenerationConfig(temperature=0.0)
            )
            return clean_sql_output(response.text)
            
        else:
            # Rota da Groq (Llama / Qwen)
            response = groq_client.chat.completions.create(
                model=model_id,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": system_prompt}, 
                    {"role": "user", "content": user_prompt}
                ]
            )
            return clean_sql_output(response.choices[0].message.content)
            
    except Exception as e:
        return f"SELECT 'STILL ERROR: {e}'"

# ==========================================
# 5. O Motor de Correção (Patching)
# ==========================================
def main():
    if not os.path.exists(CSV_FILE):
        print(f"❌ Arquivo {CSV_FILE} não encontrado.")
        return

    print(f"\n🩺 Iniciando cirurgia de dados no arquivo: {CSV_FILE}")
    
    rows = []
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    erros_encontrados = 0
    erros_corrigidos = 0
    pred_column = f"{MODEL_KEY}_predicted_sql"
    
    for i, row in enumerate(rows):
        predicted_sql = row[pred_column]
        
        # Filtro de detecção de erros (Rate Limit do Gemini, etc)
        if "ERROR" in predicted_sql or "429" in predicted_sql or "STILL ERROR" in predicted_sql:
            erros_encontrados += 1
            db_id = row["db_id"]
            question = row["question"]
            
            print(f"🔧 Consertando linha {i+1} (Banco: {db_id}) via {MODEL_KEY}...")
            
            ddl_context = retrieve_schema(db_id)
            novo_sql = generate_sql_fix(question, ddl_context, MODEL_ID, MODEL_KEY)
            
            rows[i][pred_column] = novo_sql
            erros_corrigidos += 1
            
            # Pausa de 4 segundos para respeitar os limites rígidos de cota do Gemini Free/Tier 1
            time.sleep(4)

    if erros_encontrados == 0:
        print("✅ Nenhum erro encontrado! Seus arquivos já estão perfeitos.")
        return

    # Reescreve o CSV corrigido
    with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Regera o TXT do zero para passar no avaliador
    with open(TXT_FILE, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(f"{row[pred_column]}\n")

    print(f"\n🎉 Cirurgia concluída! {erros_corrigidos} erros foram consertados e o TXT recriado.")

if __name__ == "__main__":
    main()