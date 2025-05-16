"""
Utilitaires de sécurité pour vérifier les commandes dangereuses.
"""

import re
from typing import List, Tuple

# Liste des commandes potentiellement dangereuses
DANGEROUS_COMMANDS = [
    'rm -rf', 'rm -r', 'rmdir', 'mkfs', 'dd', 'shred',
    'fdisk', 'mkfs', 'format', '>>', '>', 'truncate',
    'drop database', 'drop table', 'delete from', 'wget', 'curl -O'
]

# Liste des options dangereuses
DANGEROUS_OPTIONS = [
    '--force', '--no-preserve-root', '-f', '--delete'
]

def check_command_safety(commands: List[str]) -> Tuple[List[str], List[str]]:
    """
    Vérifie la sécurité des commandes.
    
    Args:
        commands: Liste des commandes à vérifier
        
    Returns:
        Tuple (safe_commands, unsafe_commands)
    """
    safe_commands = []
    unsafe_commands = []
    
    for command in commands:
        is_safe = True
        
        # Vérifier les commandes dangereuses
        for dangerous in DANGEROUS_COMMANDS:
            if dangerous in command:
                is_safe = False
                break
                
        # Vérifier les options dangereuses
        if is_safe:
            for option in DANGEROUS_OPTIONS:
                if option in command:
                    is_safe = False
                    break
        
        # Vérifier les redirections vers des fichiers système
        if is_safe and ('>' in command or '>>' in command):
            # Recherche de redirection vers des fichiers système
            system_paths = ['/etc/', '/var/', '/boot/', '/lib/', '/bin/', '/sbin/']
            for path in system_paths:
                if path in command:
                    is_safe = False
                    break
        
        if is_safe:
            safe_commands.append(command)
        else:
            unsafe_commands.append(command)
            
    return safe_commands, unsafe_commands

def sanitize_command(command: str) -> str:
    """
    Sanitize une commande en remplaçant les parties dangereuses.
    
    Args:
        command: Commande à sanitizer
        
    Returns:
        Commande sanitizée
    """
    # Remplacer rm -rf par rm -i
    command = re.sub(r'rm\s+-rf', 'rm -i', command)
    
    # Remplacer les redirections complètes par des redirections de visualisation
    command = re.sub(r'>\s+(/[^\s]+)', r'| less # ATTENTION: redirection vers \1 retirée', command)
    
    return command