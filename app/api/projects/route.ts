import { NextResponse } from 'next/server';
import { supabaseAdmin } from '@/lib/supabase-admin';

export async function POST(request: Request) {
  try {
    const payload = await request.json();
    const { data, error } = await supabaseAdmin().from('projects').insert({
      customer_phone: payload.customerPhone ?? null,
      vapi_call_id: payload.callId ?? null,
      transcript: payload.transcript ?? [],
      website_brief: payload.websiteBrief ?? null,
      status: 'in_progress'
    }).select('id,status,created_at').single();
    if (error) throw error;
    return NextResponse.json(data, { status: 201 });
  } catch (error) {
    console.error(error);
    return NextResponse.json({ error: 'Could not create project' }, { status: 500 });
  }
}
