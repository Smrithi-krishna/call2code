'use client';
import { useRef, useState } from 'react';

export default function VoiceButton() {
  const [state, setState] = useState<'ready' | 'connecting' | 'live' | 'building' | 'error'>('ready');
  const [result, setResult] = useState<string | null>(null);
  const [transcriptItems, setTranscriptItems] = useState<{ role: string; text: string }[]>([]);
  const pc = useRef<RTCPeerConnection | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const transcript = useRef<{ role: string; text: string }[]>([]);

  async function start() {
    try {
      setState('connecting');
      const token = await fetch('/api/realtime/session', { method: 'POST' }).then(r => r.json());
      if (!token.clientSecret) throw new Error(token.error ?? 'No session key returned');
      const connection = new RTCPeerConnection();
      pc.current = connection;
      const audio = new Audio();
      audio.autoplay = true;
      connection.ontrack = event => { audio.srcObject = event.streams[0]; };
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.current.getTracks().forEach(track => connection.addTrack(track, stream.current!));
      const channel = connection.createDataChannel('oai-events');

      channel.onmessage = event => {
        try {
          const message = JSON.parse(event.data);
          // 1. Capture the caller's spoken words
          if (message.type === 'conversation.item.input_audio_transcription.completed' && message.transcript) {
            const userMsg = { role: 'user', text: message.transcript };
            transcript.current.push(userMsg);
            setTranscriptItems(prev => [...prev, userMsg]);
          }
          // 2. Capture the AI's response words
          if (message.type === 'response.output_audio_transcript.done' && message.transcript) {
            const aiMsg = { role: 'assistant', text: message.transcript };
            transcript.current.push(aiMsg);
            setTranscriptItems(prev => [...prev, aiMsg]);
          }
        } catch {}
      };

      channel.onopen = () => channel.send(JSON.stringify({ type: 'response.create' }));
      const offer = await connection.createOffer();
      await connection.setLocalDescription(offer);

      const answer = await fetch('https://api.openai.com/v1/realtime/calls', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token.clientSecret}`, 'Content-Type': 'application/sdp' },
        body: offer.sdp
      });
      if (!answer.ok) throw new Error('Could not connect to OpenAI Realtime WebRTC');
      await connection.setRemoteDescription({ type: 'answer', sdp: await answer.text() });
      setState('live');
    } catch (error) {
      console.error(error);
      setState('error');
    }
  }

  async function stop() {
    stream.current?.getTracks().forEach(t => t.stop());
    pc.current?.close();
    pc.current = null;

    if (transcript.current.length) {
      try {
        setState('building');
        const created = await fetch('/api/projects', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ transcript: transcript.current })
        }).then(r => r.json());

        const built = await fetch(`/api/projects/${created.id}/generate`, { method: 'POST' }).then(r => r.json());
        if (!built.deploymentUrl) throw new Error(built.error ?? 'Deployment failed');
        setResult(built.deploymentUrl);
        setState('ready');
      } catch (error) {
        console.error(error);
        setState('error');
        return;
      }
    } else {
      setState('ready');
    }
  }

  return (
    <div className="voice-wrap">
      <div className="button-row">
        <button
          className="primary"
          onClick={state === 'live' ? stop : (state === 'error' ? () => { setState('ready'); } : start)}
        >
          {state === 'live' ? '■ Finish and build website' :
           state === 'connecting' ? 'Connecting to AI…' :
           state === 'building' ? 'Building with Kimi K3…' :
           state === 'error' ? 'Try again' : '☏ Talk to the AI'}
        </button>
        {result && (
          <a className="result-link" href={result} target="_blank" rel="noreferrer">
            🚀 Open your live website ↗
          </a>
        )}
      </div>

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
