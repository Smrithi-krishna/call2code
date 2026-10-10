import { NextResponse } from 'next/server';

// When an incoming call arrives on Twilio, this webhook answers automatically.
export async function POST(request: Request) {
  const base = process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000';
  const gatherUrl = `${base}/api/twilio/gather`;

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Amy">
    Hello! I am Call2Code, your AI website builder.
    Tell me about your business: What is your business called, what do you offer, and who is your target audience?
  </Say>
  <Gather input="speech" action="${gatherUrl}" method="POST" speechTimeout="auto" timeout="8">
    <Say voice="Polly.Amy">Please speak after the tone.</Say>
  </Gather>
  <Say voice="Polly.Amy">I did not catch that. Please call back anytime to build your website.</Say>
</Response>`;

  return new NextResponse(xml, { headers: { 'Content-Type': 'text/xml' } });
}
