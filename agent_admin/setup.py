from setuptools import setup, find_packages

setup(
    name="linux-assistant",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "rich>=10.0.0",
        "prompt_toolkit>=3.0.20",
        "requests>=2.26.0",
        "pyyaml>=6.0",
        "python-dotenv>=0.19.0",
        "argparse>=1.4.0",
        "colorama>=0.4.4",
        "markdown>=3.4.0"
    ],
    entry_points={
        'console_scripts': [
            'linux-assistant=linux_assistant.main:main',
        ],
    },
    author="BadrBouzakri",
    author_email="your.email@example.com",
    description="Assistant IA pour administrateurs système Linux",
    keywords="linux, admin, assistant, ollama, AI, qwen",
    url="https://github.com/BadrBouzakri/AI_Agent/tree/main/agent_admin",
    python_requires=">=3.9",
)