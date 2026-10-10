import { NextResponse } from 'next/server';
import { localProjects, ProjectRecord } from '@/lib/projects-store';
import crypto from 'crypto';

export async function POST(request: Request) {
  try {
    const body = await request.text();
    const params = new URLSearchParams(body);
    const speech = params.get('SpeechResult') ?? '';
    const phone = params.get('From') ?? '';
    const callSid = params.get('CallSid') ?? '';

    console.log(`[Twilio Call] Caller (${phone}) spoke: "${speech}"`);

    if (!speech.trim()) {
      const xml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Amy">Sorry, I did not hear anything. Please speak your website idea.</Say>
  <Gather input="speech" action="/api/twilio/gather" method="POST" speechTimeout="auto" />
</Response>`;
      return new NextResponse(xml, { headers: { 'Content-Type': 'text/xml' } });
    }

    // 1. Create project record immediately
    const projectId = crypto.randomUUID();
    const newRecord: ProjectRecord = {
      id: projectId,
      customer_phone: phone,
      vapi_call_id: callSid,
      transcript: [
        { role: 'assistant', text: 'What is your business called, what do you offer, and who is your target audience?' },
        { role: 'user', text: speech }
      ],
      website_brief: speech,
      status: 'in_progress',
      created_at: new Date().toISOString()
    };
    localProjects.set(projectId, newRecord);

    // 2. Trigger website generation & deployment in background
    const base = process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000';
    fetch(`${base}/api/projects/${projectId}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    }).catch(err => console.error('[Twilio] Background generation error:', err));

    // 3. Respond with TwiML informing caller that their site is being deployed to Vercel
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Amy">
    Thank you! I have captured your website requirements.
    I am now generating your website with Kimi K3 and deploying it live to Vercel.
    Your project ID is ${projectId.slice(0, 8)}. Goodbye!
  </Say>
  <Hangup />
</Response>`;

    return new NextResponse(xml, { headers: { 'Content-Type': 'text/xml' } });
  } catch (error) {
    console.error('Twilio gather error:', error);
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Amy">An error occurred while creating your website. Please try again soon.</Say>
  <Hangup />
</Response>`;
    return new NextResponse(xml, { headers: { 'Content-Type': 'text/xml' } });
  }
}
