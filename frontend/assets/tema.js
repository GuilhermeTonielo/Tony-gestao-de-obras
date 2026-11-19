(() => {
  const chave = "tony-tema";
  const pagina = document.documentElement;
  const cores = { claro: "#faf9f6", escuro: "#101916" };
  let temaSalvo;

  try {
    temaSalvo = localStorage.getItem(chave);
  } catch {
    // A página continua utilizável quando o navegador bloqueia o armazenamento.
  }

  function aplicarTema(valor) {
    const tema = valor === "escuro" ? "escuro" : "claro";
    pagina.dataset.tema = tema;
    document.querySelector('meta[name="theme-color"]').content = cores[tema];
  }

  aplicarTema(temaSalvo);

  document.addEventListener("DOMContentLoaded", () => {
    const painel = document.querySelector("#aparencia");
    if (!painel) return;

    const opcoes = painel.querySelectorAll('input[name="tema"]');
    for (const opcao of opcoes) {
      opcao.checked = opcao.value === pagina.dataset.tema;
      opcao.addEventListener("change", () => {
        aplicarTema(opcao.value);
        try {
          localStorage.setItem(chave, opcao.value);
        } catch {
          painel.querySelector("#descricao-tema").textContent =
            "Tema aplicado nesta página. O navegador não permitiu salvar a escolha.";
        }
      });
    }
    painel.hidden = false;
  });
})();
