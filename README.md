# Imobilizado QR

Aplicação Flask para cadastrar salas e bens patrimoniais, pesquisar e editar itens, guardar sugestões de tipo e descrição e gerar QR codes SVG para abrir salas na rede local. Cada sala também tem uma página de conferência, onde é possível marcar e desmarcar os bens encontrados.

Na tela inicial, o botão de planilha ao lado do QR Code de cada sala importa listas Excel (`.xlsx`/`.xls`) ou PDF de até 8 MB diretamente naquela sala. A lista deve ter cabeçalhos para Patrimônio e Descrição; Tipo, Estado e Etiquetado são opcionais. PDFs precisam conter texto selecionável, pois PDFs digitalizados como imagem não passam por OCR. Patrimônios que já existem são ignorados.

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

5. No próprio computador, abra http://127.0.0.1:5000. Para escanear o QR de uma sala por outro aparelho, deixe o computador e o celular na mesma rede Wi-Fi e permita o acesso do Python/Flask na rede privada do Windows, se o firewall perguntar. O QR aponta para o endereço local do computador.

O banco SQLite é criado como database.db na pasta do projeto e está excluído do Git para não enviar os registros locais.
