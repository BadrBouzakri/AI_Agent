"""
Configuration du logging pour l'application.
"""

import logging
import os
from pathlib import Path

def setup_logger(level=logging.INFO, log_file=None):
    """
    Configure le logger global de l'application.
    
    Args:
        level: Niveau de logging (DEBUG, INFO, etc.)
        log_file: Chemin vers le fichier de log
    """
    # Créer le formateur
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configurer le logger racine
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Supprimer les handlers existants pour éviter les doublons
    for handler in root_logger.handlers[::]:
        root_logger.removeHandler(handler)
    
    # Ajouter un handler de console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    root_logger.addHandler(console_handler)
    
    # Ajouter un handler de fichier si demandé
    if log_file:
        try:
            # Créer le répertoire parent si nécessaire
            log_path = Path(os.path.expanduser(log_file))
            log_dir = log_path.parent
            log_dir.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_path)
            file_handler.setFormatter(formatter)
            file_handler.setLevel(level)
            root_logger.addHandler(file_handler)
            
            root_logger.info(f"Logs écrits dans: {log_path}")
        except Exception as e:
            root_logger.error(f"Impossible de configurer le fichier de log: {e}")
            
    return root_logger