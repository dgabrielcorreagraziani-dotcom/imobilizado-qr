from io import BytesIO
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as sistema
from openpyxl import Workbook


class SistemaTests(unittest.TestCase):
    def setUp(self):
        self.diretorio = tempfile.TemporaryDirectory()
        self.configuracao_anterior = {
            chave: sistema.app.config[chave]
            for chave in ("DATABASE_PATH", "TESTING", "SECRET_KEY")
        }
        sistema.app.config.update(
            DATABASE_PATH=Path(self.diretorio.name) / "teste.db",
            TESTING=True,
            SECRET_KEY="chave-de-teste",
        )
        with patch.dict(os.environ, {
            "ADMIN_USERNAME": "admin_teste",
            "ADMIN_PASSWORD": "senha-admin-teste-123",
        }):
            sistema.criar_banco()
        sistema.limiter.reset()
        self.cliente = sistema.app.test_client()

    def tearDown(self):
        sistema.app.config.update(self.configuracao_anterior)
        self.diretorio.cleanup()

    def autenticar_admin(self):
        with self.cliente.session_transaction() as sessao:
            sessao.update(usuario_id=1, nome_usuario="admin_teste", perfil="admin")

    def postar_com_csrf(self, caminho, **kwargs):
        pagina = self.cliente.get("/login")
        token = re.search(
            rb'name="csrf_token" value="([^"]+)"', pagina.data
        ).group(1).decode()
        dados = dict(kwargs.pop("data", {}))
        dados["csrf_token"] = token
        return self.cliente.post(caminho, data=dados, **kwargs)

    def test_conta_publica_e_criada_com_perfil_user(self):
        resposta = self.postar_com_csrf("/criar-conta", data={
            "usuario": "novo_usuario",
            "senha": "senha-segura-123",
            "perfil": "admin",
        })

        self.assertEqual(resposta.status_code, 302)
        with sistema.conectar_banco() as conexao:
            usuario = conexao.execute(
                "SELECT perfil, senha_hash FROM usuarios WHERE nome_usuario = ?",
                ("novo_usuario",),
            ).fetchone()
        self.assertIsNotNone(usuario)
        self.assertEqual(usuario["perfil"], "user")
        self.assertNotEqual(usuario["senha_hash"], "senha-segura-123")

    def test_conta_publica_rejeita_usuario_invalido_e_duplicado(self):
        for dados in (
            {"usuario": "x", "senha": "senha-segura-123"},
            {"usuario": "novo_usuario", "senha": "curta"},
            {"usuario": "ADMIN_TESTE", "senha": "senha-segura-123"},
        ):
            with self.subTest(dados=dados):
                self.postar_com_csrf("/criar-conta", data=dados)

        with sistema.conectar_banco() as conexao:
            total = conexao.execute(
                "SELECT COUNT(*) AS total FROM usuarios"
            ).fetchone()["total"]
        self.assertEqual(total, 1)

    def test_numero_de_sala_extenso_e_rejeitado_sem_excecao(self):
        erro = sistema.validar_dados_bem(
            "BEM-001", "Cadeira", "9" * 5000, "Móvel", ""
        )

        self.assertEqual(erro, "Informe um número de sala válido.")

    def test_usuario_cadastrado_pode_entrar_mas_nao_administrar(self):
        self.postar_com_csrf("/criar-conta", data={
            "usuario": "novo_usuario",
            "senha": "senha-segura-123",
        })
        resposta = self.postar_com_csrf("/login", data={
            "usuario": "novo_usuario",
            "senha": "senha-segura-123",
        })

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(self.cliente.get("/").status_code, 200)
        self.assertEqual(self.cliente.get("/usuarios").status_code, 403)

    def test_cadastro_publico_aparece_na_tela_de_login(self):
        resposta = self.cliente.get("/login")
        self.assertIn(b"Criar conta", resposta.data)

    def test_importacao_excel_respeita_coluna_de_etiquetado(self):
        self.autenticar_admin()
        with sistema.conectar_banco() as conexao:
            conexao.execute(
                "INSERT INTO salas (numero, nome, token_publico) VALUES (?, ?, ?)",
                ("12", "Teste", "token-teste"),
            )
        planilha = Workbook()
        folha = planilha.active
        folha.append(["Patrimônio", "Descrição", "Tipo", "Etiquetado"])
        folha.append(["BEM-001", "Cadeira", "Móvel", "Não"])
        folha.append(["BEM-002", "Mesa", "Móvel", "Sim"])
        arquivo = BytesIO()
        planilha.save(arquivo)
        arquivo.seek(0)

        self.postar_com_csrf(
            "/sala/1/importar-bens",
            data={"arquivo": (arquivo, "bens.xlsx")},
            content_type="multipart/form-data",
        )

        with sistema.conectar_banco() as conexao:
            estados = conexao.execute(
                "SELECT patrimonio, etiquetado FROM bens ORDER BY patrimonio"
            ).fetchall()
        self.assertEqual(
            [(item["patrimonio"], item["etiquetado"]) for item in estados],
            [("BEM-001", 0), ("BEM-002", 1)],
        )

    def test_cadastro_duplicado_nao_cria_sugestoes_orfas(self):
        self.autenticar_admin()
        with sistema.conectar_banco() as conexao:
            conexao.execute(
                "INSERT INTO salas (numero, nome, token_publico) VALUES (?, ?, ?)",
                ("12", "Teste", "token-teste"),
            )
            conexao.execute(
                "INSERT INTO bens (patrimonio, descricao, sala_id, tipo) VALUES (?, ?, ?, ?)",
                ("BEM-001", "Cadeira", 1, "MÓVEL"),
            )
            contagens = (
                conexao.execute("SELECT COUNT(*) FROM tipos_bens").fetchone()[0],
                conexao.execute("SELECT COUNT(*) FROM descricoes_bens").fetchone()[0],
            )

        self.postar_com_csrf("/cadastrar-bem", data={
            "patrimonio": "BEM-001",
            "descricao": "Descrição órfã",
            "numero_sala": "12",
            "tipo": "Tipo órfão",
            "etiquetado": "0",
        })

        with sistema.conectar_banco() as conexao:
            contagens_finais = (
                conexao.execute("SELECT COUNT(*) FROM tipos_bens").fetchone()[0],
                conexao.execute("SELECT COUNT(*) FROM descricoes_bens").fetchone()[0],
            )
        self.assertEqual(contagens_finais, contagens)

    def test_post_sem_token_csrf_e_rejeitado(self):
        respostas = [
            self.cliente.post("/criar-conta", data={
                "usuario": "novo_usuario",
                "senha": "senha-segura-123",
            }),
        ]
        self.cliente.get("/login")
        respostas.append(self.cliente.post("/criar-conta", data={
            "usuario": "novo_usuario",
            "senha": "senha-segura-123",
            "csrf_token": "token-invalido",
        }))

        self.assertEqual([resposta.status_code for resposta in respostas], [400, 400])
        with sistema.conectar_banco() as conexao:
            total = conexao.execute(
                "SELECT COUNT(*) AS total FROM usuarios"
            ).fetchone()["total"]
        self.assertEqual(total, 1)

    def test_paginas_com_operacoes_post_expoem_token_csrf(self):
        self.autenticar_admin()
        with sistema.conectar_banco() as conexao:
            conexao.execute(
                "INSERT INTO salas (numero, nome, token_publico) VALUES (?, ?, ?)",
                ("12", "Teste", "token-teste"),
            )

        for caminho in (
            "/",
            "/usuarios",
            "/minha-conta",
            "/pesquisar-bens",
            "/sala/1",
            "/sala/1/conferencia",
        ):
            with self.subTest(caminho=caminho):
                resposta = self.cliente.get(caminho)
                self.assertEqual(resposta.status_code, 200)
                self.assertIn(b'meta name="csrf-token"', resposta.data)
                if b'method="POST"' in resposta.data:
                    self.assertIn(b'name="csrf_token"', resposta.data)

    def test_login_tem_limite_de_tentativas(self):
        respostas = [
            self.postar_com_csrf("/login", data={
                "usuario": "nao_existe",
                "senha": "senha-incorreta",
            })
            for _ in range(6)
        ]

        self.assertEqual([resposta.status_code for resposta in respostas[:5]], [200] * 5)
        self.assertEqual(respostas[5].status_code, 429)

    def test_cadastro_publico_tem_limite_de_requisicoes(self):
        respostas = [
            self.postar_com_csrf("/criar-conta", data={
                "usuario": f"novo_usuario_{indice}",
                "senha": "senha-segura-123",
            })
            for indice in range(4)
        ]

        self.assertEqual([resposta.status_code for resposta in respostas[:3]], [302] * 3)
        self.assertEqual(respostas[3].status_code, 429)


if __name__ == "__main__":
    unittest.main()
