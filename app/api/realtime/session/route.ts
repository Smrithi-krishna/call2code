import { NextResponse } from 'next/server';

export async function POST() {
  const key = process.env.OPENAI_API_KEY;
  if (!key) return NextResponse.json({ error: 'OPENAI_API_KEY is not configured' }, { status: 500 });
  const model = process.env.OPENAI_REALTIME_MODEL ?? 'gpt-realtime-mini';
  try {
    const response = await fetch('https://api.openai.com/v1/realtime/client_secrets', {
      method: 'POST',
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session: {
          type: 'realtime',
          model,
          output_modalities: ['audio'],
          instructions: 'You are Call2Code, an AI website builder. Speak English only. Begin with a warm, brief English greeting and ask the caller for their business name and what they offer. Ask one short follow-up question at a time about their audience, style, pages, contact details, and website goal. If the caller speaks another language, politely ask them to continue in English. When finished, summarize their website requirements in English.',
          audio: {
            input: {
              noise_reduction: { type: 'near_field' },
              transcription: { model: 'whisper-1', language: 'en' },
              turn_detection: { type: 'server_vad', threshold: 0.5, prefix_padding_ms: 300, silence_duration_ms: 700 }
            },
            output: { voice: 'marin' }
          }
        }
      })
    });
    const data = await response.json();
    if (!response.ok) {
      return NextResponse.json({ error: data?.error?.message ?? 'Realtime session failed' }, { status: 502 });
    }
    const clientSecret = data.client_secret?.value ?? data.value;
    if (!clientSecret) return NextResponse.json({ error: 'No client secret returned from OpenAI' }, { status: 502 });
    return NextResponse.json({ clientSecret, model });
  } catch {
    return NextResponse.json({ error: 'Could not reach OpenAI. Check the server internet connection and try again.' }, { status: 502 });
  }
}
