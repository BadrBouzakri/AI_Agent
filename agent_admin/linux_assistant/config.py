"""
Configuration de l'agent IA d'assistance Linux.
Gère les paramètres de l'application et les options d'Ollama.
"""

import os
import yaml
from pathlib import Path
import logging

DEFAULT_CONFIG = {
    "ollama": {
        "model": "qwen2.5-coder:7b",
        "base_url": "http://localhost:11434",
        "timeout": 60,
        "max_tokens": 2048,
    },
    "ui": {
        "prompt": "🐧> ",
        "colors": {
            "info": "blue",
            "warning": "yellow",
            "error": "red",
            "command": "green",
            "explanation": "cyan",
        },
    },
    "behavior": {
        "step_by_step": True,
        "safety_checks": True,
        "session_history": True,
        "history_size": 100,
    },
    "logging": {
        "level": "INFO",
        "file": "~/.local/share/linux-assistant/logs/assistant.log",
    }
}

class Config:
    def __init__(self):
        self.config_dir = Path(os.path.expanduser("~/.config/linux-assistant"))
        self.config_file = self.config_dir / "config.yaml"
        self.config = DEFAULT_CONFIG
        self._load_config()
        
    def _load_config(self):
        """Charge la configuration depuis le fichier YAML s'il existe."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    user_config = yaml.safe_load(f)
                    if user_config:
                        self._merge_configs(self.config, user_config)
            except Exception as e:
                logging.error(f"Erreur lors du chargement de la configuration: {e}")
    
    def _load_config_from_file(self, config_path):
        """Charge la configuration depuis un fichier spécifique."""
        try:
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    self._merge_configs(self.config, user_config)
        except Exception as e:
            logging.error(f"Erreur lors du chargement de la configuration depuis {config_path}: {e}")
                
    def _merge_configs(self, default, user):
        """Fusionne la configuration utilisateur avec les valeurs par défaut."""
        for key, value in user.items():
            if key in default and isinstance(value, dict) and isinstance(default[key], dict):
                self._merge_configs(default[key], value)
            else:
                default[key] = value
    
    def save_config(self):
        """Sauvegarde la configuration actuelle dans le fichier YAML."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False)
            
    def get(self, *keys, default=None):
        """Récupère une valeur de configuration par chemin de clés."""
        config = self.config
        for key in keys:
            if isinstance(config, dict) and key in config:
                config = config[key]
            else:
                return default
        return config

# Instance globale de configuration
config = Config()