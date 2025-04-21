import subprocess
import requests
import re
import os
import sys
import time
import signal
import platform
from typing import List, Dict, Any, Optional, Union

# Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "mistral"
CONFIG_DIR = os.path.expanduser("~/.config/ollama-terminal")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.txt")
HISTORY_FILE = os.path.join(CONFIG_DIR, "history.txt")
MAX_HISTORY = 100

class OllamaTerminal:
    def __init__(self):
        self.model = self._load_model_preference()
        self.history = self._load_history()
        self._setup_signal_handlers()
        
    def _load_model_preference(self) -> str:
        """Charge le modèle préféré depuis le fichier de configuration ou utilise la valeur par défaut."""
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR, exist_ok=True)
        
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return f.read().strip() or DEFAULT_MODEL
            except Exception:
                return DEFAULT_MODEL
        else:
            with open(CONFIG_FILE, "w") as f:
                f.write(DEFAULT_MODEL)
            return DEFAULT_MODEL
    
    def _save_model_preference(self) -> None:
        """Sauvegarde le modèle préféré dans le fichier de configuration."""
        with open(CONFIG_FILE, "w") as f:
            f.write(self.model)
    
    def _load_history(self) -> List[str]:
        """Charge l'historique des commandes."""
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r") as f:
                    return [line.strip() for line in f.readlines()[-MAX_HISTORY:]]
            except Exception:
                return []
        return []
    
    def _save_history(self, command: str) -> None:
        """Ajoute une commande à l'historique et sauvegarde."""
        if command and command not in self.history:
            self.history.append(command)
            if len(self.history) > MAX_HISTORY:
                self.history = self.history[-MAX_HISTORY:]
            
            with open(HISTORY_FILE, "a") as f:
                f.write(f"{command}\n")
    
    def _setup_signal_handlers(self) -> None:
        """Configure les gestionnaires de signaux pour une sortie propre."""
        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)
    
    def _handle_exit(self, sig, frame) -> None:
        """Gère la sortie propre du programme."""
        print("\n\nFermeture en cours... Merci d'avoir utilisé Ollama Terminal!")
        sys.exit(0)
    
    def ask_ollama(self, prompt: str) -> str:
        """Envoie une requête au serveur Ollama et retourne la réponse."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            print(f"Interrogation du modèle {self.model}...", end="", flush=True)
            start_time = time.time()
            
            response = requests.post(OLLAMA_URL, json=payload, timeout=60)
            response.raise_for_status()
            
            elapsed_time = time.time() - start_time
            print(f" Terminé ({elapsed_time:.2f}s)")
            
            result = response.json()
            return result.get("response", "").strip()
        except requests.exceptions.ConnectionError:
            print("\nErreur: Impossible de se connecter au serveur Ollama. Assurez-vous qu'il est en cours d'exécution.")
            return ""
        except requests.exceptions.Timeout:
            print("\nErreur: La requête a expiré. Le modèle prend trop de temps à répondre.")
            return ""
        except requests.exceptions.RequestException as e:
            print(f"\nErreur lors de la requête à Ollama: {e}")
            return ""
    
    def run_shell_command(self, command: str) -> subprocess.CompletedProcess:
        """Exécute une commande shell et retourne le résultat."""
        try:
            print(f"\n→ Exécution: {command}")
            # Utiliser shell=False est plus sécurisé quand c'est possible
            result = subprocess.run(
                command, 
                shell=True,  # On garde shell=True car on exécute des commandes complexes
                capture_output=True, 
                text=True,
                timeout=300  # Timeout de 5 minutes
            )
            
            if result.stdout:
                print("=== Sortie ===")
                print(result.stdout)
            
            if result.stderr:
                print("=== Erreurs ===")
                print(result.stderr)
            
            return result
        except subprocess.TimeoutExpired:
            print("Erreur: La commande a dépassé le délai maximum d'exécution (5 minutes).")
            return None
        except Exception as e:
            print(f"Erreur lors de l'exécution de la commande: {e}")
            return None
    
    def clean_command_output(self, raw_output: str) -> List[str]:
        """Nettoie la sortie brute pour en extraire des commandes valides."""
        # Séparation des lignes et nettoyage basique
        lines = [line.strip() for line in raw_output.split("\n") if line.strip()]
        
        # Filtre les lignes qui ne sont pas des commandes valides
        cleaned_lines = []
        for line in lines:
            # Ignorer les lignes vides, commentaires, ou blocs markdown
            if not line or line.startswith("#") or line.startswith("```"):
                continue
            
            # Supprimer les numéros de liste et les guillemets
            line = re.sub(r"^\d+[\.\)]\s*", "", line)
            
            # Nettoyage des guillemets et backticks
            if line.startswith("`") and line.endswith("`"):
                line = line[1:-1]
            elif line.count("`") % 2 == 0:
                line = line.replace("`", "")
            
            # Gestion des guillemets déséquilibrés
            if line.count('"') % 2 != 0:
                line = line.replace('"', '')
            if line.count("'") % 2 != 0:
                line = line.replace("'", "")
            
            # Vérifier si la ligne ressemble à une commande bash valide
            if not (line.startswith("```") or line.endswith("```")):
                cleaned_lines.append(line)
        
        return cleaned_lines
    
    def show_info(self) -> None:
        """Affiche les informations système et de configuration."""
        print("\n=== Informations sur Ollama Terminal ===")
        print(f"Système d'exploitation: {platform.system()} {platform.release()}")
        print(f"Python version: {platform.python_version()}")
        print(f"Modèle Ollama actuel: {self.model}")
        
        # Vérifier si Ollama est en cours d'exécution
        try:
            requests.get(OLLAMA_URL.replace("/api/generate", ""), timeout=2)
            print("Statut du serveur Ollama: En cours d'exécution")
        except:
            print("Statut du serveur Ollama: Non disponible")
        
        # Liste des modèles disponibles
        try:
            response = requests.get(OLLAMA_URL.replace("/api/generate", "/api/tags"), timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                if models:
                    print("\nModèles disponibles:")
                    for model in models:
                        print(f" - {model.get('name')}")
        except:
            pass
        
        print("\nRaccourcis clavier:")
        print(" - Ctrl+C: Quitter le programme")
        print(" - !info: Afficher ces informations")
        print(" - !model <nom>: Changer de modèle")
        print(" - !history: Afficher l'historique des commandes")
        print(" - !exit: Quitter le programme")
    
    def show_history(self) -> None:
        """Affiche l'historique des commandes."""
        if not self.history:
            print("L'historique est vide.")
            return
        
        print("\n=== Historique des commandes ===")
        for i, cmd in enumerate(self.history[-20:], 1):  # Afficher les 20 dernières commandes
            print(f"{i}. {cmd}")
    
    def change_model(self, model_name: str) -> None:
        """Change le modèle Ollama utilisé."""
        if not model_name:
            print(f"Modèle actuel: {self.model}")
            return
        
        self.model = model_name
        self._save_model_preference()
        print(f"Modèle changé pour: {self.model}")
    
    def select_commands(self, commands: List[str]) -> List[str]:
        """Permet à l'utilisateur de sélectionner les commandes à exécuter."""
        if not commands:
            return []
        
        if len(commands) == 1:
            confirm = input(f"\nExécuter cette commande ? \n[{commands[0]}] (oui/non) : ").lower()
            return commands if confirm in ("oui", "o", "yes", "y") else []
        
        print("\n=== Commandes disponibles ===")
        for i, cmd in enumerate(commands, 1):
            print(f"{i}. {cmd}")
        
        print("\nOptions:")
        print("- Entrez le numéro d'une commande pour l'exécuter (ex: '2')")
        print("- Entrez plusieurs numéros séparés par des espaces (ex: '1 3')")
        print("- Entrez 'all' ou '*' pour toutes les exécuter")
        print("- Entrez 'none' ou '0' pour n'en exécuter aucune")
        
        while True:
            choice = input("\nVotre choix : ").strip().lower()
            
            if choice in ("none", "0", "n", "non", "no"):
                return []
            
            if choice in ("all", "*", "a", "tout"):
                return commands
            
            try:
                # Traiter les numéros séparés par des espaces
                indices = [int(x) for x in choice.split()]
                selected = []
                
                for idx in indices:
                    if 1 <= idx <= len(commands):
                        selected.append(commands[idx-1])
                    else:
                        print(f"Erreur: Le numéro {idx} est hors limites.")
                
                if selected:
                    print("\nCommandes sélectionnées:")
                    for cmd in selected:
                        print(f"- {cmd}")
                    confirm = input("\nConfirmer l'exécution ? (oui/non) : ").lower()
                    if confirm in ("oui", "o", "yes", "y"):
                        return selected
                
                return []
                
            except ValueError:
                # Si une seule valeur est entrée
                try:
                    idx = int(choice)
                    if 1 <= idx <= len(commands):
                        selected = commands[idx-1]
                        confirm = input(f"\nConfirmer l'exécution de : \n[{selected}] (oui/non) : ").lower()
                        return [selected] if confirm in ("oui", "o", "yes", "y") else []
                    else:
                        print(f"Erreur: Le numéro {idx} est hors limites.")
                except ValueError:
                    print("Entrée invalide. Veuillez utiliser les options proposées.")
    
    def main(self) -> None:
        """Fonction principale du programme."""
        print(f"=== Ollama Terminal ===")
        print(f"Modèle actuel: {self.model}")
        print("Tapez votre demande ou '!help' pour les commandes disponibles.")
        
        while True:
            try:
                user_input = input("\n🔍 Que voulez-vous faire ? (ou '!exit' pour quitter) : ").strip()
                
                # Commandes spéciales
                if not user_input:
                    continue
                
                if user_input.lower() in ("!exit", "!quit", "exit", "quit"):
                    print("Au revoir!")
                    break
                
                if user_input.lower() == "!help":
                    print("\nCommandes disponibles:")
                    print("  !info    - Afficher les informations système")
                    print("  !model   - Afficher le modèle actuel")
                    print("  !model <nom> - Changer de modèle")
                    print("  !history - Afficher l'historique des commandes")
                    print("  !exit    - Quitter le programme")
                    continue
                
                if user_input.lower() == "!info":
                    self.show_info()
                    continue
                
                if user_input.lower() == "!history":
                    self.show_history()
                    continue
                
                if user_input.lower().startswith("!model"):
                    parts = user_input.split(maxsplit=1)
                    model_name = parts[1] if len(parts) > 1 else ""
                    self.change_model(model_name)
                    continue
                
                # Traitement des demandes normales
                prompt = (
                    f"Je suis un assistant IA sur {platform.system()}. "
                    f"Donne-moi une ou plusieurs commandes bash précises "
                    f"pour accomplir cette tâche : '{user_input}'. Ne donne que les lignes de commande valides, "
                    f"sans explication, sans bloc markdown, sans guillemets, ni numérotation."
                )
                
                command_output = self.ask_ollama(prompt)
                
                if not command_output:
                    print("Aucune commande suggérée.")
                    continue
                
                print("\n=== Commande(s) suggérée(s) ===")
                print(command_output)
                
                # Nettoyer et extraire les commandes
                commands = self.clean_command_output(command_output)
                
                if not commands:
                    print("Aucune commande valide n'a été extraite.")
                    continue
                
                # Sélection et exécution des commandes
                selected_commands = self.select_commands(commands)
                
                if selected_commands:
                    print("\n=== Exécution en cours ===")
                    for cmd in selected_commands:
                        # Enregistrer la commande dans l'historique
                        self._save_history(cmd)
                        # Exécuter la commande
                        self.run_shell_command(cmd)
                else:
                    print("Aucune commande n'a été exécutée.")
                    
            except KeyboardInterrupt:
                print("\nOpération annulée.")
            except Exception as e:
                print(f"Erreur inattendue: {e}")


if __name__ == "__main__":
    terminal = OllamaTerminal()
    terminal.main()