export async function deployToVercel(html: string, projectName = 'call2code'): Promise<string> {
  const token = process.env.VERCEL_TOKEN;
  if (!token) throw new Error('VERCEL_TOKEN is missing');

  const team = process.env.VERCEL_TEAM_ID;
  const query = team ? `?teamId=${encodeURIComponent(team)}` : '';
  const response = await fetch(`https://api.vercel.com/v13/deployments${query}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: projectName,
      ...(process.env.VERCEL_PROJECT_ID ? { project: process.env.VERCEL_PROJECT_ID } : {}),
      target: 'production',
      files: [{ file: 'index.html', data: html, encoding: 'utf-8' }],
      projectSettings: { framework: null }
    })
  });
  const data = await response.json();
  if (!response.ok || !data?.url) throw new Error(data?.error?.message ?? 'Vercel deployment failed');
  return `https://${data.url}`;
}
