// Modal global
(() => {
  const backdrop = document.getElementById('modal-backdrop');
  const modal    = document.getElementById('modal');
  const body     = document.getElementById('modal-body');

  if (!backdrop || !modal || !body) return;

  function openModal(html) {
    if (typeof html === 'string') body.innerHTML = html;
    backdrop.classList.remove('hidden');
    modal.classList.remove('hidden');
    document.body.classList.add('overflow-hidden');

    // foca no 1º [autofocus], se existir
    const af = body.querySelector('[autofocus]');
    if (af) setTimeout(() => af.focus(), 0);
  }

  function closeModal() {
    modal.classList.add('hidden');
    backdrop.classList.add('hidden');
    document.body.classList.remove('overflow-hidden');
    body.innerHTML = '';
  }

  // Exponho para você poder chamar via console se quiser
  window.Modal = { open: openModal, close: closeModal };

  // Delegação de clique (funciona com conteúdo carregado dinamicamente)
  document.addEventListener('click', (e) => {
    const target = e.target;

    // A) Abrir via data-modal-url (qualquer link/botão com esse atributo)
    const opener = target.closest('[data-modal-url]');
    if (opener) {
      e.preventDefault();
      const url = opener.getAttribute('data-modal-url');
      fetch(url, { headers: { 'X-Requested-With': 'fetch' } })
        .then(r => r.text())
        .then(html => openModal(html))
        .catch(() => openModal('<div class="p-4 text-rose-600">Falha ao carregar o conteúdo.</div>'));
      return;
    }

    // B) Fechar ao clicar no X (classe .modal-close),
    //    em qualquer elemento com [data-modal-close],
    //    ou ao clicar no backdrop
    if (
      target.closest('.modal-close') ||
      target.closest('[data-modal-close]') ||
      target === backdrop
    ) {
      e.preventDefault();
      closeModal();
      return;
    }
  });

  // C) Fechar com ESC
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !modal.classList.contains('hidden')) {
      e.preventDefault();
      closeModal();
    }
  });
})();
