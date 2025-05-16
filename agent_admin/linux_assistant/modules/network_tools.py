"""
Module d'outils réseau pour l'assistant Linux.
Fournit des fonctionnalités pour analyser et résoudre les problèmes réseau.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
import ipaddress

from ..ollama_client import OllamaClient
from ..context_manager import ContextManager

logger = logging.getLogger(__name__)

class NetworkTools:
    def __init__(self, ollama: OllamaClient, context: ContextManager):
        self.ollama = ollama
        self.context = context
        
    def parse_ifconfig_output(self, ifconfig_output: str) -> Dict[str, Dict[str, Any]]:
        """
        Analyse la sortie de la commande ifconfig.
        
        Args:
            ifconfig_output: Sortie de la commande ifconfig
            
        Returns:
            Dictionnaire des interfaces réseau et leurs propriétés
        """
        interfaces = {}
        current_interface = None
        
        lines = ifconfig_output.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Nouvelle interface
            if not line.startswith(' ') and not line.startswith('\t'):
                interface_match = re.match(r'^([\w\d]+):', line)
                if interface_match:
                    current_interface = interface_match.group(1)
                    interfaces[current_interface] = {
                        "name": current_interface,
                        "ipv4": None,
                        "ipv6": [],
                        "mac": None,
                        "netmask": None,
                        "broadcast": None,
                        "flags": None,
                        "mtu": None,
                        "status": "unknown",
                        "rx_packets": 0,
                        "tx_packets": 0,
                        "rx_bytes": 0,
                        "tx_bytes": 0,
                        "errors": 0
                    }
                    
                    # Extraire les flags
                    flags_match = re.search(r'flags=([0-9a-fx]+)\s*<([^>]+)>', line)
                    if flags_match:
                        interfaces[current_interface]["flags"] = flags_match.group(2)
                        
                        # Déterminer le statut
                        flags = flags_match.group(2).lower()
                        if "up" in flags and not "loopback" in flags:
                            interfaces[current_interface]["status"] = "up"
                        elif "up" in flags and "loopback" in flags:
                            interfaces[current_interface]["status"] = "loopback"
                        else:
                            interfaces[current_interface]["status"] = "down"
                            
            # Informations complémentaires de l'interface courante
            elif current_interface:
                # IPv4
                ipv4_match = re.search(r'inet (?:addr:)?([\d\.]+)', line)
                if ipv4_match:
                    interfaces[current_interface]["ipv4"] = ipv4_match.group(1)
                
                # Netmask
                netmask_match = re.search(r'(?:netmask|Mask:)\s*([\d\.]+)', line)
                if netmask_match:
                    interfaces[current_interface]["netmask"] = netmask_match.group(1)
                    
                # Broadcast
                broadcast_match = re.search(r'(?:broadcast|Bcast:)\s*([\d\.]+)', line)
                if broadcast_match:
                    interfaces[current_interface]["broadcast"] = broadcast_match.group(1)
                    
                # IPv6
                ipv6_match = re.search(r'inet6(?: addr:)? ([a-f0-9:]+)', line)
                if ipv6_match:
                    interfaces[current_interface]["ipv6"].append(ipv6_match.group(1))
                    
                # MAC
                mac_match = re.search(r'(?:ether|HWaddr)\s+([0-9a-f:]+)', line)
                if mac_match:
                    interfaces[current_interface]["mac"] = mac_match.group(1)
                    
                # MTU
                mtu_match = re.search(r'mtu\s+(\d+)', line)
                if mtu_match:
                    interfaces[current_interface]["mtu"] = int(mtu_match.group(1))
                    
                # Statistiques
                rx_match = re.search(r'RX packets\s+(\d+)\s+bytes\s+(\d+)', line)
                if rx_match:
                    interfaces[current_interface]["rx_packets"] = int(rx_match.group(1))
                    interfaces[current_interface]["rx_bytes"] = int(rx_match.group(2))
                    
                tx_match = re.search(r'TX packets\s+(\d+)\s+bytes\s+(\d+)', line)
                if tx_match:
                    interfaces[current_interface]["tx_packets"] = int(tx_match.group(1))
                    interfaces[current_interface]["tx_bytes"] = int(tx_match.group(2))
                    
                errors_match = re.search(r'errors\s+(\d+)', line)
                if errors_match:
                    interfaces[current_interface]["errors"] += int(errors_match.group(1))
        
        return interfaces
    
    def parse_ip_addr_output(self, ip_output: str) -> Dict[str, Dict[str, Any]]:
        """
        Analyse la sortie de la commande ip addr.
        
        Args:
            ip_output: Sortie de la commande ip addr
            
        Returns:
            Dictionnaire des interfaces réseau et leurs propriétés
        """
        interfaces = {}
        current_interface = None
        
        lines = ip_output.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Nouvelle interface
            if line.startswith("\d:") or re.match(r'^\d+:', line):
                interface_match = re.search(r'^\d+:\s+([\w\d@.]+):', line)
                if interface_match:
                    current_interface = interface_match.group(1)
                    interfaces[current_interface] = {
                        "name": current_interface,
                        "ipv4": None,
                        "ipv6": [],
                        "mac": None,
                        "netmask": None,
                        "broadcast": None,
                        "flags": None,
                        "mtu": None,
                        "status": "unknown",
                        "type": None
                    }
                    
                    # Extraire les flags et l'état
                    flags_match = re.search(r'<([^>]+)>', line)
                    mtu_match = re.search(r'mtu\s+(\d+)', line)
                    state_match = re.search(r'state\s+(\w+)', line)
                    
                    if flags_match:
                        interfaces[current_interface]["flags"] = flags_match.group(1)
                        
                    if mtu_match:
                        interfaces[current_interface]["mtu"] = int(mtu_match.group(1))
                        
                    if state_match:
                        state = state_match.group(1).lower()
                        interfaces[current_interface]["status"] = state
                        
            # Informations complémentaires de l'interface courante
            elif current_interface and line:
                # Type d'interface
                link_match = re.search(r'link/([^\s]+)', line)
                if link_match:
                    interfaces[current_interface]["type"] = link_match.group(1)
                
                # MAC
                mac_match = re.search(r'link/[^\s]+\s+([0-9a-f:]+)', line)
                if mac_match:
                    interfaces[current_interface]["mac"] = mac_match.group(1)
                
                # IPv4
                ipv4_match = re.search(r'inet\s+([\d\.]+)(?:/([\d]+))?', line)
                if ipv4_match:
                    interfaces[current_interface]["ipv4"] = ipv4_match.group(1)
                    
                    # Convertir le préfixe CIDR en netmask
                    if ipv4_match.group(2):
                        try:
                            cidr = int(ipv4_match.group(2))
                            netmask = self._cidr_to_netmask(cidr)
                            interfaces[current_interface]["netmask"] = netmask
                        except ValueError:
                            pass
                    
                    # Broadcast
                    brd_match = re.search(r'brd\s+([\d\.]+)', line)
                    if brd_match:
                        interfaces[current_interface]["broadcast"] = brd_match.group(1)
                
                # IPv6
                ipv6_match = re.search(r'inet6\s+([a-f0-9:]+)(?:/\d+)?', line)
                if ipv6_match:
                    interfaces[current_interface]["ipv6"].append(ipv6_match.group(1))
        
        return interfaces
    
    def _cidr_to_netmask(self, cidr: int) -> str:
        """
        Convertit un préfixe CIDR en masque de sous-réseau.
        
        Args:
            cidr: Préfixe CIDR (0-32)
            
        Returns:
            Masque de sous-réseau (ex: 255.255.255.0)
        """
        try:
            return str(ipaddress.IPv4Network(f'0.0.0.0/{cidr}').netmask)
        except Exception:
            return None
    
    def parse_netstat_output(self, netstat_output: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Analyse la sortie de la commande netstat.
        
        Args:
            netstat_output: Sortie de la commande netstat -tuanp
            
        Returns:
            Dictionnaire des connexions réseau
        """
        result = {
            "tcp": [],
            "udp": [],
            "tcp6": [],
            "udp6": [],
            "listening": [],
            "established": []
        }
        
        lines = netstat_output.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith("Proto"):
                continue
                
            parts = line.split()
            if len(parts) < 6:
                continue
                
            proto = parts[0].lower()
            local_addr = parts[3]
            remote_addr = parts[4]
            state = parts[5] if len(parts) > 5 else "N/A"
            pid_program = parts[6] if len(parts) > 6 else None
            
            # Extraire le port local
            local_port = None
            local_port_match = re.search(r':([\d]+)$', local_addr)
            if local_port_match:
                local_port = int(local_port_match.group(1))
                
            # Extraire le PID et le programme
            pid = None
            program = None
            if pid_program and '/' in pid_program:
                pid_parts = pid_program.split('/', 1)
                pid = int(pid_parts[0]) if pid_parts[0].isdigit() else None
                program = pid_parts[1] if len(pid_parts) > 1 else None
            
            # Créer l'entrée
            conn = {
                "proto": proto,
                "local_addr": local_addr,
                "remote_addr": remote_addr,
                "state": state,
                "pid": pid,
                "program": program,
                "local_port": local_port
            }
            
            # Ajouter aux listes appropriées
            if proto in result:
                result[proto].append(conn)
                
            if state == "LISTEN":
                result["listening"].append(conn)
            elif state == "ESTABLISHED":
                result["established"].append(conn)
        
        return result
    
    def parse_ss_output(self, ss_output: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Analyse la sortie de la commande ss.
        
        Args:
            ss_output: Sortie de la commande ss -tuanp
            
        Returns:
            Dictionnaire des connexions réseau
        """
        result = {
            "tcp": [],
            "udp": [],
            "tcp6": [],
            "udp6": [],
            "listening": [],
            "established": []
        }
        
        lines = ss_output.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith("Netid") or line.startswith("State"):
                continue
                
            parts = line.split()
            if len(parts) < 5:
                continue
                
            proto = parts[0].lower()
            state = parts[1]
            local_addr = parts[4]
            remote_addr = parts[5] if len(parts) > 5 else "*:*"
            process_info = ' '.join(parts[6:]) if len(parts) > 6 else None
            
            # Extraire le port local
            local_port = None
            local_port_match = re.search(r':([\d]+)$', local_addr)
            if local_port_match:
                local_port = int(local_port_match.group(1))
                
            # Extraire le PID et le programme
            pid = None
            program = None
            if process_info:
                pid_match = re.search(r'pid=(\d+)', process_info)
                if pid_match:
                    pid = int(pid_match.group(1))
                    
                proc_match = re.search(r'users:\(\("([^"]+)"', process_info)
                if proc_match:
                    program = proc_match.group(1)
            
            # Créer l'entrée
            conn = {
                "proto": proto,
                "local_addr": local_addr,
                "remote_addr": remote_addr,
                "state": state,
                "pid": pid,
                "program": program,
                "local_port": local_port
            }
            
            # Ajuster l'état pour la compatibilité avec netstat
            if state.lower() == "listen":
                conn["state"] = "LISTEN"
                result["listening"].append(conn)
            elif state.lower() == "estab":
                conn["state"] = "ESTABLISHED"
                result["established"].append(conn)
            
            # Ajouter aux listes appropriées
            matched_proto = None
            if proto.startswith("tcp"):
                if "6" in proto:
                    matched_proto = "tcp6"
                else:
                    matched_proto = "tcp"
            elif proto.startswith("udp"):
                if "6" in proto:
                    matched_proto = "udp6"
                else:
                    matched_proto = "udp"
                    
            if matched_proto in result:
                result[matched_proto].append(conn)
        
        return result
    
    def parse_ping_output(self, ping_output: str) -> Dict[str, Any]:
        """
        Analyse la sortie de la commande ping.
        
        Args:
            ping_output: Sortie de la commande ping
            
        Returns:
            Résultats de ping formatés
        """
        result = {
            "target": None,
            "transmitted": 0,
            "received": 0,
            "packet_loss": 100.0,  # Par défaut 100% de perte
            "min_time": None,
            "avg_time": None,
            "max_time": None,
            "responses": []
        }
        
        # Extraire l'hôte cible
        target_match = re.search(r'PING\s+([^\s]+)', ping_output)
        if target_match:
            result["target"] = target_match.group(1)
            
        # Extraire les réponses individuelles
        response_matches = re.finditer(r'bytes from ([^:]+): icmp_seq=(\d+) ttl=(\d+) time=([\d\.]+)\s+ms', ping_output)
        for match in response_matches:
            host = match.group(1)
            seq = int(match.group(2))
            ttl = int(match.group(3))
            time_ms = float(match.group(4))
            
            result["responses"].append({
                "host": host,
                "seq": seq,
                "ttl": ttl,
                "time_ms": time_ms
            })
            
        # Extraire le résumé
        stats_match = re.search(r'(\d+) packets transmitted,\s+(\d+)\s+received', ping_output)
        if stats_match:
            result["transmitted"] = int(stats_match.group(1))
            result["received"] = int(stats_match.group(2))
            
            if result["transmitted"] > 0:
                result["packet_loss"] = (1 - result["received"] / result["transmitted"]) * 100
                
        # Extraire les temps
        times_match = re.search(r'min/avg/max(?:/mdev)?\s+=\s+([\d\.]+)/([\d\.]+)/([\d\.]+)', ping_output)
        if times_match:
            result["min_time"] = float(times_match.group(1))
            result["avg_time"] = float(times_match.group(2))
            result["max_time"] = float(times_match.group(3))
        
        return result
    
    def parse_route_output(self, route_output: str) -> List[Dict[str, Any]]:
        """
        Analyse la sortie de la commande route.
        
        Args:
            route_output: Sortie de la commande route -n
            
        Returns:
            Table de routage formatée
        """
        routes = []
        
        lines = route_output.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith("Kernel") or line.startswith("Destination"):
                continue
                
            parts = line.split()
            if len(parts) < 8:
                continue
                
            destination = parts[0]
            gateway = parts[1]
            genmask = parts[2]
            flags = parts[3]
            metric = parts[4]
            ref = parts[5]
            use = parts[6]
            interface = parts[7]
            
            routes.append({
                "destination": destination,
                "gateway": gateway,
                "genmask": genmask,
                "flags": flags,
                "metric": int(metric) if metric.isdigit() else metric,
                "interface": interface,
                "is_default": destination == "0.0.0.0" or destination == "default"
            })
        
        return routes
    
    def parse_traceroute_output(self, traceroute_output: str) -> List[Dict[str, Any]]:
        """
        Analyse la sortie de la commande traceroute.
        
        Args:
            traceroute_output: Sortie de la commande traceroute
            
        Returns:
            Résultats du traceroute formatés
        """
        hops = []
        target = None
        
        # Extraire la cible
        target_match = re.search(r'traceroute to ([^\s]+)', traceroute_output)
        if target_match:
            target = target_match.group(1)
            
        # Extraire les sauts
        lines = traceroute_output.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith("traceroute"):
                continue
                
            # Format typique: "1  gateway (192.168.1.1)  0.123 ms  0.456 ms  0.789 ms"
            hop_match = re.match(r'^\s*(\d+)\s+(.+)', line)
            if hop_match:
                hop_num = int(hop_match.group(1))
                hop_data = hop_match.group(2)
                
                # Traiter les différents formats
                hosts = []
                times = []
                
                # Extraire les noms d'hôtes et les adresses IP
                host_matches = re.finditer(r'([^\s(]+)\s*(?:\(([\d\.]+)\))?', hop_data)
                for match in host_matches:
                    hostname = match.group(1)
                    ip = match.group(2) if match.group(2) else hostname
                    
                    # Vérifier si c'est un asterisque (timeout)
                    if hostname == "*":
                        continue
                        
                    # Vérifier si c'est un temps
                    if hostname.replace('.', '', 1).isdigit() and " ms" in hop_data:
                        try:
                            times.append(float(hostname))
                            continue
                        except ValueError:
                            pass
                    
                    hosts.append({
                        "hostname": hostname if hostname != ip else None,
                        "ip": ip
                    })
                
                # Extraire les temps
                time_matches = re.finditer(r'([\d\.]+)\s+ms', hop_data)
                for match in time_matches:
                    try:
                        times.append(float(match.group(1)))
                    except ValueError:
                        pass
                
                # Créer l'entrée de saut
                hop = {
                    "hop": hop_num,
                    "hosts": hosts,
                    "times": times,
                    "timeout": "*" in hop_data
                }
                
                if times:
                    hop["avg_time"] = sum(times) / len(times)
                    
                hops.append(hop)
        
        return {
            "target": target,
            "hops": hops
        }
    
    def parse_nslookup_output(self, nslookup_output: str) -> Dict[str, Any]:
        """
        Analyse la sortie de la commande nslookup.
        
        Args:
            nslookup_output: Sortie de la commande nslookup
            
        Returns:
            Résultats de nslookup formatés
        """
        result = {
            "query": None,
            "server": None,
            "addresses": [],
            "names": [],
            "error": None
        }
        
        lines = nslookup_output.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Serveur utilisé
            server_match = re.search(r'Server:\s+(.+)', line)
            if server_match:
                result["server"] = server_match.group(1)
                continue
                
            # Erreur
            if "can't find" in line or "NXDOMAIN" in line:
                result["error"] = line
                continue
                
            # Extraire les adresses et noms
            addr_match = re.search(r'Address(?:\s+\d+)?:\s+(.+)', line)
            if addr_match:
                result["addresses"].append(addr_match.group(1))
                continue
                
            name_match = re.search(r'Name:\s+(.+)', line)
            if name_match:
                result["names"].append(name_match.group(1))
                if not result["query"]:
                    result["query"] = name_match.group(1)
                continue
                
            # Si la ligne contient une adresse IP, c'est probablement la requête
            if re.search(r'^\d+\.\d+\.\d+\.\d+$', line) and not result["query"]:
                result["query"] = line
        
        return result
    
    def diagnose_network_issue(self, issue_description: str, diagnostics: Dict[str, Any] = None) -> str:
        """
        Diagnostique un problème réseau en fonction de sa description et des diagnostics disponibles.
        
        Args:
            issue_description: Description du problème réseau
            diagnostics: Résultats des diagnostics déjà effectués
            
        Returns:
            Diagnostic et suggestions
        """
        # Construire le prompt pour l'analyse
        prompt = f"""
Diagnostique un problème réseau Linux en fonction de cette description :

{issue_description}

"""
        
        if diagnostics:
            prompt += f"""
Résultats des diagnostics déjà effectués :
```
{diagnostics}
```

"""
        
        prompt += """
Fournis une analyse détaillée avec :
1. Diagnostic probable de la cause du problème
2. Une commande que l'administrateur devrait exécuter ensuite pour vérifier l'origine du problème (en mode root, sans sudo)
3. L'explication de ce que cette commande permettra de vérifier
4. Les solutions possibles selon différents scénarios

Reste concis et orienté vers l'action. Propose une commande spécifique pour la prochaine étape de diagnostic.
"""
        
        try:
            response = self.ollama.generate(
                prompt=prompt,
                temperature=0.3
            )
            return response
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse du problème réseau: {e}")
            return f"Erreur lors de l'analyse: {e}"