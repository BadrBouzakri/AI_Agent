"""
Gestionnaire de contexte pour l'assistant.
Conserve l'historique des conversations et le contexte actuel.
"""

import logging
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from .config import config

logger = logging.getLogger(__name__)

class ContextManager:
    def __init__(self):
        self.messages = []
        self.context_data = {
            "ticket": None,
            "alert": None,
            "current_task": None
        }
        self.history_size = config.get("behavior", "history_size", default=100)
        self.session_dir = self._setup_session_dir()
        
    def _setup_session_dir(self) -> Path:
        """Prépare le répertoire de session pour sauvegarder les données."""
        base_dir = Path(os.path.expanduser("~/.local/share/linux-assistant/sessions"))
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = base_dir / session_id
        
        try:
            session_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Session créée: {session_dir}")
        except Exception as e:
            logger.error(f"Erreur lors de la création du répertoire de session: {e}")
            # Fallback to temp directory
            import tempfile
            session_dir = Path(tempfile.mkdtemp(prefix="linux-assistant-"))
            
        return session_dir
        
    def add_message(self, role: str, content: str):
        """
        Ajoute un message à l'historique des conversations.
        
        Args:
            role: Le rôle ('user' ou 'assistant')
            content: Le contenu du message
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        self.messages.append(message)
        
        # Limiter la taille de l'historique
        if len(self.messages) > self.history_size:
            self.messages = self.messages[-self.history_size:]
            
        # Sauvegarder l'historique si configuré
        if config.get("behavior", "session_history", default=True):
            self._save_history()
            
    def get_history(self) -> List[Dict[str, Any]]:
        """
        Récupère l'historique des messages.
        
        Returns:
            Liste des messages
        """
        return self.messages
        
    def set_context_data(self, key: str, value: Any):
        """
        Définit une donnée de contexte.
        
        Args:
            key: Clé du contexte
            value: Valeur associée
        """
        self.context_data[key] = value
        
    def get_context_data(self) -> Dict[str, Any]:
        """
        Récupère les données de contexte actuelles.
        
        Returns:
            Dictionnaire des données de contexte
        """
        context = self.context_data.copy()
        context["history"] = self.messages
        return context
        
    def clear_context(self):
        """Réinitialise le contexte actuel."""
        self.context_data = {
            "ticket": None,
            "alert": None,
            "current_task": None
        }
        
    def _save_history(self):
        """Sauvegarde l'historique dans un fichier JSON."""
        try:
            history_file = self.session_dir / "history.json"
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.messages, f, ensure_ascii=False, indent=2)
                
            # Sauvegarder également le contexte actuel
            context_file = self.session_dir / "context.json"
            with open(context_file, 'w', encoding='utf-8') as f:
                json.dump(self.context_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de l'historique: {e}")