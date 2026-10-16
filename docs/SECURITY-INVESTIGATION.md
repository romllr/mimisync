# Investigação do pacote Windows 0.2.0

Estado: **investigação aberta; downloads suspensos**.

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

## Conclusão atual

- O relato do Defender do usuário permanece válido e sem causa esclarecida.
- O usuário informou que o bloqueio ocorreu durante o download, antes de extrair/abrir o app. Esse registro não demonstra execução do aplicativo no computador dele.
- Não há diagnóstico suficiente para declarar o pacote seguro ou falso positivo.
- Os downloads e a publicação automática permanecem suspensos. Não substituir o pacote por outro build nem mudar nome/empacotamento para contornar a detecção.
- A investigação precisa de condições de proteção equivalentes às do cliente ou de análise do fornecedor do antivírus antes de uma decisão de liberação. Nenhuma amostra foi enviada manualmente a um portal de terceiros nesta investigação.
