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

## Para abrir e testar no Windows

Baixe o ZIP na [Release 0.2.0](https://github.com/romllr/mimisync/releases/tag/v0.2.0), extraia a pasta inteira e abra **Mimisync.exe**. Mantenha `WebView2Loader.dll` ao lado do executável.

**Não precisa abrir CMD, configurar Python, instalar Node/Rust ou preparar o backend manualmente.**

Na primeira abertura:

1. O assistente verifica os componentes do Windows. Se necessário, clique em **Habilitar componentes do Windows**. O próprio Windows pede autorização de administrador e pode solicitar reinicialização; depois abra o Mimisync novamente.
2. Clique em **Instalar componentes necessários**. O app baixa a imagem oficial Ubuntu 22.04 (com verificação SHA-256), cria a distribuição WSL2 exclusiva `Mimisync-Ubuntu` e instala FFmpeg, Python e o backend embutido no executável.
3. O estúdio abre na página de modelos. Revise as licenças, selecione **Instalar modelo** no MuseTalk 1.5 e aguarde. O app prepara o ambiente isolado e baixa os checkpoints em sequência.
4. Importe vídeo e áudio e comece por uma prévia curta.

Requer Windows 11 x64, virtualização/WSL2, WebView2, internet para a primeira instalação e GPU NVIDIA com driver atualizado e VRAM suficiente. A instalação não baixa um driver NVIDIA nem altera a configuração de BIOS. Os pesos de IA podem ocupar vários GB; reserve pelo menos 20 GB por modelo. MuseTalk ~6 GB de VRAM é estimativa de triagem; LatentSync 1.5 exige 8 GB e 1.6 exige 18 GB segundo os autores.

O app controla somente sua distribuição WSL dedicada. Instalações pessoais do Ubuntu não são usadas para o fluxo de teste. O backend fica em `/opt/mimisync`, os modelos e trabalhos em `/home/mimisync/.local/share/mimisync` e os arquivos de preparação/logs do Windows em `%LOCALAPPDATA%/app.mimisync.desktop`. A interface mostra erros e permite repetir a preparação ou reparar os componentes sem comandos manuais.

**A instalação assistida e a inferência ainda precisam da homologação de vocês no Windows real.** A compilação cruzada não substitui esse teste. Não há inferência simulada nem promessa de qualidade comercial sem avaliação.

## Desenvolvimento do desktop (opcional)

Para alterar o código, instale Node 24, Rust/MSVC, Visual Studio Build Tools com Desktop development with C++, Windows SDK e WebView2. Consulte os [pré-requisitos Tauri](https://v2.tauri.app/start/prerequisites/). Execute `npm ci` e `npm run desktop`. A interface de desenvolvimento também oferece a instalação assistida.

O backend é empacotado por `src-tauri/build.rs` dentro do executável. A instalação usa a imagem oficial Canonical de `cloud-images.ubuntu.com`, confere o SHA-256 publicado e importa um ambiente separado. O `runtime/bootstrap.sh` é executado pelo app dentro desse ambiente. O código não desabilita TLS, checksum ou assinaturas dos pacotes apt.

`npm run tauri -- build --features custom-protocol` gera o instalador NSIS no Windows. `.github/workflows/windows-release.yml` permite gerar instaladores no GitHub Actions. O backend e os pesos não precisam ser preparados na máquina de build: o backend fonte vai embutido, e os pesos são baixados na máquina do usuário após revisão das licenças.

Para desenvolvimento com um Ubuntu pessoal já preparado, o caminho antigo continua disponível explicitamente: `bash scripts/setup-backend.sh` no WSL e `scripts/dev-windows.ps1` no Windows. Esse caminho é opcional para desenvolvedores e não é necessário para testar o ZIP.

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

`MIMISYNC_WSL_PROJECT` é somente uma opção de desenvolvimento. O ZIP de teste abre diretamente pelo executável e prepara o runtime dedicado quando necessário; não pressupõe um checkout do projeto na máquina do usuário.

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
