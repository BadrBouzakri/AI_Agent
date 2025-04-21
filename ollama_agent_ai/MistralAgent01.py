import subprocess
import requests
import re

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral"

def ask_ollama(prompt):
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        result = response.json()
        return result.get("response", "").strip()
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la requête à Ollama : {e}")
        return ""

def run_shell_command(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        print("=== Sortie de la commande ===")
        print(result.stdout)
        if result.stderr:
            print("=== Erreurs ===")
            print(result.stderr)
    except Exception as e:
        print(f"Erreur lors de l'exécution de la commande : {e}")

def clean_command_output(raw_output):
    cleaned_lines = []
    for line in raw_output.split("\n"):
        line = line.strip()

        # Ignorer les lignes vides ou commentaires
        if not line or line.startswith("#"):
            continue

        # Supprimer les numéros de liste : "1. ", "2) ", etc.
        line = re.sub(r"^\d+[\.\)]\s*", "", line)

        # Supprimer les backticks et guillemets déséquilibrés
        line = line.replace("`", "")
        if line.count('"') % 2 != 0:
            line = line.replace('"', '')
        if line.count("'") % 2 != 0:
            line = line.replace("'", "")

        # Supprimer les balises Markdown (par précaution)
        if line.startswith("```") or line.endswith("```"):
            continue

        cleaned_lines.append(line)
    return cleaned_lines

def main():
    while True:
        user_input = input("Que veux-tu faire  ? (ou 'exit' pour quitter) : ")
        if user_input.lower() in ("exit", "quit"):
            break

        prompt = (
            f"Je suis un assistant IA sur Ubuntu. Donne-moi une ou plusieurs commandes bash précises "
            f"pour accomplir cette tâche : '{user_input}'. Ne donne que les lignes de commande valides, "
            f"sans explication, sans bloc markdown, sans guillemets, ni numérotation."
        )
        command_output = ask_ollama(prompt)

        print("\n=== Commande(s) suggérée(s) ===")
        print(command_output)

        confirm = input("\nSouhaites-tu exécuter cette/ces commande(s) ? (oui/non) : ").lower()
        if confirm in ("oui", "o", "yes", "y"):
            print("\n=== Exécution en cours ===")
            commands = clean_command_output(command_output)
            for cmd in commands:
                print(f"\n→ Commande : {cmd}")
                run_shell_command(cmd)
        else:
            print("Commande non exécutée.")

if __name__ == "__main__":
    main()
