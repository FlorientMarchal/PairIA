# Installation PairIA avec Docker

## Prérequis
Installer **Docker Desktop** : https://www.docker.com/products/docker-desktop  
Redémarre ton PC après l'installation si demandé.

---

## Étapes

### 1. Récupérer le projet
```powershell
git pull
cd site
```

### 2. Créer le fichier `.env`
Créer un fichier `.env` dans le dossier `site/` avec le contenu suivant :
```
MYSQL_ROOT_PASSWORD=tonmotdepasse
ADMIN_ACTION_TOKEN=pairia_admin_secret_change_me
```

### 3. Copier la base de données
```powershell
cp ..\e_commmerce.sql .\init.sql
```

### 4. Lancer les conteneurs
```powershell
docker compose up -d
```
⚠️ Le premier lancement peut prendre quelques minutes.

### 5. Télécharger les modèles IA (une seule fois, ~7GB)
```powershell
docker exec pairia-ollama ollama pull llama3.1
docker exec pairia-ollama ollama pull nomic-embed-text
docker exec pairia-ollama ollama pull qwen2.5:7b
```

### 6. Indexer les produits
```powershell
docker exec pairia-api python embeeding.py
docker exec pairia-api python embeeding_images.py
```

### 7. Entraîner le classificateur (~20 minutes)
```powershell
docker exec pairia-api python finetune_intention.py
```
### Ajouer stripe
```
docker compose cp web:/var/www/html/vendor .
```
---

## Accès
| Service | URL |
|---|---|
| Site | http://localhost |
| phpMyAdmin | http://localhost:8080 |
| API Python | http://localhost:8000 |

---

## Commandes utiles

Arrêter les conteneurs :
```powershell
docker compose down
```

Relancer les conteneurs :
```powershell
docker compose up -d
```

Voir les logs de l'API :
```powershell
docker compose logs -f api
```

---

## Notes
- Le fichier `.env` et `init.sql` ne sont pas dans le git, il faut les créer à chaque nouvelle installation.
- Les modèles Ollama sont persistants — pas besoin de les retélécharger après un `docker compose down`.
- Le modèle d'intention (`modele_intention/`) est aussi persistant — pas besoin de relancer le finetuning sauf si tu veux le réentraîner.
