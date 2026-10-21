# Imobilizado QR

Aplicação Flask para cadastrar salas e bens patrimoniais, pesquisar e editar itens, guardar sugestões de tipo e descrição e gerar QR codes para abrir salas na rede local.

## Requisitos

- Python 3.10 ou superior

## Instalação no Windows

1. Abra o PowerShell nesta pasta.
2. Crie e ative um ambiente virtual:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Instale as dependências:

   ```powershell
   pip install -r requirements.txt
   ```

4. Inicie o sistema:

   ```powershell
   py app.py
   ```

5. No próprio computador, abra http://127.0.0.1:5000. Para acessar por outro aparelho na mesma rede, use o endereço de rede local exibido no terminal.

O banco SQLite é criado como database.db na pasta do projeto e está excluído do Git para não enviar os registros locais.
