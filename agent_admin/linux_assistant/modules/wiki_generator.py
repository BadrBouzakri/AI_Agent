"""
Module de génération de wiki basé sur l'intervention actuelle.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
import markdown
from typing import Optional

from ..ollama_client import OllamaClient
from ..context_manager import ContextManager
from ..config import config

logger = logging.getLogger(__name__)

class WikiGenerator:
    def __init__(self, ollama: OllamaClient, context: ContextManager):
        self.ollama = ollama
        self.context = context
        
    def generate(self) -> Optional[str]:
        """
        Génère un wiki basé sur la conversation actuelle.
        
        Returns:
            Contenu du wiki au format Markdown, ou None en cas d'échec
        """
        history = self.context.get_history()
        context_data = self.context.get_context_data()
        
        if not history or len(history) < 3:
            logger.warning("Historique insuffisant pour générer un wiki.")
            return None
            
        # Créer le prompt pour la génération du wiki
        wiki_prompt = self._create_wiki_prompt(history, context_data)
        
        try:
            # Générer le contenu du wiki
            wiki_content = self.ollama.generate(
                prompt=wiki_prompt,
                temperature=0.3,  # Basse température pour plus de précision
                max_tokens=2048
            )
            
            # Sauvegarder le wiki
            if wiki_content:
                self._save_wiki(wiki_content)
                return wiki_content
            else:
                logger.error("La génération du wiki n'a pas produit de contenu.")
                return None
                
        except Exception as e:
            logger.error(f"Erreur lors de la génération du wiki: {e}")
            return None
            
    def _create_wiki_prompt(self, history, context_data):
        """
        Crée le prompt pour la génération du wiki.
        """
        ticket = context_data.get("ticket")
        alert = context_data.get("alert")
        
        prompt = """
Génère une documentation wiki technique en Markdown basée sur la conversation suivante.
Le wiki doit inclure :

1. Un titre clair
2. Description du problème initial
3. Diagnostic technique effectué
4. Solution appliquée avec les commandes utilisées
5. Vérifications post-intervention
6. Recommandations pour éviter les problèmes similaires

Format voulu :
- Markdown bien structuré
- Sections claires avec titres
- Code en blocs avec syntax highlighting
- Explications concises et techniques

Conversation :
"""
        
        # Ajouter contexte
        if ticket:
            prompt += f"\nTicket initial : {ticket}\n\n"
        if alert:
            prompt += f"\nAlerte initiale : {alert}\n\n"
            
        # Ajouter historique récent (limité pour éviter de dépasser la taille du contexte)
        for entry in history[-15:]:
            prompt += f"{entry['role'].upper()}: {entry['content']}\n\n"
            
        prompt += "\nGénère maintenant le wiki technique complet au format Markdown."
        
        return prompt
        
    def _save_wiki(self, content: str):
        """
        Sauvegarde le wiki généré.
        
        Args:
            content: Contenu du wiki au format Markdown
        """
        try:
            # Créer un répertoire pour les wikis s'il n'existe pas
            wiki_dir = Path(os.path.expanduser("~/.local/share/linux-assistant/wikis"))
            wiki_dir.mkdir(parents=True, exist_ok=True)
            
            # Générer un nom de fichier basé sur le contexte et la date
            context_data = self.context.get_context_data()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if context_data.get("ticket"):
                title = f"ticket_{timestamp}"
            elif context_data.get("alert"):
                title = f"alerte_{timestamp}"
            else:
                title = f"wiki_{timestamp}"
                
            # Sauvegarder en markdown
            md_path = wiki_dir / f"{title}.md"
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            # Générer également une version HTML
            html_path = wiki_dir / f"{title}.html"
            html_content = markdown.markdown(content, extensions=['fenced_code', 'codehilite'])
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>{title}</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 40px; }}
                        h1 {{ color: #2c3e50; }}
                        h2 {{ color: #3498db; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
                        pre {{ background: #f8f8f8; border: 1px solid #ddd; padding: 10px; border-radius: 5px; }}
                        code {{ background: #f8f8f8; padding: 2px 4px; }}
                    </style>
                </head>
                <body>
                    {html_content}
                    <footer>
                        <p><small>Généré le {datetime.now().strftime("%d/%m/%Y à %H:%M:%S")}</small></p>
                    </footer>
                </body>
                </html>
                """)
                
            logger.info(f"Wiki sauvegardé: {md_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du wiki: {e}")
            return False