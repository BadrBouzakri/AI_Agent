"""
Module d'analyse de tickets de support.
"""

import logging
from typing import Dict, Any, Optional
import re

from ..ollama_client import OllamaClient
from ..context_manager import ContextManager

logger = logging.getLogger(__name__)

class TicketAnalyzer:
    def __init__(self, ollama: OllamaClient, context: ContextManager):
        self.ollama = ollama
        self.context = context
        
    def analyze(self, ticket_description: str) -> str:
        """
        Analyse un ticket de support et propose une approche de résolution.
        
        Args:
            ticket_description: Description du ticket
            
        Returns:
            Analyse initiale et premières étapes de résolution
        """
        # Construire le prompt pour l'analyse de ticket
        prompt = self._build_analysis_prompt(ticket_description)
        
        try:
            # Générer l'analyse
            response = self.ollama.generate(
                prompt=prompt,
                temperature=0.3  # Basse température pour plus de précision
            )
            
            # Enregistrer le contexte
            self.context.set_context_data("ticket", ticket_description)
            self.context.set_context_data("current_task", "ticket_analysis")
            
            return response
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse du ticket: {e}")
            return f"Erreur lors de l'analyse du ticket: {e}"
    
    def _build_analysis_prompt(self, ticket: str) -> str:
        """
        Construit le prompt pour l'analyse de ticket.
        
        Args:
            ticket: Description du ticket
            
        Returns:
            Prompt complet pour l'analyse
        """
        prompt = f"""
Analyse le ticket de support suivant pour un serveur Linux. 
Fournis une analyse détaillée du problème et propose la première étape de diagnostic ou de résolution.

DESCRIPTION DU TICKET :
{ticket}

Ton analyse doit inclure :
1. Identification précise du problème technique
2. Systèmes/services potentiellement concernés
3. Causes probables
4. Première commande ou action de diagnostic à effectuer (en mode root, sans sudo)
5. Ce que l'on doit observer dans le résultat de cette commande

Important : Ne propose qu'une seule action ou commande, en attendant le retour de l'administrateur avant de continuer.
"""
        return prompt
        
    def suggest_next_step(self, current_output: str) -> str:
        """
        Suggère la prochaine étape de résolution en fonction du retour précédent.
        
        Args:
            current_output: Sortie de la commande précédente
            
        Returns:
            Suggestion de prochaine étape
        """
        # Récupérer le contexte actuel
        context_data = self.context.get_context_data()
        ticket = context_data.get("ticket", "")
        history = context_data.get("history", [])
        
        # Construire le prompt pour la suggestion
        prompt = f"""
Basé sur le ticket suivant et les échanges précédents, suggère la prochaine étape de diagnostic ou résolution.

TICKET INITIAL:
{ticket}

HISTORIQUE DES ÉCHANGES:
"""
        
        # Ajouter un résumé des échanges précédents
        for entry in history[-6:]:  # Limiter aux 6 derniers messages
            if entry["role"] == "user" and entry["content"] != ticket:
                prompt += f"\nADMIN: {entry['content']}\n"
            elif entry["role"] == "assistant":
                prompt += f"\nASSISTANT: {self._summarize_response(entry['content'])}\n"
        
        # Ajouter la sortie actuelle
        prompt += f"\nRÉSULTAT ACTUEL:\n{current_output}\n"
        
        prompt += """
Basé sur ces informations, propose UNE SEULE prochaine étape avec :
1. Une explication claire de ce que tu comprends du résultat actuel
2. Une seule commande ou action à effectuer maintenant (en mode root, sans sudo)
3. Ce que l'admin doit observer ou analyser dans le retour de cette commande

Reste concentré sur la résolution du problème initial, étape par étape.
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
    
    def _summarize_response(self, response: str) -> str:
        """
        Résume une réponse pour éviter de surcharger le contexte.
        
        Args:
            response: Réponse complète
            
        Returns:
            Résumé de la réponse
        """
        # Limiter la longueur
        if len(response) <= 200:
            return response
            
        # Extraire les commandes suggérées
        commands = re.findall(r'`([^`]+)`', response)
        command_text = ", ".join([f"`{cmd}`" for cmd in commands[:2]])
        
        # Créer un résumé
        return response[:150] + "... " + (f"[Commandes suggérées: {command_text}]" if commands else "")