import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  const body = await request.text();
  const params = new URLSearchParams(body);
  const speech = params.get('SpeechResult') ?? '';
  // Next step: persist this transcript and pass the conversation to the LLM/site generator.
  console.log('Call2Code transcript:', speech);
  const xml = `<Response><Say>Thanks — I’ve got that. What should visitors do when they reach your website?</Say><Gather input="speech" action="/api/twilio/gather" method="POST" speechTimeout="auto" /></Response>`;
  return new NextResponse(xml, { headers: { 'Content-Type': 'text/xml' } });
}
