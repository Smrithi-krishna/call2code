import VoiceButton from './VoiceButton';

export default function Home() {
  return (
    <main className="shell">
      <nav><div className="brand"><span className="dot" />Call2Code</div><span className="nav-note">AI websites, made by phone</span></nav>
      <section className="hero">
        <div className="eyebrow">✦ Your next website starts with a call</div>
        <h1>Tell us your idea.<br /><em>We’ll build the site.</em></h1>
        <p className="lede">Call our AI assistant. It asks the right questions about your business, then turns your answers into a polished website ready to launch.</p>
        <div className="actions"><VoiceButton /><a className="secondary" href="#how">See how it works ↓</a></div>
        <div className="trust"><span>●</span> No design skills needed <span>●</span> Live on Vercel <span>●</span> Built in minutes</div>
      </section>
      <section id="how" className="steps">
        <div className="step"><b>01</b><h2>Have a conversation</h2><p>Our voice agent answers your call and learns about your business, audience, style, and goals.</p></div>
        <div className="step"><b>02</b><h2>Get a first draft</h2><p>Your answers become a tailored website brief and a beautiful first version — no forms or jargon.</p></div>
        <div className="step"><b>03</b><h2>Go live</h2><p>Review your site, request changes, and publish a shareable Vercel URL when you’re ready.</p></div>
      </section>
      <footer><div className="brand"><span className="dot" />Call2Code</div><span>From conversation to conversion.</span></footer>
    </main>
  );
}
