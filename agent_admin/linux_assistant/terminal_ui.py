"""
Interface utilisateur pour le terminal.
Gère l'affichage, les couleurs et les interactions avec l'utilisateur.
"""

from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.panel import Panel
from rich.text import Text
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import InMemoryHistory
from typing import List, Optional, Dict, Any
import re
import os

from .config import config

class TerminalUI:
    def __init__(self):
        self.console = Console()
        self.history = InMemoryHistory()
        self.command_completer = WordCompleter([
            '/ticket', '/alerte', '/wiki', '/historique', '/aide', '/quitter'
        ])
        self.session = PromptSession(
            history=self.history,
            completer=self.command_completer
        )
        
        # Couleurs depuis la configuration
        self.colors = config.get("ui", "colors")
        self.prompt_text = config.get("ui", "prompt", default="🐧> ")
        
        # Initialisation de l'interface
        self._setup_terminal()
        
    def _setup_terminal(self):
        """Configure le terminal pour une meilleure expérience."""
        try:
            # Effacer l'écran
            os.system('cls' if os.name == 'nt' else 'clear')
            
            # Afficher le message de bienvenue
            self.console.print(Panel.fit(
                "Assistant IA pour Administrateurs Linux\n"
                "Modèle: qwen2.5-coder:7b via Ollama\n"
                "Tapez /aide pour afficher les commandes disponibles",
                title="[bold green]Linux Admin Assistant[/]",
                border_style="green"
            ))
        except Exception as e:
            print(f"Erreur lors de l'initialisation du terminal: {e}")
        
    def print_info(self, message: str):
        """Affiche un message informatif."""
        self.console.print(f"[{self.colors.get('info', 'blue')}]ℹ️ {message}[/]")
        
    def print_warning(self, message: str):
        """Affiche un avertissement."""
        self.console.print(f"[{self.colors.get('warning', 'yellow')}]⚠️ {message}[/]")
        
    def print_error(self, message: str):
        """Affiche une erreur."""
        self.console.print(f"[{self.colors.get('error', 'red')}]❌ {message}[/]")
        
    def print_command(self, command: str):
        """Affiche une commande formatée."""
        self.console.print(Syntax(command, "bash", theme="monokai", line_numbers=False))
        
    def print_explanation(self, explanation: str):
        """Affiche une explication."""
        self.console.print(f"[{self.colors.get('explanation', 'cyan')}]{explanation}[/]")
        
    def format_assistant_response(self, response: str) -> str:
        """
        Formate la réponse de l'assistant avec mise en forme.
        Détecte et formate les commandes, les avertissements, etc.
        """
        # Détection des commandes entre backticks
        pattern_cmd = r'`(.*?)`'
        formatted = re.sub(pattern_cmd, r'[{0}]\1[/]'.format(self.colors.get('command', 'green')), response)
        
        # Détection des avertissements
        pattern_warning = r'⚠️(.*?)(\n|$)'
        formatted = re.sub(pattern_warning, r'[{0}]⚠️\1[/]\2'.format(self.colors.get('warning', 'yellow')), formatted)
        
        return formatted
    
    def display_assistant_response(self, response: str):
        """Affiche la réponse formatée de l'assistant."""
        formatted = self.format_assistant_response(response)
        self.console.print(formatted)
        
    def get_user_input(self) -> str:
        """Récupère l'entrée de l'utilisateur."""
        try:
            return self.session.prompt(self.prompt_text)
        except KeyboardInterrupt:
            return "/quitter"
        except EOFError:
            return "/quitter"
            
    def display_help(self):
        """Affiche l'aide des commandes disponibles."""
        help_text = """
# Commandes disponibles

- `/ticket <description>` - Analyser un nouveau ticket de support
- `/alerte <description>` - Analyser une alerte Nagios
- `/wiki` - Générer un wiki pour l'intervention en cours
- `/historique` - Afficher l'historique de la session
- `/aide` - Afficher cette aide
- `/quitter` - Quitter l'application

# Astuces

- Décrivez clairement vos problèmes pour obtenir de meilleures réponses
- Pour les commandes complexes, demandez toujours une explication
- Utilisez CTRL+C pour interrompre une génération de réponse
        """
        self.console.print(Markdown(help_text))
        
    def display_history(self, history: List[Dict[str, str]]):
        """Affiche l'historique des échanges."""
        if not history:
            self.print_info("Aucun historique disponible.")
            return
            
        self.console.print(Panel.fit(
            "\n".join([f"[bold]{entry['role']}:[/] {entry['content'][:50]}..." 
                      for entry in history[-10:]]),  # Afficher les 10 derniers échanges
            title="Historique récent",
            border_style="blue"
        ))