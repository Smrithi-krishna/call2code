import { NextResponse } from 'next/server';
import { supabaseAdmin } from '@/lib/supabase-admin';

export async function POST(request: Request) {
  try {
    const payload = await request.json();
    // Build a text brief from the transcript array sent by the WebRTC client
    const transcriptArray: { role: string; text: string }[] = Array.isArray(payload.transcript) ? payload.transcript : [];
    const websiteBrief = payload.websiteBrief ?? (transcriptArray.length > 0
      ? transcriptArray.map(t => `${t.role}: ${t.text}`).join('\n')
      : null);
    const { data, error } = await supabaseAdmin().from('projects').insert({
      customer_phone: payload.customerPhone ?? null,
      vapi_call_id: payload.callId ?? null,
      transcript: transcriptArray,
      website_brief: websiteBrief,
      status: 'in_progress'
    }).select('id,status,created_at').single();
    if (error) throw error;
    return NextResponse.json(data, { status: 201 });
  } catch (error) {
    console.error(error);
    return NextResponse.json({ error: 'Could not create project' }, { status: 500 });
  }
}
