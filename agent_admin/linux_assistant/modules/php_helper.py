"""
Module d'assistance pour PHP.
Fournit des fonctionnalités spécifiques pour l'analyse et la résolution des problèmes PHP.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple

from ..ollama_client import OllamaClient
from ..context_manager import ContextManager

logger = logging.getLogger(__name__)

class PHPHelper:
    def __init__(self, ollama: OllamaClient, context: ContextManager):
        self.ollama = ollama
        self.context = context
        
        # Chemins courants des fichiers PHP
        self.php_paths = {
            "rhel": {
                "conf": "/etc/php.ini",
                "conf_d": "/etc/php.d/",
                "logs": "/var/log/php-fpm/",
                "service": "php-fpm"
            },
            "debian": {
                "conf": "/etc/php/7.4/fpm/php.ini",  # Peut varier selon la version
                "conf_d": "/etc/php/7.4/fpm/conf.d/",
                "logs": "/var/log/php7.4-fpm.log",
                "service": "php7.4-fpm"
            }
        }
        
        # Patterns d'erreurs courants
        self.error_patterns = {
            "memory": r'(Allowed memory size of|out of memory|memory exhausted|cannot allocate memory)',
            "timeout": r'(maximum execution time|timed out|time limit|deadlock)',
            "upload": r'(upload|filesize|max_upload|post_max_size)',
            "permission": r'(permission denied|failed to open|cannot access|unable to open)',
            "syntax": r'(syntax error|parse error|unexpected|token)',
            "extension": r'(extension|module).*?(not found|missing)',
            "database": r'(database|mysql|mysqli|pdo).*?(connect|error|failed)'
        }
        
    def analyze_config(self, config_content: str) -> Dict[str, Any]:
        """
        Analyse un fichier de configuration PHP et retourne des informations clés.
        
        Args:
            config_content: Contenu du fichier de configuration
            
        Returns:
            Dictionnaire avec les informations clés
        """
        config_info = {
            "memory_limit": None,
            "max_execution_time": None,
            "post_max_size": None,
            "upload_max_filesize": None,
            "display_errors": None,
            "error_reporting": None,
            "log_errors": None,
            "error_log": None,
            "extensions": [],
            "opcache_enabled": False
        }
        
        # Analyser ligne par ligne
        lines = config_content.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith(';'):
                continue
                
            # Extraction des paramètres
            param_match = re.match(r'([\w\._-]+)\s*=\s*(.+)', line)
            if param_match:
                param, value = param_match.groups()
                value = value.strip('"\'')
                
                # Extraire les paramètres spécifiques d'intérêt
                if param == "memory_limit":
                    config_info["memory_limit"] = value
                    
                elif param == "max_execution_time":
                    try:
                        config_info["max_execution_time"] = int(value)
                    except ValueError:
                        config_info["max_execution_time"] = value
                        
                elif param == "post_max_size":
                    config_info["post_max_size"] = value
                    
                elif param == "upload_max_filesize":
                    config_info["upload_max_filesize"] = value
                    
                elif param == "display_errors":
                    config_info["display_errors"] = value.lower() in ("on", "true", "1")
                    
                elif param == "error_reporting":
                    config_info["error_reporting"] = value
                    
                elif param == "log_errors":
                    config_info["log_errors"] = value.lower() in ("on", "true", "1")
                    
                elif param == "error_log":
                    config_info["error_log"] = value
                    
                elif param == "opcache.enable":
                    config_info["opcache_enabled"] = value.lower() in ("on", "true", "1")
            
            # Extensions
            extension_match = re.match(r'extension\s*=\s*(.+)', line)
            if extension_match:
                ext = extension_match.group(1).strip('"\'')
                config_info["extensions"].append(ext)
        
        return config_info
    
    def analyze_error_log(self, log_content: str) -> List[Dict[str, Any]]:
        """
        Analyse un fichier de log d'erreur PHP et extrait les erreurs significatives.
        
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
                
            # Rechercher les motifs d'erreur ou les niveaux d'erreur PHP
            error_levels = ["Fatal error", "Parse error", "Warning", "Notice", "Deprecated"]
            is_error = False
            
            for level in error_levels:
                if level.lower() in line.lower():
                    is_error = True
                    break
            
            if is_error or "error" in line.lower():
                error_type = None
                severity = "error"  # Par défaut
                
                # Déterminer la sévérité
                if "fatal" in line.lower() or "parse error" in line.lower():
                    severity = "critical"
                elif "warning" in line.lower():
                    severity = "warning"
                elif "notice" in line.lower() or "deprecated" in line.lower():
                    severity = "notice"
                
                # Identifier le type d'erreur
                for err_type, pattern in self.error_patterns.items():
                    if re.search(pattern, line, re.IGNORECASE):
                        error_type = err_type
                        break
                
                # Extraire la date si disponible
                date_match = re.search(r'^\[(\d{2}-\w{3}-\d{4}\s+\d{2}:\d{2}:\d{2})\]', line)
                date = date_match.group(1) if date_match else None
                
                # Extraire le fichier et la ligne si disponibles
                file_line_match = re.search(r'in\s+(.+?)\s+on\s+line\s+(\d+)', line)
                file_info = None
                line_number = None
                
                if file_line_match:
                    file_info = file_line_match.group(1)
                    line_number = int(file_line_match.group(2))
                
                errors.append({
                    "type": error_type or "other",
                    "date": date,
                    "message": line,
                    "severity": severity,
                    "file": file_info,
                    "line": line_number
                })
        
        # Trier par date (les plus récentes d'abord) et sévérité
        errors.sort(key=lambda x: (0 if x["date"] is None else 1, x["date"] if x["date"] else ""), reverse=True)
        
        return errors
    
    def suggest_php_fixes(self, problem_type: str, context_data: Dict[str, Any]) -> str:
        """
        Suggère des solutions pour un type de problème PHP spécifique.
        
        Args:
            problem_type: Type de problème (memory, timeout, syntax, etc.)
            context_data: Données contextuelles sur le problème
            
        Returns:
            Suggestions formatées
        """
        # Construire le prompt pour les suggestions
        prompt = f"""
Génère des suggestions pour résoudre un problème PHP de type '{problem_type}'.

Contexte du problème :
{context_data}

Propose 3 solutions précises pour résoudre ce problème, avec :
1. Description de la solution
2. Commandes à exécuter (en mode root, sans sudo)
3. Modifications à apporter aux fichiers de configuration si nécessaire

Assure-toi que tes suggestions sont spécifiques, concrètes et adaptées au contexte.
"""
        
        try:
            response = self.ollama.generate(
                prompt=prompt,
                temperature=0.3
            )
            return response
        except Exception as e:
            logger.error(f"Erreur lors de la génération de suggestions PHP: {e}")
            return f"Erreur lors de la génération de suggestions: {e}"
    
    def check_php_security(self, config_content: str) -> Dict[str, Any]:
        """
        Vérifie les paramètres de sécurité dans la configuration PHP.
        
        Args:
            config_content: Contenu de la configuration PHP
            
        Returns:
            Résultat de l'analyse avec problèmes potentiels
        """
        security_issues = []
        security_config = {}
        
        # Extraire les paramètres de sécurité
        security_params = {
            "display_errors": r'display_errors\s*=\s*([^\s;]+)',
            "expose_php": r'expose_php\s*=\s*([^\s;]+)',
            "allow_url_fopen": r'allow_url_fopen\s*=\s*([^\s;]+)',
            "allow_url_include": r'allow_url_include\s*=\s*([^\s;]+)',
            "open_basedir": r'open_basedir\s*=\s*([^;]+)',
            "disable_functions": r'disable_functions\s*=\s*([^;]+)',
            "session.use_strict_mode": r'session\.use_strict_mode\s*=\s*([^\s;]+)',
            "session.cookie_secure": r'session\.cookie_secure\s*=\s*([^\s;]+)',
            "session.cookie_httponly": r'session\.cookie_httponly\s*=\s*([^\s;]+)'
        }
        
        # Vérifier chaque paramètre
        for param, pattern in security_params.items():
            match = re.search(pattern, config_content, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                security_config[param] = value
                
                # Vérifier les paramètres problématiques
                if param == "display_errors" and value.lower() in ("on", "true", "1"):
                    security_issues.append("display_errors est activé (risque de divulgation d'informations)")
                    
                if param == "expose_php" and value.lower() in ("on", "true", "1"):
                    security_issues.append("expose_php est activé (divulgue la version de PHP dans les en-têtes)")
                    
                if param == "allow_url_fopen" and value.lower() in ("on", "true", "1"):
                    security_issues.append("allow_url_fopen est activé (peut poser des risques de sécurité)")
                    
                if param == "allow_url_include" and value.lower() in ("on", "true", "1"):
                    security_issues.append("allow_url_include est activé (risque critique d'inclusion distante)")
                    
                if param == "open_basedir" and not value:
                    security_issues.append("open_basedir n'est pas défini (restriction des accès aux fichiers recommandée)")
                    
                if param == "disable_functions" and not value:
                    security_issues.append("disable_functions n'est pas défini (aucune fonction dangereuse n'est désactivée)")
                    
                if param == "session.use_strict_mode" and value.lower() not in ("on", "true", "1"):
                    security_issues.append("session.use_strict_mode n'est pas activé (risque de fixation de session)")
                    
                if param == "session.cookie_secure" and value.lower() not in ("on", "true", "1"):
                    security_issues.append("session.cookie_secure n'est pas activé (les cookies ne sont pas limités à HTTPS)")
                    
                if param == "session.cookie_httponly" and value.lower() not in ("on", "true", "1"):
                    security_issues.append("session.cookie_httponly n'est pas activé (cookies accessibles via JavaScript)")
            else:
                # Paramètre manquant
                security_config[param] = "non configuré"
                
                # Vérifier les paramètres critiques manquants
                if param in ["open_basedir", "disable_functions", "session.use_strict_mode", 
                          "session.cookie_secure", "session.cookie_httponly"]:
                    security_issues.append(f"{param} n'est pas configuré (recommandé pour la sécurité)")
        
        return {
            "config": security_config,
            "issues": security_issues,
            "secure": len(security_issues) == 0
        }