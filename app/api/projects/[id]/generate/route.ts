import { NextResponse } from 'next/server';
import { supabaseAdmin } from '@/lib/supabase-admin';
import { localProjects } from '@/lib/projects-store';
import { deployToVercel } from '@/lib/vercel-deployer';

function stripMarkdown(value: string) {
  return value.replace(/^```html\s*/i, '').replace(/^```\s*/i, '').replace(/```\s*$/i, '').trim();
}

export async function POST(_request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  let project: any;
  try {
    project = localProjects.get(id);
    if (!project) {
      const db = supabaseAdmin();
      const { data, error } = await db.from('projects').select('*').eq('id', id).single();
      if (error || !data) return NextResponse.json({ error: 'Project not found' }, { status: 404 });
      project = data;
    }
    const db = supabaseAdmin();
    await db.from('projects').update({ status: 'generating' }).eq('id', id);

    const key = process.env.OPENAI_API_KEY;
    if (!key) throw new Error('OPENAI_API_KEY is missing');
    const ai = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: process.env.OPENAI_SITE_BUILDER_MODEL ?? 'gpt-4.1-mini',
        temperature: 0.4,
        messages: [
          { role: 'system', content: 'Generate one complete polished responsive business website as a standalone HTML file. Return only HTML beginning with <!DOCTYPE html>; use inline CSS and JavaScript with no external dependencies.' },
          { role: 'user', content: `Build the website from this conversation and brief:\n${JSON.stringify(project.website_brief ?? project.transcript)}` }
        ]
      })
    });
    const data = await ai.json();
    if (!ai.ok) throw new Error(data?.error?.message ?? 'Website generation failed');
    const html = stripMarkdown(data.choices?.[0]?.message?.content ?? '');
    if (!html.toLowerCase().includes('<!doctype html')) throw new Error('OpenAI did not return a complete HTML document');

    const deploymentUrl = await deployToVercel(html, `call2code-${id.slice(0, 8)}`);
    const completedAt = new Date().toISOString();
    await db.from('projects').update({ deployment_url: deploymentUrl, status: 'completed', completed_at: completedAt }).eq('id', id);
    localProjects.set(id, { ...project, deployment_url: deploymentUrl, status: 'completed', completed_at: completedAt });
    return NextResponse.json({ id, status: 'completed', deploymentUrl });
  } catch (error) {
    console.error('Generation route error:', error);
    try { await supabaseAdmin().from('projects').update({ status: 'failed' }).eq('id', id); } catch {}
    if (localProjects.has(id)) localProjects.set(id, { ...localProjects.get(id)!, status: 'failed' });
    return NextResponse.json({ error: error instanceof Error ? error.message : 'Generation failed' }, { status: 500 });
  }
}
