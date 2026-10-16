# Mimisync · Local AI Lip Sync

Aplicativo em desenvolvimento para Windows 11: React + TypeScript + Tauri 2, backend Python local, FFmpeg e motores oficiais em ambientes separados. Nenhum serviço pago de inferência é usado.

**Estado: versão experimental com instalação assistida; ainda sem homologação de inferência em GPU/Windows.** Não há checkpoint fictício, renderização simulada ou garantia de equivalência visual ao Sync.so. Confira [validação e limitações](docs/VALIDATION.md).

## O que está implementado

- Estúdio para importar MP4/MOV e MP3/WAV via diálogo nativo; inspeção FFprobe e streaming local com suporte a seek.
- Detecção NVIDIA/driver/VRAM via `nvidia-smi`, recomendação por memória livre e diagnóstico de CUDA dentro de cada venv.
- Assistente de primeira abertura com preparação automática do backend em WSL2; sem comandos manuais para o usuário.
- Cadastro MuseTalk 1.5, LatentSync 1.5 e 1.6; fontes oficiais fixadas por commit, ambientes Python 3.10 individuais, instalação separada de checkpoints, remoção e relatórios de compatibilidade.
- Adaptadores reais para `python -m scripts.inference`, usando os parâmetros/configurações das versões oficiais. Sem fallback fictício quando os modelos não funcionam.
- Presets Fast/Balanced/Quality; parâmetros específicos; prévias de 3–15 segundos; fila serial persistente em SQLite; cancelamento de subprocessos e logs.
- Composição facial executada pelos pipelines oficiais, sem GFPGAN/CodeFormer automático. Exportação H.264/AAC, comparação A/B sincronizada e salvamento nativo de resultados concluídos.

## Baixar e testar no Windows 11

[**Baixar ZIP portátil — sem instalar o app**](https://github.com/romllr/mimisync/releases/download/preview-0.2.0-portable.3/Mimisync-0.2.0-preview3-windows-x64-portable.zip) · [Relatório e detalhes do portátil](https://github.com/romllr/mimisync/releases/tag/preview-0.2.0-portable.3)

O portátil preview 3 corrige a perda das mensagens de erro do WSL durante a preparação. Se a importação falhar, abra “Detalhes da preparação” e use “Copiar detalhes”; o código `-1` sozinho não identifica a causa. Consulte [o diagnóstico de preparação](docs/SETUP-TROUBLESHOOTING.md).

No portátil, extraia a pasta inteira e abra `Mimisync.exe`. Não execute dentro do ZIP. Ele usa o WebView2 Runtime, normalmente já presente no Windows 11. Os dados continuam no perfil do Windows; o WSL2 e os modelos continuam necessários e são preparados pelo assistente. Portanto, o aplicativo dispensa instalador, mas não elimina as dependências de inferência.

[Instalador anterior — Windows preview 2](https://github.com/romllr/mimisync/releases/download/preview-0.2.0-2/Mimisync_0.2.0_x64-setup.exe) · [Release e relatório do Defender](https://github.com/romllr/mimisync/releases/tag/preview-0.2.0-2)

Abra o instalador e depois o Mimisync. O assistente prepara o backend pelo próprio app, sem CMD. Se precisar habilitar o WSL2, o Windows pede autorização de administrador e pode pedir uma reinicialização. Depois, selecione e instale o modelo pela interface; os checkpoints são baixados separadamente após revisão da licença. É necessário driver NVIDIA compatível e espaço para os ambientes e pesos.

O instalador nativo e o ZIP portátil passaram por verificações próprias do Defender atualizado, com proteção em tempo real, de downloads e em nuvem ativas, incluindo verificação de cada arquivo baixado do GitHub e dos conteúdos extraídos do ZIP. O relatório e o SHA-256 acompanham a Release. Isso não garante ausência universal de malware nem homologa a inferência em GPU; o preview ainda é experimental e não tem assinatura de editor.

**O ZIP antigo `Mimisync-0.2.0-windows-x64-test.zip` permanece retirado:** o Defender o marcou como `Trojan:Script/Ulthar.A!ml`, e a causa desse alerta não foi esclarecida. Não restaure esse arquivo. Se o novo instalador também gerar uma detecção de ameaça, mantenha o bloqueio e informe o alerta; não desative o antivírus nem adicione exclusões. Consulte [a investigação e seus limites](docs/SECURITY-INVESTIGATION.md).

## Desenvolvimento do desktop (opcional)

Para alterar o código, instale Node 24, Rust/MSVC, Visual Studio Build Tools com Desktop development with C++, Windows SDK e WebView2. Consulte os [pré-requisitos Tauri](https://v2.tauri.app/start/prerequisites/). Execute `npm ci` e `npm run desktop`. A interface de desenvolvimento também oferece a instalação assistida.

O backend é empacotado por `src-tauri/build.rs` dentro do executável. A instalação usa a imagem oficial Canonical de `cloud-images.ubuntu.com`, confere o SHA-256 publicado e importa um ambiente separado. O `runtime/bootstrap.sh` é executado pelo app dentro desse ambiente. O código não desabilita TLS, checksum ou assinaturas dos pacotes apt.

`npm run tauri -- build --features custom-protocol` gera o instalador NSIS no Windows. `.github/workflows/windows-release.yml` permite gerar instaladores no GitHub Actions. O backend e os pesos não precisam ser preparados na máquina de build: o backend fonte vai embutido, e os pesos são baixados na máquina do usuário após revisão das licenças.

Para desenvolvimento com um Ubuntu pessoal já preparado, o caminho antigo continua disponível explicitamente: `bash scripts/setup-backend.sh` no WSL e `scripts/dev-windows.ps1` no Windows. Esse caminho é opcional para desenvolvedores e não é necessário para usar o instalador de teste.

## Desenvolvimento e testes no Linux sem GPU

```bash
npm ci
npm run build
bash scripts/setup-backend.sh
# Interface apenas; a ponte de arquivos/inferência requer Tauri:
npm run dev
```

Para testar a API diretamente, sem Tauri:

```bash
export MIMISYNC_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
.venv/bin/python -m mimisync
# Outro terminal com a mesma variável:
curl -H "Authorization: Bearer $MIMISYNC_TOKEN" http://127.0.0.1:47831/health
```

Não publique esse token. `MIMISYNC_DATA` pode definir um diretório Linux alternativo; scripts upstream exigem caminhos ASCII sem espaços/metacaracteres. O padrão usa a pasta Linux do usuário, mesmo quando o projeto está em NTFS.

`MIMISYNC_WSL_PROJECT` é somente uma opção de desenvolvimento. O app instalado prepara o runtime dedicado quando necessário; não pressupõe um checkout do projeto na máquina do usuário.

## Estrutura

```text
src/                       interface React e ponte Tauri
src-tauri/                 supervisor Rust, IPC, importação e exportação nativas
backend/mimisync/catalog.py fontes, versões, requisitos e presets
backend/mimisync/models.py  ambientes, downloads e verificação
backend/mimisync/adapters.py contratos independentes dos motores oficiais
backend/mimisync/service.py fila serial e pipeline de renderização
backend/mimisync/media.py   FFprobe/FFmpeg e exportação
backend/tests/             testes de API, fila, processos e mídia real FFmpeg
```

Detalhes: [arquitetura](docs/ARCHITECTURE.md), [modelos/licenças](docs/MODELS.md), [validação](docs/VALIDATION.md).
