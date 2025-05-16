"""
Module d'assistance pour les serveurs MySQL/MariaDB.
Fournit des fonctionnalités spécifiques pour l'analyse et la résolution des problèmes MySQL.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple

from ..ollama_client import OllamaClient
from ..context_manager import ContextManager

logger = logging.getLogger(__name__)

class MySQLHelper:
    def __init__(self, ollama: OllamaClient, context: ContextManager):
        self.ollama = ollama
        self.context = context
        
        # Chemins courants des fichiers MySQL
        self.mysql_paths = {
            "rhel": {
                "conf": "/etc/my.cnf",
                "conf_d": "/etc/my.cnf.d/",
                "logs": "/var/log/mysql/",
                "service": "mysqld"
            },
            "mariadb_rhel": {
                "conf": "/etc/my.cnf",
                "conf_d": "/etc/my.cnf.d/",
                "logs": "/var/log/mariadb/",
                "service": "mariadb"
            },
            "debian": {
                "conf": "/etc/mysql/my.cnf",
                "conf_d": "/etc/mysql/conf.d/",
                "logs": "/var/log/mysql/",
                "service": "mysql"
            },
            "mariadb_debian": {
                "conf": "/etc/mysql/mariadb.cnf",
                "conf_d": "/etc/mysql/mariadb.conf.d/",
                "logs": "/var/log/mysql/",
                "service": "mariadb"
            }
        }
        
        # Patterns d'erreurs courants
        self.error_patterns = {
            "connection": r'(Can\'t connect|Connection refused|Access denied|authentication|password)',
            "syntax": r'(syntax error|unexpected|token|unknown directive|SQL syntax)',
            "timeout": r'(timeout|timed out|connection closed|lost connection)',
            "disk": r'(disk full|no space left|file size exceeds|table is full)',
            "memory": r'(out of memory|memory exhausted|cannot allocate memory)',
            "lock": r'(deadlock|lock wait timeout|lock contention)'
        }
        
    def analyze_config(self, config_content: str) -> Dict[str, Any]:
        """
        Analyse un fichier de configuration MySQL et retourne des informations clés.
        
        Args:
            config_content: Contenu du fichier de configuration
            
        Returns:
            Dictionnaire avec les informations clés
        """
        config_info = {
            "port": 3306,  # Valeur par défaut
            "max_connections": 151,  # Valeur par défaut
            "bind_address": None,
            "datadir": None,
            "slow_query_log": False,
            "log_error": None,
            "innodb_buffer_pool_size": None,
            "max_allowed_packet": None,
            "sections": {}
        }
        
        # Tracker la section courante
        current_section = "global"
        
        # Analyser ligne par ligne
        lines = config_content.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            # Détection des sections
            section_match = re.match(r'\[(.+?)\]', line)
            if section_match:
                current_section = section_match.group(1)
                config_info["sections"][current_section] = {}
                continue
                
            # Extraction des paramètres
            param_match = re.match(r'([\w_-]+)\s*=\s*(.+)', line)
            if param_match:
                param, value = param_match.groups()
                
                # Stocker dans la section appropriée
                if current_section in config_info["sections"]:
                    config_info["sections"][current_section][param] = value
                
                # Extraire les paramètres spécifiques d'intérêt
                if param == "port":
                    try:
                        config_info["port"] = int(value)
                    except ValueError:
                        pass
                        
                elif param == "max_connections":
                    try:
                        config_info["max_connections"] = int(value)
                    except ValueError:
                        pass
                        
                elif param == "bind-address" or param == "bind_address":
                    config_info["bind_address"] = value
                    
                elif param == "datadir":
                    config_info["datadir"] = value
                    
                elif param == "slow_query_log" and value.lower() in ("1", "on", "true"):
                    config_info["slow_query_log"] = True
                    
                elif param == "log_error":
                    config_info["log_error"] = value
                    
                elif param == "innodb_buffer_pool_size":
                    config_info["innodb_buffer_pool_size"] = value
                    
                elif param == "max_allowed_packet":
                    config_info["max_allowed_packet"] = value
        
        return config_info
    
    def parse_status_output(self, status_output: str) -> Dict[str, Any]:
        """
        Analyse la sortie de la commande SHOW STATUS.
        
        Args:
            status_output: Sortie de la commande SHOW STATUS
            
        Returns:
            Statistiques clés de MySQL
        """
        stats = {}
        lines = status_output.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or '|' not in line:
                continue
                
            # Format typique: | Variable_name | Value |
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 4:  # Au moins 4 parties avec les séparateurs
                key = parts[1].strip()
                value = parts[2].strip()
                
                if key:
                    # Convertir en nombre si possible
                    try:
                        value = int(value)
                    except ValueError:
                        try:
                            value = float(value)
                        except ValueError:
                            pass
                    
                    stats[key] = value
        
        # Calculer des métriques dérivées
        if "Questions" in stats and "Uptime" in stats and stats["Uptime"] > 0:
            stats["QPS"] = stats["Questions"] / stats["Uptime"]
            
        if "Threads_connected" in stats and "max_connections" in stats and stats["max_connections"] > 0:
            stats["connection_usage"] = stats["Threads_connected"] / stats["max_connections"] * 100
        
        return stats
    
    def analyze_slow_queries(self, slow_log_content: str) -> List[Dict[str, Any]]:
        """
        Analyse un fichier de slow query log MySQL.
        
        Args:
            slow_log_content: Contenu du fichier de slow query log
            
        Returns:
            Liste des requêtes lentes avec statistiques
        """
        slow_queries = []
        current_query = None
        query_pattern = r'# Time: (\d{6}\s+\d{1,2}:\d{2}:\d{2}).*?\n# User@Host: (.+)\n# Query_time: (\d+\.\d+)\s+Lock_time: (\d+\.\d+)\s+Rows_sent: (\d+)\s+Rows_examined: (\d+)'
        
        matches = re.finditer(query_pattern, slow_log_content, re.DOTALL)
        
        for match in matches:
            time = match.group(1)
            user = match.group(2)
            query_time = float(match.group(3))
            lock_time = float(match.group(4))
            rows_sent = int(match.group(5))
            rows_examined = int(match.group(6))
            
            # Trouver le SQL après le bloc d'en-tête
            pos = match.end()
            next_match = re.search(r'# Time:', slow_log_content[pos:]) 
            
            if next_match:
                query_sql = slow_log_content[pos:pos+next_match.start()].strip()
            else:
                # Dernière requête du fichier
                query_sql = slow_log_content[pos:].strip()
            
            # Stocker la requête
            slow_queries.append({
                "time": time,
                "user": user,
                "query_time": query_time,
                "lock_time": lock_time,
                "rows_sent": rows_sent,
                "rows_examined": rows_examined,
                "sql": query_sql,
                "efficiency": rows_sent / rows_examined if rows_examined > 0 else 0
            })
        
        # Trier par temps de requête (le plus long d'abord)
        slow_queries.sort(key=lambda x: x["query_time"], reverse=True)
        
        return slow_queries
    
    def suggest_mysql_optimizations(self, server_info: Dict[str, Any]) -> str:
        """
        Suggère des optimisations MySQL basées sur les informations du serveur.
        
        Args:
            server_info: Informations sur le serveur MySQL
            
        Returns:
            Suggestions d'optimisation formatées
        """
        # Construire le prompt pour les suggestions
        prompt = f"""
Suggère des optimisations pour un serveur MySQL/MariaDB basées sur ces informations :

```
{server_info}
```

Propose 3-5 optimisations spécifiques avec :
1. Le paramètre à modifier
2. La valeur recommandée
3. L'impact attendu
4. La commande précise pour implémenter le changement (en mode root, sans sudo)

Concentre-toi sur les optimisations les plus importantes qui auront le plus d'impact sur les performances.
"""
        
        try:
            response = self.ollama.generate(
                prompt=prompt,
                temperature=0.3
            )
            return response
        except Exception as e:
            logger.error(f"Erreur lors de la génération de suggestions MySQL: {e}")
            return f"Erreur lors de la génération de suggestions: {e}"
    
    def analyze_error_log(self, log_content: str) -> List[Dict[str, Any]]:
        """
        Analyse un fichier de log d'erreur MySQL et extrait les erreurs significatives.
        
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
                
            # Rechercher les motifs d'erreur ou le mot "error"
            if "error" in line.lower() or "warning" in line.lower():
                error_type = None
                
                # Identifier le type d'erreur
                for err_type, pattern in self.error_patterns.items():
                    if re.search(pattern, line, re.IGNORECASE):
                        error_type = err_type
                        break
                
                # Extraire la date si disponible
                date_match = re.search(r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', line)
                date = date_match.group(1) if date_match else None
                
                errors.append({
                    "type": error_type or "other",
                    "date": date,
                    "message": line,
                    "severity": "error" if "error" in line.lower() else "warning"
                })
        
        # Trier par date (les plus récentes d'abord)
        errors.sort(key=lambda x: x["date"] if x["date"] else "", reverse=True)
        
        return errors