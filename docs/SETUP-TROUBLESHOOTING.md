# Preparação no Windows

## Ubuntu verificado, falha ao criar o ambiente

No relato recebido, o download passou no SHA-256 oficial e o processo parou em “Criando um ambiente exclusivo do Mimisync”, com código `-1`. O app anterior podia perder a saída UTF-16LE do WSL ao lê-la como linhas UTF-8, particularmente quando a mensagem tinha acentos. Assim, o print não contém o diagnóstico real da importação.

O portátil preview 3 preserva os dois canais de saída, linhas parciais, UTF-16LE e UTF-8, e inclui as últimas mensagens na falha, com o código também em hexadecimal. A causa da importação do usuário ainda não foi estabelecida: esta atualização corrige a coleta do erro, não promete corrigir virtualização, kernel, serviço ou outra configuração do Windows.

1. Feche o app anterior, extraia o ZIP preview 3 em uma pasta e abra o novo `Mimisync.exe`.
2. Tente preparar novamente pelo assistente.
3. Se falhar, abra “Detalhes da preparação”, clique em “Copiar detalhes” e compartilhe o texto para diagnóstico. Não precisa de CMD.

O diretório de dados e o ambiente dedicado continuam os mesmos. O app verifica se a imagem já baixada corresponde ao checksum oficial atual e a reutiliza quando corresponde. Não é necessário apagar arquivos ou reinstalar o WSL apenas para obter o novo log. Não orientar mudanças de BIOS, remoção de distribuições ou correções genéricas antes de ler a mensagem real.

## Verificação da atualização

Três testes Rust do protocolo passaram no Linux e no Windows, incluindo a reprodução de erro WSL com acentos, UTF-16 dividido entre leituras e uma última linha sem quebra, além de bytes UTF-8 inválidos que não podem interromper os logs. A compilação cruzada e a compilação nativa Windows passaram. A importação WSL deste computador e a inferência CUDA não foram reproduzidas no CI.

O ZIP final passou por análise própria do Defender, com proteção em tempo real e em nuvem ativas e conexão MAPS verificada, incluindo o download do GitHub e os arquivos extraídos, sem detecções. [Relatório exato](security/portable-38937903881.json).
