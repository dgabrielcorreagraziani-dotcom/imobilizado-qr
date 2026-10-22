from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import sqlite3
import qrcode
import qrcode.image.svg
import socket
import re
import unicodedata
from io import BytesIO
from pathlib import Path

app = Flask(__name__)
app.secret_key = "chave-local-desenvolvimento"

PORTA = 5000
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


@app.errorhandler(413)
def arquivo_acima_limite(_erro):
    sala_id = (request.view_args or {}).get("sala_id")
    if sala_id:
        flash("O arquivo deve ter no máximo 8 MB.")
        return redirect(url_for("abrir_sala", sala_id=sala_id))
    return "O arquivo deve ter no máximo 8 MB.", 413


def conectar_banco():
    conexao = sqlite3.connect("database.db")
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def criar_banco():
    with conectar_banco() as conexao:
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS salas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE
            )
        """)

        colunas_salas = {
            linha["name"]
            for linha in conexao.execute("PRAGMA table_info(salas)")
        }

        if "numero" not in colunas_salas:
            conexao.execute("ALTER TABLE salas ADD COLUMN numero TEXT")

        conexao.execute("""
            UPDATE salas
            SET numero = CAST(id AS TEXT)
            WHERE numero IS NULL OR TRIM(numero) = ''
        """)

        conexao.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_salas_numero
            ON salas(numero)
        """)

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS bens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patrimonio TEXT NOT NULL UNIQUE,
                descricao TEXT NOT NULL,
                sala_id INTEGER NOT NULL,
                FOREIGN KEY (sala_id) REFERENCES salas(id)
            )
        """)

        colunas_bens = {
            linha["name"]
            for linha in conexao.execute("PRAGMA table_info(bens)")
        }

        if "etiquetado" not in colunas_bens:
            conexao.execute("""
                ALTER TABLE bens
                ADD COLUMN etiquetado INTEGER NOT NULL DEFAULT 0
            """)

        if "tipo" not in colunas_bens:
            conexao.execute("""
                ALTER TABLE bens
                ADD COLUMN tipo TEXT NOT NULL DEFAULT ''
            """)

        if "conferido" not in colunas_bens:
            conexao.execute("""
                ALTER TABLE bens
                ADD COLUMN conferido INTEGER NOT NULL DEFAULT 0
            """)

        if "estado" not in colunas_bens:
            conexao.execute("""
                ALTER TABLE bens
                ADD COLUMN estado TEXT NOT NULL DEFAULT ''
            """)

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS tipos_bens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE
            )
        """)

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS descricoes_bens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL COLLATE NOCASE UNIQUE
            )
        """)

        tipos_antigos = conexao.execute("""
            SELECT DISTINCT UPPER(TRIM(tipo)) AS nome
            FROM bens
            WHERE tipo IS NOT NULL AND TRIM(tipo) <> ''
        """).fetchall()

        for tipo in tipos_antigos:
            conexao.execute("""
                INSERT OR IGNORE INTO tipos_bens (nome)
                VALUES (?)
            """, (tipo["nome"],))

        descricoes_antigas = conexao.execute("""
            SELECT DISTINCT TRIM(descricao) AS nome
            FROM bens
            WHERE descricao IS NOT NULL AND TRIM(descricao) <> ''
        """).fetchall()

        for descricao in descricoes_antigas:
            conexao.execute("""
                INSERT OR IGNORE INTO descricoes_bens (nome)
                VALUES (?)
            """, (descricao["nome"],))


def salvar_tipo(conexao, tipo):
    tipo = tipo.strip().upper()

    if tipo:
        conexao.execute("""
            INSERT OR IGNORE INTO tipos_bens (nome)
            VALUES (?)
        """, (tipo,))

    return tipo


def salvar_descricao(conexao, descricao):
    descricao = descricao.strip()

    if descricao:
        conexao.execute("""
            INSERT OR IGNORE INTO descricoes_bens (nome)
            VALUES (?)
        """, (descricao,))

    return descricao


def normalizar_cabecalho(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(letra for letra in texto if not unicodedata.combining(letra))
    return re.sub(r"[^a-z0-9]", "", texto.lower())


ALIAS_COLUNAS = {
    "patrimonio": {
        "patrimonio", "npatrimonio", "nrpatrimonio", "numeropatrimonio",
        "numerodopatrimonio", "numpatrimonio", "codigopatrimonio",
        "tombamento", "plaqueta", "numerotombo", "codigo", "cod"
    },
    "descricao": {"descricao", "descricaobem", "descricaodobem", "descricaoadicional", "nomebem", "especificacao", "item"},
    "tipo": {"tipo", "tipobem", "categoria", "classe", "descricaoativofixo"},
    "estado": {"estado", "condicao", "estadoconservacao"},
    "etiquetado": {"etiquetado", "possuietiqueta", "temetiqueta", "etiqueta"},
}


def mapa_colunas(cabecalho):
    mapa = {}
    for indice, valor in enumerate(cabecalho):
        nome = normalizar_cabecalho(valor)
        for campo, aliases in ALIAS_COLUNAS.items():
            if nome in aliases and campo not in mapa:
                mapa[campo] = indice
    if "patrimonio" in mapa and "descricao" in mapa:
        return mapa
    return None


def texto_celula(valor):
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def extrair_registros(tabelas):
    registros = []
    encontrou_cabecalho = False

    for linhas in tabelas:
        mapa = None
        for linha in linhas:
            linha = list(linha or [])
            novo_mapa = mapa_colunas(linha)
            if novo_mapa:
                mapa = novo_mapa
                encontrou_cabecalho = True
                continue
            if not mapa:
                continue

            def valor(campo):
                indice = mapa.get(campo)
                return texto_celula(linha[indice]) if indice is not None and indice < len(linha) else ""

            patrimonio = valor("patrimonio")
            descricao = valor("descricao")
            if patrimonio or descricao or valor("tipo") or valor("etiquetado") or valor("estado"):
                registros.append({
                    "patrimonio": patrimonio,
                    "descricao": descricao,
                    "tipo": valor("tipo").upper() or "NÃO INFORMADO",
                    "estado": valor("estado"),
                    "etiquetado": valor("etiquetado").lower() in {
                        "sim", "s", "yes", "y", "1", "x", "true", "etiquetado"
                    },
                })

    return registros, encontrou_cabecalho


def ler_excel(conteudo, extensao):
    tabelas = []
    if extensao == ".xlsx":
        from openpyxl import load_workbook
        arquivo = load_workbook(BytesIO(conteudo), read_only=True, data_only=True)
        try:
            tabelas = [list(planilha.iter_rows(values_only=True)) for planilha in arquivo.worksheets]
        finally:
            arquivo.close()
    else:
        import xlrd
        arquivo = xlrd.open_workbook(file_contents=conteudo, on_demand=True)
        try:
            tabelas = [
                [planilha.row_values(indice) for indice in range(planilha.nrows)]
                for planilha in arquivo.sheets()
            ]
        finally:
            arquivo.release_resources()
    return extrair_registros(tabelas)


def ler_pdf(conteudo):
    import pdfplumber
    tabelas = []
    with pdfplumber.open(BytesIO(conteudo)) as arquivo:
        for pagina in arquivo.pages:
            tabelas_pagina = pagina.extract_tables() or []
            if tabelas_pagina:
                tabelas.extend(tabelas_pagina)
                continue

            texto = pagina.extract_text() or ""
            linhas = [
                re.split(r"\t+|[|;]+|\s{2,}", linha.strip())
                for linha in texto.splitlines()
                if linha.strip()
            ]
            tabelas.append(linhas)
    return extrair_registros(tabelas)


def obter_ip_local():
    conexao = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        conexao.connect(("8.8.8.8", 80))
        ip = conexao.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        conexao.close()

    return ip


@app.route("/")
def inicio():
    with conectar_banco() as conexao:
        salas = conexao.execute("""
            SELECT salas.*, COUNT(bens.id) AS total_bens
            FROM salas
            LEFT JOIN bens ON bens.sala_id = salas.id
            GROUP BY salas.id
            ORDER BY CAST(salas.numero AS INTEGER), salas.numero
        """).fetchall()

    return render_template("index.html", salas=salas)


@app.route("/cadastrar-sala", methods=["POST"])
def cadastrar_sala():
    numero = request.form.get("numero", "").strip()
    nome = request.form.get("nome", "").strip()

    if not numero.isdigit() or not nome:
        flash("Informe um número válido e o nome da sala.")
        return redirect(url_for("inicio"))

    try:
        with conectar_banco() as conexao:
            conexao.execute("""
                INSERT INTO salas (numero, nome)
                VALUES (?, ?)
            """, (numero, nome))

        flash("Sala cadastrada com sucesso.")

    except sqlite3.IntegrityError:
        flash("Esse número ou nome de sala já está cadastrado.")

    return redirect(url_for("inicio"))


@app.route("/abrir-sala", methods=["POST"])
def buscar_sala():
    numero = request.form.get("numero_sala", "").strip()

    with conectar_banco() as conexao:
        sala = conexao.execute("""
            SELECT id FROM salas WHERE numero = ?
        """, (numero,)).fetchone()

    if sala is None:
        flash("Sala não encontrada.")
        return redirect(url_for("inicio"))

    return redirect(url_for("abrir_sala", sala_id=sala["id"]))


@app.route("/excluir-sala/<int:sala_id>", methods=["POST"])
def excluir_sala(sala_id):
    with conectar_banco() as conexao:
        sala = conexao.execute("""
            SELECT id, numero, nome FROM salas WHERE id = ?
        """, (sala_id,)).fetchone()

        if sala is None:
            flash("Sala não encontrada.")
            return redirect(url_for("inicio"))

        total_bens = conexao.execute("""
            SELECT COUNT(*) AS total
            FROM bens WHERE sala_id = ?
        """, (sala_id,)).fetchone()["total"]

        if total_bens > 0:
            flash("Não é possível apagar uma sala que contém bens.")
            return redirect(url_for("inicio"))

        conexao.execute(
            "DELETE FROM salas WHERE id = ?", (sala_id,)
        )

    flash(f"Sala {sala['numero']} - {sala['nome']} apagada.")
    return redirect(url_for("inicio"))


@app.route("/sala/<int:sala_id>")
def abrir_sala(sala_id):
    with conectar_banco() as conexao:
        sala = conexao.execute("""
            SELECT * FROM salas WHERE id = ?
        """, (sala_id,)).fetchone()

        if sala is None:
            return "Sala não encontrada.", 404

        bens = conexao.execute("""
            SELECT * FROM bens
            WHERE sala_id = ?
            ORDER BY patrimonio
        """, (sala_id,)).fetchall()

    return render_template("sala.html", sala=sala, bens=bens)


@app.route("/sala/<int:sala_id>/bem/<int:bem_id>/alternar-etiqueta", methods=["POST"])
def alternar_etiqueta(sala_id, bem_id):
    with conectar_banco() as conexao:
        cursor = conexao.execute("""
            UPDATE bens
            SET etiquetado = CASE WHEN etiquetado = 1 THEN 0 ELSE 1 END
            WHERE id = ? AND sala_id = ?
        """, (bem_id, sala_id))

        if cursor.rowcount == 0:
            return "Bem não encontrado nesta sala.", 404

    return redirect(url_for("abrir_sala", sala_id=sala_id))


@app.route("/sala/<int:sala_id>/importar-bens", methods=["POST"])
def importar_bens(sala_id):
    arquivo = request.files.get("arquivo")
    extensao = Path(arquivo.filename or "").suffix.lower() if arquivo else ""

    with conectar_banco() as conexao:
        sala = conexao.execute(
            "SELECT id FROM salas WHERE id = ?", (sala_id,)
        ).fetchone()
        if sala is None:
            return "Sala não encontrada.", 404

        if not arquivo or not arquivo.filename:
            flash("Escolha um arquivo Excel ou PDF para importar.")
            return redirect(url_for("abrir_sala", sala_id=sala_id))

        if extensao not in {".xlsx", ".xls", ".pdf"}:
            flash("Use um arquivo .xlsx, .xls ou .pdf.")
            return redirect(url_for("abrir_sala", sala_id=sala_id))

        try:
            conteudo = arquivo.read(app.config["MAX_CONTENT_LENGTH"] + 1)
            if len(conteudo) > app.config["MAX_CONTENT_LENGTH"]:
                flash("O arquivo deve ter no máximo 8 MB.")
                return redirect(url_for("abrir_sala", sala_id=sala_id))

            if extensao == ".pdf":
                registros, encontrou_cabecalho = ler_pdf(conteudo)
            else:
                registros, encontrou_cabecalho = ler_excel(conteudo, extensao)
        except ModuleNotFoundError:
            flash("Faltam bibliotecas da importação. No terminal, execute: python -m pip install -r requirements.txt")
            return redirect(url_for("abrir_sala", sala_id=sala_id))
        except Exception:
            flash("Não foi possível ler o arquivo. Confira se ele não está protegido ou corrompido.")
            return redirect(url_for("abrir_sala", sala_id=sala_id))

        if not encontrou_cabecalho:
            flash("Não encontrei as colunas Patrimônio e Descrição no arquivo.")
            return redirect(url_for("abrir_sala", sala_id=sala_id))
        if not registros:
            flash("Encontrei os cabeçalhos, mas nenhuma linha válida para importar.")
            return redirect(url_for("abrir_sala", sala_id=sala_id))

        inseridos = 0
        duplicados = 0
        invalidos = 0
        vistos = set()

        for registro in registros:
            patrimonio = registro["patrimonio"].strip()
            descricao = registro["descricao"].strip()
            tipo = registro["tipo"].strip().upper()
            estado = registro["estado"].strip()

            if not patrimonio or not descricao or not tipo or len(patrimonio) > 120 or len(descricao) > 1000 or len(tipo) > 120 or len(estado) > 120:
                invalidos += 1
                continue
            if patrimonio.casefold() in vistos:
                duplicados += 1
                continue
            vistos.add(patrimonio.casefold())

            try:
                conexao.execute("""
                    INSERT INTO bens (patrimonio, descricao, sala_id, etiquetado, tipo, estado)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    patrimonio, descricao, sala_id,
                    1 if extensao in {".xlsx", ".xls"} or registro["etiquetado"] else 0,
                    tipo, estado
                ))
                salvar_tipo(conexao, tipo)
                salvar_descricao(conexao, descricao)
                inseridos += 1
            except sqlite3.IntegrityError:
                duplicados += 1

    flash(
        f"Importação concluída: {inseridos} item(ns) cadastrado(s), "
        f"{duplicados} duplicado(s) ignorado(s) e {invalidos} linha(s) inválida(s)."
    )
    return redirect(url_for("abrir_sala", sala_id=sala_id))


@app.route("/sala/<int:sala_id>/conferencia")
def conferencia_sala(sala_id):
    with conectar_banco() as conexao:
        sala = conexao.execute("""
            SELECT * FROM salas WHERE id = ?
        """, (sala_id,)).fetchone()

        if sala is None:
            return "Sala não encontrada.", 404

        bens = conexao.execute("""
            SELECT * FROM bens
            WHERE sala_id = ?
            ORDER BY patrimonio
        """, (sala_id,)).fetchall()

    return render_template("conferencia.html", sala=sala, bens=bens)


@app.route("/sala/<int:sala_id>/conferencia/<int:bem_id>", methods=["POST"])
def marcar_conferencia(sala_id, bem_id):
    conferido = 1 if request.form.get("conferido") == "1" else 0

    with conectar_banco() as conexao:
        cursor = conexao.execute("""
            UPDATE bens
            SET conferido = ?
            WHERE id = ? AND sala_id = ?
        """, (conferido, bem_id, sala_id))

        if not cursor.rowcount:
            flash("Bem não encontrado nesta sala.")
        else:
            flash("Item marcado como conferido." if conferido else "Marcação removida.")

    return redirect(url_for("conferencia_sala", sala_id=sala_id))


@app.route("/pesquisar-bens")
def pesquisar_bens():
    termo = request.args.get("q", "").strip()
    bem_id = request.args.get("bem_id", type=int)
    bem_selecionado = None

    with conectar_banco() as conexao:
        salas = conexao.execute("""
            SELECT id, numero, nome
            FROM salas
            ORDER BY CAST(numero AS INTEGER), numero
        """).fetchall()

        tipos = conexao.execute("""
            SELECT nome FROM tipos_bens
            ORDER BY nome
        """).fetchall()

        descricoes = conexao.execute("""
            SELECT nome FROM descricoes_bens
            ORDER BY nome COLLATE NOCASE
        """).fetchall()

        bens = []

        if termo:
            busca = f"%{termo}%"
            bens = conexao.execute("""
                SELECT bens.*,
                       salas.numero AS numero_sala,
                       salas.nome AS nome_sala
                FROM bens
                JOIN salas ON salas.id = bens.sala_id
                WHERE bens.patrimonio LIKE ?
                   OR bens.descricao LIKE ?
                   OR bens.tipo LIKE ?
                   OR salas.numero LIKE ?
                   OR salas.nome LIKE ?
                ORDER BY bens.patrimonio
            """, (busca, busca, busca, busca, busca)).fetchall()

            if bem_id is not None:
                bem_selecionado = next(
                    (bem for bem in bens if bem["id"] == bem_id), None
                )
            elif len(bens) == 1:
                bem_selecionado = bens[0]

    return render_template(
        "pesquisar_bens.html",
        bens=bens,
        salas=salas,
        tipos=tipos,
        descricoes=descricoes,
        termo=termo,
        bem_selecionado=bem_selecionado
    )


@app.route("/cadastrar-bem", methods=["POST"])
def cadastrar_bem():
    patrimonio = request.form.get("patrimonio", "").strip()
    descricao = request.form.get("descricao", "").strip()
    numero_sala = request.form.get("numero_sala", "").strip()
    tipo = request.form.get("tipo", "").strip()
    estado = request.form.get("estado", "").strip()
    etiquetado = 1 if request.form.get("etiquetado") == "1" else 0

    if not patrimonio or not descricao or not numero_sala or not tipo:
        flash("Preencha todos os campos, incluindo o tipo.")
        return redirect(url_for("pesquisar_bens"))

    with conectar_banco() as conexao:
        sala = conexao.execute("""
            SELECT id FROM salas WHERE numero = ?
        """, (numero_sala,)).fetchone()

        if sala is None:
            flash("A sala informada não existe.")
            return redirect(url_for("pesquisar_bens"))

        tipo = salvar_tipo(conexao, tipo)
        descricao = salvar_descricao(conexao, descricao)
        cadastrado = False

        try:
            conexao.execute("""
                INSERT INTO bens
                    (patrimonio, descricao, sala_id, etiquetado, tipo, estado)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                patrimonio, descricao, sala["id"], etiquetado, tipo, estado
            ))

            flash("Bem cadastrado com sucesso.")
            cadastrado = True

        except sqlite3.IntegrityError:
            flash("Esse número patrimonial já está cadastrado.")

    if cadastrado:
        return redirect(url_for("pesquisar_bens"))

    return redirect(url_for("pesquisar_bens", q=patrimonio))


@app.route("/editar-bem/<int:bem_id>", methods=["POST"])
def editar_bem(bem_id):
    patrimonio = request.form.get("patrimonio", "").strip()
    descricao = request.form.get("descricao", "").strip()
    numero_sala = request.form.get("numero_sala", "").strip()
    tipo = request.form.get("tipo", "").strip()
    estado = request.form.get("estado", "").strip()
    etiquetado = 1 if request.form.get("etiquetado") == "1" else 0
    termo = request.form.get("termo", "").strip()

    if not patrimonio or not descricao or not numero_sala or not tipo:
        flash("Preencha todos os campos, incluindo o tipo.")
        return redirect(url_for("pesquisar_bens", q=termo))

    with conectar_banco() as conexao:
        sala = conexao.execute("""
            SELECT id FROM salas WHERE numero = ?
        """, (numero_sala,)).fetchone()

        if sala is None:
            flash("A sala informada não existe.")
            return redirect(url_for("pesquisar_bens", q=termo))

        tipo = salvar_tipo(conexao, tipo)
        descricao = salvar_descricao(conexao, descricao)
        atualizado = False

        try:
            cursor = conexao.execute("""
                UPDATE bens
                SET patrimonio = ?,
                    descricao = ?,
                    sala_id = ?,
                    etiquetado = ?,
                    tipo = ?,
                    estado = ?
                WHERE id = ?
            """, (
                patrimonio, descricao, sala["id"],
                etiquetado, tipo, estado, bem_id
            ))

            if cursor.rowcount:
                flash("Bem atualizado com sucesso.")
                atualizado = True
            else:
                flash("Bem não encontrado.")

        except sqlite3.IntegrityError:
            flash("Esse número patrimonial já pertence a outro bem.")

    if atualizado:
        return redirect(url_for("pesquisar_bens"))

    return redirect(
        url_for("pesquisar_bens", q=termo or patrimonio, bem_id=bem_id)
    )


@app.route("/excluir-bem/<int:bem_id>", methods=["POST"])
def excluir_bem(bem_id):
    termo = request.form.get("termo", "").strip()

    with conectar_banco() as conexao:
        bem = conexao.execute("""
            SELECT id FROM bens WHERE id = ?
        """, (bem_id,)).fetchone()

        if bem is None:
            flash("Bem não encontrado.")
            return redirect(url_for("pesquisar_bens", q=termo))

        conexao.execute(
            "DELETE FROM bens WHERE id = ?", (bem_id,)
        )

    flash("Bem excluído com sucesso.")
    return redirect(url_for("pesquisar_bens", q=termo))


@app.route("/sala/<int:sala_id>/qrcode.svg")
def gerar_qr(sala_id):
    with conectar_banco() as conexao:
        sala = conexao.execute("""
            SELECT id FROM salas WHERE id = ?
        """, (sala_id,)).fetchone()

    if sala is None:
        return "Sala não encontrada.", 404

    ip = obter_ip_local()
    link_sala = f"http://{ip}:{PORTA}" + url_for(
        "abrir_sala", sala_id=sala_id
    )

    factory = qrcode.image.svg.SvgPathImage
    imagem = qrcode.make(link_sala, image_factory=factory, box_size=8, border=4)
    arquivo = BytesIO(imagem.to_string())
    arquivo.seek(0)

    return send_file(
        arquivo,
        mimetype="image/svg+xml",
        max_age=0
    )


if __name__ == "__main__":
    criar_banco()

    print("\nSistema de Imobilizado QR iniciado.")
    print(f"Computador: http://127.0.0.1:{PORTA}")
    print(f"Rede local: http://{obter_ip_local()}:{PORTA}\n")

    app.run(host="0.0.0.0", port=PORTA, debug=False)
