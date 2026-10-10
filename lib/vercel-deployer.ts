export async function deployToVercel(html: string, projectName = 'call2code'): Promise<string> {
  const token = process.env.VERCEL_TOKEN;
  if (!token) throw new Error('VERCEL_TOKEN is missing');
  const project = process.env.VERCEL_PROJECT_ID;
  if (!project) throw new Error('VERCEL_PROJECT_ID is missing. Create a Vercel project first and add its Project ID to the environment.');

  const team = process.env.VERCEL_TEAM_ID;
  const query = team ? `?teamId=${encodeURIComponent(team)}` : '';
  const response = await fetch(`https://api.vercel.com/v13/deployments${query}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: projectName,
      project,
      target: 'production',
      files: [{ file: 'index.html', data: html, encoding: 'utf-8' }],
      projectSettings: { framework: null }
    })
  });
  const data = await response.json();
  if (!response.ok || !data?.url) {
    const detail = data?.error?.message ?? `HTTP ${response.status}`;
    throw new Error(`Vercel deployment failed: ${detail}. Check that VERCEL_TOKEN can deploy to VERCEL_PROJECT_ID.`);
  }
  return `https://${data.url}`;
}
