const dialogo = document.querySelector("#dialogo-obra");
const formulario = document.querySelector("#form-obra");
const salvar = document.querySelector("#salvar-obra");
const erroFormulario = document.querySelector("#erro-formulario");
const feedback = document.querySelector("#feedback");
const lista = document.querySelector("#lista-obras");
const estadoLista = document.querySelector("#estado-lista");
const total = document.querySelector("#total-obras");
const busca = document.querySelector("#buscar");
const cartao = document.querySelector("#cartao-obra");
const resumo = JSON.parse(document.querySelector("#resumo-obras").textContent);
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const filtros = [...document.querySelectorAll("[data-filter]")];
const construtoras = new Map(
  Array.from(formulario?.elements.construtora_id.options ?? [], opcao => [opcao.value, opcao.text]),
);
const rotulos = {
  planejada: "Planejada",
  em_andamento: "Em andamento",
  concluida: "Concluída",
};

let obras = [];
let filtro = "";
let listaDisponivel = false;
let versaoCarregamento = 0;

function mostrarMensagem(elemento, mensagem, erro = false) {
  elemento.textContent = mensagem;
  elemento.classList.toggle("error", erro);
  elemento.hidden = !mensagem;
}

function renderizarObras() {
  if (!listaDisponivel) return;
  const termo = busca.value.trim().toLocaleLowerCase("pt-BR");
  const visiveis = obras.filter(obra => (
    (!filtro || obra.status === filtro) &&
    (!termo || [obra.nome, obra.local].some(valor => valor?.toLocaleLowerCase("pt-BR").includes(termo)))
  ));

  for (const botao of filtros) {
    const status = botao.dataset.filter;
    botao.setAttribute("aria-pressed", String(status === filtro));
    botao.querySelector("[data-count]").textContent = obras.filter(obra => obra.status === status).length;
  }

  const fragmento = document.createDocumentFragment();
  for (const obra of visiveis) {
    const item = cartao.content.cloneNode(true);
    const link = item.querySelector(".card-link");
    link.href = link.dataset.url.replace(/0$/, String(obra.id));
    const campo = nome => item.querySelector(`[data-field="${nome}"]`);
    campo("nome").textContent = obra.nome;
    campo("local").textContent = obra.local || "Local não informado";
    campo("status").textContent = rotulos[obra.status] || obra.status;
    campo("status").dataset.status = obra.status;
    const progresso = resumo[obra.id]?.progresso;
    if (progresso != null) {
      campo("progresso").textContent = `${progresso}%`;
      campo("barra").style.width = `${progresso}%`;
    }

    const data = obra.previsao_entrega?.split("-");
    campo("entrega").textContent = data?.length === 3
      ? `Entrega · ${data[2]}/${data[1]}/${data[0]}`
      : "Entrega não definida";
    const construtora = resumo[obra.id]?.construtora ?? construtoras.get(String(obra.construtora_id));
    const avatar = campo("construtora");
    if (construtora) {
      avatar.textContent = construtora.split(/\s+/).slice(0, 2).map(palavra => palavra[0]).join("").toUpperCase();
      avatar.title = construtora;
      avatar.setAttribute("aria-label", construtora);
    } else {
      avatar.hidden = true;
    }
    fragmento.append(item);
  }

  lista.replaceChildren(fragmento);
  estadoLista.hidden = visiveis.length > 0;
  estadoLista.textContent = obras.length
    ? "Nenhuma obra corresponde aos filtros."
    : "Nenhuma obra cadastrada. Use Nova obra para começar.";
  total.textContent = obras.length ? `Mostrando ${visiveis.length} de ${obras.length} obras` : "";
}

async function carregarObras() {
  const versao = ++versaoCarregamento;
  try {
    const resposta = await fetch("/obras", { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!resposta.ok) throw new Error("Falha ao consultar obras.");
    const dados = await resposta.json();
    if (versao !== versaoCarregamento) return;
    obras = dados;
    listaDisponivel = true;
    renderizarObras();
  } catch {
    if (versao !== versaoCarregamento) return;
    listaDisponivel = false;
    estadoLista.hidden = false;
    estadoLista.textContent = "Não foi possível atualizar as obras. Confira o servidor e recarregue a página.";
  }
}

async function cadastrarObra(evento) {
  evento.preventDefault();
  const dados = Object.fromEntries(new FormData(formulario));
  dados.construtora_id = Number(dados.construtora_id);
  salvar.disabled = true;
  mostrarMensagem(erroFormulario, "");
  try {
    const resposta = await fetch("/obras", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": csrfToken },
      body: JSON.stringify(dados),
    });
    if (!resposta.ok) {
      const erro = await resposta.json().catch(() => ({}));
      mostrarMensagem(erroFormulario, erro.erro || "Não foi possível cadastrar a obra.", true);
      return;
    }

    formulario.reset();
    dialogo.close();
    filtro = "";
    busca.value = "";
    mostrarMensagem(feedback, "Obra cadastrada com sucesso.");
    await carregarObras();
  } catch {
    mostrarMensagem(erroFormulario, "Não foi possível conectar à API. Confira se o Flask está rodando.", true);
  } finally {
    salvar.disabled = false;
  }
}

if (formulario) {
  document.querySelector("#nova-obra").addEventListener("click", () => {
    mostrarMensagem(erroFormulario, "");
    dialogo.showModal();
  });
  for (const seletor of ["#fechar-formulario", "#cancelar-cadastro"]) {
    document.querySelector(seletor).addEventListener("click", () => dialogo.close());
  }
  formulario.addEventListener("submit", cadastrarObra);
}
document.querySelector("#focar-busca").addEventListener("click", () => busca.focus());
busca.addEventListener("input", renderizarObras);
for (const botao of filtros) {
  botao.addEventListener("click", () => {
    filtro = filtro === botao.dataset.filter ? "" : botao.dataset.filter;
    renderizarObras();
  });
}
carregarObras();
