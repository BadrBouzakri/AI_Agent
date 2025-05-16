"""
Client Ollama pour l'interaction avec le modèle LLM.
"""

import json
import requests
from typing import Dict, Any, List, Optional, Generator
import logging
from .config import config

logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self):
        self.base_url = config.get("ollama", "base_url")
        self.model = config.get("ollama", "model")
        self.timeout = config.get("ollama", "timeout")
        self.session = requests.Session()
        
    def generate(self, 
                prompt: str, 
                system_prompt: Optional[str] = None,
                temperature: float = 0.7, 
                max_tokens: Optional[int] = None,
                stream: bool = False) -> str:
        """
        Génère une réponse à partir du modèle Ollama.
        
        Args:
            prompt: Le prompt utilisateur
            system_prompt: Instructions système pour le modèle
            temperature: Température pour la génération (créativité)
            max_tokens: Nombre maximum de tokens à générer
            stream: Si True, retourne un générateur au lieu d'une chaîne complète
            
        Returns:
            La réponse générée par le modèle
        """
        url = f"{self.base_url}/api/generate"
        
        # Préparation des paramètres
        params = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
            "stream": stream
        }
        
        if system_prompt:
            params["system"] = system_prompt
            
        if max_tokens:
            params["max_tokens"] = max_tokens
        else:
            params["max_tokens"] = config.get("ollama", "max_tokens", default=2048)
        
        logger.debug(f"Envoi de la requête à Ollama: {params}")
        
        try:
            if not stream:
                response = self.session.post(
                    url, 
                    json=params,
                    timeout=self.timeout
                )
                response.raise_for_status()
                result = response.json()
                return result.get("response", "")
            else:
                # Mode streaming
                response = self.session.post(
                    url, 
                    json=params,
                    timeout=self.timeout,
                    stream=True
                )
                response.raise_for_status()
                
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        yield chunk.get("response", "")
                        
                        # Vérifier si c'est la fin de la réponse
                        if chunk.get("done", False):
                            break
                            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur lors de la communication avec Ollama: {e}")
            if stream:
                yield f"Erreur de communication avec Ollama: {e}"
            else:
                return f"Erreur de communication avec Ollama: {e}"
    
    def get_system_prompt(self, context: Dict[str, Any]) -> str:
        """
        Génère le prompt système complet basé sur le contexte actuel.
        """
        # Prompt de base pour l'assistant Linux
        base_prompt = """Tu es un assistant IA pour le support technique de serveurs Linux.
Tu aides un administrateur systèmes qui intervient sur des serveurs en production, 
principalement sous Red Hat Enterprise Linux (RHEL), Rocky Linux et AlmaLinux.

✅ Règles strictes à respecter :

🔒 Sécurité et prudence :
⚠️ Ne propose jamais de commande à effet potentiellement destructeur sans avertissement explicite.
Indique systématiquement les risques potentiels et propose des alternatives sûres si disponibles.

🧩 Méthode interactive :
Une seule vérification ou action par message.
Attends toujours le retour avant de passer à l'étape suivante.

💬 Clarté et pédagogie :
À chaque étape, explique ce que tu proposes, pourquoi tu le proposes, 
et ce qui doit être observé dans le retour de commande.

⚙️ Commandes et outils :
Les commandes doivent toujours être données en mode root, sans utiliser sudo.
Pour l'édition de fichiers, utilise toujours vim.
"""
        
        # Ajouter les informations contextuelles si disponibles
        if context.get("ticket"):
            base_prompt += f"\nContexte du ticket actuel: {context['ticket']}\n"
            
        if context.get("alert"):
            base_prompt += f"\nContexte de l'alerte actuelle: {context['alert']}\n"
            
        if context.get("history"):
            base_prompt += "\nHistorique récent de la conversation:\n"
            for entry in context["history"][-5:]:  # Inclure seulement les 5 derniers échanges
                base_prompt += f"- {entry}\n"
                
        return base_prompt