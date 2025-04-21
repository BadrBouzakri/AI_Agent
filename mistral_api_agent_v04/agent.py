#!/usr/bin/env python3
"""
DevOps CLI Agent - Assistant intelligent pour l'administration système et DevOps
Version améliorée basée sur le code Mistral Agent
"""

import os
import sys
import subprocess
import json
import re
import signal
import shlex
import logging
import readline
import requests
from datetime import datetime
import time
import shutil

# Configuration
MISTRAL_API_KEY = "n46jy69eatOFdxAI7Rb0PXsj6jrVv16K"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-large-latest"  # Utilisation du dernier modèle disponible
COMMAND_HISTORY = []
HISTORY_FILE = os.path.expanduser("~/.devops_agent_history.json")
LOG_FILE = os.path.expanduser("~/.devops_agent_logs.log")
SCRIPTS_DIR = os.path.expanduser("~/tech/scripts")
MAX_HISTORY_ENTRIES = 20
TERMINAL_WIDTH = shutil.get_terminal_size().columns
VERSION = "1.0.1"
DANGEROUS_COMMANDS = ["rm", "mv", "dd", "mkfs", "fdisk", ">", "2>", "truncate", "rmdir", "pkill", "kill"]

# Configuration du logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Couleurs pour le terminal
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_banner():
    """Affiche la bannière de l'agent DevOps"""
    banner = f"""
{BLUE}╔══════════════════════════════════════════════════════════════════╗
║ {BOLD}DevOps CLI Agent v{VERSION}{RESET}{BLUE}                                          ║
║ {YELLOW}Assistant intelligent pour l'administration système et DevOps{RESET}{BLUE}       ║
╚══════════════════════════════════════════════════════════════════╝{RESET}
"""
    print(banner)

def signal_handler(sig, frame):
    """Gère l'interruption propre du programme"""
    print(f"\n\n{YELLOW}Session terminée. À bientôt !{RESET}")
    save_history()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def load_history():
    """Charge l'historique des interactions"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
                return history
        except Exception as e:
            logging.error(f"Erreur lors du chargement de l'historique: {e}")
    return []

def save_history():
    """Sauvegarde l'historique des interactions"""
    if len(COMMAND_HISTORY) > 0:
        try:
            # Limiter la taille de l'historique
            history_to_save = COMMAND_HISTORY[-MAX_HISTORY_ENTRIES:] if len(COMMAND_HISTORY) > MAX_HISTORY_ENTRIES else COMMAND_HISTORY
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(history_to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde de l'historique: {e}")

def is_dangerous_command(command):
    """Vérifie si une commande est potentiellement dangereuse"""
    try:
        command_parts = shlex.split(command)
        if not command_parts:
            return False
            
        base_cmd = command_parts[0]
        
        # Vérifier les commandes dangereuses directes
        if base_cmd in DANGEROUS_COMMANDS:
            return True
            
        # Vérifier les redirections et pipes dangereux
        if ">" in command or "|" in command and ("rm" in command or "mv" in command):
            return True
            
        # Vérifier les options dangereuses spécifiques
        if base_cmd == "rm" and "-rf" in command_parts:
            return True
    except:
        # En cas d'erreur dans l'analyse, considérer comme potentiellement dangereux
        return True
            
    return False

def send_to_mistral(prompt, system_message, conversation_history=None):
    """Envoie une requête à l'API Mistral avec gestion de l'historique de conversation"""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {MISTRAL_API_KEY}"
    }
    
    # Préparation des messages
    messages = [
        {"role": "system", "content": system_message}
    ]
    
    # Ajout de l'historique de conversation si fourni
    if conversation_history:
        for entry in conversation_history:
            messages.append(entry)
    
    # Ajout du message utilisateur actuel
    messages.append({"role": "user", "content": prompt})
    
    data = {
        "model": MISTRAL_MODEL,
        "messages": messages,
        "temperature": 0.3,  # Température plus basse pour des réponses plus cohérentes
        "max_tokens": 2048
    }
    
    try:
        logging.info(f"Envoi de requête à l'API Mistral: {prompt[:100]}...")
        response = requests.post(MISTRAL_API_URL, headers=headers, json=data)
        response.raise_for_status()  # Lève une exception pour les erreurs HTTP
        
        return response.json()["choices"][0]["message"]["content"], messages
    except requests.exceptions.HTTPError as e:
        logging.error(f"Erreur HTTP lors de la communication avec l'API Mistral: {e}")
        error_detail = f"Code: {e.response.status_code}, Message: {e.response.text}" if hasattr(e, 'response') else str(e)
        return f"Erreur HTTP: {error_detail}", messages
    except requests.exceptions.ConnectionError:
        logging.error("Erreur de connexion à l'API Mistral")
        return "Erreur de connexion à l'API Mistral. Vérifiez votre connexion internet.", messages
    except requests.exceptions.Timeout:
        logging.error("Timeout lors de la connexion à l'API Mistral")
        return "Timeout lors de la connexion à l'API Mistral. Réessayez plus tard.", messages
    except Exception as e:
        logging.error(f"Erreur inattendue lors de la communication avec l'API Mistral: {e}")
        return f"Erreur inattendue: {str(e)}", messages

def execute_command(command, cwd=None):
    """Exécute une commande shell et retourne la sortie"""
    try:
        # Ajout de la commande à l'historique
        COMMAND_HISTORY.append(command)
        
        # Vérification si c'est une commande dangereuse
        if is_dangerous_command(command):
            confirm = input(f"{YELLOW}⚠️ Commande potentiellement dangereuse: {command}\nConfirmer l'exécution? (oui/non) >{RESET} ")
            if confirm.lower() not in ['oui', 'o', 'yes', 'y']:
                return True, "Exécution annulée."
        
        # Exécution de la commande dans le répertoire spécifié ou courant
        result = subprocess.run(command, shell=True, text=True, capture_output=True, cwd=cwd)
        
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr
    except Exception as e:
        logging.error(f"Erreur lors de l'exécution de la commande {command}: {e}")
        return False, str(e)

def paginate_output(text):
    """Pagine la sortie dans le terminal"""
    lines = text.split('\n')
    terminal_height = shutil.get_terminal_size().lines - 4
    
    if len(lines) <= terminal_height:
        print(text)
        return
    
    for i in range(0, len(lines), terminal_height):
        chunk = lines[i:i + terminal_height]
        print('\n'.join(chunk))
        
        if i + terminal_height < len(lines):
            input(f"{YELLOW}Appuyez sur Entrée pour continuer...{RESET}")

def show_history():
    """Affiche l'historique des commandes"""
    if not COMMAND_HISTORY:
        print(f"{YELLOW}Aucune commande exécutée durant cette session.{RESET}")
        return
    
    print(f"{BLUE}=== Historique des commandes ==={RESET}")
    for i, cmd in enumerate(COMMAND_HISTORY, 1):
        print(f"{i}. {cmd}")

def generate_system_prompt():
    """Génère le prompt système pour l'API Mistral"""
    system_message = """
Tu es un agent intelligent spécialisé en administration systèmes et DevOps, conçu pour assister un administrateur expérimenté directement depuis un terminal Ubuntu 24.04. Tu interagis uniquement via la ligne de commande.
Tu dois :
- Comprendre les requêtes de l'utilisateur comme un assistant shell intelligent.
- Fournir des commandes shell (bash) précises pour :
  - Gérer les utilisateurs, groupes, droits, services, packages, logs.
  - Travailler avec les conteneurs Docker / pods Kubernetes.
  - Déployer et superviser des applications (CI/CD, monitoring, infrastructure).
  - Créer, modifier, supprimer des fichiers et répertoires.
  - Modifier la configuration réseau, firewalls, services (systemd, Nginx, etc).
- Expliquer chaque action avant de l'exécuter.
- Attendre une confirmation explicite (`oui/non`) avant d'exécuter toute commande.
- Répondre de manière concise et technique, comme un assistant Linux professionnel.
- Afficher les sorties des commandes de manière lisible dans le terminal (pagination si besoin).
- Garder un historique des commandes exécutées durant la session.
- Proposer automatiquement des optimisations ou sécurisations après chaque tâche.

Contexte :
- Tu travailles exclusivement sur ce terminal local.
- L'utilisateur est un administrateur DevOps expérimenté.
- Tu dois répondre en français technique, sauf si on te demande l'anglais.

Limites :
- Pas d'interface graphique.
- Pas de génération de contenu inutile.
- Toujours demander validation avant modification.

Format de réponse :
1. **Résumé de la tâche**
2. **Commande(s) proposée(s)**
3. **Attente de confirmation**
4. **Exécution avec sortie**
5. **Conseils ou questions suivantes**

N'utilise pas de Markdown. Formate ta réponse pour un affichage dans un terminal texte.
"""
    return system_message

def get_system_info():
    """Récupère des informations système basiques"""
    try:
        # Récupération de la version d'Ubuntu
        with open('/etc/os-release', 'r') as f:
            os_info = f.read()
            ubuntu_version = re.search(r'VERSION="(.*)"', os_info)
            if ubuntu_version:
                ubuntu_version = ubuntu_version.group(1)
            else:
                ubuntu_version = "Version inconnue"
        
        # Récupération du nom d'hôte
        hostname = subprocess.check_output("hostname", shell=True).decode().strip()
        
        # Récupération de l'utilisateur
        username = subprocess.check_output("whoami", shell=True).decode().strip()
        
        return f"Ubuntu {ubuntu_version} | Hôte: {hostname} | Utilisateur: {username}"
    except Exception as e:
        logging.error(f"Erreur lors de la récupération des infos système: {e}")
        return "Informations système non disponibles"

def save_script(script_content, filename=None):
    """Sauvegarde un script dans le répertoire des scripts"""
    # Création du répertoire des scripts si nécessaire
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    
    # Génération d'un nom de fichier unique si non spécifié
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"script_{timestamp}.sh"
    
    # Chemin complet du fichier
    filepath = os.path.join(SCRIPTS_DIR, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        # Rendre le script exécutable
        os.chmod(filepath, 0o755)
        
        logging.info(f"Script sauvegardé: {filepath}")
        return filepath
    except Exception as e:
        logging.error(f"Erreur lors de la sauvegarde du script: {e}")
        return None

def main():
    """Fonction principale de l'agent"""
    print_banner()
    
    # Créer le répertoire des scripts s'il n'existe pas
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    
    system_info = get_system_info()
    print(f"{GREEN}Système: {system_info}{RESET}")
    print(f"{YELLOW}Tapez 'exit' ou 'quit' pour quitter, 'history' pour voir l'historique des commandes.{RESET}\n")
    
    system_prompt = generate_system_prompt()
    conversation_history = []
    
    # Charger l'historique des commandes
    global COMMAND_HISTORY
    COMMAND_HISTORY = load_history()
    
    while True:
        try:
            user_input = input(f"{BOLD}{BLUE}DevOps CLI Agent >{RESET} ")
            
            if user_input.lower() in ['exit', 'quit']:
                print(f"{YELLOW}Session terminée. À bientôt !{RESET}")
                save_history()
                break
                
            if user_input.lower() == 'history':
                show_history()
                continue
                
            if user_input.lower() == 'clear':
                os.system('clear' if os.name == 'posix' else 'cls')
                continue
                
            if not user_input.strip():
                continue
            
            # Gestion spéciale pour les commandes simples (pour plus de réactivité)
            if user_input.lower() in ['ls', 'pwd', 'whoami', 'hostname']:
                success, output = execute_command(user_input)
                if success:
                    print(output)
                else:
                    print(f"{RED}Erreur: {output}{RESET}")
                continue
            
            # Enrichissement du contexte utilisateur
            enriched_input = f"Requête: {user_input}\nContexte système: {system_info}"
            
            # Envoi de la requête à l'API Mistral
            print(f"{YELLOW}Analyse en cours...{RESET}")
            response, updated_messages = send_to_mistral(enriched_input, system_prompt, conversation_history)
            
            # Mise à jour de l'historique de conversation (limité pour économiser des tokens)
            if len(updated_messages) > 3:  # On garde le message système + les 2 derniers échanges
                conversation_history = [updated_messages[0]] + updated_messages[-4:]
            else:
                conversation_history = updated_messages
            
            # Traitement de la réponse
            print("\n" + "=" * TERMINAL_WIDTH)
            print(response)
            print("=" * TERMINAL_WIDTH + "\n")
            
            # Attente de la confirmation de l'utilisateur si une commande est proposée
            if "Souhaitez-vous exécuter ces commandes? (oui/non)" in response:
                confirmation = input(f"{YELLOW}Confirmez l'exécution (oui/non) >{RESET} ")
                
                if confirmation.lower() in ['oui', 'o', 'yes', 'y']:
                    # Extraction des commandes à partir de la réponse
                    commands_section = re.search(r"Commande\(s\) proposée\(s\):(.*?)Souhaitez-vous", response, re.DOTALL)
                    
                    if commands_section:
                        commands_text = commands_section.group(1).strip()
                        
                        # Détection des scripts multilignes (avec délimiteurs)
                        script_match = re.search(r"cat\s+>\s+(\S+)\s+<<\s*['\"](.*?)['\"](.+?)\2", commands_text, re.DOTALL)
                        if script_match:
                            # C'est un script à enregistrer
                            script_file = script_match.group(1)
                            script_content = script_match.group(3)
                            
                            # Sauvegarde du script
                            script_name = os.path.basename(script_file)
                            saved_path = save_script(script_content, script_name)
                            
                            if saved_path:
                                print(f"{GREEN}Script sauvegardé: {saved_path}{RESET}")
                                
                                # Demander d'exécuter le script
                                run_script = input(f"{YELLOW}Voulez-vous exécuter ce script? (oui/non) >{RESET} ")
                                if run_script.lower() in ['oui', 'o', 'yes', 'y']:
                                    success, output = execute_command(f"bash {saved_path}")
                                    if success:
                                        paginate_output(output)
                                    else:
                                        print(f"{RED}Erreur: {output}{RESET}")
                        else:
                            # Extraire les commandes individuelles (ignorer les commentaires)
                            commands = []
                            for line in commands_text.split('\n'):
                                line = line.strip()
                                if line and not line.startswith('#'):
                                    commands.append(line)
                            
                            print(f"{BLUE}=== Exécution des commandes ==={RESET}")
                            for cmd in commands:
                                print(f"{GREEN}$ {cmd}{RESET}")
                                success, output = execute_command(cmd)
                                
                                if success:
                                    paginate_output(output)
                                else:
                                    print(f"{RED}Erreur: {output}{RESET}")
                            
                            print(f"{GREEN}Exécution terminée.{RESET}")
                    else:
                        print(f"{RED}Impossible d'extraire les commandes de la réponse.{RESET}")
                else:
                    print(f"{YELLOW}Exécution annulée.{RESET}")
            
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Opération annulée. Pour quitter, tapez 'exit' ou 'quit'.{RESET}")
            continue
        except Exception as e:
            logging.error(f"Erreur dans la boucle principale: {str(e)}")
            print(f"{RED}Erreur: {str(e)}{RESET}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"Erreur critique: {str(e)}")
        print(f"{RED}Erreur critique: {str(e)}\nConsultez le fichier de log pour plus de détails: {LOG_FILE}{RESET}")
    finally:
        save_history()