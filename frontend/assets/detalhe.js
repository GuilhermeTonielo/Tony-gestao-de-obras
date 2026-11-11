const editar = document.querySelector("#editar-obra");
const erro = document.querySelector("#erro-obra");
const dialogo = document.querySelector("#confirmar-exclusao");
const token = document.querySelector('meta[name="csrf-token"]').content;

async function alterarObra(botao, url, method, dados, sucesso) {
  botao.disabled = true;
  erro.hidden = true;
  try {
    const headers = { Accept: "application/json", "X-CSRF-Token": token };
    if (dados) headers["Content-Type"] = "application/json";
    const resposta = await fetch(url, { method, headers, body: dados && JSON.stringify(dados) });
    if (!resposta.ok) {
      const corpo = await resposta.json().catch(() => ({}));
      throw new Error(corpo.erro || "Não foi possível concluir a operação.");
    }
    sucesso();
  } catch (falha) {
    if (dialogo.open) dialogo.close();
    erro.textContent = falha.message;
    erro.hidden = false;
  } finally {
    botao.disabled = false;
  }
}

if (editar) {
  editar.addEventListener("submit", evento => {
    evento.preventDefault();
    const dados = Object.fromEntries(new FormData(editar));
    dados.construtora_id = Number(dados.construtora_id);
    alterarObra(evento.submitter, editar.dataset.url, "PUT", dados, () => location.reload());
  });

  document.querySelector("#excluir-obra").addEventListener("click", () => dialogo.showModal());
  document.querySelector("#cancelar-exclusao").addEventListener("click", () => dialogo.close());
  document.querySelector("#confirmar-obra").addEventListener("click", ({ currentTarget: botao }) => {
    alterarObra(botao, botao.dataset.url, "DELETE", undefined, () => location.assign(botao.dataset.retorno));
  });
}
