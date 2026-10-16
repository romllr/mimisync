# Investigação do pacote Windows 0.2.0

Estado: **ZIP original retirado; investigação do alerta original aberta. Candidato nativo atualizado aprovado para publicação somente após repetir a validação completa dos bytes finais.**

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

## Conclusão atual

### Melhoria da instalação, sem conclusão sobre o alerta

A preparação do Windows passou a chamar diretamente `ShellExecuteExW` com o verbo `runas`, usando o caminho de `wsl.exe` obtido de `GetSystemDirectoryW`. O app não precisa mais iniciar PowerShell nem interpretar uma linha de script para habilitar o WSL. O Windows mantém o diálogo normal de consentimento de administrador. Cancelamento, falha e solicitação de reinício continuam tratados na interface; a preparação do backend continua pelo botão do app.

Esta mudança reduz intermediários e usa a API própria do sistema para elevação. **Não identifica a causa de `Ulthar.A!ml`, não é evidência de falso positivo e não libera um novo executável para download.** A varredura anterior analisou os bytes antigos; não deve ser atribuída a esta alteração. O fluxo de UAC/instalação requer validação em Windows 11 com proteção ativa, indisponível neste ambiente Linux e na tentativa anterior do runner.

Verificação desta alteração: compilação release cruzada `x86_64-pc-windows-gnu`, com `custom-protocol`, dependências travadas e modo offline concluída em 16/10/2026. Nenhum executável foi executado ou republicado. A autenticação GitHub disponível nesta sessão retornou HTTP 401; a consulta Git também ficou sem credenciais, impedindo publicar esta mudança a partir desta sessão.

- O relato do Defender do usuário permanece válido e sem causa esclarecida.
- O usuário informou que o bloqueio ocorreu durante o download, antes de extrair/abrir o app. Esse registro não demonstra execução do aplicativo no computador dele.
- Não há diagnóstico suficiente para declarar o pacote seguro ou falso positivo.
- O ZIP original e sua Release continuam retirados. O novo preview nativo só pode ser publicado pelos requisitos de validação descritos acima; não renomear ou reempacotar o ZIP original para contornar a detecção.
- A causa do alerta original segue sem diagnóstico. A verificação do candidato atualizado conseguiu ativar as proteções e verificar a conexão com a Microsoft. Nenhuma amostra foi enviada manualmente a um portal de terceiros nesta investigação; o runner usa o envio de amostras seguras do próprio Defender.
