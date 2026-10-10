import { NextResponse } from 'next/server';
import { supabaseAdmin } from '@/lib/supabase-admin';
import { localProjects, ProjectRecord } from '@/lib/projects-store';
import crypto from 'crypto';

export async function POST(request: Request) {
  try {
    const payload = await request.json();
    const transcriptArray: { role: string; text: string }[] = Array.isArray(payload.transcript) ? payload.transcript : [];
    const websiteBrief = payload.websiteBrief ?? (transcriptArray.length > 0
      ? transcriptArray.map(t => `${t.role}: ${t.text}`).join('\n')
      : null);

    const projectId = crypto.randomUUID();
    const newRecord: ProjectRecord = {
      id: projectId,
      customer_phone: payload.customerPhone ?? null,
      vapi_call_id: payload.callId ?? null,
      transcript: transcriptArray,
      website_brief: websiteBrief,
      status: 'in_progress',
      created_at: new Date().toISOString()
    };

    // Store in local cache first so it is immediately available
    localProjects.set(projectId, newRecord);

    // Try inserting into Supabase if configured and table exists
    try {
      const { data, error } = await supabaseAdmin().from('projects').insert({
        id: projectId,
        customer_phone: newRecord.customer_phone,
        vapi_call_id: newRecord.vapi_call_id,
        transcript: newRecord.transcript,
        website_brief: newRecord.website_brief,
        status: newRecord.status
      }).select('id,status,created_at').single();

      if (!error && data) {
        return NextResponse.json(data, { status: 201 });
      } else {
        console.warn('Supabase insert note (using local cache):', error?.message);
      }
    } catch (dbErr: any) {
      console.warn('Supabase DB error (using local cache):', dbErr?.message);
    }

    // Return the created project with valid id so the client can continue immediately
    return NextResponse.json({
      id: projectId,
      status: newRecord.status,
      created_at: newRecord.created_at
    }, { status: 201 });
  } catch (error) {
    console.error('Projects POST error:', error);
    return NextResponse.json({ error: 'Could not create project' }, { status: 500 });
  }
}
