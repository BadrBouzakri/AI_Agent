"""
Module de gestion des alertes système.
"""

import logging
import re
from typing import Dict, Any, List, Optional

from ..ollama_client import OllamaClient
from ..context_manager import ContextManager

logger = logging.getLogger(__name__)

class AlertHandler:
    def __init__(self, ollama: OllamaClient, context: ContextManager):
        self.ollama = ollama
        self.context = context
        
        # Patterns pour identifier les types d'alerte
        self.alert_patterns = {
            "disk_space": r'(disk|space|filesystem|partition|volume).*?(full|capacity|[0-9]{2,3}%)',
            "cpu_load": r'(cpu|load|charge).*?(high|elevée|importante)',
            "memory": r'(memory|ram|mémoire|swap).*?(high|low|full|elevée)',
            "service_down": r'(service|process|daemon).*?(down|stopped|arrêté|failed|échec)',
            "network": r'(network|réseau|connectivity|connexion).*?(down|issue|problème)',
            "security": r'(security|sécurité|attack|intrusion|brute force)'
        }
        
    def analyze(self, alert_description: str) -> str:
        """
        Analyse une alerte système et propose une approche de résolution.
        
        Args:
            alert_description: Description de l'alerte
            
        Returns:
            Analyse et premières étapes de résolution
        """
        # Déterminer le type d'alerte
        alert_type = self._determine_alert_type(alert_description)
        
        # Construire le prompt pour l'analyse
        prompt = self._build_analysis_prompt(alert_description, alert_type)
        
        try:
            # Générer l'analyse
            response = self.ollama.generate(
                prompt=prompt,
                temperature=0.3  # Basse température pour plus de précision
            )
            
            # Enregistrer le contexte
            self.context.set_context_data("alert", alert_description)
            self.context.set_context_data("alert_type", alert_type)
            self.context.set_context_data("current_task", "alert_handling")
            
            return response
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse de l'alerte: {e}")
            return f"Erreur lors de l'analyse de l'alerte: {e}"
    
    def _determine_alert_type(self, alert: str) -> str:
        """
        Détermine le type d'alerte en fonction de sa description.
        
        Args:
            alert: Description de l'alerte
            
        Returns:
            Type d'alerte identifié
        """
        for alert_type, pattern in self.alert_patterns.items():
            if re.search(pattern, alert, re.IGNORECASE):
                return alert_type
                
        return "unknown"
    
    def _build_analysis_prompt(self, alert: str, alert_type: str) -> str:
        """
        Construit le prompt pour l'analyse de l'alerte.
        
        Args:
            alert: Description de l'alerte
            alert_type: Type d'alerte identifié
            
        Returns:
            Prompt complet pour l'analyse
        """
        # Base du prompt
        prompt = f"""
Analyse l'alerte système suivante pour un serveur Linux et propose une approche de résolution.

ALERTE :
{alert}

TYPE D'ALERTE IDENTIFIÉ : {alert_type}

Fournis une analyse structurée incluant :
1. Gravité probable de l'alerte (critique, importante, moyenne, faible)
2. Impact potentiel sur les services
3. Première commande ou action de diagnostic à effectuer (en mode root, sans sudo)
4. Ce que l'on doit observer dans le résultat de cette commande

Reste concentré sur l'analyse initiale et la première action uniquement. Utilise toujours des commandes en mode root (pas de sudo).
"""
        
        # Ajouter des conseils spécifiques selon le type d'alerte
        if alert_type == "disk_space":
            prompt += """

Pour les alertes d'espace disque, considère :
- Identifier les partitions concernées avec `df -h`
- Localiser les répertoires volumineux avec `du -sh /*`
- Vérifier les fichiers de log qui pourraient avoir grossi
"""
        
        elif alert_type == "cpu_load":
            prompt += """

Pour les alertes de charge CPU, considère :
- Identifier les processus consommateurs avec `top` ou `htop`
- Vérifier depuis quand la charge est élevée avec `uptime`
- Analyser les tendances avec `sar`
"""
        
        elif alert_type == "service_down":
            prompt += """

Pour les alertes de service arrêté, considère :
- Vérifier l'état du service avec `systemctl status service_name`
- Examiner les logs avec `journalctl -u service_name`
- Vérifier les dépendances du service
"""
        
        return prompt
        
    def suggest_next_step(self, current_output: str) -> str:
        """
        Suggère la prochaine étape en fonction du retour précédent.
        
        Args:
            current_output: Sortie de la commande précédente
            
        Returns:
            Suggestion de prochaine étape
        """
        # Récupérer le contexte actuel
        context_data = self.context.get_context_data()
        alert = context_data.get("alert", "")
        alert_type = context_data.get("alert_type", "unknown")
        history = context_data.get("history", [])
        
        # Construire le prompt pour la suggestion
        prompt = f"""
Basé sur l'alerte suivante et les échanges précédents, suggère la prochaine étape.

ALERTE INITIALE (Type: {alert_type}):
{alert}

RÉSULTAT ACTUEL:
{current_output}

"""
        
        # Ajouter un résumé des échanges précédents
        if history:
            prompt += "\nHISTORIQUE DES ACTIONS:\n"
            for entry in history[-6:]:  # Limiter aux 6 derniers messages
                if entry["role"] == "assistant":
                    # Extraire les commandes suggérées
                    commands = re.findall(r'`([^`]+)`', entry["content"])
                    if commands:
                        commands_str = ", ".join([f"`{cmd}`" for cmd in commands[:2]])
                        prompt += f"- Action précédente: {commands_str}\n"
        
        prompt += """
Basé sur ces informations, propose UNE SEULE prochaine action avec :
1. Une interprétation concise du résultat actuel
2. Une seule commande à exécuter maintenant (en mode root, sans sudo)
3. Ce que l'administrateur doit observer dans le résultat

Reste concentré sur la résolution de l'alerte initiale, pas à pas.
"""
        
        try:
            response = self.ollama.generate(
                prompt=prompt,
                temperature=0.3
            )
            return response
        except Exception as e:
            logger.error(f"Erreur lors de la suggestion de l'étape suivante: {e}")
            return f"Erreur lors de la suggestion: {e}"