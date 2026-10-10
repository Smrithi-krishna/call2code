import { NextResponse } from 'next/server';

// Configure your Twilio phone number's voice webhook to point here.
// The gather prompt is intentionally concise so the caller can speak naturally.
export async function POST() {
  const base = process.env.NEXT_PUBLIC_APP_URL ?? '';
  const gatherUrl = `${base}/api/twilio/gather`;
  const xml = `<Response><Gather input="speech" action="${gatherUrl}" method="POST" speechTimeout="auto"><Say voice="Polly.Amy">Hi, I’m your Call2Code assistant. I’ll ask a few questions and turn your answers into a website. What is your business called, and what do you do?</Say></Gather><Say>Sorry, I didn’t hear anything. Please call again soon.</Say></Response>`;
  return new NextResponse(xml, { headers: { 'Content-Type': 'text/xml' } });
}
