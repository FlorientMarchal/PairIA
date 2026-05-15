let mediaRecorder = null;
let audioChunks = [];
let isListening = false;
let recordingStream = null;

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

  const btn = document.getElementById("voice-btn");
  const input = document.getElementById("chat-input");

  if (btn) {
    btn.classList.add("listening");
    btn.textContent = "🔴";
  }
  if (input) input.placeholder = "Enregistrement en cours...";

  // 🔥 Fallback universel
  let options = {};

  if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
    options.mimeType = "audio/webm;codecs=opus";
  } else if (MediaRecorder.isTypeSupported("audio/webm")) {
    options.mimeType = "audio/webm";
  } else if (MediaRecorder.isTypeSupported("audio/ogg;codecs=opus")) {
    options.mimeType = "audio/ogg;codecs=opus";
  } else {
    options = {}; // fallback brut
  }

  console.log("Codec choisi :", options.mimeType || "default");

  mediaRecorder = new MediaRecorder(recordingStream, options);

  mediaRecorder.ondataavailable = (event) => {
    if (event.data.size > 0) audioChunks.push(event.data);
  };

  mediaRecorder.onstop = async () => {
    const audioBlob = new Blob(audioChunks, {
      type: options.mimeType || "audio/webm",
    });

    if (audioBlob.size === 0) {
      console.error("❌ Audio vide — Chrome n'a rien enregistré");
      resetVoiceBtn();
      return;
    }

    const formData = new FormData();
    formData.append("file", audioBlob, "audio.webm");

    try {
      const response = await fetch("http://127.0.0.1:8000/transcribe", {
        method: "POST",
        body: formData,
      });

      let data;
      try {
        data = await response.json();
        console.log("Réponse brute :", data);
      } catch (e) {
        console.error("Réponse non JSON :", await response.text());
        resetVoiceBtn();
        return;
      }

      if (data.success && data.text) {
        input.value = data.text;
        setTimeout(() => sendFromInput(), 200);
      } else {
        console.error(
          "Erreur Whisper :",
          data.error || "Aucune erreur fournie",
        );
      }
    } catch (err) {
      console.error("Erreur envoi audio :", err);
    }

    resetVoiceBtn();
  };

  mediaRecorder.start(200);
}

function stopVoice() {
  isListening = false;
  if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
  if (recordingStream) {
    recordingStream.getTracks().forEach((t) => t.stop());
    recordingStream = null;
  }
}

function resetVoiceBtn() {
  const btn = document.getElementById("voice-btn");
  const input = document.getElementById("chat-input");

  if (btn) {
    btn.classList.remove("listening");
    btn.textContent = "🎤";
  }
  if (input && !input.value) input.placeholder = "Posez votre question...";
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("voice-btn");
  if (btn && voiceSupported()) btn.style.display = "flex";
});
