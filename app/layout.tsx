import './globals.css';

export const metadata = { title: 'Call2Code', description: 'Turn a phone call into a live website.' };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
