(() => {
    const raiz = document.documentElement;
    const chaveTema = "imobilizado-qr-tema";
    let temaPreferido = raiz.dataset.themePreference || "system";
    const autenticado = raiz.dataset.authenticated === "true";
    const consultaSistema = window.matchMedia("(prefers-color-scheme: dark)");
    const telaCarregamento = document.createElement("div");
    telaCarregamento.className = "tela-carregamento visivel";
    telaCarregamento.setAttribute("role", "status");
    telaCarregamento.setAttribute("aria-live", "polite");
    telaCarregamento.innerHTML = '<span class="indicador-carregamento" aria-hidden="true"></span><span class="texto-acessivel">Carregando</span>';
    document.body.appendChild(telaCarregamento);

    function mostrarCarregamento() {
        telaCarregamento.classList.add("visivel");
    }

    function esconderCarregamento() {
        telaCarregamento.classList.remove("visivel");
    }

    document.addEventListener("click", (evento) => {
        if (evento.defaultPrevented || evento.button !== 0 || evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) return;
        const link = evento.target.closest("a[href]");
        if (!link || link.target || link.hasAttribute("download") || link.relList.contains("external")) return;
        const destino = new URL(link.href, window.location.href);
        if (destino.origin !== window.location.origin || destino.hash && destino.pathname === window.location.pathname && destino.search === window.location.search) return;
        mostrarCarregamento();
    });

    document.addEventListener("submit", (evento) => {
        const formulario = evento.target;
        if (evento.defaultPrevented || formulario.matches(".form-status-etiqueta, .form-check, [data-form-etiquetas]")) return;
        if (formulario.target && formulario.target !== "_self") return;
        mostrarCarregamento();
    });

    window.addEventListener("pageshow", () => window.setTimeout(esconderCarregamento, 1500));

    const barraSuperior = document.querySelector(".topbar");
    let ultimaRolagem = window.scrollY;
    let quadroRolagemPendente = false;
    if (barraSuperior) {
        window.addEventListener("scroll", () => {
            if (quadroRolagemPendente) return;
            quadroRolagemPendente = true;
            window.requestAnimationFrame(() => {
                const rolagemAtual = window.scrollY;
                const diferenca = rolagemAtual - ultimaRolagem;
                if (rolagemAtual < 48 || diferenca < -5) {
                    barraSuperior.classList.remove("topbar-oculta");
                } else if (rolagemAtual > 96 && diferenca > 7) {
                    barraSuperior.classList.add("topbar-oculta");
                }
                ultimaRolagem = rolagemAtual;
                quadroRolagemPendente = false;
            });
        }, { passive: true });
    }

    function temaDoSistema() {
        return consultaSistema.matches ? "dark" : "light";
    }

    function obterTema() {
        if (temaPreferido === "light" || temaPreferido === "dark") return temaPreferido;
        if (!autenticado) {
            try {
                const salvo = localStorage.getItem(chaveTema);
                if (salvo === "light" || salvo === "dark") return salvo;
            } catch (_) {
                // O sistema operacional ainda determina o tema se o armazenamento estiver bloqueado.
            }
        }
        return temaDoSistema();
    }

    function aplicarTema(tema) {
        raiz.dataset.theme = tema;
        document.querySelectorAll(".theme-toggle").forEach((botao) => {
            const rotulo = botao.querySelector("span");
            if (rotulo) rotulo.textContent = tema === "dark" ? "Usar modo claro" : "Usar modo escuro";
            botao.setAttribute("aria-pressed", String(tema === "dark"));
        });
    }

    async function salvarTema(tema) {
        temaPreferido = tema;
        raiz.dataset.themePreference = tema;
        if (autenticado) {
            try {
                await fetch("/minha-conta/tema", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                        "X-Requested-With": "XMLHttpRequest"
                    },
                    body: new URLSearchParams({ tema })
                });
            } catch (_) {
                // A mudança visual permanece ativa nesta página se a rede estiver indisponível.
            }
        } else {
            try {
                localStorage.setItem(chaveTema, tema);
            } catch (_) {
                // A escolha vale até a página ser fechada quando o armazenamento está bloqueado.
            }
        }
    }

    aplicarTema(obterTema());

    document.querySelectorAll(".theme-toggle").forEach((botao) => {
        botao.addEventListener("click", () => {
            const tema = raiz.dataset.theme === "dark" ? "light" : "dark";
            aplicarTema(tema);
            salvarTema(tema);
        });
    });

    if (temaPreferido === "system" && typeof consultaSistema.addEventListener === "function") {
        consultaSistema.addEventListener("change", () => temaPreferido === "system" && aplicarTema(temaDoSistema()));
    }

    const seletorCor = document.querySelector(".seletor-cor-botao");
    function aplicarCorBotao(cor) {
        if (!/^#[0-9a-f]{6}$/i.test(cor)) return;
        const rgb = [1, 3, 5].map((inicio) => parseInt(cor.slice(inicio, inicio + 2), 16) / 255);
        const linear = rgb.map((canal) => canal <= 0.04045 ? canal / 12.92 : ((canal + 0.055) / 1.055) ** 2.4);
        const luminancia = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
        raiz.style.setProperty("--accent", cor);
        raiz.style.setProperty("--button-text", luminancia > 0.42 ? "#1d1d1f" : "#ffffff");
    }
    if (seletorCor) {
        aplicarCorBotao(seletorCor.value);
        seletorCor.addEventListener("input", () => aplicarCorBotao(seletorCor.value));
    }

    const filtroEtiquetas = document.querySelector("[data-filtro-etiquetas]");
    const formularioLote = document.querySelector("[data-form-etiquetas]");
    const itensBem = Array.from(document.querySelectorAll(".item-bem[data-etiquetado]"));
    const selecaoGeral = document.querySelector("[data-selecionar-todos]");
    const caixasSelecao = Array.from(document.querySelectorAll(".checkbox-selecao-bem"));
    const botaoLote = formularioLote?.querySelector("button[type='submit']");
    const contadorSelecao = document.querySelector("[data-contagem-etiquetas]");
    const resultadoLote = document.querySelector("[data-resultado-lote]");

    function filtrarItens(limparSelecao = true) {
        const valor = filtroEtiquetas?.value || "todos";
        itensBem.forEach((item) => {
            item.hidden = valor !== "todos" && item.dataset.etiquetado !== valor;
        });
        if (limparSelecao) {
            caixasSelecao.forEach((caixa) => { caixa.checked = false; });
            if (selecaoGeral) selecaoGeral.checked = false;
        }
        atualizarContagem();
    }
    function atualizarContagem() {
        const visiveis = caixasSelecao.filter((caixa) => !caixa.closest(".item-bem")?.hidden);
        const selecionados = caixasSelecao.filter((caixa) => caixa.checked).length;
        if (contadorSelecao) contadorSelecao.textContent = `${selecionados} selecionado(s)`;
        if (botaoLote) botaoLote.disabled = selecionados === 0;
        if (selecaoGeral) {
            selecaoGeral.checked = visiveis.length > 0 && visiveis.every((caixa) => caixa.checked);
            selecaoGeral.indeterminate = visiveis.some((caixa) => caixa.checked) && !selecaoGeral.checked;
        }
    }

    function atualizarEtiqueta(item, etiquetado) {
        const valor = Number(etiquetado);
        item.dataset.etiquetado = String(valor);
        const botao = item.querySelector(".status-botao");
        if (!botao) return;
        botao.disabled = false;
        botao.classList.toggle("status-sim", valor === 1);
        botao.classList.toggle("status-nao", valor === 0);
        botao.textContent = valor === 1 ? "Etiquetado" : "Sem etiqueta";
        botao.setAttribute("aria-label", `Alterar status da etiqueta de ${botao.dataset.patrimonio}`);
        filtrarItens(false);
    }
    filtroEtiquetas?.addEventListener("change", filtrarItens);
    selecaoGeral?.addEventListener("change", () => {
        caixasSelecao.forEach((caixa) => {
            if (!caixa.closest(".item-bem")?.hidden) caixa.checked = selecaoGeral.checked;
        });
        atualizarContagem();
    });
    caixasSelecao.forEach((caixa) => caixa.addEventListener("change", atualizarContagem));
    atualizarContagem();

    document.querySelectorAll(".form-status-etiqueta").forEach((formulario) => {
        formulario.addEventListener("submit", async (evento) => {
            evento.preventDefault();
            const botao = formulario.querySelector("button[type='submit']");
            botao.disabled = true;
            try {
                const resposta = await fetch(formulario.action, {
                    method: "POST",
                    body: new FormData(formulario),
                    headers: { "X-Requested-With": "XMLHttpRequest" }
                });
                if (!resposta.ok) throw new Error("Não foi possível atualizar a etiqueta.");
                const dados = await resposta.json();
                atualizarEtiqueta(formulario.closest(".item-bem"), dados.etiquetado);
            } catch (erro) {
                botao.disabled = false;
                botao.title = erro.message;
            }
        });
    });

    formularioLote?.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        if (!caixasSelecao.some((caixa) => caixa.checked)) return;
        botaoLote.disabled = true;
        formularioLote.setAttribute("aria-busy", "true");
        resultadoLote.textContent = "Atualizando os bens…";
        try {
            const resposta = await fetch(formularioLote.action, {
                method: "POST",
                body: new FormData(formularioLote),
                headers: { "X-Requested-With": "XMLHttpRequest" }
            });
            const dados = await resposta.json();
            if (!resposta.ok) throw new Error(dados.erro || "Não foi possível atualizar os bens.");
            const selecionados = caixasSelecao.filter((caixa) => caixa.checked);
            selecionados.forEach((caixa) => {
                const item = caixa.closest(".item-bem");
                caixa.checked = false;
                atualizarEtiqueta(item, dados.etiquetado);
            });
            resultadoLote.textContent = `Status atualizado em ${dados.atualizados} bem(ns).`;
            atualizarContagem();
        } catch (erro) {
            resultadoLote.textContent = erro.message;
            atualizarContagem();
        } finally {
            formularioLote.removeAttribute("aria-busy");
        }
    });

    document.querySelectorAll(".form-check").forEach((formulario) => {
        formulario.addEventListener("submit", async (evento) => {
            evento.preventDefault();
            const caixa = formulario.querySelector("input[type='checkbox']");
            caixa.disabled = true;
            try {
                const resposta = await fetch(formulario.action, {
                    method: "POST",
                    body: new FormData(formulario),
                    headers: { "X-Requested-With": "XMLHttpRequest" }
                });
                if (!resposta.ok) throw new Error("Não foi possível salvar a conferência.");
                const dados = await resposta.json();
                formulario.closest(".item-bem")?.classList.toggle("item-conferido", dados.conferido);
            } catch (_) {
                caixa.checked = !caixa.checked;
            } finally {
                caixa.disabled = false;
            }
        });
    });

    const modalQr = document.querySelector(".qrcode-dialog");
    if (modalQr) {
        const imagemQr = modalQr.querySelector(".qrcode-modal-imagem");
        const tituloQr = modalQr.querySelector("#titulo-modal-qr");

        document.querySelectorAll(".abrir-qr").forEach((botao) => {
            botao.addEventListener("click", () => {
                imagemQr.src = botao.dataset.qrUrl;
                imagemQr.alt = botao.dataset.qrTitulo;
                tituloQr.textContent = botao.dataset.qrTitulo;
                modalQr.showModal();
            });
        });

        modalQr.querySelector(".fechar-modal-qr").addEventListener("click", () => modalQr.close());
        modalQr.addEventListener("click", (evento) => {
            if (evento.target === modalQr) modalQr.close();
        });
    }

    function fechar(notificacao) {
        if (!notificacao || notificacao.classList.contains("saindo")) return;
        notificacao.classList.add("saindo");
        window.setTimeout(() => notificacao.remove(), 320);
    }

    document.querySelectorAll(".notificacao").forEach((notificacao) => {
        const botaoFechar = notificacao.querySelector(".fechar-notificacao");
        if (botaoFechar) botaoFechar.addEventListener("click", () => fechar(notificacao));
        const duracao = notificacao.querySelector("a") ? 4000 : 2400;
        window.setTimeout(() => fechar(notificacao), duracao);
    });
})();