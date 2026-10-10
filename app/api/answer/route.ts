import { NextResponse } from 'next/server';

// Generates a concise answer from a caller's transcript. The key stays server-side.
export async function POST(request: Request) {
  try {
    const { transcript, phone } = await request.json();
    if (!transcript || typeof transcript !== 'string') {
      return NextResponse.json({ error: 'transcript is required' }, { status: 400 });
    }
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) return NextResponse.json({ error: 'OPENAI_API_KEY is not configured' }, { status: 500 });

    const openai = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        messages: [
          { role: 'system', content: 'You are Call2Code. Turn a caller\'s website idea into a clear, friendly answer and next step. Keep it under 600 characters.' },
          { role: 'user', content: transcript }
        ],
        temperature: 0.4
      })
    });
    const data = await openai.json();
    if (!openai.ok) return NextResponse.json({ error: data?.error?.message ?? 'OpenAI request failed' }, { status: 502 });
    const answer = data.choices?.[0]?.message?.content?.trim();
    if (!answer) return NextResponse.json({ error: 'No answer returned' }, { status: 502 });

    // If a phone number is supplied, forward the answer through Twilio WhatsApp.
    if (phone) await sendWhatsApp(phone, answer);
    return NextResponse.json({ answer, sentToWhatsApp: Boolean(phone) });
  } catch (error) {
    console.error(error);
    return NextResponse.json({ error: 'Unable to process request' }, { status: 500 });
  }
}

async function sendWhatsApp(to: string, body: string) {
  const sid = process.env.TWILIO_ACCOUNT_SID;
  const token = process.env.TWILIO_AUTH_TOKEN;
  const from = process.env.TWILIO_WHATSAPP_FROM;
  if (!sid || !token || !from) throw new Error('Twilio WhatsApp environment variables are missing');
  const form = new URLSearchParams({ To: `whatsapp:${to}`, From: `whatsapp:${from}`, Body: body });
  await fetch(`https://api.twilio.com/2010-04-01/Accounts/${sid}/Messages.json`, {
    method: 'POST',
    headers: { Authorization: `Basic ${Buffer.from(`${sid}:${token}`).toString('base64')}`, 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form
  });
}
