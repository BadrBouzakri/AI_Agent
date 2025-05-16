"""
Gestionnaire de commandes pour l'assistant.
Traite les entrées utilisateur et coordonne les réponses.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple

from .ollama_client import OllamaClient
from .terminal_ui import TerminalUI
from .context_manager import ContextManager
from .utils.safety import check_command_safety

logger = logging.getLogger(__name__)

class CommandHandler:
    def __init__(self, ui: TerminalUI, ollama: OllamaClient, context: ContextManager):
        self.ui = ui
        self.ollama = ollama
        self.context = context
        
        # Initialisation des modules spécialisés
        try:
            from .modules.ticket_analyzer import TicketAnalyzer
            from .modules.alert_handler import AlertHandler
            from .modules.wiki_generator import WikiGenerator
            
            self.ticket_analyzer = TicketAnalyzer(ollama, context)
            self.alert_handler = AlertHandler(ollama, context)
            self.wiki_generator = WikiGenerator(ollama, context)
        except ImportError as e:
            logger.warning(f"Module non disponible: {e}")
            self.ticket_analyzer = None
            self.alert_handler = None
            self.wiki_generator = None
        
    def process_input(self, user_input: str):
        """
        Traite l'entrée utilisateur.
        
        Args:
            user_input: Texte saisi par l'utilisateur
        """
        # Enregistrer l'entrée dans le contexte
        self.context.add_message("user", user_input)
        
        # Vérifier s'il s'agit d'une commande
        if user_input.startswith('/'):
            self._handle_command(user_input)
        else:
            # Conversation normale, prendre en compte le contexte
            self._handle_conversation(user_input)
            
    def _handle_command(self, command: str):
        """
        Traite une commande spéciale commençant par /.
        
        Args:
            command: La commande saisie par l'utilisateur
        """
        parts = command.split(' ', 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        logger.debug(f"Traitement de la commande: {cmd} avec arguments: {args}")
        
        if cmd == '/aide':
            self.ui.display_help()
            
        elif cmd == '/ticket':
            if not args:
                self.ui.print_warning("Veuillez spécifier la description du ticket.")
                return
                
            if self.ticket_analyzer:
                self.ui.print_info(f"Analyse du ticket: {args}")
                response = self.ticket_analyzer.analyze(args)
                self.ui.display_assistant_response(response)
                self.context.add_message("assistant", response)
                self.context.set_context_data("ticket", args)
            else:
                # Fallback si le module n'est pas disponible
                self._handle_conversation(f"Analyse du ticket: {args}")
                self.context.set_context_data("ticket", args)
            
        elif cmd == '/alerte':
            if not args:
                self.ui.print_warning("Veuillez spécifier la description de l'alerte.")
                return
                
            if self.alert_handler:
                self.ui.print_info(f"Analyse de l'alerte: {args}")
                response = self.alert_handler.analyze(args)
                self.ui.display_assistant_response(response)
                self.context.add_message("assistant", response)
                self.context.set_context_data("alert", args)
            else:
                # Fallback si le module n'est pas disponible
                self._handle_conversation(f"Analyse de l'alerte: {args}")
                self.context.set_context_data("alert", args)
            
        elif cmd == '/wiki':
            self.ui.print_info("Génération du wiki basé sur la conversation actuelle...")
            
            if self.wiki_generator:
                wiki_content = self.wiki_generator.generate()
                
                if wiki_content:
                    self.ui.console.print("\n=== WIKI GÉNÉRÉ ===\n")
                    self.ui.console.print(wiki_content)
                    self.context.add_message("assistant", "Wiki généré avec succès.")
                else:
                    self.ui.print_error("Impossible de générer un wiki. Conversation insuffisante.")
            else:
                # Fallback si le module n'est pas disponible
                self._handle_conversation("Génère un wiki technique basé sur notre conversation.")
                
        elif cmd == '/historique':
            history = self.context.get_history()
            self.ui.display_history(history)
            
        else:
            self.ui.print_error(f"Commande inconnue: {cmd}")
            self.ui.print_info("Tapez /aide pour afficher les commandes disponibles.")
            
    def _handle_conversation(self, user_input: str):
        """
        Traite une entrée de conversation normale.
        
        Args:
            user_input: Texte saisi par l'utilisateur
        """
        # Obtenir le contexte actuel pour le prompt système
        context_data = self.context.get_context_data()
        system_prompt = self.ollama.get_system_prompt(context_data)
        
        # Générer la réponse
        self.ui.print_info("Génération de la réponse...")
        response = self.ollama.generate(
            prompt=user_input,
            system_prompt=system_prompt
        )
        
        # Vérifier la présence de commandes potentiellement dangereuses
        has_commands, commands = self._extract_commands(response)
        if has_commands:
            safe_commands, unsafe_commands = check_command_safety(commands)
            
            # Si des commandes dangereuses sont détectées, ajouter des avertissements
            if unsafe_commands:
                warning = "\n⚠️ Attention: Certaines commandes proposées peuvent être destructrices:\n"
                for cmd in unsafe_commands:
                    warning += f"- `{cmd}`\n"
                warning += "Vérifiez attentivement avant exécution!\n"
                response += warning
        
        # Afficher la réponse
        self.ui.display_assistant_response(response)
        
        # Enregistrer dans le contexte
        self.context.add_message("assistant", response)
        
    def _extract_commands(self, text: str) -> Tuple[bool, List[str]]:
        """
        Extrait les commandes Linux d'un texte.
        
        Args:
            text: Texte contenant potentiellement des commandes
            
        Returns:
            Tuple (has_commands, list_of_commands)
        """
        # Recherche de commandes entre backticks
        pattern = r'`(.*?)`'
        commands = re.findall(pattern, text)
        
        # Filtrer pour ne garder que les commandes shell probables
        commands = [cmd for cmd in commands if ' ' in cmd or '/' in cmd]
        
        return bool(commands), commands