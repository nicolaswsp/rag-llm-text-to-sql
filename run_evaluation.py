import subprocess
import csv
import os
import sys

# ==========================================
# 1. Configuration Paths
# ==========================================
GOLD_SQL_FILE = "spider_data/dev_gold.sql"
DB_FOLDER = "spider_data/database/"
TABLES_JSON = "spider_data/tables.json"

# MAPEAMENTO ATUALIZADO: Todos os seus 8 arquivos do Estudo de Ablação
MODELS_TO_EVALUATE = [
    {"name": "Llama 3.3 (Sem RAG)", "file": "predicted_llama_rag_none.txt"},
    {"name": "Llama 3.3 (Com RAG)", "file": "predicted_llama_rag_default.txt"},
    {"name": "Qwen 3 (Sem RAG)", "file": "predicted_qwen_rag_none.txt"},
    {"name": "Qwen 3 (Com RAG)", "file": "predicted_qwen_rag_default.txt"},
    {"name": "Gemini Flash (Sem RAG)", "file": "predicted_gemini_flash_rag_none.txt"},
    {"name": "Gemini Flash (Com RAG)", "file": "predicted_gemini_flash_rag_default.txt"},
    {"name": "Gemini Flash Lite (Sem RAG)", "file": "predicted_gemini_flash_lite_rag_none.txt"},
    {"name": "Gemini Flash Lite (Com RAG)", "file": "predicted_gemini_flash_lite_rag_default.txt"}
]

# ==========================================
# 2. Output Parser (VersÃO CORRIGIDA)
# ==========================================
def parse_spider_output_detailed(output_text):
    """
    Lê a tabela do Spider e extrai as notas de TODAS as dificuldades corrigindo as colunas.
    """
    scores = {
        "EX": {"easy": "0.000", "medium": "0.000", "hard": "0.000", "extra": "0.000", "all": "0.000"},
        "EM": {"easy": "0.000", "medium": "0.000", "hard": "0.000", "extra": "0.000", "all": "0.000"}
    }
    
    lines = output_text.split('\n')
    current_section = None
    
    for line in lines:
        if "EXECUTION ACCURACY" in line:
            current_section = "EX"
        elif "EXACT MATCH" in line:
            current_section = "EM"
            
        # A linha com os resultados reais começa com "execution" ou "exact"
        if current_section == "EX" and line.strip().startswith("execution"):
            parts = line.split()
            if len(parts) >= 6:
                scores["EX"]["easy"] = parts[1]
                scores["EX"]["medium"] = parts[2]
                scores["EX"]["hard"] = parts[3]
                scores["EX"]["extra"] = parts[4]
                scores["EX"]["all"] = parts[5]
                
        elif current_section == "EM" and line.strip().startswith("exact"):
            parts = line.split()
            if len(parts) >= 6:
                scores["EM"]["easy"] = parts[1]
                scores["EM"]["medium"] = parts[2]
                scores["EM"]["hard"] = parts[3]
                scores["EM"]["extra"] = parts[4]
                scores["EM"]["all"] = parts[5]
                    
    return scores

# ==========================================
# 3. Execution Engine
# ==========================================
def run_spider_evaluator(prediction_file):
    command = [
        sys.executable, "-X", "utf8", "evaluation.py",
        "--gold", GOLD_SQL_FILE,
        "--pred", prediction_file,
        "--etype", "all",
        "--db", DB_FOLDER,
        "--table", TABLES_JSON
    ]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=True)
        return parse_spider_output_detailed(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"\n[!] Falha ao avaliar {prediction_file}. Detalhes do erro:")
        print(e.stderr if e.stderr else e.stdout) 
        return None
    except FileNotFoundError:
        print("\n[!] Erro: 'evaluation.py' não encontrado na pasta raiz.")
        return None

# ==========================================
# 4. Main Pipeline
# ==========================================
def main():
    print("Iniciando avaliação detalhada (Estudo de Ablação)...\n")
    results_data = []
    
    for model in MODELS_TO_EVALUATE:
        model_name = model["name"]
        pred_file = model["file"]
        
        if not os.path.exists(pred_file):
            print(f"⚠️ Pulando {model_name}... Arquivo '{pred_file}' não encontrado.")
            continue
            
        print(f"📊 Avaliando {model_name}...")
        scores = run_spider_evaluator(pred_file)
        
        if scores:
            results_data.append({
                "Model": model_name,
                "EX_Easy": scores["EX"]["easy"],
                "EX_Medium": scores["EX"]["medium"],
                "EX_Hard": scores["EX"]["hard"],
                "EX_Extra": scores["EX"]["extra"],
                "EX_All": scores["EX"]["all"],
                "EM_Easy": scores["EM"]["easy"],
                "EM_Medium": scores["EM"]["medium"],
                "EM_Hard": scores["EM"]["hard"],
                "EM_Extra": scores["EM"]["extra"],
                "EM_All": scores["EM"]["all"]
            })
            print(f"   [GERAL] EX = {scores['EX']['all']} | EM = {scores['EM']['all']}")
            print(f"   [FÁCIL] EX = {scores['EX']['easy']} | [EXTRA DIFÍCIL] EX = {scores['EX']['extra']}\n")
        
    csv_filename = "evaluation_metrics_ablation_study.csv"
    if results_data:
        with open(csv_filename, "w", newline="", encoding="utf-8") as f:
            headers = ["Model", "EX_Easy", "EX_Medium", "EX_Hard", "EX_Extra", "EX_All", 
                       "EM_Easy", "EM_Medium", "EM_Hard", "EM_Extra", "EM_All"]
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(results_data)
            
        print(f"🎉 Pipeline concluído! Métricas salvas na super planilha '{csv_filename}'.")

if __name__ == "__main__":
    main()