#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IacAgent - Assistant IA CLI pour DevOps
Permet de générer de l'infrastructure as code, créer des fichiers et exécuter des commandes
via des instructions en langage naturel, en utilisant l'API Mistral.
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

import requests

# Configuration des logs
LOG_DIR = os.path.expanduser("~/iacagent")
LOG_FILE = os.path.join(LOG_DIR, "iacagent.log")

# Configuration du logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("iacagent")

# Historique des interactions
HISTORY_FILE = os.path.join(LOG_DIR, "history.json")

# Fichier de configuration et environnement
CONFIG_FILE = os.path.expanduser("~/iacagent/config.json")
ENV_FILE = os.path.expanduser("~/iacagent/.env")

# Mots-clés à risque pour les commandes
DANGEROUS_KEYWORDS = [
    "rm -rf", "mkfs", "dd if", ":(){ :|:& };:", "> /dev/sda",
    "chmod -R 777", "> /dev/null", "mv /* /dev/null",
    "shutdown", "reboot", "halt", "poweroff",
    "curl | bash", "wget | bash", "sudo su"
]

class IacAgent:
    """
    Agent IA pour l'assistance DevOps en ligne de commande
    """
    
    def __init__(self, api_key: Optional[str] = None, dry_run: bool = False):
        """
        Initialise l'agent avec la clé API et le mode d'exécution
        
        Args:
            api_key: Clé API Mistral
            dry_run: Si True, demande confirmation avant d'exécuter des commandes ou créer des fichiers
        """
        self.api_key = api_key or self.get_api_key()
        self.dry_run = dry_run
        self.history = self.load_history()
        
        # Charger le prompt
        self.prompt_template = self.load_prompt_template()
        
        logger.info("IacAgent initialisé")
    
    def get_api_key(self) -> str:
        """
        Récupère la clé API depuis l'environnement ou le fichier de configuration
        
        Returns:
            str: Clé API Mistral
        """
        # Essayer d'abord la variable d'environnement
        api_key = os.environ.get("MISTRAL_API_KEY")
        
        # Sinon, essayer le fichier .env
        if not api_key and os.path.exists(ENV_FILE):
            with open(ENV_FILE, "r") as f:
                for line in f:
                    if line.startswith("MISTRAL_API_KEY="):
                        api_key = line.strip().split("=", 1)[1].strip('"\'')
                        break
        
        # Sinon, essayer le fichier de configuration
        if not api_key and os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    api_key = config.get("api_key")
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        
        if not api_key:
            logger.error("Aucune clé API Mistral trouvée. Définissez-la avec --api-key, "
                      "dans ~/iacagent/config.json, dans ~/iacagent/.env ou dans la variable "
                      "d'environnement MISTRAL_API_KEY")
            sys.exit(1)
        
        return api_key
    
    def load_prompt_template(self) -> str:
        """
        Charge le template de prompt depuis le fichier
        
        Returns:
            str: Template de prompt
        """
        prompt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt.txt")
        
        try:
            with open(prompt_path, "r") as f:
                return f.read()
        except FileNotFoundError:
            # Fallback si le fichier n'existe pas
            logger.warning("Fichier prompt.txt non trouvé, utilisation du prompt par défaut")
            return """Tu es un assistant IA spécialisé dans le DevOps, nommé IacAgent. Tu aides les professionnels Linux/DevOps à créer de l'infrastructure as code (IaC) et à automatiser leurs tâches.

Réponds uniquement en JSON avec le format suivant:
```
{
  "type": "file_creation" | "command_execution" | "mixed" | "information",
  "files": [
    {
      "path": "/chemin/complet/vers/fichier.extension",
      "content": "Contenu du fichier à créer ou modifier",
      "mode": "create" | "append" | "overwrite"
    }
  ],
  "commands": [
    "commande1 à exécuter",
    "commande2 à exécuter"
  ],
  "information": "Toute information supplémentaire utile",
  "warnings": ["Avertissement 1", "Avertissement 2"]
}
```
"""
    
    def load_history(self) -> List[Dict]:
        """
        Charge l'historique des interactions
        
        Returns:
            List[Dict]: Historique des interactions
        """
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning("Erreur lors du chargement de l'historique")
                return []
        return []
    
    def save_history(self):
        """Sauvegarde l'historique des interactions"""
        with open(HISTORY_FILE, "w") as f:
            json.dump(self.history, f, indent=2)
    
    def add_to_history(self, query: str, response: Dict):
        """
        Ajoute une interaction à l'historique
        
        Args:
            query: Requête de l'utilisateur
            response: Réponse de l'API
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "response": response
        }
        self.history.append(entry)
        self.save_history()
    
    def query_mistral(self, user_input: str) -> Dict:
        """
        Interroge l'API Mistral avec l'entrée utilisateur
        
        Args:
            user_input: Instruction en langage naturel de l'utilisateur
            
        Returns:
            Dict: Réponse formatée de l'API
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Construire le prompt complet
        prompt = f"{self.prompt_template}\n\nUtilisateur: {user_input}\n\nRéponse:"
        
        data = {
            "model": "mistral-large-latest",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        
        try:
            logger.info("Envoi de la requête à l'API Mistral")
            response = requests.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            
            response_data = response.json()
            content = response_data["choices"][0]["message"]["content"]
            
            # Extraire le JSON de la réponse
            json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', content, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)
            else:
                # Tenter de parser directement comme JSON
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    logger.error("Impossible de parser la réponse comme JSON")
                    return {
                        "type": "information",
                        "information": "Erreur: Impossible de générer une réponse structurée. Veuillez reformuler votre demande."
                    }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur lors de la requête à l'API Mistral: {e}")
            return {
                "type": "information",
                "information": f"Erreur de connexion à l'API Mistral: {e}"
            }
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de décodage JSON: {e}")
            return {
                "type": "information",
                "information": "Erreur de traitement de la réponse. Veuillez réessayer."
            }
    
    def is_dangerous_command(self, command: str) -> bool:
        """
        Vérifie si une commande est potentiellement dangereuse
        
        Args:
            command: Commande à vérifier
            
        Returns:
            bool: True si la commande est dangereuse
        """
        command = command.lower()
        return any(keyword.lower() in command for keyword in DANGEROUS_KEYWORDS)
    
    def execute_command(self, command: str) -> str:
        """
        Exécute une commande shell et retourne le résultat
        
        Args:
            command: Commande à exécuter
            
        Returns:
            str: Sortie de la commande
        """
        if self.is_dangerous_command(command):
            warning_msg = f"ATTENTION: La commande '{command}' semble potentiellement dangereuse"
            logger.warning(warning_msg)
            
            if self.dry_run or input(f"{warning_msg}. Exécuter quand même? (o/N): ").lower() != "o":
                return "Exécution annulée par mesure de sécurité."
        
        if self.dry_run:
            confirm = input(f"Exécuter la commande: '{command}' ? (o/N): ")
            if confirm.lower() != "o":
                return "Exécution annulée."
        
        try:
            logger.info(f"Exécution de la commande: {command}")
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                output = result.stdout or "Commande exécutée avec succès (pas de sortie)"
                logger.info(f"Commande exécutée avec succès: {command}")
            else:
                output = f"Erreur (code {result.returncode}): {result.stderr}"
                logger.error(f"Erreur lors de l'exécution de la commande: {command} - {output}")
            
            return output
        
        except Exception as e:
            error_msg = f"Erreur lors de l'exécution de la commande: {e}"
            logger.error(error_msg)
            return error_msg
    
    def create_file(self, file_info: Dict) -> str:
        """
        Crée ou modifie un fichier selon les informations fournies
        
        Args:
            file_info: Informations sur le fichier (chemin, contenu, mode)
            
        Returns:
            str: Message de résultat
        """
        path = os.path.expanduser(file_info["path"])
        content = file_info["content"]
        mode = file_info.get("mode", "create")
        
        # Créer le répertoire parent si nécessaire
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        
        if self.dry_run:
            confirm = input(f"Créer/modifier le fichier: '{path}' en mode '{mode}' ? (o/N): ")
            if confirm.lower() != "o":
                return "Création/modification annulée."
        
        try:
            if mode == "append" and os.path.exists(path):
                logger.info(f"Ajout au fichier: {path}")
                with open(path, "a") as f:
                    f.write(content)
                return f"Contenu ajouté au fichier: {path}"
            
            elif mode == "overwrite" or mode == "create" or not os.path.exists(path):
                logger.info(f"Création/écrasement du fichier: {path}")
                with open(path, "w") as f:
                    f.write(content)
                return f"Fichier créé/modifié: {path}"
            
        except Exception as e:
            error_msg = f"Erreur lors de la création/modification du fichier {path}: {e}"
            logger.error(error_msg)
            return error_msg
    
    def process_response(self, response: Dict) -> str:
        """
        Traite la réponse de l'API et exécute les actions nécessaires
        
        Args:
            response: Réponse formatée de l'API
            
        Returns:
            str: Résumé des actions réalisées
        """
        response_type = response.get("type", "information")
        files = response.get("files", [])
        commands = response.get("commands", [])
        info = response.get("information", "")
        warnings = response.get("warnings", [])
        
        results = []
        
        # Traiter les avertissements
        for warning in warnings:
            logger.warning(warning)
            results.append(f"⚠️ {warning}")
        
        # Traiter les fichiers
        if files:
            results.append("\n📁 FICHIERS:")
            for file_info in files:
                result = self.create_file(file_info)
                results.append(f" - {result}")
        
        # Traiter les commandes
        if commands:
            results.append("\n🖥️ COMMANDES:")
            for command in commands:
                results.append(f" - Commande: {command}")
                output = self.execute_command(command)
                results.append(f"   Résultat: {output.strip()[:300]}")
                if len(output) > 300:
                    results.append("   (sortie tronquée, voir le log pour les détails)")
        
        # Ajouter les informations complémentaires
        if info:
            results.append(f"\n📌 INFORMATIONS:\n{info}")
        
        return "\n".join(results)
    
    def run(self, user_input: str) -> str:
        """
        Exécute le processus complet depuis l'entrée utilisateur
        
        Args:
            user_input: Instruction en langage naturel de l'utilisateur
            
        Returns:
            str: Résultat formaté pour l'utilisateur
        """
        logger.info(f"Requête utilisateur: {user_input}")
        
        # Détecter automatiquement le type d'infrastructure demandé
        iac_keywords = {
            "terraform": ["terraform", "aws", "azure", "gcp", "provider", "resource", "module", "tf"],
            "ansible": ["ansible", "playbook", "inventory", "role", "task", "host"],
            "docker": ["docker", "dockerfile", "image", "container", "compose"],
            "kubernetes": ["kubernetes", "k8s", "pod", "deployment", "service", "ingress", "configmap", "secret"],
        }
        
        detected_tools = []
        for tool, keywords in iac_keywords.items():
            if any(keyword.lower() in user_input.lower() for keyword in keywords):
                detected_tools.append(tool)
        
        if detected_tools:
            logger.info(f"Outils détectés: {', '.join(detected_tools)}")
        
        # Interroger l'API
        response = self.query_mistral(user_input)
        
        # Traiter la réponse
        result = self.process_response(response)
        
        # Enregistrer dans l'historique
        self.add_to_history(user_input, response)
        
        return result

def main():
    """Point d'entrée principal du programme"""
    parser = argparse.ArgumentParser(description="IacAgent - Assistant IA CLI pour DevOps")
    parser.add_argument("--api-key", help="Clé API Mistral")
    parser.add_argument("--dry-run", action="store_true", help="Demander confirmation avant chaque action")
    parser.add_argument("query", nargs="*", help="Requête à l'agent (facultatif)")
    
    args = parser.parse_args()
    
    # Vérifier que le répertoire et le fichier de log existent
    os.makedirs(LOG_DIR, exist_ok=True)
    Path(LOG_FILE).touch(exist_ok=True)
    
    agent = IacAgent(api_key=args.api_key, dry_run=args.dry_run)
    
    # Si une requête est fournie en argument
    if args.query:
        query = " ".join(args.query)
        result = agent.run(query)
        print(result)
    else:
        # Mode interactif
        print("🤖 IacAgent - Assistant IA CLI pour DevOps")
        print("Tapez 'q' ou 'exit' pour quitter")
        
        while True:
            try:
                query = input("\n> ")
                
                if query.lower() in ["q", "quit", "exit"]:
                    break
                
                if not query.strip():
                    continue
                
                result = agent.run(query)
                print(result)
                
            except KeyboardInterrupt:
                print("\nInterruption détectée. Au revoir!")
                break
            except Exception as e:
                logger.error(f"Erreur non gérée: {e}", exc_info=True)
                print(f"Une erreur est survenue: {e}")

if __name__ == "__main__":
    main()