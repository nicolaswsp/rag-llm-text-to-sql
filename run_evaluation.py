import subprocess
import csv
import os
import sys

# ==========================================
# 1. Configuration Paths
# ==========================================
# Make sure these match the location of your Spider dataset files
GOLD_SQL_FILE = "spider_data/dev_gold.sql"
DB_FOLDER = "spider_data/database/"
TABLES_JSON = "spider_data/tables.json"

# List of the predicted files generated in Phase 3
MODELS_TO_EVALUATE = [
    {"name": "Gemini 2.5 Flash", "file": "predicted_gemini.txt"},
    {"name": "Llama 3 (70B)", "file": "predicted_llama.txt"},
    {"name": "Mistral (8x7B)", "file": "predicted_mistral.txt"}
]

# ==========================================
# 2. Output Parser
# ==========================================
def parse_spider_output(output_text):
    """
    Reads the raw terminal text output from the Spider evaluation script
    and extracts the final 'ALL' scores for Execution and Exact Match.
    """
    ex_score = "Error"
    em_score = "Error"
    
    lines = output_text.split('\n')
    current_section = None
    
    for line in lines:
        if "EXECUTION ACCURACY" in line:
            current_section = "EX"
        elif "EXACT MATCH" in line:
            current_section = "EM"
        elif line.startswith("ALL:") and current_section == "EX":
            ex_score = line.split(":")[1].strip()
        elif line.startswith("ALL:") and current_section == "EM":
            em_score = line.split(":")[1].strip()
            
    return ex_score, em_score

# ==========================================
# 3. Execution Engine
# ==========================================
def run_spider_evaluator(prediction_file):
    """
    Uses subprocess to run the official evaluation.py script 
    as if it were typed in the terminal.
    """
    # CORRIGIDO: Removido o 'command =' duplicado
    command = [
        sys.executable, "evaluation.py",
        "--gold", GOLD_SQL_FILE,
        "--pred", prediction_file,
        "--etype", "all",
        "--db", DB_FOLDER,
        "--table", TABLES_JSON
    ]
    
    try:
        # Run the command
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return parse_spider_output(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"\n[!] Failed to evaluate {prediction_file}. Error details:")
        # ADICIONADO: Às vezes o Spider joga erros lógicos no stdout, não no stderr
        print(e.stderr if e.stderr else e.stdout) 
        return "Error", "Error"
    except FileNotFoundError:
        print("\n[!] Error: 'evaluation.py' not found. Please download it from the Spider GitHub.")
        return "Error", "Error"

# ==========================================
# 4. Main Pipeline
# ==========================================
def main():
    print("Starting automated evaluation pipeline...")
    results_data = []
    
    for model in MODELS_TO_EVALUATE:
        model_name = model["name"]
        pred_file = model["file"]
        
        # Check if the text file from Phase 3 actually exists before running
        if not os.path.exists(pred_file):
            print(f"Skipping {model_name}... File '{pred_file}' not found.")
            continue
            
        print(f"Evaluating {model_name}...")
        ex_score, em_score = run_spider_evaluator(pred_file)
        
        results_data.append({
            "Model": model_name,
            "Execution Accuracy (EX)": ex_score,
            "Exact Match (EM)": em_score
        })
        print(f"--> Result: EX = {ex_score} | EM = {em_score}")
        
    # Write everything to a clean CSV for the thesis
    csv_filename = "evaluation_metrics.csv"
    if results_data:
        with open(csv_filename, "w", newline="", encoding="utf-8") as f:
            headers = ["Model", "Execution Accuracy (EX)", "Exact Match (EM)"]
            writer = csv.DictWriter(f, fieldnames=headers)
            
            writer.writeheader()
            writer.writerows(results_data)
            
        print(f"\nPipeline finished! Metrics successfully saved to '{csv_filename}'.")
    else:
        print("\nPipeline finished, but no data was generated.")

if __name__ == "__main__":
    main()