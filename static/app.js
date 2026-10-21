(() => {
    const raiz = document.documentElement;
    const chaveTema = "imobilizado-qr-tema";

    function obterTema() {
        try {
            const salvo = localStorage.getItem(chaveTema);
            if (salvo === "light" || salvo === "dark") return salvo;
        } catch (_) {
            // O tema continua funcionando mesmo quando o armazenamento está bloqueado.
        }

        return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }

    function aplicarTema(tema) {
        raiz.dataset.theme = tema;
        document.querySelectorAll(".theme-toggle").forEach((botao) => {
            const rotulo = botao.querySelector("span");
            if (rotulo) rotulo.textContent = tema === "dark" ? "Usar modo claro" : "Usar modo escuro";
            botao.setAttribute("aria-pressed", String(tema === "dark"));
        });
    }

    aplicarTema(obterTema());

    document.querySelectorAll(".theme-toggle").forEach((botao) => {
        botao.addEventListener("click", () => {
            const tema = raiz.dataset.theme === "dark" ? "light" : "dark";
            aplicarTema(tema);
            try {
                localStorage.setItem(chaveTema, tema);
            } catch (_) {
                // A escolha vale até a página ser fechada quando o armazenamento está bloqueado.
            }
        });
    });

    function fechar(notificacao) {
        if (!notificacao || notificacao.classList.contains("saindo")) return;
        notificacao.classList.add("saindo");
        window.setTimeout(() => notificacao.remove(), 320);
    }

    document.querySelectorAll(".notificacao").forEach((notificacao) => {
        const botaoFechar = notificacao.querySelector(".fechar-notificacao");
        if (botaoFechar) {
            botaoFechar.addEventListener("click", () => fechar(notificacao));
        }

        const duracao = notificacao.querySelector("a") ? 4000 : 2400;
        window.setTimeout(() => fechar(notificacao), duracao);
    });
})();
