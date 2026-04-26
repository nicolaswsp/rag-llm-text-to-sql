import os
import json
import csv
import time
import re
import chromadb
import chromadb.utils.embedding_functions as embedding_functions
import google.generativeai as genai
from openai import OpenAI
from dotenv import load_dotenv

# ==========================================
# 1. Configurações Iniciais e Chaves
# ==========================================
load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")
groq_api_key = os.getenv("GROQ_API_KEY")

SPIDER_JSON = "spider_data/dev.json"

genai.configure(api_key=google_api_key)
groq_client = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")

# ==========================================
# PAINEL DE CONTROLE DE ARQUITETURA
# ==========================================
# Escolha a estratégia para rodar agora: "gemini", "default", ou "none"
RAG_MODE = "default"

print("==============================================")
print(f"⚙️ MODO DE ARQUITETURA ATUAL: {RAG_MODE.upper()}")
print("==============================================\n")

# Configuração condicional do Banco de Dados
chroma_client = None
schema_collection = None

if RAG_MODE == "gemini":
    print("⏳ Conectando RAG: Motor GEMINI (3072 dimensões)...")
    google_ef = embedding_functions.GoogleGenerativeAiEmbeddingFunction(
        api_key=google_api_key,
        model_name="models/gemini-embedding-001",
        task_type="RETRIEVAL_QUERY"
    )
    chroma_client = chromadb.PersistentClient(path="./spider_rag_db_gemini")
    schema_collection = chroma_client.get_collection(name="spider_schemas", embedding_function=google_ef)

elif RAG_MODE == "default":
    print("⏳ Conectando RAG: Motor CHROMA DEFAULT (384 dimensões)...")
    # O ChromaDB usa seu modelo padrão interno automaticamente se não passarmos função
    chroma_client = chromadb.PersistentClient(path="./spider_rag_db")
    schema_collection = chroma_client.get_collection(name="spider_schemas")

elif RAG_MODE == "none":
    print("⚠️ RAG DESLIGADO: O modelo não receberá os DDLs e tentará fazer a consulta 'às cegas'.")

# ==========================================
# 2. Helper Functions
# ==========================================
def retrieve_schema(db_id):
    """Busca o DDL, ou retorna vazio se o RAG estiver desligado."""
    if RAG_MODE == "none":
        return "Schema não fornecido. Baseie-se apenas na intuição sobre os nomes."

    results = schema_collection.get(where={"db_id": db_id})
    if results and results['documents']:
        return results['documents'][0]
    return ""

def clean_sql_output(raw_sql):
    """Limpa pensamentos do Qwen e formatações markdown."""
    clean_str = re.sub(r'<think>.*?</think>', '', raw_sql, flags=re.DOTALL)
    clean_str = clean_str.replace("```sql", "").replace("```", "")
    return clean_str.replace('\n', ' ').strip()

def get_last_processed_index(txt_filepath):
    """Verifica onde o modelo parou para continuar depois."""
    if not os.path.exists(txt_filepath):
        return 0
    with open(txt_filepath, "r", encoding="utf-8") as f:
        return sum(1 for line in f)

# ==========================================
# 3. LLM Generators
# ==========================================
system_prompt = (
    "You are a Senior Data Engineer expert in SQLite. "
    "Given the database schema below, write the SQL query that answers the user's question. "
    "Return ONLY the valid SQL code, without markdown formatting, without explanations, and in a single line."
)

def generate_sql_gemini(question, ddl_schema, model_id):
    try:
        model = genai.GenerativeModel(model_name=model_id, system_instruction=system_prompt)
        user_prompt = f"Database Schema:\n{ddl_schema}\n\nQuestion: {question}"
        response = model.generate_content(user_prompt, generation_config=genai.types.GenerationConfig(temperature=0.0))
        return clean_sql_output(response.text)
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "Quota" in error_msg:
            print("\n[!] Limite do Gemini atingido. Pausando por 60s...")
            time.sleep(60)
            return generate_sql_gemini(question, ddl_schema, model_id)
        return f"SELECT 'ERROR: {e}'"

def generate_sql_groq(question, ddl_schema, model_id):
    try:
        user_prompt = f"Database Schema:\n{ddl_schema}\n\nQuestion: {question}"
        response = groq_client.chat.completions.create(
            model=model_id,
            temperature=0.0,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        )
        return clean_sql_output(response.choices[0].message.content)
    except Exception as e:
        return f"SELECT 'ERROR: {e}'"

# ==========================================
# 4. Main Execution Engine
# ==========================================
MODEL_CONFIGS = {
    "gemini_flash_lite": {
        "name": "Gemini 3.1 Flash-lite",
        "provider": "google", 
        "id": "gemini-3.1-flash-lite-preview"
    },
    "gemini_flash": {
        "name": "Gemini 3.1 Flash",
        "provider": "google", 
        "id": "gemini-3-flash-preview"
    },
    "gemini_pro": {
        "name": "Gemini 2.5 Pro",
        "provider": "google", 
        "id": "gemini-2.5-pro"
    },
    "llama": {
        "name": "Llama 3.3 (70B)",
        "provider": "groq", 
        "id": "llama-3.3-70b-versatile"
    },
    "qwen": {
        "name": "Qwen 3 (32B)",
        "provider": "groq", 
        "id": "qwen/qwen3-32b"
    }
}

def run_single_model(model_key):
    config = MODEL_CONFIGS[model_key]
    
    # Nomes dos arquivos agora incluem a estratégia RAG para não misturar os testes!
    txt_file = f"predicted_{model_key}_rag_{RAG_MODE}.txt"
    csv_file = f"results_{model_key}_rag_{RAG_MODE}.csv"
    
    print(f"\n🚀 Iniciando esteira: {model_key.upper()} ({config['id']})")
    print(f"Salvo em: {txt_file}\n")
    
    with open(SPIDER_JSON, 'r', encoding='utf-8') as f:
        spider_data = json.load(f)
        
    start_index = get_last_processed_index(txt_file)
    
    if start_index >= len(spider_data):
        print(f"🎉 O modelo {model_key.upper()} já processou todos os registros neste modo!")
        return

    f_txt = open(txt_file, "a", encoding="utf-8")
    write_header = not os.path.exists(csv_file)
    f_csv = open(csv_file, "a", encoding="utf-8", newline="")
    csv_writer = csv.writer(f_csv)
    
    if write_header:
        csv_writer.writerow(["db_id", "question", "gold_sql", f"{model_key}_predicted_sql"])
        
    try:
        for index in range(start_index, len(spider_data)):
            item = spider_data[index]
            question = item['question']
            db_id = item['db_id']
            gold_sql = item['query']
            
            ddl_context = retrieve_schema(db_id)
            
            if config['provider'] == "google":
                predicted_sql = generate_sql_gemini(question, ddl_context, config['id'])
                time.sleep(12) 
            else:
                predicted_sql = generate_sql_groq(question, ddl_context, config['id'])
                time.sleep(1.5) 
                
            f_txt.write(f"{predicted_sql}\n")
            csv_writer.writerow([db_id, question, gold_sql, predicted_sql])
            
            f_txt.flush()
            f_csv.flush()
            print(f"[{model_key.upper()}] Processado {index + 1}/{len(spider_data)}: {db_id}")

    except KeyboardInterrupt:
        print(f"\n[!] Execução interrompida pelo usuário.")
    finally:
        f_txt.close()
        f_csv.close()

# ==========================================
# PAINEL DE EXECUÇÃO
# ==========================================
if __name__ == "__main__":
    # run_single_model("gemini_flash_lite")
    run_single_model("gemini_flash")
    # run_single_model("gemini_pro")
    # run_single_model("gemini")
    # run_single_model("llama")
    # run_single_model("qwen")