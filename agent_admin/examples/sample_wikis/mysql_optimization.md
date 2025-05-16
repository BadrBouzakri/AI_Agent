# Optimisation d'une Base de Données MySQL Lente

## Problème Initial

Nous avons reçu un ticket signalant une lenteur anormale sur l'application web liée à la base de données MySQL 8.0 sur AlmaLinux 9. Les requêtes qui prenaient normalement moins d'une seconde mettaient plus de 30 secondes à s'exécuter, sans surcharge apparente de CPU ou de mémoire.

## Diagnostic Technique

### 1. Vérification de l'état du service MySQL

```bash
systemctl status mysqld
```

Le service était en cours d'exécution sans erreurs apparentes dans les logs système.

### 2. Vérification des ressources système

```bash
top
free -m
df -h
```

Aucune saturation de CPU ou de mémoire détectée. Espace disque suffisant sur tous les volumes.

### 3. Analyse des requêtes lentes

```bash
mysql -e "SHOW VARIABLES LIKE 'slow_query%';"
mysql -e "SHOW VARIABLES LIKE 'long_query_time';"
```

Nous avons constaté que le slow query log n'était pas activé. Après l'avoir activé, nous avons identifié plusieurs requêtes problématiques.

### 4. Analyse de la structure des tables

```bash
mysql -e "SHOW TABLE STATUS FROM production_db;"
```

Découverte de plusieurs tables volumineuses sans index appropriés et d'une fragmentation importante.

## Solution Appliquée

### 1. Activation permanente des slow query logs

```bash
vi /etc/my.cnf.d/mysql-server.cnf
```

Ajout des lignes suivantes dans la section [mysqld] :

```
slow_query_log = 1
slow_query_log_file = /var/log/mysql/mysql-slow.log
long_query_time = 1
```

### 2. Création des index manquants

```sql
ALTER TABLE users ADD INDEX idx_last_login (last_login_date);
ALTER TABLE transactions ADD INDEX idx_user_date (user_id, transaction_date);
ALTER TABLE products ADD INDEX idx_category_price (category_id, price);
```

### 3. Optimisation des tables fragmentées

```sql
OPTIMIZE TABLE users, transactions, products, order_items;
```

### 4. Ajustement des paramètres de configuration MySQL

```bash
vi /etc/my.cnf.d/mysql-server.cnf
```

Modification des paramètres suivants :

```
innodb_buffer_pool_size = 4G
innodb_log_file_size = 512M
max_connections = 300
table_open_cache = 2000
query_cache_size = 0
query_cache_type = 0
```

### 5. Redémarrage du service MySQL

```bash
systemctl restart mysqld
```

## Vérifications Post-Intervention

1. Temps de réponse des requêtes réduit à moins de 100ms (mesuré avec les outils de monitoring)
2. Absence de nouvelles entrées dans le slow query log
3. Test de l'application web montrant une amélioration significative des performances
4. Vérification de la consommation des ressources : l'utilisation de la mémoire est plus élevée (attendu avec l'augmentation du buffer pool) mais stable

## Recommandations

1. **Surveillance continue** : Maintenir la surveillance des slow queries pour identifier rapidement les problèmes futurs

2. **Maintenance régulière** : Planifier une optimisation des tables mensuellement

3. **Revue des requêtes** : Travailler avec l'équipe de développement pour revoir les requêtes les plus fréquentes et les optimiser

4. **Indexation stratégique** : Établir une politique d'indexation pour les nouvelles tables, basée sur les patterns d'accès aux données

5. **Mise à niveau** : Envisager une mise à niveau des ressources du serveur si la croissance de la base continue au rythme actuel

6. **Réplication** : Étudier la possibilité de mettre en place une réplication pour les opérations de lecture intensive

Cette intervention a permis de résoudre le problème immédiat de performance, mais un suivi régulier est recommandé pour maintenir les performances optimales de la base de données.