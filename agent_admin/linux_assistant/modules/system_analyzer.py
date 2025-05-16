"""
Module d'analyse des systèmes Linux.
Fournit des fonctionnalités pour analyser les configurations système et diagnostiquer les problèmes.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple

from ..ollama_client import OllamaClient
from ..context_manager import ContextManager

logger = logging.getLogger(__name__)

class SystemAnalyzer:
    def __init__(self, ollama: OllamaClient, context: ContextManager):
        self.ollama = ollama
        self.context = context
        
    def analyze_disk_usage(self, df_output: str) -> Dict[str, Any]:
        """
        Analyse la sortie de la commande df pour détecter les problèmes d'espace disque.
        
        Args:
            df_output: Sortie de la commande df -h
            
        Returns:
            Analyse de l'utilisation du disque
        """
        result = {
            "filesystems": [],
            "critical": [],
            "warning": []
        }
        
        # Ignorer la première ligne (en-tête)
        lines = df_output.strip().split('\n')[1:]
        
        for line in lines:
            parts = line.split()
            if len(parts) < 5:
                continue
                
            # Format typique: Filesystem Size Used Avail Use% Mounted on
            filesystem = parts[0]
            size = parts[1]
            used = parts[2]
            avail = parts[3]
            
            # Le pourcentage d'utilisation peut être dans différentes colonnes selon le format
            use_percent = None
            for part in parts[4:]:
                if '%' in part:
                    use_percent = part
                    break
            
            if not use_percent:
                continue
                
            # Extraire le pourcentage numérique
            percent_value = int(use_percent.strip('%'))
            
            # Trouver le point de montage (dernière partie)
            mount_point = parts[-1]
            
            # Stocker les informations
            fs_info = {
                "filesystem": filesystem,
                "size": size,
                "used": used,
                "available": avail,
                "use_percent": percent_value,
                "mount_point": mount_point
            }
            
            result["filesystems"].append(fs_info)
            
            # Détecter les problèmes
            if percent_value >= 90:
                result["critical"].append(fs_info)
            elif percent_value >= 80:
                result["warning"].append(fs_info)
        
        return result
    
    def analyze_memory_usage(self, free_output: str) -> Dict[str, Any]:
        """
        Analyse la sortie de la commande free pour détecter les problèmes de mémoire.
        
        Args:
            free_output: Sortie de la commande free -m
            
        Returns:
            Analyse de l'utilisation de la mémoire
        """
        result = {
            "total": 0,
            "used": 0,
            "free": 0,
            "shared": 0,
            "buffers": 0,
            "cache": 0,
            "available": 0,
            "swap_total": 0,
            "swap_used": 0,
            "swap_free": 0,
            "use_percent": 0,
            "swap_use_percent": 0
        }
        
        # Parser la sortie
        lines = free_output.strip().split('\n')
        
        for line in lines:
            if line.startswith('Mem:'):
                parts = line.split()
                if len(parts) >= 7:  # Format plus récent
                    result["total"] = int(parts[1])
                    result["used"] = int(parts[2])
                    result["free"] = int(parts[3])
                    result["shared"] = int(parts[4])
                    result["buffers"] = int(parts[5]) if len(parts) > 5 else 0
                    result["cache"] = int(parts[6]) if len(parts) > 6 else 0
                    result["available"] = int(parts[7]) if len(parts) > 7 else 0
                    
            elif line.startswith('Swap:'):
                parts = line.split()
                if len(parts) >= 4:
                    result["swap_total"] = int(parts[1])
                    result["swap_used"] = int(parts[2])
                    result["swap_free"] = int(parts[3])
        
        # Calculer les pourcentages
        if result["total"] > 0:
            # Utilisation réelle (en tenant compte des buffers/cache)
            real_used = result["used"] - (result["buffers"] + result["cache"])
            result["use_percent"] = round(real_used / result["total"] * 100, 2)
            
        if result["swap_total"] > 0:
            result["swap_use_percent"] = round(result["swap_used"] / result["swap_total"] * 100, 2)
        
        return result
    
    def analyze_load_average(self, load_output: str, cpu_count: int) -> Dict[str, Any]:
        """
        Analyse la charge CPU (load average).
        
        Args:
            load_output: Sortie de la commande uptime ou cat /proc/loadavg
            cpu_count: Nombre de CPUs
            
        Returns:
            Analyse de la charge CPU
        """
        result = {
            "load_1min": 0,
            "load_5min": 0,
            "load_15min": 0,
            "per_cpu_1min": 0,
            "per_cpu_5min": 0,
            "per_cpu_15min": 0,
            "status": "normal"
        }
        
        # Extraire les valeurs de charge
        load_match = re.search(r'load average:\s*([0-9.]+),\s*([0-9.]+),\s*([0-9.]+)', load_output) or \
                   re.search(r'([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)', load_output)
        
        if load_match:
            result["load_1min"] = float(load_match.group(1))
            result["load_5min"] = float(load_match.group(2))
            result["load_15min"] = float(load_match.group(3))
            
            # Calculer la charge par CPU
            if cpu_count > 0:
                result["per_cpu_1min"] = round(result["load_1min"] / cpu_count, 2)
                result["per_cpu_5min"] = round(result["load_5min"] / cpu_count, 2)
                result["per_cpu_15min"] = round(result["load_15min"] / cpu_count, 2)
                
                # Déterminer le statut
                if result["per_cpu_5min"] >= 1.5:
                    result["status"] = "critical"
                elif result["per_cpu_5min"] >= 1.0:
                    result["status"] = "warning"
                else:
                    result["status"] = "normal"
        
        return result
    
    def analyze_listening_ports(self, netstat_output: str) -> List[Dict[str, Any]]:
        """
        Analyse les ports en écoute sur le système.
        
        Args:
            netstat_output: Sortie de la commande netstat -tulpn ou ss -tulpn
            
        Returns:
            Liste des services en écoute
        """
        listening_ports = []
        
        # Format différent entre netstat et ss
        is_ss_format = "State" in netstat_output
        
        lines = netstat_output.strip().split('\n')
        for line in lines:
            # Sauter les en-têtes
            if line.startswith("Proto") or line.startswith("Netid") or line.startswith("State"):
                continue
                
            parts = line.split()
            if len(parts) < 5:
                continue
                
            if is_ss_format:  # Format ss
                proto_index = 0
                local_addr_index = 4
                process_index = 6  # Peut varier
            else:  # Format netstat
                proto_index = 0
                local_addr_index = 3
                process_index = 6  # Peut varier
            
            proto = parts[proto_index]
            local_addr = parts[local_addr_index]
            
            # Extraire le port de l'adresse locale
            port_match = re.search(r':([0-9]+)$', local_addr)
            if not port_match:
                continue
                
            port = int(port_match.group(1))
            
            # Extraire le processus s'il est disponible
            process = None
            pid = None
            
            # Rechercher dans les dernières colonnes
            for i in range(process_index, len(parts)):
                process_match = re.search(r'([0-9]+)/(.+)', parts[i])
                if process_match:
                    pid = int(process_match.group(1))
                    process = process_match.group(2)
                    break
            
            listening_ports.append({
                "protocol": proto,
                "port": port,
                "local_address": local_addr,
                "process": process,
                "pid": pid
            })
        
        return listening_ports
    
    def analyze_selinux_status(self, sestatus_output: str) -> Dict[str, Any]:
        """
        Analyse l'état de SELinux.
        
        Args:
            sestatus_output: Sortie de la commande sestatus
            
        Returns:
            État de SELinux
        """
        result = {
            "enabled": False,
            "mode": None,
            "policy": None,
            "status": None
        }
        
        # Analyser ligne par ligne
        lines = sestatus_output.strip().split('\n')
        for line in lines:
            line = line.strip()
            
            # Vérifier l'état de SELinux
            if "SELinux status" in line:
                status = line.split(':')[1].strip()
                result["status"] = status
                result["enabled"] = status.lower() == "enabled"
                
            # Vérifier le mode (enforcing/permissive/disabled)
            elif "Current mode" in line:
                result["mode"] = line.split(':')[1].strip().lower()
                
            # Vérifier la politique
            elif "Policy from config file" in line or "Policy type" in line:
                result["policy"] = line.split(':')[1].strip()
        
        return result
    
    def analyze_firewall_status(self, firewall_output: str) -> Dict[str, Any]:
        """
        Analyse l'état du pare-feu (firewalld, iptables).
        
        Args:
            firewall_output: Sortie des commandes liées au pare-feu
            
        Returns:
            État du pare-feu
        """
        result = {
            "enabled": False,
            "type": None,
            "zones": [],
            "services": [],
            "ports": [],
            "status": None
        }
        
        # Détecter le type de pare-feu
        if "firewalld" in firewall_output:
            result["type"] = "firewalld"
            
            # Vérifier si firewalld est actif
            if "running" in firewall_output or "active" in firewall_output:
                result["enabled"] = True
                result["status"] = "active"
            
            # Extraire les zones
            zone_matches = re.finditer(r'\* ([a-z0-9_]+)', firewall_output) or \
                         re.finditer(r'zone: ([a-z0-9_]+)', firewall_output)
            for match in zone_matches:
                result["zones"].append(match.group(1))
                
            # Extraire les services
            service_matches = re.finditer(r'services: (.+)$', firewall_output)
            for match in service_matches:
                services = match.group(1).split()
                result["services"].extend(services)
                
            # Extraire les ports
            port_matches = re.finditer(r'ports: (.+)$', firewall_output)
            for match in port_matches:
                ports = match.group(1).split()
                result["ports"].extend(ports)
                
        elif "iptables" in firewall_output:
            result["type"] = "iptables"
            
            # Vérifier si des règles sont définies
            if "Chain" in firewall_output and not "0 references" in firewall_output:
                result["enabled"] = True
                result["status"] = "configured"
                
                # Compter les ACCEPT/DROP/REJECT
                accept_count = len(re.findall(r'ACCEPT', firewall_output))
                drop_count = len(re.findall(r'DROP', firewall_output))
                reject_count = len(re.findall(r'REJECT', firewall_output))
                
                result["rules_summary"] = {
                    "accept": accept_count,
                    "drop": drop_count,
                    "reject": reject_count
                }
        
        return result
    
    def suggest_system_fixes(self, system_info: Dict[str, Any]) -> str:
        """
        Suggère des solutions pour les problèmes système détectés.
        
        Args:
            system_info: Informations système collectées
            
        Returns:
            Suggestions formatées
        """
        # Construire le prompt pour les suggestions
        prompt = f"""
Suggère des solutions pour les problèmes système Linux suivants :

```
{system_info}
```

Propose 3-5 actions concrètes pour résoudre les problèmes détectés, avec :
1. Description du problème
2. Commandes précises pour le diagnostic approfondi (en mode root)
3. Commandes de résolution (en mode root)
4. Recommandations pour éviter ce problème à l'avenir

Concentre-toi sur les problèmes les plus critiques en priorité.
"""
        
        try:
            response = self.ollama.generate(
                prompt=prompt,
                temperature=0.3
            )
            return response
        except Exception as e:
            logger.error(f"Erreur lors de la génération de suggestions système: {e}")
            return f"Erreur lors de la génération de suggestions: {e}"