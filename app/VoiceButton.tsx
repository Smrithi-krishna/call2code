'use client';
import { useRef, useState } from 'react';

export default function VoiceButton() {
  const [state, setState] = useState('ready');
  const pc = useRef<RTCPeerConnection | null>(null);
  const stream = useRef<MediaStream | null>(null);

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
      channel.onopen = () => channel.send(JSON.stringify({ type: 'response.create' }));
      const offer = await connection.createOffer();
      await connection.setLocalDescription(offer);
      const answer = await fetch('https://api.openai.com/v1/realtime/calls', {
        method: 'POST', headers: { Authorization: `Bearer ${token.clientSecret}`, 'Content-Type': 'application/sdp' }, body: offer.sdp
      });
      if (!answer.ok) throw new Error('Could not connect to OpenAI Realtime');
      await connection.setRemoteDescription({ type: 'answer', sdp: await answer.text() });
      setState('live');
    } catch (error) { console.error(error); setState('error'); }
  }
  function stop() { stream.current?.getTracks().forEach(t => t.stop()); pc.current?.close(); pc.current = null; setState('ready'); }
  return <button className="primary" onClick={state === 'live' ? stop : start}>{state === 'live' ? '■ End conversation' : state === 'connecting' ? 'Connecting…' : state === 'error' ? 'Try again' : '☏ Talk to the AI'}</button>;
}
