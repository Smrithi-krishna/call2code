const NEXUS_CONFIG = { name: 'Nexus Voice', phone: '9496177845' };
document.title = `${NEXUS_CONFIG.name} — Speak to what’s next`;
document.querySelectorAll('.phone-link').forEach((link) => { link.href = `tel:${NEXUS_CONFIG.phone}`; });
document.querySelector('#year').textContent = new Date().getFullYear();

const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach((entry) => { if (entry.isIntersecting) { entry.target.classList.add('is-visible'); revealObserver.unobserve(entry.target); } });
}, { threshold: 0.12 });
document.querySelectorAll('.reveal').forEach((element) => revealObserver.observe(element));

document.querySelectorAll('.magnetic').forEach((element) => {
  element.addEventListener('pointermove', (event) => {
    const rect = element.getBoundingClientRect();
    const x = (event.clientX - rect.left - rect.width / 2) * 0.12;
    const y = (event.clientY - rect.top - rect.height / 2) * 0.12;
    element.style.transform = `translate(${x}px, ${y}px)`;
  });
  element.addEventListener('pointerleave', () => { element.style.transform = ''; });
});

const toast = document.querySelector('.toast');
document.querySelector('.phone-link').addEventListener('click', () => {
  toast.textContent = 'Opening your phone…'; toast.classList.add('show');
  window.setTimeout(() => toast.classList.remove('show'), 2200);
});

document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener('click', (event) => {
    const target = document.querySelector(link.getAttribute('href'));
    if (!target) return; event.preventDefault(); target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
});

const hero = document.querySelector('.hero');
window.addEventListener('pointermove', (event) => {
  if (window.innerWidth < 800) return;
  const x = (event.clientX / window.innerWidth - 0.5) * 12;
  const y = (event.clientY / window.innerHeight - 0.5) * 8;
  hero.querySelector('.hero-orbit').style.transform = `translate(${x}px, ${y}px)`;
}, { passive: true });
