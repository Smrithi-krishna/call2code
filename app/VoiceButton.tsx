'use client';
import { useRef, useState } from 'react';

export default function VoiceButton() {
  const [state, setState] = useState<'ready' | 'connecting' | 'live' | 'building' | 'error'>('ready');
  const [statusMessage, setStatusMessage] = useState('');
  const [result, setResult] = useState<string | null>(null);
  const [transcriptItems, setTranscriptItems] = useState<{ role: string; text: string }[]>([]);
  const pc = useRef<RTCPeerConnection | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const transcript = useRef<{ role: string; text: string }[]>([]);

  function closeVoiceConnection() {
    stream.current?.getTracks().forEach(track => track.stop());
    stream.current = null;
    pc.current?.close();
    pc.current = null;
    if (audioRef.current) audioRef.current.srcObject = null;
  }

  async function start() {
    try {
      setState('connecting');
      setStatusMessage('Preparing the voice connection…');
      setResult(null);
      setTranscriptItems([]);
      transcript.current = [];

      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
        throw new Error('Microphone access requires HTTPS. On your phone, open the deployed Vercel https:// link; a local http:// laptop address blocks the microphone.');
      }

      const tokenResponse = await fetch('/api/realtime/session', { method: 'POST' });
      const token = await tokenResponse.json();
      if (!tokenResponse.ok || !token.clientSecret) {
        throw new Error(token.error ?? 'Could not start the AI voice session. Check the server API key and try again.');
      }

      setStatusMessage('Allow microphone access when your browser asks.');
      stream.current = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });

      const connection = new RTCPeerConnection();
      pc.current = connection;
      connection.ontrack = event => {
        const audio = audioRef.current;
        if (!audio) return;
        audio.srcObject = event.streams[0];
        void audio.play().catch(() => {
          setStatusMessage('AI audio is connected. Tap Play in the audio controls below to hear it.');
        });
      };
      connection.onconnectionstatechange = () => {
        if (connection.connectionState === 'failed') {
          setStatusMessage('The voice connection failed. Check your internet connection and try again.');
        }
      };
      stream.current.getTracks().forEach(track => connection.addTrack(track, stream.current!));
      const channel = connection.createDataChannel('oai-events');

      channel.onmessage = event => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === 'error') {
            setStatusMessage(message.error?.message ?? 'The AI voice session returned an error.');
            return;
          }
          // 1. Capture the caller's spoken words
          if (message.type === 'conversation.item.input_audio_transcription.completed' && message.transcript) {
            const userMsg = { role: 'user', text: message.transcript };
            transcript.current.push(userMsg);
            setTranscriptItems(prev => [...prev, userMsg]);
            setStatusMessage('I heard you. The AI is replying…');
          }
          if (message.type === 'input_audio_buffer.speech_started') {
            setStatusMessage('Listening…');
          }
          if (message.type === 'input_audio_buffer.speech_stopped') {
            setStatusMessage('I heard you. Preparing a reply…');
          }
          // 2. Capture the AI's response words
          if (message.type === 'response.output_audio_transcript.done' && message.transcript) {
            const aiMsg = { role: 'assistant', text: message.transcript };
            transcript.current.push(aiMsg);
            setTranscriptItems(prev => [...prev, aiMsg]);
            setStatusMessage('Your turn. Speak when ready.');
          }
          if (message.type === 'response.done' && message.response?.status === 'failed') {
            setStatusMessage(message.response.status_details?.error?.message ?? 'The AI could not complete its reply. Try speaking again.');
          }
        } catch {}
      };

      channel.onopen = () => {
        setStatusMessage('Connected. The AI is greeting you…');
        channel.send(JSON.stringify({ type: 'response.create' }));
      };
      channel.onerror = () => setStatusMessage('The voice event channel failed. Please try again.');
      const offer = await connection.createOffer();
      await connection.setLocalDescription(offer);

      const answer = await fetch('https://api.openai.com/v1/realtime/calls', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token.clientSecret}`, 'Content-Type': 'application/sdp' },
        body: connection.localDescription?.sdp ?? offer.sdp
      });
      if (!answer.ok) {
        const details = await answer.text();
        throw new Error(`OpenAI voice connection failed (${answer.status}): ${details.slice(0, 300)}`);
      }
      await connection.setRemoteDescription({ type: 'answer', sdp: await answer.text() });
      setState('live');
      setStatusMessage('Connected. The AI should greet you now. Please speak English.');
    } catch (error) {
      closeVoiceConnection();
      setState('error');
      const message = error instanceof Error ? error.message : 'Voice setup failed. Please try again.';
      if (error instanceof DOMException && error.name === 'NotAllowedError') {
        setStatusMessage('Microphone permission was blocked. Allow microphone access for this site in your browser settings, then try again.');
      } else if (error instanceof DOMException && error.name === 'NotFoundError') {
        setStatusMessage('No microphone was found. Check that your phone or laptop microphone is available.');
      } else {
        setStatusMessage(message);
      }
    }
  }

  async function stop() {
    closeVoiceConnection();

    if (transcript.current.length) {
      try {
        setState('building');
        const created = await fetch('/api/projects', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ transcript: transcript.current })
        }).then(async r => { const data = await r.json(); if (!r.ok || !data.id) throw new Error(data.error ?? 'Could not save project'); return data; });

        const built = await fetch(`/api/projects/${created.id}/generate`, { method: 'POST' }).then(r => r.json());
        if (!built.deploymentUrl) throw new Error(built.error ?? 'Deployment failed');
        setResult(built.deploymentUrl);
        setState('ready');
      } catch (error) {
        setState('error');
        setStatusMessage(error instanceof Error ? error.message : 'Website generation failed.');
        return;
      }
    } else {
      setState('ready');
      setStatusMessage('');
    }
  }

  return (
    <div className="voice-wrap">
      <div className="button-row">
        <button
          className="primary"
          onClick={state === 'live' ? stop : start}
          disabled={state === 'connecting' || state === 'building'}
        >
          {state === 'live' ? '■ Finish and build website' :
           state === 'connecting' ? 'Connecting to AI…' :
           state === 'building' ? 'Building with OpenAI…' :
           state === 'error' ? 'Try again' : '☏ Talk to the AI'}
        </button>
        {result && (
          <a className="result-link" href={result} target="_blank" rel="noreferrer">
            🚀 Open your live website ↗
          </a>
        )}
      </div>

      {statusMessage && <p role="status" aria-live="polite" className="voice-status">{statusMessage}</p>}
      <audio ref={audioRef} autoPlay playsInline controls aria-label="AI voice audio" className="voice-audio" />

      {transcriptItems.length > 0 && (
        <div className="transcript-container">
          <div className="transcript-title">
            <span className="live-badge">LIVE</span>
            <b>Caller Conversation</b>
          </div>
          <div className="transcript-list">
            {transcriptItems.map((item, i) => (
              <div key={i} className={`transcript-item ${item.role}`}>
                <span className="transcript-role">
                  {item.role === 'user' ? "👤 Person's Words:" : '🤖 Call2Code:'}
                </span>
                <p className="transcript-text">{item.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
