# ia/admin_main.py
import re
import os
import json
import uuid
import httpx
import ollama

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

OLLAMA_HOST        = os.environ.get("OLLAMA_HOST",        "http://localhost:11434")
OLLAMA_MODEL       = os.environ.get("ADMIN_OLLAMA_MODEL", "qwen2.5:7b")
PHP_ACTIONS_URL    = os.environ.get("ADMIN_ACTIONS_URL",  "http://localhost/admin/includes/admin_actions.php")
ADMIN_ACTION_TOKEN = os.environ.get("ADMIN_ACTION_TOKEN", "")

ollama_client = ollama.Client(host=OLLAMA_HOST)

app = FastAPI(title="PairIA Admin Chatbot API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_session_messages: dict = {}

ACTION_STATUS_TEXTS = {
    "modifier_statut_commande":       "Je mets à jour le statut…",
    "modifier_statut_batch":          "Je mets à jour les statuts en lot…",
    "modifier_prix":                  "Je modifie le prix…",
    "modifier_stock":                 "Je modifie le stock…",
    "modifier_prix_batch":            "Je mets à jour les prix…",
    "modifier_article":               "Je modifie l'article…",
    "ajouter_article":                "J'ajoute l'article au catalogue…",
    "supprimer_article":              "Je supprime l'article…",
    "supprimer_commentaire":          "Je supprime le commentaire…",
    "supprimer_commentaires_article": "Je supprime les commentaires…",
    "arrondir_prix":                  "J'arrondis les prix…",
}

TOOLS = [
    {"type":"function","function":{"name":"lister_commandes","description":"Lister les commandes avec filtre optionnel sur le statut","parameters":{"type":"object","properties":{"statut":{"type":"string","description":"en_attente, payée, expédiée, livrée, annulée"},"limit":{"type":"integer"},"depuis":{"type":"string"}}}}},
    {"type":"function","function":{"name":"detail_commande","description":"Obtenir le detail complet d'une commande par son ID. Le resultat contient un champ lignes avec les articles. Exemple de bonne reponse apres cet appel : La commande #5 contient 1 article : Nova Air Lifestyle, taille 39, couleur Blanc, quantite 1, prix 89.99 euros. Statut : expediee, livree a 456 allees des broussiers. Cite TOUJOURS les articles de lignes par leur nom_article, taille et couleur.","parameters":{"type":"object","properties":{"id_commande":{"type":"integer"}},"required":["id_commande"]}}},
    {"type":"function","function":{"name":"detail_article","description":"Obtenir le detail d'un article par son ID exact","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"}},"required":["id_shoes"]}}},
    {"type":"function","function":{"name":"rechercher_article","description":"Rechercher un article par nom, marque ou categorie","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"rechercher_client","description":"Rechercher un client par nom ou email","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"commandes_client","description":"Voir les commandes d'un client","parameters":{"type":"object","properties":{"id_client":{"type":"integer"}},"required":["id_client"]}}},
    {"type":"function","function":{"name":"top_articles","description":"Top des articles les plus vendus","parameters":{"type":"object","properties":{"limit":{"type":"integer"}}}}},
    {"type":"function","function":{"name":"lister_articles_stock_faible","description":"Lister les articles avec un stock faible (sous le seuil)","parameters":{"type":"object","properties":{"seuil":{"type":"integer","description":"Seuil de stock, defaut 20"}}}}},
    {"type":"function","function":{"name":"stats_globales","description":"Statistiques globales de la boutique (CA, nb commandes, nb clients, etc.)","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"ca_par_mois","description":"Chiffre d'affaires par mois sur 12 mois","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"modifier_statut_commande","description":"Modifier le statut d'UNE SEULE commande identifiee par son ID. Utilise CET outil (pas modifier_statut_batch) quand il s'agit d'une seule commande.","parameters":{"type":"object","properties":{"id_commande":{"type":"integer"},"nouveau_statut":{"type":"string","description":"en_attente, payée, expédiée, livrée, annulée"}},"required":["id_commande","nouveau_statut"]}}},
    {"type":"function","function":{"name":"modifier_statut_batch","description":"Modifier le statut de PLUSIEURS commandes en une fois","parameters":{"type":"object","properties":{"ids":{"type":"array","items":{"type":"integer"},"description":"Liste des IDs de commandes"},"nouveau_statut":{"type":"string"}},"required":["ids","nouveau_statut"]}}},
    {"type":"function","function":{"name":"modifier_prix","description":"Modifier le prix d'UN article. nouveau_prix est le NOUVEAU prix FINAL en euros, pas une différence.","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"},"nouveau_prix":{"type":"number","description":"Le nouveau prix FINAL de l'article en euros. Exemple: si prix actuel=120€ et hausse de 5€, envoyer 125."}},"required":["id_shoes","nouveau_prix"]}}},
    {"type":"function","function":{"name":"lister_variantes","description":"OBLIGATOIRE pour toute demande concernant le STOCK d'un article (voir, modifier, gerer le stock). Affiche les variantes (taille, couleur, stock) dans une carte interactive. N'utilise JAMAIS modifier_article ou un autre outil pour le stock - utilise TOUJOURS lister_variantes.","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"}},"required":["id_shoes"]}}},
    {"type":"function","function":{"name":"modifier_prix_batch","description":"Modifier les prix d'un groupe d'articles","parameters":{"type":"object","properties":{"filtre_type":{"type":"string","description":"categorie, marque, genre, ou tous"},"filtre_valeur":{"type":"string","description":"Valeur du filtre (ignoré si tous)"},"type_modif":{"type":"string","description":"pourcentage, fixe, ou nouveau_prix"},"valeur":{"type":"number","description":"Valeur: pourcentage (+10 = +10%), montant fixe (+5 = +5€, -5 = -5€), ou nouveau prix"}},"required":["filtre_type","type_modif","valeur"]}}},
    {"type":"function","function":{"name":"modifier_article","description":"Modifier un ou plusieurs champs d'un article","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"},"nom":{"type":"string"},"categorie":{"type":"string"},"marque":{"type":"string"},"genre":{"type":"string"},"Prix":{"type":"number"},"description":{"type":"string"},"caracteristiques":{"type":"string"},"materiaux":{"type":"string"},"usage":{"type":"string"},"mots_cles":{"type":"string"},"url_image":{"type":"string"}},"required":["id_shoes"]}}},
    {"type":"function","function":{"name":"ajouter_article","description":"Ajouter un nouvel article au catalogue","parameters":{"type":"object","properties":{"nom":{"type":"string"},"categorie":{"type":"string"},"marque":{"type":"string"},"genre":{"type":"string","description":"Mixte, Homme, ou Femme"},"prix":{"type":"number"},"description":{"type":"string"},"caracteristiques":{"type":"string"},"materiaux":{"type":"string"},"usage":{"type":"string"},"mots_cles":{"type":"string"},"url_image":{"type":"string"},"variants":{"type":"array","items":{"type":"object","properties":{"taille":{"type":"integer"},"couleur":{"type":"string"},"stock":{"type":"integer"}}}}},"required":["nom","categorie","marque","prix"]}}},
    {"type":"function","function":{"name":"supprimer_article","description":"Supprimer un article du catalogue","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"}},"required":["id_shoes"]}}},
    {"type":"function","function":{"name":"supprimer_commentaire","description":"Supprimer un commentaire","parameters":{"type":"object","properties":{"id_commentaire":{"type":"integer"}},"required":["id_commentaire"]}}},
    {"type":"function","function":{"name":"supprimer_commentaires_article","description":"Supprimer TOUS les commentaires d'un article","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"}},"required":["id_shoes"]}}},
    {"type":"function","function":{"name":"arrondir_prix","description":"Arrondir les prix des articles","parameters":{"type":"object","properties":{"methode":{"type":"string","description":"nearest, up, down, half, nine"},"filtre_type":{"type":"string","description":"categorie, marque, genre, ou tous"},"filtre_valeur":{"type":"string"}},"required":["methode"]}}},
]

async def fetch_context_data() -> str:
    async with httpx.AsyncClient(timeout=15.0) as client:
        headers = {"X-Admin-Token": ADMIN_ACTION_TOKEN}

        async def call(action, params={}):
            try:
                r = await client.post(PHP_ACTIONS_URL, json={"action": action, "params": params}, headers=headers)
                text = r.text.strip()
                if '{' in text:
                    text = text[text.index('{'):]
                data = json.loads(text)
                return data.get("data", []) if data.get("success") else []
            except Exception as e:
                print(f"[CONTEXT] Erreur {action}: {e}")
                return []

        articles     = await call("lister_articles")
        commandes    = await call("lister_commandes", {"limit": 50})
        clients      = await call("lister_clients",   {"limit": 100})
        commentaires = await call("lister_commentaires", {"limit": 50})
        stats        = await call("stats_globales")
        top_articles = await call("top_articles", {"limit": 10})
        ca_mois      = await call("ca_par_mois")

    lines = []
    lines.append("ARTICLES DU CATALOGUE :")
    for a in articles:
        lines.append(f"  article id={a.get('id_shoes')} nom={a.get('nom')} marque={a.get('marque')} categorie={a.get('categorie')} genre={a.get('genre')} prix={a.get('Prix')}€ stock={a.get('stock_total')}")

    lines.append("COMMANDES RECENTES :")
    for c in commandes:
        lines.append(f"  commande id={c.get('id_commande')} client={c.get('nom_client','?')} statut={c.get('statut')} total={c.get('total','?')}€ date={c.get('date_commande','?')}")

    lines.append("CLIENTS :")
    for c in clients:
        lines.append(f"  client id={c.get('id_client')} prenom={c.get('prenom','')} nom={c.get('nom','')} email={c.get('email','')} ca={c.get('ca_total','0')}€")

    lines.append("COMMENTAIRES RECENTS :")
    for c in commentaires:
        lines.append(f"  commentaire id={c.get('id_commentaire')} article_id={c.get('id_shoes')} article={c.get('nom_article','?')} note={c.get('note')}/5 auteur={c.get('prenom','')} {c.get('nom','')} texte={str(c.get('commentaire',''))[:80]}")

    lines.append("STATISTIQUES :")
    if isinstance(stats, dict):
        for k, v in stats.items():
            lines.append(f"  {k}={v}")

    lines.append("TOP ARTICLES VENDUS :")
    for a in top_articles:
        lines.append(f"  {a.get('nom_article')} vendus={a.get('total_vendu','?')} ca={a.get('ca','?')}€")

    lines.append("CA PAR MOIS :")
    for m in ca_mois:
        lines.append(f"  mois={m.get('mois','?')} ca={m.get('ca','?')}€")

    return "\n".join(lines)

def build_system_prompt(context_data: str = "") -> str:
    return f"""Tu es l'assistant IA de l'administrateur de PairIA, une boutique en ligne de chaussures.
Tu aides a gerer la boutique : commandes, catalogue, clients, commentaires, statistiques.

DONNEES ACTUELLES DE LA BOUTIQUE :
{context_data}

REGLES ABSOLUES :
- Tu as TOUTES les donnees ci-dessus. N'appelle JAMAIS un outil pour lire des donnees.
- N'invente JAMAIS de donnees, d'IDs, de noms ou de prix.
- Pour modifier le prix d'un article : lis son prix actuel dans ARTICLES DU CATALOGUE ci-dessus, calcule le nouveau prix final, puis appelle modifier_prix avec ce prix final. Exemple : article id=61 prix=120€, hausse de 5€ → appelle modifier_prix avec id_shoes=61 nouveau_prix=125.
- Utilise les outils UNIQUEMENT pour modifier, ajouter ou supprimer des donnees.
- Agis directement sans demander confirmation, SAUF pour les suppressions et les modifications de prix en lot.
- Reponds TOUJOURS en francais, de facon courte et directe.
- N'affiche JAMAIS de JSON ou de parametres techniques dans tes reponses.

CATEGORIES DISPONIBLES :
Baskets lifestyle, Baskets sport, Bottines, Danse, Espadrilles, Impermeables, Indoor, Marche, Minimalistes, Mocassins, Montantes legeres, Randonnee, Running, Sabots, Sandales, Securite, Slip-on, Talons, Training, Vegan

REGLES SUPPRESSION :
- L'ID est dans les donnees ci-dessus. Si l'admin donne un nom, trouve l'ID correspondant dans ARTICLES DU CATALOGUE, montre l'article trouve, demande confirmation, puis appelle supprimer_article avec cet ID.

STATUTS COMMANDES : en_attente -> payee -> expediee -> livree. Ne retrograde JAMAIS.
Pour plusieurs commandes, utilise modifier_statut_batch.

MODIFICATIONS DE PRIX EN LOT :
- Dis ce qui va se passer et attends confirmation avant d'appeler modifier_prix_batch.
- Pour une BAISSE : valeur negative. Pour une HAUSSE : valeur positive.

CREATION D'ARTICLE :
- Champs obligatoires : nom, categorie (dans la liste), marque, genre, prix.
- Champs optionnels : description, caracteristiques, materiaux, usage, mots_cles, url_image.
- Demande les champs obligatoires manquants un par un.
- Une fois que tu as tous les champs obligatoires, demande : "Avez-vous une image du produit ? Si oui uploadez-la pour que je remplisse automatiquement les details. Sinon je peux les demander manuellement ou les laisser vides."
- Quand tu as nom, categorie, marque, genre et prix et que l'admin a repondu sur l'image (ou dit non), reponds UNIQUEMENT avec ce texte exact : VARIANT_FORM_NEEDED:{{"nom":"...","categorie":"...","marque":"...","genre":"...","prix":0.0,"description":"...","caracteristiques":"...","materiaux":"...","usage":"...","mots_cles":"...","url_image":"..."}} en remplissant les valeurs reelles et en laissant vides les champs non fournis.
- Ne demande jamais les variantes directement, le formulaire s'en charge.
""".strip()

class Message(BaseModel):
    role: str
    content: str

class AdminChatRequest(BaseModel):
    question: str
    history: List[Message] = []
    admin_id: Optional[int] = None
    session_id: Optional[str] = None
    image_url: Optional[str] = None

class ReindexRequest(BaseModel):
    article_id: Optional[int] = None

async def call_php_action(action: str, params: dict) -> dict:
    print(f"[PHP] action={action} | params={params}")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                PHP_ACTIONS_URL,
                json={"action": action, "params": params},
                headers={"X-Admin-Token": ADMIN_ACTION_TOKEN},
            )
            print(f"[PHP] status={resp.status_code} | body={resp.text[:200]!r}")
            text = resp.text.strip()
            if '{' in text:
                text = text[text.index('{'):]
            return json.loads(text)
    except Exception as e:
        return {"success": False, "message": f"Erreur appel PHP : {e}", "data": None}

def format_result_for_llm(action: str, result: dict) -> str:
    if not result.get("success"):
        return f"ERREUR : {result.get('message', 'inconnue')}. STOP, ne rappelle pas cet outil."
    data = result.get("data")
    msg  = result.get("message", "")
    if data is None:
        return f"{msg}. ACTION TERMINEE AVEC SUCCES. Ne rappelle pas cet outil."
    if isinstance(data, list):
        if not data:
            return "Aucun resultat trouve pour cette recherche. Dis-le clairement a l'admin, par exemple : 'Il n'y a aucune commande en attente actuellement.'"
        lines = [f"{msg} ({len(data)} elements) :"]
        for item in data[:30]:
            lines.append("- " + " | ".join(f"{k}: {v}" for k, v in item.items()))
        return "\n".join(lines)
    if isinstance(data, dict):
        lines = [msg]
        for k, v in data.items():
            if isinstance(v, list):
                lines.append(f"{k} ({len(v)}) :")
                for item in v[:15]:
                    if isinstance(item, dict):
                        lines.append("  - " + " | ".join(f"{ik}: {iv}" for ik, iv in item.items()))
                    else:
                        lines.append(f"  - {item}")
            else:
                lines.append(f"{k}: {v}")
        return "\n".join(lines)
    return f"{msg}. ACTION TERMINEE AVEC SUCCES."

def run_reindex(article_id: int = None):
    api_url = os.environ.get("CLIENT_API_URL", "http://api:8000")
    token   = os.environ.get("ADMIN_ACTION_TOKEN", "")
    try:
        httpx.post(f"{api_url}/reindex", json={"article_id": article_id},
                   headers={"X-Admin-Token": token}, timeout=5.0)
        print(f"[REINDEX] Demande envoyee (article_id={article_id}).")
    except Exception as e:
        print(f"[REINDEX] Erreur : {e}")

@app.post("/admin/reindex")
async def reindex(request: ReindexRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_reindex, request.article_id)
    return {"status": "started", "article_id": request.article_id}

@app.post("/admin/chat/stream")
async def admin_chat_stream(request: AdminChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    print(f"[ADMIN] session={session_id[:8]} | question: {request.question!r}")

    context_data  = await fetch_context_data()
    system_prompt = build_system_prompt(context_data)

    messages = [{"role": "system", "content": system_prompt}]

    if session_id in _session_messages:
        for m in _session_messages[session_id]:
            if m["role"] != "system":
                messages.append(m)

    if request.image_url:
        if not any("image_url" in str(m.get("content", "")) for m in messages):
            messages.append({
                "role": "system",
                "content": f"[CONTEXTE] L'admin a uploade une image. URL : {request.image_url} — utilise-la comme url_image lors de l'appel a ajouter_article."
            })
        question = f"[Image: {request.image_url}] {request.question}"
    else:
        question = request.question

    # Si la question contient un nom d'article, injecte l'ID dans la question
    # Si la question fait reference a "cette commande/cet article" sans ID, cherche le dernier ID mentionne dans l'historique
    if any(w in question.lower() for w in ["cette commande", "cet article", "cette article"]) and "ID=" not in question:
        import re as _re2
        hist_pour_recherche = _session_messages.get(session_id, [])
        for m in reversed(hist_pour_recherche):
            txt = m.get("content", "")
            match_id = _re2.search(r"commande\s*(?:n[uo°]*m?[eé]ro\s*|#\s*)?(\d+)", txt, _re2.IGNORECASE) if "commande" in question.lower() else _re2.search(r"article\s*(?:#|id\s*)?(\d+)", txt, _re2.IGNORECASE)
            if match_id:
                if "commande" in question.lower():
                    question = question + f" (id_commande={match_id.group(1)})"
                else:
                    question = question + f" (id_shoes={match_id.group(1)})"
                print(f"[REF] ID trouve dans historique: {match_id.group(1)}")
                break

    mots_action_nom = ["supprim", "efface", "enleve", "retire", "delete", "augment", "diminu", "baisse", "monte", "passe", "modifi", "change", "stock"]
    if any(w in question.lower() for w in mots_action_nom):
        for line in context_data.split("\n"):
            if "article id=" in line:
                parts = {p.split("=")[0].strip(): p.split("=")[1].strip() for p in line.strip().split(" ") if "=" in p}
                nom = parts.get("nom", "").lower()
                if nom and nom in question.lower():
                    question = question + f" (ID={parts.get('id')})"
                    print(f"[SUPPRESSION] ID trouve automatiquement: {parts.get('id')}")
                    break

    # Court-circuit : creation directe d'article depuis le formulaire JS (evite les hallucinations du LLM sur cette etape critique)
    if question.startswith("Cree l'article avec ces donnees :"):
        try:
            import re as _re
            m1 = _re.search(r"donnees : (\{.*?\}) et ces variantes : (\[.*\])", question)
            if m1:
                article_payload = json.loads(m1.group(1))
                variants_payload = json.loads(m1.group(2))
                article_payload["variants"] = variants_payload
                yield_events = []
                async def _direct_create():
                    status_text = ACTION_STATUS_TEXTS.get("ajouter_article", "J'ajoute l'article…")
                    out = []
                    out.append(f"data: {json.dumps({'type': 'thinking'})}\n\n")
                    out.append(f"data: {json.dumps({'type': 'action_start', 'action': 'ajouter_article', 'status_text': status_text})}\n\n")
                    result = await call_php_action("ajouter_article", article_payload)
                    out.append(f"data: {json.dumps({'type': 'action_result', 'action': 'ajouter_article', 'result': result})}\n\n")
                    if result.get("success"):
                        article_id = result.get('data', {}).get('id_shoes') if result.get('data') else None
                        run_reindex(article_id)
                        content = f"L'article \"{article_payload.get('nom')}\" a ete cree avec succes."
                    else:
                        content = f"Erreur lors de la creation : {result.get('message', 'inconnue')}"
                    _session_messages[session_id].append({"role": "user", "content": "Article cree."})
                    _session_messages[session_id].append({"role": "assistant", "content": content})
                    for char in content:
                        out.append(f"data: {json.dumps({'chunk': char})}\n\n")
                    out.append("data: [DONE]\n\n")
                    return out
                events = await _direct_create()
                async def _stream_direct():
                    for e in events:
                        yield e
                return StreamingResponse(_stream_direct(), media_type="text/event-stream")
        except Exception as e:
            print(f"[ADMIN] erreur creation directe: {e}")


    # Court-circuit : modification directe du stock des variantes depuis le formulaire JS
    if question.startswith("Modifie le stock des variantes :"):
        try:
            import re as _re_stock
            m2 = _re_stock.search(r"variantes : (\[.*\])", question)
            if m2:
                variantes_payload = json.loads(m2.group(1))
                async def _direct_stock():
                    status_text = "Je mets a jour le stock…"
                    out = []
                    out.append(f"data: {json.dumps({'type': 'thinking'})}\n\n")
                    out.append(f"data: {json.dumps({'type': 'action_start', 'action': 'modifier_stock_variantes', 'status_text': status_text})}\n\n")
                    result = await call_php_action("modifier_stock_variantes", {"variantes": variantes_payload})
                    out.append(f"data: {json.dumps({'type': 'action_result', 'action': 'modifier_stock_variantes', 'result': result})}\n\n")
                    if result.get("success"):
                        article_id = result.get('data', {}).get('id_shoes') if result.get('data') else None
                        if article_id:
                            run_reindex(article_id)
                        content = "Le stock des variantes a ete mis a jour."
                    else:
                        content = f"Erreur lors de la mise a jour du stock : {result.get('message', 'inconnue')}"
                    _session_messages[session_id].append({"role": "user", "content": "Stock mis a jour."})
                    _session_messages[session_id].append({"role": "assistant", "content": content})
                    for char in content:
                        out.append(f"data: {json.dumps({'chunk': char})}\n\n")
                    out.append("data: [DONE]\n\n")
                    return out
                events2 = await _direct_stock()
                async def _stream_direct2():
                    for e in events2:
                        yield e
                return StreamingResponse(_stream_direct2(), media_type="text/event-stream")
        except Exception as e:
            print(f"[ADMIN] erreur modification stock directe: {e}")

        except Exception as e:
            print(f"[ADMIN] erreur creation directe: {e}")

    messages.append({"role": "user", "content": question})

    if session_id not in _session_messages:
        _session_messages[session_id] = []
    if len(_session_messages[session_id]) > 12:
        _session_messages[session_id] = _session_messages[session_id][-12:]
    _session_messages[session_id].append({"role": "user", "content": question})

    async def generate():
        had_tool_calls = False
        try:
            yield f"data: {json.dumps({'type': 'thinking'})}\n\n"

            max_iterations = 8
            iteration = 0
            last_tool_call = None
            same_tool_count = 0

            # Detection question de suivi
            mots_suivi = ['elle ', 'il ', 'lui ', ' ca ', 'ca ', 'cet article', 'cette commande', 'celui', 'celle']
            historique_recent = _session_messages.get(session_id, [])
            mots_action_followup = ["passe", "modifi", "supprim", "ajout", "change", "augment", "diminu", "baisse", "monte", "efface", "enleve", "retire", "delete", "arrondi", "cree", "crée", "stock"]
            est_question_action = any(w in question.lower() for w in mots_action_followup)
            est_suivi = (any(w in (' ' + question.lower() + ' ') for w in mots_suivi) and len(historique_recent) >= 2 and len(question) < 80 and not est_question_action)
            if est_suivi:
                try:
                    contexte_recent = historique_recent[-6:]
                    sys_msg_suivi = {'role': 'system', 'content': 'Tu es un assistant admin. Reponds en francais en une ou deux phrases naturelles, jamais de liste a puces, en te basant sur la conversation precedente.'}
                    msgs_followup = [sys_msg_suivi] + contexte_recent
                    reponse_suivi = ollama_client.chat(
                        model=OLLAMA_MODEL,
                        messages=msgs_followup,
                        options={'temperature': 0.2, 'num_predict': 500},
                        keep_alive="30m",
                    )
                    content = reponse_suivi['message']['content'].strip()
                    messages.append({'role': 'assistant', 'content': content})
                    _session_messages[session_id].append({'role': 'assistant', 'content': content})
                    for char in content:
                        yield f"data: {json.dumps({'chunk': char})}\n\n"
                    return
                except Exception as e:
                    print(f'[ADMIN] erreur suivi: {e}')


            while iteration < max_iterations:
                iteration += 1
                response = ollama_client.chat(
                    model=OLLAMA_MODEL,
                    messages=messages,
                    tools=TOOLS,
                    stream=False,
                    options={"temperature": 0.1, "num_predict": 4096},
                    keep_alive="30m",
                )

                msg = response["message"]
                print(f"[ADMIN] iter={iteration} | tool_calls={bool(msg.get('tool_calls'))} | content={msg.get('content','')[:80]!r}")

                if not msg.get("tool_calls"):
                    content = msg.get("content", "").strip()

                    # Detecte VARIANT_FORM_NEEDED
                    if content.startswith("VARIANT_FORM_NEEDED:"):
                        try:
                            article_data = json.loads(content.split("VARIANT_FORM_NEEDED:")[1])
                        except Exception:
                            article_data = {}
                        yield f"data: {json.dumps({'type': 'variant_form', 'article': article_data})}\n\n"
                        break


                    noms_outils = [t["function"]["name"] for t in TOOLS]
                    content_stripped = content.strip()
                    is_fake_tool_call = (
                        ('"name"' in content[:100] and ('"arguments"' in content[:200] or '"parameters"' in content[:200] or '"type":"function"' in content[:50] or content_stripped.startswith('{')))
                        or any(content_stripped.startswith(n + "(") for n in noms_outils)
                    )
                    if is_fake_tool_call:
                        print(f"[ADMIN] contenu complet faux tool call: {content!r}")
                        import re as _re3
                        looks_like_statut_action = "modifier_statut" in content.lower()
                        m_id_q = _re3.search(r'id_commande=(\d+)', question)
                        m_statut_q = _re3.search(r'\b(en_attente|pay[eé]e|exp[eé]di[eé]e|livr[eé]e|annul[eé]e)\b', question, _re3.IGNORECASE)
                        if looks_like_statut_action and m_id_q and m_statut_q:
                            id_extrait = int(m_id_q.group(1))
                            statut_brut = m_statut_q.group(1).lower()
                            mapping_statuts = {"en_attente": "en_attente", "payee": "payée", "payée": "payée", "expediee": "expédiée", "expédiée": "expédiée", "livree": "livrée", "livrée": "livrée", "annulee": "annulée", "annulée": "annulée"}
                            statut_extrait = mapping_statuts.get(statut_brut, statut_brut)
                            print(f"[ADMIN] extraction directe depuis faux tool call: id={id_extrait}, statut={statut_extrait}")
                            yield f"data: {json.dumps({'type': 'action_start', 'action': 'modifier_statut_commande', 'status_text': 'Je mets a jour le statut...'})}\n\n"
                            result = await call_php_action("modifier_statut_commande", {"id_commande": id_extrait, "nouveau_statut": statut_extrait})
                            yield f"data: {json.dumps({'type': 'action_result', 'action': 'modifier_statut_commande', 'result': result})}\n\n"
                            if result.get("success"):
                                content = f"Le statut de la commande #{id_extrait} a ete mis a jour : {statut_extrait}."
                            else:
                                content = f"Erreur : {result.get('message', 'inconnue')}"
                            messages.append({"role": "assistant", "content": content})
                            _session_messages[session_id].append({"role": "assistant", "content": content})
                            for char in content:
                                yield f"data: {json.dumps({'chunk': char})}\n\n"
                            return
                    if is_fake_tool_call and not had_tool_calls and iteration == 1:
                        print(f"[ADMIN] faux tool call detecte, retry unique: {content[:100]!r}")
                        messages.append({"role": "user", "content": f"Tu as ecrit le JSON en texte au lieu d'utiliser le mecanisme d'appel d'outil. Refais EXACTEMENT la meme action avec les memes parametres, via le mecanisme natif d'appel d'outil (tool call)."})
                        continue
                    if is_fake_tool_call and iteration > 1:
                        content = "Je n'ai pas pu executer cette action correctement. Pouvez-vous reformuler votre demande avec plus de precision (par exemple en donnant l'ID exact) ?"
                    if is_fake_tool_call:
                        content = ""
                    if not content and had_tool_calls:
                        content = "C'est fait."
                    if not content and not had_tool_calls:
                        content = "Je n'ai pas compris, pouvez-vous reformuler ?"
                    if not content and not had_tool_calls:
                        content = "Je n'ai pas compris, pouvez-vous reformuler ?"

                    messages.append({"role": "assistant", "content": content})
                    _session_messages[session_id].append({"role": "assistant", "content": content})

                    for char in content:
                        yield f"data: {json.dumps({'chunk': char})}\n\n"
                    break

                had_tool_calls = True
                tool_calls = msg["tool_calls"]

                # Detection boucle : meme outil, memes args deux fois de suite
                current_tool = str(tool_calls)
                if current_tool == last_tool_call:
                    same_tool_count += 1
                    if same_tool_count >= 2:
                        content = "C'est fait."
                        messages.append({"role": "assistant", "content": content})
                        _session_messages[session_id].append({"role": "assistant", "content": content})
                        for char in content:
                            yield f"data: {json.dumps({'chunk': char})}\n\n"
                        break
                else:
                    same_tool_count = 0
                last_tool_call = current_tool

                messages.append({"role": "assistant", "content": "", "tool_calls": tool_calls})
                _session_messages[session_id].append({"role": "assistant", "content": "", "tool_calls": tool_calls})

                for tool_call in tool_calls:
                    fn_name = tool_call["function"]["name"]
                    fn_args = tool_call["function"].get("arguments", {})
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except Exception:
                            fn_args = {}

                    int_params   = ["id_commande","id_shoes","id_client","id_commentaire","limit","nouveau_stock","seuil"]
                    float_params = ["nouveau_prix","valeur","prix"]
                    for k, v in fn_args.items():
                        if k in int_params:
                            try: fn_args[k] = int(v)
                            except (ValueError, TypeError): pass
                        if k in float_params: fn_args[k] = float(v)
                    # Cast special pour 'ids' (liste d'entiers, parfois envoyee comme string par le LLM)
                    if "ids" in fn_args and not isinstance(fn_args["ids"], list):
                        ids_val = fn_args["ids"]
                        if isinstance(ids_val, str):
                            try:
                                ids_val = json.loads(ids_val)
                            except Exception:
                                ids_val = [int(x.strip()) for x in ids_val.strip("[]").split(",") if x.strip().isdigit()]
                        fn_args["ids"] = [int(x) for x in ids_val] if isinstance(ids_val, list) else [int(ids_val)]

                    print(f"[DEBUG] fn_args avant interception: {fn_args}")
                    # Interception ajouter_article sans variantes
                    if fn_name == "ajouter_article" and not fn_args.get("variants"):
                        champs_garder = ["nom", "marque", "categorie", "genre", "prix"]
                        article_data = {k: v for k, v in fn_args.items() if k in champs_garder}
                        yield f"data: {json.dumps({'type': 'variant_form', 'article': article_data})}\n\n"
                        return

                    # Validation statut commande - normalise les variantes d'accord, bloque seulement le reste
                    STATUTS_VALIDES = ["en_attente", "payée", "expédiée", "livrée", "annulée"]
                    NORMALISATION_STATUTS = {
                        "en_attente": "en_attente", "attente": "en_attente",
                        "payee": "payée", "payé": "payée", "paye": "payée", "payée": "payée",
                        "expedie": "expédiée", "expédié": "expédiée", "expedié": "expédiée", "expediee": "expédiée", "expédiée": "expédiée",
                        "livre": "livrée", "livré": "livrée", "livree": "livrée", "livrée": "livrée",
                        "annule": "annulée", "annulé": "annulée", "annulee": "annulée", "annulée": "annulée",
                    }
                    if fn_name in ("modifier_statut_commande", "modifier_statut_batch"):
                        statut_demande = fn_args.get("nouveau_statut", "")
                        statut_normalise = NORMALISATION_STATUTS.get(statut_demande.lower().strip(), None)
                        if statut_normalise:
                            fn_args["nouveau_statut"] = statut_normalise
                            print(f"[ADMIN] statut normalise: {statut_demande!r} -> {statut_normalise!r}")
                        elif statut_demande not in STATUTS_VALIDES:
                            print(f"[ADMIN] statut invalide detecte: {statut_demande!r}, action bloquee")
                            messages.append({"role": "tool", "content": f"ERREUR : '{statut_demande}' n'est pas un statut valide. Cette action n'a pas ete executee. Si la question d'origine ne concernait pas un changement de statut de commande, reponds directement en texte avec les donnees deja fournies dans le contexte, sans appeler aucun outil.", "name": fn_name})
                            continue

                    # Blocage suppression non demandee
                    if fn_name == "supprimer_article" and not any(w in " ".join([m.get("content","") for m in messages if m["role"]=="user"]).lower() for w in ["supprim", "efface", "enleve", "retire", "delete"]):
                        messages.append({"role": "tool", "content": "INTERDIT : supprimer_article ne peut pas etre appele automatiquement. Stop.", "name": fn_name})
                        continue

                    # Correction automatique prix - on recalcule TOUJOURS nous-memes depuis la question d'origine
                    if fn_name == "modifier_prix" and "nouveau_prix" in fn_args:
                        id_shoes = fn_args.get("id_shoes")
                        q_lower = question.lower()
                        match_montant = re.search(r"(\d+[.,]?\d*)\s*(?:€|euros?)", q_lower)
                        montant = float(match_montant.group(1).replace(",", ".")) if match_montant else None

                        mots_hausse = ["augment", "monte", "hausse"]
                        mots_baisse = ["baisse", "diminu", "reduit", "réduit"]
                        mots_fixe = ["passe", "mets", "met le prix", "fixe le prix", "change le prix a", "change le prix à"]

                        is_hausse = any(w in q_lower for w in mots_hausse)
                        is_baisse = any(w in q_lower for w in mots_baisse)
                        is_fixe = any(w in q_lower for w in mots_fixe)

                        if montant is not None and (is_hausse or is_baisse):
                            detail = await call_php_action("detail_article", {"id_shoes": id_shoes})
                            if detail.get("success") and detail.get("data"):
                                prix_actuel = float(detail["data"].get("Prix", 0))
                                delta = montant if is_hausse else -montant
                                fn_args["nouveau_prix"] = round(prix_actuel + delta, 2)
                                print(f"[PRIX] Recalcul depuis question: {prix_actuel} {'+' if is_hausse else '-'} {montant} = {fn_args['nouveau_prix']}")
                        elif montant is not None and is_fixe:
                            fn_args["nouveau_prix"] = montant
                            print(f"[PRIX] Prix fixe depuis question: {montant}")

                    status_text = ACTION_STATUS_TEXTS.get(fn_name, "Je traite la demande…")
                    yield f"data: {json.dumps({'type': 'action_start', 'action': fn_name, 'status_text': status_text})}\n\n"

                    result    = await call_php_action(fn_name, fn_args)
                    formatted = format_result_for_llm(fn_name, result)

                    yield f"data: {json.dumps({'type': 'action_result', 'action': fn_name, 'result': result})}\n\n"
                    # Outil lister_variantes -> carte interactive de gestion du stock
                    if fn_name == "lister_variantes" and result.get("success"):
                        data_variantes = result.get("data", {})
                        yield f"data: {json.dumps({'type': 'stock_form', 'nom': data_variantes.get('nom'), 'id_shoes': fn_args.get('id_shoes'), 'variantes': data_variantes.get('variantes', [])})}\n\n"
                        content = f"Voici les variantes de {data_variantes.get('nom', 'cet article')}."
                        messages.append({"role": "assistant", "content": content})
                        _session_messages[session_id].append({"role": "assistant", "content": content})
                        for char in content:
                            yield f"data: {json.dumps({'chunk': char})}\n\n"
                        return

                    # Pour les outils de detail/lecture precise, formulation dediee sans le system prompt complet
                    ACTIONS_FORMULATION_DEDIEE = ["detail_commande", "detail_article", "rechercher_article", "rechercher_client", "commandes_client"]
                    if fn_name in ACTIONS_FORMULATION_DEDIEE and result.get("success"):
                        try:
                            reponse_dediee = ollama_client.chat(
                                model=OLLAMA_MODEL,
                                messages=[
                                    {"role": "system", "content": "Tu es un assistant admin. Reponds en francais en UNE OU DEUX PHRASES NATURELLES (jamais de liste a puces, jamais de markdown), en te basant UNIQUEMENT sur les donnees fournies. Cite les details specifiques demandes (articles, noms, tailles, couleurs, etc.) directement dans la phrase."},
                                    {"role": "user", "content": question},
                                    {"role": "tool", "content": formatted, "name": fn_name},
                                ],
                                options={"temperature": 0.2, "num_predict": 500},
                                keep_alive="30m",
                            )
                            content = reponse_dediee["message"]["content"].strip()
                            messages.append({"role": "assistant", "content": content})
                            _session_messages[session_id].append({"role": "tool", "content": formatted, "name": fn_name})
                            _session_messages[session_id].append({"role": "assistant", "content": content})
                            for char in content:
                                yield f"data: {json.dumps({'chunk': char})}\n\n"
                            return
                        except Exception as e:
                            print(f"[ADMIN] erreur formulation dediee: {e}")


                    # Stop apres toute action de modification reussie
                    ACTIONS_STOP_APRES_SUCCES = ["modifier_prix", "modifier_prix_batch", "modifier_stock", "modifier_article", "modifier_statut_commande", "modifier_statut_batch", "supprimer_article", "supprimer_commentaire", "supprimer_commentaires_article", "ajouter_article", "arrondir_prix"]
                    if fn_name in ACTIONS_STOP_APRES_SUCCES and result.get("success"):
                        content = "C'est fait."
                        messages.append({"role": "assistant", "content": content})
                        _session_messages[session_id].append({"role": "assistant", "content": content})
                        for char in content:
                            yield f"data: {json.dumps({'chunk': char})}\n\n"
                        return


                    messages.append({"role": "tool", "content": formatted, "name": fn_name})
                    _session_messages[session_id].append({"role": "tool", "content": formatted, "name": fn_name})

                    if fn_name in ['ajouter_article', 'modifier_article', 'supprimer_article']:
                        article_id = result.get('data', {}).get('id_shoes') if result.get('data') else None
                        run_reindex(article_id)

            else:
                msg_timeout = "Je n'ai pas pu traiter cette demande. Reformulez svp."
                yield f"data: {json.dumps({'chunk': msg_timeout})}\n\n"

            if len(_session_messages) > 100:
                oldest = list(_session_messages.keys())[0]
                del _session_messages[oldest]

        except Exception as e:
            yield f"data: {json.dumps({'chunk': f'Erreur : {str(e)}'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/admin/health")

class ImageAnalyzeRequest(BaseModel):
    image_b64: str

@app.post("/admin/analyze-image")
async def analyze_image(request: ImageAnalyzeRequest):
    try:
        response = ollama_client.chat(
            model="llava:7b",
            messages=[{
                "role": "user",
                "content": """Tu analyses une image de chaussure pour un catalogue e-commerce francais. Reponds UNIQUEMENT en JSON valide sans markdown, TOUJOURS EN FRANCAIS.

Voici des exemples de bonnes descriptions issues de notre catalogue :

Exemple 1 - Nova Air Lifestyle :
description: "Les Nova Air Lifestyle sont conçues pour offrir un confort optimal au quotidien. Leur tige en mesh respirant assure une excellente circulation de l'air même lors des longues journées. La semelle en EVA absorbe efficacement les chocs à chaque pas, réduisant la fatigue. Leur design épuré et moderne s'adapte aussi bien à une tenue décontractée qu'à un look urbain soigné."
caracteristiques: "Ultra légères, Respirantes, Semelle amortissante, Usage quotidien, Lacets plats"
materiaux: "Mesh respirant, semelle EVA"
usage: "Ville, courses, sorties week-end"
mots_cles: "lifestyle, confort, légères, urbain, quotidien"

Exemple 2 - RetroWave 90s :
description: "Inspirées des icônes des années 90, les RetroWave 90s revivent avec une touche moderne. Leur tige en cuir synthétique vieilli et leur semelle épaisse en caoutchouc rappellent les classiques du streetwear, tout en offrant le confort contemporain."
caracteristiques: "Style rétro années 90, Semelle épaisse, Confort toute journée, Languette rembourrée"
materiaux: "Cuir synthétique vieilli, caoutchouc"
usage: "Mode rétro, style urbain décalé"
mots_cles: "rétro, 90s, streetwear, vintage, urbain"

Maintenant analyse cette image et reponds avec ce JSON exact :
{"description": "description commerciale detaillee de 2-3 phrases en francais", "caracteristiques": "liste de 4-6 caracteristiques separees par des virgules", "materiaux": "materiaux principaux en francais", "usage": "usage recommande en francais", "mots_cles": "6-8 mots cles en francais separes par des virgules"}

Reponds UNIQUEMENT avec le JSON, rien d'autre.""",
                "images": [request.image_b64]
            }],
            options={"temperature": 0.1}
        )
        content = response["message"]["content"].strip()
        print(f"[LLAVA] reponse brute: {content[:500]}")
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        data = json.loads(content)
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "message": str(e)}

def health():
    return {"status": "ok", "service": "admin-chatbot"}
