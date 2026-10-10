import { NextResponse } from 'next/server';
import { supabaseAdmin } from '@/lib/supabase-admin';

export async function POST(_request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  try {
    const db = supabaseAdmin();
    const { data: project, error: readError } = await db.from('projects').select('*').eq('id', id).single();
    if (readError || !project) return NextResponse.json({ error: 'Project not found' }, { status: 404 });
    await db.from('projects').update({ status: 'generating' }).eq('id', id);

    const openaiKey = process.env.OPENAI_API_KEY;
    if (!openaiKey) throw new Error('OPENAI_API_KEY is missing');
    const ai = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST', headers: { Authorization: `Bearer ${openaiKey}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: 'gpt-4.1-mini', temperature: 0.4, messages: [
        { role: 'system', content: 'Generate a complete, polished, responsive single-page business website as one self-contained HTML file. Return only HTML. Use inline CSS and no external dependencies.' },
        { role: 'user', content: `Create the website from this brief:\n${JSON.stringify(project.website_brief ?? project.transcript)}` }
      ] })
    });
    const aiData = await ai.json();
    if (!ai.ok) throw new Error(aiData?.error?.message ?? 'Website generation failed');
    const html = aiData.choices?.[0]?.message?.content?.replace(/^```html\s*/i, '').replace(/```\s*$/i, '').trim();
    if (!html) throw new Error('OpenAI returned no HTML');

    const vercelToken = process.env.VERCEL_TOKEN;
    if (!vercelToken) throw new Error('VERCEL_TOKEN is missing');
    const deploy = await fetch('https://api.vercel.com/v13/deployments', {
      method: 'POST',
      headers: { Authorization: `Bearer ${vercelToken}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: `call2code-${id.slice(0, 8)}`,
        target: 'production',
        files: [{ file: 'index.html', data: html, encoding: 'utf-8' }],
        projectSettings: { framework: null }
      })
    });
    const deployData = await deploy.json();
    if (!deploy.ok) throw new Error(deployData?.error?.message ?? 'Vercel deployment failed');
    const url = `https://${deployData.url}`;
    const { error: updateError } = await db.from('projects').update({ deployment_url: url, status: 'completed', completed_at: new Date().toISOString() }).eq('id', id);
    if (updateError) throw updateError;
    return NextResponse.json({ id, status: 'completed', deploymentUrl: url });
  } catch (error) {
    console.error(error);
    try { await supabaseAdmin().from('projects').update({ status: 'failed' }).eq('id', id); } catch {}
    return NextResponse.json({ error: error instanceof Error ? error.message : 'Generation failed' }, { status: 500 });
  }
}
