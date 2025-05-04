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
import glob
import fnmatch
import platform

# Bibliothèques pour l'interface
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.syntax import Syntax
    from rich import box
    from rich.table import Table
    from rich.progress import Progress
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
LOG_FILE = os.path.expanduser("~/.mistral_agent/logs/agent.log")
HISTORY_FILE = os.path.expanduser("~/.mistral_agent/history.json")
CONFIG_FILE = os.path.expanduser("~/.mistral_agent/config.json")
PROMPT_FILE = os.path.expanduser("~/.mistral_agent/prompt.txt")
CONTEXT_FILE = os.path.expanduser("~/.mistral_agent/context.json")
MAX_HISTORY_ENTRIES = 50
DANGEROUS_COMMANDS = ["rm", "mv", "dd", "mkfs", "fdisk", ">", "2>", "truncate", "rmdir", "pkill", "kill", ":(){:|:&};:"]

# Configuration par défaut
DEFAULT_CONFIG = {
    "api_key": API_KEY,
    "api_url": API_URL,
    "model": MODEL,
    "scripts_dir": SCRIPTS_DIR,
    "max_history": MAX_HISTORY_ENTRIES,
    "language": "fr",
    "theme": "default",
    "dangerous_commands": DANGEROUS_COMMANDS,
    "auto_save_scripts": True,
    "auto_execute_scripts": False,
    "debug_mode": False,
    "show_system_info": True,
    "use_streaming": True,
    "temperature": 0.7,
    "max_tokens": 4000
}

# Liste d'alias communs
COMMON_ALIASES = {
    "ll": "ls -l",
    "la": "ls -la",
    "grep": "grep --color=auto",
    "df": "df -h",
    "du": "du -h",
    "mkdir": "mkdir -p",
    "cls": "clear"
}

# Créer les répertoires nécessaires
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
os.makedirs(SCRIPTS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)

# Initialisation du logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class AdvancedCompleter:
    """Système avancé d'autocomplétion pour le terminal"""
    
    def __init__(self, agent):
        self.agent = agent
        self.commands = set()
        self.update_commands_list()
        self.matches = []
        self.current_match_index = 0
        self.current_input = ""
        self.completing_path = False
        self.path_prefix = ""
        
    def update_commands_list(self):
        """Met à jour la liste des commandes disponibles"""
        # Commandes de base
        base_commands = [
            "help", "exit", "quit", "clear", "history", "set-prompt", "set-api-key",
            "save-context", "load-context", "list-contexts", "config", "theme", "alias",
            "cd", "ls", "pwd", "cat", "grep", "find", "mkdir", "touch", "cp", "mv", "rm", 
            "chmod", "chown", "ps", "top", "df", "du", "free", "ifconfig", "ip", "ping", 
            "ssh", "scp", "rsync", "git", "docker", "kubectl", "terraform", "ansible", 
            "python", "pip", "npm", "yarn", "cargo", "go", "make", "gcc", "javac"
        ]
        
        # Ajouter toutes les commandes dans le PATH
        for path in os.environ.get("PATH", "").split(os.pathsep):
            if os.path.exists(path):
                try:
                    for cmd in os.listdir(path):
                        if os.path.isfile(os.path.join(path, cmd)) and os.access(os.path.join(path, cmd), os.X_OK):
                            base_commands.append(cmd)
                except Exception:
                    pass
        
        # Ajouter les scripts personnalisés
        if os.path.exists(SCRIPTS_DIR):
            for script in os.listdir(SCRIPTS_DIR):
                if os.path.isfile(os.path.join(SCRIPTS_DIR, script)) and os.access(os.path.join(SCRIPTS_DIR, script), os.X_OK):
                    base_commands.append(script)
        
        # Ajouter les alias
        for alias in self.agent.aliases.keys():
            base_commands.append(alias)
        
        # Mettre à jour la liste des commandes (sans doublons)
        self.commands = set(base_commands)
        
    def get_path_completions(self, path):
        """Obtenir les complétions pour un chemin"""
        if path.startswith("~"):
            path = os.path.expanduser(path)
            
        # Gérer le cas où on est au début d'un chemin
        if path == "" or path == "./" or path == "/":
            dirname = path
            prefix = ""
        else:
            dirname = os.path.dirname(path)
            prefix = os.path.basename(path)
            
            # Si le chemin ne contient pas de séparateur, utiliser le répertoire courant
            if dirname == "":
                dirname = "."
                
        # S'assurer que le répertoire existe
        if not os.path.isdir(dirname):
            return []
            
        try:
            # Obtenir tous les fichiers et répertoires dans le répertoire
            completions = []
            
            for item in os.listdir(dirname):
                # Ignorer les fichiers et répertoires cachés sauf si le préfixe commence par un point
                if item.startswith('.') and not prefix.startswith('.'):
                    continue
                    
                # Si le préfixe est vide ou l'élément commence par le préfixe
                if not prefix or item.startswith(prefix):
                    full_path = os.path.join(dirname, item)
                    
                    # Ajouter un slash pour les répertoires
                    if os.path.isdir(full_path):
                        completions.append(f"{item}/")
                    else:
                        completions.append(item)
                        
            return completions
        except Exception as e:
            logging.error(f"Erreur lors de la complétion de chemin: {e}")
            return []
            
    def complete(self, text, state):
        """Fonction d'autocomplétion pour readline"""
        if state == 0:
            line = readline.get_line_buffer()
            begin = readline.get_begidx()
            end = readline.get_endidx()
            
            # Si on est au milieu d'un chemin
            if " " in line[:begin]:
                # Nous complétions probablement un chemin
                cmd_parts = shlex.split(line[:begin])
                self.completing_path = True
                
                # Extraire le préfixe du chemin
                if begin == end:
                    self.path_prefix = ""
                else:
                    self.path_prefix = line[begin:end]
                    
                # Obtenir les complétions pour le chemin
                self.matches = self.get_path_completions(self.path_prefix)
            else:
                # Nous complétions une commande
                self.completing_path = False
                self.update_commands_list()  # Mise à jour des commandes disponibles
                
                if text:
                    self.matches = [cmd for cmd in self.commands if cmd.startswith(text)]
                else:
                    self.matches = list(self.commands)
                    
            self.current_match_index = 0
            self.current_input = text
            
        # Retourner la correspondance actuelle ou None si hors limites
        try:
            match = self.matches[state]
            return match
        except IndexError:
            return None

class MistralAgent:
    def __init__(self, language="fr", debug=False, long_prompt=False, start_dir=None, theme="default"):
        # Charger ou créer la configuration
        self.config = self.load_config()
        
        # Répertoire de démarrage
        if start_dir and os.path.isdir(os.path.expanduser(start_dir)):
            self.current_dir = os.path.abspath(os.path.expanduser(start_dir))
        else:
            self.current_dir = os.getcwd()
            
        # Mise à jour des paramètres avec ceux de la ligne de commande
        self.config["language"] = language
        self.config["debug_mode"] = debug
        self.config["theme"] = theme
        
        # Création du répertoire pour les scripts s'il n'existe pas
        os.makedirs(self.config["scripts_dir"], exist_ok=True)
        
        # Initialisation des composants
        self.console = Console() if HAS_RICH else None
        self.conversation_history = []
        self.context_data = {}
        self.aliases = self.load_aliases()
        self.load_history()
        self.setup_signal_handlers()
        
        # Initialisation de l'autocomplétion
        self.completer = AdvancedCompleter(self)
        self.setup_readline()
        
        # Message système initial
        self.system_message = self.load_system_message(long_prompt)
        
        # Journaliser le démarrage
        logging.info(f"Agent Mistral démarré: version=1.1.0, langue={language}, debug={debug}, theme={theme}")
        
    def load_config(self):
        """Charge la configuration ou crée le fichier par défaut"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Mettre à jour avec les valeurs par défaut manquantes
                    for key, value in DEFAULT_CONFIG.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                logging.error(f"Erreur lors du chargement de la configuration: {e}")
                
        # Si le fichier n'existe pas ou est invalide, créer le fichier par défaut
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Erreur lors de la création du fichier de configuration: {e}")
            
        return DEFAULT_CONFIG
        
    def save_config(self):
        """Sauvegarde la configuration actuelle"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde de la configuration: {e}")
            return False
    
    def load_aliases(self):
        """Charge les alias depuis la configuration ou utilise les alias par défaut"""
        if "aliases" in self.config:
            return self.config["aliases"]
        else:
            self.config["aliases"] = COMMON_ALIASES
            self.save_config()
            return COMMON_ALIASES
            
    def save_aliases(self):
        """Sauvegarde les alias dans la configuration"""
        self.config["aliases"] = self.aliases
        return self.save_config()
        
    def setup_readline(self):
        """Configure l'autocomplétion des commandes avec readline"""
        readline.set_completer(self.completer.complete)
        
        # Différent selon le système d'exploitation
        if sys.platform == 'darwin':  # macOS
            readline.parse_and_bind("bind ^I rl_complete")
        else:  # Linux et autres
            readline.parse_and_bind("tab: complete")
            
        readline.set_completer_delims(' \t\n')
        
        # Activer l'historique readline pour les flèches haut/bas
        histfile = os.path.expanduser("~/.mistral_agent/readline_history")
        try:
            os.makedirs(os.path.dirname(histfile), exist_ok=True)
            readline.read_history_file(histfile)
            readline.set_history_length(1000)
        except FileNotFoundError:
            pass
            
        # Sauvegarder l'historique à la fermeture
        import atexit
        atexit.register(readline.write_history_file, histfile)

    def load_system_message(self, use_long_prompt=False):
        """Charge le message système depuis le fichier ou utilise celui par défaut"""
        if use_long_prompt and os.path.exists(PROMPT_FILE):
            try:
                with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
                    custom_prompt = f.read()
                    if custom_prompt.strip():
                        return custom_prompt
            except Exception as e:
                logging.error(f"Erreur lors du chargement du prompt: {e}")
        
        # Message par défaut
        return """
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

Le répertoire de travail actuel est: {current_dir}
""".format(current_dir=self.current_dir)

    def save_system_message(self, message):
        """Sauvegarde le message système dans un fichier"""
        try:
            os.makedirs(os.path.dirname(PROMPT_FILE), exist_ok=True)
            with open(PROMPT_FILE, 'w', encoding='utf-8') as f:
                f.write(message)
            return True
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde du prompt: {e}")
            return False

    def setup_signal_handlers(self):
        """Configure les gestionnaires de signaux pour une sortie propre"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, sig, frame):
        """Gère les signaux d'interruption"""
        print("\nFermeture propre de l'agent Mistral...")
        self.save_history()
        self.save_config()
        sys.exit(0)

    def load_history(self):
        """Charge l'historique des conversations"""
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    self.conversation_history = json.load(f)
                    # Limiter la taille de l'historique
                    if len(self.conversation_history) > self.config["max_history"]:
                        self.conversation_history = self.conversation_history[-self.config["max_history"]:]
            except Exception as e:
                logging.error(f"Erreur lors du chargement de l'historique: {e}")
                self.conversation_history = []
    
    def save_history(self):
        """Sauvegarde l'historique des conversations"""
        try:
            os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde de l'historique: {e}")

    def save_context(self, name="default"):
        """Sauvegarde le contexte actuel"""
        context = {
            "history": self.conversation_history,
            "current_dir": self.current_dir,
            "system_message": self.system_message,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # Charger les contextes existants
            contexts = {}
            if os.path.exists(CONTEXT_FILE):
                with open(CONTEXT_FILE, 'r', encoding='utf-8') as f:
                    contexts = json.load(f)
                    
            # Ajouter/mettre à jour le contexte
            contexts[name] = context
            
            # Sauvegarder
            os.makedirs(os.path.dirname(CONTEXT_FILE), exist_ok=True)
            with open(CONTEXT_FILE, 'w', encoding='utf-8') as f:
                json.dump(contexts, f, ensure_ascii=False, indent=2)
                
            return True
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde du contexte: {e}")
            return False
            
    def load_context(self, name="default"):
        """Charge un contexte sauvegardé"""
        if not os.path.exists(CONTEXT_FILE):
            return False
            
        try:
            with open(CONTEXT_FILE, 'r', encoding='utf-8') as f:
                contexts = json.load(f)
                
            if name in contexts:
                context = contexts[name]
                self.conversation_history = context["history"]
                self.current_dir = context["current_dir"]
                self.system_message = context["system_message"]
                
                # Vérifier si le répertoire existe toujours
                if not os.path.isdir(self.current_dir):
                    self.current_dir = os.getcwd()
                    
                return True
            return False
        except Exception as e:
            logging.error(f"Erreur lors du chargement du contexte: {e}")
            return False
            
    def list_contexts(self):
        """Liste les contextes sauvegardés"""
        if not os.path.exists(CONTEXT_FILE):
            return []
            
        try:
            with open(CONTEXT_FILE, 'r', encoding='utf-8') as f:
                contexts = json.load(f)
                
            return [(name, context["timestamp"]) for name, context in contexts.items()]
        except Exception as e:
            logging.error(f"Erreur lors du listage des contextes: {e}")
            return []

    def get_prompt(self):
        """Affiche le prompt personnalisé avec le répertoire courant"""
        # Mettre à jour le prompt avec le répertoire actuel
        dir_name = os.path.basename(self.current_dir)
        if dir_name == "":  # Si on est à la racine
            dir_name = "/"
        
        # Styles de couleurs selon le thème
        if self.config["theme"] == "dark":
            prompt_color = "bright_cyan"
            dir_color = "bright_green"
        elif self.config["theme"] == "light":
            prompt_color = "blue"
            dir_color = "green"
        elif self.config["theme"] == "hacker":
            prompt_color = "bright_green"
            dir_color = "bright_green"
        else:  # default
            prompt_color = "cyan"
            dir_color = "green"
            
        prompt = f"🤖 Mistral@{dir_name} $ "
        
        if HAS_RICH:
            return self.console.input(f"[bold {prompt_color}]🤖 Mistral[/bold {prompt_color}][bold white]@[/bold white][bold {dir_color}]{dir_name}[/bold {dir_color}] $ ")
        else:
            return input(prompt)

    def is_dangerous_command(self, command):
        """Vérifie si une commande est potentiellement dangereuse"""
        command_parts = shlex.split(command) if command else []
        if not command_parts:
            return False
            
        base_cmd = command_parts[0]
        
        # Vérifier les commandes dangereuses directes
        if base_cmd in self.config["dangerous_commands"]:
            return True
            
        # Vérifier les redirections et pipes dangereux
        if ">" in command or "|" in command and ("rm" in command or "mv" in command):
            return True
            
        # Vérifier les options dangereuses spécifiques
        if base_cmd == "rm" and ("-rf" in command_parts or "-fr" in command_parts):
            return True
            
        return False

    def execute_command(self, command):
        """Exécute une commande shell et retourne le résultat"""
        logging.info(f"Exécution de la commande: {command}")
        
        # Vérifier si la commande est un alias
        if command.strip().split()[0] in self.aliases:
            alias_name = command.strip().split()[0]
            alias_value = self.aliases[alias_name]
            # Remplacer uniquement le premier mot (alias)
            command = command.replace(alias_name, alias_value, 1)
            if self.config["debug_mode"]:
                logging.info(f"Alias {alias_name} remplacé par: {alias_value}")
        
        # Gestion spéciale pour la commande cd
        if command.strip().startswith("cd "):
            try:
                # Extraire le chemin cible
                target_dir = command.strip()[3:].strip()
                
                # Gestion des chemins relatifs ou absolus
                if target_dir.startswith('/'):
                    new_dir = target_dir  # Chemin absolu
                elif target_dir.startswith('~'):
                    new_dir = os.path.expanduser(target_dir)
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
            
            result = stdout.decode('utf-8', errors='replace')
            error = stderr.decode('utf-8', errors='replace')
            
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
        filepath = os.path.join(self.config["scripts_dir"], filename)
        
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
            "Authorization": f"Bearer {self.config['api_key']}"
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
            "model": self.config["model"],
            "messages": messages,
            "temperature": self.config["temperature"],
            "max_tokens": self.config["max_tokens"]
        }
        
        try:
            # Afficher un indicateur de progression si rich est disponible
            if HAS_RICH and not self.config["use_streaming"]:
                with Progress() as progress:
                    task = progress.add_task("[cyan]Appel de l'API Mistral...", total=None)
                    response = requests.post(self.config["api_url"], headers=headers, json=payload)
                    progress.update(task, completed=100)
            else:
                if not self.config["use_streaming"]:
                    print("Appel de l'API Mistral...")
                response = requests.post(self.config["api_url"], headers=headers, json=payload)
            
            if response.status_code == 200:
                response_data = response.json()
                if self.config["debug_mode"]:
                    print(json.dumps(response_data, indent=2))
                    
                assistant_message = response_data['choices'][0]['message']['content']
                
                # Mettre à jour l'historique de conversation
                self.conversation_history.append({"role": "user", "content": user_message})
                self.conversation_history.append({"role": "assistant", "content": assistant_message})
                
                # Limiter la taille de l'historique
                max_entries = self.config["max_history"]
                if len(self.conversation_history) > max_entries * 2:
                    # Conserver les entrées les plus récentes
                    self.conversation_history = self.conversation_history[-(max_entries * 2):]
                    
                return assistant_message
            else:
                error_message = f"Erreur API ({response.status_code}): {response.text}"
                logging.error(error_message)
                return f"Erreur lors de l'appel à l'API Mistral: {error_message}"
        except Exception as e:
            logging.error(f"Exception lors de l'appel à l'API: {str(e)}")
            return f"Erreur de connexion à l'API Mistral: {str(e)}"
            
    def call_mistral_api_streaming(self, user_message):
        """Appelle l'API Mistral avec streaming pour une meilleure expérience"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config['api_key']}"
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
            "model": self.config["model"],
            "messages": messages,
            "temperature": self.config["temperature"],
            "max_tokens": self.config["max_tokens"],
            "stream": True
        }
        
        try:
            # Indiquer que le streaming commence
            if HAS_RICH:
                self.console.print("[cyan]Réception de la réponse...[/cyan]")
            else:
                print("Réception de la réponse...")
                
            response = requests.post(self.config["api_url"], headers=headers, json=payload, stream=True)
            
            if response.status_code == 200:
                full_response = ""
                
                for line in response.iter_lines():
                    if line:
                        # Décodage de la ligne
                        line = line.decode('utf-8')
                        
                        # Ignorer les lignes qui ne commencent pas par "data:"
                        if not line.startswith('data:'):
                            continue
                            
                        # Ignorer la ligne "data: [DONE]"
                        if line == 'data: [DONE]':
                            break
                            
                        # Extraire le JSON après "data:"
                        json_str = line[5:].strip()
                        
                        try:
                            chunk = json.loads(json_str)
                            # Extraire le fragment de texte
                            delta = chunk['choices'][0]['delta']
                            if 'content' in delta:
                                content = delta['content']
                                full_response += content
                                
                                # Afficher le fragment
                                if HAS_RICH:
                                    self.console.print(content, end="")
                                else:
                                    print(content, end="", flush=True)
                        except json.JSONDecodeError:
                            pass
                
                # Ajouter un saut de ligne à la fin
                print()
                
                # Mettre à jour l'historique de conversation
                self.conversation_history.append({"role": "user", "content": user_message})
                self.conversation_history.append({"role": "assistant", "content": full_response})
                
                # Limiter la taille de l'historique
                max_entries = self.config["max_history"]
                if len(self.conversation_history) > max_entries * 2:
                    # Conserver les entrées les plus récentes
                    self.conversation_history = self.conversation_history[-(max_entries * 2):]
                    
                return full_response
            else:
                error_message = f"Erreur API ({response.status_code}): {response.text}"
                logging.error(error_message)
                return f"Erreur lors de l'appel à l'API Mistral: {error_message}"
        except Exception as e:
            logging.error(f"Exception lors de l'appel à l'API streaming: {str(e)}")
            return f"Erreur de connexion à l'API Mistral: {str(e)}"
            
    def process_response(self, response):
        """Traite la réponse de l'API pour exécuter des commandes ou créer des scripts"""
        # Si la réponse a déjà été traitée (en streaming), ne rien faire
        if not response:
            return
            
        # Rechercher les commandes à exécuter
        exec_pattern = r"\[EXEC\](.*?)\[\/EXEC\]"
        script_pattern = r"\[SCRIPT\s+(\w+)\s+([^\]]+)\](.*?)\[\/SCRIPT\]"
        
        # Variable pour suivre si des commandes ont été exécutées
        commands_executed = False
        scripts_created = False
        
        # Exécution des commandes
        for match in re.finditer(exec_pattern, response, re.DOTALL):
            command = match.group(1).strip()
            result = self.execute_command(command)
            commands_executed = True
            
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
            scripts_created = True
            
            if HAS_RICH:
                self.console.print(f"\n[bold green]Script {script_type} créé:[/bold green] {filepath}")
                self.console.print(Syntax(script_content, script_type.lower()))
                
                # Demander si l'utilisateur veut exécuter le script
                if script_type.lower() in ["bash", "shell", "python"] and self.config["auto_execute_scripts"]:
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
                if script_type.lower() in ["bash", "shell", "python"] and self.config["auto_execute_scripts"]:
                    if input("Voulez-vous exécuter ce script maintenant? [o/N] ").lower() == 'o':
                        if script_type.lower() == "python":
                            cmd = f"python3 {filepath}"
                        else:
                            cmd = filepath
                            
                        result = self.execute_command(cmd)
                        print(f"\nRésultat de l'exécution:\n{result}")
        
        # Afficher le texte normal (sans les tags spéciaux) uniquement s'il n'y a pas eu de streaming
        if not self.config["use_streaming"]:
            clean_response = re.sub(exec_pattern, "", response)
            clean_response = re.sub(script_pattern, "", clean_response)
            clean_response = clean_response.strip()
            
            if clean_response:
                if HAS_RICH:
                    self.console.print(Panel(clean_response, border_style="cyan", box=box.ROUNDED))
                else:
                    print(f"\n{clean_response}\n")
        elif not commands_executed and not scripts_created:
            # Si streaming est activé et qu'il n'y a pas eu de commandes ou scripts
            # (donc juste du texte normal), ne rien faire car c'est déjà affiché
            pass
            
    def display_system_info(self):
        """Affiche les informations système"""
        if not self.config["show_system_info"]:
            return
            
        system_info = {
            "Système": platform.system(),
            "Version": platform.version(),
            "Architecture": platform.machine(),
            "Python": platform.python_version(),
            "Utilisateur": os.getenv("USER", "N/A"),
            "Répertoire home": os.path.expanduser("~"),
            "Répertoire actuel": self.current_dir,
            "Répertoire scripts": self.config["scripts_dir"]
        }
        
        if HAS_RICH:
            table = Table(title="Informations système")
            table.add_column("Paramètre", style="cyan")
            table.add_column("Valeur", style="green")
            
            for key, value in system_info.items():
                table.add_row(key, str(value))
                
            self.console.print(table)
        else:
            print("=== Informations système ===")
            for key, value in system_info.items():
                print(f"{key}: {value}")
            print("===========================")
            
    def process_agent_commands(self, command):
        """Traite les commandes internes de l'agent"""
        cmd_parts = command.strip().split(' ', 1)
        cmd = cmd_parts[0].lower()
        
        # Commande help - affiche l'aide
        if cmd == "help":
            self.display_help()
            return True
        
        # Commande set-prompt - définir un nouveau prompt système
        elif cmd == "set-prompt":
            if len(cmd_parts) > 1:
                new_prompt = cmd_parts[1]
                if self.save_system_message(new_prompt):
                    self.system_message = new_prompt
                    if HAS_RICH:
                        self.console.print("[green]Prompt système mis à jour avec succès.[/green]")
                    else:
                        print("Prompt système mis à jour avec succès.")
                else:
                    if HAS_RICH:
                        self.console.print("[red]Erreur lors de la mise à jour du prompt système.[/red]")
                    else:
                        print("Erreur lors de la mise à jour du prompt système.")
            else:
                if HAS_RICH:
                    self.console.print("[yellow]Usage: set-prompt <nouveau_prompt>[/yellow]")
                else:
                    print("Usage: set-prompt <nouveau_prompt>")
            return True
        
        # Commande set-api-key - définir une nouvelle clé API
        elif cmd == "set-api-key":
            if len(cmd_parts) > 1:
                new_key = cmd_parts[1].strip()
                self.config["api_key"] = new_key
                if self.save_config():
                    if HAS_RICH:
                        self.console.print("[green]Clé API mise à jour avec succès.[/green]")
                    else:
                        print("Clé API mise à jour avec succès.")
                else:
                    if HAS_RICH:
                        self.console.print("[red]Erreur lors de la mise à jour de la clé API.[/red]")
                    else:
                        print("Erreur lors de la mise à jour de la clé API.")
            else:
                if HAS_RICH:
                    self.console.print("[yellow]Usage: set-api-key <nouvelle_clé>[/yellow]")
                else:
                    print("Usage: set-api-key <nouvelle_clé>")
            return True
        
        # Commande save-context - sauvegarder le contexte actuel
        elif cmd == "save-context":
            name = "default"
            if len(cmd_parts) > 1:
                name = cmd_parts[1].strip()
            
            if self.save_context(name):
                if HAS_RICH:
                    self.console.print(f"[green]Contexte '{name}' sauvegardé avec succès.[/green]")
                else:
                    print(f"Contexte '{name}' sauvegardé avec succès.")
            else:
                if HAS_RICH:
                    self.console.print(f"[red]Erreur lors de la sauvegarde du contexte '{name}'.[/red]")
                else:
                    print(f"Erreur lors de la sauvegarde du contexte '{name}'.")
            return True
        
        # Commande load-context - charger un contexte sauvegardé
        elif cmd == "load-context":
            name = "default"
            if len(cmd_parts) > 1:
                name = cmd_parts[1].strip()
            
            if self.load_context(name):
                if HAS_RICH:
                    self.console.print(f"[green]Contexte '{name}' chargé avec succès.[/green]")
                else:
                    print(f"Contexte '{name}' chargé avec succès.")
            else:
                if HAS_RICH:
                    self.console.print(f"[red]Contexte '{name}' introuvable ou invalide.[/red]")
                else:
                    print(f"Contexte '{name}' introuvable ou invalide.")
            return True
        
        # Commande list-contexts - lister les contextes sauvegardés
        elif cmd == "list-contexts":
            contexts = self.list_contexts()
            
            if contexts:
                if HAS_RICH:
                    table = Table(title="Contextes sauvegardés")
                    table.add_column("Nom", style="cyan")
                    table.add_column("Date", style="green")
                    
                    for name, timestamp in contexts:
                        table.add_row(name, timestamp)
                        
                    self.console.print(table)
                else:
                    print("=== Contextes sauvegardés ===")
                    for name, timestamp in contexts:
                        print(f"{name}: {timestamp}")
                    print("============================")
            else:
                if HAS_RICH:
                    self.console.print("[yellow]Aucun contexte sauvegardé trouvé.[/yellow]")
                else:
                    print("Aucun contexte sauvegardé trouvé.")
            return True
            
        # Commande config - afficher ou modifier la configuration
        elif cmd == "config":
            if len(cmd_parts) > 1:
                # Commande de modification de la configuration
                config_cmd = cmd_parts[1].strip()
                
                # Format: config set cle valeur
                if config_cmd.startswith("set "):
                    set_parts = config_cmd[4:].strip().split(' ', 1)
                    if len(set_parts) == 2:
                        key, value = set_parts
                        
                        # Convertir la valeur selon le type attendu
                        if key in self.config:
                            if isinstance(self.config[key], bool):
                                value = value.lower() in ["true", "1", "oui", "yes", "o", "y"]
                            elif isinstance(self.config[key], int):
                                try:
                                    value = int(value)
                                except ValueError:
                                    if HAS_RICH:
                                        self.console.print(f"[red]Erreur: {value} n'est pas un entier valide.[/red]")
                                    else:
                                        print(f"Erreur: {value} n'est pas un entier valide.")
                                    return True
                            elif isinstance(self.config[key], float):
                                try:
                                    value = float(value)
                                except ValueError:
                                    if HAS_RICH:
                                        self.console.print(f"[red]Erreur: {value} n'est pas un nombre valide.[/red]")
                                    else:
                                        print(f"Erreur: {value} n'est pas un nombre valide.")
                                    return True
                                    
                        # Mettre à jour la configuration
                        self.config[key] = value
                        if self.save_config():
                            if HAS_RICH:
                                self.console.print(f"[green]Configuration mise à jour: {key} = {value}[/green]")
                            else:
                                print(f"Configuration mise à jour: {key} = {value}")
                        else:
                            if HAS_RICH:
                                self.console.print("[red]Erreur lors de la sauvegarde de la configuration.[/red]")
                            else:
                                print("Erreur lors de la sauvegarde de la configuration.")
                    else:
                        if HAS_RICH:
                            self.console.print("[yellow]Usage: config set <clé> <valeur>[/yellow]")
                        else:
                            print("Usage: config set <clé> <valeur>")
                
                # Format: config get cle
                elif config_cmd.startswith("get "):
                    key = config_cmd[4:].strip()
                    if key in self.config:
                        if HAS_RICH:
                            self.console.print(f"[cyan]{key}[/cyan] = [green]{self.config[key]}[/green]")
                        else:
                            print(f"{key} = {self.config[key]}")
                    else:
                        if HAS_RICH:
                            self.console.print(f"[yellow]Clé '{key}' non trouvée dans la configuration.[/yellow]")
                        else:
                            print(f"Clé '{key}' non trouvée dans la configuration.")
                
                # Format: config reset
                elif config_cmd == "reset":
                    if HAS_RICH:
                        if Confirm.ask("[yellow]Êtes-vous sûr de vouloir réinitialiser la configuration?[/yellow]"):
                            self.config = DEFAULT_CONFIG.copy()
                            if self.save_config():
                                self.console.print("[green]Configuration réinitialisée avec succès.[/green]")
                            else:
                                self.console.print("[red]Erreur lors de la réinitialisation de la configuration.[/red]")
                    else:
                        if input("Êtes-vous sûr de vouloir réinitialiser la configuration? [o/N] ").lower() == 'o':
                            self.config = DEFAULT_CONFIG.copy()
                            if self.save_config():
                                print("Configuration réinitialisée avec succès.")
                            else:
                                print("Erreur lors de la réinitialisation de la configuration.")
                else:
                    if HAS_RICH:
                        self.console.print("[yellow]Commande config invalide. Options: set, get, reset[/yellow]")
                    else:
                        print("Commande config invalide. Options: set, get, reset")
            else:
                # Afficher toute la configuration
                if HAS_RICH:
                    table = Table(title="Configuration")
                    table.add_column("Paramètre", style="cyan")
                    table.add_column("Valeur", style="green")
                    
                    for key, value in self.config.items():
                        table.add_row(key, str(value))
                        
                    self.console.print(table)
                else:
                    print("=== Configuration ===")
                    for key, value in self.config.items():
                        print(f"{key}: {value}")
                    print("====================")
            return True
            
        # Commande theme - changer le thème
        elif cmd == "theme":
            available_themes = ["default", "dark", "light", "hacker"]
            
            if len(cmd_parts) > 1:
                theme = cmd_parts[1].strip().lower()
                if theme in available_themes:
                    self.config["theme"] = theme
                    if self.save_config():
                        if HAS_RICH:
                            self.console.print(f"[green]Thème changé pour: {theme}[/green]")
                        else:
                            print(f"Thème changé pour: {theme}")
                    else:
                        if HAS_RICH:
                            self.console.print("[red]Erreur lors de la sauvegarde du thème.[/red]")
                        else:
                            print("Erreur lors de la sauvegarde du thème.")
                else:
                    if HAS_RICH:
                        self.console.print(f"[yellow]Thème inconnu: {theme}. Thèmes disponibles: {', '.join(available_themes)}[/yellow]")
                    else:
                        print(f"Thème inconnu: {theme}. Thèmes disponibles: {', '.join(available_themes)}")
            else:
                if HAS_RICH:
                    self.console.print(f"[cyan]Thème actuel: {self.config['theme']}[/cyan]")
                    self.console.print(f"[cyan]Thèmes disponibles: {', '.join(available_themes)}[/cyan]")
                else:
                    print(f"Thème actuel: {self.config['theme']}")
                    print(f"Thèmes disponibles: {', '.join(available_themes)}")
            return True
            
        # Commande alias - gérer les alias
        elif cmd == "alias":
            if len(cmd_parts) > 1:
                alias_cmd = cmd_parts[1].strip()
                
                # Format: alias set nom valeur
                if alias_cmd.startswith("set "):
                    alias_parts = alias_cmd[4:].strip().split(' ', 1)
                    if len(alias_parts) == 2:
                        alias_name, alias_value = alias_parts
                        self.aliases[alias_name] = alias_value
                        if self.save_aliases():
                            if HAS_RICH:
                                self.console.print(f"[green]Alias ajouté: {alias_name} = {alias_value}[/green]")
                            else:
                                print(f"Alias ajouté: {alias_name} = {alias_value}")
                        else:
                            if HAS_RICH:
                                self.console.print("[red]Erreur lors de la sauvegarde des alias.[/red]")
                            else:
                                print("Erreur lors de la sauvegarde des alias.")
                    else:
                        if HAS_RICH:
                            self.console.print("[yellow]Usage: alias set <nom> <valeur>[/yellow]")
                        else:
                            print("Usage: alias set <nom> <valeur>")
                
                # Format: alias remove nom
                elif alias_cmd.startswith("remove "):
                    alias_name = alias_cmd[7:].strip()
                    if alias_name in self.aliases:
                        del self.aliases[alias_name]
                        if self.save_aliases():
                            if HAS_RICH:
                                self.console.print(f"[green]Alias supprimé: {alias_name}[/green]")
                            else:
                                print(f"Alias supprimé: {alias_name}")
                        else:
                            if HAS_RICH:
                                self.console.print("[red]Erreur lors de la sauvegarde des alias.[/red]")
                            else:
                                print("Erreur lors de la sauvegarde des alias.")
                    else:
                        if HAS_RICH:
                            self.console.print(f"[yellow]Alias '{alias_name}' introuvable.[/yellow]")
                        else:
                            print(f"Alias '{alias_name}' introuvable.")
                
                # Format: alias reset
                elif alias_cmd == "reset":
                    if HAS_RICH:
                        if Confirm.ask("[yellow]Êtes-vous sûr de vouloir réinitialiser tous les alias?[/yellow]"):
                            self.aliases = COMMON_ALIASES.copy()
                            if self.save_aliases():
                                self.console.print("[green]Alias réinitialisés avec succès.[/green]")
                            else:
                                self.console.print("[red]Erreur lors de la réinitialisation des alias.[/red]")
                    else:
                        if input("Êtes-vous sûr de vouloir réinitialiser tous les alias? [o/N] ").lower() == 'o':
                            self.aliases = COMMON_ALIASES.copy()
                            if self.save_aliases():
                                print("Alias réinitialisés avec succès.")
                            else:
                                print("Erreur lors de la réinitialisation des alias.")
                else:
                    if HAS_RICH:
                        self.console.print("[yellow]Commande alias invalide. Options: set, remove, reset[/yellow]")
                    else:
                        print("Commande alias invalide. Options: set, remove, reset")
            else:
                # Afficher tous les alias
                if HAS_RICH:
                    table = Table(title="Alias")
                    table.add_column("Nom", style="cyan")
                    table.add_column("Commande", style="green")
                    
                    for name, value in self.aliases.items():
                        table.add_row(name, value)
                        
                    self.console.print(table)
                else:
                    print("=== Alias ===")
                    for name, value in self.aliases.items():
                        print(f"{name}: {value}")
                    print("============")
            return True
            
        # Commande history - afficher ou gérer l'historique des conversations
        elif cmd == "history":
            if len(cmd_parts) > 1:
                history_cmd = cmd_parts[1].strip()
                
                # Format: history clear
                if history_cmd == "clear":
                    if HAS_RICH:
                        if Confirm.ask("[yellow]Êtes-vous sûr de vouloir effacer tout l'historique des conversations?[/yellow]"):
                            self.conversation_history = []
                            if self.save_history():
                                self.console.print("[green]Historique effacé avec succès.[/green]")
                            else:
                                self.console.print("[red]Erreur lors de l'effacement de l'historique.[/red]")
                    else:
                        if input("Êtes-vous sûr de vouloir effacer tout l'historique des conversations? [o/N] ").lower() == 'o':
                            self.conversation_history = []
                            if self.save_history():
                                print("Historique effacé avec succès.")
                            else:
                                print("Erreur lors de l'effacement de l'historique.")
                else:
                    if HAS_RICH:
                        self.console.print("[yellow]Commande history invalide. Options: clear[/yellow]")
                    else:
                        print("Commande history invalide. Options: clear")
            else:
                # Afficher un résumé de l'historique
                history_count = len(self.conversation_history) // 2  # Diviser par 2 car chaque échange a 2 messages
                if HAS_RICH:
                    self.console.print(f"[cyan]Historique: {history_count} échanges[/cyan]")
                    self.console.print(f"[cyan]Taille maximale: {self.config['max_history']} échanges[/cyan]")
                else:
                    print(f"Historique: {history_count} échanges")
                    print(f"Taille maximale: {self.config['max_history']} échanges")
            return True
            
        # Commande system-info - afficher les informations système
        elif cmd == "system-info":
            self.display_system_info()
            return True
            
        # Pas une commande interne
        return False
        
    def display_help(self):
        """Affiche l'aide de l'agent"""
        commands = [
            ("help", "Affiche cette aide"),
            ("exit, quit", "Quitter l'agent"),
            ("clear", "Effacer l'écran"),
            ("pwd", "Afficher le répertoire courant"),
            ("cd <chemin>", "Changer de répertoire"),
            ("set-prompt <texte>", "Définir un nouveau prompt système"),
            ("set-api-key <clé>", "Définir une nouvelle clé API"),
            ("save-context [nom]", "Sauvegarder le contexte actuel"),
            ("load-context [nom]", "Charger un contexte sauvegardé"),
            ("list-contexts", "Lister les contextes sauvegardés"),
            ("config", "Afficher la configuration"),
            ("config set <clé> <valeur>", "Modifier un paramètre de configuration"),
            ("config get <clé>", "Afficher un paramètre de configuration"),
            ("config reset", "Réinitialiser la configuration"),
            ("theme [nom]", "Afficher ou changer le thème"),
            ("alias", "Afficher tous les alias"),
            ("alias set <nom> <valeur>", "Définir un alias"),
            ("alias remove <nom>", "Supprimer un alias"),
            ("alias reset", "Réinitialiser les alias"),
            ("history", "Afficher un résumé de l'historique"),
            ("history clear", "Effacer l'historique des conversations"),
            ("system-info", "Afficher les informations système")
        ]
        
        if HAS_RICH:
            table = Table(title="Commandes de l'agent Mistral")
            table.add_column("Commande", style="cyan")
            table.add_column("Description", style="green")
            
            for cmd, desc in commands:
                table.add_row(cmd, desc)
                
            self.console.print(table)
        else:
            print("=== Commandes de l'agent Mistral ===")
            for cmd, desc in commands:
                print(f"{cmd.ljust(30)} : {desc}")
            print("==================================")

    def run(self):
        """Démarre la boucle principale de l'agent"""
        if HAS_RICH:
            self.console.print(Panel.fit(
                "[bold cyan]Agent IA Mistral[/bold cyan] - Assistant DevOps et SysAdmin",
                border_style="cyan",
                box=box.DOUBLE_EDGE
            ))
            self.console.print(f"[bold]Langue:[/bold] {self.config['language']} | [bold]Répertoire des scripts:[/bold] {self.config['scripts_dir']}")
            self.console.print(f"[bold]Répertoire courant:[/bold] {self.current_dir}")
            self.console.print("[bold]Tapez 'help' pour voir les commandes disponibles[/bold]\n")
        else:
            print("====== Agent IA Mistral - Assistant DevOps et SysAdmin ======")
            print(f"Langue: {self.config['language']} | Répertoire des scripts: {self.config['scripts_dir']}")
            print(f"Répertoire courant: {self.current_dir}")
            print("Tapez 'help' pour voir les commandes disponibles\n")
            
        # Afficher les infos système au démarrage
        self.display_system_info()

        # Boucle principale
        while True:
            try:
                user_input = self.get_prompt()
                
                # Ignorer les entrées vides
                if not user_input.strip():
                    continue
                    
                # Vérifier si c'est une commande interne de l'agent
                if self.process_agent_commands(user_input):
                    continue
                    
                # Commandes spéciales
                if user_input.lower() in ['exit', 'quit']:
                    self.save_history()
                    self.save_config()
                    break
                elif user_input.lower() == 'clear':
                    os.system('clear' if os.name == 'posix' else 'cls')
                    continue
                elif user_input.lower() == 'pwd':
                    if HAS_RICH:
                        self.console.print(f"[bold green]Répertoire courant:[/bold green] {self.current_dir}")
                    else:
                        print(f"Répertoire courant: {self.current_dir}")
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
                
                # Appel à l'API Mistral - avec ou sans streaming
                if self.config["use_streaming"]:
                    assistant_response = self.call_mistral_api_streaming(user_input)
                else:
                    assistant_response = self.call_mistral_api(user_input)
                
                # Traitement de la réponse
                self.process_response(assistant_response)
                
                # Sauvegarde périodique de l'historique
                self.save_history()
                
            except KeyboardInterrupt:
                print("\nInterruption détectée. Pour quitter, tapez 'exit'.")
            except Exception as e:
                logging.error(f"Erreur dans la boucle principale: {str(e)}")
                if self.config["debug_mode"]:
                    import traceback
                    traceback.print_exc()
                if HAS_RICH:
                    self.console.print(f"[bold red]Erreur:[/bold red] {str(e)}")
                else:
                    print(f"Erreur: {str(e)}")

def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(description="Mistral Agent - Assistant IA pour terminal Linux")
    parser.add_argument("--lang", choices=["fr", "en"], default="fr", help="Langue de l'interface (fr/en)")
    parser.add_argument("--debug", action="store_true", help="Activer le mode debug")
    parser.add_argument("--long-prompt", action="store_true", help="Utiliser un prompt long personnalisé")
    parser.add_argument("--set-prompt", type=str, help="Définir un nouveau prompt long")
    parser.add_argument("--start-dir", type=str, help="Répertoire de démarrage")
    parser.add_argument("--theme", choices=["default", "dark", "light", "hacker"], default="default", help="Thème de l'interface")
    parser.add_argument("--scripts-dir", type=str, help="Répertoire pour les scripts générés")
    parser.add_argument("--shell-completion", action="store_true", help="Installer la complétion shell")
    parser.add_argument("--no-streaming", action="store_true", help="Désactiver le mode streaming pour les réponses")
    
    args = parser.parse_args()
    
    # Installer la complétion shell si demandé
    if args.shell_completion:
        install_shell_completion()
        return
    
    # Définir un nouveau prompt si demandé
    if args.set_prompt:
        agent = MistralAgent(language=args.lang, debug=args.debug, long_prompt=True)
        if agent.save_system_message(args.set_prompt):
            print("Prompt personnalisé sauvegardé avec succès.")
        else:
            print("Erreur lors de la sauvegarde du prompt.")
        return
    
    # Mettre à jour le répertoire des scripts si spécifié
    if args.scripts_dir:
        scripts_dir = os.path.expanduser(args.scripts_dir)
        os.makedirs(scripts_dir, exist_ok=True)
        agent = MistralAgent(language=args.lang, debug=args.debug)
        agent.config["scripts_dir"] = scripts_dir
        agent.save_config()
        print(f"Répertoire des scripts défini sur: {scripts_dir}")
        return
        
    # Créer et exécuter l'agent
    agent = MistralAgent(
        language=args.lang,
        debug=args.debug,
        long_prompt=args.long_prompt,
        start_dir=args.start_dir,
        theme=args.theme
    )
    
    # Mettre à jour le mode streaming
    if args.no_streaming:
        agent.config["use_streaming"] = False
        agent.save_config()
    
    agent.run()

def install_shell_completion():
    """Installe la complétion shell pour l'agent Mistral"""
    # Déterminer le shell de l'utilisateur
    shell = os.environ.get("SHELL", "")
    home = os.path.expanduser("~")
    
    # Contenu de la complétion Bash
    bash_completion = """
# Complétion Bash pour l'agent Mistral
_mistral_completions()
{
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    
    # Commandes de base
    opts="help exit quit clear pwd cd set-prompt set-api-key save-context load-context list-contexts config theme alias history system-info"
    
    # Complétion contextuelle
    case "${prev}" in
        cd)
            # Complétion des répertoires
            COMPREPLY=( $(compgen -d -- "${cur}") )
            return 0
            ;;
        theme)
            # Complétion des thèmes
            COMPREPLY=( $(compgen -W "default dark light hacker" -- "${cur}") )
            return 0
            ;;
        config)
            # Complétion des sous-commandes de config
            COMPREPLY=( $(compgen -W "set get reset" -- "${cur}") )
            return 0
            ;;
        alias)
            # Complétion des sous-commandes d'alias
            COMPREPLY=( $(compgen -W "set remove reset" -- "${cur}") )
            return 0
            ;;
        history)
            # Complétion des sous-commandes d'history
            COMPREPLY=( $(compgen -W "clear" -- "${cur}") )
            return 0
            ;;
        *)
            ;;
    esac
    
    # Complétion générale
    COMPREPLY=( $(compgen -W "${opts}" -- "${cur}") )
    return 0
}

complete -F _mistral_completions mistral
"""
    
    # Contenu de la complétion Zsh
    zsh_completion = """
#compdef mistral

_mistral() {
    local -a commands
    commands=(
        'help:Affiche l\\'aide'
        'exit:Quitter l\\'agent'
        'quit:Quitter l\\'agent'
        'clear:Effacer l\\'écran'
        'pwd:Afficher le répertoire courant'
        'cd:Changer de répertoire'
        'set-prompt:Définir un nouveau prompt système'
        'set-api-key:Définir une nouvelle clé API'
        'save-context:Sauvegarder le contexte actuel'
        'load-context:Charger un contexte sauvegardé'
        'list-contexts:Lister les contextes sauvegardés'
        'config:Gérer la configuration'
        'theme:Gérer le thème'
        'alias:Gérer les alias'
        'history:Gérer l\\'historique'
        'system-info:Afficher les informations système'
    )
    
    _arguments -C \\
        "1: :{_describe 'command' commands}" \\
        "*::arg:->args"
    
    case $line[1] in
        cd)
            _files -/
            ;;
        theme)
            _values 'theme' default dark light hacker
            ;;
        config)
            _values 'config_cmd' set get reset
            ;;
        alias)
            _values 'alias_cmd' set remove reset
            ;;
        history)
            _values 'history_cmd' clear
            ;;
    esac
}

_mistral
"""
    
    # Déterminer le fichier de configuration du shell
    if "bash" in shell:
        # Bash
        shell_config = os.path.join(home, ".bashrc")
        completion_dir = os.path.join(home, ".bash_completion.d")
        os.makedirs(completion_dir, exist_ok=True)
        completion_file = os.path.join(completion_dir, "mistral")
        
        with open(completion_file, "w") as f:
            f.write(bash_completion)
            
        # Ajouter au .bashrc si nécessaire
        with open(shell_config, "r") as f:
            content = f.read()
            
        if "bash_completion.d/mistral" not in content:
            with open(shell_config, "a") as f:
                f.write("\n# Complétion Mistral\n")
                f.write(f"if [ -f {completion_file} ]; then\n")
                f.write(f"    . {completion_file}\n")
                f.write("fi\n")
    
    elif "zsh" in shell:
        # Zsh
        completion_dir = os.path.join(home, ".zsh", "completions")
        os.makedirs(completion_dir, exist_ok=True)
        completion_file = os.path.join(completion_dir, "_mistral")
        
        with open(completion_file, "w") as f:
            f.write(zsh_completion)
            
        # Vérifier si fpath contient déjà le répertoire
        zshrc = os.path.join(home, ".zshrc")
        with open(zshrc, "r") as f:
            content = f.read()
            
        if completion_dir not in content and "completions" not in content:
            with open(zshrc, "a") as f:
                f.write("\n# Complétion Mistral\n")
                f.write(f"fpath=({completion_dir} $fpath)\n")
                f.write("autoload -Uz compinit\n")
                f.write("compinit\n")
    
    else:
        print(f"Shell non supporté pour la complétion: {shell}")
        return
    
    print(f"Complétion shell installée pour {os.path.basename(shell)}")
    print("Veuillez redémarrer votre shell ou exécuter 'source ~/.bashrc' (ou équivalent) pour activer la complétion.")

if __name__ == "__main__":
    main()