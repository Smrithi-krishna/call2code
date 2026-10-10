import { NextResponse } from 'next/server';

export async function POST() {
  const key = process.env.OPENAI_API_KEY;
  if (!key) return NextResponse.json({ error: 'OPENAI_API_KEY is not configured' }, { status: 500 });
  const model = process.env.OPENAI_REALTIME_MODEL ?? 'gpt-realtime-mini';
  const response = await fetch('https://api.openai.com/v1/realtime/client_secrets', {
    method: 'POST',
    headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session: {
        type: 'realtime',
        model,
        instructions: 'You are Call2Code. Speak Malayalam by default and understand Malayalam, English, and Manglish. Ask one short question at a time to learn the business name, offer, audience, style, pages, contact details, and desired call to action. If the caller speaks English, reply in English. Keep questions simple and conversational. When complete, summarize the website brief clearly in the language the caller used.'
      }
    })
  });
  const data = await response.json();
  if (!response.ok) return NextResponse.json({ error: data?.error?.message ?? 'Realtime session failed' }, { status: 502 });
  const clientSecret = data.client_secret?.value ?? data.value;
  if (!clientSecret) return NextResponse.json({ error: 'No client secret returned from OpenAI' }, { status: 502 });
  return NextResponse.json({ clientSecret, model });
}
