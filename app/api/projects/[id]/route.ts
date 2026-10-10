import { NextResponse } from 'next/server';
import { supabaseAdmin } from '@/lib/supabase-admin';

export async function PATCH(request: Request, context: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await context.params;
    const payload = await request.json();
    const allowed = ['transcript', 'website_brief', 'deployment_url', 'status', 'completed_at'];
    const update = Object.fromEntries(Object.entries(payload).filter(([key]) => allowed.includes(key)));
    const { data, error } = await supabaseAdmin().from('projects').update(update).eq('id', id).select().single();
    if (error) throw error;
    return NextResponse.json(data);
  } catch (error) {
    console.error(error);
    return NextResponse.json({ error: 'Could not update project' }, { status: 500 });
  }
}
