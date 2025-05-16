"""
Module d'assistance pour les serveurs Apache (httpd).
Fournit des fonctionnalités spécifiques pour l'analyse et la résolution des problèmes Apache.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple

from ..ollama_client import OllamaClient
from ..context_manager import ContextManager

logger = logging.getLogger(__name__)

class ApacheHelper:
    def __init__(self, ollama: OllamaClient, context: ContextManager):
        self.ollama = ollama
        self.context = context
        
        # Chemins courants des fichiers Apache
        self.apache_paths = {
            "rhel": {
                "conf": "/etc/httpd/conf/httpd.conf",
                "conf_d": "/etc/httpd/conf.d/",
                "logs": "/var/log/httpd/",
                "service": "httpd",
                "modules": "/etc/httpd/modules/"
            },
            "debian": {
                "conf": "/etc/apache2/apache2.conf",
                "conf_d": "/etc/apache2/sites-available/",
                "logs": "/var/log/apache2/",
                "service": "apache2",
                "modules": "/etc/apache2/mods-available/"
            }
        }
        
        # Patterns d'erreurs courants
        self.error_patterns = {
            "ssl": r'(SSL|TLS|certificate|cert|unable to verify the first certificate|handshake).*error',
            "permission": r'(Permission denied|failed to open|could not access|unable to open|is writable by others)',
            "syntax": r'(Syntax error|configuration error|parse error|unexpected|token|unknown directive)',
            "timeout": r'(timeout|timed out|connection refused)',
            "module": r'(module|mod_.*?) not found|(module|mod_.*?) missing',
            "memory": r'(out of memory|memory exhausted|cannot allocate memory)'
        }
        
    def analyze_config(self, config_content: str) -> Dict[str, Any]:
        """
        Analyse un fichier de configuration Apache et retourne des informations clés.
        
        Args:
            config_content: Contenu du fichier de configuration
            
        Returns:
            Dictionnaire avec les informations clés
        """
        config_info = {
            "virtual_hosts": [],
            "modules": [],
            "ports": [],
            "document_roots": [],
            "ssl_enabled": False,
            "rewrite_enabled": False,
            "error_log": None,
            "access_log": None
        }
        
        # Analyse des VirtualHosts
        vhost_matches = re.findall(r'<VirtualHost\s+(.+?)>(.*?)</VirtualHost>', 
                                 config_content, re.DOTALL)
        
        for match in vhost_matches:
            address = match[0].strip()
            vhost_content = match[1]
            
            # Extraire le ServerName
            server_name = re.search(r'ServerName\s+(.+)', vhost_content)
            server_name = server_name.group(1).strip() if server_name else "unnamed"
            
            # Extraire le DocumentRoot
            doc_root = re.search(r'DocumentRoot\s+"?([^"\s]+)"?', vhost_content)
            doc_root = doc_root.group(1).strip() if doc_root else None
            
            # Vérifier si SSL est activé
            ssl_enabled = "SSLEngine on" in vhost_content
            
            vhost_info = {
                "address": address,
                "server_name": server_name,
                "document_root": doc_root,
                "ssl": ssl_enabled
            }
            
            config_info["virtual_hosts"].append(vhost_info)
            
            if doc_root:
                config_info["document_roots"].append(doc_root)
                
            if ssl_enabled:
                config_info["ssl_enabled"] = True
            
            # Extraire les ports des adresses
            if ':' in address:
                port = address.split(':')[1].strip()
                if port not in config_info["ports"]:
                    config_info["ports"].append(port)
        
        # Modules chargés
        module_matches = re.findall(r'LoadModule\s+(\w+)\s+', config_content)
        config_info["modules"] = module_matches
        
        # Vérifier si le module rewrite est activé
        if "rewrite_module" in module_matches:
            config_info["rewrite_enabled"] = True
            
        # Extraire les chemins des logs
        error_log = re.search(r'ErrorLog\s+"?([^"\s]+)"?', config_content)
        if error_log:
            config_info["error_log"] = error_log.group(1).strip()
            
        access_log = re.search(r'CustomLog\s+"?([^"\s]+)"?\s', config_content)
        if access_log:
            config_info["access_log"] = access_log.group(1).strip()
            
        return config_info
    
    def analyze_error_log(self, log_content: str) -> List[Dict[str, Any]]:
        """
        Analyse un fichier de log d'erreur Apache et extrait les erreurs significatives.
        
        Args:
            log_content: Contenu du fichier de log
            
        Returns:
            Liste d'erreurs avec informations associées
        """
        errors = []
        lines = log_content.split('\n')
        
        # Parcourir les lignes du log (en se concentrant sur les plus récentes)
        for line in lines[-1000:]:  # Limiter aux 1000 dernières lignes
            line = line.strip()
            if not line:
                continue
                
            # Rechercher les motifs d'erreur
            error_type = None
            for err_type, pattern in self.error_patterns.items():
                if re.search(pattern, line, re.IGNORECASE):
                    error_type = err_type
                    break
                    
            # Si c'est une erreur connue, l'ajouter à la liste
            if error_type or "[error]" in line.lower():
                # Essayer d'extraire la date
                date_match = re.search(r'^\[(.*?)\]', line)
                date = date_match.group(1) if date_match else None
                
                errors.append({
                    "type": error_type or "other",
                    "date": date,
                    "message": line,
                    "context": {"line": line}
                })
                
        # Trier par date (les plus récentes d'abord)
        errors.sort(key=lambda x: x["date"] if x["date"] else "", reverse=True)
        
        return errors
    
    def suggest_apache_fixes(self, problem_type: str, context_data: Dict[str, Any]) -> str:
        """
        Suggère des solutions pour un type de problème Apache spécifique.
        
        Args:
            problem_type: Type de problème (ssl, permission, syntax, etc.)
            context_data: Données contextuelles sur le problème
            
        Returns:
            Suggestions formatées
        """
        # Construire le prompt pour les suggestions
        prompt = f"""
Génère des suggestions pour résoudre un problème Apache de type '{problem_type}'.

Contexte du problème :
{context_data}

Propose 3 commandes précises (en mode root, sans sudo) pour diagnostiquer et résoudre ce problème.
Pour chaque commande, explique son objectif et ce qu'elle permet de vérifier ou corriger.
"""
        
        try:
            response = self.ollama.generate(
                prompt=prompt,
                temperature=0.3
            )
            return response
        except Exception as e:
            logger.error(f"Erreur lors de la génération de suggestions Apache: {e}")
            return f"Erreur lors de la génération de suggestions: {e}"
    
    def check_ssl_config(self, ssl_config: str) -> Dict[str, Any]:
        """
        Vérifie une configuration SSL d'Apache.
        
        Args:
            ssl_config: Contenu de la configuration SSL
            
        Returns:
            Résultat de l'analyse avec problèmes potentiels
        """
        result = {
            "valid": True,
            "issues": [],
            "cert_file": None,
            "key_file": None,
            "chain_file": None,
            "protocols": []
        }
        
        # Extraire les fichiers de certificat et clé
        cert_match = re.search(r'SSLCertificateFile\s+"?([^"\s]+)"?', ssl_config)
        if cert_match:
            result["cert_file"] = cert_match.group(1).strip()
        else:
            result["valid"] = False
            result["issues"].append("SSLCertificateFile manquant")
            
        key_match = re.search(r'SSLCertificateKeyFile\s+"?([^"\s]+)"?', ssl_config)
        if key_match:
            result["key_file"] = key_match.group(1).strip()
        else:
            result["valid"] = False
            result["issues"].append("SSLCertificateKeyFile manquant")
            
        # Vérifier le fichier de chaîne (optionnel)
        chain_match = re.search(r'SSLCertificateChainFile\s+"?([^"\s]+)"?', ssl_config)
        if chain_match:
            result["chain_file"] = chain_match.group(1).strip()
            
        # Vérifier les protocoles
        protocols_match = re.search(r'SSLProtocol\s+(.+)', ssl_config)
        if protocols_match:
            protocols = protocols_match.group(1).strip()
            result["protocols"] = protocols.split()
            
            # Vérifier si des protocoles obsolètes sont utilisés
            obsolete_protocols = ["SSLv2", "SSLv3", "TLSv1", "TLSv1.1"]
            for protocol in obsolete_protocols:
                if protocol in protocols and "-" + protocol not in protocols:
                    result["issues"].append(f"Protocole obsolète activé: {protocol}")
        
        return result