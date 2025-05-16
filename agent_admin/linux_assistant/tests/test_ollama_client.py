"""
Tests pour le client Ollama.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
import requests

from linux_assistant.ollama_client import OllamaClient

@pytest.fixture
def mock_config():
    with patch("linux_assistant.ollama_client.config") as mock_conf:
        mock_conf.get.side_effect = lambda *args, **kwargs: {
            ("ollama", "base_url"): "http://localhost:11434",
            ("ollama", "model"): "qwen2.5-coder:7b",
            ("ollama", "timeout"): 60,
            ("ollama", "max_tokens", 2048): 2048
        }.get(args, kwargs.get("default"))
        yield mock_conf
        
@pytest.fixture
def ollama_client(mock_config):
    return OllamaClient()

def test_init(ollama_client, mock_config):
    assert ollama_client.base_url == "http://localhost:11434"
    assert ollama_client.model == "qwen2.5-coder:7b"
    assert ollama_client.timeout == 60

@patch("requests.Session.post")
def test_generate_success(mock_post, ollama_client):
    # Configurer le mock
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "Test response"}
    mock_post.return_value = mock_response
    
    # Appeler la méthode
    result = ollama_client.generate("Test prompt")
    
    # Vérifications
    assert result == "Test response"
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["model"] == "qwen2.5-coder:7b"
    assert kwargs["json"]["prompt"] == "Test prompt"

@patch("requests.Session.post")
def test_generate_with_system_prompt(mock_post, ollama_client):
    # Configurer le mock
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "Test response"}
    mock_post.return_value = mock_response
    
    # Appeler la méthode avec un prompt système
    result = ollama_client.generate("Test prompt", system_prompt="System instructions")
    
    # Vérifications
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["system"] == "System instructions"

@patch("requests.Session.post")
def test_generate_error(mock_post, ollama_client):
    # Configurer le mock pour lever une exception
    mock_post.side_effect = requests.exceptions.RequestException("Test error")
    
    # Appeler la méthode
    result = ollama_client.generate("Test prompt")
    
    # Vérifier que l'erreur est gérée
    assert "Erreur de communication avec Ollama" in result

def test_system_prompt_generation(ollama_client):
    # Tester la génération de prompt système
    context = {
        "ticket": "Problème avec Apache",
        "history": [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Réponse 1"}
        ]
    }
    
    prompt = ollama_client.get_system_prompt(context)
    
    # Vérifications
    assert "assistant IA pour le support technique" in prompt.lower()
    assert "Problème avec Apache" in prompt