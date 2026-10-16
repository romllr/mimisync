# Validação

## Executado nesta máquina Linux sem GPU

- `npm run build`: TypeScript e bundle Vite aprovados.
- `python -m pytest backend/tests -q` (Python 3.10.22): 14 testes aprovados. Cobrem autenticação e escopo do token, catálogo com versões/checkpoints distintos, licenças, importação real FFprobe e byte ranges, recusa de render sem modelo, preparação/exportação FFmpeg com mídia sintética de teste, contratos CLI dos três adaptadores, recuperação do histórico e cancelamento de processo real e inicialização/encerramento da API loopback autenticada pelo CLI.
- `cargo check --locked --target x86_64-pc-windows-gnu`: aprovado com toolchain cruzada MinGW extraída de pacotes Debian verificados. Verifica tipos, comandos Tauri e recursos Windows; não executa o programa, não produz NSIS e não homologa MSVC/Windows real.
- `cargo build --locked --release --features tauri/custom-protocol --target x86_64-pc-windows-gnu`: executável Windows x64 gerado com interface embutida. Cabeçalho PE, subsistema GUI e tabela de DLLs inspecionados; loader WebView2 incluído no pacote. Isso não equivale a executá-lo no Windows.
- Dois testes Rust nativos para a saída UTF-16 do WSL e seleção exata do checksum oficial passaram. O bootstrap foi verificado com `bash -n`; a imagem oficial e seu manifesto foram consultados por HTTPS, e o nome do arquivo foi conferido na listagem Canonical.
- A nova ação de instalação completa é testada como orquestração (ambiente antes de checkpoints); não representa uma inferência em GPU.
- Os fixtures FFmpeg dos testes são padrões de vídeo/tons para testar mídia; nunca são exibidos como inferência ou demonstração de qualidade.

## Ainda precisa de homologação

- Instalação completa dos três ambientes CUDA e dos checkpoints, seguida de inferência de cada versão em GPU NVIDIA. Os testes dos argumentos não substituem essa execução.
- Comparação visual com fala real, oclusões, movimentos, detalhes labiais/dentários, identidade e consistência temporal.
- Instalação assistida completa em Windows real (UAC/reinicialização, download/importação WSL e bootstrap), desktop nativo Windows/MSVC, inicialização WSL2, diálogos, transferência de arquivos grandes, sincronização A/B e NSIS no Windows real.
- Qualidade de transcodificação com fontes VFR, HDR e rotação. Não há promessa de qualidade comercial sem medição.

O host desta implementação não expõe NVIDIA. O Hugging Face respondeu 403 na tentativa inicial de consultar os modelos; a política de rede foi ajustada posteriormente. A ausência de GPU continua impedindo a homologação de inferência. Nenhum checkpoint foi baixado ou substituído. O aplicativo exige instalação/verificação real antes de aceitar um render.

## Checklist para a primeira máquina Windows com GPU

1. Executar os testes do backend e compilar o Tauri no Windows.
2. Confirmar `nvidia-smi` no WSL; instalar MuseTalk; inspecionar `pip check` e teste CUDA do venv.
3. Baixar pesos, confirmar `artifacts.json`, revisão HF e commit de código.
4. Renderizar voz/vídeo de 3–5 s com rosto frontal; validar imagem/áudio, duração, resolução e sincronização manualmente.
5. Repetir com LatentSync 1.5 e 1.6 nos requisitos de VRAM correspondentes, respeitando licenças.
6. Testar cancelamento durante inferência e exportação, fila com dois renders, reinicialização e exportação de resultado.
7. Comparar parâmetros/presets em conteúdo representativo antes de selecionar defaults para produção.
