# ia/admin_main.py
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
    {"type":"function","function":{"name":"modifier_statut_commande","description":"Modifier le statut d'UNE commande","parameters":{"type":"object","properties":{"id_commande":{"type":"integer"},"nouveau_statut":{"type":"string","description":"en_attente, payée, expédiée, livrée, annulée"}},"required":["id_commande","nouveau_statut"]}}},
    {"type":"function","function":{"name":"modifier_statut_batch","description":"Modifier le statut de PLUSIEURS commandes en une fois","parameters":{"type":"object","properties":{"ids":{"type":"array","items":{"type":"integer"},"description":"Liste des IDs de commandes"},"nouveau_statut":{"type":"string"}},"required":["ids","nouveau_statut"]}}},
    {"type":"function","function":{"name":"modifier_prix","description":"Modifier le prix d'UN article. nouveau_prix est le NOUVEAU prix FINAL en euros, pas une différence.","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"},"nouveau_prix":{"type":"number","description":"Le nouveau prix FINAL de l'article en euros. Exemple: si prix actuel=120€ et hausse de 5€, envoyer 125."}},"required":["id_shoes","nouveau_prix"]}}},
    {"type":"function","function":{"name":"modifier_stock","description":"Modifier le stock d'un article","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"},"nouveau_stock":{"type":"integer"}},"required":["id_shoes","nouveau_stock"]}}},
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
        lines.append(f"  {a.get('nom')} ({a.get('marque')}) vendus={a.get('quantite_vendue','?')} ca={a.get('ca','?')}€")

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
            return "Aucun resultat."
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

    messages.append({"role": "user", "content": question})

    if session_id not in _session_messages:
        _session_messages[session_id] = []
    _session_messages[session_id].append({"role": "user", "content": question})

    async def generate():
        had_tool_calls = False
        try:
            yield f"data: {json.dumps({'type': 'thinking'})}\n\n"

            max_iterations = 8
            iteration = 0
            last_tool_call = None
            same_tool_count = 0

            while iteration < max_iterations:
                iteration += 1

                response = ollama_client.chat(
                    model=OLLAMA_MODEL,
                    messages=messages,
                    tools=TOOLS,
                    stream=False,
                    options={"temperature": 0.1, "num_predict": 4096},
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


                    is_fake_tool_call = ('"name"' in content[:100] and ('"arguments"' in content[:200] or '"parameters"' in content[:200] or '"type":"function"' in content[:50] or content.strip().startswith('{')))
                    if is_fake_tool_call and not had_tool_calls and iteration < max_iterations:
                        print(f"[ADMIN] faux tool call detecte, retry: {content[:100]!r}")
                        messages.append({"role": "user", "content": f"Tu as ecrit le JSON en texte au lieu d'utiliser le mecanisme d'appel d'outil. Refais exactement la meme action que tu viens de tenter, mais via le mecanisme natif d'appel d'outil (tool call), sans rien ecrire en texte."})
                        continue
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

                    print(f"[DEBUG] fn_args avant interception: {fn_args}")
                    # Interception ajouter_article sans variantes
                    if fn_name == "ajouter_article" and not fn_args.get("variants"):
                        champs_garder = ["nom", "marque", "categorie", "genre", "prix"]
                        article_data = {k: v for k, v in fn_args.items() if k in champs_garder}
                        yield f"data: {json.dumps({'type': 'variant_form', 'article': article_data})}\n\n"
                        return

                    # Blocage suppression non demandee
                    if fn_name == "supprimer_article" and not any(w in " ".join([m.get("content","") for m in messages if m["role"]=="user"]).lower() for w in ["supprim", "efface", "enleve", "retire", "delete"]):
                        messages.append({"role": "tool", "content": "INTERDIT : supprimer_article ne peut pas etre appele automatiquement. Stop.", "name": fn_name})
                        continue

                    # Correction automatique prix
                    if fn_name == "modifier_prix" and "nouveau_prix" in fn_args:
                        nouveau_prix = fn_args["nouveau_prix"]
                        print(f"[DEBUG] nouveau_prix={nouveau_prix}, test < 30 = {nouveau_prix < 30}")
                        if nouveau_prix < 30:
                            id_shoes = fn_args.get("id_shoes")
                            detail = await call_php_action("detail_article", {"id_shoes": id_shoes})
                            if detail.get("success") and detail.get("data"):
                                prix_actuel = float(detail["data"].get("Prix", 0))
                                fn_args["nouveau_prix"] = round(prix_actuel + nouveau_prix, 2)
                                print(f"[PRIX] Correction: {nouveau_prix} + {prix_actuel} = {fn_args['nouveau_prix']}")

                    status_text = ACTION_STATUS_TEXTS.get(fn_name, "Je traite la demande…")
                    yield f"data: {json.dumps({'type': 'action_start', 'action': fn_name, 'status_text': status_text})}\n\n"

                    result    = await call_php_action(fn_name, fn_args)
                    formatted = format_result_for_llm(fn_name, result)

                    yield f"data: {json.dumps({'type': 'action_result', 'action': fn_name, 'result': result})}\n\n"

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
