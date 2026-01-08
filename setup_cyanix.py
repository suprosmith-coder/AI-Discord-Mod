#!/usr/bin/env python3
"""
Cyanix AI - Environment Setup Wizard
Helps users configure their .env file easily
"""

import os
import sys
import json
from pathlib import Path

def setup_wizard():
    print("🎉 Welcome to Cyanix AI Setup Wizard!")
    print("=" * 50)
    
    env_config = {}
    
    # Step 1: API Keys
    print("\n🔑 STEP 1: API Credentials")
    print("-" * 30)
    
    discord_token = input("Enter your Discord Bot Token: ").strip()
    if discord_token:
        env_config["DISCORD_BOT_TOKEN"] = discord_token
    
    openai_key = input("Enter your OpenAI API Key (press Enter if none): ").strip()
    if openai_key:
        env_config["OPENAI_API_KEY"] = openai_key
    
    hf_token = input("Enter your Hugging Face Token (optional): ").strip()
    if hf_token:
        env_config["HUGGINGFACE_TOKEN"] = hf_token
    
    # Step 2: Basic Configuration
    print("\n⚙️ STEP 2: Basic Configuration")
    print("-" * 30)
    
    sensitivity = input("AI Sensitivity (0.0-1.0, default 0.75): ").strip()
    if sensitivity and 0 <= float(sensitivity) <= 1:
        env_config["DEFAULT_SENSITIVITY"] = sensitivity
    
    warning_system = input("Enable warning system? (yes/no, default no): ").strip().lower()
    env_config["WARNING_SYSTEM"] = "true" if warning_system == "yes" else "false"
    
    # Step 3: Trigger Words
    print("\n🚨 STEP 3: Trigger Words Configuration")
    print("-" * 30)
    
    use_triggers = input("Use triggering words system? (yes/no, default no): ").strip().lower()
    env_config["USE_TRIGGERING_WORDS"] = "true" if use_triggers == "yes" else "false"
    
    if use_triggers == "yes":
        print("\n📝 Creating wordlist.txt with example words...")
        with open("wordlist.txt", "w") as f:
            f.write("badword1,badword2,offensive_term,hate_speech")
        print("✓ Created wordlist.txt")
        print("Edit this file to add your own triggering words")
    
    # Step 4: Advanced Options
    print("\n⚡ STEP 4: Advanced Options")
    print("-" * 30)
    
    print("Using default advanced settings...")
    env_config.update({
        "MODERATION_ENABLED": "true",
        "TEXT_MODERATION": "true",
        "IMAGE_MODERATION": "true",
        "WARNING_LIMIT": "3",
        "DEFAULT_MUTE_TIME": "10m",
        "ENABLE_LOGGING": "true",
        "LOG_LEVEL": "INFO",
        "CACHE_ENABLED": "true",
        "CACHE_DURATION": "300",
        "BOT_NAME": "Cyanix AI",
        "ENABLE_WELCOME_MESSAGE": "true"
    })
    
    # Create .env file
    create_env_file(env_config)
    
    # Create necessary directories
    create_directories()
    
    print("\n" + "=" * 50)
    print("✅ Setup Complete!")
    print("\n📁 Files created:")
    print("  • .env - Configuration file")
    print("  • logs/ - Log directory")
    print("  • backups/ - Backup directory")
    print("  • data/ - Data storage")
    
    if use_triggers == "yes":
        print("  • wordlist.txt - Trigger words list")
    
    print("\n🚀 Next steps:")
    print("  1. Review the .env file")
    print("  2. Install dependencies: pip install -r requirements.txt")
    print("  3. Run the bot: python cyanix_bot.py")
    print("  4. Use /help in Discord to see commands")
    
    print("\n💡 Need help? Join our Discord: https://discord.gg/cyanix")

def create_env_file(config):
    """Create .env file from template and config"""
    print("\n📄 Creating .env file...")
    
    # Start with template
    env_content = """# ========================================
# 🎯 CYANIX AI - DISCORD MODERATION BOT
# ========================================

# 🔑 API CREDENTIALS
"""
    
    # Add API credentials
    if "DISCORD_BOT_TOKEN" in config:
        env_content += f"DISCORD_BOT_TOKEN={config['DISCORD_BOT_TOKEN']}\n"
    
    if "OPENAI_API_KEY" in config:
        env_content += f"OPENAI_API_KEY={config['OPENAI_API_KEY']}\n"
    
    if "HUGGINGFACE_TOKEN" in config:
        env_content += f"HUGGINGFACE_TOKEN={config['HUGGINGFACE_TOKEN']}\n"
    else:
        env_content += "# HUGGINGFACE_TOKEN=optional_huggingface_token\n"
    
    env_content += """
# ⚙️ BOT CONFIGURATION
BOT_PREFIX=$
DEFAULT_LANGUAGE=en

# 🎛️ MODERATION SETTINGS
"""
    
    # Add moderation settings
    env_content += f"MODERATION_ENABLED={config.get('MODERATION_ENABLED', 'true')}\n"
    env_content += f"TEXT_MODERATION={config.get('TEXT_MODERATION', 'true')}\n"
    env_content += f"IMAGE_MODERATION={config.get('IMAGE_MODERATION', 'true')}\n"
    env_content += f"DEFAULT_SENSITIVITY={config.get('DEFAULT_SENSITIVITY', '0.75')}\n"
    env_content += f"WARNING_SYSTEM={config.get('WARNING_SYSTEM', 'false')}\n"
    env_content += f"WARNING_LIMIT={config.get('WARNING_LIMIT', '3')}\n"
    env_content += f"DEFAULT_MUTE_TIME={config.get('DEFAULT_MUTE_TIME', '10m')}\n"
    
    env_content += """
# 📊 LOGGING & ANALYTICS
"""
    env_content += f"ENABLE_LOGGING={config.get('ENABLE_LOGGING', 'true')}\n"
    env_content += f"LOG_LEVEL={config.get('LOG_LEVEL', 'INFO')}\n"
    env_content += "ENABLE_ANALYTICS=true\n"
    
    env_content += """
# 🚨 TRIGGERING WORDS SYSTEM
"""
    env_content += f"USE_TRIGGERING_WORDS={config.get('USE_TRIGGERING_WORDS', 'false')}\n"
    env_content += "TRIGGERING_WORDS_FILE=./wordlist.txt\n"
    
    env_content += """
# 🏃 PERFORMANCE OPTIONS
CACHE_ENABLED=true
CACHE_DURATION=300
MAX_IMAGE_SIZE_MB=10
API_TIMEOUT=30

# 🎨 CUSTOMIZATION
BOT_NAME=Cyanix AI
BOT_COLOR=5865F2
ENABLE_WELCOME_MESSAGE=true

# ⚠️ ADVANCED SETTINGS
DATABASE_TYPE=json
AUTO_UPDATE=false
BACKUP_ENABLED=true
DEBUG_MODE=false

# 🌐 NETWORK SETTINGS
RATE_LIMIT_DELAY=0.5
"""
    
    # Write to file
    with open(".env", "w") as f:
        f.write(env_content)
    
    print("✓ Created .env file")

def create_directories():
    """Create necessary directories"""
    directories = ["logs", "backups", "data", "cache"]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✓ Created {directory}/ directory")

def validate_environment():
    """Validate environment setup"""
    print("\n🔍 Validating environment...")
    
    errors = []
    warnings = []
    
    # Check .env file exists
    if not os.path.exists(".env"):
        errors.append("❌ .env file not found. Run setup_wizard() first.")
    
    # Check required files
    required_files = ["cyanix_bot.py", "ai_discord_functions.py"]
    for file in required_files:
        if not os.path.exists(file):
            errors.append(f"❌ Required file not found: {file}")
    
    # Check optional files
    if os.path.exists("wordlist.txt"):
        with open("wordlist.txt", "r") as f:
            content = f.read()
            if not content.strip():
                warnings.append("⚠️ wordlist.txt is empty")
    
    # Display results
    if errors:
        print("\n❌ Validation errors:")
        for error in errors:
            print(f"  {error}")
    
    if warnings:
        print("\n⚠️  Validation warnings:")
        for warning in warnings:
            print(f"  {warning}")
    
    if not errors:
        print("✅ Environment validated successfully!")
    
    return len(errors) == 0

def generate_docs():
    """Generate documentation from .env file"""
    print("\n📚 Generating documentation...")
    
    docs = """# 🎯 Cyanix AI Configuration Guide

## Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
"""
    
    # Read .env file if exists
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        var, value = line.split("=", 1)
                        var = var.strip()
                        value = value.strip()
                        
                        # Determine if required
                        required = "✅" if var in ["DISCORD_BOT_TOKEN", "OPENAI_API_KEY"] else "❌"
                        
                        docs += f"| `{var}` | *Description* | `{value}` | {required} |\n"
    
    with open("CONFIGURATION.md", "w") as f:
        f.write(docs)
    
    print("✓ Generated CONFIGURATION.md")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "setup":
            setup_wizard()
        elif sys.argv[1] == "validate":
            validate_environment()
        elif sys.argv[1] == "docs":
            generate_docs()
        elif sys.argv[1] == "help":
            print("""
Cyanix AI Configuration Manager
===============================
Commands:
  setup    - Interactive setup wizard
  validate - Validate environment
  docs     - Generate documentation
  help     - Show this help
            """)
    else:
        setup_wizard()