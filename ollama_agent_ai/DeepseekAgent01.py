import subprocess
import requests
import re
import os
import sys
import time
import signal
import platform
import json
from typing import List, Dict, Any, Optional, Union

# Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODELS_URL = "http://localhost:11434/api/tags"
DEFAULT_MODEL = "deepseek-r1:1.5b"
CONFIG_DIR = os.path.expanduser("~/.config/ollama-terminal")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.txt")
HISTORY_FILE = os.path.join(CONFIG_DIR, "history.txt")
MAX_HISTORY = 100
MODEL_START_TIMEOUT = 200  # Délai d'attente maximum pour le démarrage du modèle (en secondes)

class OllamaTerminal:
    def __init__(self):
        self.model = self._load_model_preference()
        self.history = self._load_history()
        self._setup_signal_handlers()
        self._ensure_server_running()
        self._ensure_model_available()
        
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
    
    def _ensure_server_running(self) -> bool:
        """
        Vérifie si le serveur Ollama est en cours d'exécution.
        Si ce n'est pas le cas, tente de le démarrer.
        """
        try:
            requests.get("http://localhost:11434", timeout=2)
            return True
        except requests.exceptions.ConnectionError:
            print("Le serveur Ollama n'est pas en cours d'exécution. Tentative de démarrage...")
            
            if platform.system() == "Windows":
                # Windows - utiliser start pour démarrer en arrière-plan
                subprocess.Popen("start ollama serve", shell=True)
            else:
                # Linux/Mac - démarrer en arrière-plan
                subprocess.Popen("ollama serve &", shell=True)
            
            # Attendre que le serveur démarre
            for _ in range(10):  # 10 tentatives, 1 seconde d'intervalle
                time.sleep(1)
                try:
                    requests.get("http://localhost:11434", timeout=2)
                    print("Le serveur Ollama a été démarré avec succès.")
                    return True
                except requests.exceptions.ConnectionError:
                    pass
            
            print("Impossible de démarrer le serveur Ollama. Veuillez le démarrer manuellement.")
            return False
    
    def _ensure_model_available(self) -> bool:
        """
        Vérifie si le modèle sélectionné est disponible.
        Si ce n'est pas le cas, tente de le télécharger.
        """
        try:
            response = requests.get(OLLAMA_MODELS_URL, timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [model.get("name") for model in models]
                
                if self.model in model_names:
                    return True
                else:
                    print(f"Le modèle '{self.model}' n'est pas disponible. Tentative de téléchargement...")
                    return self._pull_model(self.model)
            
            return False
        except requests.exceptions.ConnectionError:
            print("Le serveur Ollama n'est pas accessible.")
            return False
    
    def _pull_model(self, model_name: str) -> bool:
        """
        Télécharge le modèle spécifié.
        """
        try:
            print(f"Téléchargement du modèle '{model_name}'. Cela peut prendre un certain temps...")
            
            if platform.system() == "Windows":
                process = subprocess.Popen(f"ollama pull {model_name}", shell=True)
            else:
                process = subprocess.Popen(f"ollama pull {model_name}", shell=True)
            
            # Attendre que le processus termine avec un timeout
            start_time = time.time()
            while process.poll() is None:
                if time.time() - start_time > MODEL_START_TIMEOUT:
                    process.kill()
                    print(f"Le téléchargement du modèle a dépassé le délai de {MODEL_START_TIMEOUT} secondes.")
                    return False
                time.sleep(1)
            
            if process.returncode == 0:
                print(f"Le modèle '{model_name}' a été téléchargé avec succès.")
                return True
            else:
                print(f"Échec du téléchargement du modèle '{model_name}'.")
                return False
                
        except Exception as e:
            print(f"Erreur lors du téléchargement du modèle: {e}")
            return False
    
    def ask_ollama(self, prompt: str, with_context: List[Dict] = None) -> str:
        """
        Envoie une requête au serveur Ollama et retourne la réponse.
        Supporte le contexte de conversation pour une meilleure continuité.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        
        # Ajouter le contexte s'il est fourni
        if with_context:
            payload["context"] = with_context
        
        try:
            print(f"Interrogation du modèle {self.model}...", end="", flush=True)
            start_time = time.time()
            
            response = requests.post(OLLAMA_URL, json=payload, timeout=60)
            response.raise_for_status()
            
            elapsed_time = time.time() - start_time
            print(f" Terminé ({elapsed_time:.2f}s)")
            
            result = response.json()
            return result.get("response", "").strip(), result.get("context", None)
        except requests.exceptions.ConnectionError:
            print("\nErreur: Impossible de se connecter au serveur Ollama. Assurez-vous qu'il est en cours d'exécution.")
            return "", None
        except requests.exceptions.Timeout:
            print("\nErreur: La requête a expiré. Le modèle prend trop de temps à répondre.")
            return "", None
        except requests.exceptions.RequestException as e:
            print(f"\nErreur lors de la requête à Ollama: {e}")
            return "", None
    
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
            response = requests.get(OLLAMA_MODELS_URL, timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                if models:
                    print("\nModèles disponibles:")
                    for model in models:
                        name = model.get('name')
                        size = model.get('size', 0) / (1024 * 1024 * 1024)  # Convertir en GB
                        print(f" - {name} ({size:.2f} GB)")
        except:
            pass
        
        print("\nRaccourcis clavier:")
        print(" - Ctrl+C: Quitter le programme")
        print(" - !info: Afficher ces informations")
        print(" - !model <nom>: Changer de modèle")
        print(" - !history: Afficher l'historique des commandes")
        print(" - !exit: Quitter le programme")
        print(" - !exec <commande>: Exécuter directement une commande shell")
    
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
        
        # Vérifier si le modèle existe, sinon tenter de le télécharger
        try:
            response = requests.get(OLLAMA_MODELS_URL, timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [model.get("name") for model in models]
                
                if model_name not in model_names:
                    print(f"Le modèle '{model_name}' n'est pas disponible. Tentative de téléchargement...")
                    if not self._pull_model(model_name):
                        print(f"Impossible d'utiliser le modèle '{model_name}'. Le modèle '{self.model}' est conservé.")
                        return
        except Exception as e:
            print(f"Erreur lors de la vérification du modèle: {e}")
            return
        
        # Changer le modèle
        self.model = model_name
        self._save_model_preference()
        print(f"Modèle changé pour: {self.model}")
    
    def select_commands(self, commands: List[str]) -> List[str]:
        """Permet à l'utilisateur de sélectionner les commandes à exécuter."""
        if not commands:
            return []
        
        if len(commands) == 1:
            confirm = input(f"\nExécuter cette commande ? \n[{commands[0]}] (oui/non/éditer) : ").lower()
            if confirm in ("éditer", "editer", "edit", "e"):
                edited_cmd = input(f"Éditer la commande : [{commands[0]}] > ")
                return [edited_cmd if edited_cmd.strip() else commands[0]]
            return commands if confirm in ("oui", "o", "yes", "y") else []
        
        print("\n=== Commandes disponibles ===")
        for i, cmd in enumerate(commands, 1):
            print(f"{i}. {cmd}")
        
        print("\nOptions:")
        print("- Entrez le numéro d'une commande pour l'exécuter (ex: '2')")
        print("- Entrez plusieurs numéros séparés par des espaces (ex: '1 3')")
        print("- Entrez 'all' ou '*' pour toutes les exécuter")
        print("- Entrez 'none' ou '0' pour n'en exécuter aucune")
        print("- Entrez 'e:X' pour éditer la commande numéro X")
        
        while True:
            choice = input("\nVotre choix : ").strip().lower()
            
            if choice in ("none", "0", "n", "non", "no"):
                return []
            
            if choice in ("all", "*", "a", "tout"):
                return commands
            
            # Mode édition
            if choice.startswith("e:") or choice.startswith("éditer:") or choice.startswith("editer:"):
                try:
                    parts = choice.split(":", 1)
                    if len(parts) < 2:
                        print("Format incorrect. Utilisez 'e:X' où X est le numéro de la commande.")
                        continue
                    
                    idx = int(parts[1])
                    if 1 <= idx <= len(commands):
                        original_cmd = commands[idx-1]
                        edited_cmd = input(f"Éditer la commande : [{original_cmd}] > ")
                        if edited_cmd.strip():
                            commands[idx-1] = edited_cmd
                            print(f"Commande {idx} mise à jour.")
                        continue
                    else:
                        print(f"Erreur: Le numéro {idx} est hors limites.")
                        continue
                except ValueError:
                    print("Numéro de commande invalide.")
                    continue
            
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
                        confirm = input(f"\nConfirmer l'exécution de : \n[{selected}] (oui/non/éditer) : ").lower()
                        if confirm in ("éditer", "editer", "edit", "e"):
                            edited_cmd = input(f"Éditer la commande : [{selected}] > ")
                            return [edited_cmd if edited_cmd.strip() else selected]
                        return [selected] if confirm in ("oui", "o", "yes", "y") else []
                    else:
                        print(f"Erreur: Le numéro {idx} est hors limites.")
                except ValueError:
                    print("Entrée invalide. Veuillez utiliser les options proposées.")
    
    def exec_direct_command(self, command: str) -> None:
        """Exécute directement une commande shell."""
        if not command:
            print("Aucune commande spécifiée.")
            return
        
        self._save_history(command)
        self.run_shell_command(command)
    
    def get_system_info(self) -> str:
        """Récupère les informations système pour le contexte."""
        osname = platform.system()
        release = platform.release()
        if osname == "Linux":
            try:
                distro = subprocess.check_output("cat /etc/os-release | grep PRETTY_NAME", shell=True, text=True)
                distro = distro.split("=")[1].strip().strip('"')
            except:
                distro = "Linux"
            return f"{distro} {release}"
        return f"{osname} {release}"
    
    def main(self) -> None:
        """Fonction principale du programme."""
        print(f"=== Ollama Terminal ===")
        print(f"Modèle actuel: {self.model}")
        print("Tapez votre demande ou '!help' pour les commandes disponibles.")
        
        # Contexte pour la conversation
        conversation_context = None
        system_info = self.get_system_info()
        
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
                    print("  !exec <commande> - Exécuter directement une commande shell")
                    print("  !context - Réinitialiser le contexte de conversation")
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
                
                if user_input.lower() == "!context":
                    conversation_context = None
                    print("Contexte de conversation réinitialisé.")
                    continue
                
                if user_input.lower().startswith("!exec "):
                    command = user_input[6:].strip()
                    if command:
                        self.exec_direct_command(command)
                    continue
                
                # Assurer que le serveur est en cours d'exécution
                if not self._ensure_server_running():
                    continue
                
                # Assurer que le modèle est disponible
                if not self._ensure_model_available():
                    continue
                
                # Traitement des demandes normales
                prompt = (
                    f"Je suis un assistant IA sur {system_info}. "
                    f"Donne-moi une ou plusieurs commandes bash précises "
                    f"pour accomplir cette tâche : '{user_input}'. Ne donne que les lignes de commande valides, "
                    f"sans explication, sans bloc markdown, sans guillemets, ni numérotation."
                )
                
                command_output, new_context = self.ask_ollama(prompt, conversation_context)
                
                # Mettre à jour le contexte si disponible
                if new_context:
                    conversation_context = new_context
                
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