// js/voice.js
// Reconnaissance vocale via Whisper (local) + MediaRecorder API

let mediaRecorder = null;
let audioChunks = [];
let isListening = false;
let recordingStream = null;
let isCancelled = false; // ✅ Flag d'annulation

let _ttsUtterance = null; // utterance en cours
let _ttsSpeakingBtn = null; // bouton actif

function voiceSupported() {
  return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
}

function toggleVoice() {
  isListening ? stopVoice() : startVoice();
}

async function startVoice() {
  try {
    recordingStream = await navigator.mediaDevices.getUserMedia({
      audio: true,
    });
  } catch (err) {
    alert("Micro refusé : " + err.message);
    return;
  }

  audioChunks = [];
  isListening = true;
  isCancelled = false;

  const btn = document.getElementById("voice-btn");
  const input = document.getElementById("chat-input");

  if (btn) {
    btn.classList.add("listening");
    btn.textContent = "🔴";
    btn.title = "Cliquer pour arrêter et transcrire";
  }
  if (input) input.placeholder = "Enregistrement en cours...";

  // affiche le bouton d'annulation pendant l'enregistrement
  _showCancelBtn();

  // Détection du meilleur codec disponible
  let options = {};
  if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
    options.mimeType = "audio/webm;codecs=opus";
  } else if (MediaRecorder.isTypeSupported("audio/webm")) {
    options.mimeType = "audio/webm";
  } else if (MediaRecorder.isTypeSupported("audio/ogg;codecs=opus")) {
    options.mimeType = "audio/ogg;codecs=opus";
  }

  console.log("[VOICE] Codec :", options.mimeType || "default");

  mediaRecorder = new MediaRecorder(recordingStream, options);

  mediaRecorder.ondataavailable = (event) => {
    if (event.data.size > 0) audioChunks.push(event.data);
  };

  mediaRecorder.onstop = async () => {
    if (isCancelled) {
      _hideCancelBtn();
      resetVoiceBtn();
      return;
    }

    const audioBlob = new Blob(audioChunks, {
      type: options.mimeType || "audio/webm",
    });

    if (audioBlob.size === 0) {
      console.error("[VOICE] Audio vide");
      _hideCancelBtn();
      resetVoiceBtn();
      return;
    }

    const btn = document.getElementById("voice-btn");
    const input = document.getElementById("chat-input");

    if (btn) {
      btn.textContent = "⏳";
      btn.title = "Transcription en cours...";
    }
    if (input) {
      input.placeholder = "Transcription en cours...";
      //  désactiver l'input pendant la transcription
      // pour éviter que l'utilisateur tape pendant l'affichage mot par mot
      input.disabled = true;
    }

    const formData = new FormData();
    formData.append("file", audioBlob, "audio.webm");

    try {
      const response = await fetch("http://127.0.0.1:8000/transcribe", {
        method: "POST",
        body: formData,
      });

      if (isCancelled) {
        if (input) input.disabled = false;
        _hideCancelBtn();
        resetVoiceBtn();
        return;
      }

      let data;
      try {
        data = await response.json();
        if (data.language) {
          await _mettreAjourLangue(data.language);
        }
        console.log("[WHISPER] réponse :", data);
      } catch (e) {
        console.error("[VOICE] Réponse non JSON :", e);
        if (input) input.disabled = false;
        _hideCancelBtn();
        resetVoiceBtn();
        return;
      }

      if (data.success && data.text && data.text.trim().length > 0) {
        //réactiver l'input AVANT l'affichage mot par mot
        if (input) input.disabled = false;

        //  await garantit que l'affichage est TERMINÉ
        // avant d'envoyer — avant le setTimeout causait une course
        await _afficherMotParMot(data.text, input);

        // ✅ Envoie seulement si pas annulé et texte présent
        if (!isCancelled && input && input.value.trim()) {
          sendFromInput();
        }
      } else {
        if (input) {
          input.disabled = false;
          input.placeholder = "Rien détecté — réessayez en parlant plus fort";
          setTimeout(() => {
            if (input && !input.value)
              input.placeholder = "Posez votre question...";
          }, 3000);
        }
        console.warn("[WHISPER] pas de texte :", data.error);
      }
    } catch (err) {
      console.error("[VOICE] Erreur envoi audio :", err);
      if (input) {
        input.disabled = false;
        input.placeholder = "Erreur de transcription. Réessayez.";
        setTimeout(() => {
          if (input && !input.value)
            input.placeholder = "Posez votre question...";
        }, 3000);
      }
    }

    _hideCancelBtn();
    resetVoiceBtn();
  };

  mediaRecorder.start(200);
}

/**
 * Affiche le texte mot par mot dans l'input pour simuler la transcription
 * Délai de 60ms entre chaque mot
 */
async function _afficherMotParMot(texte, input) {
  const mots = texte.split(" ");
  input.value = "";

  for (let i = 0; i < mots.length; i++) {
    //  Stop si l'utilisateur annule pendant l'affichage
    if (isCancelled) {
      input.value = "";
      return;
    }
    input.value += (i > 0 ? " " : "") + mots[i];
    // Délai entre chaque mot : 60ms → donne l'impression de frappe en temps réel
    await new Promise((resolve) => setTimeout(resolve, 60));
  }
}

/**
 * Arrête l'enregistrement normalement (pour transcrire)
 */
function stopVoice() {
  isListening = false;
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  if (recordingStream) {
    recordingStream.getTracks().forEach((t) => t.stop());
    recordingStream = null;
  }
}

/**
 * AJOUT : annule l'enregistrement ou la transcription en cours
 * L'utilisateur peut reprendre l'enregistrement ou écrire manuellement
 */
function cancelVoice() {
  isCancelled = true;
  isListening = false;

  // Arrête l'enregistrement sans déclencher la transcription
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  if (recordingStream) {
    recordingStream.getTracks().forEach((t) => t.stop());
    recordingStream = null;
  }

  const input = document.getElementById("chat-input");
  if (input) {
    input.value = "";
    input.placeholder = "Posez votre question...";
    //  Remet le focus sur l'input pour que l'utilisateur puisse
    // taper manuellement immédiatement
    input.focus();
    input.disabled = false;
  }

  _hideCancelBtn();
  resetVoiceBtn();
  console.log("[VOICE] Annulé par l'utilisateur");
}

/**
 * AJOUT : crée et affiche le bouton d'annulation dans le chat
 */
function _showCancelBtn() {
  // Évite les doublons
  if (document.getElementById("voice-cancel-btn")) return;

  const inputRow = document.querySelector(".chat-input-row");
  if (!inputRow) return;

  const cancelBtn = document.createElement("button");
  cancelBtn.id = "voice-cancel-btn";
  cancelBtn.type = "button";
  cancelBtn.textContent = "✕";
  cancelBtn.title = "Annuler l'enregistrement";
  cancelBtn.onclick = cancelVoice;

  // Style inline
  cancelBtn.style.cssText = `
    background: #e53e3e;
    color: white;
    border: none;
    border-radius: 50%;
    width: 28px;
    height: 28px;
    font-size: 14px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: opacity 0.15s;
  `;

  // ✅ Insère le bouton juste après le bouton micro
  const voiceBtn = document.getElementById("voice-btn");
  if (voiceBtn && voiceBtn.nextSibling) {
    inputRow.insertBefore(cancelBtn, voiceBtn.nextSibling);
  } else {
    inputRow.appendChild(cancelBtn);
  }
}

/**
 * ✅ Supprime le bouton d'annulation
 */
function _hideCancelBtn() {
  const cancelBtn = document.getElementById("voice-cancel-btn");
  if (cancelBtn) cancelBtn.remove();
}

/**
 * Remet le bouton micro en état normal
 */
function resetVoiceBtn() {
  const btn = document.getElementById("voice-btn");
  const input = document.getElementById("chat-input");

  if (btn) {
    btn.classList.remove("listening");
    btn.textContent = "🎤";
    btn.title = "Dicter un message";
  }
  if (input && !input.value) {
    input.placeholder = "Posez votre question...";
  }
}

// ✅ Affiche le bouton micro seulement si le navigateur supporte l'audio
document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("voice-btn");
  if (btn && voiceSupported()) btn.style.display = "flex";
});

/**
 * Lance ou stoppe la lecture TTS d'un texte.
 * @param {string} text   - Texte à lire
 * @param {HTMLElement} btn - Bouton qui a déclenché l'action
 */
function toggleTTS(text, btn) {
  // Si on clique sur le bouton déjà actif → stop
  if (_ttsSpeakingBtn === btn && speechSynthesis.speaking) {
    stopTTS();
    return;
  }

  // Stopper toute lecture précédente
  stopTTS();

  _ttsUtterance = new SpeechSynthesisUtterance(text);
  _ttsUtterance.lang = _ttsLangCode(currentLangue);
  _ttsUtterance.rate = 1;
  _ttsUtterance.pitch = 1;

  // État "en lecture"
  _ttsSpeakingBtn = btn;
  btn.textContent = "⏹️";
  btn.title = "Arrêter la lecture";
  btn.classList.add("tts-playing");

  _ttsUtterance.onend = () => _resetTTSBtn(btn);
  _ttsUtterance.onerror = () => _resetTTSBtn(btn);

  speechSynthesis.speak(_ttsUtterance);
}

function stopTTS() {
  if (speechSynthesis.speaking) speechSynthesis.cancel();
  if (_ttsSpeakingBtn) _resetTTSBtn(_ttsSpeakingBtn);
  _ttsUtterance = null;
  _ttsSpeakingBtn = null;
}

function _resetTTSBtn(btn) {
  if (!btn) return;
  btn.textContent = "🔊";
  btn.title = "Lire à voix haute";
  btn.classList.remove("tts-playing");
  if (_ttsSpeakingBtn === btn) {
    _ttsSpeakingBtn = null;
    _ttsUtterance = null;
  }
}

/** Convertit la langue interne (ex: "fr", "en", "es") en BCP-47 */
function _ttsLangCode(langue) {
  const lang =
    langue || (typeof currentLangue !== "undefined" ? currentLangue : "fr");
  const map = {
    fr: "fr-FR",
    en: "en-US",
    es: "es-ES",
    de: "de-DE",
    it: "it-IT",
    pt: "pt-PT",
    nl: "nl-NL",
    ar: "ar-SA",
    zh: "zh-CN",
    ja: "ja-JP",
    ko: "ko-KR",
    ru: "ru-RU",
  };
  return map[lang] || "fr-FR";
}

/** Crée et retourne le bouton TTS à injecter dans une bulle bot */
function createTTSButton(text) {
  const btn = document.createElement("button");
  btn.className = "chat-tts-btn";
  btn.textContent = "🔊";
  btn.title = "Lire à voix haute";
  btn.type = "button";
  btn.setAttribute("aria-label", "Lire ce message à voix haute");
  btn.onclick = () => toggleTTS(text, btn);
  return btn;
}
