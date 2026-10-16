# Fontes, dependências e licenças

Fontes inspecionadas em 16/10/2026. O gerenciador fixa código por commit, consulta o SHA do repositório Hugging Face e grava `downloads.json` antes do download. Tentativas posteriores reutilizam essa revisão. `artifacts.json` registra tamanho e SHA-256 dos arquivos baixados; não representa assinatura dos autores. As transferências usam HTTPS com validação TLS. Não são usados mirrors de terceiros para substituir os modelos obrigatórios.

| Motor | Repositório oficial e commit | Checkpoint oficial | Face | VRAM |
|---|---|---|---|---|
| MuseTalk 1.5 | [TMElyralab/MuseTalk](https://github.com/TMElyralab/MuseTalk), `0a89dec45a0192b824e3cf4daf96c239440c5ed8` | [TMElyralab/MuseTalk](https://huggingface.co/TMElyralab/MuseTalk), `musetalkV15/unet.pth` + JSON | 256² | ~6 GB: estimativa de triagem, não mínimo oficial |
| LatentSync 1.5 | [bytedance/LatentSync](https://github.com/bytedance/LatentSync/tree/7b380d6adde7aa23cba4a53bb15cd5cfb3c168e7), `7b380d6adde7aa23cba4a53bb15cd5cfb3c168e7` | [ByteDance/LatentSync-1.5](https://huggingface.co/ByteDance/LatentSync-1.5) | 256² | 8 GB, documentação oficial |
| LatentSync 1.6 | [bytedance/LatentSync](https://github.com/bytedance/LatentSync), `a229c3948406bc2cf6eaf4873e662e70c6a04746` | [ByteDance/LatentSync-1.6](https://huggingface.co/ByteDance/LatentSync-1.6) | 512² | 18 GB, documentação oficial |

O código 1.5 é anterior ao lançamento 1.6 e usa `stage2.yaml`; 1.6 usa `stage2_512.yaml`. Checkpoints e venvs nunca são compartilhados entre essas versões. Não se baixa o arquivo 1.6 e o rotula como 1.5.

## Dependências

MuseTalk: Python 3.10, PyTorch 2.0.1 + cu118, torchvision 0.15.2, torchaudio 2.0.2, requirements oficiais, MMCV 2.0.1, MMDetection 3.1.0, MMPose 1.1.0, MMEngine 0.10.7. O instalador usa o índice oficial MMLab; se não houver wheel compatível e a extensão não compilar, a instalação falha e apresenta os logs. Não desabilita checagens para declarar sucesso.

LatentSync: Python 3.10 e requirements de cada revisão (PyTorch 2.5.1, CUDA 12.1 no índice upstream, Diffusers, decord, InsightFace e ONNX Runtime GPU, entre outros). `pip check`, CUDA e importação do CLI são verificados no ambiente individual. Isso **não** comprova que uma inferência completa tenha funcionado.

O gerenciador não instala drivers, CUDA Toolkit de compilação ou pacotes apt automaticamente. Instale pré-requisitos do sistema conforme os logs antes de tentar novamente. Extensões compiladas podem exigir toolchain adicional. Conflitos dos requirements upstream são erros visíveis, não motivo para trocar silenciosamente os modelos.

## Licenças e auxiliares

- [MuseTalk LICENSE](https://github.com/TMElyralab/MuseTalk/blob/0a89dec45a0192b824e3cf4daf96c239440c5ed8/LICENSE): MIT, com avisos de terceiros. Pesos auxiliares têm termos próprios.
- [LatentSync LICENSE](https://github.com/bytedance/LatentSync/blob/a229c3948406bc2cf6eaf4873e662e70c6a04746/LICENSE): Apache-2.0. Essa licença de código não substitui a de pesos auxiliares.
- [InsightFace](https://github.com/deepinsight/insightface#license): código MIT; modelos pré-treinados disponibilizados pelo projeto são para pesquisa não comercial. LatentSync carrega `buffalo_l` para detecção/landmarks. Uso comercial exige obter direitos apropriados ou uma alteração separada de integração, que não está implementada aqui.
- [SD VAE ft-mse](https://huggingface.co/stabilityai/sd-vae-ft-mse): revisar model card/licença OpenRAIL e restrições de distribuição/uso. O gerenciador mantém VAE local para inferência LatentSync offline.
- [Whisper tiny](https://huggingface.co/openai/whisper-tiny), [DWPose](https://huggingface.co/yzd-v/DWPose) e face parsing: consultar termos individuais. Os arquivos de face parsing são distribuídos em [ManyOtherFunctions/face-parse-bisent](https://huggingface.co/ManyOtherFunctions/face-parse-bisent), a origem indicada pelo script Windows oficial do MuseTalk; o programa não afirma que são pesos publicados pelo autor do MuseTalk.
- S3FD: o detector facial incluído no MuseTalk usa o arquivo oficial `https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth`. O gerenciador baixa esse auxiliar explicitamente e verifica o prefixo SHA-256 publicado (`619a316812`), evitando download implícito na primeira inferência. Revisar os avisos de terceiros no LICENSE do MuseTalk.
- FFmpeg/libx264 têm obrigações de licença próprias. O protótipo usa a instalação externa; não redistribui um build FFmpeg.

O checkbox da interface registra que o usuário revisou os termos para aquela ação; não concede direitos e não resolve automaticamente restrições de uso comercial.

## Downloads e rede

Necessários: GitHub e seus assets, PyPI, `download.pytorch.org`, `download.openmmlab.com`, `www.adrianbulat.com`, `huggingface.co`, CDN/Xet associados ao Hugging Face. Nenhum vídeo/áudio é enviado a esses destinos; são downloads de dependências/modelos. Em uso já preparado, inferência usa arquivos locais. Não solicite chaves de API paga.

Sem acesso/credencial a um arquivo, a instalação deve falhar. Não coloque tokens no chat, em scripts versionados ou na interface. Se necessário, configure autenticação Hugging Face de forma segura no ambiente WSL. Downloads grandes podem concluir o arquivo atual antes que o cancelamento seja observado; o cancelamento não faz rollback dos arquivos já baixados.

## Presets

| Preset | MuseTalk batch (FP16) | LatentSync passos / guidance | CRF H.264 |
|---|---|---|---|
| Fast | 8 | 20 / 1.5 | 20 |
| Balanced | 4 | 30 / 1.5 | 18 |
| Quality | 2 | 50 / 1.5 | 16 |

MuseTalk não é um modelo de difusão; não inventamos um parâmetro de passos para ele. Batch menor reduz pico de memória, sem promessa de maior fidelidade. Quality aumenta passos do LatentSync e reduz perdas de exportação; não garante resultado superior em toda entrada. Os parâmetros avançados só substituem o preset quando o painel está aberto.
