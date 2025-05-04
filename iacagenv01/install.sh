#!/bin/bash

# Couleurs pour les messages
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Chemin d'installation
INSTALL_DIR="$HOME/iacagent"
SERVICE_NAME="iacagent"
SHELL_RC_FILE=""

# Détecter le shell de l'utilisateur
detect_shell() {
    if [[ "$SHELL" == *"zsh"* ]]; then
        SHELL_RC_FILE="$HOME/.zshrc"
    elif [[ "$SHELL" == *"bash"* ]]; then
        if [[ -f "$HOME/.bashrc" ]]; then
            SHELL_RC_FILE="$HOME/.bashrc"
        else
            SHELL_RC_FILE="$HOME/.bash_profile"
        fi
    else
        SHELL_RC_FILE="$HOME/.bashrc"
        echo -e "${YELLOW}Shell non reconnu, utilisation de ~/.bashrc par défaut${NC}"
    fi
}

# Fonction pour afficher un message de confirmation
print_status() {
    echo -e "${BLUE}$1${NC}"
}

# Fonction pour afficher un message d'erreur et quitter
error_exit() {
    echo -e "${RED}Erreur: $1${NC}" >&2
    exit 1
}

# Vérifier si python3 est installé
check_python() {
    if ! command -v python3 &> /dev/null; then
        error_exit "Python 3 n'est pas installé. Veuillez l'installer avant de continuer."
    fi
    
    # Vérifier la version de Python
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    print_status "Python version: $PYTHON_VERSION détectée"
    
    # Vérifier si pip est installé
    if ! command -v pip3 &> /dev/null; then
        error_exit "pip3 n'est pas installé. Veuillez l'installer avant de continuer."
    fi
}

# Créer la structure de dossiers et installer les fichiers
setup_directories() {
    print_status "Configuration des dossiers et fichiers..."
    
    # Créer le dossier d'installation s'il n'existe pas
    mkdir -p "$INSTALL_DIR" || error_exit "Impossible de créer le dossier $INSTALL_DIR"
    
    # Copier les fichiers du projet
    cp agent.py "$INSTALL_DIR/" || error_exit "Impossible de copier agent.py"
    chmod +x "$INSTALL_DIR/agent.py" || error_exit "Impossible de rendre agent.py exécutable"
    
    if [ -f "prompt.txt" ]; then
        cp prompt.txt "$INSTALL_DIR/" || error_exit "Impossible de copier prompt.txt"
    fi
    
    if [ -f "requirements.txt" ]; then
        cp requirements.txt "$INSTALL_DIR/" || error_exit "Impossible de copier requirements.txt"
    else
        # Créer un fichier requirements.txt minimal
        echo "requests>=2.25.0" > "$INSTALL_DIR/requirements.txt"
    fi
    
    # Créer un fichier .env pour la clé API
    if [ ! -f "$INSTALL_DIR/.env" ]; then
        echo "MISTRAL_API_KEY=" > "$INSTALL_DIR/.env"
        print_status "Fichier .env créé dans $INSTALL_DIR"
    fi
    
    # Créer un fichier config.json vide
    if [ ! -f "$INSTALL_DIR/config.json" ]; then
        echo '{"api_key": ""}' > "$INSTALL_DIR/config.json"
        print_status "Fichier config.json créé dans $INSTALL_DIR"
    fi
    
    # Créer un fichier d'historique vide si besoin
    if [ ! -f "$INSTALL_DIR/history.json" ]; then
        echo "[]" > "$INSTALL_DIR/history.json"
    fi
    
    # Créer un fichier de log vide
    touch "$INSTALL_DIR/iacagent.log"
}

# Installer les dépendances Python dans un environnement virtuel
install_dependencies() {
    print_status "Configuration de l'environnement virtuel Python..."
    
    # Vérifier si python3-venv est installé
    if ! python3 -m venv --help &> /dev/null; then
        echo -e "${YELLOW}Le module python3-venv semble manquant. Tentative d'installation...${NC}"
        sudo apt-get update && sudo apt-get install -y python3-venv python3-full || {
            echo -e "${YELLOW}Impossible d'installer automatiquement python3-venv.${NC}"
            echo -e "${YELLOW}Veuillez l'installer manuellement avec:${NC}"
            echo -e "${BLUE}sudo apt-get install python3-venv python3-full${NC}"
            read -p "Appuyez sur Entrée pour continuer une fois installé, ou Ctrl+C pour annuler..."
        }
    fi
    
    # Créer l'environnement virtuel
    python3 -m venv "$INSTALL_DIR/venv" || error_exit "Impossible de créer l'environnement virtuel"
    
    print_status "Installation des dépendances Python dans l'environnement virtuel..."
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
    "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" || error_exit "Impossible d'installer les dépendances Python"
}

# Configurer l'alias dans le fichier de configuration du shell
setup_alias() {
    print_status "Configuration de l'alias shell..."
    
    # Détecter le shell
    detect_shell
    
    # Créer un script wrapper
    cat > "$INSTALL_DIR/iacagent_wrapper.sh" << EOF
#!/bin/bash
# Wrapper script pour IacAgent utilisant l'environnement virtuel
$INSTALL_DIR/venv/bin/python "$INSTALL_DIR/agent.py" "\$@"
EOF
    
    # Rendre le script wrapper exécutable
    chmod +x "$INSTALL_DIR/iacagent_wrapper.sh"
    
    # Vérifier si l'alias existe déjà
    if grep -q "alias iacagent=" "$SHELL_RC_FILE"; then
        print_status "L'alias 'iacagent' existe déjà dans $SHELL_RC_FILE"
        # Mettre à jour l'alias existant pour utiliser l'environnement virtuel
        sed -i "s|alias iacagent=.*|alias iacagent='$INSTALL_DIR/iacagent_wrapper.sh'|" "$SHELL_RC_FILE"
    else
        echo "# IacAgent - Assistant IA CLI pour DevOps" >> "$SHELL_RC_FILE"
        echo "alias iacagent='$INSTALL_DIR/iacagent_wrapper.sh'" >> "$SHELL_RC_FILE"
        print_status "Alias 'iacagent' ajouté à $SHELL_RC_FILE"
    fi
}

# Installer le service systemd
install_systemd_service() {
    print_status "Configuration du service systemd..."
    
    # Chemin du fichier service pour l'utilisateur
    USER_SERVICE_DIR="$HOME/.config/systemd/user"
    mkdir -p "$USER_SERVICE_DIR"
    
    # Créer le fichier service
    cat > "$USER_SERVICE_DIR/$SERVICE_NAME.service" << EOF
[Unit]
Description=IacAgent - Assistant IA CLI pour DevOps
After=network.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/agent.py --daemon
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=default.target
EOF
    
    # Recharger les services systemd
    systemctl --user daemon-reload || print_status "Impossible de recharger systemd, vous devrez peut-être le faire manuellement"
    
    print_status "Service systemd créé dans $USER_SERVICE_DIR/$SERVICE_NAME.service"
    print_status "Pour activer le service: systemctl --user enable $SERVICE_NAME"
    print_status "Pour démarrer le service: systemctl --user start $SERVICE_NAME"
}

# Demander la clé API Mistral
configure_api_key() {
    print_status "Configuration de la clé API Mistral..."
    
    read -p "Entrez votre clé API Mistral (laisser vide pour configurer plus tard): " API_KEY
    
    if [ ! -z "$API_KEY" ]; then
        # Mettre à jour le fichier .env
        sed -i "s/MISTRAL_API_KEY=.*/MISTRAL_API_KEY=$API_KEY/" "$INSTALL_DIR/.env"
        
        # Mettre à jour le fichier config.json
        # Utilisation de sed au lieu de jq pour éviter une dépendance supplémentaire
        sed -i 's/"api_key": ".*"/"api_key": "'$API_KEY'"/' "$INSTALL_DIR/config.json"
        
        print_status "Clé API configurée"
    else
        print_status "Aucune clé API fournie. Vous pourrez la configurer plus tard dans $INSTALL_DIR/.env ou $INSTALL_DIR/config.json"
    fi
}

# Message final
show_final_message() {
    echo -e "\n${GREEN}✅ Installation de IacAgent terminée !${NC}"
    echo -e "${YELLOW}Pour utiliser IacAgent:${NC}"
    echo -e "  - Redémarrez votre terminal ou exécutez: source $SHELL_RC_FILE"
    echo -e "  - Puis lancez la commande: ${GREEN}iacagent${NC}"
    echo -e "\n${YELLOW}Fichiers installés dans:${NC} $INSTALL_DIR"
    echo -e "${YELLOW}Configuration:${NC} $INSTALL_DIR/config.json ou $INSTALL_DIR/.env"
    echo -e "${YELLOW}Logs:${NC} $INSTALL_DIR/iacagent.log"
    
    # Vérifier si la clé API a été configurée
    if grep -q "MISTRAL_API_KEY=" "$INSTALL_DIR/.env" && ! grep -q "MISTRAL_API_KEY=.\+" "$INSTALL_DIR/.env"; then
        echo -e "\n${RED}⚠️ N'oubliez pas de configurer votre clé API Mistral !${NC}"
    fi
}

# Programme principal
main() {
    echo -e "${GREEN}=== Installation de IacAgent - Assistant IA CLI pour DevOps ===${NC}"
    
    check_python
    setup_directories
    install_dependencies
    setup_alias
    install_systemd_service
    configure_api_key
    show_final_message
}

# Exécuter le programme principal
main