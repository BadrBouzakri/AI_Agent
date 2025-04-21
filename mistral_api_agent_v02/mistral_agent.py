#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mistral Agent - Un assistant IA pour terminal Linux
Utilise le modèle Mistral pour assister dans les tâches DevOps et SysAdmin
"""

import os
import sys
import re
import json
import logging
import readline
import subprocess
import requests
from datetime import datetime
import argparse
from typing import List, Dict, Any, Optional, Tuple
import shlex
import signal

# Bibliothèques pour l'interface
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.syntax import Syntax
    from rich import box
    import typer
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("Pour une meilleure expérience visuelle, installez rich et typer: pip install rich typer")

# Paramètres constants
API_KEY = "n46jy69eatOFdxAI7Rb0PXsj6jrVv16K"
API_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL = "mistral-large-latest"
SCRIPTS_DIR = os.path.expanduser("~/tech/scripts")
LOG_FILE = os.path.expanduser("~/.ia_agent_logs.log")
HISTORY_FILE = os.path.expanduser("~/.ia_agent_history.json")
MAX_HISTORY_ENTRIES = 20
DANGEROUS_COMMANDS = ["rm", "mv", "dd", "mkfs", "fdisk", ">", "2>", "truncate", "rmdir", "pkill", "kill"]

# Initialisation du logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Classe principale de l'agent
class MistralAgent:
    def __init__(self, language="fr", debug=False):
        # Création du répertoire pour les scripts s'il n'existe pas
        os.makedirs(SCRIPTS_DIR, exist_ok=True)
        
        self.debug = debug
        self.language = language
        self.console = Console() if HAS_RICH else None
        self.conversation_history = []
        self.load_history()
        self.setup_signal_handlers()
        
        # Conserver le répertoire de travail actuel
        self.current_dir = os.getcwd()
        
        # Message système initial qui explique le rôle de l'agent
        self.system_message = """
Tu es un agent IA basé sur le modèle Mistral, conçu pour assister dans les tâches Linux et DevOps.
Tu dois être concis, précis et aider l'utilisateur à exécuter des tâches dans un terminal Linux.
Tu peux exécuter des commandes shell, créer des scripts (Bash, Python, YAML, etc.), et naviguer dans le système de fichiers.

Voici comment tu dois répondre:
1. Pour une commande à exécuter directement: [EXEC] commande [/EXEC]
2. Pour créer un script: [SCRIPT type nom_fichier] contenu [/SCRIPT]
3. Pour du texte normal: Réponds simplement sans aucun tag spécial
4. Pour naviguer entre les répertoires: tu peux utiliser [EXEC] cd chemin [/EXEC] et j'adapterai le répertoire de travail en conséquence.

N'utilise pas de formatage markdown complexe. Sois concis.
Pour les commandes dangereuses (rm, mv, etc.), avertis l'utilisateur d'abord.
"""
        # Personnalisation selon la langue
        self.prompt_text = f"🤖 Mistral@{os.path.basename(self.current_dir)} $ " if language == "fr" else f"🤖 Mistral@{os.path.basename(self.current_dir)} $ "

    def setup_signal_handlers(self):
        """Configure les gestionnaires de signaux pour une sortie propre"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, sig, frame):
        """Gère les signaux d'interruption"""
        print("\nFermeture propre de l'agent Mistral...")
        self.save_history()
        sys.exit(0)

    def load_history(self):
        """Charge l'historique des conversations"""
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    self.conversation_history = json.load(f)
                    # Limiter la taille de l'historique
                    if len(self.conversation_history) > MAX_HISTORY_ENTRIES:
                        self.conversation_history = self.conversation_history[-MAX_HISTORY_ENTRIES:]
            except Exception as e:
                logging.error(f"Erreur lors du chargement de l'historique: {e}")
                self.conversation_history = []
    
    def save_history(self):
        """Sauvegarde l'historique des conversations"""
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde de l'historique: {e}")

    def get_prompt(self):
        """Affiche le prompt personnalisé avec le répertoire courant"""
        # Mettre à jour le prompt avec le répertoire actuel
        dir_name = os.path.basename(self.current_dir)
        if dir_name == "":  # Si on est à la racine
            dir_name = "/"
            
        prompt = f"🤖 Mistral@{dir_name} $ "
        
        if HAS_RICH:
            return self.console.input(f"[bold cyan]{prompt}[/bold cyan]")
        else:
            return input(prompt)

    def is_dangerous_command(self, command):
        """Vérifie si une commande est potentiellement dangereuse"""
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
            
        return False

    def execute_command(self, command):
        """Exécute une commande shell et retourne le résultat"""
        logging.info(f"Exécution de la commande: {command}")
        
        # Gestion spéciale pour la commande cd
        if command.strip().startswith("cd "):
            try:
                # Extraire le chemin cible
                target_dir = command.strip()[3:].strip()
                
                # Gestion des chemins relatifs ou absolus
                if target_dir.startswith('/'):
                    new_dir = target_dir  # Chemin absolu
                else:
                    new_dir = os.path.join(self.current_dir, target_dir)
                
                # Résoudre les chemins comme ../ ou ./
                new_dir = os.path.abspath(new_dir)
                
                # Vérifier si le répertoire existe
                if os.path.isdir(new_dir):
                    os.chdir(new_dir)
                    self.current_dir = new_dir
                    return f"Répertoire courant : {new_dir}"
                else:
                    return f"Erreur: Le répertoire {new_dir} n'existe pas."
            except Exception as e:
                logging.error(f"Erreur lors du changement de répertoire: {e}")
                return f"Erreur lors du changement de répertoire: {str(e)}"
        
        # Pour les autres commandes, vérifier si elles sont dangereuses
        if self.is_dangerous_command(command):
            if HAS_RICH:
                confirm = Confirm.ask(f"[bold red]⚠️ Commande potentiellement dangereuse: [/bold red][yellow]{command}[/yellow]. Confirmer l'exécution?")
            else:
                confirm = input(f"⚠️ Commande potentiellement dangereuse: {command}. Confirmer l'exécution? [o/N] ").lower() == 'o'
            
            if not confirm:
                return "Commande annulée par l'utilisateur."
        
        try:
            # Exécuter la commande dans le répertoire courant
            process = subprocess.Popen(
                command, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                cwd=self.current_dir  # Utiliser le répertoire courant
            )
            stdout, stderr = process.communicate()
            
            result = stdout.decode('utf-8')
            error = stderr.decode('utf-8')
            
            if process.returncode != 0:
                return f"Erreur (code {process.returncode}):\n{error}"
            else:
                return result
        except Exception as e:
            logging.error(f"Erreur lors de l'exécution de la commande: {e}")
            return f"Erreur: {str(e)}"

    def save_script(self, script_type, filename, content):
        """Sauvegarde un script généré dans le répertoire approprié"""
        # Détermination de l'extension appropriée
        extensions = {
            "python": ".py",
            "bash": ".sh",
            "shell": ".sh",
            "yaml": ".yaml",
            "yml": ".yml",
            "docker": ".dockerfile",
            "dockerfile": ".dockerfile",
            "terraform": ".tf",
            "json": ".json",
            "js": ".js",
            "ansible": ".yml",
            "php": ".php",
            "ruby": ".rb",
            "go": ".go",
            "java": ".java",
            "c": ".c",
            "cpp": ".cpp",
            "csharp": ".cs",
            "sql": ".sql",
        }
        
        # Vérification si le nom de fichier a déjà une extension
        has_extension = "." in filename
        
        # Si pas d'extension et qu'on a un type connu, ajouter l'extension
        if not has_extension and script_type.lower() in extensions:
            filename = filename + extensions[script_type.lower()]
            
        # Chemin complet du fichier
        filepath = os.path.join(SCRIPTS_DIR, filename)
        
        # Sauvegarde du fichier
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Rendre exécutable les scripts shell et python
            if script_type.lower() in ["bash", "shell", "python"]:
                os.chmod(filepath, 0o755)
                
            logging.info(f"Script {script_type} sauvegardé: {filepath}")
            return filepath
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde du script: {e}")
            return f"Erreur lors de la sauvegarde: {str(e)}"

    def call_mistral_api(self, user_message):
        """Appelle l'API Mistral pour obtenir une réponse"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
        
        # Préparer les messages pour l'API
        messages = [
            {"role": "system", "content": self.system_message}
        ]
        
        # Ajouter l'historique de conversation
        for entry in self.conversation_history:
            messages.append(entry)
            
        # Ajouter le message de l'utilisateur
        messages.append({"role": "user", "content": user_message})
        
        payload = {
            "model": MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4000
        }
        
        try:
            response = requests.post(API_URL, headers=headers, json=payload)
            
            if response.status_code == 200:
                response_data = response.json()
                if self.debug:
                    print(json.dumps(response_data, indent=2))
                    
                assistant_message = response_data['choices'][0]['message']['content']
                
                # Mettre à jour l'historique de conversation
                self.conversation_history.append({"role": "user", "content": user_message})
                self.conversation_history.append({"role": "assistant", "content": assistant_message})
                
                # Limiter la taille de l'historique
                if len(self.conversation_history) > MAX_HISTORY_ENTRIES * 2:
                    self.conversation_history = self.conversation_history[-MAX_HISTORY_ENTRIES * 2:]
                    
                return assistant_message
            else:
                error_message = f"Erreur API ({response.status_code}): {response.text}"
                logging.error(error_message)
                return f"Erreur lors de l'appel à l'API Mistral: {error_message}"
        except Exception as e:
            logging.error(f"Exception lors de l'appel à l'API: {str(e)}")
            return f"Erreur de connexion à l'API Mistral: {str(e)}"

    def process_response(self, response):
        """Traite la réponse de l'API pour exécuter des commandes ou créer des scripts"""
        # Rechercher les commandes à exécuter
        exec_pattern = r"\[EXEC\](.*?)\[\/EXEC\]"
        script_pattern = r"\[SCRIPT\s+(\w+)\s+([^\]]+)\](.*?)\[\/SCRIPT\]"
        
        # Exécution des commandes
        for match in re.finditer(exec_pattern, response, re.DOTALL):
            command = match.group(1).strip()
            result = self.execute_command(command)
            
            if HAS_RICH:
                self.console.print("\n[bold green]Commande:[/bold green]")
                self.console.print(Syntax(command, "bash"))
                self.console.print("\n[bold green]Résultat:[/bold green]")
                self.console.print(result)
            else:
                print(f"\nCommande: {command}")
                print(f"Résultat: {result}")
        
        # Création de scripts
        for match in re.finditer(script_pattern, response, re.DOTALL):
            script_type = match.group(1).strip()
            script_name = match.group(2).strip()
            script_content = match.group(3).strip()
            
            filepath = self.save_script(script_type, script_name, script_content)
            
            if HAS_RICH:
                self.console.print(f"\n[bold green]Script {script_type} créé:[/bold green] {filepath}")
                self.console.print(Syntax(script_content, script_type.lower()))
                
                # Demander si l'utilisateur veut exécuter le script
                if script_type.lower() in ["bash", "shell", "python"]:
                    if Confirm.ask("Voulez-vous exécuter ce script maintenant?"):
                        if script_type.lower() == "python":
                            cmd = f"python3 {filepath}"
                        else:
                            cmd = filepath
                            
                        result = self.execute_command(cmd)
                        self.console.print("\n[bold green]Résultat de l'exécution:[/bold green]")
                        self.console.print(result)
            else:
                print(f"\nScript {script_type} créé: {filepath}")
                print(f"\n--- Début du script ---\n{script_content}\n--- Fin du script ---")
                
                # Demander si l'utilisateur veut exécuter le script
                if script_type.lower() in ["bash", "shell", "python"]:
                    if input("Voulez-vous exécuter ce script maintenant? [o/N] ").lower() == 'o':
                        if script_type.lower() == "python":
                            cmd = f"python3 {filepath}"
                        else:
                            cmd = filepath
                            
                        result = self.execute_command(cmd)
                        print(f"\nRésultat de l'exécution:\n{result}")
        
        # Afficher le texte normal (sans les tags spéciaux)
        clean_response = re.sub(exec_pattern, "", response)
        clean_response = re.sub(script_pattern, "", clean_response)
        clean_response = clean_response.strip()
        
        if clean_response:
            if HAS_RICH:
                self.console.print(Panel(clean_response, border_style="cyan", box=box.ROUNDED))
            else:
                print(f"\n{clean_response}\n")

    def run(self):
        """Démarre la boucle principale de l'agent"""
        if HAS_RICH:
            self.console.print(Panel.fit(
                "[bold cyan]Agent IA Mistral[/bold cyan] - Assistant DevOps et SysAdmin",
                border_style="cyan",
                box=box.DOUBLE_EDGE
            ))
            self.console.print(f"[bold]Langue:[/bold] {self.language} | [bold]Répertoire des scripts:[/bold] {SCRIPTS_DIR}")
            self.console.print(f"[bold]Répertoire courant:[/bold] {self.current_dir}")
            self.console.print("[bold]Commandes spéciales:[/bold]")
            self.console.print("  • [cyan]exit[/cyan] ou [cyan]quit[/cyan] : quitter")
            self.console.print("  • [cyan]clear[/cyan] : effacer l'écran")
            self.console.print("  • [cyan]pwd[/cyan] : afficher le répertoire courant")
            self.console.print("  • [cyan]cd[/cyan] [path] : changer de répertoire\n")
        else:
            print("====== Agent IA Mistral - Assistant DevOps et SysAdmin ======")
            print(f"Langue: {self.language} | Répertoire des scripts: {SCRIPTS_DIR}")
            print(f"Répertoire courant: {self.current_dir}")
            print("Commandes spéciales:")
            print("  • exit ou quit : quitter")
            print("  • clear : effacer l'écran")
            print("  • pwd : afficher le répertoire courant")
            print("  • cd [path] : changer de répertoire\n")

                    # Boucle principale
        while True:
            try:
                user_input = self.get_prompt()
                
                # Commandes spéciales
                if user_input.lower() in ['exit', 'quit']:
                    self.save_history()
                    break
                elif user_input.lower() == 'clear':
                    os.system('clear')
                    continue
                elif user_input.lower() == 'pwd':
                    if HAS_RICH:
                        self.console.print(f"[bold green]Répertoire courant:[/bold green] {self.current_dir}")
                    else:
                        print(f"Répertoire courant: {self.current_dir}")
                    continue
                elif not user_input.strip():
                    continue
                elif user_input.startswith('cd '):
                    # Gérer directement les commandes cd sans passer par l'API
                    result = self.execute_command(user_input)
                    if HAS_RICH:
                        self.console.print(f"[bold green]{result}[/bold green]")
                    else:
                        print(result)
                    continue
                elif user_input.lower() == 'ls' or user_input.lower() == 'ls -la':
                    # Exécuter ls directement pour plus de réactivité
                    result = self.execute_command(user_input)
                    if HAS_RICH:
                        self.console.print(Syntax(result, "bash"))
                    else:
                        print(result)
                    continue
                
                # Appel à l'API Mistral
                assistant_response = self.call_mistral_api(user_input)
                
                # Traitement de la réponse
                self.process_response(assistant_response)
                
                # Sauvegarde périodique de l'historique
                self.save_history()
                
            except KeyboardInterrupt:
                print("\nInterruption détectée. Pour quitter, tapez 'exit'.")
            except Exception as e:
                logging.error(f"Erreur dans la boucle principale: {str(e)}")
                if self.debug:
                    import traceback
                    traceback.print_exc()
                if HAS_RICH:
                    self.console.print(f"[bold red]Erreur:[/bold red] {str(e)}")
                else:
                    print(f"Erreur: {str(e)}")

def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(description="Agent IA Mistral pour terminal Linux")
    parser.add_argument("--lang", "-l", choices=["fr", "en"], default="fr", help="Langue de l'agent (fr/en)")
    parser.add_argument("--debug", "-d", action="store_true", help="Mode debug")
    parser.add_argument("--scripts-dir", "-s", help="Répertoire pour les scripts générés")
    parser.add_argument("--start-dir", "-cd", help="Répertoire de démarrage")
    parser.add_argument("--shell-completion", action="store_true", help="Installer la complétion shell")
    args = parser.parse_args()
    
    # Configuration du répertoire des scripts si spécifié
    if args.scripts_dir:
        global SCRIPTS_DIR
        SCRIPTS_DIR = os.path.expanduser(args.scripts_dir)
    
    # Création du répertoire des scripts s'il n'existe pas
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    
    # Configuration du répertoire de démarrage
    if args.start_dir:
        start_dir = os.path.expanduser(args.start_dir)
        if os.path.isdir(start_dir):
            os.chdir(start_dir)
        else:
            print(f"Le répertoire de démarrage {start_dir} n'existe pas. Utilisation du répertoire courant.")
            
    # Installation de la complétion shell
    if args.shell_completion:
        try:
            shell_config = os.path.expanduser("~/.bashrc")
            if os.path.exists(os.path.expanduser("~/.zshrc")):
                shell_config = os.path.expanduser("~/.zshrc")
                
            completion_script = f"""
# Complétion pour l'agent Mistral IA
_mistral_completions()
{{
    local cur prev opts
    COMPREPLY=()
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"
    opts="--lang --debug --scripts-dir --start-dir --shell-completion"
    
    if [[ ${{prev}} == "--lang" ]]; then
        COMPREPLY=( $(compgen -W "fr en" -- ${{cur}}) )
        return 0
    elif [[ ${{prev}} == "--scripts-dir" || ${{prev}} == "--start-dir" || ${{prev}} == "-s" || ${{prev}} == "-cd" ]]; then
        COMPREPLY=( $(compgen -d -- ${{cur}}) )
        return 0
    fi
    
    if [[ ${{cur}} == -* ]]; then
        COMPREPLY=( $(compgen -W "${{opts}}" -- ${{cur}}) )
        return 0
    fi
}}
complete -F _mistral_completions mistral
"""
            with open(shell_config, "a") as f:
                f.write(completion_script)
            print(f"Complétion shell installée dans {shell_config}. Rechargez votre shell ou exécutez 'source {shell_config}'.")
            sys.exit(0)
        except Exception as e:
            print(f"Erreur lors de l'installation de la complétion shell: {e}")
            sys.exit(1)
    
    # Démarrage de l'agent
    agent = MistralAgent(language=args.lang, debug=args.debug)
    agent.run()

if __name__ == "__main__":
    main()