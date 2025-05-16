"""
Module d'assistance pour Elasticsearch.
Fournit des fonctionnalités spécifiques pour l'analyse et la résolution des problèmes Elasticsearch.
"""

import logging
import re
import json
from typing import Dict, Any, List, Optional, Tuple

from ..ollama_client import OllamaClient
from ..context_manager import ContextManager

logger = logging.getLogger(__name__)

class ElasticsearchHelper:
    def __init__(self, ollama: OllamaClient, context: ContextManager):
        self.ollama = ollama
        self.context = context
        
        # Chemins courants des fichiers Elasticsearch
        self.es_paths = {
            "conf": "/etc/elasticsearch/elasticsearch.yml",
            "jvm_conf": "/etc/elasticsearch/jvm.options",
            "logs": "/var/log/elasticsearch/",
            "data": "/var/lib/elasticsearch/",
            "service": "elasticsearch"
        }
        
        # Patterns d'erreurs courants
        self.error_patterns = {
            "memory": r'(OutOfMemoryError|GC overhead|memory exhausted|cannot allocate memory)',
            "disk": r'(disk|space|low|watermark|flood|read-only|disk full)',
            "connection": r'(connect|connection|transport|discovery|failed to connect|network)',
            "cluster": r'(cluster|quorum|split-brain|master|join)',
            "shard": r'(shard|replica|allocation|index|failed|recovery)',
            "mapping": r'(mapping|field|index|schema|type)'
        }
        
    def analyze_config(self, config_content: str) -> Dict[str, Any]:
        """
        Analyse un fichier de configuration Elasticsearch et retourne des informations clés.
        
        Args:
            config_content: Contenu du fichier de configuration
            
        Returns:
            Dictionnaire avec les informations clés
        """
        config_info = {
            "cluster_name": None,
            "node_name": None,
            "network_host": None,
            "http_port": 9200,  # Valeur par défaut
            "transport_port": 9300,  # Valeur par défaut
            "data_path": None,
            "logs_path": None,
            "discovery": {},
            "bootstrap": {},
            "gateway": {},
            "action": {},
            "node_roles": []
        }
        
        # Analyser ligne par ligne
        lines = config_content.split('\n')
        current_section = None
        section_data = {}
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Identifier les sections (paramètres avec indentation)
            if ":" in line and not line.startswith(" ") and not line.startswith("\t"):
                # Nouvelle section principale
                parts = line.split(":", 1)
                key = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else None
                
                # Stocker les valeurs principales
                if key == "cluster.name":
                    config_info["cluster_name"] = value
                elif key == "node.name":
                    config_info["node_name"] = value
                elif key == "network.host":
                    config_info["network_host"] = value
                elif key == "http.port":
                    try:
                        config_info["http_port"] = int(value)
                    except (ValueError, TypeError):
                        pass
                elif key == "transport.port":
                    try:
                        config_info["transport_port"] = int(value)
                    except (ValueError, TypeError):
                        pass
                elif key == "path.data":
                    config_info["data_path"] = value
                elif key == "path.logs":
                    config_info["logs_path"] = value
                elif key == "node.roles":
                    if value and value.startswith("[") and value.endswith("]"):
                        roles = value[1:-1].split(",")
                        config_info["node_roles"] = [r.strip() for r in roles]
                    elif value:
                        config_info["node_roles"] = [value]
                
                # Grouper par préfixe pour les sections complexes
                if key.startswith("discovery."):
                    config_info["discovery"][key[10:]] = value
                elif key.startswith("bootstrap."):
                    config_info["bootstrap"][key[10:]] = value
                elif key.startswith("gateway."):
                    config_info["gateway"][key[8:]] = value
                elif key.startswith("action."):
                    config_info["action"][key[7:]] = value
                
        return config_info
    
    def analyze_jvm_options(self, jvm_content: str) -> Dict[str, Any]:
        """
        Analyse les options JVM d'Elasticsearch.
        
        Args:
            jvm_content: Contenu du fichier jvm.options
            
        Returns:
            Dictionnaire avec les paramètres JVM
        """
        jvm_info = {
            "heap_min": None,
            "heap_max": None,
            "gc_options": [],
            "gc_logs": False,
            "dump_path": None,
            "other_options": []
        }
        
        # Analyser ligne par ligne
        lines = jvm_content.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            # Analyser les options spécifiques
            if line.startswith("-Xms"):
                jvm_info["heap_min"] = line[4:]
            elif line.startswith("-Xmx"):
                jvm_info["heap_max"] = line[4:]
            elif "gc" in line.lower():
                jvm_info["gc_options"].append(line)
            elif "GCLog" in line or "gc.log" in line:
                jvm_info["gc_logs"] = True
            elif "dump" in line.lower() and "path" in line.lower():
                # Extraire le chemin du dump
                path_match = re.search(r'=(.*)', line)
                if path_match:
                    jvm_info["dump_path"] = path_match.group(1).strip()
            else:
                jvm_info["other_options"].append(line)
        
        return jvm_info
    
    def parse_cluster_health(self, health_output: str) -> Dict[str, Any]:
        """
        Analyse la sortie de la commande cluster health d'Elasticsearch.
        
        Args:
            health_output: Réponse JSON de l'API _cluster/health
            
        Returns:
            État de santé du cluster formaté
        """
        try:
            # Essayer de parser comme JSON
            health_data = json.loads(health_output)
            
            # Extraire les informations pertinentes
            health_info = {
                "status": health_data.get("status"),
                "cluster_name": health_data.get("cluster_name"),
                "number_of_nodes": health_data.get("number_of_nodes"),
                "active_shards": health_data.get("active_shards"),
                "relocating_shards": health_data.get("relocating_shards"),
                "initializing_shards": health_data.get("initializing_shards"),
                "unassigned_shards": health_data.get("unassigned_shards"),
                "delayed_unassigned_shards": health_data.get("delayed_unassigned_shards"),
                "active_shards_percent": health_data.get("active_shards_percent_as_number"),
                "timed_out": health_data.get("timed_out")
            }
            
            # Calcul du statut global
            if health_info["status"] == "green":
                health_info["health_summary"] = "Excellent - Toutes les shards sont allouées"
            elif health_info["status"] == "yellow":
                health_info["health_summary"] = "Attention - Certaines shards de réplica ne sont pas allouées"
            elif health_info["status"] == "red":
                health_info["health_summary"] = "Critique - Certaines shards primaires ne sont pas allouées"
            else:
                health_info["health_summary"] = "Inconnu"
            
            return health_info
            
        except json.JSONDecodeError:
            # Format alternatif (non-JSON)
            health_info = {}
            
            # Essayer d'extraire les informations clés
            status_match = re.search(r'status\s*[=:]\s*(\w+)', health_output)
            if status_match:
                health_info["status"] = status_match.group(1)
                
            nodes_match = re.search(r'nodes\s*[=:]\s*(\d+)', health_output) or \
                       re.search(r'number_of_nodes\s*[=:]\s*(\d+)', health_output)
            if nodes_match:
                health_info["number_of_nodes"] = int(nodes_match.group(1))
                
            # Détecter d'autres métriques pertinentes
            for metric in ["active_shards", "relocating_shards", "initializing_shards", 
                           "unassigned_shards", "delayed_unassigned_shards"]:
                metric_match = re.search(rf'{metric}\s*[=:]\s*(\d+)', health_output)
                if metric_match:
                    health_info[metric] = int(metric_match.group(1))
            
            return health_info
    
    def analyze_error_log(self, log_content: str) -> List[Dict[str, Any]]:
        """
        Analyse un fichier de log d'erreur Elasticsearch et extrait les erreurs significatives.
        
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
                
            # Rechercher les erreurs
            is_error = "ERROR" in line or "WARN" in line
            
            if is_error:
                error_type = None
                severity = "ERROR" if "ERROR" in line else "WARN"
                
                # Identifier le type d'erreur
                for err_type, pattern in self.error_patterns.items():
                    if re.search(pattern, line, re.IGNORECASE):
                        error_type = err_type
                        break
                
                # Extraire la date
                date_match = re.search(r'^\[(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}[,\.]\d+)', line)
                date = date_match.group(1) if date_match else None
                
                # Extraire le contexte
                context_match = re.search(r'\[([^\]]+)\]\s*\[([^\]]+)\]\s*\[([^\]]+)\]', line)
                context = {}
                
                if context_match:
                    context["timestamp"] = context_match.group(1)
                    context["log_level"] = context_match.group(2)
                    context["component"] = context_match.group(3)
                
                errors.append({
                    "type": error_type or "other",
                    "date": date,
                    "message": line,
                    "severity": severity,
                    "context": context
                })
        
        # Trier par date (les plus récentes d'abord)
        errors.sort(key=lambda x: x["date"] if x["date"] else "", reverse=True)
        
        return errors
    
    def suggest_es_optimizations(self, server_info: Dict[str, Any]) -> str:
        """
        Suggère des optimisations Elasticsearch basées sur les informations du serveur.
        
        Args:
            server_info: Informations sur le serveur Elasticsearch
            
        Returns:
            Suggestions d'optimisation formatées
        """
        # Construire le prompt pour les suggestions
        prompt = f"""
Suggère des optimisations pour un serveur Elasticsearch basées sur ces informations :

```
{server_info}
```

Propose 3-5 optimisations spécifiques avec :
1. Le paramètre à modifier
2. La valeur recommandée
3. L'impact attendu
4. La commande précise pour implémenter le changement (en mode root, sans sudo)

Concentre-toi sur les optimisations qui auront le plus d'impact sur les performances et la stabilité.
"""
        
        try:
            response = self.ollama.generate(
                prompt=prompt,
                temperature=0.3
            )
            return response
        except Exception as e:
            logger.error(f"Erreur lors de la génération de suggestions Elasticsearch: {e}")
            return f"Erreur lors de la génération de suggestions: {e}"