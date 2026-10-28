# Imobilizado QR

Sistema Flask para controlar salas e bens patrimoniais. O QR de cada sala é gerado em SVG quando solicitado; o arquivo da imagem não é salvo. O banco guarda os dados dos bens e um token aleatório por sala, usado no endereço público do espelho. A migração adiciona esse token ao `database.db` existente sem apagar os registros.

Ao ler o QR, a pessoa vê somente uma página de consulta dos bens daquela sala. Essa página não contém links para o gerenciamento, pesquisa, conferência ou outras salas. O restante do sistema exige login. O espelho é acessível a quem tiver o QR ou o respectivo endereço; portanto, trate as etiquetas como links de consulta compartilháveis.

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

4. Na primeira execução, configure a conta inicial de administrador e a chave da sessão. Se `ADMIN_PASSWORD` não estiver definida, o sistema gera uma senha inicial aleatória e a mostra no console. Guarde essa senha. Depois, crie e gerencie as demais contas pela tela Usuários:

   ```powershell
   $env:ADMIN_USERNAME = "admin"
   $env:ADMIN_PASSWORD = "defina-uma-senha-forte"
   $env:SECRET_KEY = "defina-uma-chave-aleatoria-longa"
   ```

5. Inicie o sistema:

   ```powershell
   py app.py
   ```

6. Abra `http://127.0.0.1:5000` e entre com a conta inicial. A tela de login também permite criar uma conta pública, que sempre recebe o perfil `user`. O administrador pode abrir **Usuários** para criar contas `user` e `admin`, mudar perfis e excluir contas. `user` pode usar o inventário; só `admin` pode administrar contas. Formulários e chamadas de alteração usam proteção CSRF; o login aceita até 5 tentativas por minuto e o cadastro público até 3 requisições por hora por endereço IP. As variáveis definidas no PowerShell valem para essa janela; configure `SECRET_KEY` no serviço de hospedagem para manter as sessões entre reinicializações.

O limitador usa armazenamento em memória por padrão, suficiente para uma única instância local. Em produção com múltiplos processos/servidores, configure `RATELIMIT_STORAGE_URI` com um armazenamento compartilhado, por exemplo Redis, para que o limite seja consistente entre instâncias. Se a aplicação estiver atrás de um proxy, configure o servidor para encaminhar o endereço do cliente de forma confiável antes de depender dos limites por IP.

## Testes

Com as dependências instaladas, execute a suíte de regressão no PowerShell:

```powershell
python -m unittest discover -s tests -v
```

## Acesso por QR entre redes diferentes

Para que celulares e computadores fora da rede da empresa abram o QR, hospede o Flask em um serviço acessível pela internet, configure HTTPS e defina `PUBLIC_BASE_URL` com o endereço público, por exemplo `https://inventario.empresa.com`. O QR usará esse endereço e abrirá apenas `/espelho/<token-da-sala>`. Sem essa configuração, o QR usa o endereço pelo qual a pessoa administrativa abriu o sistema, o que é adequado para uso local, mas não torna o servidor acessível pela internet.

O banco SQLite fica junto ao `app.py`, em `database.db`, independentemente da pasta de onde o programa for iniciado. Para aproximadamente 1.000 bens e poucos usuários simultâneos, ele é suficiente; mantenha backups regulares. Se vários usuários precisarem editar simultaneamente, planeje migrar para PostgreSQL.

A importação de listas Excel (`.xlsx`/`.xls`) e PDF com texto selecionável continua disponível no gerenciamento. PDFs digitalizados como imagem não passam por OCR. Patrimônios já cadastrados são ignorados.

## Histórico de ações

Nas telas autenticadas, o botão **Histórico** no canto inferior direito abre as 50 ações mais recentes, como cadastro e remoção de salas e bens, importações, alterações de etiquetas, conferências e administração de usuários. Os registros ficam salvos no banco de dados; ações anteriores à criação do histórico não são incluídas.
