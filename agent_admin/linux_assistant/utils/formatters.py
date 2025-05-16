"""
Utilitaires de formatage pour l'affichage et la sortie.
"""

import re
from typing import Dict, Any, List
from datetime import datetime

def format_datetime(dt):
    """
    Formate une date/heure pour l'affichage.
    
    Args:
        dt: Objet datetime ou chaîne ISO 8601
        
    Returns:
        Chaîne formatée
    """
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            return dt
    
    if isinstance(dt, datetime):
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    
    return str(dt)

def truncate_text(text, max_length=100):
    """
    Tronque un texte à une longueur maximale.
    
    Args:
        text: Texte à tronquer
        max_length: Longueur maximale
        
    Returns:
        Texte tronqué
    """
    if not text or len(text) <= max_length:
        return text
        
    return text[:max_length-3] + "..."

def format_command_for_markdown(command):
    """
    Formate une commande pour l'affichage en Markdown.
    
    Args:
        command: Commande à formater
        
    Returns:
        Commande formatée
    """
    # Échapper les caractères spéciaux Markdown
    escaped = re.sub(r'([\`\*\_\{\}\[\]\(\)\#\+\-\.\_\!])', r'\\\1', command)
    return f"```bash\n{escaped}\n```"

def extract_error_message(error_text):
    """
    Extrait un message d'erreur concis d'un texte d'erreur complet.
    
    Args:
        error_text: Texte d'erreur complet
        
    Returns:
        Message d'erreur concis
    """
    # Recherche de patterns communs dans les erreurs Linux
    patterns = [
        r'Error: (.+?)(?:\n|$)',
        r'ERROR: (.+?)(?:\n|$)',
        r'failed: (.+?)(?:\n|$)',
        r'\(ERROR\) (.+?)(?:\n|$)',
        r'Permission denied: (.+?)(?:\n|$)',
        r'Could not (.+?)(?:\n|$)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, error_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Si aucun pattern ne correspond, retourner la première ligne
    lines = error_text.strip().split('\n')
    return lines[0] if lines else error_text