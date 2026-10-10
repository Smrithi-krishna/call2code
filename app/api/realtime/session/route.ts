import { NextResponse } from 'next/server';

export async function POST() {
  const key = process.env.OPENAI_API_KEY;
  if (!key) return NextResponse.json({ error: 'OPENAI_API_KEY is not configured' }, { status: 500 });
  const response = await fetch('https://api.openai.com/v1/realtime/client_secrets', {
    method: 'POST',
    headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ session: {
      type: 'realtime',
      model: process.env.OPENAI_REALTIME_MODEL ?? 'gpt-realtime-mini',
      instructions: 'You are Call2Code. Ask one short question at a time to learn the business name, offer, audience, style, pages, contact details, and desired call to action. When complete, summarize the website brief clearly.',
      audio: { output: { voice: 'marin' }, input: { turn_detection: { type: 'server_vad' }, transcription: { model: 'gpt-4o-mini-transcribe' } } }
    } })
  });
  const data = await response.json();
  if (!response.ok) return NextResponse.json({ error: data?.error?.message ?? 'Realtime session failed' }, { status: 502 });
  return NextResponse.json({ clientSecret: data.value ?? data.client_secret?.value });
}
