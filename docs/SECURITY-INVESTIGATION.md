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
