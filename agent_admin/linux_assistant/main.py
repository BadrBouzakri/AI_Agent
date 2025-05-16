#!/usr/bin/env python3
"""
Point d'entrée principal de l'assistant Linux.
Gère l'initialisation, la boucle principale et la coordination des composants.
"""

import argparse
import logging
import sys
import os
from pathlib import Path

from .config import config
from .terminal_ui import TerminalUI
from .ollama_client import OllamaClient
from .command_handler import CommandHandler
from .context_manager import ContextManager
from .utils.logger import setup_logger

def parse_args():
    """Parse les arguments de ligne de commande."""
    parser = argparse.ArgumentParser(description="Assistant IA pour administrateurs Linux")
    parser.add_argument('--debug', action='store_true', help='Active le mode debug')
    parser.add_argument('--model', type=str, help='Modèle Ollama à utiliser')
    parser.add_argument('--config', type=str, help='Chemin vers un fichier de configuration personnalisé')
    return parser.parse_args()

def setup_environment(args):
    """Configure l'environnement d'exécution."""
    # Configurer le logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    log_file = os.path.expanduser(config.get("logging", "file", default="~/.local/share/linux-assistant/logs/assistant.log"))
    log_dir = os.path.dirname(log_file)
    os.makedirs(log_dir, exist_ok=True)
    
    setup_logger(log_level, log_file)
    logger = logging.getLogger(__name__)
    
    # Appliquer les options de ligne de commande
    if args.model:
        config.config["ollama"]["model"] = args.model
        logger.info(f"Utilisation du modèle spécifié: {args.model}")
    
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            config._load_config_from_file(config_path)
            logger.info(f"Configuration chargée depuis: {args.config}")
        else:
            logger.error(f"Fichier de configuration introuvable: {args.config}")
            sys.exit(1)
    
    return logger

def main():
    """Fonction principale de l'application."""
    args = parse_args()
    logger = setup_environment(args)
    
    try:
        # Initialisation des composants
        ui = TerminalUI()
        ollama_client = OllamaClient()
        context_manager = ContextManager()
        command_handler = CommandHandler(ui, ollama_client, context_manager)
        
        # Vérification de la disponibilité d'Ollama
        ui.print_info(f"Initialisation de l'agent avec le modèle {config.get('ollama', 'model')}...")
        
        try:
            # Test simple de communication avec Ollama
            test_response = ollama_client.generate("Test de connexion", max_tokens=10)
            ui.print_info("Connexion avec Ollama établie avec succès.")
        except Exception as e:
            ui.print_error(f"Erreur de connexion à Ollama: {e}")
            ui.print_explanation(
                "Veuillez vérifier qu'Ollama est installé et en cours d'exécution, "
                "et que le modèle qwen2.5-coder:7b est disponible."
            )
            return 1
        
        # Boucle principale
        ui.print_info("Assistant prêt. Tapez votre question ou '/aide' pour afficher les commandes.")
        
        while True:
            user_input = ui.get_user_input()
            
            if user_input.lower() == "/quitter":
                ui.print_info("Au revoir !")
                break
                
            # Traitement de la commande ou de la requête
            command_handler.process_input(user_input)
    
    except KeyboardInterrupt:
        ui.print_info("\nInterruption détectée. Au revoir !")
        return 0
    except Exception as e:
        logger.exception("Erreur non gérée dans la boucle principale")
        print(f"Erreur: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())