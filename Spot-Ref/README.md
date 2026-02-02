# Spot-Ref

Projet Python pour l'ingestion et la recherche sémantique de documents, entièrement piloté via Docker.

## 🚀 Démarrage rapide

1. **Cloner le dépôt et se placer dans le dossier**

   ```bash
   cd /Users/thomasberbessou/Spot-Ref
   ```

2. **Configurer les variables d'environnement**
   - Copier `.env.example` en `.env` et renseigner les clés nécessaires (ex: AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT).

3. **Configuration des Docker**

   ```bash
   docker compose build
   ```

4. **Ingestion des données**

   ```bash
   docker compose up ingestion
   ```

   (Le conteneur s'arrête automatiquement à la fin de l'ingestion.)

5. **Lancer l'interface utilisateur**

   ```bash
   docker compose up chainlit
   ```

   (Accéder à [http://localhost:8000](http://localhost:8000))

6. **Arrêter tous les services**

   ```bash
   docker compose down
   ```

## 📂 Structure du projet

```tree
.
├── README.md
├── pyproject.toml
├── requirements.txt
├── src/
│   ├── llm_semantic_splitter.py
│   ├── transfert_pdf_txt.py
│   └── ...
├── test/
│   ├── test_convert_files.py
│   ├── test_llm_semantic_splitter.py
│   └── test_translate.py
├── Customer_txt/
├── .env
├── .env.example
├── .gitignore
├── .dockerignore
├── Dockerfile.chainlit
├── Dockerfile.ingestion
├── docker-compose.yml
└── ...
```

## 📜 Règles et Spécifications

### Architecture de l'Application

- Architecture basée sur LangGraph et Chainlit.
- Composants principaux : StateGraph, Nodes, Tools.
- Interface utilisateur via Chainlit.
- Nécessite des variables d'environnement pour Azure OpenAI et Qdrant.

### Ingestion

- Ingestion des documents dans Qdrant.
- Découpage sémantique via LLM.
- Interface CLI pour l'ingestion.

### LLM Semantic Splitter

- Découpe les documents avec Azure OpenAI.
- Retourne des chunks et des métadonnées.
- Gère les erreurs et traite les documents de `Customer_txt`.

### Prompt List

- Contient les templates de prompts pour les interactions LLM.
- Définit `LLMSPLITTER_PROMPT` pour le découpage sémantique.

### Règles Principales

- Point d'entrée principal de l'application avec Chainlit et LangGraph.
- Définit le workflow de l'agent conversationnel.

### Conversion PDF vers Texte

- Conversion des PDF en texte via OCR.
- Préserve la structure

### Conversion PowerPoint vers PDF

- Conversion des PowerPoint en PDF.
- Utilise `unoconv`

### Environnement et Structure

- Variables d'environnement requises.
- Structure des dossiers et flux de données.

### Développement et Déploiement

- Instructions de configuration et de déploiement.
- Déploiement Docker inclus.

### Directives de Test

- Organisation des tests et couverture requise.
- Détail des pratiques de tests unitaires et d'intégration.

### Convention de Code

- Voir les fichiers Python pour les conventions de style et de documentation.

## 📈 Tracing et Observabilité avec Langfuse

L'application intègre Langfuse pour le tracing et l'observabilité des requêtes RAG. Voici comment l'utiliser :

### 1. Démarrer Langfuse avec Docker

```bash
docker compose build langfuse
```

Puis lancez tous les services :

```bash
docker compose up
```

### 2. Créer un compte

- Accédez à l'interface Langfuse sur [http://localhost:3000](http://localhost:3000)
- Créez un compte lors de la première connexion

### 3. Créer un projet Langfuse

- Une fois connecté, créez un nouveau projet dans Langfuse
- Récupérez la **clé publique** et la **clé secrète** du projet (onglet "API Keys")

### 4. Configurer les variables d'environnement

- Ajoutez les clés dans votre fichier `.env` :

```env
LANGFUSE_SECRET_KEY=sk-...   # Clé secrète du projet Langfuse
LANGFUSE_PUBLIC_KEY=pk-...   # Clé publique du projet Langfuse
LANGFUSE_HOST=http://langfuse:3000
```

### 5. Lancer l'interface Chainlit

```bash
docker compose up chainlit -d 
```

### 6. Utiliser l'application

- Posez vos questions dans l'interface Chainlit
- Les traces détaillées de chaque requête seront visibles dans Langfuse (<http://localhost:3000>)
- Vous pouvez explorer les traces, les inputs/outputs, les métadonnées, et les erreurs éventuelles

> **Astuce :** Langfuse permet de filtrer, explorer et auditer toutes les interactions RAG pour un meilleur debug et monitoring.

## 🚀 Déploiement en Production avec Azure Container Apps

Pour le déploiement en production, tous les fichiers et scripts nécessaires sont organisés dans le dossier `prod_azure/`.

### 📁 Structure du Déploiement

```
prod_azure/
├── README.md                          # Guide de déploiement complet
├── env.example                        # Template des variables d'environnement
├── Dockerfile.chainlit.prod           # Container Chainlit optimisé
├── Dockerfile.ingestion.prod          # Container d'ingestion
├── Dockerfile.qdrant.prod             # Container Qdrant personnalisé
├── docker-compose.prod.yml            # Configuration Docker Compose
├── DEPLOYMENT-SUMMARY.md              # Résumé technique complet
└── scripts/
    ├── azure-setup.ps1                # Configuration infrastructure Azure
    ├── build-and-push.ps1             # Construction et push des images
    ├── deploy-containers.ps1          # Déploiement des Container Apps
    ├── configure-env.ps1              # Configuration des variables
    ├── run-ingestion.ps1              # Lancement de l'ingestion
    └── quick-deploy.ps1               # Déploiement en une commande
```

### 🚀 Démarrage Rapide

```powershell
# Naviguez vers le dossier de production
cd prod_azure

# Configurez l'environnement
cp env.example .env
# Editez .env avec vos valeurs

# Déploiement complet en une commande
.\scripts\quick-deploy.ps1 `
    -ResourceGroupName "spot-ref-prod" `
    -Location "France Central" `
    -ContainerRegistryName "spotrefacr" `
    -ContainerAppsEnvironmentName "spot-ref-env" `
    -AzureOpenAIApiKey "your-api-key" `
    -AzureOpenAIEndpoint "https://your-resource.openai.azure.com/" `
    -AzureOpenAIDeployment "gpt4o" `
    -AzureOpenAIEmbeddingDeployment "text-embedding-ada-002"

# Lancez l'ingestion
.\scripts\run-ingestion.ps1 -ResourceGroupName "spot-ref-prod"
```

### 📖 Documentation Complète

- **[Guide de Déploiement](prod_azure/README.md)** : Instructions détaillées étape par étape
- **[Résumé Technique](prod_azure/DEPLOYMENT-SUMMARY.md)** : Spécifications techniques complètes
- **[Variables d'Environnement](prod_azure/env.example)** : Template de configuration

### 🏗️ Architecture de Production

Le déploiement comprend :
- **Azure Container Registry (ACR)** : Stockage des images Docker
- **Azure Container Apps** : Hébergement des conteneurs
- **Log Analytics** : Monitoring et observabilité
- **Azure Storage** : Persistance des données Qdrant

### 💰 Estimation des Coûts

- **Container Apps** : ~50€/mois pour un usage modéré
- **Container Registry** : ~10€/mois pour le stockage des images
- **Log Analytics** : ~20€/mois pour les logs et métriques
- **Azure Storage** : ~5€/mois pour la persistance Qdrant

### 🔒 Sécurité et Monitoring

- **Utilisateurs non-root** : Tous les conteneurs utilisent des utilisateurs non-privilegiés
- **HTTPS/TLS** : Chiffrement automatique
- **Health Checks** : Vérification automatique de l'état des conteneurs
- **Logs centralisés** : Monitoring via Azure Log Analytics

### 📊 URLs de Production

Une fois déployé, l'application sera accessible via :
- **Interface Chainlit** : `https://spot-ref-chainlit.{region}.azurecontainerapps.io`
- **API Qdrant** : `https://spot-ref-qdrant.{region}.azurecontainerapps.io`

---

## 🔧 Dépannage et Support

### Problèmes Courants

1. **Erreur de connexion Qdrant** : Vérifiez que le service Qdrant est démarré
2. **Problème d'ingestion** : Vérifiez les permissions SharePoint et les clés Azure OpenAI
3. **Interface Chainlit indisponible** : Vérifiez les logs avec `docker logs chainlit_app`

### Logs et Monitoring

```bash
# Logs de l'application
docker logs chainlit_app

# Logs de l'ingestion
docker logs ingestion_app

# Monitoring des ressources
docker stats
```
