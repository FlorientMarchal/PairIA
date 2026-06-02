#!/bin/bash
# scripts/pull-models.sh
# À lancer UNE FOIS après le premier démarrage Docker
# pour télécharger les modèles Ollama dans le volume persistant

echo "⏳ Attente démarrage Ollama..."
until curl -s http://localhost:11434/api/tags > /dev/null; do
  sleep 2
done

echo "✅ Ollama prêt. Téléchargement des modèles..."
docker exec pairia-ollama ollama pull llama3.1
docker exec pairia-ollama ollama pull nomic-embed-text

echo "✅ Modèles installés. Tu peux démarrer l'API."
