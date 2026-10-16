# Investigação do pacote Windows 0.2.0

Estado: **ZIP original retirado; causa do alerta original em investigação. Novo preview nativo publicado após validação completa do Defender e do download.**

## Relato confirmado

Em 16/10/2026, o usuário apresentou uma captura do Histórico de Proteção do Microsoft Defender: **Trojan:Script/Ulthar.A!ml**, gravidade **grave**, status **removido**, no download `Mimisync-0.2.0-windows-x64-test.zip`. O alerta mostrado é uma detecção de ameaça; não é apenas uma mensagem do SmartScreen sobre baixa reputação.

Não há conclusão de falso positivo. Não orientar usuários a restaurar o arquivo, executar mesmo assim, adicionar exclusões ou desativar o antivírus.

## Identificação do artefato

- ZIP SHA-256: `2cc6338ba6efaf0dffd48c44237d8d7c259dd59bee54c881bf01cbf504a3d861`
- Mimisync.exe no ZIP: `346fe9ff9abf65d3fa37fe18443853e674af79b4307c3f262f0fa0fc4c538202`
- WebView2Loader.dll no ZIP: `86545b66cdb0603bc26b626fb9ad610cb6e71f28d468f5ea66df23b03dda96d5`
- Fonte: commit `4119f91570f58571ff0c9d15ff91590bd80d5b82`, build cruzado Windows GNU feito no ambiente de desenvolvimento.
- Publicação do ZIP no Git: commit `b0b1beffe29010b1c9f0bb048466b03710b3f58b`.

O blob publicado foi comparado com o arquivo local e os checksums internos conferem. Isso confirma identidade/integridade, **não segurança**. O executável do app não contém assinatura Authenticode; isso, isoladamente, não explica nem invalida uma detecção Trojan do Defender.

## Medidas

- Retirar o ZIP da árvore atual de downloads.
- Colocar a Release em rascunho, incluindo o instalador nativo que apareceu depois do ZIP.
- Suspender publicação automática de executáveis.
- Preservar o histórico e as cópias locais para análise, sem executar os arquivos afetados.
- Preparar análise no Windows usando o Defender e os mesmos bytes do ZIP relatado; registrar hashes, versão do mecanismo, assinaturas e resultado real.

O instalador gerado no GitHub Windows é um artefato diferente e não será oferecido como alternativa segura sem análise. Build aprovado, checksum válido e recompilação não substituem uma avaliação antimalware.

## Resultados obtidos (16/10/2026)

### Varredura sob demanda: não reproduziu a detecção

[Execução 38924908396](https://github.com/romllr/mimisync/actions/runs/38924908396) e [relatório JSON](security/defender-run-38924908396.json).

O teste verificou o SHA-256 do ZIP original, o extraiu, conferiu os executáveis e fez uma varredura customizada pelo Defender, sem executar o app. O mecanismo `1.1.26090.9`, com assinaturas `1.461.56.0` atualizadas, não reportou detecções nessa varredura. A DLL WebView2 tem assinatura Authenticode válida; o app e o instalador nativo não são assinados.

**Limitação decisiva:** `RealTimeProtectionEnabled` estava `false` no runner. Uma varredura sob demanda nessas condições não reproduz o bloqueio de download mostrado pelo usuário. Este resultado não comprova falso positivo nem autoriza republicação.

### Tentativa com proteção em tempo real: inconclusiva

[Execução 38926124634](https://github.com/romllr/mimisync/actions/runs/38926124634) e [relatório JSON](security/defender-run-38926124634.json).

A etapa que exigia habilitar a proteção em tempo real falhou. Como consequência, a preparação das amostras não foi executada, e o relatório de varredura registrou `scan_incomplete`, sem arquivos analisados. Os arrays de detecções vazios desse segundo relatório **não são resultado negativo de uma varredura**. A proteção não foi contornada nem enfraquecida para fazer o teste passar.

Uma execução intermediária com a configuração antiga foi cancelada após identificar que a atualização do workflow ainda não estava no branch remoto; ela não é contada como análise adicional.

### App atualizado: proteção em tempo real ativa, nuvem desativada

[Execução 38929665537](https://github.com/romllr/mimisync/actions/runs/38929665537) e [relatório JSON](security/current-38929665537.json).

O código atualizado foi compilado no Windows com a toolchain nativa. O instalador e o executável foram analisados sem execução. O Defender estava atualizado e com proteção em tempo real ativa; não houve detecções. Entretanto, `MAPSReporting=0` e `DisableBlockAtFirstSeen=true`: a proteção em nuvem não estava ativa. Este teste não esclarece o bloqueio original por `Ulthar.A!ml`.

Uma verificação adicional foi preparada com proteção em tempo real, proteção de downloads/scripts, MAPS e bloqueio à primeira vista habilitados no runner isolado. Ela exige que `MpCmdRun -ValidateMapsConnection` confirme a conexão com o serviço da Microsoft. O consentimento de envio de amostras seguras é restrito a esse runner, que contém código público do projeto, sem os vídeos do usuário. Se esses requisitos não forem verificáveis, o relatório deve indicar a limitação e falhar, sem publicar executáveis.

### App atualizado: proteção em tempo real e nuvem verificadas

[Execução 38930626131](https://github.com/romllr/mimisync/actions/runs/38930626131) e [relatório JSON](security/current-38930626131.json).

O Defender atualizado analisou o executável e o instalador nativo do código `db86b6f1766182d14d7845acc84e74a98836a9be`, sem executar o app e sem detectar ameaças. A proteção em tempo real estava ativa. MAPS avançado, bloqueio à primeira vista, proteção de downloads e de scripts estavam habilitados. `MpCmdRun -ValidateMapsConnection` confirmou conexão com o serviço da Microsoft (código 0). Não houve erro de configuração nem arquivos removidos. Os hashes desse build estão no relatório.

Revisão: este resultado permite preparar um **novo preview nativo**, repetindo os mesmos requisitos de proteção sobre os arquivos efetivamente publicados. O workflow de publicação seleciona esse commit explicitamente, recompila, analisa os bytes finais, confere SHA-256, cria uma Release em rascunho, baixa o próprio asset do GitHub, confere seu hash e o analisa novamente antes de tornar a Release pública. Qualquer falha mantém o candidato sem publicação pública. A seleção fica registrada em `scripts/security/approved-release.json`.

Não há conclusão de falso positivo sobre o ZIP antigo, que permanece retirado. Não há garantia universal de ausência de malware nem validação de uso real de GUI/CUDA. O novo preview permanece sem assinatura Authenticode; a análise antimalware não substitui assinatura de editor nem testes de inferência em hardware NVIDIA.

### Preview 2 publicado: bytes finais e download verificados

[Execução 38931626918](https://github.com/romllr/mimisync/actions/runs/38931626918), [relatório final](security/current-38931626918.json) e [Release](https://github.com/romllr/mimisync/releases/tag/preview-0.2.0-2).

A compilação nativa final e a varredura passaram, com proteção em tempo real, em nuvem, de downloads e de scripts ativas e conexão MAPS verificada. O workflow baixou o próprio asset do GitHub, conferiu seu SHA-256, marcou sua origem como Internet e o analisou novamente, sem detecções, antes de tornar a Release pública. O relatório preserva o resultado e autoriza somente esse candidato. O instalador público foi também baixado neste ambiente sem execução: tamanho e SHA-256 correspondem ao relatório.

- Instalador: `Mimisync_0.2.0_x64-setup.exe`, 3.170.766 bytes.
- SHA-256: `b6ccb14f147a53c5e0e4673a1e26b2091bb1fdf7b1690d70f34a6ebbddadecb0`.
- Fonte: `db86b6f1766182d14d7845acc84e74a98836a9be`.
- Mecanismo Defender: `1.1.26090.9`; assinaturas: `1.461.56.0`.

Este resultado descreve esses arquivos nesse ambiente de análise. Não prova falso positivo do ZIP original, não garante o comportamento de todos os antivírus nem valida execução da interface ou inferência CUDA. O executável continua sem assinatura Authenticode. Diante de nova detecção, manter o bloqueio e registrar o alerta, sem exclusões.

## Conclusão atual

### Melhoria da instalação, sem conclusão sobre o alerta

A preparação do Windows passou a chamar diretamente `ShellExecuteExW` com o verbo `runas`, usando o caminho de `wsl.exe` obtido de `GetSystemDirectoryW`. O app não precisa mais iniciar PowerShell nem interpretar uma linha de script para habilitar o WSL. O Windows mantém o diálogo normal de consentimento de administrador. Cancelamento, falha e solicitação de reinício continuam tratados na interface; a preparação do backend continua pelo botão do app.

Esta mudança reduz intermediários e usa a API própria do sistema para elevação. **Não identifica a causa de `Ulthar.A!ml`, não é evidência de falso positivo e não libera um novo executável para download.** A varredura anterior analisou os bytes antigos; não deve ser atribuída a esta alteração. O fluxo de UAC/instalação requer validação em Windows 11 com proteção ativa, indisponível neste ambiente Linux e na tentativa anterior do runner.

Verificação desta alteração: compilação release cruzada `x86_64-pc-windows-gnu`, com `custom-protocol`, dependências travadas e modo offline concluída em 16/10/2026. Nenhum executável foi executado ou republicado. A autenticação GitHub disponível nesta sessão retornou HTTP 401; a consulta Git também ficou sem credenciais, impedindo publicar esta mudança a partir desta sessão.

- O relato do Defender do usuário permanece válido e sem causa esclarecida.
- O usuário informou que o bloqueio ocorreu durante o download, antes de extrair/abrir o app. Esse registro não demonstra execução do aplicativo no computador dele.
- Não há diagnóstico suficiente para declarar o ZIP original seguro ou falso positivo. O preview nativo atualizado tem os resultados próprios documentados acima.
- O ZIP original e sua Release continuam retirados. O novo preview nativo só pode ser publicado pelos requisitos de validação descritos acima; não renomear ou reempacotar o ZIP original para contornar a detecção.
- A causa do alerta original segue sem diagnóstico. A verificação do candidato atualizado conseguiu ativar as proteções e verificar a conexão com a Microsoft. Nenhuma amostra foi enviada manualmente a um portal de terceiros nesta investigação; o runner usa o envio de amostras seguras do próprio Defender.

## Versão portátil do preview 2

[Release portátil](https://github.com/romllr/mimisync/releases/tag/preview-0.2.0-portable.2), [execução 38935119716](https://github.com/romllr/mimisync/actions/runs/38935119716) e [relatório exato](security/portable-38935119716.json).

O portátil foi compilado com a toolchain Windows nativa a partir do mesmo commit de aplicação revisado (`db86b6f1766182d14d7845acc84e74a98836a9be`). Os bytes finais foram verificados separadamente; não se atribui a este build o resultado de outro executável. O ZIP e os conteúdos extraídos passaram por varredura do Defender atualizado, com proteção em tempo real, de downloads/scripts e em nuvem ativas e conexão MAPS verificada. O asset foi baixado do GitHub em rascunho, conferido por SHA-256, extraído e analisado de novo antes da publicação. Não houve detecções.

- Arquivo: `Mimisync-0.2.0-preview2-windows-x64-portable.zip`, 5.511.125 bytes.
- SHA-256: `c9cdbc2f47b37c9c1c0f7dcc8e5d4fabdbc43e0308f4b990d07c280224a54251`.
- O download público foi conferido neste ambiente sem execução: CRC do ZIP, todos os hashes do manifesto e presença do executável correspondem. São 620 entradas.
- A tabela de imports do PE foi inspecionada: somente DLLs do Windows, sem dependência de `WebView2Loader.dll` externo ou VC++ Redistributable adicional. O WebView2 Runtime continua necessário, normalmente presente no Windows 11.
- A aplicação dispensa instalador; dados permanecem no perfil do Windows. WSL2, ambientes Python/FFmpeg e modelos continuam necessários e são preparados pelo assistente. Não é um ambiente de inferência independente de instalações.
- A interface e a inferência CUDA não foram executadas nessa análise; o aplicativo continua experimental e sem assinatura digital.

Tentativas anteriores foram preservadas nos relatórios `portable-diagnostic-*.json`: a extração do instalador não encontrou um único executável com o hash esperado; outra máquina falhou na conexão MAPS (`0x80508015`); um erro de sintaxe no script impediu outra análise de iniciar. Nenhuma dessas tentativas publicou um portátil nem equivale a uma detecção de ameaça. O fluxo final usa compilação direta, atualização de assinaturas e inicialização da política antes do teste de conexão, além de validar a sintaxe dos scripts antes da compilação. O ZIP original bloqueado permanece retirado, sem diagnóstico de falso positivo.
