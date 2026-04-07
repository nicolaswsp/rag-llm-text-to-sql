import os
import json
import csv
import time
import chromadb
import re
import google.generativeai as genai
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ==========================================
# 1. Configuration & Paths
# ==========================================
google_api_key = os.getenv("GOOGLE_API_KEY")
groq_api_key = os.getenv("GROQ_API_KEY")

SPIDER_JSON = "spider_data/dev.json"

genai.configure(api_key=google_api_key)
groq_client = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")

chroma_client = chromadb.PersistentClient(path="./spider_rag_db")
schema_collection = chroma_client.get_collection(name="spider_schemas")

# Dicionário com as configurações de cada modelo
MODEL_CONFIGS = {
    "gemini": {
        "txt_file": "predicted_gemini.txt",
        "csv_file": "results_gemini.csv",
        "provider": "google",
        "id": "gemini-2.5-flash"
    },
    "llama": {
        "txt_file": "predicted_llama.txt",
        "csv_file": "results_llama.csv",
        "provider": "groq",
        "id": "llama-3.3-70b-versatile"
    },
    "qwen": {
        "txt_file": "predicted_qwen.txt",
        "csv_file": "results_qwen.csv",
        "provider": "groq",
        "id": "qwen/qwen3-32b"
    }
}

# ==========================================
# 2. Helper Functions
# ==========================================
def retrieve_schema(db_id):
    results = schema_collection.get(where={"db_id": db_id})
    if results['documents']:
        return results['documents'][0]
    return ""

def clean_sql_output(raw_sql):
    # Remove Chain-of-Thought (pensamentos do Qwen/DeepSeek)
    clean_str = re.sub(r'<think>.*?</think>', '', raw_sql, flags=re.DOTALL)
    # Remove blocos markdown e quebras de linha
    clean_str = clean_str.replace("```sql", "").replace("```", "")
    return clean_str.replace('\n', ' ').strip()

def get_last_processed_index(txt_filepath):
    """Lê o arquivo TXT do modelo específico para saber de onde recomeçar."""
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
        response = model.generate_content(
            user_prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.0)
        )
        return clean_sql_output(response.text)
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "Quota" in error_msg:
            print("\n[!] Limite do Gemini atingido. Pausando por 60 segundos...")
            time.sleep(60)
            return generate_sql_gemini(question, ddl_schema, model_id)
        return f"SELECT 'ERROR GEMINI: {e}'"

def generate_sql_groq(question, ddl_schema, model_id):
    try:
        user_prompt = f"Database Schema:\n{ddl_schema}\n\nQuestion: {question}"
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
        return f"SELECT 'ERROR GROQ: {e}'"

# ==========================================
# 4. Main Execution Engine
# ==========================================
def run_single_model(model_key):
    """Roda a inferência isolada para um único modelo."""
    config = MODEL_CONFIGS[model_key]
    print(f"\n🚀 Iniciando esteira para o modelo: {model_key.upper()} ({config['id']})")
    
    with open(SPIDER_JSON, 'r', encoding='utf-8') as f:
        spider_data = json.load(f)
        
    start_index = get_last_processed_index(config['txt_file'])
    
    if start_index >= len(spider_data):
        print(f"🎉 O modelo {model_key.upper()} já processou todos os registros!")
        return

    print(f"Retomando a partir do registro {start_index} de {len(spider_data)}...\n")
    
    write_header = not os.path.exists(config['csv_file'])
    
    f_txt = open(config['txt_file'], "a", encoding="utf-8")
    f_csv = open(config['csv_file'], "a", encoding="utf-8", newline="")
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
            
            # Escolhe a função de geração correta
            if config['provider'] == "google":
                predicted_sql = generate_sql_gemini(question, ddl_context, config['id'])
                time.sleep(12) # Pausa obrigatória do Gemini
            else:
                predicted_sql = generate_sql_groq(question, ddl_context, config['id'])
                time.sleep(1.5) # Pausa leve para Groq não bloquear por spam
                
            f_txt.write(f"{predicted_sql}\n")
            csv_writer.writerow([db_id, question, gold_sql, predicted_sql])
            
            f_txt.flush()
            f_csv.flush()
            
            print(f"[{model_key.upper()}] Processado {index + 1}/{len(spider_data)}: {db_id}")

    except KeyboardInterrupt:
        print(f"\n[!] Execução do {model_key.upper()} interrompida pelo usuário. Salvo com segurança.")
    finally:
        f_txt.close()
        f_csv.close()

# ==========================================
# PAINEL DE CONTROLE (ESCOLHA O MODELO AQUI)
# ==========================================
if __name__ == "__main__":
    # Descomente apenas o modelo que você deseja rodar no momento:
    
    # run_single_model("gemini")
    # run_single_model("llama")
    run_single_model("qwen")